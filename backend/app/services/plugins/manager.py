from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import multiprocessing as mp
from pathlib import Path
from queue import Empty
import threading
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import ProgrammingError

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginEventConfig,
    PluginEventDefinition,
    PluginRunState,
    PluginUserConfig,
    PluginVersion,
)
from app.services.plugins.errors import PluginUserVisibleError
from app.services.plugins.external_wakeup_service import ExternalWakeupService
from app.services.plugins.runtime import run_external_daemon, run_im_plugin, run_short_lived_event


def _parse_cron_field(value: str, *, minimum: int, maximum: int, sunday_alias: bool = False) -> set[int]:
    values: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError("empty cron field")
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
            if step < 1:
                raise ValueError("cron step must be positive")
        if part == "*":
            start, end = minimum, maximum
        elif "-" in part:
            raw_start, raw_end = part.split("-", 1)
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(part)
        if sunday_alias:
            if start == 7:
                start = 0
            if end == 7:
                end = 0
        if start < minimum or start > maximum or end < minimum or end > maximum:
            raise ValueError("cron field out of range")
        if start > end:
            raise ValueError("cron ranges must be ascending")
        values.update(range(start, end + 1, step))
    return values


def validate_cron_expression(expression: str) -> str:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError("cron expression must have 5 fields")
    _parse_cron_field(fields[0], minimum=0, maximum=59)
    _parse_cron_field(fields[1], minimum=0, maximum=23)
    _parse_cron_field(fields[2], minimum=1, maximum=31)
    _parse_cron_field(fields[3], minimum=1, maximum=12)
    _parse_cron_field(fields[4], minimum=0, maximum=7, sunday_alias=True)
    return " ".join(fields)


def next_cron_run(expression: str, after: datetime) -> datetime:
    fields = validate_cron_expression(expression).split()
    minutes = _parse_cron_field(fields[0], minimum=0, maximum=59)
    hours = _parse_cron_field(fields[1], minimum=0, maximum=23)
    days = _parse_cron_field(fields[2], minimum=1, maximum=31)
    months = _parse_cron_field(fields[3], minimum=1, maximum=12)
    weekdays = _parse_cron_field(fields[4], minimum=0, maximum=7, sunday_alias=True)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = candidate + timedelta(days=366)
    while candidate <= deadline:
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and cron_weekday in weekdays
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("cron expression has no run time in the next year")


@dataclass
class DaemonHandle:
    plugin_id: str
    process_type: str
    process: mp.Process
    queue: Any
    version_id: str


