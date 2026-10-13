"""Astrophysical vetting — the core differentiator (AGENTS.md §7.5).

Computes physically-grounded diagnostics (odd-even depth, secondary eclipse,
transit shape, implied radius, signal strength, transit count), assembles a
feature vector, runs the trained XGBoost classifier when present (physics-based
heuristic otherwise), then produces a verdict in which HARD PHYSICAL FLAGS
override the ML — a strong secondary eclipse or a stellar-sized radius flips the
verdict to eclipsing binary no matter what the model says, and the explanation
says so.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .. import config
from .types import (
    Diagnostic,
    DetectionResult,
    Preprocessed,
    StellarParams,
    VetResult,
)

RSUN_IN_REARTH = 109.076

# Features the ML model sees (must match ml/01_build_training_set.ipynb).
# Odd-even / secondary / shape are deliberately NOT model features: the KOI table
# lacks continuous equivalents, so they act as physics overrides instead.
MODEL_FEATURES = [
    "period",
    "duration_hours",
    "depth_ppm",
    "snr",
    "implied_radius_rearth",
    "srad",
    "steff",
    "slogg",
    "duration_over_period",
    "depth_snr",
]

CLASSES = ["planet_candidate", "eclipsing_binary", "variable_or_other"]

# Solar imputation when stellar params are unavailable.
_SOLAR = {"srad": 1.0, "steff": 5772.0, "slogg": 4.44}


# --- Individual diagnostics -------------------------------------------------
def _diag_odd_even(pre: Preprocessed, det: DetectionResult) -> Diagnostic:
    """Compare alternating transit depths; >3σ mismatch suggests an eclipsing binary."""
    time, flux = pre.time, pre.flux_flat
    P, t0 = det.period_days, det.t0
    dur = (det.duration_hours or 0) / 24.0
    if not P or dur <= 0:
        return Diagnostic("odd_even", "Odd–even depth", "n/a", "flag", "Insufficient data.", 0.0)

    epoch = np.round((time - t0) / P).astype(int)
    phase = ((time - t0 + 0.5 * P) % P) - 0.5 * P
    in_tr = np.abs(phase) < 0.5 * dur
    out_tr = np.abs(phase) > 2.0 * dur
    if in_tr.sum() < 6 or out_tr.sum() < 10:
        return Diagnostic("odd_even", "Odd–even depth", "n/a", "flag", "Too few transit points.", 0.0)

    base = np.median(flux[out_tr])
    scatter = 1.4826 * np.median(np.abs(flux[out_tr] - base)) or 1e-6

    def depth_for(mask):
        pts = flux[in_tr & mask]
        if pts.size < 3:
            return None, None
        d = base - np.median(pts)
        err = scatter / np.sqrt(pts.size)
        return d, err

    d_odd, e_odd = depth_for((epoch % 2) == 1)
    d_even, e_even = depth_for((epoch % 2) == 0)
    if d_odd is None or d_even is None:
        return Diagnostic("odd_even", "Odd–even depth", "n/a", "flag", "Too few alternating transits.", 0.0)

    sigma = abs(d_odd - d_even) / np.sqrt(e_odd ** 2 + e_even ** 2)
    # TLS provides its own estimate; take the larger (more conservative).
    if det.odd_even_mismatch is not None:
        sigma = max(sigma, float(det.odd_even_mismatch))

    if sigma > config.ODD_EVEN_SIGMA_FAIL:
        return Diagnostic("odd_even", "Odd–even depth", f"{sigma:.1f}σ", "fail",
                          "Alternating transits differ strongly in depth — a hallmark of two eclipsing stars.", sigma)
    if sigma > config.ODD_EVEN_SIGMA_FLAG:
        return Diagnostic("odd_even", "Odd–even depth", f"{sigma:.1f}σ", "flag",
                          "Alternating depths differ mildly — likely red noise, but worth a look.", sigma)
    return Diagnostic("odd_even", "Odd–even depth", f"{sigma:.1f}σ", "pass",
                      "Alternating transit depths agree — consistent with one object.", sigma)


def _diag_secondary(pre: Preprocessed, det: DetectionResult) -> Diagnostic:
    """Search for an occultation near phase 0.5; a significant one implies a luminous companion."""
    time, flux = pre.time, pre.flux_flat
    P, t0 = det.period_days, det.t0
    dur = (det.duration_hours or 0) / 24.0
    if not P or dur <= 0:
        return Diagnostic("secondary", "Secondary eclipse", "n/a", "pass", "Not evaluable.", 0.0)

    phase01 = ((time - t0) % P) / P
    w = max(0.5 * dur / P, 0.01)
    in_sec = np.abs(phase01 - 0.5) < w
    baseline = (np.abs(phase01 - 0.5) > 3 * w) & (phase01 > 0.1) & (phase01 < 0.9)
    if in_sec.sum() < 3 or baseline.sum() < 10:
        return Diagnostic("secondary", "Secondary eclipse", "none", "pass",
                          "No occultation detectable at phase 0.5.", 0.0)

    base = np.median(flux[baseline])
    scatter = 1.4826 * np.median(np.abs(flux[baseline] - base)) or 1e-6
    sec_depth = base - np.median(flux[in_sec])
    sig = sec_depth / (scatter / np.sqrt(in_sec.sum()))

    if sig > config.SECONDARY_SIGNIFICANCE_FAIL and sec_depth > 0:
        return Diagnostic("secondary", "Secondary eclipse", f"{sig:.1f}σ", "fail",
                          "A clear dip halfway around the orbit — light from an eclipsed companion star.", sig)
    if sig > config.SECONDARY_SIGNIFICANCE_FLAG and sec_depth > 0:
        return Diagnostic("secondary", "Secondary eclipse", f"{sig:.1f}σ", "flag",
                          "A weak dip near phase 0.5 — possibly a shallow occultation.", sig)
    return Diagnostic("secondary", "Secondary eclipse", "none", "pass",
                      "No significant occultation at phase 0.5.", max(sig, 0.0))


def _diag_shape(pre: Preprocessed, det: DetectionResult) -> Diagnostic:
    """Flat-bottomed (U) is planet-like; sharp V often means grazing / stellar companion."""
    time, flux = pre.time, pre.flux_flat
    P, t0 = det.period_days, det.t0
    dur = (det.duration_hours or 0) / 24.0
    if not P or dur <= 0:
        return Diagnostic("shape", "Transit shape", "n/a", "flag", "Not evaluable.", 0.0)

    phase = ((time - t0 + 0.5 * P) % P) - 0.5 * P
    half = 0.5 * dur
    out_tr = np.abs(phase) > 2.0 * dur
    core = np.abs(phase) < 0.30 * half
    full = np.abs(phase) < half
    if out_tr.sum() < 10 or core.sum() < 3 or full.sum() < 6:
        return Diagnostic("shape", "Transit shape", "n/a", "flag", "Too few in-transit points.", 0.0)

    base = np.median(flux[out_tr])
    depth_core = base - np.median(flux[core])
    depth_full = base - np.median(flux[full])
    flatness = float(np.clip(depth_full / depth_core, 0.0, 1.0)) if depth_core > 0 else 0.0

    if flatness >= 0.7:
        return Diagnostic("shape", "Transit shape", "U-shaped", "pass",
                          "Flat-bottomed dip — consistent with a planet crossing the disk.", flatness)
    if flatness >= 0.5:
        return Diagnostic("shape", "Transit shape", "rounded", "flag",
                          "Somewhat rounded — mildly grazing geometry possible.", flatness)
    return Diagnostic("shape", "Transit shape", "V-shaped", "flag",
                      "Sharp V-shape — a grazing pass or stellar companion is possible.", flatness)


def _diag_radius(det: DetectionResult, stellar: StellarParams) -> tuple[Diagnostic, Optional[float]]:
    depth = det.depth or 0.0
    if not stellar.radius_rsun or depth <= 0:
        return (
            Diagnostic("radius", "Implied radius", "indeterminate", "flag",
                       "Stellar radius unknown — size cannot be pinned down.", 0.0),
            None,
        )
    r_earth = stellar.radius_rsun * np.sqrt(depth) * RSUN_IN_REARTH
    val = f"{r_earth:.2f} R⊕"
    if r_earth > config.RADIUS_REARTH_STELLAR + 3:
        return (Diagnostic("radius", "Implied radius", val, "fail",
                           "Far larger than any planet — almost certainly a stellar companion.", r_earth), r_earth)
    if r_earth > config.RADIUS_REARTH_STELLAR:
        return (Diagnostic("radius", "Implied radius", val, "flag",
                           "At the boundary between the largest planets and small stars.", r_earth), r_earth)
    return (Diagnostic("radius", "Implied radius", val, "pass",
                       "Within the planetary size range.", r_earth), r_earth)


def _diag_snr(det: DetectionResult) -> Diagnostic:
    sde = det.sde or 0.0
    val = f"SDE {sde:.1f}"
    if sde >= 10:
        return Diagnostic("snr", "Signal strength", val, "pass",
                          "Strong signal, well above the noise floor.", sde)
    if sde >= config.SDE_THRESHOLD:
        return Diagnostic("snr", "Signal strength", val, "flag",
                          "Marginal signal — real, but not far above the noise.", sde)
    return Diagnostic("snr", "Signal strength", val, "fail",
                      "Weak signal — could be noise.", sde)


def _diag_count(det: DetectionResult) -> Diagnostic:
    n = det.n_transits or 0
    if n >= 3:
        return Diagnostic("count", "Transits seen", f"{n}", "pass",
                          "Multiple transits — the period is well constrained.", float(n))
    if n == 2:
        return Diagnostic("count", "Transits seen", "2", "flag",
                          "Only two dips — period plausible but not firm.", 2.0)
    return Diagnostic("count", "Transits seen", f"{n}", "flag",
                      "A single dip — not enough to confirm a period.", float(n))


# --- Feature vector ---------------------------------------------------------
def build_features(det: DetectionResult, stellar: StellarParams, implied_radius: Optional[float]) -> dict:
    period = det.period_days or 0.0
    dur_h = det.duration_hours or 0.0
    depth_ppm = det.depth_ppm or 0.0
    snr = det.snr or det.sde or 0.0
    srad = stellar.radius_rsun or _SOLAR["srad"]
    steff = stellar.teff or _SOLAR["steff"]
    slogg = stellar.logg or _SOLAR["slogg"]
    prad = implied_radius if implied_radius is not None else (srad * np.sqrt(max(det.depth or 0, 0)) * RSUN_IN_REARTH)
    return {
        "period": period,
        "duration_hours": dur_h,
        "depth_ppm": depth_ppm,
        "snr": snr,
        "implied_radius_rearth": prad,
        "srad": srad,
        "steff": steff,
        "slogg": slogg,
        "duration_over_period": (dur_h / 24.0) / period if period else 0.0,
        "depth_snr": depth_ppm * snr,
    }


# --- Classifier -------------------------------------------------------------
_model_cache = {"loaded": False, "bundle": None}


def _load_model():
    """Return the loaded joblib object (a {'model','classes'} dict), or None."""
    if _model_cache["loaded"]:
        return _model_cache["bundle"]
    _model_cache["loaded"] = True
    try:
        import joblib

        if config.MODEL_PATH.exists():
            _model_cache["bundle"] = joblib.load(config.MODEL_PATH)
    except Exception:  # noqa: BLE001
        _model_cache["bundle"] = None
    return _model_cache["bundle"]


def get_model():
    """The underlying estimator, unwrapping the saved bundle if present."""
    b = _load_model()
    if b is None:
        return None
    return b["model"] if isinstance(b, dict) else b


def get_model_classes() -> list:
    """Class names aligned with predict_proba columns."""
    b = _load_model()
    if isinstance(b, dict) and "classes" in b:
        return list(b["classes"])
    m = get_model()
    return list(getattr(m, "classes_", CLASSES)) if m is not None else CLASSES


def model_loaded() -> bool:
    return get_model() is not None


def _heuristic_probs(diags: dict, feats: dict) -> dict:
    """Physics-based baseline used when no trained model is present."""
    oe = diags["odd_even"].score
    sec = diags["secondary"].score
    flat = diags["shape"].score
    sde = feats["snr"]
    prad = feats["implied_radius_rearth"]

    eb = 0.0
    eb += np.clip((oe - config.ODD_EVEN_SIGMA_FLAG) / 3.0, 0, 1) * 3.0
    eb += np.clip((sec - config.SECONDARY_SIGNIFICANCE_FLAG) / 3.0, 0, 1) * 3.0
    eb += np.clip((prad - config.RADIUS_REARTH_STELLAR) / 10.0, 0, 1) * 3.0
    eb += np.clip((0.6 - flat) / 0.4, 0, 1) * 0.8
    var = np.clip((10.0 - sde) / 10.0, 0, 1) * 2.0

    logit_planet = 2.2
    logit_eb = -2.0 + eb
    logit_var = -2.0 + var
    z = np.array([logit_planet, logit_eb, logit_var])
    z = np.exp(z - z.max())
    p = z / z.sum()
    return {CLASSES[i]: float(p[i]) for i in range(3)}


def _model_probs(feats: dict) -> Optional[dict]:
    model = get_model()
    if model is None:
        return None
    try:
        x = np.array([[feats[f] for f in MODEL_FEATURES]], dtype=float)
        proba = model.predict_proba(x)[0]
        classes = get_model_classes()
        # Map model's class labels onto our canonical names if needed.
        out = {c: 0.0 for c in CLASSES}
        for cls, pr in zip(classes, proba):
            name = str(cls)
            if name in out:
                out[name] = float(pr)
            elif name.startswith("planet"):
                out["planet_candidate"] = float(pr)
            elif "binary" in name or name == "eb":
                out["eclipsing_binary"] = float(pr)
            else:
                out["variable_or_other"] = float(pr)
        return out
    except Exception:  # noqa: BLE001
        return None


# --- Orchestration ----------------------------------------------------------
def vet(pre: Preprocessed, det: DetectionResult, stellar: StellarParams) -> VetResult:
    if not det.found:
        return VetResult(
            verdict="no_significant_signal",
            confidence=1.0 - float(np.clip((det.sde or 0) / config.SDE_THRESHOLD, 0, 0.9)),
            probabilities={c: 0.0 for c in CLASSES},
            implied_radius_rearth=None,
            diagnostics=[_diag_snr(det), _diag_count(det)],
            features={},
        )

    d_oe = _diag_odd_even(pre, det)
    d_sec = _diag_secondary(pre, det)
    d_shape = _diag_shape(pre, det)
    d_rad, implied_radius = _diag_radius(det, stellar)
    d_snr = _diag_snr(det)
    d_cnt = _diag_count(det)
    diags = {"odd_even": d_oe, "secondary": d_sec, "shape": d_shape,
             "radius": d_rad, "snr": d_snr, "count": d_cnt}

    feats = build_features(det, stellar, implied_radius)

    probs = _model_probs(feats)
    used_model = probs is not None
    if probs is None:
        probs = _heuristic_probs(diags, feats)

    # --- Physics reconciliation: the DIRECT eclipsing-binary signatures
    #     (secondary eclipse, odd-even depth, implied radius) arbitrate the
    #     planet-vs-EB question and override the catalog-trained model when they
    #     conflict — in BOTH directions (AGENTS.md §7.5). ---
    override_note = None
    hard_eb = d_sec.verdict == "fail" or d_oe.verdict == "fail" or d_rad.verdict == "fail"
    if hard_eb:
        # (1) Strong physical EB evidence -> force eclipsing binary.
        capped = min(probs["planet_candidate"], 0.10)
        freed = probs["planet_candidate"] - capped
        probs["planet_candidate"] = capped
        probs["eclipsing_binary"] = min(1.0, probs["eclipsing_binary"] + freed + 0.5)
        override_note = "physics_override_eb"
    elif probs["eclipsing_binary"] >= max(probs["planet_candidate"], probs["variable_or_other"]):
        # (2) The model leans eclipsing binary but NO fail-level EB signature is
        # present (no secondary, agreeing odd-even depths, planetary radius). An
        # eclipsing binary with no binary signature is unsupported, so suppress
        # the EB mass and hand it to the physical alternatives (mostly planet).
        eb = probs["eclipsing_binary"]
        probs["eclipsing_binary"] = eb * 0.10
        probs["planet_candidate"] += eb * 0.75
        probs["variable_or_other"] += eb * 0.15
        override_note = "physics_override_no_eb_signature"

    # Renormalize.
    tot = sum(probs.values()) or 1.0
    probs = {k: v / tot for k, v in probs.items()}

    top = max(probs, key=probs.get)

    # Physics-primary verdict: a strong, clean, flat-bottomed transit with no EB
    # signature is a planet candidate even when the catalog-trained model is
    # spread (the model is a prior; the direct diagnostics are the evidence).
    physics_clean_strong = (
        d_snr.verdict == "pass"
        and d_sec.verdict == "pass"
        and d_oe.verdict != "fail"
        and d_shape.verdict in ("pass", "flag")
        and d_rad.verdict != "fail"
    )

    if hard_eb:
        verdict, conf = "likely_eclipsing_binary", probs["eclipsing_binary"]
    elif top == "planet_candidate":
        verdict, conf = "planet_candidate", probs["planet_candidate"]
    elif top == "variable_or_other" and physics_clean_strong:
        # Model leans "variability" but we detected a clean, strong transit.
        verdict, conf = "planet_candidate", max(probs["planet_candidate"], 0.6)
    elif top == "variable_or_other":
        verdict, conf = "stellar_variability", probs["variable_or_other"]
    else:  # eclipsing_binary on top without a hard fail (rare after reconciliation)
        verdict, conf = "likely_eclipsing_binary", probs["eclipsing_binary"]

    # Low-confidence only for genuinely marginal signals (weak, ambiguous).
    if verdict == "planet_candidate" and not physics_clean_strong and conf < 0.5:
        verdict, conf = "low_confidence", conf

    order = ["odd_even", "secondary", "shape", "radius", "snr", "count"]
    return VetResult(
        verdict=verdict,
        confidence=float(conf),
        probabilities=probs,
        implied_radius_rearth=implied_radius,
        diagnostics=[diags[k] for k in order],
        features={**feats, "_used_model": used_model, "_override": override_note},
    )
