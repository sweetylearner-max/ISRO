"""Injection-recovery tests (AGENTS.md §12): a 2 R-earth / 7 d planet at low
noise must be recovered; shrinking it into the noise must lose it."""
from __future__ import annotations

from app.exoseer_core import inject, run_pipeline
from app.exoseer_core.types import NoiseParams, PlanetParams, StellarParams

SOLAR = StellarParams(radius_rsun=1.0, teff=5700, logg=4.4, mass_msun=1.0, source="test")


def _run(radius, period, noise):
    planet = PlanetParams(radius_rearth=radius, period_days=period, impact=0.2)
    lc = inject.make_synthetic_lightcurve(
        "SynHost", planet, NoiseParams(level=noise), stellar=SOLAR, prefer_real=False
    )
    opts = {"sde_threshold": 7.0, "period_min": 0.5, "period_max": max(2 * period, 10)}
    r = run_pipeline(lc, "SynHost", "synthetic", opts, stellar=SOLAR)
    recovered, _, _ = inject.evaluate_recovery(lc.meta["injected"], _Det(r["detection"]), 7.0)
    return recovered, r["detection"]


class _Det:
    """Adapt the detection dict to the attribute access evaluate_recovery expects."""

    def __init__(self, d):
        self.period_days = d["period_days"]
        self.depth_ppm = d["depth_ppm"]
        self.duration_hours = d["duration_hours"]
        self.sde = d["sde"]
        self.found = d["found"]


def test_recovers_clear_planet():
    recovered, det = _run(radius=2.5, period=7.3, noise=0.15)
    assert recovered is True
    assert det["period_days"] is not None


def test_loses_tiny_planet_in_high_noise():
    # A tiny planet buried in hard noise should fall below the detection limit.
    recovered, _ = _run(radius=0.6, period=7.3, noise=1.0)
    assert recovered is False
