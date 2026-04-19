from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def load_dependency_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def bootstrap_module(manifest_path: str | Path, entry_module: str):
    manifest = load_dependency_manifest(manifest_path)
    for path in reversed(manifest.get("paths") or []):
        if path not in sys.path:
            sys.path.insert(0, path)
    for key in list(sys.modules):
        if key == entry_module or key.startswith(f"{entry_module}."):
            sys.modules.pop(key, None)
    return importlib.import_module(entry_module)
