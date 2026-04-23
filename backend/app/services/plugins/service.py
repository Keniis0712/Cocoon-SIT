from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginEventDefinition,
    PluginGroupVisibility,
    PluginRunState,
    PluginUserConfig,
    PluginVersion,
    User,
    UserGroup,
    UserGroupMember,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
    PluginEventOut,
    PluginGroupVisibilityOut,
    PluginListItemOut,
    PluginRunStateOut,
    PluginSharedPackageOut,
    PluginVersionOut,
)
from app.services.plugins.dependency_builder import DependencyBuilder
from app.services.plugins.manifest import PluginPackageManifest
from app.services.plugins.manager import PluginRuntimeManager
from app.services.plugins.schema_validation import PluginSchemaValidationError, validate_json_schema_value
from app.services.plugins.runtime import validate_plugin_functions, validate_plugin_settings


class PluginService:
    def __init__(
        self,
        *,
        settings: Settings,
        dependency_builder: DependencyBuilder,
        runtime_manager: PluginRuntimeManager,
    ) -> None:
        self.settings = settings
        self.dependency_builder = dependency_builder
        self.runtime_manager = runtime_manager

    def list_plugins(self, session: Session) -> list[PluginListItemOut]:
        items = list(session.scalars(select(PluginDefinition).order_by(PluginDefinition.created_at.asc())).all())
        return [PluginListItemOut.model_validate(item) for item in items]

    def get_plugin_detail(self, session: Session, plugin_id: str) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        versions = list(
            session.scalars(
                select(PluginVersion)
                .where(PluginVersion.plugin_id == plugin_id)
                .order_by(PluginVersion.created_at.desc())
            ).all()
        )
        run_state = session.scalar(select(PluginRunState).where(PluginRunState.plugin_id == plugin_id))
        active_version = session.get(PluginVersion, plugin.active_version_id) if plugin.active_version_id else None
        event_defs = []
        if active_version:
            event_defs = list(
                session.scalars(
                    select(PluginEventDefinition).where(
                        PluginEventDefinition.plugin_id == plugin_id,
                        PluginEventDefinition.plugin_version_id == active_version.id,
                    )
                ).all()
            )
        event_configs = {
            item.event_name: item
            for item in session.scalars(
                select(PluginEventConfig).where(PluginEventConfig.plugin_id == plugin_id)
            ).all()
        }
        return PluginDetailOut(
            **PluginListItemOut.model_validate(plugin).model_dump(),
            active_version=PluginVersionOut.model_validate(active_version) if active_version else None,
            versions=[PluginVersionOut.model_validate(item) for item in versions],
            events=[
                PluginEventOut(
                    name=item.name,
                    mode=item.mode,
                    function_name=item.function_name,
                    title=item.title,
                    description=item.description,
                    config_schema_json=item.config_schema_json or {},
                    default_config_json=item.default_config_json or {},
                    config_json=(event_configs.get(item.name).config_json if event_configs.get(item.name) else item.default_config_json) or {},
                    is_enabled=event_configs.get(item.name).is_enabled if event_configs.get(item.name) else True,
                )
                for item in event_defs
            ],
            run_state=PluginRunStateOut.model_validate(run_state) if run_state else None,
        )

    def install_plugin(self, session: Session, upload: UploadFile) -> PluginDetailOut:
        return self._install_or_update(session, upload, existing_plugin=None)

    def list_shared_packages(self, session: Session) -> list[PluginSharedPackageOut]:
        manifest_paths = [Path(item.manifest_path) for item in session.scalars(select(PluginVersion)).all()]
        inventory = self.dependency_builder.collect_inventory(
            shared_lib_root=self.settings.plugin_root / "shared_libs",
            manifest_paths=manifest_paths,
        )
        return [
            PluginSharedPackageOut(
                name=item.name,
                normalized_name=item.normalized_name,
                version=item.version,
                path=str(item.path),
                reference_count=item.reference_count,
                size_bytes=item.size_bytes,
            )
            for item in inventory
        ]

    def update_plugin(self, session: Session, plugin_id: str, upload: UploadFile) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        was_enabled = plugin.status == "enabled"
        previous_active_version_id = plugin.active_version_id
        previous_status = plugin.status
        self.disable_plugin(session, plugin_id)
        try:
            detail = self._install_or_update(session, upload, existing_plugin=plugin)
            if was_enabled:
                self.enable_plugin(session, plugin_id)
                detail = self.get_plugin_detail(session, plugin_id)
            return detail
        except Exception:
            session.refresh(plugin)
            plugin.active_version_id = previous_active_version_id
            plugin.status = previous_status
            session.flush()
            session.commit()
            if was_enabled:
                self.runtime_manager.reload_plugin(plugin_id)
                self.runtime_manager.run_once()
            raise

    def enable_plugin(self, session: Session, plugin_id: str) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        if not plugin.active_version_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin has no active version")
        plugin.status = "enabled"
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def disable_plugin(self, session: Session, plugin_id: str) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        plugin.status = "disabled"
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        return self.get_plugin_detail(session, plugin_id)

    def delete_plugin(self, session: Session, plugin_id: str) -> None:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self.runtime_manager.reload_plugin(plugin_id)
        plugin_versions = list(session.scalars(select(PluginVersion).where(PluginVersion.plugin_id == plugin_id)).all())
        version_paths = [Path(item.source_zip_path).parent for item in plugin_versions]
        remaining_manifest_paths = [
            Path(item.manifest_path)
            for item in session.scalars(select(PluginVersion).where(PluginVersion.plugin_id != plugin_id)).all()
        ]
        data_dir = Path(plugin.data_dir)
        session.query(PluginDispatchRecord).filter(PluginDispatchRecord.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginGroupVisibility).filter(PluginGroupVisibility.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginUserConfig).filter(PluginUserConfig.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginEventConfig).filter(PluginEventConfig.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginEventDefinition).filter(PluginEventDefinition.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginRunState).filter(PluginRunState.plugin_id == plugin_id).delete(synchronize_session=False)
        session.query(PluginVersion).filter(PluginVersion.plugin_id == plugin_id).delete(synchronize_session=False)
        session.delete(plugin)
        session.flush()
        session.commit()
        for path in version_paths:
            shutil.rmtree(path, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)
        self.dependency_builder.prune_unused_packages(
            shared_lib_root=self.settings.plugin_root / "shared_libs",
            manifest_paths=remaining_manifest_paths,
        )

    def update_plugin_config(self, session: Session, plugin_id: str, config_json: dict) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self._validate_config_payload(plugin.config_schema_json or {}, config_json, location="plugin_config")
        plugin.config_json = dict(config_json or {})
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def update_event_config(self, session: Session, plugin_id: str, event_name: str, config_json: dict) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        event = self._get_active_event_definition(session, plugin, event_name)
        current = session.scalar(
            select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin_id,
                PluginEventConfig.event_name == event_name,
            )
        )
        if not current:
            current = PluginEventConfig(
                plugin_id=plugin_id,
                event_name=event_name,
                config_json=dict(event.default_config_json or {}),
                is_enabled=True,
            )
            session.add(current)
            session.flush()
        self._validate_config_payload(event.config_schema_json or {}, config_json, location=f"event_config.{event_name}")
        current.config_json = dict(config_json or {})
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def set_event_enabled(self, session: Session, plugin_id: str, event_name: str, enabled: bool) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        event = self._get_active_event_definition(session, plugin, event_name)
        current = session.scalar(
            select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin_id,
                PluginEventConfig.event_name == event_name,
            )
        )
        if not current:
            current = PluginEventConfig(
                plugin_id=plugin_id,
                event_name=event_name,
                config_json=dict(event.default_config_json or {}),
                is_enabled=enabled,
            )
            session.add(current)
        else:
            current.is_enabled = enabled
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def list_plugins_for_user(self, session: Session, user: User) -> list[dict]:
        plugins = list(session.scalars(select(PluginDefinition).order_by(PluginDefinition.created_at.asc())).all())
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
            self._serialize_user_plugin(item, user_configs.get(item.id), visibility_map.get(item.id, []))
            for item in plugins
            if self._resolve_plugin_visibility(item, visibility_map.get(item.id, []))
        ]

    def get_plugin_for_user(self, session: Session, user: User, plugin_id: str) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(session, plugin_ids=[plugin.id], group_ids=group_ids).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        user_config = session.scalar(
            select(PluginUserConfig).where(
                PluginUserConfig.plugin_id == plugin.id,
                PluginUserConfig.user_id == user.id,
            )
        )
        return self._serialize_user_plugin(plugin, user_config, visibility_overrides)

    def set_plugin_enabled_for_user(self, session: Session, user: User, plugin_id: str, *, enabled: bool) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(session, plugin_ids=[plugin.id], group_ids=group_ids).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        current = self._ensure_user_config(session, plugin, user.id)
        current.is_enabled = enabled
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def update_user_plugin_config(self, session: Session, user: User, plugin_id: str, config_json: dict) -> dict:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        group_ids = self._group_ids_for_user(session, user.id)
        visibility_overrides = self._group_visibility_map(session, plugin_ids=[plugin.id], group_ids=group_ids).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self._validate_config_payload(plugin.user_config_schema_json or {}, config_json, location="plugin_user_config")
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
        visibility_overrides = self._group_visibility_map(session, plugin_ids=[plugin.id], group_ids=group_ids).get(plugin.id, [])
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
        visibility_overrides = self._group_visibility_map(session, plugin_ids=[plugin.id], group_ids=group_ids).get(plugin.id, [])
        if not self._resolve_plugin_visibility(plugin, visibility_overrides):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        current = self._ensure_user_config(session, plugin, user.id)
        current.error_text = None
        current.error_at = None
        session.flush()
        session.commit()
        session.refresh(current)
        return self._serialize_user_plugin(plugin, current, visibility_overrides)

    def set_global_visibility(self, session: Session, plugin_id: str, user: User, *, visible: bool) -> PluginDetailOut:
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

    def list_group_visibility(self, session: Session, plugin_id: str) -> list[PluginGroupVisibilityOut]:
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

    def record_user_plugin_error(self, session: Session, plugin_id: str, user_id: str, error_text: str) -> None:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            return
        row = self._ensure_user_config(session, plugin, user_id)
        row.error_text = error_text.strip() or "Plugin runtime error"
        row.error_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()

    def clear_user_plugin_error_for_runtime(self, session: Session, plugin_id: str, user_id: str) -> None:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            return
        row = self._ensure_user_config(session, plugin, user_id)
        row.error_text = None
        row.error_at = None
        session.flush()

    def _require_bootstrap_admin(self, user: User) -> None:
        if user.username != self.settings.default_admin_username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only bootstrap admin can manage plugin visibility",
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

    def _resolve_plugin_visibility(self, plugin: PluginDefinition, group_overrides: list[bool]) -> bool:
        if group_overrides:
            return any(group_overrides)
        return bool(plugin.is_globally_visible)

    def _ensure_user_config(self, session: Session, plugin: PluginDefinition, user_id: str) -> PluginUserConfig:
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

    def _refresh_user_config_validation(
        self,
        session: Session,
        plugin: PluginDefinition,
        user_config: PluginUserConfig,
    ) -> None:
        user_config.error_text = None
        user_config.error_at = None
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
            user_config.error_text = message
            user_config.error_at = datetime.now(UTC).replace(tzinfo=None)

    def _serialize_user_plugin(
        self,
        plugin: PluginDefinition,
        user_config: PluginUserConfig | None,
        group_overrides: list[bool],
    ) -> dict:
        visible = self._resolve_plugin_visibility(plugin, group_overrides)
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
            "user_error_text": user_config.error_text if user_config else None,
            "user_error_at": user_config.error_at if user_config else None,
        }

    def _get_active_event_definition(self, session: Session, plugin: PluginDefinition, event_name: str) -> PluginEventDefinition:
        if not plugin.active_version_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin has no active version")
        event = session.scalar(
            select(PluginEventDefinition).where(
                PluginEventDefinition.plugin_id == plugin.id,
                PluginEventDefinition.plugin_version_id == plugin.active_version_id,
                PluginEventDefinition.name == event_name,
            )
        )
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin event not found")
        return event

    def _install_or_update(
        self,
        session: Session,
        upload: UploadFile,
        *,
        existing_plugin: PluginDefinition | None,
    ) -> PluginDetailOut:
        temp_dir = Path(tempfile.mkdtemp(prefix="plugin-install-"))
        plugin_root: Path | None = None
        data_dir: Path | None = None
        version_root_created = False
        data_dir_created = False
        db_touched = False
        committed = False
        try:
            archive_path = temp_dir / (upload.filename or "plugin.zip")
            archive_path.write_bytes(upload.file.read())
            extracted_root = temp_dir / "content"
            extracted_root.mkdir(parents=True, exist_ok=True)
            try:
                with ZipFile(archive_path) as bundle:
                    bundle.extractall(extracted_root)
            except BadZipFile as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plugin zip") from exc
            manifest_path = extracted_root / "plugin.json"
            if not manifest_path.exists():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plugin.json not found in plugin zip")
            try:
                manifest = PluginPackageManifest.load(manifest_path)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            if existing_plugin and existing_plugin.name != manifest.name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Updated plugin zip must keep the same plugin name")
            plugin_root = self.settings.plugin_root / manifest.name / "versions" / manifest.version
            content_root = plugin_root / "content"
            if plugin_root.exists():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin version already installed")
            plugin_root.mkdir(parents=True, exist_ok=True)
            version_root_created = True
            shutil.copy2(archive_path, plugin_root / "source.zip")
            shutil.copytree(extracted_root, content_root, dirs_exist_ok=True)
            try:
                dep_manifest_path = self.dependency_builder.build(
                    extracted_root=content_root,
                    version_root=plugin_root,
                    shared_lib_root=self.settings.plugin_root / "shared_libs",
                )
            except subprocess.CalledProcessError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plugin dependency installation failed",
                ) from exc
            try:
                validate_plugin_functions(
                    str(dep_manifest_path),
                    manifest.entry_module,
                    manifest.plugin_type,
                    events=[item.model_dump() for item in manifest.events],
                    service_function=manifest.service_function,
                    settings_validation_function=manifest.settings_validation_function,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Plugin validation failed: {exc}",
                ) from exc
            self._validate_config_payload(manifest.config_schema or {}, manifest.default_config or {}, location="plugin_default_config")
            self._validate_config_payload(
                manifest.user_config_schema or {},
                manifest.user_default_config or {},
                location="plugin_user_default_config",
            )
            plugin = existing_plugin
            if plugin is None:
                data_dir = self.settings.plugin_data_root / manifest.name
                data_dir_created = not data_dir.exists()
                data_dir.mkdir(parents=True, exist_ok=True)
                plugin = PluginDefinition(
                    name=manifest.name,
                    display_name=manifest.display_name,
                    plugin_type=manifest.plugin_type,
                    entry_module=manifest.entry_module,
                    service_function_name=manifest.service_function,
                    status="disabled",
                    data_dir=str(data_dir),
                    config_schema_json=manifest.config_schema,
                    default_config_json=manifest.default_config,
                    config_json=dict(manifest.default_config or {}),
                    user_config_schema_json=manifest.user_config_schema,
                    user_default_config_json=manifest.user_default_config,
                    settings_validation_function_name=manifest.settings_validation_function,
                    is_globally_visible=True,
                )
                session.add(plugin)
                db_touched = True
                session.flush()
            else:
                db_touched = True
                plugin.display_name = manifest.display_name
                plugin.plugin_type = manifest.plugin_type
                plugin.entry_module = manifest.entry_module
                plugin.service_function_name = manifest.service_function
                plugin.config_schema_json = manifest.config_schema
                plugin.default_config_json = manifest.default_config
                plugin.user_config_schema_json = manifest.user_config_schema
                plugin.user_default_config_json = manifest.user_default_config
                plugin.settings_validation_function_name = manifest.settings_validation_function
            version = PluginVersion(
                plugin_id=plugin.id,
                version=manifest.version,
                source_zip_path=str(plugin_root / "source.zip"),
                extracted_path=str(content_root),
                manifest_path=str(dep_manifest_path),
                install_status="installed",
                error_text=None,
                metadata_json=json.loads((content_root / "plugin.json").read_text(encoding="utf-8")),
            )
            session.add(version)
            db_touched = True
            session.flush()
            for item in manifest.events:
                self._validate_config_payload(item.config_schema or {}, item.default_config or {}, location=f"event_default_config.{item.name}")
                session.add(
                    PluginEventDefinition(
                        plugin_id=plugin.id,
                        plugin_version_id=version.id,
                        name=item.name,
                        mode=item.mode,
                        function_name=item.function_name,
                        title=item.title,
                        description=item.description,
                        config_schema_json=item.config_schema,
                        default_config_json=item.default_config,
                    )
                )
                current = session.scalar(
                    select(PluginEventConfig).where(
                        PluginEventConfig.plugin_id == plugin.id,
                        PluginEventConfig.event_name == item.name,
                    )
                )
                if not current:
                    session.add(
                        PluginEventConfig(
                            plugin_id=plugin.id,
                            event_name=item.name,
                            is_enabled=True,
                            config_json=dict(item.default_config or {}),
                        )
                    )
            plugin.active_version_id = version.id
            session.flush()
            session.commit()
            committed = True
            self.runtime_manager.reload_plugin(plugin.id)
            return self.get_plugin_detail(session, plugin.id)
        except Exception:
            if db_touched and not committed:
                session.rollback()
            if version_root_created and not committed and plugin_root is not None:
                shutil.rmtree(plugin_root, ignore_errors=True)
                with suppress(Exception):
                    self.dependency_builder.prune_unused_packages(
                        shared_lib_root=self.settings.plugin_root / "shared_libs",
                        manifest_paths=[Path(item.manifest_path) for item in session.scalars(select(PluginVersion)).all()],
                    )
            if data_dir_created and not committed and data_dir is not None:
                shutil.rmtree(data_dir, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _validate_config_payload(self, schema: dict, payload: dict, *, location: str) -> None:
        try:
            validate_json_schema_value(schema, payload or {}, location=location)
        except PluginSchemaValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
