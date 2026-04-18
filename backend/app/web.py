from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def _resolve_frontend_file(dist_dir: Path, requested_path: str) -> Path | None:
    if not requested_path:
        return None

    candidate = (dist_dir / requested_path).resolve()
    try:
        candidate.relative_to(dist_dir.resolve())
    except ValueError:
        return None

    if candidate.is_file():
        return candidate
    return None


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    if not dist_dir.exists():
        return

    index_file = dist_dir / "index.html"
    if not index_file.exists():
        return

    @app.get("/", include_in_schema=False)
    async def frontend_index():
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_route(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        frontend_file = _resolve_frontend_file(dist_dir, full_path)
        if frontend_file:
            return FileResponse(frontend_file)

        return FileResponse(index_file)
