"""GET /catalog -> famous demo systems."""
from __future__ import annotations

from fastapi import APIRouter

from ..exoseer_core import catalog as catalog_mod
from ..schemas import CatalogEntry, CatalogResponse

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog() -> CatalogResponse:
    return CatalogResponse(systems=[CatalogEntry(**e) for e in catalog_mod.get_catalog()])
