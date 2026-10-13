# AGENTS.md — ExoSeer

> **Project:** ExoSeer — an explainable AI engine that finds and *vets* exoplanet transit
> signals in noisy stellar light curves, using only free, public NASA data.
> **Built for:** Bharatiya Antariksh Hackathon (BAH) 2026 — Problem Statement #7,
> "AI-enabled Detection of Exoplanets from Noisy Astronomical Light Curves."
> **Stack:** Next.js + TypeScript frontend · FastAPI + Python ML backend · 100% free tooling.
>
> *The name "ExoSeer" is a suggestion — change `APP_NAME` in one place if you prefer another.*

---

## 0. How to use this file (read first)

You are the coding agent building this project. This file is your contract.

1. Build **in the phase order** in §13. Each phase has **acceptance criteria** — do not start
   a phase until the previous one passes its criteria. Phase 1 alone must be a working demo.
2. The **scientific pipeline (§7)** is the heart of the product. Implement it exactly as
   specified; the methods are chosen because they run fast on a free CPU and are defensible to
   domain-expert judges.
3. The **API contract (§8)** is frozen — the frontend depends on these exact schemas.
4. Visual/UX decisions live in `ExoSeer_App_Guide.md` (the product spec). When this file says
   "see App Guide," obey that document for layout, copy, and design tokens.
5. Resource URLs, dataset locations, and free-tier hosting live in `RESOURCES.md`.
6. **Never overclaim.** This tool surfaces *candidates*, not confirmed discoveries. See §16.
7. Commit small, commit often. After each phase, the app must run with one command.

---

## 1. Mission, scope, and non-goals

**Mission.** Take any star observed by Kepler/K2/TESS (or a user-uploaded light curve), and:
detect periodic transit-like dips → measure the signal → **classify whether it is a planet,
an eclipsing binary, stellar variability, or noise** → explain the verdict in plain English →
let the user stress-test the engine by injecting synthetic planets.

**The differentiator (do not lose this).** Most teams stop at "detect a dip / binary classifier
on the Kaggle flux set." ExoSeer goes further: it performs **astrophysical vetting** (the part the
problem statement explicitly calls hard) and produces **explainable, physically-grounded
verdicts**. Detection is table stakes; *vetting + explainability + the injection sandbox* is why
we win.

**In scope (v1):**
- Ingest real light curves from NASA MAST by star ID/name; CSV upload; synthetic generation.
- Detrend, period-search (TLS), phase-fold.
- Vetting diagnostics + a trained classifier with a verdict and probabilities.
- Plain-English explanation (deterministic; optional LLM enhancement).
- Injection–recovery sandbox.
- A polished, fast web UI (see App Guide).
- Free deployment (frontend + backend).

**Non-goals (v1 — explicitly do not build):**
- Training large generative/diffusion models.
- Pixel-level photometry from raw images beyond what `lightkurve` gives for free.
- User accounts / auth / payments. (A no-login "recent runs" list via localStorage is fine.)
- Mobile-native apps. (The web app must be responsive; that's enough.)
- Real-time streaming from telescopes.

---

## 2. Problem statement & winning angle

> *"Develop an AI-based data analysis pipeline capable of automatically detecting exoplanet
> transit signals from noisy astronomical light curve data... brightness variations can be due
> to a transiting planet, an eclipsing stellar companion, or starspots... difficult to
> disentangle in noisy datasets in crowded fields."* — BAH 2026 PS#7

The judges' rubric rewards: novelty, technical soundness, real impact, and a working demo.
ExoSeer hits all four by reframing the task from **"detection"** to **"detection + automated
vetting with explanations"** — directly answering the "disentangle planet vs binary vs starspot"
challenge that the prompt names as the unsolved part.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js App Router, TypeScript, Tailwind)                  │
│  Landing · Discovery Console · Injection Sandbox · Gallery · About     │
│  Charts: Plotly.js (MVP) → uPlot (perf). Animations: Framer Motion.    │
└───────────────┬────────────────────────────────────────────────────────┘
                │ REST (JSON), async job + poll
┌───────────────▼────────────────────────────────────────────────────────┐
│  BACKEND  (FastAPI, Pydantic, uvicorn)                                  │
│  /analyze (job) · /jobs/{id} · /inject · /catalog · /healthz            │
│  In-memory + disk job store; on-disk light-curve cache.                 │
└───────────────┬────────────────────────────────────────────────────────┘
                │ Python function calls
