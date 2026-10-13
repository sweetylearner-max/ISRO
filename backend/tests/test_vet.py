"""Vetting tests (AGENTS.md §12): a known eclipsing-binary signature must be
flagged and rejected, and physics must override a planet-leaning model."""
from __future__ import annotations

from app.exoseer_core import run_pipeline
from app.exoseer_core.types import StellarParams
from tests.fixtures import synthetic_eclipsing_binary, synthetic_planet

SOLAR = StellarParams(radius_rsun=1.0, teff=5700, logg=4.4, mass_msun=1.0, source="test")
OPTS = {"sde_threshold": 7.0, "period_min": 0.5, "period_max": 10.0}


def test_eclipsing_binary_rejected():
    lc = synthetic_eclipsing_binary()
    r = run_pipeline(lc, "SynEB", "synthetic", OPTS, stellar=SOLAR)
    v = r["vetting"]
    assert v["verdict"] == "likely_eclipsing_binary"
    # At least one hard diagnostic (odd-even or secondary) must fail.
    fails = {d["key"]: d for d in v["diagnostics"] if d["verdict"] == "fail"}
    assert "odd_even" in fails or "secondary" in fails


def test_planet_passes_diagnostics():
    lc = synthetic_planet(period=6.1, depth=0.0025)
    r = run_pipeline(lc, "SynPlanet", "synthetic", OPTS, stellar=SOLAR)
    v = r["vetting"]
    assert v["verdict"] == "planet_candidate"
    # No hard failures on a clean planet.
    assert all(d["verdict"] != "fail" for d in v["diagnostics"])


def test_giant_radius_flags_stellar_companion():
    # Very deep transit around a Sun-like star -> implied radius >> planetary.
    lc = synthetic_planet(period=4.0, depth=0.09, dur_frac=0.04)
    r = run_pipeline(lc, "SynGiant", "synthetic", OPTS, stellar=SOLAR)
    radius_diag = next(d for d in r["vetting"]["diagnostics"] if d["key"] == "radius")
    assert radius_diag["verdict"] in ("flag", "fail")
