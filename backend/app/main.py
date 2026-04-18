from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.container import AppContainer
from app.core.logging import configure_logging
from app.web import mount_frontend


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    resolved_settings = settings or get_settings()
    container = AppContainer(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container.connection_manager.bind_loop(asyncio.get_running_loop())
        container.initialize()
        app.state.container = container
        try:
            yield
        finally:
            container.shutdown()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description=(
            "Cocoon-SIT backend implementing REST 202 + WebSocket realtime contracts, "
            "versioned prompt templates, audit artifacts, and worker-driven runtime execution."
        ),
        lifespan=lifespan,
    )
    app.state.container = container
    if resolved_settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    mount_frontend(app, Path(resolved_settings.frontend_dist_path))

    return app


app = create_app()


def dump_openapi(settings: Settings | None = None) -> Path:
    local_app = create_app(settings)
    output_path = Path(settings.dump_openapi_path if settings else get_settings().dump_openapi_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(local_app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-openapi", action="store_true")
    args = parser.parse_args()
    if args.dump_openapi:
        path = dump_openapi()
        print(path)
