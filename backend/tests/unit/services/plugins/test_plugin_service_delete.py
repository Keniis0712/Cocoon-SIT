from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Query

from app.core.config import Settings
from app.models import (
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginEventDefinition,
    PluginImDeliveryOutbox,
    PluginImTargetRoute,
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


def test_plugin_service_delete_and_validate_payload_cleanup(tmp_path, monkeypatch):
    session_factory = _session_factory()
    service, _runtime_calls, dependency_calls = _service(tmp_path)
    removed_paths = []

    monkeypatch.setattr(
        "app.services.plugins.service_admin_mixin.shutil.rmtree",
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
        "app.services.plugins.service_install_mixin.validate_json_schema_value",
        lambda schema, payload, location: (_ for _ in ()).throw(
            PluginSchemaValidationError("bad schema")
        ),
    )
    with pytest.raises(Exception) as exc_info:
        service._validate_config_payload({}, {}, location="plugin_config")
    assert getattr(exc_info.value, "status_code", None) == 400


def test_plugin_service_delete_clears_version_references_before_removing_versions(
    tmp_path, monkeypatch
):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)
    original_delete = Query.delete
    checked = {"done": False}

    def delete_with_check(self, *args, **kwargs):
        entity = self.column_descriptions[0].get("entity")
        if entity is PluginVersion:
            plugin_id = self.whereclause.right.value  # type: ignore[attr-defined]
            plugin = self.session.get(PluginDefinition, plugin_id)
            run_state = (
                self.session.query(PluginRunState)
                .filter(PluginRunState.plugin_id == plugin_id)
                .one_or_none()
            )
            assert plugin is not None
            assert plugin.active_version_id is None
            assert run_state is None or run_state.current_version_id is None
            checked["done"] = True
        return original_delete(self, *args, **kwargs)

    monkeypatch.setattr(Query, "delete", delete_with_check)

    with session_factory() as session:
        plugin = _seed_plugin(session)
        run_state = session.get(PluginRunState, "run-state-1")
        assert run_state is not None
        run_state.current_version_id = "version-1"
        session.commit()

        service.delete_plugin(session, plugin.id)

    assert checked["done"] is True


def test_plugin_service_delete_removes_im_delivery_and_route_rows(tmp_path):
    session_factory = _session_factory()
    service, _runtime_calls, _dependency_calls = _service(tmp_path)

    with session_factory() as session:
        plugin = _seed_plugin(session)
        session.add(
            PluginImDeliveryOutbox(
                id="outbox-1",
                plugin_id=plugin.id,
                action_id=None,
                message_id=None,
                status="queued",
                payload_json={"reply_text": "hello"},
                attempt_count=0,
            )
        )
        session.add(
            PluginImTargetRoute(
                id="route-1",
                plugin_id=plugin.id,
                target_type="cocoon",
                target_id="cocoon-1",
                external_platform="onebot_v11",
                conversation_kind="private",
                external_account_id="acct-1",
                external_conversation_id="conv-1",
                route_metadata_json={"conversation_kind": "private"},
            )
        )
        session.commit()

        service.delete_plugin(session, plugin.id)

        assert session.get(PluginDefinition, plugin.id) is None
        assert session.get(PluginImDeliveryOutbox, "outbox-1") is None
        assert session.get(PluginImTargetRoute, "route-1") is None
