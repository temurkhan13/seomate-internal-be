"""Audit and capture routes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from seomate.storage import Audit, Capture
from seomate_api.deps import get_db_session
from seomate_api.schemas import (
    AuditDetailResponse,
    AuditSummaryResponse,
    CaptureDetailResponse,
    CaptureSummaryResponse,
    RuleResultResponse,
)

router = APIRouter(prefix="/api/audits", tags=["audits"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[AuditSummaryResponse])
async def list_audits(
    session: DBSession,
    site_domain: str | None = Query(None, description="Filter by exact site domain"),
    limit: int = Query(50, ge=1, le=500),
) -> list[Audit]:
    """List audits, most recent first."""
    stmt = select(Audit).order_by(desc(Audit.started_at)).limit(limit)
    if site_domain:
        stmt = stmt.where(Audit.site_domain == site_domain)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{audit_id}", response_model=AuditDetailResponse)
async def get_audit(audit_id: UUID, session: DBSession) -> Audit:
    """Audit detail including the frozen config snapshot."""
    audit = await session.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return audit


@router.get("/{audit_id}/captures", response_model=list[CaptureSummaryResponse])
async def list_captures(
    audit_id: UUID,
    session: DBSession,
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
    return [_to_summary(c) for c in captures]


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


def _to_summary(c: Capture) -> CaptureSummaryResponse:
    """Convert a Capture ORM row into a CaptureSummaryResponse with rule counts."""
    rules: Iterable[dict] = c.rules or []
    rules_total = len(list(rules)) if c.rules else 0
    rules_passed = sum(1 for r in (c.rules or []) if r.get("passed"))
    rules_failed = rules_total - rules_passed
    return CaptureSummaryResponse(
        capture_id=c.capture_id,
        variable_id=c.variable_id,
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
