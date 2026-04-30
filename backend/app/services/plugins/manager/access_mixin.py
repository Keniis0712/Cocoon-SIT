from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupRoom,
    Cocoon,
    PluginChatGroupConfig,
    PluginDefinition,
    PluginGroupVisibility,
    PluginRunState,
    PluginTargetBinding,
    PluginUserConfig,
    User,
    UserGroupMember,
)
from app.services.plugins.manager.models import ShortLivedScope
from app.services.security.authorization_service import AuthorizationService

logger = logging.getLogger(__name__)


class PluginManagerAccessMixin:
    def _authorization_service(self, session: Session) -> AuthorizationService:
        container = session.info.get("container")
        service = getattr(container, "authorization_service", None)
        if isinstance(service, AuthorizationService):
            return service
        return AuthorizationService()

    def _resolve_rpc_user(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        id_key: str,
        username_key: str,
        subject: str,
    ) -> User:
        raw_id = str(payload.get(id_key) or "").strip()
        raw_username = str(payload.get(username_key) or "").strip()
        provided = bool(raw_id) + bool(raw_username)
        if provided != 1:
            raise ValueError(f"Exactly one of {id_key} or {username_key} is required for {subject}")
        if raw_id:
            user = session.get(User, raw_id)
            if not user:
                raise ValueError(f"{id_key} must reference an existing user")
            return user
        user = session.scalar(select(User).where(User.username == raw_username))
        if not user:
            raise ValueError(f"{username_key} must reference an existing user")
        return user

    def _resolve_im_user_id(
        self, session: Session, raw_value: Any, *, field_name: str
    ) -> str | None:
        normalized = str(raw_value or "").strip()
        if not normalized:
            return None
        if not session.get(User, normalized):
            raise ValueError(f"{field_name} must reference an existing user")
        return normalized

    def _im_client_request_id(
        self,
        *,
        plugin_id: str,
        message_kind: str,
        external_account_id: str,
        external_conversation_id: str,
        external_message_id: str,
    ) -> str:
        raw = "|".join(
            [
                plugin_id,
                message_kind,
                external_account_id,
                external_conversation_id,
                external_message_id,
            ]
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return f"plugin-im:{plugin_id}:{digest}"

    def _ensure_run_state(self, session: Session, plugin_id: str) -> PluginRunState:
        current = session.scalar(
            select(PluginRunState).where(PluginRunState.plugin_id == plugin_id)
        )
        if current:
            return current
        current = PluginRunState(plugin_id=plugin_id, status="stopped")
        session.add(current)
        session.flush()
        return current

    def _ensure_user_config(
        self, session: Session, plugin: PluginDefinition, user_id: str
    ) -> PluginUserConfig:
        current = session.scalar(
            select(PluginUserConfig).where(
                PluginUserConfig.plugin_id == plugin.id,
                PluginUserConfig.user_id == user_id,
            )
        )
        if current:
            return current
        current = PluginUserConfig(
            plugin_id=plugin.id,
            user_id=user_id,
            is_enabled=True,
            config_json=dict(plugin.user_default_config_json or {}),
        )
        session.add(current)
        session.flush()
        return current

    def _ensure_chat_group_config(
        self,
        session: Session,
        plugin: PluginDefinition,
        chat_group_id: str,
    ) -> PluginChatGroupConfig:
        current = session.scalar(
            select(PluginChatGroupConfig).where(
                PluginChatGroupConfig.plugin_id == plugin.id,
                PluginChatGroupConfig.chat_group_id == chat_group_id,
            )
        )
        if current:
            return current
        current = PluginChatGroupConfig(
            plugin_id=plugin.id,
            chat_group_id=chat_group_id,
            is_enabled=True,
            config_json=dict(plugin.user_default_config_json or {}),
        )
        session.add(current)
        session.flush()
        return current

    def _list_short_lived_scopes(
        self, session: Session, plugin: PluginDefinition
    ) -> list[ShortLivedScope]:
        rows = list(
            session.scalars(
                select(PluginTargetBinding)
                .where(PluginTargetBinding.plugin_id == plugin.id)
                .order_by(PluginTargetBinding.created_at.asc())
            ).all()
        )
        scopes: dict[tuple[str, str], ShortLivedScope] = {}
        for binding in rows:
            key = (binding.scope_type, binding.scope_id)
            if key in scopes:
                continue
            if binding.scope_type == "user":
                if not self._binding_target_exists(session, binding):
                    continue
                user_config = self._ensure_user_config(session, plugin, binding.scope_id)
                if not user_config.is_enabled or user_config.validation_error_text:
                    continue
                if not self._can_deliver_to_user(session, plugin, binding.scope_id):
                    continue
                user = session.get(User, binding.scope_id)
                scopes[key] = ShortLivedScope(
                    scope_type="user",
                    scope_id=binding.scope_id,
                    user_id=binding.scope_id,
                    config_json=dict(user_config.config_json or {}),
                    timezone=(user.timezone if user and user.timezone else "UTC"),
                )
            elif binding.scope_type == "chat_group":
                if not session.get(ChatGroupRoom, binding.scope_id):
                    continue
                group_config = self._ensure_chat_group_config(session, plugin, binding.scope_id)
                if not group_config.is_enabled or group_config.validation_error_text:
                    continue
                scopes[key] = ShortLivedScope(
                    scope_type="chat_group",
                    scope_id=binding.scope_id,
                    user_id=None,
                    config_json=dict(group_config.config_json or {}),
                    timezone=None,
                )
        return list(scopes.values())

    def _binding_target_exists(self, session: Session, binding: PluginTargetBinding) -> bool:
        if binding.target_type == "cocoon":
            return session.get(Cocoon, binding.target_id) is not None
        if binding.target_type == "chat_group":
            return session.get(ChatGroupRoom, binding.target_id) is not None
        return False

    def _can_deliver_to_user(
        self, session: Session, plugin: PluginDefinition, user_id: str
    ) -> bool:
        group_ids = [
            item.group_id
            for item in session.scalars(
                select(UserGroupMember).where(UserGroupMember.user_id == user_id)
            ).all()
        ]
        if group_ids:
            overrides = list(
                session.scalars(
                    select(PluginGroupVisibility).where(
                        PluginGroupVisibility.plugin_id == plugin.id,
                        PluginGroupVisibility.group_id.in_(group_ids),
                    )
                ).all()
            )
            if overrides:
                return any(item.is_visible for item in overrides)
        return bool(plugin.is_globally_visible)

    def _record_user_error(
        self, session: Session, *, plugin: PluginDefinition, user_id: str, message: str
    ) -> None:
        row = self._ensure_user_config(session, plugin, user_id)
        row.runtime_error_text = message.strip() or "Plugin runtime error"
        row.runtime_error_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()

    def _record_chat_group_error(
        self, session: Session, *, plugin: PluginDefinition, chat_group_id: str, message: str
    ) -> None:
        row = self._ensure_chat_group_config(session, plugin, chat_group_id)
        row.runtime_error_text = message.strip() or "Plugin runtime error"
        row.runtime_error_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()

    def _clear_user_error(self, session: Session, *, plugin_id: str, user_id: str) -> None:
        current = session.scalar(
            select(PluginUserConfig).where(
                PluginUserConfig.plugin_id == plugin_id,
                PluginUserConfig.user_id == user_id,
            )
        )
        if not current:
            return
        current.runtime_error_text = None
        current.runtime_error_at = None
        session.flush()
