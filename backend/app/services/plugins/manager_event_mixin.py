from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.models import (
    PluginDefinition,
    PluginEventConfig,
    PluginEventDefinition,
    PluginTargetBinding,
    PluginVersion,
)
from app.services.plugins.errors import PluginUserVisibleError
from app.services.plugins.manager_models import next_cron_run
from app.services.plugins.runtime import run_short_lived_event

logger = logging.getLogger(__name__)


class PluginEventRuntimeMixin:
    def _submit_short_lived_event(self, plugin_id: str, event_name: str) -> bool:
        submitted = False
        with self.session_factory() as session:
            plugin = session.get(PluginDefinition, plugin_id)
            if not plugin or plugin.status != "enabled" or not plugin.active_version_id:
                logger.info(
                    "Plugin short-lived event skipped before submit plugin_id=%s "
                    "event_name=%s reason=%s status=%s active_version_id=%s",
                    plugin_id,
                    event_name,
                    "plugin_missing" if not plugin else "plugin_not_enabled_or_no_active_version",
                    getattr(plugin, "status", None),
                    getattr(plugin, "active_version_id", None),
                )
                return False
            active_version = session.get(PluginVersion, plugin.active_version_id)
            if not active_version:
                logger.info(
                    "Plugin short-lived event skipped before submit plugin_id=%s "
                    "event_name=%s reason=active_version_missing active_version_id=%s",
                    plugin_id,
                    event_name,
                    plugin.active_version_id,
                )
                return False
            event = session.scalar(
                select(PluginEventDefinition).where(
                    PluginEventDefinition.plugin_id == plugin_id,
                    PluginEventDefinition.plugin_version_id == active_version.id,
                    PluginEventDefinition.name == event_name,
                )
            )
            if not event or event.mode != "short_lived":
                logger.info(
                    "Plugin short-lived event skipped before submit plugin_id=%s "
                    "event_name=%s reason=%s event_mode=%s",
                    plugin_id,
                    event_name,
                    "event_missing" if not event else "event_not_short_lived",
                    getattr(event, "mode", None),
                )
                return False
            cfg = session.scalar(
                select(PluginEventConfig).where(
                    PluginEventConfig.plugin_id == plugin_id,
                    PluginEventConfig.event_name == event_name,
                )
            )
            if cfg and not cfg.is_enabled:
                logger.info(
                    "Plugin short-lived event skipped before submit plugin_id=%s "
                    "event_name=%s reason=event_disabled",
                    plugin_id,
                    event_name,
                )
                return False
            config_json = dict(event.default_config_json or {})
            if cfg:
                config_json.update(cfg.config_json or {})
            binding_count = (
                session.query(PluginTargetBinding)
                .filter(PluginTargetBinding.plugin_id == plugin_id)
                .count()
            )
            scopes = self._list_short_lived_scopes(session, plugin)
            if not scopes:
                logger.warning(
                    "Plugin short-lived event has no eligible scopes plugin_id=%s "
                    "plugin_name=%s event_name=%s target_binding_count=%s",
                    plugin_id,
                    plugin.name,
                    event_name,
                    binding_count,
                )
                return False
            logger.info(
                "Plugin short-lived event submitting plugin_id=%s plugin_name=%s "
                "event_name=%s scope_count=%s target_binding_count=%s",
                plugin_id,
                plugin.name,
                event_name,
                len(scopes),
                binding_count,
            )
            for scope in scopes:
                key = (plugin_id, event_name, scope.scope_type, scope.scope_id)
                if key in self._short_lived_futures:
                    logger.info(
                        "Plugin short-lived event already running plugin_id=%s "
                        "event_name=%s scope_type=%s scope_id=%s",
                        plugin_id,
                        event_name,
                        scope.scope_type,
                        scope.scope_id,
                    )
                    continue
                future = self._ensure_pool().submit(
                    run_short_lived_event,
                    active_version.manifest_path,
                    plugin.entry_module,
                    event.function_name,
                    plugin.name,
                    active_version.version,
                    dict(plugin.config_json or {}),
                    event.name,
                    config_json,
                    plugin.data_dir,
                    scope.config_json,
                    scope.user_id,
                    scope.scope_type,
                    scope.scope_id,
                )
                self._short_lived_futures[key] = future
                submitted = True
                logger.info(
                    "Plugin short-lived event submitted plugin_id=%s event_name=%s "
                    "scope_type=%s scope_id=%s user_id=%s",
                    plugin_id,
                    event_name,
                    scope.scope_type,
                    scope.scope_id,
                    scope.user_id,
                )
            if not submitted:
                logger.info(
                    "Plugin short-lived event submit finished with no new futures "
                    "plugin_id=%s event_name=%s scope_count=%s",
                    plugin_id,
                    event_name,
                    len(scopes),
                )
            return submitted

    def _handle_finished_short_lived(self) -> None:
        for key, future in list(self._short_lived_futures.items()):
            if not future.done():
                continue
            plugin_id, event_name, scope_type, scope_id = key
            self._short_lived_futures.pop(key, None)
            try:
                result = future.result()
            except Exception as exc:
                logger.exception(
                    "Plugin short-lived event failed plugin_id=%s event_name=%s "
                    "scope_type=%s scope_id=%s",
                    plugin_id,
                    event_name,
                    scope_type,
                    scope_id,
                )
                with self.session_factory() as session:
                    plugin = session.get(PluginDefinition, plugin_id)
                    if isinstance(exc, PluginUserVisibleError) and plugin and exc.user_id:
                        self._record_user_error(
                            session, plugin=plugin, user_id=exc.user_id, message=str(exc)
                        )
                        run_state = self._ensure_run_state(session, plugin_id)
                        run_state.status = "running"
                        run_state.error_text = None
                    elif plugin and scope_type == "user":
                        self._record_user_error(
                            session, plugin=plugin, user_id=scope_id, message=str(exc)
                        )
                        run_state = self._ensure_run_state(session, plugin_id)
                        run_state.status = "running"
                        run_state.error_text = None
                    elif plugin and scope_type == "chat_group":
                        self._record_chat_group_error(
                            session, plugin=plugin, chat_group_id=scope_id, message=str(exc)
                        )
                        run_state = self._ensure_run_state(session, plugin_id)
                        run_state.status = "running"
                        run_state.error_text = None
                    else:
                        run_state = self._ensure_run_state(session, plugin_id)
                        run_state.status = "failed"
                        run_state.error_text = str(exc)
                    session.commit()
                continue
            if result is None:
                logger.info(
                    "Plugin short-lived event finished without envelope plugin_id=%s "
                    "event_name=%s scope_type=%s scope_id=%s",
                    plugin_id,
                    event_name,
                    scope_type,
                    scope_id,
                )
                continue
            with self.session_factory() as session:
                plugin = session.get(PluginDefinition, plugin_id)
                version = (
                    session.get(PluginVersion, plugin.active_version_id)
                    if plugin and plugin.active_version_id
                    else None
                )
                if not plugin or not version:
                    session.rollback()
                    continue
                task_ids = self.external_wakeup_service.ingest(
                    session,
                    plugin=plugin,
                    version=version,
                    event_name=event_name,
                    envelope=result,
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
                logger.info(
                    "Plugin short-lived event dispatched plugin_id=%s event_name=%s "
                    "scope_type=%s scope_id=%s wakeup_task_count=%s",
                    plugin_id,
                    event_name,
                    scope_type,
                    scope_id,
                    len(task_ids),
                )
                run_state = self._ensure_run_state(session, plugin_id)
                run_state.status = "running"
                run_state.heartbeat_at = datetime.now(UTC).isoformat()
                session.commit()

    def _sync_plugins(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        try:
            with self.session_factory() as session:
                plugins = list(session.scalars(select(PluginDefinition)).all())
                versions = {item.id: item for item in session.scalars(select(PluginVersion)).all()}
                event_rows = list(session.scalars(select(PluginEventDefinition)).all())
                event_configs = list(session.scalars(select(PluginEventConfig)).all())
                event_config_map = {
                    (item.plugin_id, item.event_name): item for item in event_configs
                }
        except ProgrammingError:
            return

        event_by_plugin: dict[str, list[PluginEventDefinition]] = {}
        for item in event_rows:
            event_by_plugin.setdefault(item.plugin_id, []).append(item)

        enabled_plugin_ids = {
            item.id for item in plugins if item.status == "enabled" and item.active_version_id
        }
        for plugin_id in list(self._daemon_handles):
            if plugin_id not in enabled_plugin_ids:
                self._stop_daemon_handle(plugin_id)

        for plugin in plugins:
            if plugin.status != "enabled" or not plugin.active_version_id:
                continue
            active_version = versions.get(plugin.active_version_id)
            if not active_version:
                continue
            active_events = [
                item
                for item in event_by_plugin.get(plugin.id, [])
                if item.plugin_version_id == active_version.id
            ]
            if plugin.plugin_type == "external":
                daemon_events: list[dict[str, Any]] = []
                for event in active_events:
                    cfg = event_config_map.get((plugin.id, event.name))
                    config_json = dict(event.default_config_json or {})
                    if cfg:
                        if not cfg.is_enabled:
                            continue
                        config_json.update(cfg.config_json or {})
                    if event.mode == "daemon":
                        daemon_events.append(
                            {
                                "name": event.name,
                                "function_name": event.function_name,
                                "config_json": config_json,
                            }
                        )
                    elif event.mode == "short_lived":
                        key = (plugin.id, event.name)
                        schedule_mode = (cfg.schedule_mode if cfg else "manual") or "manual"
                        interval_seconds = cfg.schedule_interval_seconds if cfg else None
                        cron_expression = cfg.schedule_cron if cfg else None
                        if schedule_mode == "manual":
                            self._short_lived_next_run.pop(key, None)
                            continue
                        next_run = self._short_lived_next_run.get(key)
                        if next_run is None:
                            next_run = self._next_run_for_schedule(
                                schedule_mode,
                                interval_seconds=interval_seconds,
                                cron_expression=cron_expression,
                                after=now,
                            )
                            self._short_lived_next_run[key] = next_run
                        if next_run <= now:
                            self._submit_short_lived_event(plugin.id, event.name)
                            self._short_lived_next_run[key] = self._next_run_for_schedule(
                                schedule_mode,
                                interval_seconds=interval_seconds,
                                cron_expression=cron_expression,
                                after=now,
                            )
                if daemon_events:
                    self._ensure_external_daemon(plugin, active_version, daemon_events)
            elif plugin.plugin_type == "im":
                self._ensure_im_process(plugin, active_version)

    def _next_run_for_schedule(
        self,
        schedule_mode: str,
        *,
        interval_seconds: int | None,
        cron_expression: str | None,
        after: datetime,
    ) -> datetime:
        if schedule_mode == "interval":
            return after + timedelta(seconds=max(int(interval_seconds or 1), 1))
        if schedule_mode == "cron" and cron_expression:
            return next_cron_run(cron_expression, after)
        return after + timedelta(days=3650)
