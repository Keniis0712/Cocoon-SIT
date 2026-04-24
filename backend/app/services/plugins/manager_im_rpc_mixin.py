from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AvailableModel,
    Character,
    ChatGroupMember,
    ChatGroupRoom,
    Cocoon,
    PluginDefinition,
    PluginImTargetRoute,
    User,
)
from app.services.workspace.targets import ensure_session_state

logger = logging.getLogger(__name__)


class PluginImRpcMixin:
    def _handle_im_rpc_request(
        self, session: Session, *, plugin: PluginDefinition, payload: dict[str, Any]
    ) -> None:
        request_id = str(payload.get("request_id") or "").strip()
        method = str(payload.get("method") or "").strip()
        request_payload = dict(payload.get("payload") or {})
        handle = self._daemon_handles.get(plugin.id)
        if not request_id or not handle or handle.inbound_queue is None:
            return
        try:
            if method == "create_cocoon":
                response_payload = self._rpc_create_cocoon(session, request_payload)
            elif method == "create_chat_group":
                response_payload = self._rpc_create_chat_group(session, request_payload)
            elif method == "verify_user_binding":
                response_payload = self._rpc_verify_user_binding(session, request_payload)
            elif method == "list_accessible_targets":
                response_payload = self._rpc_list_accessible_targets(session, request_payload)
            elif method == "list_accessible_characters":
                response_payload = self._rpc_list_accessible_characters(session, request_payload)
            elif method == "upsert_im_target_route":
                response_payload = self._rpc_upsert_im_target_route(
                    session, plugin, request_payload
                )
            elif method == "delete_im_target_route":
                response_payload = self._rpc_delete_im_target_route(
                    session, plugin, request_payload
                )
            else:
                raise ValueError(f"Unsupported IM RPC method: {method}")
        except Exception as exc:  # noqa: BLE001
            handle.inbound_queue.put(
                {
                    "type": "rpc_response",
                    "request_id": request_id,
                    "ok": False,
                    "error": str(exc),
                    "payload": {},
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
            )
            return
        handle.inbound_queue.put(
            {
                "type": "rpc_response",
                "request_id": request_id,
                "ok": True,
                "error": None,
                "payload": response_payload,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )

    def _rpc_create_cocoon(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        owner = self._resolve_rpc_user(
            session,
            payload,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        character_id = str(payload.get("character_id") or "").strip()
        selected_model_id = str(payload.get("selected_model_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not character_id or not session.get(Character, character_id):
            raise ValueError("character_id must reference an existing character")
        if not selected_model_id or not session.get(AvailableModel, selected_model_id):
            raise ValueError("selected_model_id must reference an existing model")
        if not name:
            raise ValueError("name is required")
        cocoon_kwargs = {
            "name": name,
            "owner_user_id": owner.id,
            "character_id": character_id,
            "selected_model_id": selected_model_id,
            "parent_id": str(payload.get("parent_id") or "").strip() or None,
        }
        if payload.get("default_temperature") is not None:
            cocoon_kwargs["default_temperature"] = payload.get("default_temperature")
        if payload.get("max_context_messages") is not None:
            cocoon_kwargs["max_context_messages"] = payload.get("max_context_messages")
        if payload.get("auto_compaction_enabled") is not None:
            cocoon_kwargs["auto_compaction_enabled"] = payload.get("auto_compaction_enabled")
        cocoon = Cocoon(**cocoon_kwargs)
        session.add(cocoon)
        session.flush()
        ensure_session_state(session, cocoon_id=cocoon.id)
        session.flush()
        return {
            "id": cocoon.id,
            "name": cocoon.name,
            "owner_user_id": cocoon.owner_user_id,
            "owner_username": owner.username,
            "character_id": cocoon.character_id,
            "selected_model_id": cocoon.selected_model_id,
        }

    def _rpc_create_chat_group(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        owner = self._resolve_rpc_user(
            session,
            payload,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        character_id = str(payload.get("character_id") or "").strip()
        selected_model_id = str(payload.get("selected_model_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not character_id or not session.get(Character, character_id):
            raise ValueError("character_id must reference an existing character")
        if not selected_model_id or not session.get(AvailableModel, selected_model_id):
            raise ValueError("selected_model_id must reference an existing model")
        if not name:
            raise ValueError("name is required")
        room_kwargs = {
            "name": name,
            "owner_user_id": owner.id,
            "character_id": character_id,
            "selected_model_id": selected_model_id,
            "external_platform": str(payload.get("external_platform") or "").strip() or None,
            "external_group_id": str(payload.get("external_group_id") or "").strip() or None,
            "external_account_id": str(payload.get("external_account_id") or "").strip() or None,
        }
        if payload.get("default_temperature") is not None:
            room_kwargs["default_temperature"] = payload.get("default_temperature")
        if payload.get("max_context_messages") is not None:
            room_kwargs["max_context_messages"] = payload.get("max_context_messages")
        if payload.get("auto_compaction_enabled") is not None:
            room_kwargs["auto_compaction_enabled"] = payload.get("auto_compaction_enabled")
        room = ChatGroupRoom(**room_kwargs)
        session.add(room)
        session.flush()
        session.add(ChatGroupMember(room_id=room.id, user_id=owner.id, member_role="admin"))
        for user_id in payload.get("initial_member_ids") or []:
            normalized = str(user_id or "").strip()
            if not normalized or normalized == owner.id or not session.get(User, normalized):
                continue
            session.add(ChatGroupMember(room_id=room.id, user_id=normalized, member_role="member"))
        ensure_session_state(session, chat_group_id=room.id)
        session.flush()
        return {
            "id": room.id,
            "name": room.name,
            "owner_user_id": room.owner_user_id,
            "owner_username": owner.username,
            "character_id": room.character_id,
            "selected_model_id": room.selected_model_id,
        }

    def _rpc_verify_user_binding(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.im_bind_token_service.verify_user_token(
            session,
            username=str(payload.get("username") or ""),
            token=str(payload.get("token") or ""),
        )
        return {
            "user_id": user.id,
            "username": user.username,
        }

    def _rpc_list_accessible_targets(
        self, session: Session, payload: dict[str, Any]
    ) -> dict[str, Any]:
        user = self._resolve_rpc_user(
            session,
            payload,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        authorization_service = self._authorization_service(session)
        cocoons = list(session.scalars(select(Cocoon).order_by(Cocoon.created_at.desc())).all())
        rooms = list(
            session.scalars(select(ChatGroupRoom).order_by(ChatGroupRoom.created_at.desc())).all()
        )
        items: list[dict[str, Any]] = []
        for cocoon in authorization_service.filter_visible_cocoons(session, user, cocoons):
            items.append(
                {
                    "target_type": "cocoon",
                    "target_id": cocoon.id,
                    "name": cocoon.name,
                    "created_at": cocoon.created_at.isoformat() if cocoon.created_at else None,
                }
            )
        for room in authorization_service.filter_visible_chat_groups(session, user, rooms):
            items.append(
                {
                    "target_type": "chat_group",
                    "target_id": room.id,
                    "name": room.name,
                    "created_at": room.created_at.isoformat() if room.created_at else None,
                }
            )
        items.sort(
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("target_type") or ""),
                str(item.get("target_id") or ""),
            ),
            reverse=True,
        )
        return {"items": items}

    def _rpc_list_accessible_characters(
        self, session: Session, payload: dict[str, Any]
    ) -> dict[str, Any]:
        user = self._resolve_rpc_user(
            session,
            payload,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        authorization_service = self._authorization_service(session)
        characters = list(
            session.scalars(select(Character).order_by(Character.created_at.desc())).all()
        )
        items = [
            {
                "character_id": character.id,
                "name": character.name,
                "created_at": character.created_at.isoformat() if character.created_at else None,
            }
            for character in characters
            if authorization_service.can_use_character(session, user, character)
        ]
        return {"items": items}

    def _rpc_upsert_im_target_route(
        self, session: Session, plugin: PluginDefinition, payload: dict[str, Any]
    ) -> dict[str, Any]:
        target_type = str(payload.get("target_type") or "").strip()
        target_id = str(payload.get("target_id") or "").strip()
        external_platform = str(payload.get("external_platform") or "").strip()
        conversation_kind = str(payload.get("conversation_kind") or "").strip()
        external_account_id = str(payload.get("external_account_id") or "").strip()
        external_conversation_id = str(payload.get("external_conversation_id") or "").strip()
        metadata_json = dict(payload.get("metadata_json") or {})
        if target_type not in {"cocoon", "chat_group"} or not target_id:
            raise ValueError(
                "target_type must be 'cocoon' or 'chat_group' and target_id is required"
            )
        if conversation_kind not in {"private", "group"}:
            raise ValueError("conversation_kind must be 'private' or 'group'")
        if not external_platform or not external_account_id or not external_conversation_id:
            raise ValueError(
                "external_platform, external_account_id, and external_conversation_id are required"
            )
        if target_type == "cocoon":
            if not session.get(Cocoon, target_id):
                raise ValueError("target_id must reference an existing cocoon")
        elif not session.get(ChatGroupRoom, target_id):
            raise ValueError("target_id must reference an existing chat group")
        route = session.scalar(
            select(PluginImTargetRoute).where(
                PluginImTargetRoute.plugin_id == plugin.id,
                PluginImTargetRoute.external_platform == external_platform,
                PluginImTargetRoute.conversation_kind == conversation_kind,
                PluginImTargetRoute.external_account_id == external_account_id,
                PluginImTargetRoute.external_conversation_id == external_conversation_id,
            )
        )
        if route is None:
            route = PluginImTargetRoute(
                plugin_id=plugin.id,
                target_type=target_type,
                target_id=target_id,
                external_platform=external_platform,
                conversation_kind=conversation_kind,
                external_account_id=external_account_id,
                external_conversation_id=external_conversation_id,
                route_metadata_json=metadata_json,
            )
            session.add(route)
            session.flush()
        else:
            route.target_type = target_type
            route.target_id = target_id
            route.route_metadata_json = metadata_json
            session.flush()
        return {
            "id": route.id,
            "plugin_id": route.plugin_id,
            "target_type": route.target_type,
            "target_id": route.target_id,
            "external_platform": route.external_platform,
            "conversation_kind": route.conversation_kind,
            "external_account_id": route.external_account_id,
            "external_conversation_id": route.external_conversation_id,
        }

    def _rpc_delete_im_target_route(
        self, session: Session, plugin: PluginDefinition, payload: dict[str, Any]
    ) -> dict[str, Any]:
        external_platform = str(payload.get("external_platform") or "").strip()
        conversation_kind = str(payload.get("conversation_kind") or "").strip()
        external_account_id = str(payload.get("external_account_id") or "").strip()
        external_conversation_id = str(payload.get("external_conversation_id") or "").strip()
        if conversation_kind not in {"private", "group"}:
            raise ValueError("conversation_kind must be 'private' or 'group'")
        if not external_platform or not external_account_id or not external_conversation_id:
            raise ValueError(
                "external_platform, external_account_id, and external_conversation_id are required"
            )
        route = session.scalar(
            select(PluginImTargetRoute).where(
                PluginImTargetRoute.plugin_id == plugin.id,
                PluginImTargetRoute.external_platform == external_platform,
                PluginImTargetRoute.conversation_kind == conversation_kind,
                PluginImTargetRoute.external_account_id == external_account_id,
                PluginImTargetRoute.external_conversation_id == external_conversation_id,
            )
        )
        deleted = route is not None
        if route is not None:
            session.delete(route)
            session.flush()
        return {"deleted": deleted}
