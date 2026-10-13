"""Deterministic synthetic fixtures so tests never depend on live MAST."""
from __future__ import annotations

import numpy as np

from app.exoseer_core.types import LightCurve

_CADENCE = 0.0204  # Kepler long cadence (days)


def synthetic_planet(period=5.3, depth=0.0018, dur_frac=0.03, baseline=70.0, seed=1) -> LightCurve:
    """A clean transiting planet: shallow, flat-bottomed, no secondary, even depths."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, baseline, _CADENCE)
    flux = 1.0 + rng.normal(0, 1.2e-4, t.size)
    t0 = 1.3
    phase = ((t - t0 + 0.5 * period) % period) - 0.5 * period
    half = 0.5 * dur_frac * period
    intr = np.abs(phase) < half
    # smooth-ish (rounded) bottom
    flux[intr] -= depth * (1 - (phase[intr] / half) ** 2) ** 0.25
    return LightCurve(time=t, flux=flux, meta={"target": "SynPlanet", "mission": "synthetic"})


def synthetic_eclipsing_binary(period=3.9, baseline=60.0, seed=2) -> LightCurve:
    """Deep primary + secondary eclipse + odd/even depth mismatch -> EB signature."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, baseline, _CADENCE)
    flux = 1.0 + rng.normal(0, 3e-4, t.size)
    t0 = 1.0
    phase = ((t - t0 + 0.5 * period) % period) - 0.5 * period
    phase01 = ((t - t0) % period) / period
    epoch = np.round((t - t0) / period).astype(int)
    prim = np.abs(phase) < 0.06
    flux[prim & (epoch % 2 == 0)] -= 0.020   # deep even primaries
    flux[prim & (epoch % 2 == 1)] -= 0.013   # shallow odd primaries (odd-even mismatch)
    sec = np.abs(phase01 - 0.5) < 0.05
    flux[sec] -= 0.009                        # secondary eclipse
    return LightCurve(time=t, flux=flux, meta={"target": "SynEB", "mission": "synthetic"})
