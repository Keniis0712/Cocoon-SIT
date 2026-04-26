from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PluginDefinition,
    PluginGroupVisibility,
    PluginTargetBinding,
    PluginUserConfig,
    User,
    UserGroup,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
    PluginGroupVisibilityOut,
)
from app.schemas.workspace.plugins import ChatGroupPluginConfigOut, UserPluginTargetBindingOut


class PluginServiceUserMixin:
    def list_plugins_for_user(self, session: Session, user: User) -> list[dict]:
        plugins = list(
            session.scalars(
                select(PluginDefinition).order_by(PluginDefinition.created_at.asc())
            ).all()
        )
        user_configs = {
            item.plugin_id: item
            for item in session.scalars(
                select(PluginUserConfig).where(PluginUserConfig.user_id == user.id)
            ).all()
        }
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_map = self._group_visibility_map(
            session,
            plugin_ids=[item.id for item in plugins],
            group_ids=group_ids,
        )
        return [
            self._serialize_user_plugin(
                item, user_configs.get(item.id), visibility_map.get(item.id, [])
            )
            for item in plugins
            if self._resolve_plugin_visibility(item, visibility_map.get(item.id, []))
        ]

    def get_plugin_for_user(self, session: Session, user: User, plugin_id: str) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        user_config = session.scalar(
            select(PluginUserConfig).where(
                PluginUserConfig.plugin_id == plugin.id,
                PluginUserConfig.user_id == user.id,
            )
        )
        return self._serialize_user_plugin(plugin, user_config, visibility_overrides)

    def set_plugin_enabled_for_user(
        self, session: Session, user: User, plugin_id: str, *, enabled: bool
    ) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        current = self._ensure_user_config(session, plugin, user.id)
        current.is_enabled = enabled
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def update_user_plugin_config(
        self, session: Session, user: User, plugin_id: str, config_json: dict
    ) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self._validate_config_payload(
            plugin.user_config_schema_json or {}, config_json, location="plugin_user_config"
        )
        current = self._ensure_user_config(session, plugin, user.id)
        current.config_json = dict(config_json or {})
        self._refresh_user_config_validation(session, plugin, current)
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def validate_user_plugin_config(self, session: Session, user: User, plugin_id: str) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        current = self._ensure_user_config(session, plugin, user.id)
        self._refresh_user_config_validation(session, plugin, current)
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def clear_user_plugin_error(self, session: Session, user: User, plugin_id: str) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(
            session, plugin_ids=[plugin.id], group_ids=group_ids
        ).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        current = self._ensure_user_config(session, plugin, user.id)
        current.runtime_error_text = None
        current.runtime_error_at = None
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def get_chat_group_plugin_config(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        chat_group_id: str,
    ) -> ChatGroupPluginConfigOut:
        plugin = self._require_user_visible_plugin(session, user, plugin_id)
        self._require_user_can_manage_chat_group(session, user, chat_group_id)
        current = self._ensure_chat_group_config(session, plugin, chat_group_id)
        return self._serialize_chat_group_plugin_config(plugin, current)

    def set_chat_group_plugin_enabled(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        chat_group_id: str,
        *,
        enabled: bool,
    ) -> ChatGroupPluginConfigOut:
        plugin = self._require_user_visible_plugin(session, user, plugin_id)
        self._require_user_can_manage_chat_group(session, user, chat_group_id)
        current = self._ensure_chat_group_config(session, plugin, chat_group_id)
        current.is_enabled = enabled
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_chat_group_plugin_config(plugin, current)

    def update_chat_group_plugin_config(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        chat_group_id: str,
        config_json: dict,
    ) -> ChatGroupPluginConfigOut:
        plugin = self._require_user_visible_plugin(session, user, plugin_id)
        self._require_user_can_manage_chat_group(session, user, chat_group_id)
        self._validate_config_payload(
            plugin.user_config_schema_json or {}, config_json, location="plugin_chat_group_config"
        )
        current = self._ensure_chat_group_config(session, plugin, chat_group_id)
        current.config_json = dict(config_json or {})
        self._refresh_chat_group_config_validation(session, plugin, current)
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_chat_group_plugin_config(plugin, current)

    def validate_chat_group_plugin_config(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        chat_group_id: str,
    ) -> ChatGroupPluginConfigOut:
        plugin = self._require_user_visible_plugin(session, user, plugin_id)
        self._require_user_can_manage_chat_group(session, user, chat_group_id)
        current = self._ensure_chat_group_config(session, plugin, chat_group_id)
        self._refresh_chat_group_config_validation(session, plugin, current)
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_chat_group_plugin_config(plugin, current)

    def clear_chat_group_plugin_error(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        chat_group_id: str,
    ) -> ChatGroupPluginConfigOut:
        plugin = self._require_user_visible_plugin(session, user, plugin_id)
        self._require_user_can_manage_chat_group(session, user, chat_group_id)
        current = self._ensure_chat_group_config(session, plugin, chat_group_id)
        current.runtime_error_text = None
        current.runtime_error_at = None
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_chat_group_plugin_config(plugin, current)

    def set_global_visibility(
        self, session: Session, plugin_id: str, user: User, *, visible: bool
    ) -> PluginDetailOut:
        self._require_bootstrap_admin(user)
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        plugin.is_globally_visible = visible
        session.flush()
        session.commit()
        return self.get_plugin_detail(session, plugin_id)

    def set_group_visibility(
        self,
        session: Session,
        plugin_id: str,
        group_id: str,
        user: User,
        *,
        visible: bool,
    ) -> PluginGroupVisibilityOut:
        self._require_bootstrap_admin(user)
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group = session.get(UserGroup, group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        current = session.scalar(
            select(PluginGroupVisibility).where(
                PluginGroupVisibility.plugin_id == plugin_id,
                PluginGroupVisibility.group_id == group_id,
            )
        )
        if not current:
            current = PluginGroupVisibility(
                plugin_id=plugin_id,
                group_id=group_id,
                is_visible=visible,
            )
            session.add(current)
        else:
            current.is_visible = visible
        session.flush()
        session.commit()
        return PluginGroupVisibilityOut.model_validate(current)

    def list_group_visibility(
        self, session: Session, plugin_id: str
    ) -> list[PluginGroupVisibilityOut]:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        rows = list(
            session.scalars(
                select(PluginGroupVisibility)
                .where(PluginGroupVisibility.plugin_id == plugin_id)
                .order_by(PluginGroupVisibility.created_at.asc())
            ).all()
        )
        return [PluginGroupVisibilityOut.model_validate(item) for item in rows]

    def list_target_bindings_for_user(
        self,
        session: Session,
        user: User,
        plugin_id: str,
    ) -> list[UserPluginTargetBindingOut]:
        self._require_user_visible_plugin(session, user, plugin_id)
        rows = list(
            session.scalars(
                select(PluginTargetBinding)
                .where(PluginTargetBinding.plugin_id == plugin_id)
                .order_by(PluginTargetBinding.created_at.asc())
            ).all()
        )
        return [
            self._serialize_target_binding(session, item)
            for item in rows
            if self._can_user_manage_binding_target(session, user, item)
        ]

    def add_target_binding_for_user(
        self,
        session: Session,
        user: User,
        plugin_id: str,
        *,
        target_type: str,
        target_id: str,
    ) -> UserPluginTargetBindingOut:
        self._require_user_visible_plugin(session, user, plugin_id)
        target_type = target_type.strip()
        target_id = target_id.strip()
        if target_type not in {"cocoon", "chat_group"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_type must be 'cocoon' or 'chat_group'",
            )
        self._require_user_can_bind_target(session, user, target_type, target_id)
        scope_type, scope_id = self._scope_for_binding_target(session, user, target_type, target_id)
        current = session.scalar(
            select(PluginTargetBinding).where(
                PluginTargetBinding.plugin_id == plugin_id,
                PluginTargetBinding.scope_type == scope_type,
                PluginTargetBinding.scope_id == scope_id,
                PluginTargetBinding.target_type == target_type,
                PluginTargetBinding.target_id == target_id,
            )
        )
        if current:
            return self._serialize_target_binding(session, current)
        current = PluginTargetBinding(
            plugin_id=plugin_id,
            scope_type=scope_type,
            scope_id=scope_id,
            target_type=target_type,
            target_id=target_id,
        )
        session.add(current)
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_target_binding(session, current)

    def delete_target_binding_for_user(
        self, session: Session, user: User, plugin_id: str, binding_id: str
    ) -> None:
        self._require_user_visible_plugin(session, user, plugin_id)
        current = session.scalar(
            select(PluginTargetBinding).where(
                PluginTargetBinding.id == binding_id,
                PluginTargetBinding.plugin_id == plugin_id,
            )
        )
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plugin target binding not found"
            )
        if not self._can_user_manage_binding_target(session, user, current):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Plugin target binding access denied"
            )
        session.delete(current)
        session.flush()
        session.commit()

    def record_user_plugin_error(
        self, session: Session, plugin_id: str, user_id: str, error_text: str
    ) -> None:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            return
        row = self._ensure_user_config(session, plugin, user_id)
        row.runtime_error_text = error_text.strip() or "Plugin runtime error"
        row.runtime_error_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()

    def clear_user_plugin_error_for_runtime(
        self, session: Session, plugin_id: str, user_id: str
    ) -> None:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            return
        row = self._ensure_user_config(session, plugin, user_id)
        row.runtime_error_text = None
        row.runtime_error_at = None
        session.flush()
