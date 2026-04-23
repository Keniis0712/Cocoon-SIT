from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginEventDefinition,
    PluginRunState,
    PluginVersion,
)
from app.services.plugins.schema_validation import PluginSchemaValidationError
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
            prune_unused_packages=lambda **kwargs: dependency_calls.append(("prune_unused_packages", kwargs)),
        ),
        runtime_manager=SimpleNamespace(
            reload_plugin=lambda plugin_id: runtime_calls.append(("reload", plugin_id)),
            run_once=lambda: runtime_calls.append(("run_once",)),
            update_short_lived_schedule=lambda plugin_id, event_name, **kwargs: runtime_calls.append(
                ("schedule", plugin_id, event_name, kwargs)
            ),
            trigger_short_lived_event=lambda plugin_id, event_name: runtime_calls.append(("run", plugin_id, event_name)),
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
        ("update_event_schedule", ("missing", "tick"), {"schedule_mode": "manual", "schedule_interval_seconds": None, "schedule_cron": None}),
        ("run_short_lived_event_now", ("missing", "tick"), {}),
        ("set_event_enabled", ("missing", "tick", True), {}),
    ],
)
def test_plugin_service_public_methods_raise_404_for_missing_plugins(tmp_path, method_name, args, kwargs):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        with pytest.raises(Exception) as exc_info:
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


def test_plugin_service_update_plugin_rolls_back_enabled_plugin_when_install_fails(tmp_path, monkeypatch):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=True)
        original_version = plugin.active_version_id

        monkeypatch.setattr(
            service,
            "_install_or_update",
            lambda session, upload, existing_plugin=None: (_ for _ in ()).throw(RuntimeError("boom")),
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
            __import__("sqlalchemy").select(PluginEventConfig).where(
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


def test_plugin_service_updates_event_schedule_and_manual_run(tmp_path):
    session_factory = _session_factory()
    service, runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=True, with_event_config=False)

        detail = service.update_event_schedule(
            session,
            plugin.id,
            "tick",
            schedule_mode="interval",
            schedule_interval_seconds=30,
            schedule_cron=None,
        )
        run_detail = service.run_short_lived_event_now(session, plugin.id, "tick")

        config = session.scalar(
            __import__("sqlalchemy").select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin.id,
                PluginEventConfig.event_name == "tick",
            )
        )

    assert detail.events[0].schedule_mode == "interval"
    assert detail.events[0].schedule_interval_seconds == 30
    assert run_detail.events[0].schedule_interval_seconds == 30
    assert config is not None and config.schedule_mode == "interval"
    assert runtime_calls == [
        (
            "schedule",
            "plugin-1",
            "tick",
            {
                "schedule_mode": "interval",
                "interval_seconds": 30,
                "cron_expression": None,
            },
        ),
        ("run", "plugin-1", "tick"),
    ]


def test_plugin_service_run_short_lived_event_reports_unsubmitted_run(tmp_path):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)
    service.runtime_manager.trigger_short_lived_event = lambda plugin_id, event_name: False

    with session_factory() as session:
        plugin = _seed_plugin(session, enabled=True, with_event_config=False)

        with pytest.raises(Exception) as exc_info:
            service.run_short_lived_event_now(session, plugin.id, "tick")

    assert getattr(exc_info.value, "status_code", None) == 409


def test_plugin_service_delete_and_validate_payload_cleanup(tmp_path, monkeypatch):
    session_factory = _session_factory()
    service, _runtime_calls, dependency_calls = _service(tmp_path)
    removed_paths = []

    monkeypatch.setattr(
        "app.services.plugins.service.shutil.rmtree",
        lambda path, ignore_errors=True: removed_paths.append(Path(path)),
    )

    with session_factory() as session:
        plugin = _seed_plugin(session)
        session.add(
            PluginDispatchRecord(
                id="dispatch-1",
                plugin_id=plugin.id,
                plugin_version_id="version-1",
                event_name="tick",
                target_type="cocoon",
                target_id="cocoon-1",
            )
        )
        session.add(
            PluginEventConfig(
                id="event-config-extra",
                plugin_id=plugin.id,
                event_name="tick",
                is_enabled=True,
                config_json={"interval": 5},
            )
        )
        session.commit()

        service.delete_plugin(session, plugin.id)

        assert session.get(PluginDefinition, plugin.id) is None
        prune_call = next(call for call in dependency_calls if call[0] == "prune_unused_packages")
        assert prune_call[1]["manifest_paths"] == []

    assert Path("plugins/demo/versions/1.0.0") in removed_paths
    assert Path("plugin-data/demo") in removed_paths

    monkeypatch.setattr(
        "app.services.plugins.service.validate_json_schema_value",
        lambda schema, payload, location: (_ for _ in ()).throw(PluginSchemaValidationError("bad schema")),
    )
    with pytest.raises(Exception) as exc_info:
        service._validate_config_payload({}, {}, location="plugin_config")
    assert getattr(exc_info.value, "status_code", None) == 400
