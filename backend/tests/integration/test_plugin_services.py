from __future__ import annotations

import io
import json
from pathlib import Path
import time
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.models import ChatGroupRoom, Cocoon, PluginDefinition, PluginDispatchRecord, PluginRunState, SessionState, User, WakeupTask
from app.services.plugins.dependency_builder import DependencyBuilder

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


def test_install_external_plugin_and_short_lived_wakeup(client, auth_headers, default_cocoon_id):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "sample-external",
            "version": "1.0.0",
            "display_name": "Sample External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "sample_short",
                    "mode": "short_lived",
                    "function_name": "sample_short",
                    "title": "Sample Short",
                    "description": "Short-lived external event",
                    "config_schema": {"type": "object"},
                    "default_config": {},
                }
            ],
        },
        sources={
            "main.py": f"""
def sample_short(ctx):
    return {{
        "summary": "short-lived wakeup",
        "payload": {{"source": "test"}}
    }}
""",
        },
    )
    assert response.status_code == 200, response.text
    plugin_id = response.json()["id"]
    _bind_plugin_target(client, auth_headers, plugin_id, target_type="cocoon", target_id=default_cocoon_id)

    enable_response = client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers)
    assert enable_response.status_code == 200, enable_response.text

    container = client.app.state.container
    container.plugin_runtime_manager.run_short_lived_event_now(plugin_id, "sample_short")
    time.sleep(0.5)
    container.plugin_runtime_manager.run_once()

    with container.session_factory() as session:
        dispatch = session.scalar(select(PluginDispatchRecord).where(PluginDispatchRecord.plugin_id == plugin_id))
        wakeup = session.scalar(select(WakeupTask).where(WakeupTask.reason == "short-lived wakeup"))
        assert dispatch is not None
        assert wakeup is not None
        assert wakeup.cocoon_id == default_cocoon_id


def test_external_plugin_can_target_chat_group(client, auth_headers):
    container = client.app.state.container
    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        default_cocoon = session.scalar(select(Cocoon).limit(1))
        assert default_cocoon is not None
        room = ChatGroupRoom(
            name="Plugin Group",
            owner_user_id=admin.id,
            character_id=default_cocoon.character_id,
            selected_model_id=default_cocoon.selected_model_id,
        )
        session.add(room)
        session.flush()
        session.add(SessionState(chat_group_id=room.id, persona_json={}, active_tags_json=[]))
        session.commit()
        room_id = room.id

    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "group-external",
            "version": "1.0.0",
            "display_name": "Group External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "group_short",
                    "mode": "short_lived",
                    "function_name": "group_short",
                    "title": "Group Short",
                    "description": "Chat-group wakeup",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={
            "main.py": f"""
def group_short(ctx):
    return {{
        "summary": "group wakeup",
        "payload": {{"kind": "group"}}
    }}
""",
        },
    )
    assert response.status_code == 200, response.text
    plugin_id = response.json()["id"]
    _bind_plugin_target(client, auth_headers, plugin_id, target_type="chat_group", target_id=room_id)
    assert client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers).status_code == 200

    container.plugin_runtime_manager.run_short_lived_event_now(plugin_id, "group_short")
    time.sleep(0.5)
    container.plugin_runtime_manager.run_once()

    with container.session_factory() as session:
        wakeup = session.scalar(select(WakeupTask).where(WakeupTask.chat_group_id == room_id))
        assert wakeup is not None
        assert wakeup.reason == "group wakeup"


