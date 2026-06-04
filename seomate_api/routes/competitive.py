"""Competitive analysis route , you vs N competitors (the COMPETE layer).

A separate surface from the audit: runs a live DataForSEO Labs comparison of the
target against competitor domains across visibility, keyword gaps, and
positioning. Each call is paid (Labs), so it is GET-with-explicit-params and the
UI only triggers it on an intentional submit. Pass real business competitors
for a meaningful result , keyword-overlap auto-discovery is a weak fallback.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from seomate.competitive import run_competitive
from seomate.saved import attach_analysis, save_analysis

router = APIRouter(prefix="/api/competitive", tags=["competitive"])


class CompetitorTake(BaseModel):
    domain: str
    take: str


class CompetitiveAnalysisIn(BaseModel):
    """A session-authored strategic read attached to a saved competitive run.

    The platform produces the numbers; a Claude session writes this judgment and
    PUTs it so it renders in the run's "Strategist read" section. No analysis is
    ever generated server-side , this endpoint only stores what a session wrote.
    """

    headline: str
    competitor_take: list[CompetitorTake] | None = None
    the_gaps: list[str] | None = None
    recommendations: list[str] | None = None
    self_gap: str | None = None


@router.get("")
async def competitive(
    target: str = Query(..., description="Site domain to analyse, e.g. example.com"),
    competitors: str | None = Query(
        None,
        description="Comma-separated competitor domains. If omitted, auto-discovered (low quality for niche sites).",
    ),
    keyword_limit: int = Query(100, ge=10, le=500),
) -> dict:
    """Run a live competitive analysis. Hits DataForSEO Labs (paid) on each call."""
    comp_list = [c.strip() for c in (competitors or "").split(",") if c.strip()]
    try:
        report = await run_competitive(
            target, comp_list or None, keyword_limit=keyword_limit
        )
    except Exception as exc:  # noqa: BLE001 - surface upstream failure to the UI
        raise HTTPException(
            status_code=502, detail=f"competitive analysis failed: {exc}"
        ) from exc
    # Persist the run so it shows in history and can be revisited for free.
    report["analysis_id"] = await save_analysis(
        "competitive", report.get("target", target), report
    )
    return report


@router.put("/{analysis_id}/analysis")
async def attach_competitive_analysis(
    analysis_id: str, body: CompetitiveAnalysisIn
) -> dict:
    """Attach a session-authored strategic read to a saved run (no DataForSEO).

    Free: stores the judgment a Claude session wrote for an existing run so the
    saved page shows the "so what" beside the numbers.
    """
    updated = await attach_analysis(analysis_id, body.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="saved analysis not found")
    return {"analysis_id": updated, "status": "attached"}
