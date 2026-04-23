from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.plugins.bootstrap import bootstrap_module
from app.services.plugins.errors import PluginUserVisibleError
from app.services.plugins.external_sdk import ExternalEventContext
from app.services.plugins.im_sdk import ImPluginContext


@dataclass
class PluginSettingsValidationContext:
    plugin_name: str
    plugin_version: str
    plugin_config: dict[str, Any]
    user_config: dict[str, Any]
    user_id: str | None
    scope_type: str | None
    scope_id: str | None
    data_dir: str


def _normalize_envelope(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise TypeError("Plugin event functions must return None or a dict envelope")


def _normalize_settings_validation_result(value: Any) -> str | None:
    if value is None or value is True:
        return None
    if value is False:
        return "Plugin settings validation failed"
    if isinstance(value, str):
        text = value.strip()
        return text or "Plugin settings validation failed"
    if isinstance(value, dict):
        if value.get("ok") is True:
            return None
        message = value.get("message") or value.get("error")
        if isinstance(message, str) and message.strip():
            return message.strip()
        if value.get("ok") is False:
            return "Plugin settings validation failed"
    raise TypeError("Plugin settings validator must return None/bool/str/dict")


def run_short_lived_event(
    manifest_path: str,
    entry_module: str,
    function_name: str,
    plugin_name: str,
    plugin_version: str,
    plugin_config: dict[str, Any],
    event_name: str,
    event_config: dict[str, Any],
    data_dir: str,
    user_config: dict[str, Any] | None = None,
    user_id: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> dict[str, Any] | None:
    module = bootstrap_module(manifest_path, entry_module)
    func = getattr(module, function_name)
    context = ExternalEventContext(
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        event_name=event_name,
        plugin_config=plugin_config,
        event_config=event_config,
        data_dir=data_dir,
        user_config=dict(user_config or {}),
        user_id=user_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if inspect.iscoroutinefunction(func):
        return _normalize_envelope(asyncio.run(func(context)))
    return _normalize_envelope(func(context))


async def _run_external_daemon_function(
    module,
    *,
    function_name: str,
    plugin_name: str,
    plugin_version: str,
    event_name: str,
    plugin_config: dict[str, Any],
    event_config: dict[str, Any],
    data_dir: str,
    outbound_queue,
) -> None:
    func = getattr(module, function_name)
    if not inspect.iscoroutinefunction(func):
        raise TypeError(f"Daemon event function '{function_name}' must be async")
    context = ExternalEventContext(
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        event_name=event_name,
        plugin_config=plugin_config,
        event_config=event_config,
        data_dir=data_dir,
        outbound_queue=outbound_queue,
    )
    try:
        await func(context)
    except PluginUserVisibleError as exc:
        if outbound_queue and exc.user_id:
            outbound_queue.put(
                {
                    "type": "user_error",
                    "user_id": exc.user_id,
                    "error": str(exc),
                    "plugin_event": event_name,
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
            )
            return
        raise


async def _heartbeat_loop(outbound_queue, interval_seconds: int = 2) -> None:
    while True:
        outbound_queue.put(
            {
                "type": "heartbeat",
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
        await asyncio.sleep(interval_seconds)


def run_external_daemon(
    manifest_path: str,
    entry_module: str,
    plugin_name: str,
    plugin_version: str,
    plugin_config: dict[str, Any],
    daemon_events: list[dict[str, Any]],
    data_dir: str,
    outbound_queue,
) -> None:
    module = bootstrap_module(manifest_path, entry_module)

    async def _main() -> None:
        tasks = [asyncio.create_task(_heartbeat_loop(outbound_queue))]
        for item in daemon_events:
            tasks.append(
                asyncio.create_task(
                    _run_external_daemon_function(
                        module,
                        function_name=item["function_name"],
                        plugin_name=plugin_name,
                        plugin_version=plugin_version,
                        event_name=item["name"],
                        plugin_config=plugin_config,
                        event_config=item["config_json"],
                        data_dir=data_dir,
                        outbound_queue=outbound_queue,
                    )
                )
            )
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()

    asyncio.run(_main())


def run_im_plugin(
    manifest_path: str,
    entry_module: str,
    service_function: str,
    plugin_name: str,
    plugin_version: str,
    plugin_config: dict[str, Any],
    data_dir: str,
    outbound_queue,
) -> None:
    module = bootstrap_module(manifest_path, entry_module)
    func = getattr(module, service_function)
    context = ImPluginContext(
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        plugin_config=plugin_config,
        data_dir=data_dir,
        outbound_queue=outbound_queue,
    )
    try:
        if inspect.iscoroutinefunction(func):
            asyncio.run(func(context))
            return
        func(context)
    except PluginUserVisibleError as exc:
        if outbound_queue and exc.user_id:
            outbound_queue.put(
                {
                    "type": "user_error",
                    "user_id": exc.user_id,
                    "error": str(exc),
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
            )
            return
        raise


def validate_plugin_functions(
    manifest_path: str,
    entry_module: str,
    plugin_type: str,
    *,
    events: list[dict[str, Any]],
    service_function: str | None = None,
    settings_validation_function: str | None = None,
) -> None:
    module = bootstrap_module(manifest_path, entry_module)
    if plugin_type == "external":
        for item in events:
            func = getattr(module, item["function_name"], None)
            if not callable(func):
                raise ValueError(f"Plugin function not found: {item['function_name']}")
            if item.get("mode") == "daemon" and not inspect.iscoroutinefunction(func):
                raise ValueError(f"Daemon plugin function must be async: {item['function_name']}")
    elif plugin_type == "im":
        func = getattr(module, service_function or "", None)
        if not callable(func):
            raise ValueError(f"IM service function not found: {service_function}")
    if settings_validation_function:
        validator = getattr(module, settings_validation_function, None)
        if not callable(validator):
            raise ValueError(f"Settings validation function not found: {settings_validation_function}")


def validate_plugin_settings(
    manifest_path: str,
    entry_module: str,
    validation_function: str,
    *,
    plugin_name: str,
    plugin_version: str,
    plugin_config: dict[str, Any],
    user_config: dict[str, Any],
    user_id: str | None,
    data_dir: str,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> str | None:
    module = bootstrap_module(manifest_path, entry_module)
    func = getattr(module, validation_function, None)
    if not callable(func):
        raise ValueError(f"Settings validation function not found: {validation_function}")
    context = PluginSettingsValidationContext(
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        plugin_config=dict(plugin_config or {}),
        user_config=dict(user_config or {}),
        user_id=user_id,
        scope_type=scope_type,
        scope_id=scope_id,
        data_dir=data_dir,
    )
    if inspect.iscoroutinefunction(func):
        result = asyncio.run(func(context))
    else:
        result = func(context)
    return _normalize_settings_validation_result(result)
