from __future__ import annotations

from collections.abc import Iterable
import importlib
import importlib.abc
import importlib.machinery
import json
import sys
from pathlib import Path


def load_dependency_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def _package_tree_candidates(fullname: str, roots: Iterable[str]) -> list[str]:
    relative_parts = fullname.split(".")
    seen: set[str] = set()
    candidates: list[str] = []
    for root in roots:
        if not root:
            continue
        candidate = Path(root).joinpath(*relative_parts)
        if not candidate.is_dir():
            continue
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        candidates.append(candidate_str)
    return candidates


def _merged_package_locations(fullname: str, current_locations: Iterable[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for location in current_locations:
        location_str = str(location)
        if location_str in seen:
            continue
        seen.add(location_str)
        merged.append(location_str)
    for candidate in _package_tree_candidates(fullname, sys.path):
        if candidate in seen:
            continue
        seen.add(candidate)
        merged.append(candidate)
    return merged


def _refresh_loaded_package_paths() -> None:
    for module_name, module in list(sys.modules.items()):
        if not module_name or module is None:
            continue
        package_path = getattr(module, "__path__", None)
        if package_path is None:
            continue
        merged_locations = _merged_package_locations(module_name, package_path)
        module.__path__ = merged_locations
        spec = getattr(module, "__spec__", None)
        if spec is not None and spec.submodule_search_locations is not None:
            spec.submodule_search_locations = list(merged_locations)


class _PluginPackageTreeFinder(importlib.abc.MetaPathFinder):
    """Merges split package trees contributed by multiple plugin dependency roots."""

    def find_spec(self, fullname: str, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.submodule_search_locations is None:
            return spec
        spec.submodule_search_locations = _merged_package_locations(fullname, spec.submodule_search_locations)
        return spec


_PACKAGE_TREE_FINDER = _PluginPackageTreeFinder()


def _ensure_package_tree_finder() -> None:
    if any(isinstance(finder, _PluginPackageTreeFinder) for finder in sys.meta_path):
        return
    for index, finder in enumerate(sys.meta_path):
        if finder is importlib.machinery.PathFinder:
            sys.meta_path.insert(index, _PACKAGE_TREE_FINDER)
            return
    sys.meta_path.append(_PACKAGE_TREE_FINDER)


def _promote_manifest_paths(paths: Iterable[str]) -> None:
    normalized_paths = [path for path in paths if path]
    for path in normalized_paths:
        while path in sys.path:
            sys.path.remove(path)
    for path in reversed(normalized_paths):
        sys.path.insert(0, path)


def bootstrap_module(manifest_path: str | Path, entry_module: str):
    manifest = load_dependency_manifest(manifest_path)
    _promote_manifest_paths(manifest.get("paths") or [])
    importlib.invalidate_caches()
    _ensure_package_tree_finder()
    _refresh_loaded_package_paths()
    for key in list(sys.modules):
        if key == entry_module or key.startswith(f"{entry_module}."):
            sys.modules.pop(key, None)
    return importlib.import_module(entry_module)
