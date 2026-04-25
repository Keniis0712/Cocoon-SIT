from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from concurrent.futures import Future, ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from queue import Empty
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import PluginDefinition, PluginVersion
from app.services.access.im_bind_token_service import ImBindTokenService
from app.services.plugins.external_wakeup_service import ExternalWakeupService
from app.services.plugins.manager.access_mixin import PluginManagerAccessMixin
from app.services.plugins.manager.event_mixin import PluginEventRuntimeMixin
from app.services.plugins.manager.im_delivery_mixin import PluginImDeliveryMixin
from app.services.plugins.manager.im_rpc_mixin import PluginImRpcMixin
from app.services.plugins.manager.models import (
    DaemonHandle,
    ShortLivedScope,
    next_cron_run,
    validate_cron_expression,
)
from app.services.plugins.manager.process_mixin import PluginProcessRuntimeMixin
from app.services.workspace.message_dispatch_service import MessageDispatchService

logger = logging.getLogger(__name__)


class PluginRuntimeManager(
    PluginEventRuntimeMixin,
    PluginProcessRuntimeMixin,
    PluginImDeliveryMixin,
    PluginImRpcMixin,
    PluginManagerAccessMixin,
):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        settings: Settings,
        external_wakeup_service: ExternalWakeupService,
        message_dispatch_service: MessageDispatchService,
        im_bind_token_service: ImBindTokenService,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.external_wakeup_service = external_wakeup_service
        self.message_dispatch_service = message_dispatch_service
        self.im_bind_token_service = im_bind_token_service
        self._ctx = mp.get_context("spawn")
        self._pool: ProcessPoolExecutor | None = None
        self._daemon_handles: dict[str, DaemonHandle] = {}
        self._short_lived_futures: dict[tuple[str, str, str, str], Future] = {}
        self._short_lived_next_run: dict[tuple[str, str], datetime] = {}
        self._im_deliveries_in_flight: dict[str, tuple[str, datetime]] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="plugin-runtime-manager", daemon=True
        )
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
            self._im_deliveries_in_flight.clear()
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def reload_plugin(self, plugin_id: str) -> None:
        with self._lock:
            self._stop_daemon_handle(plugin_id)
            for key in list(self._short_lived_next_run):
                if key[0] == plugin_id:
                    self._short_lived_next_run.pop(key, None)
            for delivery_id, delivery_state in list(self._im_deliveries_in_flight.items()):
                current_plugin_id = delivery_state[0]
                if current_plugin_id == plugin_id:
                    self._im_deliveries_in_flight.pop(delivery_id, None)

    def run_once(self) -> None:
        with self._lock:
            self._drain_queues()
            self._handle_finished_short_lived()
            self._sync_plugins()
            self._dispatch_im_deliveries()

    def run_short_lived_event_now(self, plugin_id: str, event_name: str) -> None:
        self.trigger_short_lived_event(plugin_id, event_name)

    def trigger_short_lived_event(self, plugin_id: str, event_name: str) -> bool:
        with self._lock:
            return self._submit_short_lived_event(plugin_id, event_name)

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
                self._short_lived_next_run[key] = now + timedelta(
                    seconds=max(int(interval_seconds), 1)
                )
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
                logger.exception("Plugin runtime loop failed")
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
                    item = handle.outbound_queue.get_nowait()
                except Empty:
                    break
                self._handle_queue_message(plugin_id, handle.version_id, handle.process_type, item)

    def _handle_queue_message(
        self, plugin_id: str, version_id: str, process_type: str, payload: dict[str, Any]
    ) -> None:
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
                run_state.heartbeat_at = str(
                    payload.get("occurred_at") or datetime.now(UTC).isoformat()
                )
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
            elif kind == "im_inbound_message":
                self._ingest_im_inbound_message(session, plugin=plugin, payload=payload)
                run_state.status = "running"
                run_state.heartbeat_at = datetime.now(UTC).isoformat()
            elif kind == "delivery_result":
                self._handle_im_delivery_result(session, plugin=plugin, payload=payload)
                run_state.status = "running"
                run_state.heartbeat_at = datetime.now(UTC).isoformat()
            elif kind == "rpc_request":
                self._handle_im_rpc_request(session, plugin=plugin, payload=payload)
                run_state.status = "running"
                run_state.heartbeat_at = datetime.now(UTC).isoformat()
            session.commit()


__all__ = [
    "PluginRuntimeManager",
    "validate_cron_expression",
    "next_cron_run",
    "DaemonHandle",
    "ShortLivedScope",
]