def test_daemon_external_and_im_plugins_start_and_report_state(client, auth_headers, default_cocoon_id):
    daemon_response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "daemon-external",
            "version": "1.0.0",
            "display_name": "Daemon External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "daemon_one",
                    "mode": "daemon",
                    "function_name": "daemon_one",
                    "title": "Daemon One",
                    "description": "First daemon",
                    "config_schema": {"type": "object"},
                },
                {
                    "name": "daemon_two",
                    "mode": "daemon",
                    "function_name": "daemon_two",
                    "title": "Daemon Two",
                    "description": "Second daemon",
                    "config_schema": {"type": "object"},
                },
            ],
        },
        sources={
            "main.py": f"""
import asyncio

async def daemon_one(ctx):
    ctx.emit_event({{
        "summary": "daemon wakeup one",
        "payload": {{"event": "one"}}
    }})
    while True:
        await asyncio.sleep(0.2)

async def daemon_two(ctx):
    ctx.heartbeat()
    while True:
        await asyncio.sleep(0.2)
""",
        },
    )
    assert daemon_response.status_code == 200, daemon_response.text
    daemon_id = daemon_response.json()["id"]
    _bind_plugin_target(client, auth_headers, daemon_id, target_type="cocoon", target_id=default_cocoon_id)
    assert client.post(f"/api/v1/admin/plugins/{daemon_id}/enable", headers=auth_headers).status_code == 200

    im_response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "sample-im",
            "version": "1.0.0",
            "display_name": "Sample IM",
            "plugin_type": "im",
            "entry_module": "main",
            "service_function": "run",
        },
        sources={
            "main.py": """
import asyncio

async def run(ctx):
    ctx.heartbeat()
    while True:
        await asyncio.sleep(0.2)
""",
        },
    )
    assert im_response.status_code == 200, im_response.text
    im_id = im_response.json()["id"]
    assert client.post(f"/api/v1/admin/plugins/{im_id}/enable", headers=auth_headers).status_code == 200

    container = client.app.state.container
    deadline = time.time() + 5
    found_dispatch = False
    while time.time() < deadline:
        time.sleep(0.3)
        container.plugin_runtime_manager.run_once()
        with container.session_factory() as session:
            dispatch = session.scalar(
                select(PluginDispatchRecord).where(
                    PluginDispatchRecord.plugin_id == daemon_id,
                    PluginDispatchRecord.event_name == "daemon_one",
                )
            )
            daemon_state = session.scalar(select(PluginRunState).where(PluginRunState.plugin_id == daemon_id))
            im_state = session.scalar(select(PluginRunState).where(PluginRunState.plugin_id == im_id))
            if (
                dispatch
                and daemon_state
                and daemon_state.status == "running"
                and daemon_state.pid
                and im_state
                and im_state.status == "running"
                and im_state.pid
            ):
                found_dispatch = True
                break
    assert found_dispatch

    disable_response = client.post(f"/api/v1/admin/plugins/{daemon_id}/disable", headers=auth_headers)
    assert disable_response.status_code == 200, disable_response.text


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
        plugin = session.scalar(select(PluginDefinition).where(PluginDefinition.name == "missing-function"))
        assert plugin is None


def test_dependency_builder_archives_packages_with_package_level_dedup(tmp_path):
    builder = DependencyBuilder()
    extracted_root = tmp_path / "content"
    version_one_root = tmp_path / "versions" / "1.0.0"
    version_two_root = tmp_path / "versions" / "2.0.0"
    shared_lib_root = tmp_path / "shared_libs"
    extracted_root.mkdir(parents=True, exist_ok=True)

    def write_fake_distribution(staging_root: Path, *, name: str, version: str, package_dir: str, module_name: str):
        package_root = staging_root / package_dir
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(f"VALUE = '{version}'\n", encoding="utf-8")
        dist_info = staging_root / f"{name.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True, exist_ok=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            f"{package_dir}/__init__.py,,\n{dist_info.name}/METADATA,,\n{dist_info.name}/RECORD,,\n",
            encoding="utf-8",
        )
        (staging_root / f"{module_name}.py").write_text("FLAG = True\n", encoding="utf-8")

    def fake_install(requirements_path: Path, staging_root: Path) -> None:
        marker = requirements_path.read_text(encoding="utf-8").strip()
        staging_root.mkdir(parents=True, exist_ok=True)
        if marker == "samplepkg==1.0.0":
            write_fake_distribution(
                staging_root,
                name="samplepkg",
                version="1.0.0",
                package_dir="samplepkg",
                module_name="samplepkg_helpers",
            )
        elif marker == "samplepkg==2.0.0":
            write_fake_distribution(
                staging_root,
                name="samplepkg",
                version="2.0.0",
                package_dir="samplepkg",
                module_name="samplepkg_helpers",
            )
        else:
            raise AssertionError(f"Unexpected requirement marker: {marker}")

    builder._install_to_staging = fake_install  # type: ignore[method-assign]

    (extracted_root / "requirements.txt").write_text("samplepkg==1.0.0\n", encoding="utf-8")
    version_one_root.mkdir(parents=True, exist_ok=True)
    manifest_one = builder.build(
        extracted_root=extracted_root,
        version_root=version_one_root,
        shared_lib_root=shared_lib_root,
    )
    payload_one = json.loads(manifest_one.read_text(encoding="utf-8"))
    package_one_root = shared_lib_root / "samplepkg" / "1.0.0"
    assert payload_one["paths"][0] == str(package_one_root)
    assert payload_one["paths"][-1] == str(extracted_root)
    assert payload_one["packages"] == [
        {
            "name": "samplepkg",
            "normalized_name": "samplepkg",
            "version": "1.0.0",
            "path": str(package_one_root),
        }
    ]
    assert (package_one_root / "samplepkg" / "__init__.py").exists()
    package_one_mtime = (package_one_root / "samplepkg" / "__init__.py").stat().st_mtime_ns

    version_two_root.mkdir(parents=True, exist_ok=True)
    manifest_repeat = builder.build(
        extracted_root=extracted_root,
        version_root=version_two_root,
        shared_lib_root=shared_lib_root,
    )
    payload_repeat = json.loads(manifest_repeat.read_text(encoding="utf-8"))
    assert payload_repeat["paths"][0] == str(package_one_root)
    assert (package_one_root / "samplepkg" / "__init__.py").stat().st_mtime_ns == package_one_mtime

    (extracted_root / "requirements.txt").write_text("samplepkg==2.0.0\n", encoding="utf-8")
    version_three_root = tmp_path / "versions" / "3.0.0"
    version_three_root.mkdir(parents=True, exist_ok=True)
    manifest_two = builder.build(
        extracted_root=extracted_root,
        version_root=version_three_root,
        shared_lib_root=shared_lib_root,
    )
    payload_two = json.loads(manifest_two.read_text(encoding="utf-8"))
    package_two_root = shared_lib_root / "samplepkg" / "2.0.0"
    assert payload_two["paths"][0] == str(package_two_root)
    assert (package_two_root / "samplepkg" / "__init__.py").exists()


