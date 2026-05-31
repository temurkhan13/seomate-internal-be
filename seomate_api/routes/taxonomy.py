"""Taxonomy routes — expose the parsed catalog to the UI.

The Catalog is a singleton loaded at app startup (see lifespan in
``main.py``). Lookups are O(1).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from seomate.taxonomy import Catalog
from seomate_api.deps import get_catalog
from seomate_api.schemas import VariableResponse

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])

CatalogParam = Annotated[Catalog, Depends(get_catalog)]


@router.get("/version", response_model=dict[str, str])
async def get_version(catalog: CatalogParam) -> dict[str, str]:
    """Return the content-hash version of the loaded taxonomy."""
    return {"version": catalog.version, "source_path": str(catalog.source_path)}


@router.get("/variables/{variable_id}", response_model=VariableResponse)
async def get_variable(variable_id: str, catalog: CatalogParam) -> VariableResponse:
    """Return one variable's full definition (Steps 1-7 + rules + dependencies)."""
    var = catalog.get(variable_id)
    if var is None:
        raise HTTPException(
            status_code=404,
            detail=f"Variable {variable_id} not in taxonomy",
        )
    return VariableResponse.model_validate(
        {
            **var.model_dump(),
            "evidence_weight": var.evidence_weight.value if var.evidence_weight else None,
            "has_step_1_5": var.has_step_1_5,
        }
    )
