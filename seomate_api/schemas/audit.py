"""Audit response schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditSummaryResponse(BaseModel):
    """Listing view for /api/audits — counts only, no captures."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: UUID
    site_domain: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    taxonomy_version: str
    total_cost_gbp: Decimal | None = None
    variables_attempted: int
    variables_passed: int
    variables_failed: int
    variables_partial: int
    variables_errored: int
    variables_unmeasurable: int
    anomaly_count: int = Field(
        default=0,
        description="Number of completeness-gate anomalies detected at audit close.",
    )
    consistency_violation_count: int = Field(
        default=0,
        description="Number of cross-extractor consistency-rule violations detected at audit close.",
    )


class AuditDetailResponse(AuditSummaryResponse):
    """Detail view for /api/audits/{audit_id}. Adds the config snapshot and structured anomaly lists."""

    config_snapshot: dict[str, Any] = Field(
        description="The effective YAML config at audit start, frozen for reproducibility.",
    )
    anomalies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Completeness-gate anomalies. Each item carries 'check', 'severity', and check-specific evidence fields.",
    )
    consistency_violations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Cross-extractor consistency-rule violations. Each item carries 'check', 'severity', and rule-specific evidence fields.",
    )
