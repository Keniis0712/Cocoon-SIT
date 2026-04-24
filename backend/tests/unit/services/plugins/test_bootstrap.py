from __future__ import annotations

import json
from pathlib import Path
import sys

from app.services.plugins.bootstrap import bootstrap_module


def _write_manifest(path: Path, *, paths: list[str]) -> Path:
    path.write_text(json.dumps({"paths": paths}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _clear_modules(prefixes: tuple[str, ...]) -> None:
    for key in list(sys.modules):
        if key.startswith(prefixes):
            sys.modules.pop(key, None)


def test_bootstrap_module_imports_split_package_tree(tmp_path):
    original_sys_path = list(sys.path)
    try:
        dist_one = tmp_path / "dist_one"
        dist_two = tmp_path / "dist_two"
        plugin_root = tmp_path / "plugin"
        manifest_path = tmp_path / "dependency_manifest.json"

        (dist_one / "mergedpkg" / "adapters").mkdir(parents=True, exist_ok=True)
        (dist_two / "mergedpkg" / "adapters" / "child").mkdir(parents=True, exist_ok=True)
        plugin_root.mkdir(parents=True, exist_ok=True)

        (dist_one / "mergedpkg" / "__init__.py").write_text("ROOT = 'base'\n", encoding="utf-8")
        (dist_one / "mergedpkg" / "adapters" / "__init__.py").write_text("BASE = 'adapter'\n", encoding="utf-8")
        (dist_two / "mergedpkg" / "adapters" / "child" / "__init__.py").write_text("VALUE = 'child'\n", encoding="utf-8")
        (plugin_root / "entry_plugin.py").write_text(
            "from mergedpkg.adapters.child import VALUE\nRESULT = VALUE\n",
            encoding="utf-8",
        )

        _write_manifest(manifest_path, paths=[str(dist_one), str(dist_two), str(plugin_root)])
        module = bootstrap_module(manifest_path, "entry_plugin")

        assert module.RESULT == "child"
    finally:
        sys.path[:] = original_sys_path
        _clear_modules(("entry_plugin", "mergedpkg"))


def test_bootstrap_module_refreshes_preloaded_package_paths(tmp_path):
    original_sys_path = list(sys.path)
    try:
        dist_one = tmp_path / "dist_one"
        dist_two = tmp_path / "dist_two"
        plugin_root = tmp_path / "plugin"
        manifest_path = tmp_path / "dependency_manifest.json"

        (dist_one / "stickymerged" / "adapters").mkdir(parents=True, exist_ok=True)
        (dist_two / "stickymerged" / "adapters" / "child").mkdir(parents=True, exist_ok=True)
        plugin_root.mkdir(parents=True, exist_ok=True)

        (dist_one / "stickymerged" / "__init__.py").write_text("ROOT = 'base'\n", encoding="utf-8")
        (dist_one / "stickymerged" / "adapters" / "__init__.py").write_text("BASE = 'adapter'\n", encoding="utf-8")
        (dist_two / "stickymerged" / "adapters" / "child" / "__init__.py").write_text("VALUE = 'child'\n", encoding="utf-8")
        (plugin_root / "entry_preloaded.py").write_text(
            "from stickymerged.adapters.child import VALUE\nRESULT = VALUE\n",
            encoding="utf-8",
        )

        sys.path.insert(0, str(dist_one))
        __import__("stickymerged.adapters")

        _write_manifest(manifest_path, paths=[str(dist_one), str(dist_two), str(plugin_root)])
        module = bootstrap_module(manifest_path, "entry_preloaded")

        assert module.RESULT == "child"
    finally:
        sys.path[:] = original_sys_path
        _clear_modules(("entry_preloaded", "stickymerged"))


def test_bootstrap_module_promotes_current_manifest_paths_for_shared_entry_name(tmp_path):
    original_sys_path = list(sys.path)
    try:
        plugin_one = tmp_path / "plugin_one"
        plugin_two = tmp_path / "plugin_two"
        manifest_one = tmp_path / "dependency_manifest_one.json"
        manifest_two = tmp_path / "dependency_manifest_two.json"

        plugin_one.mkdir(parents=True, exist_ok=True)
        plugin_two.mkdir(parents=True, exist_ok=True)
        (plugin_one / "main.py").write_text(
            "PLUGIN = 'one'\n"
            "def daily_forecast(ctx):\n"
            "    return {'summary': PLUGIN}\n",
            encoding="utf-8",
        )
        (plugin_two / "main.py").write_text("PLUGIN = 'two'\n", encoding="utf-8")

        _write_manifest(manifest_one, paths=[str(plugin_one)])
        _write_manifest(manifest_two, paths=[str(plugin_two)])

        module_two = bootstrap_module(manifest_two, "main")
        module_one = bootstrap_module(manifest_one, "main")

        assert module_two.PLUGIN == "two"
        assert module_one.PLUGIN == "one"
        assert callable(module_one.daily_forecast)
    finally:
        sys.path[:] = original_sys_path
        _clear_modules(("main",))