┌───────────────▼────────────────────────────────────────────────────────┐
│  ENGINE  (pure-Python package `exoseer_core`)                           │
│  ingest → preprocess → detect (TLS/BLS) → fold → vet → explain          │
│  Uses: lightkurve, astropy, astroquery, transitleastsquares, batman,    │
│        numpy, scipy, scikit-learn, xgboost, shap.                       │
│  Loads a pre-trained vetting model (model.joblib) shipped in the repo.  │
└───────────────┬────────────────────────────────────────────────────────┘
                │ reads
┌───────────────▼────────────────────────────────────────────────────────┐
│  DATA  (all free)                                                       │
│  NASA MAST (live, via lightkurve) · NASA Exoplanet Archive KOI/TOI      │
│  tables (for training, vendored as CSV) · TIC/Gaia stellar params       │
└──────────────────────────────────────────────────────────────────────┘
```

**Why this split:** the engine is a plain Python library with zero web dependencies, so it can be
unit-tested, run in the training notebook, and reused. The backend is a thin async wrapper. The
frontend never talks to MAST directly.

---

## 4. Tech stack (all free)

**Backend / engine (Python 3.11):**
- `fastapi`, `uvicorn[standard]`, `pydantic` (v2) — API.
- `lightkurve` — MAST search/download, detrend, fold. (Pulls in `astropy`, `astroquery`.)
- `transitleastsquares` — primary transit search (period, t0, depth, duration, SDE, FAP, odd/even). Needs `numba`, `batman-package`.
- `astropy` (`astropy.timeseries.BoxLeastSquares`) — BLS cross-check.
- `batman-package` — synthetic transit generation for the injection sandbox.
- `numpy`, `scipy`, `pandas` — numerics.
- `scikit-learn`, `xgboost` — vetting classifier. `shap` — feature attribution.
- `joblib` — model load/save. `python-dotenv` — config.

**Frontend (Node 20+):**
- `next` (App Router, latest stable), `react`, `typescript`.
- `tailwindcss` — styling (design tokens in App Guide).
- `plotly.js-dist-min` + a thin React wrapper for MVP charts; migrate hot paths to `uplot` if the raw curve (10k–60k points) feels sluggish.
- `framer-motion` — transitions/animations.
- `lucide-react` — icons. `zod` — runtime validation of API responses.

**Pin Python deps in `backend/requirements.txt`; pin JS deps via `package-lock.json`.** Use the
latest stable of each unless a version note in `RESOURCES.md` says otherwise. `transitleastsquares`
+ `numba` are the version-sensitive pair — if install fails, pin `numba` to a version compatible
with your Python (3.11 is the safe target).

---

## 5. Repository structure

```
exoseer/
├── AGENTS.md                      # this file
├── ExoSeer_App_Guide.md           # product + UX/UI spec (source of truth for the UI)
├── RESOURCES.md                   # free data, libs, hosting
├── README.md                      # quickstart (generate from this file in Phase 0)
├── docker-compose.yml             # one-command local run (frontend + backend)
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile                 # for Hugging Face Spaces / Render
│   ├── app/
│   │   ├── main.py                # FastAPI app, CORS, routers
│   │   ├── config.py              # env, feature flags
│   │   ├── schemas.py             # Pydantic request/response models (see §8)
│   │   ├── jobs.py                # async job store (in-mem + disk), progress callbacks
│   │   ├── routes/
│   │   │   ├── analyze.py
│   │   │   ├── inject.py
│   │   │   ├── catalog.py
│   │   │   └── health.py
│   │   └── exoseer_core/          # THE ENGINE (pure python, no fastapi imports)
│   │       ├── __init__.py
│   │       ├── ingest.py          # MAST / CSV / synthetic
│   │       ├── preprocess.py      # clean, normalize, flatten, stitch
│   │       ├── detect.py          # TLS + BLS, CNN scorer (optional)
│   │       ├── fold.py            # phase fold + binning
│   │       ├── vet.py             # diagnostics + classifier + verdict
│   │       ├── explain.py         # templated NL + SHAP + optional LLM
│   │       ├── inject.py          # synthetic transit injection (batman)
│   │       ├── stellar.py         # stellar params from TIC/Gaia (astroquery)
│   │       ├── catalog.py         # famous systems registry
│   │       └── types.py           # dataclasses mirroring API schemas
│   ├── models/
│   │   └── vetting_xgb.joblib     # trained model (output of the notebook), vendored
│   ├── data/
│   │   ├── koi_cumulative.csv     # NASA Exoplanet Archive Kepler KOI table (vendored)
│   │   └── toi.csv                # NASA Exoplanet Archive TESS TOI table (vendored)
│   ├── cache/                     # downloaded light curves (gitignored)
│   └── tests/
│       ├── test_pipeline.py       # end-to-end on a known planet (Kepler-10 b)
│       ├── test_vet.py            # diagnostics on a known eclipsing binary
│       └── test_inject.py
│
├── ml/
│   ├── 01_build_training_set.ipynb   # KOI/TOI tables → feature matrix + labels
│   ├── 02_train_vetting_model.ipynb  # train XGBoost, evaluate, export joblib
│   └── 03_optional_cnn_detector.ipynb# Kaggle flux set → 1D CNN (stretch)
│
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    ├── lib/
    │   ├── api.ts                 # typed client + zod schemas + job polling
    │   ├── format.ts              # number/units formatting
    │   └── tokens.ts              # design tokens (mirror App Guide)
    ├── components/
    │   ├── StarSearchPanel.tsx
    │   ├── UploadPanel.tsx
    │   ├── LightCurveChart.tsx
    │   ├── FoldedTransitChart.tsx
    │   ├── ProgressStepper.tsx
    │   ├── VerdictBadge.tsx
    │   ├── ConfidenceMeter.tsx
    │   ├── StatCard.tsx
    │   ├── DiagnosticsPanel.tsx
    │   ├── ExplanationCard.tsx
    │   ├── ShapBar.tsx
    │   ├── InjectionControls.tsx
    │   ├── GalleryGrid.tsx
    │   ├── Starfield.tsx
    │   └── DossierExport.tsx
    └── app/
        ├── layout.tsx
        ├── page.tsx               # landing
        ├── console/page.tsx       # discovery console (main)
        ├── sandbox/page.tsx       # injection–recovery
        ├── gallery/page.tsx
        └── about/page.tsx
