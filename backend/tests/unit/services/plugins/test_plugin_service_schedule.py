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
            __import__("sqlalchemy")
            .select(PluginEventConfig)
            .where(
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
