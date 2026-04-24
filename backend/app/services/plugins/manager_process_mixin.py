from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.models import (
    PluginDefinition,
    PluginVersion,
)
from app.services.plugins.manager_models import DaemonHandle
from app.services.plugins.runtime import run_external_daemon, run_im_plugin

logger = logging.getLogger(__name__)


class PluginProcessRuntimeMixin:
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
        outbound_queue = self._ctx.Queue()
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
                outbound_queue,
            ),
            daemon=True,
        )
        process.start()
        self._daemon_handles[plugin.id] = DaemonHandle(
            plugin_id=plugin.id,
            process_type="external_daemon",
            process=process,
            outbound_queue=outbound_queue,
            inbound_queue=None,
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
        inbound_queue = self._ctx.Queue()
        outbound_queue = self._ctx.Queue()
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
                inbound_queue,
                outbound_queue,
            ),
            daemon=True,
        )
        process.start()
        self._daemon_handles[plugin.id] = DaemonHandle(
            plugin_id=plugin.id,
            process_type="im",
            process=process,
            outbound_queue=outbound_queue,
            inbound_queue=inbound_queue,
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
        if handle.inbound_queue is not None:
            try:
                handle.inbound_queue.put(
                    {"type": "stop", "occurred_at": datetime.now(UTC).isoformat()}
                )
            except Exception:
                logger.debug("Failed to send stop signal to plugin_id=%s", plugin_id, exc_info=True)
        if handle.process.is_alive():
            handle.process.terminate()
            handle.process.join(timeout=2)
        with self.session_factory() as session:
            run_state = self._ensure_run_state(session, plugin_id)
            run_state.status = "stopped"
            run_state.pid = None
            session.commit()
