"""FastAPI dependency-injection helpers.

The DB session and the Taxonomy catalog are the two app-wide
dependencies routes consume. The catalog is loaded once at startup
(see ``main.py`` lifespan) and read-only thereafter.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from seomate.storage.db import get_async_session_factory
from seomate.taxonomy import Catalog


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async DB session per request.

    The API is read-only at H1, so the session is used only for SELECTs.
    No commit/rollback semantics needed beyond context-manager close.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


def get_catalog(request: Request) -> Catalog:
    """Return the singleton taxonomy catalog loaded at app startup."""
    return request.app.state.catalog


# Convenience type aliases for route signatures.
SessionDep = Depends(get_db_session)
CatalogDep = Depends(get_catalog)
