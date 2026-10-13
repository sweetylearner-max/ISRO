"""GET /healthz -> liveness + engine capability report."""
from __future__ import annotations

import importlib.util

from fastapi import APIRouter

from ..exoseer_core import transitmodel, vet
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


def _have(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:  # noqa: BLE001
        return False


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(
        ok=True,
        model_loaded=vet.model_loaded(),
        engine={
            "tls": _have("transitleastsquares"),
            "lightkurve": _have("lightkurve"),
            "astropy": _have("astropy"),
            "batman": transitmodel.has_batman(),
            "xgboost": _have("xgboost"),
            "shap": _have("shap"),
        },
    )
