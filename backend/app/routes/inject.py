"""POST /inject -> job (same poll endpoint as /analyze). Injection-recovery sandbox."""
from __future__ import annotations

from fastapi import APIRouter

from ..exoseer_core import inject as inject_mod
from ..exoseer_core import run_pipeline, stellar as stellar_mod
from ..exoseer_core.types import NoiseParams, PlanetParams
from ..jobs import store
from ..schemas import InjectRequest, JobCreated

router = APIRouter(tags=["inject"])

_PERIOD_TOL = 0.02


def _recovery(injected: dict, det: dict, implied_radius, sde_threshold: float) -> dict:
    inj_p = injected.get("period_days") or 0.0
    rec_p = det.get("period_days") or 0.0
    period_ok = any(abs(rec_p / inj_p - r) < _PERIOD_TOL for r in (1.0, 2.0, 0.5)) if (inj_p and rec_p) else False
    recovered = bool(det.get("found") and (det.get("sde") or 0) >= sde_threshold and period_ok)
    return {
        "injected": {
            "radius_rearth": injected.get("radius_rearth"),
            "period_days": injected.get("period_days"),
            "impact": injected.get("impact"),
            "depth_ppm": injected.get("depth_ppm"),
        },
        "recovered": {
            "period_days": det.get("period_days"),
            "depth_ppm": det.get("depth_ppm"),
            "duration_hours": det.get("duration_hours"),
            "sde": det.get("sde"),
            "radius_rearth": implied_radius,
        },
        "recovered_bool": recovered,
    }


@router.post("/inject", response_model=JobCreated, status_code=202)
def inject(req: InjectRequest) -> JobCreated:
    job_id = store.create()
    sde_threshold = 7.0

    def run(on_progress) -> dict:
        stellar = stellar_mod.lookup(req.host)
        planet = PlanetParams(
            radius_rearth=req.planet.radius_rearth,
            period_days=req.planet.period_days,
            impact=req.planet.impact,
        )
        # Synthetic quiet baseline: instant, deterministic, and controlled noise —
        # ideal for the "shrink the planet until it's lost" detection-limit demo.
        # (The host still seeds real stellar radius/mass for the transit geometry.)
        lc = inject_mod.make_synthetic_lightcurve(
            req.host, planet, NoiseParams(level=req.noise_level), stellar=stellar,
            on_progress=on_progress, prefer_real=False,
        )
        options = {"sde_threshold": sde_threshold, "period_min": 0.5,
                   "period_max": max(2.0 * req.planet.period_days, 10.0)}
        result = run_pipeline(lc, req.host, "synthetic", options, on_progress=on_progress, stellar=stellar)
        result["injection"] = _recovery(
            lc.meta.get("injected", {}),
            result["detection"],
            result["vetting"].get("implied_radius_rearth"),
            sde_threshold,
        )
        return result

    store.submit(job_id, run)
    return JobCreated(job_id=job_id)
