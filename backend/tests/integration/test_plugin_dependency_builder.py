from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
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


def test_dependency_builder_archives_packages_with_package_level_dedup(tmp_path):
    builder = DependencyBuilder()
    extracted_root = tmp_path / "content"
    version_one_root = tmp_path / "versions" / "1.0.0"
    version_two_root = tmp_path / "versions" / "2.0.0"
    shared_lib_root = tmp_path / "shared_libs"
    extracted_root.mkdir(parents=True, exist_ok=True)

    def write_fake_distribution(
        staging_root: Path, *, name: str, version: str, package_dir: str, module_name: str
    ):
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
            "size_bytes": payload_one["packages"][0]["size_bytes"],
        }
    ]
    assert payload_one["packages"][0]["size_bytes"] > 0
    assert (package_one_root / "samplepkg" / "__init__.py").exists()
    assert (
        json.loads((package_one_root / ".package-info.json").read_text(encoding="utf-8"))[
            "size_bytes"
        ]
        > 0
    )
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
    monkeypatch.setattr(
        "app.services.plugins.dependency_builder.shutil.which",
        lambda name: "/usr/local/bin/uv" if name == "uv" else None,
    )

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
