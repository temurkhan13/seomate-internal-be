"""Site strategy route , the independent STRATEGIST surface.

Unlike ``/audits/{id}/strategy`` (one audit's strategic view), this is
domain-driven: it takes a site, picks the latest audit for it (on-site
positioning + the fixes sequenced into waves), and combines that with a live
competitive run (standing + keyword opportunities) into one strategy surface.
Strategy is a property of the site, not of a single audit run.

The competitive half hits DataForSEO Labs (paid), so this is
GET-with-explicit-params and the UI only triggers it on an intentional submit.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from seomate.agent import build_strategy
from seomate.competitive import run_competitive
from seomate.storage import Audit
from seomate_api.deps import get_db_session

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


def _norm_domain(d: str) -> str:
    d = (d or "").strip().lower()
    for p in ("https://", "http://"):
        if d.startswith(p):
            d = d[len(p):]
    if d.startswith("www."):
        d = d[4:]
    return d.rstrip("/")


@router.get("")
async def site_strategy(
    session: DBSession,
    target: str = Query(..., description="Site domain, e.g. example.com"),
    competitors: str | None = Query(
        None,
        description="Comma-separated competitor domains; auto-discovered if omitted.",
    ),
    keyword_limit: int = Query(100, ge=10, le=500),
) -> dict:
    """Domain-driven strategy: latest-audit positioning + sequenced waves, plus a
    live competitive run (standing + keyword opportunities). The competitive half
    is paid (DataForSEO Labs). Returns ``has_audit: false`` (with the audit half
    null) when the domain has no audit yet , the competitive half still renders.
    """
    norm = _norm_domain(target)

    audit_id = (
        await session.execute(
            select(Audit.audit_id)
            .where(Audit.site_domain == norm)
            .order_by(desc(Audit.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    audit_strategy = await build_strategy(audit_id) if audit_id else None

    comp_list = [c.strip() for c in (competitors or "").split(",") if c.strip()]
    try:
        competitive = await run_competitive(
            target, comp_list or None, keyword_limit=keyword_limit
        )
    except Exception as exc:  # noqa: BLE001 - surface upstream failure to the UI
        raise HTTPException(
            status_code=502, detail=f"competitive analysis failed: {exc}"
        ) from exc

    return {
        "target": norm,
        "has_audit": audit_id is not None,
        "audit": audit_strategy,
        "competitive": competitive,
    }
