"""SEOMATE API — FastAPI application root.

Read-only HTTP API serving the Next.js inspection UI. The auditor is the
only writer to Postgres; this app exposes captures over typed JSON.

The taxonomy catalog is loaded once at app startup (lifespan event) and
cached on ``app.state.catalog``. Routes access it via the ``get_catalog``
dependency.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from seomate.storage.db import get_async_engine
from seomate.taxonomy import Catalog
from seomate_api import __version__
from seomate_api.auth import require_basic_auth
from seomate_api.routes import audits as audits_routes
from seomate_api.routes import competitive as competitive_routes
from seomate_api.routes import strategy as strategy_routes
from seomate_api.routes import taxonomy as taxonomy_routes
from seomate_api.settings import get_api_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the taxonomy catalog at startup; dispose the DB engine on shutdown."""
    app.state.catalog = Catalog.from_file()
    yield
    await get_async_engine().dispose()


def create_app() -> FastAPI:
    settings = get_api_settings()
    app = FastAPI(
        title="SEOMATE API",
        version=__version__,
        description="Read-only API serving the SEOMATE inspection UI.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    # Routers carry the basic-auth dependency. ``/api/health`` above is
    # deliberately outside it so healthchecks (Render, uptime monitors) pass.
    auth_deps = [Depends(require_basic_auth)]
    app.include_router(audits_routes.router, dependencies=auth_deps)
    app.include_router(taxonomy_routes.router, dependencies=auth_deps)
    app.include_router(competitive_routes.router, dependencies=auth_deps)
    app.include_router(strategy_routes.router, dependencies=auth_deps)

    return app


app = create_app()
