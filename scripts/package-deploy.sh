#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

OUTPUT_DIR="${1:-dist}"
ARCHIVE_NAME="${2:-}"

if [[ -z "${ARCHIVE_NAME}" ]]; then
  ARCHIVE_NAME="cocoon-sit-deploy-$(date +%Y%m%d-%H%M%S).zip"
fi
if [[ "${ARCHIVE_NAME}" != *.zip ]]; then
  ARCHIVE_NAME="${ARCHIVE_NAME}.zip"
fi

mkdir -p "${OUTPUT_DIR}"
ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"
rm -f "${ARCHIVE_PATH}"

python3 - "${REPO_ROOT}" "${ARCHIVE_PATH}" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

repo_root = Path(sys.argv[1]).resolve()
archive_path = Path(sys.argv[2]).resolve()

required_paths = [
    "deploy/docker-compose.yml",
    "deploy/backend.Dockerfile",
    "deploy/.env.example",
    "deploy/init-db.sql",
    "backend",
    "frontend",
    "packages",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
]

include_roots = [
    "deploy",
    "backend",
    "frontend",
    "packages",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
]

exclude_prefixes = [
    ".git/",
    "node_modules/",
    ".pnpm-store/",
    ".uv-cache/",
    ".tmp_pytest/",
    ".artifacts/",
    "dist/",
    "backend/.venv/",
    "backend/.pytest_cache/",
    "backend/.mypy_cache/",
    "backend/.ruff_cache/",
    "backend/.artifacts/",
    "frontend/dist/",
    "frontend/node_modules/",
    "packages/ts-sdk/node_modules/",
]


def normalize(value: Path | str) -> str:
    return str(value).replace("\\", "/").lstrip("./")


def is_excluded(relative_path: str) -> bool:
    normalized = normalize(relative_path)
    return any(normalized.startswith(prefix) for prefix in exclude_prefixes)


for required in required_paths:
    if not (repo_root / required).exists():
        raise SystemExit(f"Missing required deployment path: {required}")

files: set[str] = set()
for entry in include_roots:
    full_path = repo_root / entry
    if full_path.is_dir():
        for path in full_path.rglob("*"):
            if path.is_file():
                relative = normalize(path.relative_to(repo_root))
                if not is_excluded(relative):
                    files.add(relative)
    elif full_path.is_file():
        relative = normalize(entry)
        if not is_excluded(relative):
            files.add(relative)

if not files:
    raise SystemExit("No deployment files matched the include list.")

archive_path.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as bundle:
    for relative in sorted(files):
        bundle.write(repo_root / relative, relative)

size_bytes = archive_path.stat().st_size
size_mb = round(size_bytes / (1024 * 1024), 2)
print(f"Created deploy bundle: {archive_path}")
print(f"Files packed: {len(files)}")
print(f"Archive size: {size_mb} MB")
PY
