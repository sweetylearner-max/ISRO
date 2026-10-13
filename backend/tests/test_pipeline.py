"""End-to-end pipeline tests (AGENTS.md §12). The synthetic case always runs;
the real Kepler-10 case runs only if MAST/cache is reachable (kept off the
critical path so CI never depends on the network)."""
from __future__ import annotations

import os

import pytest

from app.exoseer_core import ingest, run_pipeline
from app.exoseer_core.types import IngestError, StellarParams
from tests.fixtures import synthetic_planet

SOLAR = StellarParams(radius_rsun=1.0, teff=5700, logg=4.4, mass_msun=1.0, source="test")
OPTS = {"sde_threshold": 7.0, "period_min": 0.5, "period_max": 20.0}


def test_synthetic_planet_detected_and_vetted():
    lc = synthetic_planet(period=5.3)
    r = run_pipeline(lc, "SynPlanet", "synthetic", OPTS, stellar=SOLAR)
    assert r["detection"]["found"] is True
    assert r["detection"]["period_days"] == pytest.approx(5.3, rel=0.02)
    assert r["vetting"]["verdict"] == "planet_candidate"
    assert r["vetting"]["confidence"] > 0.5
    assert r["explanation"]["narrative"]


@pytest.mark.skipif(os.getenv("EXOSEER_SKIP_MAST") == "1", reason="MAST disabled")
def test_real_kepler10_if_available():
    """Kepler-10 b: a tiny rocky world, period ~0.837 d. Skips if MAST unreachable."""
    try:
        lc = ingest.from_mast("Kepler-10", "Kepler")
    except IngestError:
        pytest.skip("MAST unavailable / not cached")
    r = run_pipeline(lc, "Kepler-10", "Kepler", {"sde_threshold": 7, "period_min": 0.5, "period_max": 5})
    assert r["detection"]["found"] is True
    assert r["detection"]["period_days"] == pytest.approx(0.837, rel=0.05)
    assert r["vetting"]["verdict"] == "planet_candidate"
