"""Taxonomy response schemas — what the UI sees about a Variable.

These flatten the parsed Variable model from ``seomate.taxonomy.schemas``
into UI-friendly shapes (no Pydantic ``Any`` in evidence dicts, dependency
edges as a flat list, etc.).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RuleSummaryResponse(BaseModel):
    """Step 1.5 rule definition (from the taxonomy, not a capture's outcome)."""

    model_config = ConfigDict(from_attributes=True)

    rule_id: int
    title: str
    text: str


class CitationResponse(BaseModel):
    """A citation parsed from Step 2."""

    model_config = ConfigDict(from_attributes=True)

    label: str
    url: str | None = None
    description: str | None = None


class DependencyResponse(BaseModel):
    """One classified dependency edge from Step 7."""

    model_config = ConfigDict(from_attributes=True)

    target_id: str
    kind: str
    note: str | None = None


class VariableResponse(BaseModel):
    """A taxonomy variable as exposed to the UI."""

    model_config = ConfigDict(from_attributes=True)

    variable_id: str
    pillar: str
    name: str
    evidence_weight: str | None = None
    definition: str = ""
    rules: list[RuleSummaryResponse] = []
    citations: list[CitationResponse] = []
    weight_rationale: str = ""
    data_sources: list[str] = []
    verification: str = ""
    cost: str = ""
    dependencies: list[DependencyResponse] = []
    has_step_1_5: bool
    removed: bool
    removed_into: str | None = None
