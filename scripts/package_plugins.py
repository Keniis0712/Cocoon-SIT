from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = REPO_ROOT / "plugins"
PACKAGES_ROOT = PLUGINS_ROOT / "packages"
PLUGIN_TYPE_DIRS = ("external", "im")
IGNORED_DIR_NAMES = {"__pycache__", ".git", ".DS_Store"}
IGNORED_FILE_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _iter_plugin_dirs() -> list[Path]:
    plugin_dirs: list[Path] = []
    for plugin_type in PLUGIN_TYPE_DIRS:
        type_root = PLUGINS_ROOT / plugin_type
        if not type_root.is_dir():
            continue
        for child in sorted(type_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name in IGNORED_DIR_NAMES:
                continue
            if (child / "plugin.json").is_file():
                plugin_dirs.append(child)
    return plugin_dirs


def _load_manifest(plugin_dir: Path) -> dict[str, object]:
    manifest_path = plugin_dir / "plugin.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing plugin manifest: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid plugin manifest JSON: {manifest_path} ({exc})") from exc


def _iter_plugin_files(plugin_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(plugin_dir.rglob("*")):
        if path.is_dir():
            if path.name in IGNORED_DIR_NAMES:
                continue
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if path.suffix in IGNORED_FILE_SUFFIXES:
            continue
        files.append(path)
    return files


def _package_plugin(plugin_dir: Path, archive_path: Path, *, overwrite: bool) -> bool:
    if archive_path.exists() and not overwrite:
        return False
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as bundle:
        for file_path in _iter_plugin_files(plugin_dir):
            bundle.write(file_path, file_path.relative_to(plugin_dir).as_posix())
    return True


def _archive_name(plugin_dir: Path, manifest: dict[str, object]) -> str:
    version = str(manifest.get("version") or "").strip()
    if not version:
        raise SystemExit(f"Plugin {plugin_dir} is missing a version in plugin.json")
    plugin_type = plugin_dir.parent.name
    return f"{plugin_dir.name}-{plugin_type}-{version}.zip"


def package_all_plugins() -> int:
    created = 0
    skipped = 0
    for plugin_dir in _iter_plugin_dirs():
        manifest = _load_manifest(plugin_dir)
        archive_path = PACKAGES_ROOT / _archive_name(plugin_dir, manifest)
        if _package_plugin(plugin_dir, archive_path, overwrite=False):
            created += 1
            print(f"packed   {archive_path.relative_to(REPO_ROOT).as_posix()}")
        else:
            skipped += 1
            print(f"skipped  {archive_path.relative_to(REPO_ROOT).as_posix()} (version unchanged)")
    print(f"done: created={created}, skipped={skipped}, output_dir={PACKAGES_ROOT.relative_to(REPO_ROOT).as_posix()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package all local plugins into versioned zip archives."
    )
    parser.parse_args()
    return package_all_plugins()


if __name__ == "__main__":
    raise SystemExit(main())
