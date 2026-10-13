"""Explainability (AGENTS.md §7.6).

1. Deterministic narrative ($0, always on): one sentence per diagnostic, ordered
   by importance, ending with the verdict and the single strongest piece of
   evidence. Never overclaims (candidate, not discovery).
2. Feature importance: SHAP over the trained model when present; a physics-derived
   attribution otherwise — so the UI's bar always has something to show.
3. Optional LLM: if EXOSEER_LLM_PROVIDER != none, the structured dossier (numbers
   + verdicts only, never raw data) is sent to a free LLM to rewrite the prose.
   Strictly additive; any error/timeout falls back to the deterministic text.
"""
from __future__ import annotations

import json
from typing import Optional

import numpy as np

from .. import config
from .types import DetectionResult, VetResult
from .vet import CLASSES, MODEL_FEATURES, get_model

_VERDICT_LEAD = {
    "planet_candidate": "Likely planet candidate",
    "likely_eclipsing_binary": "Likely eclipsing binary",
    "stellar_variability": "Likely stellar variability",
    "low_confidence": "Low-confidence signal",
    "no_significant_signal": "No significant signal",
}


def _fmt(x: Optional[float], nd: int = 2) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def build_narrative(det: DetectionResult, vet: VetResult, star_name: str) -> str:
    lead = _VERDICT_LEAD.get(vet.verdict, "Signal")
    conf = vet.confidence

    if vet.verdict == "no_significant_signal":
        return (
            f"No significant transit was found for {star_name} "
            f"(SDE {_fmt(det.sde, 1)}, below the detection threshold of {config.SDE_THRESHOLD:g}). "
            "Try another sector/quarter, or a different star."
        )

    dmap = {d.key: d for d in vet.diagnostics}
    parts: list[str] = [f"{lead} (confidence {conf:.2f})."]

    # Evidence sentences, strongest first depending on the verdict.
    evidence: list[str] = []
    if vet.verdict == "planet_candidate":
        if "shape" in dmap and dmap["shape"].verdict == "pass":
            evidence.append("is flat-bottomed")
        if "secondary" in dmap and dmap["secondary"].verdict == "pass":
            evidence.append("shows no secondary eclipse")
        if "odd_even" in dmap and dmap["odd_even"].verdict == "pass":
            evidence.append(f"has odd and even depths agreeing to within {dmap['odd_even'].value}")
        if evidence:
            parts.append("The transit " + ", ".join(evidence) + ".")
        if "radius" in dmap and dmap["radius"].value not in ("indeterminate", "n/a"):
            parts.append(f"The implied radius of {dmap['radius'].value} is in the planetary range.")
    else:
        # Lead with the failing diagnostic(s).
        for key in ("secondary", "odd_even", "radius", "shape"):
            d = dmap.get(key)
            if d and d.verdict in ("fail", "flag"):
                parts.append(d.reason)
        if not any(dmap.get(k) and dmap[k].verdict == "fail" for k in ("secondary", "odd_even", "radius")):
            parts.append("The evidence is mixed and does not cleanly favour a planet.")

    # Measured summary line — always factual.
    n = det.n_transits or 0
    parts.append(
        f"Period {_fmt(det.period_days, 3)} d, depth {_fmt(det.depth_ppm, 0)} ppm, "
        f"SDE {_fmt(det.sde, 1)} over {n} transit{'s' if n != 1 else ''}."
    )
    if det.period_ambiguous:
        parts.append("Note: the box- and template-search periods disagree, so the period is uncertain.")

    return " ".join(parts)


def _shap_importance(feats: dict) -> list[dict]:
    """SHAP contributions for the predicted class over MODEL_FEATURES."""
    model = get_model()
    if model is None:
        return []
    try:
        import shap

        x = np.array([[feats[f] for f in MODEL_FEATURES]], dtype=float)
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(x)
        # Multiclass -> list; pick the predicted class.
        if isinstance(sv, list):
            probs = model.predict_proba(x)[0]
            arr = np.asarray(sv[int(np.argmax(probs))])[0]
        else:
            arr = np.asarray(sv)[0]
            if arr.ndim > 1:
                arr = arr[:, int(np.argmax(model.predict_proba(x)[0]))]
        pairs = sorted(zip(MODEL_FEATURES, arr), key=lambda p: abs(p[1]), reverse=True)
        return [{"feature": f, "contribution": float(c)} for f, c in pairs[:6]]
    except Exception:  # noqa: BLE001
        return []


