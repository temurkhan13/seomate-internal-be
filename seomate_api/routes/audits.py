"""Audit and capture routes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from seomate.agent import plan_fixes
from seomate.storage import Audit, Capture
from seomate.taxonomy import Catalog
from seomate_api.deps import get_catalog, get_db_session
from seomate_api.schemas import (
    AuditDetailResponse,
    AuditSummaryResponse,
    CaptureDetailResponse,
    CaptureSummaryResponse,
    RuleResultResponse,
)

router = APIRouter(prefix="/api/audits", tags=["audits"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]


async def _deferred_counts(session: AsyncSession, audit_ids: list[UUID]) -> dict[UUID, int]:
    """Count, per audit, captures flagged deferred (value->>'deferred' == 'true').

    Deferred is a per-capture business-decision flag (e.g. a paid source not
    activated), a subset of 'unmeasurable'. Computed here so the dashboard can
    show 'genuine unmeasurable' vs 'deferred' without a schema column.
    """
    if not audit_ids:
        return {}
    stmt = (
        select(Capture.audit_id, func.count())
        .where(
            Capture.audit_id.in_(audit_ids),
            Capture.value["deferred"].astext == "true",
        )
        .group_by(Capture.audit_id)
    )
    rows = await session.execute(stmt)
    return {aid: n for aid, n in rows.all()}


async def _not_applicable_counts(
    session: AsyncSession, audit_ids: list[UUID]
) -> dict[UUID, int]:
    """Count, per audit, captures with status 'not_applicable'.

    NOT_APPLICABLE means measured-but-no-pass/fail-bar (descriptive metrics).
    The audits table only stores passed/failed/partial/errored/unmeasurable
    counts, so without this the Outcomes tiles undercount and don't reconcile
    to variables_attempted. Computed live from captures, no schema column.
    """
    if not audit_ids:
        return {}
    stmt = (
        select(Capture.audit_id, func.count())
        .where(
            Capture.audit_id.in_(audit_ids),
            Capture.status == "not_applicable",
        )
        .group_by(Capture.audit_id)
    )
    rows = await session.execute(stmt)
    return {aid: n for aid, n in rows.all()}


@router.get("", response_model=list[AuditSummaryResponse])
async def list_audits(
    session: DBSession,
    site_domain: str | None = Query(None, description="Filter by exact site domain"),
    limit: int = Query(50, ge=1, le=500),
) -> list[AuditSummaryResponse]:
    """List audits, most recent first."""
    stmt = select(Audit).order_by(desc(Audit.started_at)).limit(limit)
    if site_domain:
        stmt = stmt.where(Audit.site_domain == site_domain)
    result = await session.execute(stmt)
    audits = list(result.scalars().all())
    audit_ids = [a.audit_id for a in audits]
    deferred = await _deferred_counts(session, audit_ids)
    not_applicable = await _not_applicable_counts(session, audit_ids)
    return [
        AuditSummaryResponse.model_validate(a).model_copy(
            update={
                "variables_deferred": deferred.get(a.audit_id, 0),
                "variables_not_applicable": not_applicable.get(a.audit_id, 0),
            }
        )
        for a in audits
    ]


@router.get("/{audit_id}", response_model=AuditDetailResponse)
async def get_audit(audit_id: UUID, session: DBSession) -> AuditDetailResponse:
    """Audit detail including the frozen config snapshot."""
    audit = await session.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    deferred = await _deferred_counts(session, [audit_id])
    not_applicable = await _not_applicable_counts(session, [audit_id])
    return AuditDetailResponse.model_validate(audit).model_copy(
        update={
            "variables_deferred": deferred.get(audit_id, 0),
            "variables_not_applicable": not_applicable.get(audit_id, 0),
        }
    )


@router.get("/{audit_id}/plan")
async def get_audit_plan(audit_id: UUID) -> dict:
    """Remediation plan for an audit , the platform's FIX layer.

    Joins every actionable finding (failed / partial) with its remediation spec
    and returns prioritized work orders grouped by who-can-fix-them
    (session / human / budget / owner / offsite), with the auto-generatable
    fixes flagged and each work order's failing rules + verify path surfaced.
    This exposes the existing ``plan_fixes`` engine through the API so the
    dashboard can show "here is how to fix what the audit found", not just the
    diagnosis. ``plan_fixes`` opens its own DB session.
    """
    try:
        return await plan_fixes(audit_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{audit_id}/captures", response_model=list[CaptureSummaryResponse])
async def list_captures(
    audit_id: UUID,
    session: DBSession,
    catalog: CatalogDep,
    pillar: str | None = Query(None, description="Filter by pillar (e.g. 'P1')"),
    status: str | None = Query(None, description="Filter by capture status"),
    evidence_weight: str | None = Query(None, description="Filter by evidence weight"),
    subject_type: str | None = Query(None, description="Filter by subject type"),
) -> list[CaptureSummaryResponse]:
    """List captures for an audit, optionally filtered."""
    audit = await session.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")

    stmt = select(Capture).where(Capture.audit_id == audit_id).order_by(
        Capture.pillar, Capture.variable_id
    )
    if pillar:
        stmt = stmt.where(Capture.pillar == pillar)
    if status:
        stmt = stmt.where(Capture.status == status)
    if evidence_weight:
        stmt = stmt.where(Capture.evidence_weight == evidence_weight)
    if subject_type:
        stmt = stmt.where(Capture.subject_type == subject_type)

    result = await session.execute(stmt)
    captures = result.scalars().all()
    return [_to_summary(c, catalog) for c in captures]


@router.get(
    "/{audit_id}/captures/{variable_id}",
    response_model=CaptureDetailResponse,
)
async def get_capture(
    audit_id: UUID,
    variable_id: str,
    session: DBSession,
) -> Capture:
    """Single capture detail by audit + variable id."""
    stmt = select(Capture).where(
        Capture.audit_id == audit_id,
        Capture.variable_id == variable_id,
    )
    result = await session.execute(stmt)
    capture = result.scalar_one_or_none()
    if capture is None:
        raise HTTPException(
            status_code=404,
            detail=f"Capture not found: audit={audit_id} variable={variable_id}",
        )
    return capture


# ─── Helpers ────────────────────────────────────────────────────────────────


def _to_summary(c: Capture, catalog: Catalog | None = None) -> CaptureSummaryResponse:
    """Convert a Capture ORM row into a CaptureSummaryResponse with rule counts.

    Resolves the variable's human name from the taxonomy so the UI can show
    "P1-31 — Open Graph tags" instead of a bare code (and so a mislabeled
    capture is visible at a glance).
    """
    rules: Iterable[dict] = c.rules or []
    rules_total = len(list(rules)) if c.rules else 0
    rules_passed = sum(1 for r in (c.rules or []) if r.get("passed"))
    rules_failed = rules_total - rules_passed
    var = catalog.get(c.variable_id) if catalog else None
    return CaptureSummaryResponse(
        capture_id=c.capture_id,
        variable_id=c.variable_id,
        variable_name=(var.name if var else ""),
        pillar=c.pillar,
        captured_at=c.captured_at,
        subject_type=c.subject_type,
        subject_id=c.subject_id,
        status=c.status,
        evidence_weight=c.evidence_weight,
        cost_incurred_gbp=c.cost_incurred_gbp,
        rules_total=rules_total,
        rules_passed=rules_passed,
        rules_failed=rules_failed,
    )
