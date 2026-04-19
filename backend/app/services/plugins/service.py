from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginEventDefinition,
    PluginRunState,
    PluginVersion,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
    PluginEventOut,
    PluginListItemOut,
    PluginRunStateOut,
    PluginSharedPackageOut,
    PluginVersionOut,
)
from app.services.plugins.dependency_builder import DependencyBuilder
from app.services.plugins.manifest import PluginPackageManifest
from app.services.plugins.manager import PluginRuntimeManager
from app.services.plugins.schema_validation import PluginSchemaValidationError, validate_json_schema_value
from app.services.plugins.runtime import validate_plugin_functions


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
        try:
            archive_path = temp_dir / (upload.filename or "plugin.zip")
            archive_path.write_bytes(upload.file.read())
            extracted_root = temp_dir / "content"
            extracted_root.mkdir(parents=True, exist_ok=True)
            with ZipFile(archive_path) as bundle:
                bundle.extractall(extracted_root)
            manifest_path = extracted_root / "plugin.json"
            if not manifest_path.exists():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plugin.json not found in plugin zip")
            manifest = PluginPackageManifest.load(manifest_path)
            if existing_plugin and existing_plugin.name != manifest.name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Updated plugin zip must keep the same plugin name")
            plugin_root = self.settings.plugin_root / manifest.name / "versions" / manifest.version
            content_root = plugin_root / "content"
            if plugin_root.exists():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin version already installed")
            plugin_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive_path, plugin_root / "source.zip")
            shutil.copytree(extracted_root, content_root, dirs_exist_ok=True)
            dep_manifest_path = self.dependency_builder.build(
                extracted_root=content_root,
                version_root=plugin_root,
                shared_lib_root=self.settings.plugin_root / "shared_libs",
            )
            validate_plugin_functions(
                str(dep_manifest_path),
                manifest.entry_module,
                manifest.plugin_type,
                events=[item.model_dump() for item in manifest.events],
                service_function=manifest.service_function,
            )
            self._validate_config_payload(manifest.config_schema or {}, manifest.default_config or {}, location="plugin_default_config")
            plugin = existing_plugin
            if plugin is None:
                data_dir = self.settings.plugin_data_root / manifest.name
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
                )
                session.add(plugin)
                session.flush()
            else:
                plugin.display_name = manifest.display_name
                plugin.plugin_type = manifest.plugin_type
                plugin.entry_module = manifest.entry_module
                plugin.service_function_name = manifest.service_function
                plugin.config_schema_json = manifest.config_schema
                plugin.default_config_json = manifest.default_config
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
            self.runtime_manager.reload_plugin(plugin.id)
            return self.get_plugin_detail(session, plugin.id)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _validate_config_payload(self, schema: dict, payload: dict, *, location: str) -> None:
        try:
            validate_json_schema_value(schema, payload or {}, location=location)
        except PluginSchemaValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
