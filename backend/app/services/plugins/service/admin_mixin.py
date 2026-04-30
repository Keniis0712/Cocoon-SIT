from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PluginChatGroupConfig,
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginEventDefinition,
    PluginGroupVisibility,
    PluginImDeliveryOutbox,
    PluginImTargetRoute,
    PluginRunState,
    PluginTargetBinding,
    PluginUserConfig,
    PluginVersion,
    User,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
    PluginEventOut,
    PluginListItemOut,
    PluginRunStateOut,
    PluginSharedPackageOut,
    PluginVersionOut,
)


class PluginServiceAdminMixin:
    def list_plugins(self, session: Session) -> list[PluginListItemOut]:
        items = list(
            session.scalars(
                select(PluginDefinition).order_by(PluginDefinition.created_at.asc())
            ).all()
        )
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
        run_state = session.scalar(
            select(PluginRunState).where(PluginRunState.plugin_id == plugin_id)
        )
        active_version = (
            session.get(PluginVersion, plugin.active_version_id)
            if plugin.active_version_id
            else None
        )
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
            active_version=PluginVersionOut.model_validate(active_version)
            if active_version
            else None,
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
                    config_json=(
                        event_configs.get(item.name).config_json
                        if event_configs.get(item.name)
                        else item.default_config_json
                    )
                    or {},
                    is_enabled=event_configs.get(item.name).is_enabled
                    if event_configs.get(item.name)
                    else True,
                    schedule_mode="manual",
                    schedule_interval_seconds=None,
                    schedule_cron=None,
                )
                for item in event_defs
            ],
            run_state=PluginRunStateOut.model_validate(run_state) if run_state else None,
        )

    def install_plugin(self, session: Session, upload: UploadFile, actor: User) -> PluginDetailOut:
        return self._install_or_update(session, upload, existing_plugin=None, owner_user_id=actor.id)

    def list_shared_packages(self, session: Session) -> list[PluginSharedPackageOut]:
        manifest_paths = [
            Path(item.manifest_path) for item in session.scalars(select(PluginVersion)).all()
        ]
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

    def update_plugin(
        self, session: Session, plugin_id: str, upload: UploadFile
    ) -> PluginDetailOut:
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Plugin has no active version"
            )
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
        plugin_versions = list(
            session.scalars(select(PluginVersion).where(PluginVersion.plugin_id == plugin_id)).all()
        )
        version_paths = [Path(item.source_zip_path).parent for item in plugin_versions]
        remaining_manifest_paths = [
            Path(item.manifest_path)
            for item in session.scalars(
                select(PluginVersion).where(PluginVersion.plugin_id != plugin_id)
            ).all()
        ]
        data_dir = Path(plugin.data_dir)
        plugin.active_version_id = None
        session.flush()
        session.query(PluginRunState).filter(PluginRunState.plugin_id == plugin_id).update(
            {
                PluginRunState.current_version_id: None,
            },
            synchronize_session=False,
        )
        session.query(PluginDispatchRecord).filter(
            PluginDispatchRecord.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginChatGroupConfig).filter(
            PluginChatGroupConfig.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginGroupVisibility).filter(
            PluginGroupVisibility.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginImDeliveryOutbox).filter(
            PluginImDeliveryOutbox.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginImTargetRoute).filter(
            PluginImTargetRoute.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginTargetBinding).filter(
            PluginTargetBinding.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginUserConfig).filter(PluginUserConfig.plugin_id == plugin_id).delete(
            synchronize_session=False
        )
        session.query(PluginEventConfig).filter(PluginEventConfig.plugin_id == plugin_id).delete(
            synchronize_session=False
        )
        session.query(PluginEventDefinition).filter(
            PluginEventDefinition.plugin_id == plugin_id
        ).delete(synchronize_session=False)
        session.query(PluginRunState).filter(PluginRunState.plugin_id == plugin_id).delete(
            synchronize_session=False
        )
        session.query(PluginVersion).filter(PluginVersion.plugin_id == plugin_id).delete(
            synchronize_session=False
        )
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

    def update_plugin_config(
        self, session: Session, plugin_id: str, config_json: dict
    ) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self._validate_config_payload(
            plugin.config_schema_json or {}, config_json, location="plugin_config"
        )
        plugin.config_json = dict(config_json or {})
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def validate_admin_plugin_config(
        self, session: Session, plugin_id: str, config_json: dict
    ) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        self._validate_config_payload(
            plugin.config_schema_json or {}, config_json, location="plugin_config"
        )
        self._validate_admin_plugin_settings(session, plugin, plugin_config=dict(config_json or {}))
        return self.get_plugin_detail(session, plugin_id)