def _physics_importance(vet: VetResult) -> list[dict]:
    """Attribution from the diagnostics when there's no trained model / SHAP fails.

    Contributions are measured relative to each test's fail threshold and signed
    so that POSITIVE = evidence toward a planet. A clean planet therefore shows
    all-positive bars; an eclipsing binary drives odd-even / secondary negative.
    """
    dmap = {d.key: d for d in vet.diagnostics}
    oe = dmap["odd_even"].score if "odd_even" in dmap else 0.0
    sec = dmap["secondary"].score if "secondary" in dmap else 0.0
    flat = dmap["shape"].score if "shape" in dmap else 0.0
    radius = dmap["radius"].score if "radius" in dmap else 0.0
    sde = dmap["snr"].score if "snr" in dmap else 0.0

    def clip(x: float) -> float:
        return float(max(-1.0, min(1.0, x)))

    signed = {
        "odd_even_sigma": clip((config.ODD_EVEN_SIGMA_FAIL - oe) / config.ODD_EVEN_SIGMA_FAIL),
        "secondary_significance": clip(
            (config.SECONDARY_SIGNIFICANCE_FAIL - sec) / config.SECONDARY_SIGNIFICANCE_FAIL
        ),
        "shape_flatness": clip((flat - 0.5) / 0.5),
        "implied_radius": clip((config.RADIUS_REARTH_STELLAR - radius) / config.RADIUS_REARTH_STELLAR)
        if radius > 0
        else 0.0,
        "signal_strength": clip((sde - config.SDE_THRESHOLD) / 20.0),
    }
    pairs = sorted(signed.items(), key=lambda p: abs(p[1]), reverse=True)
    return [{"feature": f, "contribution": v} for f, v in pairs]


def _llm_rewrite(narrative: str, dossier: dict) -> Optional[str]:
    """Send the structured dossier (numbers only) to a free LLM; None on any failure."""
    provider = config.LLM_PROVIDER
    if provider == "none" or not config.LLM_KEY:
        return None
    prompt = (
        "You are an astronomer. Rewrite the following exoplanet vetting summary as "
        "2-4 fluent, precise sentences for a curious non-expert. Do NOT invent numbers "
        "or claim a confirmed discovery; say 'candidate'. Structured dossier:\n"
        + json.dumps(dossier)
        + f"\n\nBaseline text: {narrative}"
    )
    try:
        import urllib.request

        if provider == "anthropic":
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": config.LLM_MODEL or "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode(),
                headers={
                    "content-type": "application/json",
                    "x-api-key": config.LLM_KEY,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())
            return data["content"][0]["text"].strip()

        if provider == "groq":
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps({
                    "model": config.LLM_MODEL or "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                }).encode(),
                headers={"content-type": "application/json", "authorization": f"Bearer {config.LLM_KEY}"},
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())
            return data["choices"][0]["message"]["content"].strip()

        if provider == "gemini":
            model = config.LLM_MODEL or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={config.LLM_KEY}"
            req = urllib.request.Request(
                url,
                data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
                headers={"content-type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:  # noqa: BLE001 - additive only; never break the dossier
        return None
    return None


def explain(det: DetectionResult, vet: VetResult, star_name: str) -> tuple[str, list[dict], bool]:
    narrative = build_narrative(det, vet, star_name)

    importance = _shap_importance(vet.features) if vet.features else []
    if not importance:
        importance = _physics_importance(vet)

    llm_used = False
    dossier = {
        "verdict": vet.verdict,
        "confidence": round(vet.confidence, 3),
        "period_days": det.period_days,
        "depth_ppm": det.depth_ppm,
        "sde": det.sde,
        "n_transits": det.n_transits,
        "implied_radius_rearth": vet.implied_radius_rearth,
        "diagnostics": [{d.key: d.verdict} for d in vet.diagnostics],
    }
    enhanced = _llm_rewrite(narrative, dossier)
    if enhanced:
        narrative = enhanced
        llm_used = True

    return narrative, importance, llm_used
