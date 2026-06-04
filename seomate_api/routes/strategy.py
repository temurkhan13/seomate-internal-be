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

from seomate.agent import audit_diff, build_strategy
from seomate.competitive import run_competitive
from seomate.saved import save_analysis
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
) -> dict:
    """Domain-driven strategy , FREE (DB only): the latest audit's positioning +
    sequenced waves, plus the Loop diff (what moved since the previous audit).

    The paid competitive half (standing + keyword opportunities) is NOT run here.
    It lives on /api/competitive and the UI fetches it only on an explicit action,
    so navigating to the strategy view never silently spends DataForSEO budget.
    Returns ``has_audit: false`` (audit null) when the domain has no audit yet.
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
    diff = await audit_diff(norm)

    return {
        "target": norm,
        "has_audit": audit_id is not None,
        "audit": audit_strategy,
        "diff": diff,
    }


@router.get("/run")
async def strategy_run(
    session: DBSession,
    target: str = Query(..., description="Site domain, e.g. example.com"),
    competitors: str | None = Query(
        None, description="Comma-separated competitor domains for the competitive half."
    ),
    focus: str | None = Query(
        None,
        description="Comma-separated focus/priority keywords. When competitors are omitted, competitors are derived from who ranks for these.",
    ),
    keyword_limit: int = Query(100, ge=10, le=500),
) -> dict:
    """Build a full strategy SNAPSHOT and persist it , PAID (runs competitive).

    Bundles the free audit-half (positioning + waves + Loop diff) with a live
    competitive run (standing + keyword opportunities), saves the whole bundle as
    a ``kind='strategy'`` row, and returns it (with ``analysis_id``). The saved
    snapshot can then be revisited for free from the Strategy history, exactly
    like an audit. This is the only strategy endpoint that spends DataForSEO.
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
    diff = await audit_diff(norm)

    comp_list = [c.strip() for c in (competitors or "").split(",") if c.strip()]
    focus_list = [k.strip() for k in (focus or "").split(",") if k.strip()]
    try:
        competitive = await run_competitive(
            target, comp_list or None, seed_keywords=focus_list or None, keyword_limit=keyword_limit
        )
    except Exception as exc:  # noqa: BLE001 - surface upstream failure to the UI
        raise HTTPException(
            status_code=502, detail=f"competitive analysis failed: {exc}"
        ) from exc

    payload = {
        "target": norm,
        "has_audit": audit_id is not None,
        "audit": audit_strategy,
        "diff": diff,
        "competitive": competitive,
    }
    payload["analysis_id"] = await save_analysis("strategy", norm, payload)
    return payload
