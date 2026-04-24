from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

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

    def write_fake_distribution(
        staging_root: Path, *, name: str, version: str, package_dir: str, payload: str
    ):
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

        first = _install_response(
            client,
            auth_headers,
            manifest={**base_manifest, "name": "inventory-one"},
            sources=shared_sources,
        )
        second = _install_response(
            client,
            auth_headers,
            manifest={**base_manifest, "name": "inventory-two"},
            sources=shared_sources,
        )
        third = _install_response(
            client,
            auth_headers,
            manifest={**base_manifest, "name": "inventory-three"},
            sources=unique_sources,
        )
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


def test_dependency_builder_collect_inventory_tolerates_disappearing_files(tmp_path, monkeypatch):
    builder = DependencyBuilder()
    shared_lib_root = tmp_path / "shared_libs"
    package_root = shared_lib_root / "volatilepkg" / "1.0.0"
    module_file = package_root / "volatilepkg" / "__init__.py"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    module_file.write_text("VALUE = 'ok'\n", encoding="utf-8")

    original_stat = Path.stat

    def flaky_stat(self: Path, *args, **kwargs):
        if self == module_file:
            raise FileNotFoundError(str(module_file))
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    inventory = builder.collect_inventory(shared_lib_root=shared_lib_root, manifest_paths=[])

    assert len(inventory) == 1
    assert inventory[0].normalized_name == "volatilepkg"
    assert inventory[0].size_bytes >= 0
    assert (package_root / ".package-info.json").exists()
