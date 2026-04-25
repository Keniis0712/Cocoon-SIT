import asyncio
from types import SimpleNamespace

import pytest

import app.services.plugins.runtime.runtime as runtime
from app.services.plugins.errors import PluginUserVisibleError


class _Queue:
    def __init__(self):
        self.items = []

    def put(self, value):
        self.items.append(value)


def test_normalize_envelope_accepts_none_and_dict():
    assert runtime._normalize_envelope(None) is None
    assert runtime._normalize_envelope({"ok": True}) == {"ok": True}

    with pytest.raises(TypeError):
        runtime._normalize_envelope("bad")


def test_run_short_lived_event_supports_sync_and_async(monkeypatch):
    async def async_event(context):
        context.heartbeat()
        return {"summary": "async wakeup"}

    def sync_event(context):
        return {"summary": "sync wakeup"}

    module = SimpleNamespace(async_event=async_event, sync_event=sync_event)
    monkeypatch.setattr("app.services.plugins.runtime.runtime.bootstrap_module", lambda manifest_path, entry_module: module)

    sync_result = runtime.run_short_lived_event(
        manifest_path="manifest.json",
        entry_module="plugin",
        function_name="sync_event",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        event_name="sync",
        event_config={},
        data_dir="data",
    )
    async_result = runtime.run_short_lived_event(
        manifest_path="manifest.json",
        entry_module="plugin",
        function_name="async_event",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        event_name="async",
        event_config={},
        data_dir="data",
    )

    assert sync_result == {"summary": "sync wakeup"}
    assert async_result == {"summary": "async wakeup"}


def test_run_external_daemon_function_requires_async_and_can_emit_events():
    module = SimpleNamespace(sync_event=lambda context: None)

    with pytest.raises(TypeError):
        asyncio.run(
            runtime._run_external_daemon_function(
                module,
                function_name="sync_event",
                plugin_name="plugin-a",
                plugin_version="1.0.0",
                event_name="daemon",
                plugin_config={},
                event_config={},
                data_dir="data",
                outbound_queue=_Queue(),
            )
        )

    async def async_event(context):
        context.emit_event({"summary": "daemon wakeup"})

    queue = _Queue()
    module = SimpleNamespace(async_event=async_event)
    asyncio.run(
        runtime._run_external_daemon_function(
            module,
            function_name="async_event",
            plugin_name="plugin-a",
            plugin_version="1.0.0",
            event_name="daemon",
            plugin_config={},
            event_config={},
            data_dir="data",
            outbound_queue=queue,
        )
    )

    assert queue.items[0]["type"] == "external_event"


def test_run_external_daemon_and_im_plugin(monkeypatch):
    async def daemon_one(context):
        context.emit_event({"summary": "daemon wakeup"})

    async def daemon_two(context):
        context.heartbeat()

    async def im_async(context):
        context.heartbeat()

    def im_sync(context):
        context.heartbeat()

    queue = _Queue()
    module = SimpleNamespace(daemon_one=daemon_one, daemon_two=daemon_two, im_async=im_async, im_sync=im_sync)
    monkeypatch.setattr("app.services.plugins.runtime.runtime.bootstrap_module", lambda manifest_path, entry_module: module)
    monkeypatch.setattr("app.services.plugins.runtime.runtime._heartbeat_loop", lambda outbound_queue: asyncio.sleep(0))

    runtime.run_external_daemon(
        manifest_path="manifest.json",
        entry_module="plugin",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        daemon_events=[
            {"name": "daemon-one", "function_name": "daemon_one", "config_json": {}},
            {"name": "daemon-two", "function_name": "daemon_two", "config_json": {}},
        ],
        data_dir="data",
        outbound_queue=queue,
    )
    runtime.run_im_plugin(
        manifest_path="manifest.json",
        entry_module="plugin",
        service_function="im_async",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data",
        inbound_queue=_Queue(),
        outbound_queue=queue,
    )
    runtime.run_im_plugin(
        manifest_path="manifest.json",
        entry_module="plugin",
        service_function="im_sync",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data",
        inbound_queue=_Queue(),
        outbound_queue=queue,
    )

    assert any(item["type"] == "external_event" for item in queue.items)
    assert any(item["type"] == "heartbeat" for item in queue.items)


