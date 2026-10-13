"""ExoSeer engine — pure-Python exoplanet transit detection & vetting.

Zero web dependencies: importable in notebooks, unit tests, and the FastAPI
backend alike. Pipeline: ingest -> preprocess -> detect (TLS/BLS) -> fold ->
vet -> explain.
"""
from __future__ import annotations

from . import (
    catalog,
    detect,
    explain,
    fold,
    ingest,
    inject,
    pipeline,
    preprocess,
    stellar,
    transitmodel,
    vet,
)
from .pipeline import run_pipeline
from .types import (
    DetectionError,
    EngineError,
    IngestError,
    LightCurve,
    NoiseParams,
    PlanetParams,
    StellarLookupError,
    StellarParams,
)

__all__ = [
    "catalog", "detect", "explain", "fold", "ingest", "inject", "pipeline",
    "preprocess", "stellar", "transitmodel", "vet", "run_pipeline",
    "LightCurve", "PlanetParams", "NoiseParams", "StellarParams",
    "EngineError", "IngestError", "DetectionError", "StellarLookupError",
]
