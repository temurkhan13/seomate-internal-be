"""Saved-analyses route , history for the Competitive + Strategy surfaces.

Audits are persisted and browsable; competitive runs and strategy snapshots are
too (the ``saved_analyses`` table). This serves that history: list past runs of a
kind (optionally for one domain) and fetch one in full , so a colleague can
revisit a past analysis for free instead of re-paying DataForSEO to look again.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from seomate.saved import get_analysis, list_analyses

router = APIRouter(prefix="/api/saved", tags=["saved"])


@router.get("")
async def list_saved(
    kind: str = Query(..., description="'competitive' or 'strategy'"),
    target: str | None = Query(
        None, description="Restrict to one domain (optional)."
    ),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Saved analyses of a kind, newest first. Summary only (no payload)."""
    if kind not in ("competitive", "strategy"):
        raise HTTPException(status_code=400, detail="kind must be competitive or strategy")
    return await list_analyses(kind, target, limit=limit)


@router.get("/{analysis_id}")
async def get_saved(analysis_id: UUID) -> dict:
    """One saved analysis with its full payload (free , no DataForSEO call)."""
    row = await get_analysis(analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return row
