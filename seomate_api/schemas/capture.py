"""Capture response schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RuleResultResponse(BaseModel):
    """One Step 1.5 rule's outcome as exposed via the API."""

    model_config = ConfigDict(from_attributes=True)

    rule_id: int
    rule_text: str
    passed: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class CaptureSummaryResponse(BaseModel):
    """Listing view for /api/audits/{audit_id}/captures.

    Lightweight fields only — no value, no rules, no errors. Optimised
    for the filterable capture-table page in the UI.
    """

    model_config = ConfigDict(from_attributes=True)

    capture_id: UUID
    variable_id: str
    pillar: str
    captured_at: datetime
    subject_type: str
    subject_id: str
    status: str
    evidence_weight: str
    cost_incurred_gbp: Decimal
    rules_total: int = 0
    rules_passed: int = 0
    rules_failed: int = 0


class CaptureDetailResponse(BaseModel):
    """Full capture view for /api/audits/{audit_id}/captures/{variable_id}."""

    model_config = ConfigDict(from_attributes=True)

    capture_id: UUID
    audit_id: UUID
    variable_id: str
    pillar: str
    captured_at: datetime
    taxonomy_version: str
    subject_type: str
    subject_id: str
    status: str
    value: Any | None = None
    rules: list[RuleResultResponse] | None = None
    evidence_weight: str
    data_sources_used: list[str] = Field(default_factory=list)
    cost_incurred_gbp: Decimal
    staleness_seconds: int | None = None
    errors: list[str] | None = None