```

---

## 6. Environment setup

**Backend**
```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Swagger UI at http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend
npm install
# .env.local:  NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev
# http://localhost:3000
```

**One command (both):** `docker-compose up --build`.

**Environment variables**
- Backend: `EXOSEER_CACHE_DIR` (default `./cache`), `EXOSEER_LLM_PROVIDER` (`none`|`groq`|`gemini`|`hf`|`anthropic`, default `none`), `EXOSEER_LLM_KEY` (only if a provider is set), `CORS_ORIGINS`.
- Frontend: `NEXT_PUBLIC_API_BASE`.
- **No secrets committed.** `.env*` is gitignored. The app must be fully functional with `EXOSEER_LLM_PROVIDER=none`.

---

## 7. The scientific pipeline (`exoseer_core`) — implement exactly

All functions are pure (input → output), typed, and accept an optional `on_progress(stage: str,
pct: float)` callback so the backend can stream the stepper UI.

### 7.1 Ingest (`ingest.py`)
- `from_mast(target: str, mission: str|None, sector_or_quarter: int|None) -> LightCurve`
  - Use `lightkurve.search_lightcurve(target, mission=...)`. Prefer PDCSAP flux. If multiple
    sectors/quarters, `download_all()` then `.stitch()`. Accept names ("Kepler-10"), KIC/TIC IDs,
    or TOI numbers.
  - Cache the downloaded FITS/parsed arrays in `EXOSEER_CACHE_DIR` keyed by target+mission so the
    demo never re-downloads.
  - On MAST timeout/empty result, raise a typed `IngestError` with a user-friendly message.
- `from_csv(file) -> LightCurve` — expect columns `time, flux[, flux_err]`. Validate, coerce to
  days, sort by time. Reject if <500 points or non-monotonic after sort.
- `synthetic(host: str, planet: PlanetParams, noise: NoiseParams) -> LightCurve` — see §7.7.

### 7.2 Preprocess (`preprocess.py`)
Order matters:
1. Drop NaNs/infs in time and flux.
2. Normalize flux to median = 1.0 (`lc.normalize()`).
3. **Flatten / detrend** to remove stellar variability while preserving transits:
   `lc.flatten(window_length=401, polyorder=2, break_tolerance=5)` (Savitzky-Golay).
   Keep BOTH `lc_norm` (variability visible) and `lc_flat` (detrended) — the UI shows both.
4. Sigma-clip outliers on the flattened curve (`sigma=5`), but never clip in-transit points more
   than necessary (use `lightkurve`'s clipping which is transit-aware enough for v1).
5. Record cadence (median Δt) and baseline (t_max − t_min) for downstream sampling.

### 7.3 Detection (`detect.py`)
- **Primary — Transit Least Squares:**
  ```python
  from transitleastsquares import transitleastsquares
  model = transitleastsquares(t, flat_flux)
  results = model.power(  # constrain the grid to keep CPU time ~10–30s
      period_min=0.5, period_max=min(baseline/2, 50),
      oversampling_factor=3, duration_grid_step=1.1)
  ```
  Extract: `period`, `T0`, `duration`, `depth`, `SDE` (signal detection efficiency),
  `FAP` (false-alarm probability via `transitleastsquares` stats), `transit_times`,
  `odd_even_mismatch` (TLS provides this), `snr`, `rp_rs` (radius ratio).
- **Cross-check — BLS:** run `astropy.timeseries.BoxLeastSquares` on the same data; record its
  best period. If TLS and BLS disagree by >1% (and not a 2×/0.5× alias), lower the
  detection confidence and note "period ambiguous" in the explanation.
- **Detection gate:** declare "signal found" if `SDE >= 7` (tunable constant `SDE_THRESHOLD`).
  Below that → verdict `no_significant_signal`, skip vetting, still return the plots.
- **Optional CNN scorer (stretch, Phase ≥5):** the Kaggle 1D-CNN (notebook 03) scores the
  flattened curve 0–1 as a second opinion; surface it as an extra signal feature, never as the
  sole decision.

### 7.4 Phase fold (`fold.py`)
- Fold `lc_flat` at `period`, `T0`. Produce `phase[], flux[]` and a binned version
  (`~200` bins) for a clean overlay. Also produce the TLS model curve (`results.model_folded_*`)
  to overlay the best-fit transit shape on the data.

### 7.5 Vetting (`vet.py`) — the core differentiator
Compute these diagnostics, each returning a value, a significance, and a `pass|flag|fail` verdict
with a one-line human reason:

| Diagnostic | Method | Planet-like | Red flag |
|---|---|---|---|
| **Odd–even depth** | Mean depth of odd-indexed transits vs even-indexed; difference in σ | < 3σ agreement | > 3σ → eclipsing binary |
| **Secondary eclipse** | Search for a dip near phase 0.5 (and eccentric phases); depth & significance | none significant | significant secondary → binary |
| **Transit shape** | Flat-bottom fraction = T_full/T_total from the fitted model; or χ² of box vs limb-darkened template | U-shaped / flat-bottomed | V-shaped / grazing → suspect |
| **Implied radius** | `Rp = R_star * sqrt(depth)`, R_star from TIC/Gaia (`stellar.py`); convert to R⊕ | ≲ 25 R⊕ | ≳ 25–28 R⊕ → stellar companion |
| **SNR / SDE** | from detection | high | low → noise/marginal |
| **Transit count** | number of transits in baseline | ≥ 2–3 | 1 → unconfirmable |

`stellar.py`: fetch `R_star`, `Teff`, `logg`, `M_star` via `astroquery` (TIC for TESS, Gaia/KIC
otherwise). If unavailable, mark radius "indeterminate" and proceed (don't crash).

**Classifier:** assemble the feature vector (see §10), run the pre-trained XGBoost model
(`models/vetting_xgb.joblib`) to get class probabilities over
`{planet_candidate, eclipsing_binary, variable_or_other}`. The **verdict** combines model output
with hard physical flags: any *fail*-level red flag (e.g., strong secondary eclipse, radius ≫
planetary) caps the planet probability and flips the verdict — physics overrides the ML when they
conflict, and the explanation says so.

Output verdict ∈ `{planet_candidate, likely_eclipsing_binary, stellar_variability,
low_confidence, no_significant_signal}` plus a 0–1 confidence.

### 7.6 Explainability (`explain.py`)
- **Deterministic narrative (default, $0):** a templated generator that turns each diagnostic's
  verdict+magnitude into one sentence, ordered by importance, ending with the overall verdict and
  the single strongest piece of evidence. Example output:
  > *"Likely planet candidate (confidence 0.81). The transit is flat-bottomed and shows no
  > secondary eclipse; odd and even transit depths agree to within 1.4σ. The implied radius of
  > 4.2 R⊕ is in the planetary range. Period 3.52 d, SDE 12.3 over 9 transits."*
- **SHAP:** compute per-feature contributions for the classifier; the UI renders a small bar.
- **Optional LLM enhancement:** if `EXOSEER_LLM_PROVIDER != none`, pass the *structured dossier*
  (never raw data) to a free LLM (Groq / Google AI Studio / HF Inference) to rewrite the narrative
  more fluently. Strictly additive; falls back to the deterministic text on any error or timeout.

### 7.7 Injection (`inject.py`)
- Use `batman` to generate a transit model with user-chosen `rp_rs` (from radius), `period`, `T0`,
  impact parameter `b`, quadratic limb darkening. Multiply into a chosen **quiet** host star's
  real flux. Optionally add white noise (scale by a "difficulty" slider) and a slow sinusoid (red
  noise) to mimic stellar variability.
- Run the full pipeline on the injected curve and report **injected vs recovered** parameters and
  a boolean `recovered` (SDE ≥ threshold AND recovered period within tolerance of injected).

---

## 8. Backend API contract (frozen)

CORS allows the frontend origin. All responses are JSON. Long work uses a job/poll pattern.

### `POST /analyze` → `202 { "job_id": str }`
Request:
```json
{
  "source": "mast" | "upload" | "catalog",
  "target": "Kepler-10",            // for mast/catalog
  "mission": "Kepler" | "TESS" | "K2" | null,
  "sector_or_quarter": null,
  "csv_base64": null,               // for upload
  "options": { "sde_threshold": 7, "period_max": 50 }
}
```

### `GET /jobs/{job_id}` → `200 JobStatus`
```json
{
  "job_id": "…",
  "status": "queued" | "running" | "done" | "error",
  "stage": "fetching" | "detrending" | "searching" | "folding" | "vetting" | "explaining" | "complete",
  "progress": 0.0,                  // 0..1
  "error": null,
  "result": null | AnalysisResult
}
```

### `AnalysisResult` (the dossier — the frontend's core object)
```json
{
  "star": { "id": "Kepler-10", "mission": "Kepler", "teff": 5627, "radius_rsun": 1.06, "logg": 4.34 },
  "lightcurve": {
    "time": [/* days */], "flux_norm": [/* variability visible */], "flux_flat": [/* detrended */]
  },
  "detection": {
    "found": true, "period_days": 0.8375, "t0": 134.45, "duration_hours": 1.8,
    "depth_ppm": 152.0, "sde": 21.4, "fap": 1.2e-9, "snr": 18.7, "n_transits": 47,
    "bls_period_days": 0.8375, "period_ambiguous": false
  },
  "folded": { "phase": [], "flux": [], "phase_binned": [], "flux_binned": [], "model": [] },
  "vetting": {
    "verdict": "planet_candidate",
    "confidence": 0.86,
    "probabilities": { "planet_candidate": 0.86, "eclipsing_binary": 0.05, "variable_or_other": 0.09 },
    "implied_radius_rearth": 1.47,
    "diagnostics": [
      { "key": "odd_even",  "label": "Odd–even depth",   "value": "0.9σ",  "verdict": "pass", "reason": "Alternating transit depths agree." },
      { "key": "secondary", "label": "Secondary eclipse", "value": "none",  "verdict": "pass", "reason": "No occultation at phase 0.5." },
      { "key": "shape",     "label": "Transit shape",     "value": "U-shaped", "verdict": "pass", "reason": "Flat-bottomed, consistent with a planet." },
      { "key": "radius",    "label": "Implied radius",    "value": "1.47 R⊕", "verdict": "pass", "reason": "Within the planetary size range." },
      { "key": "snr",       "label": "Signal strength",   "value": "SDE 21.4", "verdict": "pass", "reason": "Strong, well above the noise floor." }
    ]
  },
  "explanation": {
    "narrative": "…plain-English paragraph…",
    "feature_importance": [ { "feature": "secondary_significance", "contribution": 0.22 }, { "feature": "shape_metric", "contribution": 0.18 } ]
  }
}
```

### `POST /inject` → `202 { "job_id": str }`  (same poll endpoint)
Request:
```json
{
  "host": "Kepler-16",              // a quiet star from the catalog
  "planet": { "radius_rearth": 2.0, "period_days": 7.3, "impact": 0.2 },
  "noise_level": 0.5                // 0 (easy) .. 1 (hard)
}
```
Result adds an `injection` block: `{ "injected": {...}, "recovered": {...}, "recovered_bool": true }`
alongside the normal dossier.

### `GET /catalog` → `200 { "systems": CatalogEntry[] }`
Famous, fast-loading systems for instant demos (see §9.4). Each entry: `{ id, mission, label,
blurb, expected_verdict }`.

### `GET /healthz` → `200 { "ok": true, "model_loaded": true }`

**Job store:** in-memory dict keyed by `job_id`, mirrored to disk so a Space restart doesn't lose
an in-flight demo. Auto-expire after 1 hour. Run the pipeline in a background task /
threadpool so the event loop stays responsive.

---

## 9. Frontend spec

Follow `ExoSeer_App_Guide.md` for exact copy, layout, and design tokens. Engineering rules:

### 9.1 Data layer (`lib/api.ts`)
- Typed client with `analyze()`, `inject()`, `getJob()`, `getCatalog()`.
- **Validate every response with `zod`** against schemas mirroring §8 — fail loud in dev.
- `usePipelineJob()` hook: kicks off a job, polls `GET /jobs/{id}` every ~1.2s, exposes
  `{ stage, progress, result, error }`. Stop polling on `done`/`error`. Show the stepper from
  `stage`.

### 9.2 Charts
- `LightCurveChart`: raw/detrended toggle; thousands of points; pan/zoom. Plotly `scattergl`
  (WebGL) for performance in MVP; swap to `uPlot` if needsbe.
- `FoldedTransitChart`: scatter of folded points (low opacity) + binned points (solid) + the TLS
  model line overlaid. This is the "hero" science chart — make it beautiful.

### 9.3 Pages
- `/` landing → see App Guide §"Screen 1". Primary CTA routes to `/console`; "Try a demo star"
  routes to `/console?demo=<famous_id>` and auto-runs.
- `/console` → input panel (search / upload / "Surprise me" / open sandbox), the two charts, the
  verdict + diagnostics + explanation panels, dossier export. The **first visit auto-loads a
  famous multi-planet or hot-Jupiter system** so the very first interaction is a guaranteed win.
- `/sandbox` → `InjectionControls` (radius, period, impact, noise sliders + host picker) →
  side-by-side injected vs recovered + a `recovered` indicator.
- `/gallery` → grid of catalog systems; click → opens console pre-loaded.
- `/about` → method, data sources, **limitations & honesty** (see §16), credits to NASA/MAST.

### 9.4 Catalog seeds (guaranteed-good demos)
Include at least: a clean hot Jupiter (e.g. **Kepler-8 b**), a famous multi-planet system
(**Kepler-90** / **TRAPPIST-1** via TESS), a tiny terrestrial (**Kepler-10 b**), and at least one
**known eclipsing binary / false positive** so the demo shows ExoSeer *correctly rejecting* a
non-planet. Verify each loads fast and gives the expected verdict before the finale.

---

## 10. ML training (`ml/` notebooks) — run on free Colab/Kaggle GPU/CPU

The vetting model is trained **offline** and the resulting `vetting_xgb.joblib` is committed to
`backend/models/`. The app never trains at runtime.

**`01_build_training_set.ipynb`**
- Download the NASA Exoplanet Archive **Kepler KOI cumulative** table and the **TESS TOI** table
  (URLs in `RESOURCES.md`); vendor them as CSV in `backend/data/`.
- Labels: KOI `koi_disposition` → CONFIRMED→`planet`, FALSE POSITIVE→`eclipsing_binary`/`other`
  (use `koi_fpflag_*` to separate EB-like from other FP where possible); TOI `tfopwg_disp` →
  CP/KP→`planet`, FP/FA→false positive, EB→`eclipsing_binary`. Drop ambiguous CANDIDATE/PC rows
  from training (or hold out).
- Features per row (use catalog-provided measurements so training is fast and reproducible):
  `period`, `duration`, `depth`, `snr/mes`, `prad` (planet radius), `srad`/`steff`/`slogg`
  (stellar), plus engineered `duration_over_period`, `depth_snr`, and the fp/odd-even/secondary
  flags where the table provides them. **The live pipeline computes the equivalent features from
  TLS + stellar lookup**, so train and inference features must align — document the mapping in a
  `FEATURES` constant shared in spirit between notebook and `vet.py`.
- Handle class imbalance with `scale_pos_weight` / class weights; stratified train/test split.

**`02_train_vetting_model.ipynb`**
- Train `XGBoostClassifier` (multiclass). Report accuracy, per-class precision/recall, confusion
  matrix, and ROC-AUC. Target: clearly beats a majority-class baseline and separates planets from
  EBs well (this is your defensible "it works" slide).
- Compute and save a SHAP explainer alongside the model. Export `vetting_xgb.joblib`.

**`03_optional_cnn_detector.ipynb` (stretch)**
- Kaggle "Exoplanet Hunting in Deep Space" flux set (5,087 stars, only 37 positives — **heavily
  imbalanced**). Detrend, SMOTE/augment (reverse positives), train a small 1D CNN, export. Use
  only as a secondary detection signal, never the verdict.

---

## 11. Coding conventions

- **TypeScript** strict mode on; no `any` in committed code; props typed; `zod`-validate external data.
- **Python** type hints everywhere; Pydantic v2 models for I/O; `dataclasses` in the engine.
- **Errors**: typed exceptions in the engine (`IngestError`, `DetectionError`, `StellarLookupError`),
  caught in the routes and mapped to friendly `JobStatus.error` strings. Never leak stack traces to
  the client. Never crash the job on a missing stellar radius — degrade gracefully.
- **Determinism**: set numpy/random seeds in injection and any sampling; same input → same output.
- **Caching**: cache MAST downloads on disk; the gallery systems must work offline-of-MAST during
  the demo (pre-warm the cache in a `make warm` script before judging).
- **No secrets** in the repo. **No PII.** LLM calls send only the structured dossier.
- **Comments** explain *why* (the astrophysics), not *what*. Cite the method in a docstring
  (e.g., "odd-even test per standard transit vetting; >3σ suggests an eclipsing binary").

---

## 12. Testing

- `test_pipeline.py`: run `from_mast("Kepler-10", "Kepler")` (or a cached fixture) end-to-end;
  assert a signal is found, period ≈ 0.837 d (within tolerance), verdict == `planet_candidate`.
- `test_vet.py`: feed a known **eclipsing binary** fixture; assert the secondary-eclipse or
  odd-even diagnostic flags it and the verdict is `likely_eclipsing_binary`.
- `test_inject.py`: inject a 2 R⊕ / 7 d planet at low noise; assert `recovered == true` and
  recovered period within tolerance.
- **Use cached fixtures** so CI/tests never depend on live MAST. Frontend: at minimum a smoke test
  that the console renders the dossier from a mocked API response.

---

## 13. Build order & milestones (do in this order)

Each milestone ends with a **demoable** state. Do not skip ahead.

**Phase 0 — Scaffold (½ day).** Monorepo, `docker-compose up` runs an empty FastAPI (`/healthz`)
and a Next.js landing placeholder. Generate `README.md` from this file.
*Done when:* one command brings both up and the landing page hits `/healthz` green.

**Phase 1 — MVP engine + console (the core demo) (2–3 days).**
`ingest.from_mast` → `preprocess` → `detect` (TLS + BLS) → `fold`. `POST /analyze` job +
`GET /jobs/{id}`. Console renders the light curve, the folded transit with model overlay, and stat
cards (period, depth, duration, SDE, SNR, n_transits). Auto-run a famous star on first visit.
*Done when:* type "Kepler-8" → see its transit detected, folded, and measured. **This alone is a
standalone working demo and a fundable proposal artifact.**

**Phase 2 — Vetting + verdict (2 days).**
`stellar.py` lookups; all diagnostics in `vet.py`; train + vendor `vetting_xgb.joblib` (notebooks
01–02); verdict + probabilities + `DiagnosticsPanel` with pass/flag chips and tooltips; physics
overrides ML when they conflict.
*Done when:* a planet reads `planet_candidate` and a known eclipsing binary reads
`likely_eclipsing_binary`, each with sensible diagnostics.

**Phase 3 — Explainability (1 day).**
Deterministic narrative + SHAP bar in `ExplanationCard`. Optional LLM enhancement behind the flag,
defaulting to off.
*Done when:* every verdict shows a clear, correct plain-English reason and a feature-importance bar.

**Phase 4 — Injection sandbox (1–1.5 days).**
`inject.py` + `/inject` + `/sandbox` UI with sliders and the injected-vs-recovered view.
*Done when:* dragging the radius down until ExoSeer *loses* the planet visibly demonstrates the
noise floor live.

**Phase 5 — Polish & deploy (1.5 days).**
Landing hero + starfield + Framer Motion; gallery; dossier export (JSON + print-to-PDF);
about/limitations page; responsive pass; **pre-warm the MAST cache**; deploy backend to Hugging
Face Spaces (Docker) and frontend to Vercel; set CORS + `NEXT_PUBLIC_API_BASE`.
*Done when:* a stranger can open the public URL and discover a planet in under a minute.

**Stretch (only if time remains):** CNN detector (notebook 03) as a second signal; TPF centroid /
difference-imaging vetting for blends; batch mode (analyze a list); a "citizen science" vote.

---

## 14. Deployment (free)

- **Backend → Hugging Face Spaces (Docker SDK), free CPU tier.** It provides a generous
  always-available CPU box; TLS runs comfortably there. Note the free tier sleeps after extended
  inactivity and cold-starts on the next request — hit the URL right before judging. Put the
  `Dockerfile` at `backend/Dockerfile`, expose the uvicorn port the Space expects (read its
  current docs), and commit the vendored model + data so no large downloads happen at boot.
  *Alternative:* Render free web service (also sleeps when idle) or Railway.
- **Frontend → Vercel (free Hobby).** Set `NEXT_PUBLIC_API_BASE` to the Space URL. Enable CORS for
  the Vercel domain in FastAPI.
- **Avoid Fly.io for new accounts** — no longer free for new sign-ups (pay-as-you-go).
- Verify each platform's *current* free-tier limits at the source before relying (see `RESOURCES.md`).

---

## 15. Performance & robustness

- Constrain the TLS period grid (`period_max`, `oversampling_factor=3`) to keep a search to
  ~10–30s; show the stepper so the wait feels intentional, not broken.
- **Always cache** downloaded light curves; pre-warm the gallery before the demo.
- Handle MAST flakiness: timeout, one retry, then a clear error + offer a cached gallery star.
- Cap uploaded CSV size and point count; downsample for plotting (keep full data for the search).
- Keep the WebGL chart performant: don't re-render on every poll tick; memoize.

---

## 16. Guardrails & scientific honesty (non-negotiable)

- **Never say "discovered a new planet."** Say **"planet candidate"** / "consistent with a
  transiting planet." Real confirmation needs radial-velocity follow-up and human review.
- State limitations plainly on the About page: single-sector data, faint-star noise, grazing
  geometries, and blended sources can fool any automated vetter; ExoSeer flags uncertainty rather
  than hiding it.
- Credit NASA / the MAST archive and the Kepler/K2/TESS missions in the footer and About page.
- Calibrated confidence beats false certainty — judges reward teams that know their method's edges.

---

## 17. Definition of done

1. `docker-compose up` runs the whole app locally; the public URLs work.
2. A user can: search a star → get a measured, vetted, explained verdict; reject a known binary;
   inject and recover a synthetic planet.
3. Tests in §12 pass against cached fixtures.
4. The proposal/demo artifacts exist: this repo + a short slide deck whose flow follows the
   "judge demo script" in the App Guide + the offline metrics from notebook 02.
5. Nothing in the product overclaims (see §16).