class PluginRuntimeManager:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        settings: Settings,
        external_wakeup_service: ExternalWakeupService,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.external_wakeup_service = external_wakeup_service
        self._ctx = mp.get_context("spawn")
        self._pool: ProcessPoolExecutor | None = None
        self._daemon_handles: dict[str, DaemonHandle] = {}
        self._short_lived_futures: dict[tuple[str, str], Future] = {}
        self._short_lived_next_run: dict[tuple[str, str], datetime] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="plugin-runtime-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            for plugin_id in list(self._daemon_handles):
                self._stop_daemon_handle(plugin_id)
            self._daemon_handles.clear()
            self._short_lived_next_run.clear()
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def reload_plugin(self, plugin_id: str) -> None:
        with self._lock:
            self._stop_daemon_handle(plugin_id)
            for key in list(self._short_lived_next_run):
                if key[0] == plugin_id:
                    self._short_lived_next_run.pop(key, None)

    def run_once(self) -> None:
        with self._lock:
            self._drain_queues()
            self._handle_finished_short_lived()
            self._sync_plugins()

    def run_short_lived_event_now(self, plugin_id: str, event_name: str) -> None:
        self.trigger_short_lived_event(plugin_id, event_name)

    def trigger_short_lived_event(self, plugin_id: str, event_name: str) -> None:
        with self._lock:
            self._submit_short_lived_event(plugin_id, event_name)

    def update_short_lived_schedule(
        self,
        plugin_id: str,
        event_name: str,
        *,
        schedule_mode: str,
        interval_seconds: int | None,
        cron_expression: str | None,
    ) -> None:
        key = (plugin_id, event_name)
        now = datetime.now(UTC).replace(tzinfo=None)
        with self._lock:
            if schedule_mode == "interval" and interval_seconds:
                self._short_lived_next_run[key] = now + timedelta(seconds=max(int(interval_seconds), 1))
            elif schedule_mode == "cron" and cron_expression:
                self._short_lived_next_run[key] = next_cron_run(cron_expression, now)
            else:
                self._short_lived_next_run.pop(key, None)

    def _run_loop(self) -> None:
        interval = max(float(self.settings.plugin_watchdog_interval_seconds), 0.2)
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                pass
            time.sleep(interval)

    def _ensure_pool(self) -> ProcessPoolExecutor:
        if self._pool is not None:
            return self._pool
        self._pool = ProcessPoolExecutor(
            max_workers=max(int(self.settings.plugin_short_lived_max_workers), 1),
            mp_context=self._ctx,
            max_tasks_per_child=1,
        )
        return self._pool

    def _drain_queues(self) -> None:
        for plugin_id, handle in list(self._daemon_handles.items()):
            while True:
                try:
                    item = handle.queue.get_nowait()
                except Empty:
                    break
                self._handle_queue_message(plugin_id, handle.version_id, handle.process_type, item)

    def _handle_queue_message(self, plugin_id: str, version_id: str, process_type: str, payload: dict[str, Any]) -> None:
        with self.session_factory() as session:
            plugin = session.get(PluginDefinition, plugin_id)
            version = session.get(PluginVersion, version_id)
            if not plugin or not version:
                session.rollback()
                return
            run_state = self._ensure_run_state(session, plugin_id)
            kind = payload.get("type")
            if kind == "heartbeat":
                run_state.status = "running"
                run_state.heartbeat_at = str(payload.get("occurred_at") or datetime.now(UTC).isoformat())
            elif kind == "external_event":
                self.external_wakeup_service.ingest(
                    session,
                    plugin=plugin,
                    version=version,
                    event_name=str(payload.get("plugin_event") or ""),
                    envelope=dict(payload.get("envelope") or {}),
                )
                run_state.status = "running"
                run_state.heartbeat_at = datetime.now(UTC).isoformat()
            elif kind == "error":
                run_state.status = "failed"
                run_state.error_text = str(payload.get("error") or "unknown plugin runtime error")
            elif kind == "user_error":
                user_id = str(payload.get("user_id") or "").strip()
                if user_id:
                    self._record_user_error(
                        session,
                        plugin=plugin,
                        user_id=user_id,
                        message=str(payload.get("error") or "Plugin runtime error"),
                    )
            elif kind == "user_error_clear":
                user_id = str(payload.get("user_id") or "").strip()
                if user_id:
                    self._clear_user_error(session, plugin_id=plugin_id, user_id=user_id)
            session.commit()

    def _submit_short_lived_event(self, plugin_id: str, event_name: str) -> bool:
        key = (plugin_id, event_name)
        if key in self._short_lived_futures:
            return False
        with self.session_factory() as session:
            plugin = session.get(PluginDefinition, plugin_id)
            if not plugin or plugin.status != "enabled" or not plugin.active_version_id:
                return False
            active_version = session.get(PluginVersion, plugin.active_version_id)
            if not active_version:
                return False
            event = session.scalar(
                select(PluginEventDefinition).where(
                    PluginEventDefinition.plugin_id == plugin_id,
                    PluginEventDefinition.plugin_version_id == active_version.id,
                    PluginEventDefinition.name == event_name,
                )
            )
            if not event or event.mode != "short_lived":
                return False
            cfg = session.scalar(
                select(PluginEventConfig).where(
                    PluginEventConfig.plugin_id == plugin_id,
                    PluginEventConfig.event_name == event_name,
                )
            )
            if cfg and not cfg.is_enabled:
                return False
            config_json = dict(event.default_config_json or {})
            if cfg:
                config_json.update(cfg.config_json or {})
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
            )
            self._short_lived_futures[key] = future
            return True

    def _handle_finished_short_lived(self) -> None:
        for key, future in list(self._short_lived_futures.items()):
            if not future.done():
                continue
            plugin_id, event_name = key
            self._short_lived_futures.pop(key, None)
            try:
                result = future.result()
            except Exception as exc:
                with self.session_factory() as session:
                    plugin = session.get(PluginDefinition, plugin_id)
                    if isinstance(exc, PluginUserVisibleError) and plugin and exc.user_id:
                        self._record_user_error(session, plugin=plugin, user_id=exc.user_id, message=str(exc))
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
                continue
            with self.session_factory() as session:
                plugin = session.get(PluginDefinition, plugin_id)
                version = session.get(PluginVersion, plugin.active_version_id) if plugin and plugin.active_version_id else None
                if not plugin or not version:
                    session.rollback()
                    continue
                self.external_wakeup_service.ingest(
                    session,
                    plugin=plugin,
                    version=version,
                    event_name=event_name,
                    envelope=result,
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
                versions = {
                    item.id: item
                    for item in session.scalars(select(PluginVersion)).all()
                }
                event_rows = list(session.scalars(select(PluginEventDefinition)).all())
                event_configs = list(session.scalars(select(PluginEventConfig)).all())
                event_config_map = {(item.plugin_id, item.event_name): item for item in event_configs}
        except ProgrammingError:
            return

        event_by_plugin: dict[str, list[PluginEventDefinition]] = {}
        for item in event_rows:
            event_by_plugin.setdefault(item.plugin_id, []).append(item)

        enabled_plugin_ids = {item.id for item in plugins if item.status == "enabled" and item.active_version_id}
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
                        if key not in self._short_lived_futures and next_run <= now:
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
                            )
                            self._short_lived_futures[key] = future
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

    def _ensure_external_daemon(
        self,
        plugin: PluginDefinition,
        version: PluginVersion,
        daemon_events: list[dict[str, Any]],
    ) -> None:
        existing = self._daemon_handles.get(plugin.id)
        if existing and existing.process.is_alive() and existing.version_id == version.id:
            return
        self._stop_daemon_handle(plugin.id)
        queue = self._ctx.Queue()
        process = self._ctx.Process(
            target=run_external_daemon,
            args=(
                version.manifest_path,
                plugin.entry_module,
                plugin.name,
                version.version,
                dict(plugin.config_json or {}),
                daemon_events,
                plugin.data_dir,
                queue,
            ),
            daemon=True,
        )
        process.start()
        self._daemon_handles[plugin.id] = DaemonHandle(
            plugin_id=plugin.id,
            process_type="external_daemon",
            process=process,
            queue=queue,
            version_id=version.id,
        )
        with self.session_factory() as session:
            run_state = self._ensure_run_state(session, plugin.id)
            run_state.current_version_id = version.id
            run_state.process_type = "external_daemon"
            run_state.pid = process.pid
            run_state.status = "running"
            run_state.error_text = None
            run_state.meta_json = {"backend": "process"}
            session.commit()

    def _ensure_im_process(self, plugin: PluginDefinition, version: PluginVersion) -> None:
        existing = self._daemon_handles.get(plugin.id)
        if existing and existing.process.is_alive() and existing.version_id == version.id:
            return
        self._stop_daemon_handle(plugin.id)
        queue = self._ctx.Queue()
        process = self._ctx.Process(
            target=run_im_plugin,
            args=(
                version.manifest_path,
                plugin.entry_module,
                plugin.service_function_name or "run",
                plugin.name,
                version.version,
                dict(plugin.config_json or {}),
                plugin.data_dir,
                queue,
            ),
            daemon=True,
        )
        process.start()
        self._daemon_handles[plugin.id] = DaemonHandle(
            plugin_id=plugin.id,
            process_type="im",
            process=process,
            queue=queue,
            version_id=version.id,
        )
        with self.session_factory() as session:
            run_state = self._ensure_run_state(session, plugin.id)
            run_state.current_version_id = version.id
            run_state.process_type = "im"
            run_state.pid = process.pid
            run_state.status = "running"
            run_state.error_text = None
            run_state.meta_json = {"backend": "process"}
            session.commit()

    def _stop_daemon_handle(self, plugin_id: str) -> None:
        handle = self._daemon_handles.pop(plugin_id, None)
        if not handle:
            return
        if handle.process.is_alive():
            handle.process.terminate()
            handle.process.join(timeout=2)
        with self.session_factory() as session:
            run_state = self._ensure_run_state(session, plugin_id)
            run_state.status = "stopped"
            run_state.pid = None
            session.commit()

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

    def _record_user_error(self, session: Session, *, plugin: PluginDefinition, user_id: str, message: str) -> None:
        row = self._ensure_user_config(session, plugin, user_id)
        row.error_text = message.strip() or "Plugin runtime error"
        row.error_at = datetime.now(UTC).replace(tzinfo=None)
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
        current.error_text = None
        current.error_at = None
        session.flush()
