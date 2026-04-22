from __future__ import annotations

import io
import json
from zipfile import ZipFile


def _plugin_zip(*, manifest: dict, sources: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as bundle:
        bundle.writestr("plugin.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, content in sources.items():
            bundle.writestr(path, content)
    return buffer.getvalue()


def _plugin_manifest(*, version: str) -> dict:
    return {
        "name": "api-plugin",
        "version": version,
        "display_name": "API Plugin",
        "plugin_type": "external",
        "entry_module": "main",
        "default_config": {"tick_interval": 5},
        "events": [
            {
                "name": "tick",
                "mode": "short_lived",
                "function_name": "tick",
                "title": "Tick",
                "description": "Tick event",
                "config_schema": {"type": "object"},
                "default_config": {"limit": 1},
            }
        ],
    }


def test_plugin_admin_routes_cover_detail_shared_libs_and_event_toggles(client, auth_headers):
    payload = _plugin_zip(
        manifest=_plugin_manifest(version="1.0.0"),
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )

    install = client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", payload, "application/zip")},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    listing = client.get("/api/v1/admin/plugins", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == plugin_id for item in listing.json())

    detail = client.get(f"/api/v1/admin/plugins/{plugin_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == plugin_id

    shared = client.get("/api/v1/admin/plugins/shared-libs", headers=auth_headers)
    assert shared.status_code == 200, shared.text
    assert isinstance(shared.json(), list)

    enable = client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers)
    assert enable.status_code == 200, enable.text

    event_disable = client.post(f"/api/v1/admin/plugins/{plugin_id}/events/tick/disable", headers=auth_headers)
    assert event_disable.status_code == 200, event_disable.text

    event_enable = client.post(f"/api/v1/admin/plugins/{plugin_id}/events/tick/enable", headers=auth_headers)
    assert event_enable.status_code == 200, event_enable.text

    disable = client.post(f"/api/v1/admin/plugins/{plugin_id}/disable", headers=auth_headers)
    assert disable.status_code == 200, disable.text


def test_plugin_admin_routes_cover_update_configuration_and_delete(client, auth_headers):
    install_payload = _plugin_zip(
        manifest=_plugin_manifest(version="1.0.0"),
        sources={"main.py": "def tick(ctx):\n    return {'ok': True}\n"},
    )
    install = client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", install_payload, "application/zip")},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    update_payload = _plugin_zip(
        manifest=_plugin_manifest(version="1.1.0"),
        sources={"main.py": "def tick(ctx):\n    return {'version': '1.1.0'}\n"},
    )
    update = client.post(
        f"/api/v1/admin/plugins/{plugin_id}/update",
        headers=auth_headers,
        files={"file": ("plugin-update.zip", update_payload, "application/zip")},
    )
    assert update.status_code == 200, update.text
    assert update.json()["active_version"]["version"] == "1.1.0"
    assert len(update.json()["versions"]) >= 2

    config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/config",
        headers=auth_headers,
        json={"config_json": {"tick_interval": 9}},
    )
    assert config.status_code == 200, config.text
    assert config.json()["config_json"]["tick_interval"] == 9

    event_config = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/events/tick/config",
        headers=auth_headers,
        json={"config_json": {"limit": 3}},
    )
    assert event_config.status_code == 200, event_config.text
    tick_event = next(item for item in event_config.json()["events"] if item["name"] == "tick")
    assert tick_event["config_json"]["limit"] == 3

    deleted = client.delete(f"/api/v1/admin/plugins/{plugin_id}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True}
