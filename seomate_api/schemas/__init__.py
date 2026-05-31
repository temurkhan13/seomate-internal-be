"""Pydantic response schemas for the SEOMATE API.

These are the shapes the Next.js UI consumes. TypeScript types are
generated from FastAPI's OpenAPI schema and live in ``web/lib/types.ts``.
"""
from seomate_api.schemas.audit import (
    AuditDetailResponse,
    AuditSummaryResponse,
)
from seomate_api.schemas.capture import (
    CaptureDetailResponse,
    CaptureSummaryResponse,
    RuleResultResponse,
)
from seomate_api.schemas.taxonomy import (
    CitationResponse,
    DependencyResponse,
    RuleSummaryResponse,
    VariableResponse,
)

__all__ = [
    "AuditDetailResponse",
    "AuditSummaryResponse",
    "CaptureDetailResponse",
    "CaptureSummaryResponse",
    "CitationResponse",
    "DependencyResponse",
    "RuleResultResponse",
    "RuleSummaryResponse",
    "VariableResponse",
]
