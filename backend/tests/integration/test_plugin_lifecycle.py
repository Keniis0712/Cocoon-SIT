from __future__ import annotations

import io
import json
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.models import (
    PluginDefinition,
)

pytestmark = pytest.mark.integration


def _plugin_zip(*, manifest: dict, sources: dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as bundle:
        bundle.writestr("plugin.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, content in sources.items():
            bundle.writestr(path, content)
    buffer.seek(0)
    return buffer


def _install_response(client, auth_headers, *, manifest: dict, sources: dict[str, str]):
    payload = _plugin_zip(manifest=manifest, sources=sources)
    return client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", payload.getvalue(), "application/zip")},
    )


def _bind_plugin_target(client, auth_headers, plugin_id: str, *, target_type: str, target_id: str):
    response = client.post(
        f"/api/v1/plugins/{plugin_id}/targets",
        headers=auth_headers,
        json={"target_type": target_type, "target_id": target_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_plugin_update_and_delete(client, auth_headers):
    install = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "updatable",
            "version": "1.0.0",
            "display_name": "Updatable",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    update_zip = _plugin_zip(
        manifest={
            "name": "updatable",
            "version": "2.0.0",
            "display_name": "Updatable Two",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event updated",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )
    update = client.post(
        f"/api/v1/admin/plugins/{plugin_id}/update",
        headers=auth_headers,
        files={"file": ("plugin.zip", update_zip.getvalue(), "application/zip")},
    )
    assert update.status_code == 200, update.text
    assert update.json()["display_name"] == "Updatable Two"
    assert update.json()["active_version"]["version"] == "2.0.0"

    delete = client.delete(f"/api/v1/admin/plugins/{plugin_id}", headers=auth_headers)
    assert delete.status_code == 200, delete.text
    assert delete.json()["deleted"] is True


def test_plugin_config_and_event_config_validate_json_schema(client, auth_headers):
    install = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "schema-plugin",
            "version": "1.0.0",
            "display_name": "Schema Plugin",
            "plugin_type": "external",
            "entry_module": "main",
            "config_schema": {
                "type": "object",
                "required": ["api_key"],
                "properties": {
                    "api_key": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
            },
            "default_config": {"api_key": "seed", "timeout": 5},
            "events": [
                {
                    "name": "poller",
                    "mode": "short_lived",
                    "function_name": "poller",
                    "title": "Poller",
                    "description": "Schema checked event",
                    "config_schema": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "enum": ["a", "b"]},
                        },
                    },
                    "default_config": {"channel": "a"},
                }
            ],
        },
        sources={"main.py": "def poller(ctx):\n    return None\n"},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    bad_plugin_config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/config",
        headers=auth_headers,
        json={"config_json": {"api_key": 123, "timeout": "slow"}},
    )
    assert bad_plugin_config.status_code == 400, bad_plugin_config.text

    good_plugin_config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/config",
        headers=auth_headers,
        json={"config_json": {"api_key": "abc", "timeout": 10}},
    )
    assert good_plugin_config.status_code == 200, good_plugin_config.text

    bad_event_config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/events/poller/config",
        headers=auth_headers,
        json={"config_json": {"channel": "c"}},
    )
    assert bad_event_config.status_code == 400, bad_event_config.text

    good_event_config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/events/poller/config",
        headers=auth_headers,
        json={"config_json": {"channel": "b"}},
    )
    assert good_event_config.status_code == 200, good_event_config.text

    schedule = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/events/poller/schedule",
        headers=auth_headers,
        json={"schedule_mode": "interval", "schedule_interval_seconds": 30, "schedule_cron": None},
    )
    assert schedule.status_code == 200, schedule.text
    assert schedule.json()["events"][0]["schedule_mode"] == "interval"
    assert schedule.json()["events"][0]["schedule_interval_seconds"] == 30


def test_plugin_install_rejects_invalid_default_config(client, auth_headers):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "invalid-defaults",
            "version": "1.0.0",
            "display_name": "Invalid Defaults",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "bad",
                    "mode": "short_lived",
                    "function_name": "bad",
                    "title": "Bad",
                    "description": "Bad defaults",
                    "config_schema": {
                        "type": "object",
                        "required": ["channel"],
                        "properties": {"channel": {"type": "string"}},
                    },
                    "default_config": {"channel": 123},
                }
            ],
        },
        sources={"main.py": "def bad(ctx):\n    return None\n"},
    )
    assert response.status_code == 400, response.text


def test_plugin_install_rejects_event_interval_seconds_config(client, auth_headers):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "reserved-event-schedule",
            "version": "1.0.0",
            "display_name": "Reserved Event Schedule",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event",
                    "config_schema": {
                        "type": "object",
                        "properties": {"interval_seconds": {"type": "integer"}},
                    },
                    "default_config": {},
                }
            ],
        },
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )
    assert response.status_code == 400, response.text
    assert "event schedule settings" in response.text


def test_plugin_install_rejects_invalid_manifest_as_bad_request(client, auth_headers):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "invalid-manifest",
            "version": "1.0.0",
            "display_name": "Invalid Manifest",
            "plugin_type": "external",
            "entry_module": "main",
        },
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )

    assert response.status_code == 400, response.text
    assert "External plugins must define at least one event" in response.text


def test_plugin_install_failure_cleans_partial_version_directory(client, auth_headers):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "missing-function",
            "version": "1.0.0",
            "display_name": "Missing Function",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Missing function event",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={"main.py": "def other(ctx):\n    return None\n"},
    )

    assert response.status_code == 400, response.text
    assert "Plugin validation failed" in response.text
    container = client.app.state.container
    assert not (container.settings.plugin_root / "missing-function" / "versions" / "1.0.0").exists()
    assert not (container.settings.plugin_data_root / "missing-function").exists()
    with container.session_factory() as session:
        plugin = session.scalar(
            select(PluginDefinition).where(PluginDefinition.name == "missing-function")
        )
        assert plugin is None
