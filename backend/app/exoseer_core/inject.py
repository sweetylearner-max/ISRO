"""Injection–recovery sandbox (AGENTS.md §7.7).

Generate a batman transit for user-chosen parameters, multiply it into a quiet
host star's real flux (falling back to a synthesized quiet star if MAST is
unreachable), optionally add white + red noise scaled by a difficulty slider,
then let the full pipeline try to recover it. Deterministic given a seed.
"""
from __future__ import annotations

import numpy as np

from .. import config
from . import transitmodel
from .types import (
    DetectionResult,
    LightCurve,
    NoiseParams,
    PlanetParams,
    ProgressFn,
    StellarParams,
    noop_progress,
)

_KEPLER_LONG_CADENCE = 0.020434  # days (~29.4 min)


def _synthesize_quiet_star(period_days: float, seed: int = config.RANDOM_SEED) -> tuple[np.ndarray, np.ndarray]:
    """Flat, low-noise baseline spanning enough orbits to see ~12+ transits."""
    rng = np.random.default_rng(seed)
    baseline = max(35.0, period_days * 14.0)
    time = np.arange(0.0, baseline, _KEPLER_LONG_CADENCE)
    flux = 1.0 + rng.normal(0.0, 5e-5, size=time.size)
    return time, flux


def _load_quiet_host(
    host: str, period_days: float, on_progress: ProgressFn, prefer_real: bool = True
) -> tuple[np.ndarray, np.ndarray, str]:
    """Prefer a real, quiet host's detrended flux; fall back to synthesis offline."""
    if not prefer_real or not host:
        t, f = _synthesize_quiet_star(period_days)
        return t, f, "synthetic"
    try:
        from . import ingest, preprocess

        lc = ingest.from_mast(host, on_progress=lambda s, p: on_progress("fetching", 0.3 * p))
        pre = preprocess.preprocess(lc, on_progress=lambda s, p: None)
        # Use the detrended flux as the quiet baseline (median ~1).
        return pre.time, pre.flux_flat, "real"
    except Exception:  # noqa: BLE001 - offline / miss -> synthesize
        t, f = _synthesize_quiet_star(period_days)
        return t, f, "synthetic"


def make_synthetic_lightcurve(
    host: str,
    planet: PlanetParams,
    noise: NoiseParams,
    stellar: StellarParams | None = None,
    on_progress: ProgressFn = noop_progress,
    prefer_real: bool = True,
) -> LightCurve:
    on_progress("fetching", 0.1)
    stellar = stellar or StellarParams(radius_rsun=1.0, mass_msun=1.0, teff=5700, source="assumed_solar")
    base_time, base_flux, host_kind = _load_quiet_host(
        host, planet.period_days, on_progress, prefer_real=prefer_real
    )

    rng = np.random.default_rng(config.RANDOM_SEED)

    rp_rs = transitmodel.rp_rs_from_radii(planet.radius_rearth, stellar.radius_rsun)
    a_rs = transitmodel.a_over_rstar(planet.period_days, stellar.mass_msun, stellar.radius_rsun)
    inc = transitmodel.inclination_deg(a_rs, planet.impact)

    # Place first transit a little into the baseline for context.
    span = base_time.max() - base_time.min()
    t0 = base_time.min() + 0.15 * span

    transit = transitmodel.transit_flux(
        base_time, t0=t0, period_days=planet.period_days, rp_rs=rp_rs, a_rs=a_rs, inc_deg=inc
    )
    flux = base_flux * transit

    # Difficulty: white noise grows with the slider; add mild red (sinusoidal) noise.
    level = float(np.clip(noise.level, 0.0, 1.0))
    white_sigma = 5e-5 + level * 1.5e-3
    flux = flux + rng.normal(0.0, white_sigma, size=flux.size)
    if level > 0:
        red_amp = level * 8e-4
        red_period = 3.3 + 5.0 * rng.random()
        flux = flux + red_amp * np.sin(2 * np.pi * base_time / red_period)

    on_progress("fetching", 1.0)
    return LightCurve(
        time=base_time,
        flux=flux,
        meta={
            "target": f"Injected into {host}",
            "mission": "synthetic",
            "host_kind": host_kind,
            "injected": {
                "radius_rearth": planet.radius_rearth,
                "period_days": planet.period_days,
                "impact": planet.impact,
                "t0": t0,
                "rp_rs": rp_rs,
                "depth_ppm": rp_rs ** 2 * 1e6,
            },
            "stellar": {"radius_rsun": stellar.radius_rsun, "mass_msun": stellar.mass_msun},
        },
    )


def evaluate_recovery(
    injected: dict,
    det: DetectionResult,
    sde_threshold: float,
    period_tol: float = 0.02,
) -> tuple[bool, dict, dict]:
    """Compare injected vs recovered; recovered iff SDE>=thr AND period within tol (or a 2x/0.5x alias)."""
    inj_period = injected.get("period_days", 0.0)
    rec_period = det.period_days or 0.0
    period_ok = False
    if inj_period > 0 and rec_period > 0:
        for ratio in (1.0, 2.0, 0.5):
            if abs(rec_period / inj_period - ratio) < period_tol:
                period_ok = True
                break
    recovered = bool(det.found and (det.sde or 0) >= sde_threshold and period_ok)

    recovered_dict = {
        "period_days": det.period_days,
        "depth_ppm": det.depth_ppm,
        "duration_hours": det.duration_hours,
        "sde": det.sde,
        "radius_rearth": None,  # filled by the route after implied-radius calc
    }
    injected_dict = {
        "radius_rearth": injected.get("radius_rearth"),
        "period_days": injected.get("period_days"),
        "impact": injected.get("impact"),
        "depth_ppm": injected.get("depth_ppm"),
    }
    return recovered, recovered_dict, injected_dict
