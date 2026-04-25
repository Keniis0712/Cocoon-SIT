from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PluginDefinition,
    PluginEventConfig,
    PluginEventDefinition,
    PluginVersion,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
)
from app.services.plugins.manifest import PluginPackageManifest
from app.services.plugins.runtime import validate_plugin_functions, validate_plugin_settings
from app.services.plugins.schema_validation import (
    PluginSchemaValidationError,
    validate_json_schema_value,
)


class PluginServiceInstallMixin:
    def _get_active_event_definition(
        self, session: Session, plugin: PluginDefinition, event_name: str
    ) -> PluginEventDefinition:
        if not plugin.active_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin has no active version"
            )
        event = session.scalar(
            select(PluginEventDefinition).where(
                PluginEventDefinition.plugin_id == plugin.id,
                PluginEventDefinition.plugin_version_id == plugin.active_version_id,
                PluginEventDefinition.name == event_name,
            )
        )
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plugin event not found"
            )
        return event

    def _install_or_update(
        self,
        session: Session,
        upload: UploadFile,
        *,
        existing_plugin: PluginDefinition | None,
        owner_user_id: str | None = None,
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
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plugin zip"
                ) from exc
            manifest_path = extracted_root / "plugin.json"
            if not manifest_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="plugin.json not found in plugin zip",
                )
            try:
                manifest = PluginPackageManifest.load(manifest_path)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            if existing_plugin and existing_plugin.name != manifest.name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Updated plugin zip must keep the same plugin name",
                )
            plugin_root = self.settings.plugin_root / manifest.name / "versions" / manifest.version
            content_root = plugin_root / "content"
            if plugin_root.exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plugin version already installed",
                )
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
            self._validate_config_payload(
                manifest.config_schema or {},
                manifest.default_config or {},
                location="plugin_default_config",
            )
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
                    owner_user_id=owner_user_id,
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
                metadata_json=json.loads(
                    (content_root / "plugin.json").read_text(encoding="utf-8")
                ),
            )
            session.add(version)
            db_touched = True
            session.flush()
            for item in manifest.events:
                schema_properties = (item.config_schema or {}).get("properties")
                if "interval_seconds" in (item.default_config or {}) or (
                    isinstance(schema_properties, dict) and "interval_seconds" in schema_properties
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "event config must not define interval_seconds; "
                            "use plugin event schedule settings"
                        ),
                    )
                self._validate_config_payload(
                    item.config_schema or {},
                    item.default_config or {},
                    location=f"event_default_config.{item.name}",
                )
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
                            schedule_mode="manual",
                            schedule_interval_seconds=None,
                            schedule_cron=None,
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
                        manifest_paths=[
                            Path(item.manifest_path)
                            for item in session.scalars(select(PluginVersion)).all()
                        ],
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

    def _validate_admin_plugin_settings(
        self,
        session: Session,
        plugin: PluginDefinition,
        *,
        plugin_config: dict[str, object],
    ) -> None:
        if not plugin.settings_validation_function_name or not plugin.active_version_id:
            return
        if not self._has_admin_plugin_config_surface(plugin, plugin_config=plugin_config):
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
                plugin_config=plugin_config,
                user_config={},
                user_id=None,
                data_dir=plugin.data_dir,
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    def _has_admin_plugin_config_surface(
        self,
        plugin: PluginDefinition,
        *,
        plugin_config: dict[str, object],
    ) -> bool:
        if dict(plugin_config or {}):
            return True
        if dict(plugin.config_json or {}):
            return True
        if dict(plugin.default_config_json or {}):
            return True
        schema = dict(plugin.config_schema_json or {})
        if not schema:
            return False
        meaningful_keys = set(schema.keys()) - {
            "type",
            "title",
            "description",
            "additionalProperties",
        }
        if meaningful_keys:
            return True
        return bool(schema.get("properties") or schema.get("required"))
