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
    PluginVersion,
)
from app.services.plugins.external_wakeup_service import ExternalWakeupService
from app.services.plugins.runtime import run_external_daemon, run_im_plugin, run_short_lived_event


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
        with self._lock:
            self._short_lived_next_run[(plugin_id, event_name)] = datetime.now(UTC).replace(tzinfo=None)
        self.run_once()

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
            session.commit()

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
                        interval_seconds = int(
                            (cfg.config_json if cfg else {}).get("interval_seconds")
                            or self.settings.plugin_short_lived_default_interval_seconds
                        )
                        next_run = self._short_lived_next_run.get(key)
                        if next_run is None:
                            self._short_lived_next_run[key] = now
                            next_run = now
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
                            self._short_lived_next_run[key] = now + timedelta(seconds=max(interval_seconds, 1))
                if daemon_events:
                    self._ensure_external_daemon(plugin, active_version, daemon_events)
            elif plugin.plugin_type == "im":
                self._ensure_im_process(plugin, active_version)

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
