from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PluginDefinition,
    PluginImDeliveryOutbox,
)
from app.services.plugins.im_delivery_service import PLUGIN_IM_SOURCE_KIND

logger = logging.getLogger(__name__)


class PluginImDeliveryMixin:
    def _dispatch_im_deliveries(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        for delivery_id, (_plugin_id, deadline) in list(self._im_deliveries_in_flight.items()):
            if deadline <= now:
                self._im_deliveries_in_flight.pop(delivery_id, None)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(PluginImDeliveryOutbox)
                    .where(
                        PluginImDeliveryOutbox.status.in_(("queued", "delivering")),
                        (
                            PluginImDeliveryOutbox.next_attempt_at.is_(None)
                            | (PluginImDeliveryOutbox.next_attempt_at <= now)
                        ),
                    )
                    .order_by(PluginImDeliveryOutbox.created_at.asc())
                ).all()
            )
            for row in rows:
                if row.id in self._im_deliveries_in_flight:
                    continue
                handle = self._daemon_handles.get(row.plugin_id)
                if (
                    not handle
                    or handle.process_type != "im"
                    or handle.inbound_queue is None
                    or not handle.process.is_alive()
                ):
                    continue
                try:
                    payload = dict(row.payload_json or {})
                    payload["delivery_id"] = row.id
                    handle.inbound_queue.put(
                        {
                            "type": "deliver_reply",
                            "delivery_id": row.id,
                            "reply": payload,
                            "occurred_at": datetime.now(UTC).isoformat(),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    row.status = "queued"
                    row.attempt_count = int(row.attempt_count or 0) + 1
                    row.last_error_text = str(exc)
                    row.next_attempt_at = now + timedelta(
                        seconds=min(60, max(1, 2 ** min(row.attempt_count, 5)))
                    )
                    continue
                row.status = "delivering"
                row.attempt_count = int(row.attempt_count or 0) + 1
                row.last_error_text = None
                row.next_attempt_at = now + timedelta(seconds=30)
                self._im_deliveries_in_flight[row.id] = (row.plugin_id, row.next_attempt_at)
            session.commit()

    def _handle_im_delivery_result(
        self, session: Session, *, plugin: PluginDefinition, payload: dict[str, Any]
    ) -> None:
        delivery_id = str(payload.get("delivery_id") or "").strip()
        if not delivery_id:
            return
        self._im_deliveries_in_flight.pop(delivery_id, None)
        row = session.get(PluginImDeliveryOutbox, delivery_id)
        if not row or row.plugin_id != plugin.id:
            return
        result = dict(payload.get("result") or {})
        if bool(result.get("ok")):
            row.status = "delivered"
            row.delivered_at = datetime.now(UTC).replace(tzinfo=None)
            row.last_error_text = None
            row.next_attempt_at = None
            return
        row.status = "queued" if bool(result.get("retryable", True)) else "failed"
        row.last_error_text = str(result.get("error") or "IM delivery failed")
        if row.status == "queued":
            row.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                seconds=min(60, max(1, 2 ** min(int(row.attempt_count or 1), 5)))
            )
        else:
            row.next_attempt_at = None

    def _ingest_im_inbound_message(
        self, session: Session, *, plugin: PluginDefinition, payload: dict[str, Any]
    ) -> None:
        message_kind = str(payload.get("message_kind") or "").strip()
        route = dict(payload.get("route") or {})
        target_type = str(route.get("target_type") or "").strip()
        target_id = str(route.get("target_id") or "").strip()
        if target_type not in {"cocoon", "chat_group"} or not target_id:
            raise ValueError(
                "IM inbound route must include target_type 'cocoon' or 'chat_group' and target_id"
            )
        message = dict(payload.get("message") or {})
        content = str(message.get("text") or "").strip()
        if not content:
            raise ValueError("IM inbound message text is required")
        external_message_id = str(message.get("message_id") or "").strip()
        if not external_message_id:
            raise ValueError("IM inbound message_id is required")
        client_request_id = self._im_client_request_id(
            plugin_id=plugin.id,
            message_kind=message_kind,
            external_account_id=str(message.get("account_id") or "").strip(),
            external_conversation_id=str(message.get("conversation_id") or "").strip(),
            external_message_id=external_message_id,
        )
        sender_user_id = self._resolve_im_user_id(
            session, message.get("sender_user_id"), field_name="sender_user_id"
        )
        owner_user_id = self._resolve_im_user_id(
            session, message.get("owner_user_id"), field_name="owner_user_id"
        )
        memory_owner_user_id = self._resolve_im_user_id(
            session,
            message.get("memory_owner_user_id"),
            field_name="memory_owner_user_id",
        )
        if memory_owner_user_id is None:
            memory_owner_user_id = owner_user_id or sender_user_id
        source_payload = {
            "source_kind": PLUGIN_IM_SOURCE_KIND,
            "source_plugin_id": plugin.id,
            "external_account_id": str(message.get("account_id") or "").strip() or None,
            "external_conversation_id": str(message.get("conversation_id") or "").strip() or None,
            "external_message_id": external_message_id,
            "external_sender_id": str(message.get("sender_id") or "").strip() or None,
            "external_sender_display_name": str(message.get("sender_display_name") or "").strip()
            or None,
            "sender_user_id": sender_user_id,
            "owner_user_id": owner_user_id,
            "memory_owner_user_id": memory_owner_user_id,
            "im_message_kind": message_kind,
            "im_route_metadata_json": dict(route.get("metadata_json") or {}),
            "im_metadata_json": {
                **dict(message.get("metadata_json") or {}),
                "raw_payload": dict(message.get("raw_payload") or {}),
                "occurred_at": str(message.get("occurred_at") or ""),
            },
        }
        if target_type == "cocoon":
            self.message_dispatch_service.enqueue_chat_message(
                session,
                target_id,
                content=content,
                client_request_id=client_request_id,
                timezone="UTC",
                sender_user_id=sender_user_id,
                external_sender_id=source_payload["external_sender_id"],
                external_sender_display_name=source_payload["external_sender_display_name"],
                extra_payload=source_payload,
            )
            return
        self.message_dispatch_service.enqueue_chat_group_message(
            session,
            target_id,
            content=content,
            client_request_id=client_request_id,
            timezone="UTC",
            sender_user_id=sender_user_id,
            external_sender_id=source_payload["external_sender_id"],
            external_sender_display_name=source_payload["external_sender_display_name"],
            extra_payload=source_payload,
        )
