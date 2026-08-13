"""FastAPI application entrypoint.

Serves ``/api/*`` and (in production) the built React SPA at ``/``. A
catch-all route falls back to ``index.html`` so client-side deep links work.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Stochastic Inventory Reorder / Safety Stock Explorer",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins) or ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    static_dir = settings.static_dir
    if static_dir is not None and Path(static_dir).exists():
        assets = Path(static_dir) / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str, request: Request) -> FileResponse:
            index = Path(static_dir) / "index.html"
            if not index.exists():
                raise HTTPException(status_code=404, detail="frontend not built")
            candidate = Path(static_dir) / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
