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


def test_plugin_service_update_plugin_config_validates_admin_plugin_settings(tmp_path, monkeypatch):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=False)
        plugin.settings_validation_function_name = "validate_settings"
        session.commit()

        monkeypatch.setattr(
            "app.services.plugins.service_install_mixin.validate_plugin_settings",
            lambda *args, **kwargs: "bad runtime config",
        )

        detail = service.update_plugin_config(session, plugin.id, {"token": "updated"})

        session.refresh(plugin)
        assert plugin.config_json == {"token": "updated"}
        assert detail.config_json == {"token": "updated"}

    assert runtime_calls == [("reload", "plugin-1"), ("run_once",)]


def test_plugin_service_validate_admin_plugin_config_runs_settings_validation(
    tmp_path, monkeypatch
):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=False)
        plugin.settings_validation_function_name = "validate_settings"
        session.commit()

        monkeypatch.setattr(
            "app.services.plugins.service_install_mixin.validate_plugin_settings",
            lambda *args, **kwargs: "bad runtime config",
        )

        with pytest.raises(Exception) as exc_info:
            service.validate_admin_plugin_config(session, plugin.id, {"token": "updated"})

        session.refresh(plugin)
        assert plugin.config_json == {"token": "current"}

    assert getattr(exc_info.value, "status_code", None) == 400
    assert runtime_calls == []


def test_plugin_service_update_plugin_rolls_back_enabled_plugin_when_install_fails(
    tmp_path, monkeypatch
):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=True)
        original_version = plugin.active_version_id

        monkeypatch.setattr(
            service,
            "_install_or_update",
            lambda session, upload, existing_plugin=None: (_ for _ in ()).throw(
                RuntimeError("boom")
            ),
        )

        with pytest.raises(RuntimeError, match="boom"):
            service.update_plugin(session, plugin.id, SimpleNamespace())

        session.refresh(plugin)
        assert plugin.status == "enabled"
        assert plugin.active_version_id == original_version

    assert runtime_calls == [
        ("reload", "plugin-1"),
        ("reload", "plugin-1"),
        ("run_once",),
    ]


def test_plugin_service_updates_event_config_and_event_enabled_records_defaults(tmp_path):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=False, with_event_config=False)

        detail = service.update_event_config(session, plugin.id, "tick", {"interval": 30})
        enabled_detail = service.set_event_enabled(session, plugin.id, "tick", False)

        config = session.scalar(
            __import__("sqlalchemy")
            .select(PluginEventConfig)
            .where(
                PluginEventConfig.plugin_id == plugin.id,
                PluginEventConfig.event_name == "tick",
            )
        )

    assert detail.events[0].config_json == {"interval": 30}
    assert enabled_detail.events[0].is_enabled is False
    assert config is not None and config.config_json == {"interval": 30}
    assert runtime_calls == [
        ("reload", "plugin-1"),
        ("run_once",),
        ("reload", "plugin-1"),
        ("run_once",),
    ]
