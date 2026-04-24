from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, Message, PluginImDeliveryOutbox, PluginImTargetRoute


PLUGIN_IM_SOURCE_KIND = "plugin_im"


class PluginImDeliveryService:
    def is_im_source_action(self, action: ActionDispatch) -> bool:
        return str((action.payload_json or {}).get("source_kind") or "") == PLUGIN_IM_SOURCE_KIND

    def enqueue_reply(
        self,
        session: Session,
        *,
        action: ActionDispatch,
        message: Message,
    ) -> PluginImDeliveryOutbox | None:
        payload = dict(action.payload_json or {})
        if str(payload.get("source_kind") or "") == PLUGIN_IM_SOURCE_KIND:
            plugin_id = str(payload.get("source_plugin_id") or "").strip()
            if not plugin_id:
                return None
            return self._enqueue_single_reply(
                session,
                plugin_id=plugin_id,
                action=action,
                message=message,
                external_account_id=payload.get("external_account_id"),
                external_conversation_id=payload.get("external_conversation_id"),
                external_message_id=payload.get("external_message_id"),
                external_sender_id=payload.get("external_sender_id"),
                external_sender_display_name=payload.get("external_sender_display_name"),
                source_message_id=payload.get("message_id"),
                metadata_json=dict(payload.get("im_metadata_json") or {}),
            )
        if str(action.event_type or "").strip() != "wakeup":
            return None
        target_type = "chat_group" if action.chat_group_id else "cocoon"
        target_id = action.chat_group_id or action.cocoon_id
        if not target_id:
            return None
        routes = list(
            session.scalars(
                select(PluginImTargetRoute)
                .where(
                    PluginImTargetRoute.target_type == target_type,
                    PluginImTargetRoute.target_id == target_id,
                )
                .order_by(PluginImTargetRoute.created_at.asc())
            ).all()
        )
        first_outbox: PluginImDeliveryOutbox | None = None
        for route in routes:
            outbox = self._enqueue_single_reply(
                session,
                plugin_id=route.plugin_id,
                action=action,
                message=message,
                external_account_id=route.external_account_id,
                external_conversation_id=route.external_conversation_id,
                external_message_id=None,
                external_sender_id=None,
                external_sender_display_name=None,
                source_message_id=None,
                metadata_json=dict(route.route_metadata_json or {}),
            )
            if first_outbox is None:
                first_outbox = outbox
        return first_outbox

    def _enqueue_single_reply(
        self,
        session: Session,
        *,
        plugin_id: str,
        action: ActionDispatch,
        message: Message,
        external_account_id: str | None,
        external_conversation_id: str | None,
        external_message_id: str | None,
        external_sender_id: str | None,
        external_sender_display_name: str | None,
        source_message_id: str | None,
        metadata_json: dict,
    ) -> PluginImDeliveryOutbox:
        outbox = PluginImDeliveryOutbox(
            plugin_id=plugin_id,
            action_id=action.id,
            message_id=message.id,
            status="queued",
            payload_json={
                "plugin_id": plugin_id,
                "action_id": action.id,
                "message_id": message.id,
                "target_type": "chat_group" if action.chat_group_id else "cocoon",
                "target_id": action.chat_group_id or action.cocoon_id,
                "reply_text": message.content,
                "source_message_id": source_message_id,
                "external_account_id": external_account_id,
                "external_conversation_id": external_conversation_id,
                "external_message_id": external_message_id,
                "external_sender_id": external_sender_id,
                "external_sender_display_name": external_sender_display_name,
                "metadata_json": metadata_json,
                "created_at": datetime.now(UTC).isoformat(),
            },
            attempt_count=0,
            next_attempt_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(outbox)
        session.flush()
        return outbox
