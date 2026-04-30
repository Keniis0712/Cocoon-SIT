from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginEventConfig,
    PluginEventDefinition,
    PluginRunState,
    PluginVersion,
)
from app.services.plugins.service import PluginService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _service(tmp_path):
    runtime_calls = []
    dependency_calls = []
    service = PluginService(
        settings=Settings(
            plugin_root=tmp_path / "plugins",
            plugin_data_root=tmp_path / "plugin-data",
        ),
        dependency_builder=SimpleNamespace(
            collect_inventory=lambda **kwargs: (
                dependency_calls.append(("collect_inventory", kwargs))
                or [
                    SimpleNamespace(
                        name="Pkg",
                        normalized_name="pkg",
                        version="1.0.0",
                        path=Path(tmp_path / "plugins" / "shared_libs" / "pkg" / "1.0.0"),
                        reference_count=2,
                        size_bytes=128,
                    )
                ]
            ),
            prune_unused_packages=lambda **kwargs: dependency_calls.append(
                ("prune_unused_packages", kwargs)
            ),
        ),
        runtime_manager=SimpleNamespace(
            reload_plugin=lambda plugin_id: runtime_calls.append(("reload", plugin_id)),
            run_once=lambda: runtime_calls.append(("run_once",)),
            update_short_lived_schedule=lambda plugin_id, event_name, **kwargs: (
                runtime_calls.append(("schedule", plugin_id, event_name, kwargs))
            ),
            trigger_short_lived_event=lambda plugin_id, event_name: runtime_calls.append(
                ("run", plugin_id, event_name)
            ),
        ),
    )
    return service, runtime_calls, dependency_calls


def _seed_plugin(session, *, enabled: bool = False, with_event_config: bool = False):
    plugin = PluginDefinition(
        id="plugin-1",
        name="demo",
        display_name="Demo Plugin",
        plugin_type="external",
        entry_module="main",
        service_function_name=None,
        status="enabled" if enabled else "disabled",
        data_dir="plugin-data/demo",
        config_schema_json={"type": "object"},
        default_config_json={"token": "seed"},
        config_json={"token": "current"},
    )
    version = PluginVersion(
        id="version-1",
        plugin_id=plugin.id,
        version="1.0.0",
        source_zip_path="plugins/demo/versions/1.0.0/source.zip",
        extracted_path="plugins/demo/versions/1.0.0/content",
        manifest_path="plugins/demo/versions/1.0.0/manifest.json",
        metadata_json={},
    )
    plugin.active_version_id = version.id
    event = PluginEventDefinition(
        id="event-def-1",
        plugin_id=plugin.id,
        plugin_version_id=version.id,
        name="tick",
        mode="short_lived",
        function_name="tick",
        title="Tick",
        description="Tick event",
        config_schema_json={"type": "object"},
        default_config_json={"interval": 5},
    )
    run_state = PluginRunState(id="run-state-1", plugin_id=plugin.id, status="running", pid=1234)
    session.add_all([plugin, version, event, run_state])
    if with_event_config:
        session.add(
            PluginEventConfig(
                id="event-config-1",
                plugin_id=plugin.id,
                event_name="tick",
                is_enabled=False,
                config_json={"interval": 10},
            )
        )
    session.commit()
    return plugin


def test_plugin_service_get_detail_list_and_shared_packages(tmp_path):
    session_factory = _session_factory()
    service, _runtime_calls, dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, with_event_config=True)

        listed = service.list_plugins(session)
        detail = service.get_plugin_detail(session, plugin.id)
        shared = service.list_shared_packages(session)

    assert [item.id for item in listed] == [plugin.id]
    assert detail.active_version.version == "1.0.0"
    assert detail.run_state.status == "running"
    assert detail.events[0].config_json == {"interval": 10}
    assert detail.events[0].is_enabled is False
    assert detail.events[0].schedule_mode == "manual"
    assert shared[0].normalized_name == "pkg"
    collect_call = next(call for call in dependency_calls if call[0] == "collect_inventory")
    assert collect_call[1]["manifest_paths"] == [Path("plugins/demo/versions/1.0.0/manifest.json")]


@pytest.mark.parametrize(
    ("method_name", "args", "kwargs"),
    [
        ("get_plugin_detail", ("missing",), {}),
        ("update_plugin", ("missing", SimpleNamespace()), {}),
        ("enable_plugin", ("missing",), {}),
        ("disable_plugin", ("missing",), {}),
        ("delete_plugin", ("missing",), {}),
        ("update_plugin_config", ("missing", {}), {}),
        ("update_event_config", ("missing", "tick", {}), {}),
        ("run_short_lived_event_now", ("missing", "tick"), {}),
        ("set_event_enabled", ("missing", "tick", True), {}),
    ],
)
def test_plugin_service_public_methods_raise_404_for_missing_plugins(
    tmp_path, method_name, args, kwargs
):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session, pytest.raises(Exception) as exc_info:
        getattr(service, method_name)(session, *args, **(kwargs or {}))

    assert getattr(exc_info.value, "status_code", None) == 404


def test_plugin_service_enable_requires_active_version_and_helpers_cover_missing_events(tmp_path):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-no-version",
            name="empty",
            display_name="Empty",
            plugin_type="external",
            entry_module="main",
            data_dir="plugin-data/empty",
        )
        session.add(plugin)
        session.commit()

        with pytest.raises(Exception) as no_version:
            service.enable_plugin(session, plugin.id)
        assert getattr(no_version.value, "status_code", None) == 400

        with pytest.raises(Exception) as no_active_event:
            service._get_active_event_definition(session, plugin, "missing")
        assert getattr(no_active_event.value, "status_code", None) == 400

        plugin.active_version_id = "version-missing"
        session.commit()
        with pytest.raises(Exception) as missing_event:
            service._get_active_event_definition(session, plugin, "missing")
        assert getattr(missing_event.value, "status_code", None) == 404


def test_plugin_service_enable_does_not_validate_admin_plugin_settings(tmp_path, monkeypatch):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=False)
        plugin.settings_validation_function_name = "validate_settings"
        session.commit()

        def _unexpected(*args, **kwargs):
            raise AssertionError("enable should not trigger admin settings validation")

        monkeypatch.setattr(
            "app.services.plugins.service.install_mixin.validate_plugin_settings", _unexpected
        )

        detail = service.enable_plugin(session, plugin.id)

        session.refresh(plugin)
        assert plugin.status == "enabled"
        assert detail.status == "enabled"

    assert runtime_calls == [("reload", "plugin-1"), ("run_once",)]
