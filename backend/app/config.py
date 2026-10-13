"""Runtime configuration and tunable constants for ExoSeer.

Everything is environment-driven so the app runs with zero setup (all defaults
are demo-safe) and can be tuned in deployment without code changes. The app MUST
be fully functional with EXOSEER_LLM_PROVIDER=none (the default).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_NAME = "ExoSeer"

# --- Paths -----------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.getenv("EXOSEER_CACHE_DIR", str(BACKEND_DIR / "cache")))
MODELS_DIR = BACKEND_DIR / "models"
DATA_DIR = BACKEND_DIR / "data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "vetting_xgb.joblib"

# --- CORS ------------------------------------------------------------------
# Comma-separated list; "*" allows all (fine for a public demo backend).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]

# --- Optional LLM narrative enhancement ------------------------------------
# none | groq | gemini | hf | anthropic  (default none -> deterministic text)
LLM_PROVIDER = os.getenv("EXOSEER_LLM_PROVIDER", "none").lower()
LLM_KEY = os.getenv("EXOSEER_LLM_KEY", "")
LLM_MODEL = os.getenv("EXOSEER_LLM_MODEL", "")

# --- Pipeline tunables (see AGENTS.md §7) ----------------------------------
SDE_THRESHOLD = float(os.getenv("EXOSEER_SDE_THRESHOLD", "7.0"))
PERIOD_MIN_DAYS = float(os.getenv("EXOSEER_PERIOD_MIN", "0.5"))
PERIOD_MAX_DAYS = float(os.getenv("EXOSEER_PERIOD_MAX", "50.0"))
TLS_OVERSAMPLING = int(os.getenv("EXOSEER_TLS_OVERSAMPLING", "2"))
# TLS cost scales with baseline (period-grid density). Cap the baseline used for
# the SEARCH to keep the demo fast; the full curve is still used for display,
# depth, transit-count and vetting. ~90 d gives many transits for gallery planets.
SEARCH_BASELINE_DAYS = float(os.getenv("EXOSEER_SEARCH_BASELINE_DAYS", "90.0"))

# Physical vetting thresholds. FLAG raises a caution (non-overriding); FAIL is a
# strong violation that hard-overrides the ML to an eclipsing-binary verdict.
# FAIL bars are deliberately conservative: real planets often show 3-4 sigma
# odd-even / secondary scatter from red noise, so only a clear signal flips it.
ODD_EVEN_SIGMA_FLAG = 3.0
ODD_EVEN_SIGMA_FAIL = 5.0
SECONDARY_SIGNIFICANCE_FLAG = 3.0
SECONDARY_SIGNIFICANCE_FAIL = 5.0
RADIUS_REARTH_STELLAR = 25.0        # implied radius above this -> likely stellar companion

# Job lifecycle.
JOB_TTL_SECONDS = int(os.getenv("EXOSEER_JOB_TTL", str(60 * 60)))  # 1 hour

# Reproducibility: same input -> same output.
RANDOM_SEED = 42
