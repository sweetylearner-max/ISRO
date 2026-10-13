"""ExoSeer FastAPI application: CORS, routers, warning hygiene.

Endpoints (AGENTS.md §8): POST /analyze, GET /jobs/{id}, POST /inject,
GET /catalog, GET /healthz. Swagger UI at /docs.
"""
from __future__ import annotations

import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routes import analyze, catalog, health, inject

# Astro libraries are chatty; keep server logs clean without hiding real errors.
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

app = FastAPI(
    title=f"{config.APP_NAME} API",
    description="Explainable exoplanet transit detection & vetting on free NASA data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS if "*" not in config.CORS_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(inject.router)
app.include_router(catalog.router)


@app.get("/", tags=["health"])
def root() -> dict:
    return {"name": config.APP_NAME, "docs": "/docs", "health": "/healthz"}
