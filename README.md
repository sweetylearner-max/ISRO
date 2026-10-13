# ✦ ExoSeer — See worlds hidden in starlight

**An explainable AI that detects exoplanets in real NASA light curves — and tells you why.**

ExoSeer takes any star observed by Kepler / K2 / TESS (or your own uploaded light
curve), finds the faint periodic dimming of a transiting planet, and then does the
hard part: it **vets** the signal — deciding whether it is a *planet*, a pair of
*eclipsing stars*, *stellar variability*, or *noise* — and explains its verdict in
plain language a human can check.

> Built for the **Bharatiya Antariksh Hackathon (BAH) 2026**, ISRO — Problem
> Statement #7, *"AI-enabled Detection of Exoplanets from Noisy Astronomical Light
> Curves."* 100% free tooling and open NASA data.

ExoSeer surfaces **candidates**, not confirmed discoveries. See *Scientific honesty* below.

---

## Why it's different

Most approaches stop at "detect a dip." ExoSeer goes further and performs
**astrophysical vetting with explanations** — the part the problem statement calls
the hard, unsolved bit:

- **Detect** — Transit Least Squares (primary) cross-checked with Box Least Squares.
- **Vet** — odd–even depth, secondary eclipse, transit shape, implied radius,
  signal strength, transit count → a trained XGBoost classifier, with **physics
  overriding the model in both directions** when they conflict.
- **Explain** — a deterministic plain-English narrative + SHAP feature importance
  (optional LLM enhancement, off by default).
- **Stress-test** — an injection–recovery sandbox: plant a synthetic planet and
  shrink it until ExoSeer loses it in the noise — the detection limit, felt in the hand.

---

## Architecture

```
Frontend (Next.js 16 · React 19 · Tailwind v4 · Plotly · Framer Motion)
   │  REST (JSON), async job + poll
Backend  (FastAPI · Pydantic v2 · uvicorn)
   │  /analyze · /jobs/{id} · /inject · /catalog · /healthz
Engine   (pure-Python package `exoseer_core`, zero web deps)
   │  ingest → preprocess → detect (TLS/BLS) → fold → vet → explain
Data     NASA MAST (via lightkurve) · NASA Exoplanet Archive KOI table · TIC/Gaia
```

The engine is a plain Python library (no FastAPI imports) so it is unit-tested,
reusable in notebooks, and swappable. The frontend never talks to MAST directly.

---

## Quickstart

### Backend (Python 3.11)

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000          # Swagger UI at http://localhost:8000/docs
```

> The heavy scientific stack (`transitleastsquares`, `numba`, `batman-package`,
> `lightkurve`) targets **Python 3.11**. On macOS, `xgboost` needs OpenMP:
> `brew install libomp`.

### Frontend (Node 20+)

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm run dev                                          # http://localhost:3000
```

### One command (Docker)

```bash
docker compose up --build      # backend on :8000, frontend on :3000
```

### Pre-warm the demo cache

MAST downloads are cached on disk. Before a live demo, warm the gallery stars:

```bash
make warm       # POSTs /analyze for every gallery system (respects BACKEND_URL)
```

---

## The app

- **Landing** (`/`) — the pitch + a live dipping light-curve. *Try a demo star →*.
- **Console** (`/console`) — search a star / upload a CSV / "surprise me"; see the
  raw + detrended light curve, the phase-folded transit with model overlay, the
  verdict, confidence, stat cards, vetting diagnostics, the explanation + SHAP, and
  a dossier export (JSON / print-to-PDF). Auto-runs a famous planet on first visit.
- **Sandbox** (`/sandbox`) — inject a synthetic planet into a quiet star and watch
  ExoSeer recover it… then shrink it until it's lost in the noise.
- **Gallery** (`/gallery`) — famous systems, including a known **eclipsing binary**
  so you can watch ExoSeer correctly reject a non-planet.
- **About** (`/about`) — how it works, the data, and — plainly — the limitations.

---

## The vetting model

Trained **offline** and vendored to `backend/models/vetting_xgb.joblib` (the app
never trains at runtime; a physics-based heuristic is used if the model is absent).

```bash
cd backend && .venv/bin/python ../ml/train_vetting_model.py
```

Downloads the NASA Exoplanet Archive **Kepler KOI cumulative** table, builds a
feature matrix matching `exoseer_core.vet.MODEL_FEATURES`, labels rows from
`koi_disposition` (+ `koi_fpflag_ss` to separate eclipsing binaries), and trains a
multiclass XGBoost model. Current metrics: **~83% test accuracy** vs a 36%
majority-class baseline; planet-vs-EB F1 ≈ 0.90. See `ml/` for the notebooks.

---

## Testing

```bash
cd backend && .venv/bin/python -m pytest tests/     # uses synthetic fixtures; no live MAST needed
```

Covers: a synthetic planet detected & vetted → `planet_candidate`; a synthetic
eclipsing binary → `likely_eclipsing_binary`; injection recovery and loss-in-noise.

---

## Deployment (free tiers)

- **Backend → Hugging Face Spaces (Docker SDK).** `backend/Dockerfile` listens on
  port **7860** (HF default); `backend/README_SPACE.md` has the Space metadata.
- **Frontend → Vercel (Hobby).** Set `NEXT_PUBLIC_API_BASE` to the Space URL; the
  backend `CORS_ORIGINS` must include your Vercel domain.

---

## Scientific honesty (non-negotiable)

ExoSeer says **"planet candidate"**, never "planet discovered." Real confirmation
needs radial-velocity follow-up and human review. Single-sector or faint-star data
is noisy; grazing geometries and blended sources can fool any automated vetter —
ExoSeer flags uncertainty rather than hiding it. Calibrated confidence beats false
certainty.

Credit: NASA and the Kepler / K2 / TESS mission teams, the
[MAST archive](https://mast.stsci.edu/), the
[NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/), and the
open-source [`lightkurve`](https://lightkurve.github.io/lightkurve/) and
[`transitleastsquares`](https://github.com/hippke/tls) communities.

---

## Repository layout

```
backend/    FastAPI app + exoseer_core engine + trained model + tests
frontend/   Next.js App Router UI (console, sandbox, gallery, about)
ml/         training script + notebooks (KOI → features → XGBoost)
brain/      the project's source-of-truth specs (AGENTS.md, App Guide, RESOURCES)
```
# ISRO
