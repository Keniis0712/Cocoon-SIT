from pathlib import Path

import pytest

from app.services.plugins.manifest import PluginPackageManifest


def test_plugin_package_manifest_loads_valid_external_manifest(tmp_path: Path):
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text(
        """
        {
          "name": "demo",
          "version": "1.0.0",
          "display_name": "Demo",
          "plugin_type": "external",
          "entry_module": "demo.main",
          "events": [
            {
              "name": "wake",
              "mode": "short_lived",
              "function_name": "handle",
              "title": "Wake",
              "description": "Wake event"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    manifest = PluginPackageManifest.load(manifest_path)

    assert manifest.name == "demo"
    assert manifest.events[0].name == "wake"


def test_plugin_package_manifest_rejects_invalid_json(tmp_path: Path):
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text("{ invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid plugin.json"):
        PluginPackageManifest.load(manifest_path)


def test_plugin_package_manifest_rejects_invalid_payload(tmp_path: Path):
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text('{"name": "demo"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid plugin manifest"):
        PluginPackageManifest.load(manifest_path)


def test_plugin_package_manifest_requires_events_for_external_plugins(tmp_path: Path):
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text(
        """
        {
          "name": "demo",
          "version": "1.0.0",
          "display_name": "Demo",
          "plugin_type": "external",
          "entry_module": "demo.main"
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="External plugins must define at least one event"):
        PluginPackageManifest.load(manifest_path)


def test_plugin_package_manifest_requires_service_function_for_im_plugins(tmp_path: Path):
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text(
        """
        {
          "name": "demo",
          "version": "1.0.0",
          "display_name": "Demo",
          "plugin_type": "im",
          "entry_module": "demo.main"
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="IM plugins must define service_function"):
        PluginPackageManifest.load(manifest_path)
