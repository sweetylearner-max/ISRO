---
title: ExoSeer Backend
emoji: 🪐
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ExoSeer — Backend (FastAPI)

This Hugging Face Space runs the **ExoSeer** backend: an explainable AI engine that detects
and *vets* exoplanet transit signals in noisy stellar light curves, using only free, public
NASA data (Kepler / K2 / TESS via MAST).

It is a Docker Space. The container builds from `Dockerfile`, installs the Python scientific
stack (lightkurve, transitleastsquares, astropy, astroquery, xgboost, shap, …), and serves a
FastAPI app with `uvicorn` on port **7860** (declared as `app_port` above, which is where the
Space routes public traffic).

## Endpoints

- `POST /analyze` — start an analysis job for a star (MAST), an uploaded CSV, or a catalog entry.
- `GET  /jobs/{job_id}` — poll job status/progress and retrieve the result dossier.
- `POST /inject` — injection–recovery sandbox (synthetic transit into a quiet host star).
- `GET  /catalog` — famous, fast-loading systems for instant demos.
- `GET  /healthz` — liveness + engine capability report (also used by the container HEALTHCHECK).
- Interactive API docs (Swagger UI) at `/docs`.

## Configuration

All configuration is environment-driven and every value has a demo-safe default, so the Space
runs with nothing set. Common variables:

- `CORS_ORIGINS` — comma-separated allowed origins (set this to your Vercel frontend URL).
- `EXOSEER_CACHE_DIR` — on-disk light-curve cache directory (defaults to `/app/cache` in the image).
- `EXOSEER_LLM_PROVIDER` — optional narrative enhancement (`none` | `groq` | `gemini` | `hf` | `anthropic`);
  defaults to `none`, which uses the deterministic templated explanation. No key required.
- `EXOSEER_SDE_THRESHOLD` — detection gate on the TLS signal detection efficiency (default `7.0`).

The vendored trained model (`models/vetting_xgb.joblib`) and NASA reference tables (`data/`) are
baked into the image, so no large downloads happen at container boot.

## Notes

- Free Spaces sleep after extended inactivity and cold-start on the next request — hit the URL
  shortly before a demo so the container is awake and the cache is warm.
- ExoSeer surfaces **planet candidates**, not confirmed discoveries.
- Data courtesy of NASA and the MAST archive (Kepler / K2 / TESS missions).
