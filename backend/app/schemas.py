"""Pydantic v2 request/response models — the FROZEN API contract (AGENTS.md §8).

The frontend's zod schemas mirror these exactly. Do not rename fields without
updating frontend/lib/api.ts in lockstep.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# --- Requests --------------------------------------------------------------

Source = Literal["mast", "upload", "catalog"]
Mission = Literal["Kepler", "TESS", "K2"]


class AnalyzeOptions(BaseModel):
    sde_threshold: float = 7.0
    period_max: float = 50.0
    period_min: float = 0.5


class AnalyzeRequest(BaseModel):
    source: Source = "mast"
    target: Optional[str] = None          # for mast / catalog
    mission: Optional[Mission] = None
    sector_or_quarter: Optional[int] = None
    csv_base64: Optional[str] = None      # for upload
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class InjectPlanet(BaseModel):
    radius_rearth: float = 2.0
    period_days: float = 7.3
    impact: float = 0.2


class InjectRequest(BaseModel):
    host: str = "Kepler-16"               # a quiet star from the catalog
    planet: InjectPlanet = Field(default_factory=InjectPlanet)
    noise_level: float = 0.5              # 0 (easy) .. 1 (hard)


# --- Result sub-objects ----------------------------------------------------

class StarInfo(BaseModel):
    id: str
    mission: Optional[str] = None
    teff: Optional[float] = None
    radius_rsun: Optional[float] = None
    logg: Optional[float] = None
    mass_msun: Optional[float] = None


class LightCurveData(BaseModel):
    time: list[float]
    flux_norm: list[float]     # variability visible
    flux_flat: list[float]     # detrended


class DetectionData(BaseModel):
    found: bool
    period_days: Optional[float] = None
    t0: Optional[float] = None
    duration_hours: Optional[float] = None
    depth_ppm: Optional[float] = None
    sde: Optional[float] = None
    fap: Optional[float] = None
    snr: Optional[float] = None
    n_transits: Optional[int] = None
    bls_period_days: Optional[float] = None
    period_ambiguous: bool = False


class FoldedData(BaseModel):
    phase: list[float]
    flux: list[float]
    phase_binned: list[float]
    flux_binned: list[float]
    model: list[float]
    model_phase: list[float] = Field(default_factory=list)


Verdict = Literal[
    "planet_candidate",
    "likely_eclipsing_binary",
    "stellar_variability",
    "low_confidence",
    "no_significant_signal",
]

DiagnosticVerdict = Literal["pass", "flag", "fail"]


class Diagnostic(BaseModel):
    key: str
    label: str
    value: str
    verdict: DiagnosticVerdict
    reason: str


class Probabilities(BaseModel):
    planet_candidate: float = 0.0
    eclipsing_binary: float = 0.0
    variable_or_other: float = 0.0


class VettingData(BaseModel):
    verdict: Verdict
    confidence: float
    probabilities: Probabilities
    implied_radius_rearth: Optional[float] = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class FeatureContribution(BaseModel):
    feature: str
    contribution: float


class ExplanationData(BaseModel):
    narrative: str
    feature_importance: list[FeatureContribution] = Field(default_factory=list)
    llm_used: bool = False


class InjectionData(BaseModel):
    injected: dict
    recovered: dict
    recovered_bool: bool


class AnalysisResult(BaseModel):
    star: StarInfo
    lightcurve: LightCurveData
    detection: DetectionData
    folded: Optional[FoldedData] = None
    vetting: Optional[VettingData] = None
    explanation: Optional[ExplanationData] = None
    injection: Optional[InjectionData] = None
    warnings: list[str] = Field(default_factory=list)


# --- Job envelope ----------------------------------------------------------

JobState = Literal["queued", "running", "done", "error"]
Stage = Literal[
    "queued",
    "fetching",
    "detrending",
    "searching",
    "folding",
    "vetting",
    "explaining",
    "complete",
]


class JobStatus(BaseModel):
    job_id: str
    status: JobState
    stage: Stage
    progress: float = 0.0
    error: Optional[str] = None
    result: Optional[AnalysisResult] = None


class JobCreated(BaseModel):
    job_id: str


# --- Catalog ---------------------------------------------------------------

class CatalogEntry(BaseModel):
    id: str
    mission: str
    label: str
    blurb: str
    expected_verdict: str
    kind: Literal["planet", "eclipsing_binary", "multi", "small", "quiet_host"] = "planet"


class CatalogResponse(BaseModel):
    systems: list[CatalogEntry]


class HealthResponse(BaseModel):
    ok: bool
    model_loaded: bool
    engine: dict
