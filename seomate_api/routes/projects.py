"""Projects route , the platform's top-level view.

A "project" is a site (domain) the platform has worked on. This aggregates the
existing audits + saved analyses by domain into project summaries for the home
dashboard: latest audit health, run counts, latest competitive/strategy, and
last activity. No new tables , projects are derived from what is already stored,
so it works immediately for every site that has been audited or analysed.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from seomate.storage import Audit, Capture, SavedAnalysis
from seomate_api.deps import get_db_session

router = APIRouter(prefix="/api/projects", tags=["projects"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]

_PILLAR_LABEL = {
    "P0": "Relevance & structure",
    "P1": "On-page",
    "P2": "Technical",
    "P3": "Off-page authority",
    "P4": "Content & E-E-A-T",
    "P5": "Local",
    "P6": "AI search / GEO",
}

# Friendly display names for known projects; falls back to the bare domain.
_FRIENDLY_NAMES = {
    "pixelettetech.com": "Pixelette Technologies",
}


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt else None


@router.get("")
async def list_projects(session: DBSession) -> list[dict[str, Any]]:
    """Every project (site) the platform has worked on, newest activity first.

    Each project carries the LATEST audit's health (overall + per-pillar), the
    run counts, the latest competitive + strategy snapshot ids, and the last
    activity timestamp , enough for a dashboard card without opening anything.
    """
    # 1) audits grouped by domain , the latest one + how many in total.
    audits = list(
        (await session.execute(select(Audit).order_by(desc(Audit.started_at)))).scalars().all()
    )
    by_domain: dict[str, dict[str, Any]] = {}
    for a in audits:
        e = by_domain.get(a.site_domain)
        if e is None:
            by_domain[a.site_domain] = {"latest": a, "count": 1}
        else:
            e["count"] += 1

    # 2) per-pillar health for just the latest audits (one grouped query).
    latest_ids = [e["latest"].audit_id for e in by_domain.values()]
    pillar_health: dict[Any, dict[str, dict[str, int]]] = {}
    if latest_ids:
        rows = (
            await session.execute(
                select(Capture.audit_id, Capture.pillar, Capture.status, func.count())
                .where(Capture.audit_id.in_(latest_ids))
                .group_by(Capture.audit_id, Capture.pillar, Capture.status)
            )
        ).all()
        for aid, pillar, status, n in rows:
            pillar_health.setdefault(aid, {}).setdefault(pillar, {})[status] = int(n)

    # 3) saved analyses grouped by target + kind , latest id/date + count.
    analyses = (
        await session.execute(
            select(
                SavedAnalysis.analysis_id,
                SavedAnalysis.kind,
                SavedAnalysis.target,
                SavedAnalysis.created_at,
            ).order_by(desc(SavedAnalysis.created_at))
        )
    ).all()
    sa_by: dict[str, dict[str, dict[str, Any]]] = {}
    for aid, kind, target, created in analyses:
        kinds = sa_by.setdefault(target, {})
        if kind not in kinds:
            kinds[kind] = {"latest_id": str(aid), "latest_at": created, "count": 1}
        else:
            kinds[kind]["count"] += 1

    # 4) assemble one card per domain (union of audited + analysed sites).
    projects: list[dict[str, Any]] = []
    for d in set(by_domain) | set(sa_by):
        latest_audit = None
        audit_count = 0
        au = by_domain.get(d)
        if au:
            a = au["latest"]
            audit_count = au["count"]
            ph = pillar_health.get(a.audit_id, {})
            pillars = []
            for p in sorted(_PILLAR_LABEL):
                st = ph.get(p, {})
                graded = st.get("passed", 0) + st.get("failed", 0) + st.get("partial", 0)
                pillars.append({
                    "pillar": p,
                    "label": _PILLAR_LABEL[p],
                    "health_pct": round(100 * st.get("passed", 0) / graded) if graded else None,
                })
            graded_total = a.variables_passed + a.variables_failed + a.variables_partial
            latest_audit = {
                "audit_id": str(a.audit_id),
                "status": a.status,
                "completed_at": _iso(a.completed_at) or _iso(a.started_at),
                "started_at": _iso(a.started_at),
                "overall_pct": round(100 * a.variables_passed / graded_total) if graded_total else None,
                "variables_attempted": a.variables_attempted,
                "pillars": pillars,
            }

        sa = sa_by.get(d, {})
        comp = sa.get("competitive")
        strat = sa.get("strategy")
        latest_competitive = (
            {"analysis_id": comp["latest_id"], "created_at": _iso(comp["latest_at"])}
            if comp else None
        )
        latest_strategy = (
            {"analysis_id": strat["latest_id"], "created_at": _iso(strat["latest_at"])}
            if strat else None
        )
        dates = [
            x for x in (
                latest_audit["completed_at"] if latest_audit else None,
                _iso(comp["latest_at"]) if comp else None,
                _iso(strat["latest_at"]) if strat else None,
            ) if x
        ]
        projects.append({
            "domain": d,
            "name": _FRIENDLY_NAMES.get(d, d),
            "latest_audit": latest_audit,
            "audit_count": audit_count,
            "latest_competitive": latest_competitive,
            "competitive_count": comp["count"] if comp else 0,
            "latest_strategy": latest_strategy,
            "strategy_count": strat["count"] if strat else 0,
            "last_activity": max(dates) if dates else None,
        })

    projects.sort(key=lambda p: p["last_activity"] or "", reverse=True)
    return projects


@router.get("/{domain}")
async def get_project(domain: str, session: DBSession) -> dict[str, Any]:
    """One project's summary , the cheap version for the workspace header.

    The list endpoint aggregates every project; a workspace page only needs one,
    and it re-renders that header on every tab switch. This scopes all queries to
    the single domain so a tab switch does not pay for the whole portfolio.
    """
    audits = list(
        (await session.execute(
            select(Audit)
            .where(Audit.site_domain == domain)
            .order_by(desc(Audit.started_at))
        )).scalars().all()
    )
    latest = audits[0] if audits else None
    latest_audit = None
    if latest is not None:
        rows = (
            await session.execute(
                select(Capture.pillar, Capture.status, func.count())
                .where(Capture.audit_id == latest.audit_id)
                .group_by(Capture.pillar, Capture.status)
            )
        ).all()
        ph: dict[str, dict[str, int]] = {}
        for pillar, status, n in rows:
            ph.setdefault(pillar, {})[status] = int(n)
        pillars = []
        for p in sorted(_PILLAR_LABEL):
            st = ph.get(p, {})
            graded = st.get("passed", 0) + st.get("failed", 0) + st.get("partial", 0)
            pillars.append({
                "pillar": p,
                "label": _PILLAR_LABEL[p],
                "health_pct": round(100 * st.get("passed", 0) / graded) if graded else None,
            })
        graded_total = latest.variables_passed + latest.variables_failed + latest.variables_partial
        latest_audit = {
            "audit_id": str(latest.audit_id),
            "status": latest.status,
            "completed_at": _iso(latest.completed_at) or _iso(latest.started_at),
            "started_at": _iso(latest.started_at),
            "overall_pct": round(100 * latest.variables_passed / graded_total) if graded_total else None,
            "variables_attempted": latest.variables_attempted,
            "pillars": pillars,
        }

    sa = (
        await session.execute(
            select(SavedAnalysis.analysis_id, SavedAnalysis.kind, SavedAnalysis.created_at)
            .where(SavedAnalysis.target == domain)
            .order_by(desc(SavedAnalysis.created_at))
        )
    ).all()
    comp = [r for r in sa if r.kind == "competitive"]
    strat = [r for r in sa if r.kind == "strategy"]
    latest_competitive = (
        {"analysis_id": str(comp[0].analysis_id), "created_at": _iso(comp[0].created_at)}
        if comp else None
    )
    latest_strategy = (
        {"analysis_id": str(strat[0].analysis_id), "created_at": _iso(strat[0].created_at)}
        if strat else None
    )
    if not audits and not sa:
        raise HTTPException(status_code=404, detail=f"No project for {domain}")
    dates = [
        x for x in (
            latest_audit["completed_at"] if latest_audit else None,
            _iso(comp[0].created_at) if comp else None,
            _iso(strat[0].created_at) if strat else None,
        ) if x
    ]
    return {
        "domain": domain,
        "name": _FRIENDLY_NAMES.get(domain, domain),
        "latest_audit": latest_audit,
        "audit_count": len(audits),
        "latest_competitive": latest_competitive,
        "competitive_count": len(comp),
        "latest_strategy": latest_strategy,
        "strategy_count": len(strat),
        "last_activity": max(dates) if dates else None,
    }


@router.get("/{domain}/trend")
async def project_trend(domain: str, session: DBSession) -> dict[str, Any]:
    """Improvement over time for one project.

    The whole point of the audit loop: as fixes land and the site is re-audited,
    the score should climb. This returns the trajectory , overall + per-pillar
    audit health across every audit, and the target's search footprint across
    competitive runs , so "did we improve?" becomes a line, not a guess.

    Both series are de-duped to the last run per calendar day, so a burst of
    same-day re-runs collapses to one clean point.
    """
    audits = list(
        (await session.execute(
            select(Audit).where(Audit.site_domain == domain).order_by(Audit.started_at)
        )).scalars().all()
    )

    pillar_health: dict[Any, dict[str, dict[str, int]]] = {}
    if audits:
        rows = (
            await session.execute(
                select(Capture.audit_id, Capture.pillar, Capture.status, func.count())
                .where(Capture.audit_id.in_([a.audit_id for a in audits]))
                .group_by(Capture.audit_id, Capture.pillar, Capture.status)
            )
        ).all()
        for aid, pillar, status, n in rows:
            pillar_health.setdefault(aid, {}).setdefault(pillar, {})[status] = int(n)

    # last audit per calendar day (audits are ordered oldest-first, so last wins).
    by_day: dict[str, Audit] = {}
    for a in audits:
        day = (a.completed_at or a.started_at).isoformat()[:10]
        by_day[day] = a

    audit_trend = []
    for day in sorted(by_day):
        a = by_day[day]
        ph = pillar_health.get(a.audit_id, {})
        pillars: dict[str, int | None] = {}
        for p in sorted(_PILLAR_LABEL):
            st = ph.get(p, {})
            graded = st.get("passed", 0) + st.get("failed", 0) + st.get("partial", 0)
            pillars[p] = round(100 * st.get("passed", 0) / graded) if graded else None
        graded_total = a.variables_passed + a.variables_failed + a.variables_partial
        audit_trend.append({
            "audit_id": str(a.audit_id),
            "at": day,
            "overall_pct": round(100 * a.variables_passed / graded_total) if graded_total else None,
            "pillars": pillars,
        })

    # competitive footprint over time , the target's own visibility per day.
    comps = (
        await session.execute(
            select(SavedAnalysis.created_at, SavedAnalysis.payload)
            .where(SavedAnalysis.kind == "competitive", SavedAnalysis.target == domain)
            .order_by(SavedAnalysis.created_at)
        )
    ).all()
    comp_by_day: dict[str, dict[str, Any]] = {}
    for created, payload in comps:
        day = created.isoformat()[:10]
        vis = (payload or {}).get("visibility") or []
        tgt = next((v for v in vis if v.get("is_target")), None)
        if tgt:
            comp_by_day[day] = {
                "at": day,
                "organic_keywords": tgt.get("organic_keywords"),
                "organic_traffic": tgt.get("organic_traffic"),
            }
    competitive_trend = [comp_by_day[d] for d in sorted(comp_by_day)]

    return {
        "domain": domain,
        "pillar_labels": _PILLAR_LABEL,
        "audit_trend": audit_trend,
        "competitive_trend": competitive_trend,
    }
