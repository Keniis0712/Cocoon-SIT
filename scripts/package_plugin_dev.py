from __future__ import annotations

import argparse

from package_plugins import (
    PACKAGES_ROOT,
    PLUGINS_ROOT,
    REPO_ROOT,
    _iter_plugin_dirs,
    _package_plugin,
)


def _resolve_plugin_dir(raw_value: str) -> Path:
    normalized = raw_value.strip().replace("\\", "/").strip("/")
    if not normalized:
        raise SystemExit("Plugin name or path is required.")

    direct_path = (PLUGINS_ROOT / normalized).resolve()
    if direct_path.is_dir() and (direct_path / "plugin.json").is_file():
        return direct_path

    matches = [path for path in _iter_plugin_dirs() if path.name == normalized]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        options = ", ".join(path.relative_to(PLUGINS_ROOT).as_posix() for path in matches)
        raise SystemExit(f"Plugin name is ambiguous. Use one of: {options}")

    raise SystemExit(f"Plugin not found: {raw_value}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package one plugin into a force-overwritten .dev.zip archive."
    )
    parser.add_argument("plugin", help="Plugin folder name or path under plugins/, e.g. qweather_daily_alert or external/qweather_daily_alert")
    args = parser.parse_args()

    plugin_dir = _resolve_plugin_dir(args.plugin)
    plugin_type = plugin_dir.parent.name
    archive_name = f"{plugin_dir.name}-{plugin_type}.dev.zip"
    archive_path = PACKAGES_ROOT / archive_name
    _package_plugin(plugin_dir, archive_path, overwrite=True)
    print(f"packed   {archive_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
