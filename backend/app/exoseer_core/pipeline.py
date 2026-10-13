"""High-level pipeline orchestration: ingest -> preprocess -> detect -> fold ->
vet -> explain, emitting stage/progress via a callback. Returns a plain dict
matching the AnalysisResult schema so the route layer stays thin and web-free
science stays in the engine.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from . import detect as detect_mod
from . import explain as explain_mod
from . import fold as fold_mod
from . import preprocess as preprocess_mod
from . import stellar as stellar_mod
from . import vet as vet_mod
from .types import LightCurve, ProgressFn, StellarParams, noop_progress

DISPLAY_MAX = 12000  # cap transported light-curve points (full data used for search)


def _downsample(*arrays: np.ndarray, n: int = DISPLAY_MAX) -> list[list[float]]:
    length = arrays[0].size
    if length <= n:
        idx = np.arange(length)
    else:
        idx = np.linspace(0, length - 1, n).astype(int)
    return [np.asarray(a)[idx].astype(float).tolist() for a in arrays]


def _round_list(a, nd: int = 6) -> list[float]:
    return [round(float(x), nd) for x in a]


def run_pipeline(
    lc: LightCurve,
    target: str,
    mission: Optional[str],
    options: dict,
    on_progress: ProgressFn = noop_progress,
    stellar: Optional[StellarParams] = None,
) -> dict:
    warnings: list[str] = []
    if lc.meta.get("from_cache"):
        warnings.append("Loaded from cache.")

    # --- Preprocess --------------------------------------------------------
    on_progress("detrending", 0.0)
    pre = preprocess_mod.preprocess(lc, on_progress=on_progress)

    # --- Detect ------------------------------------------------------------
    on_progress("searching", 0.0)
    det = detect_mod.detect(
        pre,
        sde_threshold=float(options.get("sde_threshold", 7.0)),
        period_min=float(options.get("period_min", 0.5)),
        period_max=float(options.get("period_max", 50.0)),
        on_progress=on_progress,
    )
    if det.period_ambiguous:
        warnings.append("Box- and template-search periods disagree; period may be ambiguous.")

    # --- Fold --------------------------------------------------------------
    on_progress("folding", 0.0)
    fr = fold_mod.fold(pre, det, on_progress=on_progress)

    # --- Stellar + Vet -----------------------------------------------------
    on_progress("vetting", 0.0)
    if stellar is None:
        stellar = stellar_mod.lookup(target, mission)
    vr = vet_mod.vet(pre, det, stellar)
    on_progress("vetting", 0.8)

    # --- Explain -----------------------------------------------------------
    on_progress("explaining", 0.2)
    narrative, importance, llm_used = explain_mod.explain(det, vr, target)
    on_progress("explaining", 1.0)

    # --- Assemble wire dict ------------------------------------------------
    t_ds, fn_ds, ff_ds = _downsample(pre.time, pre.flux_norm, pre.flux_flat)

    result = {
        "star": {
            "id": lc.meta.get("target", target),
            "mission": lc.meta.get("mission", mission),
            "teff": stellar.teff,
            "radius_rsun": stellar.radius_rsun,
            "logg": stellar.logg,
            "mass_msun": stellar.mass_msun,
        },
        "lightcurve": {
            "time": _round_list(t_ds, 6),
            "flux_norm": _round_list(fn_ds, 6),
            "flux_flat": _round_list(ff_ds, 6),
        },
        "detection": {
            "found": bool(det.found),
            "period_days": det.period_days,
            "t0": det.t0,
            "duration_hours": det.duration_hours,
            "depth_ppm": det.depth_ppm,
            "sde": det.sde,
            "fap": det.fap,
            "snr": det.snr,
            "n_transits": det.n_transits,
            "bls_period_days": det.bls_period_days,
            "period_ambiguous": det.period_ambiguous,
        },
        "folded": {
            "phase": _round_list(fr.phase, 5),
            "flux": _round_list(fr.flux, 6),
            "phase_binned": _round_list(fr.phase_binned, 5),
            "flux_binned": _round_list(fr.flux_binned, 6),
            "model": _round_list(fr.model_flux, 6),
            "model_phase": _round_list(fr.model_phase, 5),
        },
        "vetting": {
            "verdict": vr.verdict,
            "confidence": round(vr.confidence, 4),
            "probabilities": {
                "planet_candidate": round(vr.probabilities.get("planet_candidate", 0.0), 4),
                "eclipsing_binary": round(vr.probabilities.get("eclipsing_binary", 0.0), 4),
                "variable_or_other": round(vr.probabilities.get("variable_or_other", 0.0), 4),
            },
            "implied_radius_rearth": (
                round(vr.implied_radius_rearth, 3) if vr.implied_radius_rearth is not None else None
            ),
            "diagnostics": [
                {"key": d.key, "label": d.label, "value": d.value, "verdict": d.verdict, "reason": d.reason}
                for d in vr.diagnostics
            ],
        },
        "explanation": {
            "narrative": narrative,
            "feature_importance": [
                {"feature": fi["feature"], "contribution": round(fi["contribution"], 4)}
                for fi in importance
            ],
            "llm_used": llm_used,
        },
        "warnings": warnings,
    }
    on_progress("complete", 1.0)
    return result
