from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PluginDefinition,
    PluginEventConfig,
)
from app.schemas.admin.plugins import (
    PluginDetailOut,
)
from app.services.plugins.manager import validate_cron_expression


class PluginServiceEventMixin:
    def update_event_config(
        self, session: Session, plugin_id: str, event_name: str, config_json: dict
    ) -> PluginDetailOut:
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
        self._validate_config_payload(
            event.config_schema_json or {}, config_json, location=f"event_config.{event_name}"
        )
        current.config_json = dict(config_json or {})
        session.flush()
        session.commit()
        self.runtime_manager.reload_plugin(plugin_id)
        self.runtime_manager.run_once()
        return self.get_plugin_detail(session, plugin_id)

    def update_event_schedule(
        self,
        session: Session,
        plugin_id: str,
        event_name: str,
        *,
        schedule_mode: str,
        schedule_interval_seconds: int | None,
        schedule_cron: str | None,
    ) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        event = self._get_active_event_definition(session, plugin, event_name)
        if event.mode != "short_lived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only short-lived events can be scheduled",
            )
        if schedule_mode not in {"manual", "interval", "cron"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid schedule_mode"
            )
        if schedule_mode == "interval" and not schedule_interval_seconds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="schedule_interval_seconds is required",
            )
        normalized_cron = None
        if schedule_mode == "cron":
            try:
                normalized_cron = validate_cron_expression(schedule_cron or "")
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
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
        current.schedule_mode = schedule_mode
        current.schedule_interval_seconds = (
            int(schedule_interval_seconds) if schedule_mode == "interval" else None
        )
        current.schedule_cron = normalized_cron if schedule_mode == "cron" else None
        session.flush()
        session.commit()
        self.runtime_manager.update_short_lived_schedule(
            plugin_id,
            event_name,
            schedule_mode=current.schedule_mode,
            interval_seconds=current.schedule_interval_seconds,
            cron_expression=current.schedule_cron,
        )
        return self.get_plugin_detail(session, plugin_id)

    def run_short_lived_event_now(
        self, session: Session, plugin_id: str, event_name: str
    ) -> PluginDetailOut:
        plugin = session.get(PluginDefinition, plugin_id)
        if not plugin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        event = self._get_active_event_definition(session, plugin, event_name)
        if event.mode != "short_lived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only short-lived events can be manually run",
            )
        submitted = self.runtime_manager.trigger_short_lived_event(plugin_id, event_name)
        if submitted is False:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No eligible plugin target bindings were submitted for this event",
            )
        return self.get_plugin_detail(session, plugin_id)

    def set_event_enabled(
        self, session: Session, plugin_id: str, event_name: str, enabled: bool
    ) -> PluginDetailOut:
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