def test_dependency_builder_uses_uv_when_runtime_python_has_no_pip(tmp_path, monkeypatch):
    builder = DependencyBuilder()
    requirements_path = tmp_path / "requirements.txt"
    staging_root = tmp_path / "staging"
    requirements_path.write_text("requests==2.31.0\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:3] == [command[0], "-m", "pip"] and command[-1] == "--version":
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.plugins.dependency_builder.subprocess.run", fake_run)
    monkeypatch.setattr("app.services.plugins.dependency_builder.shutil.which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)

    builder._install_to_staging(requirements_path, staging_root)

    assert calls[-1][:4] == ["/usr/local/bin/uv", "pip", "install", "--python"]
    assert "--target" in calls[-1]
    assert str(requirements_path) in calls[-1]


def test_dependency_builder_prunes_only_unreferenced_packages(tmp_path):
    builder = DependencyBuilder()
    shared_lib_root = tmp_path / "shared_libs"
    kept_root = shared_lib_root / "samplepkg" / "1.0.0"
    removed_root = shared_lib_root / "otherpkg" / "2.0.0"
    (kept_root / "samplepkg").mkdir(parents=True, exist_ok=True)
    (removed_root / "otherpkg").mkdir(parents=True, exist_ok=True)
    kept_manifest = tmp_path / "kept_manifest.json"
    kept_manifest.write_text(
        json.dumps(
            {
                "paths": [str(kept_root), str(tmp_path / "plugin")],
                "packages": [
                    {
                        "name": "samplepkg",
                        "normalized_name": "samplepkg",
                        "version": "1.0.0",
                        "path": str(kept_root),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    builder.prune_unused_packages(shared_lib_root=shared_lib_root, manifest_paths=[kept_manifest])

    assert kept_root.exists()
    assert not removed_root.exists()
    assert not (shared_lib_root / "otherpkg").exists()


def test_delete_plugin_prunes_shared_packages_only_after_last_reference(client, auth_headers):
    container = client.app.state.container
    builder = container.dependency_builder

    def write_fake_distribution(staging_root: Path, *, name: str, version: str, package_dir: str):
        package_root = staging_root / package_dir
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(f"VALUE = '{version}'\n", encoding="utf-8")
        dist_info = staging_root / f"{name.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True, exist_ok=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            f"{package_dir}/__init__.py,,\n{dist_info.name}/METADATA,,\n{dist_info.name}/RECORD,,\n",
            encoding="utf-8",
        )

    def fake_install(requirements_path: Path, staging_root: Path) -> None:
        marker = requirements_path.read_text(encoding="utf-8").strip()
        staging_root.mkdir(parents=True, exist_ok=True)
        if marker != "sharedpkg==1.0.0":
            raise AssertionError(f"Unexpected requirement marker: {marker}")
        write_fake_distribution(
            staging_root,
            name="sharedpkg",
            version="1.0.0",
            package_dir="sharedpkg",
        )

    original_install = builder._install_to_staging
    builder._install_to_staging = fake_install  # type: ignore[method-assign]
    try:
        manifest = {
            "version": "1.0.0",
            "display_name": "Shared Plugin",
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
        }
        sources = {
            "main.py": "def tick(ctx):\n    return None\n",
            "requirements.txt": "sharedpkg==1.0.0\n",
        }
        first = _install_response(
            client,
            auth_headers,
            manifest={**manifest, "name": "shared-one"},
            sources=sources,
        )
        second = _install_response(
            client,
            auth_headers,
            manifest={**manifest, "name": "shared-two"},
            sources=sources,
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text

        package_root = container.settings.plugin_root / "shared_libs" / "sharedpkg" / "1.0.0"
        assert package_root.exists()

        first_id = first.json()["id"]
        second_id = second.json()["id"]
        delete_first = client.delete(f"/api/v1/admin/plugins/{first_id}", headers=auth_headers)
        assert delete_first.status_code == 200, delete_first.text
        assert package_root.exists()

        delete_second = client.delete(f"/api/v1/admin/plugins/{second_id}", headers=auth_headers)
        assert delete_second.status_code == 200, delete_second.text
        assert not package_root.exists()
    finally:
        builder._install_to_staging = original_install  # type: ignore[method-assign]


def test_list_shared_packages_reports_reference_counts(client, auth_headers):
    container = client.app.state.container
    builder = container.dependency_builder

    def write_fake_distribution(staging_root: Path, *, name: str, version: str, package_dir: str, payload: str):
        package_root = staging_root / package_dir
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(payload, encoding="utf-8")
        dist_info = staging_root / f"{name.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True, exist_ok=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            f"{package_dir}/__init__.py,,\n{dist_info.name}/METADATA,,\n{dist_info.name}/RECORD,,\n",
            encoding="utf-8",
        )

    def fake_install(requirements_path: Path, staging_root: Path) -> None:
        marker = requirements_path.read_text(encoding="utf-8").strip()
        staging_root.mkdir(parents=True, exist_ok=True)
        if marker == "sharedpkg==1.0.0":
            write_fake_distribution(
                staging_root,
                name="sharedpkg",
                version="1.0.0",
                package_dir="sharedpkg",
                payload="VALUE = 'shared'\n",
            )
            return
        if marker == "uniquepkg==2.0.0":
            write_fake_distribution(
                staging_root,
                name="uniquepkg",
                version="2.0.0",
                package_dir="uniquepkg",
                payload="VALUE = 'unique'\n",
            )
            return
        raise AssertionError(f"Unexpected requirement marker: {marker}")

    original_install = builder._install_to_staging
    builder._install_to_staging = fake_install  # type: ignore[method-assign]
    try:
        base_manifest = {
            "version": "1.0.0",
            "display_name": "Inventory Plugin",
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
        }
        shared_sources = {
            "main.py": "def tick(ctx):\n    return None\n",
            "requirements.txt": "sharedpkg==1.0.0\n",
        }
        unique_sources = {
            "main.py": "def tick(ctx):\n    return None\n",
            "requirements.txt": "uniquepkg==2.0.0\n",
        }

        first = _install_response(client, auth_headers, manifest={**base_manifest, "name": "inventory-one"}, sources=shared_sources)
        second = _install_response(client, auth_headers, manifest={**base_manifest, "name": "inventory-two"}, sources=shared_sources)
        third = _install_response(client, auth_headers, manifest={**base_manifest, "name": "inventory-three"}, sources=unique_sources)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert third.status_code == 200, third.text

        response = client.get("/api/v1/admin/plugins/shared-libs", headers=auth_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        shared_item = next(item for item in payload if item["normalized_name"] == "sharedpkg")
        unique_item = next(item for item in payload if item["normalized_name"] == "uniquepkg")
        assert shared_item["reference_count"] == 2
        assert unique_item["reference_count"] == 1
        assert shared_item["size_bytes"] > 0
        assert unique_item["size_bytes"] > 0
    finally:
        builder._install_to_staging = original_install  # type: ignore[method-assign]
