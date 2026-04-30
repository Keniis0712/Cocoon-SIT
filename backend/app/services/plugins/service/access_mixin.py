from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupMember,
    ChatGroupRoom,
    Cocoon,
    PluginChatGroupConfig,
    PluginDefinition,
    PluginEventDefinition,
    PluginGroupVisibility,
    PluginTargetBinding,
    PluginUserConfig,
    PluginUserEventConfig,
    PluginVersion,
    User,
    UserGroupMember,
)
from app.schemas.workspace.plugins import (
    ChatGroupPluginConfigOut,
    UserPluginEventOut,
    UserPluginTargetBindingOut,
)
from app.services.plugins.runtime import validate_plugin_settings


class PluginServiceAccessMixin:
    def _require_bootstrap_admin(self, user: User) -> None:
        if user.username != self.settings.default_admin_username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only bootstrap admin can manage plugin visibility",
            )

    def _require_user_visible_plugin(
        self, session: Session, user: User, plugin_id: str
    ) -> PluginDefinition:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        return plugin

    def _require_user_can_bind_target(
        self, session: Session, user: User, target_type: str, target_id: str
    ) -> None:
        if target_type == "cocoon":
            target = session.get(Cocoon, target_id)
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Cocoon not found"
                )
            if target.owner_user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the cocoon owner can bind plugins",
                )
            return
        target = session.get(ChatGroupRoom, target_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat group not found"
            )
        if target.owner_user_id == user.id:
            return
        membership = session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == target_id,
                ChatGroupMember.user_id == user.id,
            )
        )
        if not membership or membership.member_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Chat group management denied"
            )

    def _require_user_can_manage_chat_group(
        self, session: Session, user: User, chat_group_id: str
    ) -> ChatGroupRoom:
        target = session.get(ChatGroupRoom, chat_group_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat group not found"
            )
        if target.owner_user_id == user.id:
            return target
        membership = session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == chat_group_id,
                ChatGroupMember.user_id == user.id,
            )
        )
        if not membership or membership.member_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Chat group management denied"
            )
        return target

    def _scope_for_binding_target(
        self,
        session: Session,
        user: User,
        target_type: str,
        target_id: str,
    ) -> tuple[str, str]:
        if target_type == "cocoon":
            target = session.get(Cocoon, target_id)
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Cocoon not found"
                )
            return "user", target.owner_user_id
        self._require_user_can_manage_chat_group(session, user, target_id)
        return "chat_group", target_id

    def _can_user_manage_binding_target(
        self, session: Session, user: User, binding: PluginTargetBinding
    ) -> bool:
        try:
            if binding.scope_type == "user" and binding.scope_id != user.id:
                return False
            if binding.scope_type == "chat_group":
                self._require_user_can_manage_chat_group(session, user, binding.scope_id)
                return True
            self._require_user_can_bind_target(
                session, user, binding.target_type, binding.target_id
            )
        except HTTPException:
            return False
        return True

    def _serialize_target_binding(
        self, session: Session, binding: PluginTargetBinding
    ) -> UserPluginTargetBindingOut:
        target_name = binding.target_id
        if binding.target_type == "cocoon":
            target = session.get(Cocoon, binding.target_id)
            target_name = target.name if target else binding.target_id
        elif binding.target_type == "chat_group":
            target = session.get(ChatGroupRoom, binding.target_id)
            target_name = target.name if target else binding.target_id
        return UserPluginTargetBindingOut(
            id=binding.id,
            plugin_id=binding.plugin_id,
            scope_type=binding.scope_type,
            scope_id=binding.scope_id,
            target_type=binding.target_type,
            target_id=binding.target_id,
            target_name=target_name,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )

    def _group_ids_for_user(self, session: Session, user_id: str) -> list[str]:
        return [
            item.group_id
            for item in session.scalars(
                select(UserGroupMember).where(UserGroupMember.user_id == user_id)
            ).all()
        ]

    def _group_visibility_map(
        self,
        session: Session,
        *,
        plugin_ids: list[str],
        group_ids: list[str],
    ) -> dict[str, list[bool]]:
        if not plugin_ids or not group_ids:
            return {}
        rows = list(
            session.scalars(
                select(PluginGroupVisibility).where(
                    PluginGroupVisibility.plugin_id.in_(plugin_ids),
                    PluginGroupVisibility.group_id.in_(group_ids),
                )
            ).all()
        )
        mapping: dict[str, list[bool]] = {}
        for item in rows:
            mapping.setdefault(item.plugin_id, []).append(bool(item.is_visible))
        return mapping

    def _resolve_plugin_visibility(
        self, plugin: PluginDefinition, group_overrides: list[bool]
    ) -> bool:
        if group_overrides:
            return any(group_overrides)
        return bool(plugin.is_globally_visible)

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

    def _ensure_user_event_config(
        self,
        session: Session,
        *,
        plugin_id: str,
        user_id: str,
        event_name: str,
    ) -> PluginUserEventConfig:
        current = session.scalar(
            select(PluginUserEventConfig).where(
                PluginUserEventConfig.plugin_id == plugin_id,
                PluginUserEventConfig.user_id == user_id,
                PluginUserEventConfig.event_name == event_name,
            )
        )
        if current:
            return current
        current = PluginUserEventConfig(
            plugin_id=plugin_id,
            user_id=user_id,
            event_name=event_name,
            schedule_mode="manual",
            schedule_interval_seconds=None,
            schedule_cron=None,
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

    def _refresh_user_config_validation(
        self,
        session: Session,
        plugin: PluginDefinition,
        user_config: PluginUserConfig,
    ) -> None:
        user_config.validation_error_text = None
        user_config.validation_error_at = None
        if not plugin.settings_validation_function_name:
            return
        if not plugin.active_version_id:
            return
        version = session.get(PluginVersion, plugin.active_version_id)
        if not version:
            return
        try:
            message = validate_plugin_settings(
                version.manifest_path,
                plugin.entry_module,
                plugin.settings_validation_function_name,
                plugin_name=plugin.name,
                plugin_version=version.version,
                plugin_config=dict(plugin.config_json or {}),
                user_config=dict(user_config.config_json or {}),
                user_id=user_config.user_id,
                data_dir=plugin.data_dir,
            )
        except Exception as exc:
            message = str(exc)
        if message:
            user_config.validation_error_text = message
            user_config.validation_error_at = datetime.now(UTC).replace(tzinfo=None)

    def _refresh_chat_group_config_validation(
        self,
        session: Session,
        plugin: PluginDefinition,
        chat_group_config: PluginChatGroupConfig,
    ) -> None:
        chat_group_config.validation_error_text = None
        chat_group_config.validation_error_at = None
        if not plugin.settings_validation_function_name:
            return
        if not plugin.active_version_id:
            return
        version = session.get(PluginVersion, plugin.active_version_id)
        if not version:
            return
        try:
            message = validate_plugin_settings(
                version.manifest_path,
                plugin.entry_module,
                plugin.settings_validation_function_name,
                plugin_name=plugin.name,
                plugin_version=version.version,
                plugin_config=dict(plugin.config_json or {}),
                user_config=dict(chat_group_config.config_json or {}),
                user_id=None,
                scope_type="chat_group",
                scope_id=chat_group_config.chat_group_id,
                data_dir=plugin.data_dir,
            )
        except Exception as exc:
            message = str(exc)
        if message:
            chat_group_config.validation_error_text = message
            chat_group_config.validation_error_at = datetime.now(UTC).replace(tzinfo=None)

    def _serialize_chat_group_plugin_config(
        self,
        plugin: PluginDefinition,
        chat_group_config: PluginChatGroupConfig,
    ) -> ChatGroupPluginConfigOut:
        return ChatGroupPluginConfigOut(
            plugin_id=plugin.id,
            chat_group_id=chat_group_config.chat_group_id,
            is_enabled=bool(chat_group_config.is_enabled),
            config_schema_json=dict(plugin.user_config_schema_json or {}),
            default_config_json=dict(plugin.user_default_config_json or {}),
            config_json=dict(chat_group_config.config_json or {}),
            error_text=(
                chat_group_config.validation_error_text or chat_group_config.runtime_error_text
            ),
            error_at=chat_group_config.validation_error_at or chat_group_config.runtime_error_at,
        )

    def _serialize_user_plugin(
        self,
        session: Session,
        plugin: PluginDefinition,
        user: User,
        user_config: PluginUserConfig | None,
        group_overrides: list[bool],
    ) -> dict:
        visible = self._resolve_plugin_visibility(plugin, group_overrides)
        events: list[UserPluginEventOut] = []
        if plugin.active_version_id:
            event_defs = list(
                session.scalars(
                    select(PluginEventDefinition).where(
                        PluginEventDefinition.plugin_id == plugin.id,
                        PluginEventDefinition.plugin_version_id == plugin.active_version_id,
                    )
                ).all()
            )
            event_schedule_map = {
                item.event_name: item
                for item in session.scalars(
                    select(PluginUserEventConfig).where(
                        PluginUserEventConfig.plugin_id == plugin.id,
                        PluginUserEventConfig.user_id == user.id,
                    )
                ).all()
            }
            events = [
                UserPluginEventOut(
                    name=item.name,
                    mode=item.mode,
                    function_name=item.function_name,
                    title=item.title,
                    description=item.description,
                    config_schema_json=dict(item.config_schema_json or {}),
                    default_config_json=dict(item.default_config_json or {}),
                    schedule_mode=(
                        event_schedule_map[item.name].schedule_mode
                        if item.name in event_schedule_map
                        else "manual"
                    ),
                    schedule_interval_seconds=(
                        event_schedule_map[item.name].schedule_interval_seconds
                        if item.name in event_schedule_map
                        else None
                    ),
                    schedule_cron=(
                        event_schedule_map[item.name].schedule_cron
                        if item.name in event_schedule_map
                        else None
                    ),
                )
                for item in event_defs
            ]
        return {
            "id": plugin.id,
            "name": plugin.name,
            "display_name": plugin.display_name,
            "plugin_type": plugin.plugin_type,
            "status": plugin.status,
            "is_globally_visible": bool(plugin.is_globally_visible),
            "is_visible": visible,
            "is_enabled": bool(user_config.is_enabled) if user_config else True,
            "config_schema_json": dict(plugin.config_schema_json or {}),
            "default_config_json": dict(plugin.default_config_json or {}),
            "user_config_schema_json": dict(plugin.user_config_schema_json or {}),
            "user_default_config_json": dict(plugin.user_default_config_json or {}),
            "user_config_json": (
                dict(user_config.config_json or {})
                if user_config
                else dict(plugin.user_default_config_json or {})
            ),
            "user_error_text": (
                (user_config.validation_error_text or user_config.runtime_error_text)
                if user_config
                else None
            ),
            "user_error_at": (
                (user_config.validation_error_at or user_config.runtime_error_at)
                if user_config
                else None
            ),
            "events": [item.model_dump() for item in events],
        }