def test_runtime_reports_user_visible_errors_for_daemon_and_im(monkeypatch):
    async def daemon_user_error(_context):
        raise PluginUserVisibleError("api key invalid", user_id="user-1")

    def im_user_error(_context):
        raise PluginUserVisibleError("location not found", user_id="user-2")

    queue = _Queue()
    module = SimpleNamespace(daemon_user_error=daemon_user_error, im_user_error=im_user_error)
    monkeypatch.setattr("app.services.plugins.runtime.runtime.bootstrap_module", lambda manifest_path, entry_module: module)
    monkeypatch.setattr("app.services.plugins.runtime.runtime._heartbeat_loop", lambda outbound_queue: asyncio.sleep(0))

    runtime.run_external_daemon(
        manifest_path="manifest.json",
        entry_module="plugin",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        daemon_events=[{"name": "daemon-user-error", "function_name": "daemon_user_error", "config_json": {}}],
        data_dir="data",
        outbound_queue=queue,
    )
    runtime.run_im_plugin(
        manifest_path="manifest.json",
        entry_module="plugin",
        service_function="im_user_error",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data",
        inbound_queue=_Queue(),
        outbound_queue=queue,
    )

    user_errors = [item for item in queue.items if item.get("type") == "user_error"]
    assert any(item["user_id"] == "user-1" and item["error"] == "api key invalid" for item in user_errors)
    assert any(item["user_id"] == "user-2" and item["error"] == "location not found" for item in user_errors)


def test_validate_plugin_functions_checks_external_and_im_manifests(monkeypatch):
    async def daemon_ok(context):
        return None

    def short_ok(context):
        return None

    def im_ok(context):
        return None

    def validate_settings(context):
        return None

    module = SimpleNamespace(daemon_ok=daemon_ok, short_ok=short_ok, im_ok=im_ok, validate_settings=validate_settings)
    monkeypatch.setattr("app.services.plugins.runtime.runtime.bootstrap_module", lambda manifest_path, entry_module: module)

    runtime.validate_plugin_functions(
        manifest_path="manifest.json",
        entry_module="plugin",
        plugin_type="external",
        events=[
            {"name": "short", "function_name": "short_ok", "mode": "short_lived"},
            {"name": "daemon", "function_name": "daemon_ok", "mode": "daemon"},
        ],
        settings_validation_function="validate_settings",
    )
    runtime.validate_plugin_functions(
        manifest_path="manifest.json",
        entry_module="plugin",
        plugin_type="im",
        events=[],
        service_function="im_ok",
    )

    with pytest.raises(ValueError):
        runtime.validate_plugin_functions(
            manifest_path="manifest.json",
            entry_module="plugin",
            plugin_type="external",
            events=[{"name": "missing", "function_name": "missing_fn", "mode": "short_lived"}],
        )

    with pytest.raises(ValueError):
        runtime.validate_plugin_functions(
            manifest_path="manifest.json",
            entry_module="plugin",
            plugin_type="external",
            events=[{"name": "bad-daemon", "function_name": "short_ok", "mode": "daemon"}],
        )

    with pytest.raises(ValueError):
        runtime.validate_plugin_functions(
            manifest_path="manifest.json",
            entry_module="plugin",
            plugin_type="im",
            events=[],
            service_function="missing_fn",
        )

    with pytest.raises(ValueError):
        runtime.validate_plugin_functions(
            manifest_path="manifest.json",
            entry_module="plugin",
            plugin_type="external",
            events=[{"name": "short", "function_name": "short_ok", "mode": "short_lived"}],
            settings_validation_function="missing_fn",
        )


def test_validate_plugin_settings_supports_sync_and_async(monkeypatch):
    async def validate_async(context):
        assert context.user_id == "user-1"
        return {"ok": False, "message": "invalid key"}

    def validate_sync(context):
        return None

    module = SimpleNamespace(validate_async=validate_async, validate_sync=validate_sync)
    monkeypatch.setattr("app.services.plugins.runtime.runtime.bootstrap_module", lambda manifest_path, entry_module: module)

    result = runtime.validate_plugin_settings(
        manifest_path="manifest.json",
        entry_module="plugin",
        validation_function="validate_async",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={"x": 1},
        user_config={"api_key": "bad"},
        user_id="user-1",
        data_dir="data",
    )
    ok_result = runtime.validate_plugin_settings(
        manifest_path="manifest.json",
        entry_module="plugin",
        validation_function="validate_sync",
        plugin_name="plugin-a",
        plugin_version="1.0.0",
        plugin_config={},
        user_config={},
        user_id="user-1",
        data_dir="data",
    )

    assert result == "invalid key"
    assert ok_result is None
