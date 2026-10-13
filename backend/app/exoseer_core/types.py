"""Internal dataclasses and typed exceptions for the ExoSeer engine.

These mirror the API schemas (app/schemas.py) but carry numpy arrays and stay
free of any web/pydantic dependency so the engine can be unit-tested and reused
in notebooks. Conversion to the wire format happens in the routes layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

# --- Typed exceptions (AGENTS.md §11) --------------------------------------


class EngineError(Exception):
    """Base class; carries a user-friendly message safe to surface to the client."""


class IngestError(EngineError):
    """Could not obtain a usable light curve (MAST miss/timeout, bad CSV, ...)."""


class DetectionError(EngineError):
    """Transit search failed unexpectedly."""


class StellarLookupError(EngineError):
    """Stellar parameters unavailable — non-fatal; caller should degrade."""


# Progress callback: on_progress(stage, pct 0..1)
ProgressFn = Callable[[str, float], None]


def noop_progress(stage: str, pct: float) -> None:  # pragma: no cover
    pass


# --- Data containers -------------------------------------------------------


@dataclass
class LightCurve:
    """A raw or normalized light curve: parallel time/flux arrays in days."""

    time: np.ndarray
    flux: np.ndarray
    flux_err: Optional[np.ndarray] = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.time = np.asarray(self.time, dtype=float)
        self.flux = np.asarray(self.flux, dtype=float)
        if self.flux_err is not None:
            self.flux_err = np.asarray(self.flux_err, dtype=float)

    @property
    def n(self) -> int:
        return int(self.time.size)


@dataclass
class Preprocessed:
    """Output of preprocess: variability-visible and detrended flux on one time base."""

    time: np.ndarray
    flux_norm: np.ndarray   # normalized to median 1.0, variability visible
    flux_flat: np.ndarray   # detrended (Savitzky-Golay), transits preserved
    cadence_days: float
    baseline_days: float
    meta: dict = field(default_factory=dict)


@dataclass
class StellarParams:
    """Host-star parameters; any field may be None (degrade gracefully)."""

    radius_rsun: Optional[float] = None
    teff: Optional[float] = None
    logg: Optional[float] = None
    mass_msun: Optional[float] = None
    source: str = "unknown"


@dataclass
class DetectionResult:
    found: bool
    period_days: Optional[float] = None
    t0: Optional[float] = None
    duration_hours: Optional[float] = None
    depth: Optional[float] = None            # fractional (not ppm)
    depth_ppm: Optional[float] = None
    sde: Optional[float] = None
    fap: Optional[float] = None
    snr: Optional[float] = None
    n_transits: Optional[int] = None
    rp_rs: Optional[float] = None
    odd_even_mismatch: Optional[float] = None   # in sigma, if provided by TLS
    bls_period_days: Optional[float] = None
    period_ambiguous: bool = False
    transit_times: list[float] = field(default_factory=list)
    method: str = "tls"
    # folded model for overlay (phase-sorted), filled by fold.py
    model_phase: Optional[np.ndarray] = None
    model_flux: Optional[np.ndarray] = None


@dataclass
class FoldResult:
    phase: np.ndarray
    flux: np.ndarray
    phase_binned: np.ndarray
    flux_binned: np.ndarray
    model_phase: np.ndarray
    model_flux: np.ndarray


@dataclass
class Diagnostic:
    key: str
    label: str
    value: str
    verdict: str      # pass | flag | fail
    reason: str
    score: float = 0.0  # numeric magnitude for the classifier/feature vector


@dataclass
class VetResult:
    verdict: str
    confidence: float
    probabilities: dict
    implied_radius_rearth: Optional[float]
    diagnostics: list[Diagnostic]
    features: dict = field(default_factory=dict)   # raw feature vector for explain/SHAP


@dataclass
class PlanetParams:
    radius_rearth: float = 2.0
    period_days: float = 7.3
    impact: float = 0.2
    t0: float = 1.0


@dataclass
class NoiseParams:
    level: float = 0.5   # 0 easy .. 1 hard
