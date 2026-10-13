# RESOURCES.md — ExoSeer (everything free)

Every resource below is free to use. **Free tiers change — verify current limits at the source
before you depend on them.** Links are starting points; descriptions are paraphrased, not copied.

---

## 1. Data (all free, no purchase)

**Light curves (the raw material) — via `lightkurve`:**
- NASA Kepler / K2 / TESS light curves are stored on the **Mikulski Archive for Space Telescopes
  (MAST)** and downloaded through the open-source `lightkurve` package — search by star name,
  KIC/TIC ID, or coordinates; no API key.
  - Lightkurve docs & tutorials: https://lightkurve.github.io/lightkurve/
  - Lightkurve GitHub: https://github.com/lightkurve/lightkurve
  - MAST portal: https://mast.stsci.edu/
  - exo.MAST (per-planet TESS light curves & parameters, REST): https://exo.mast.stsci.edu/

**Labels for the vetting model — NASA Exoplanet Archive (free tables):**
- **Kepler KOI cumulative table** (dispositions: CONFIRMED / CANDIDATE / FALSE POSITIVE, plus
  measured period/depth/duration and false-positive flags) — your primary training labels.
- **TESS Project Candidates (TOI) table** (dispositions CP/KP/PC/FP/FA/EB).
- NASA Exoplanet Archive: https://exoplanetarchive.ipac.caltech.edu/
  (Use the table download / TAP service to vendor `koi_cumulative.csv` and `toi.csv` into
  `backend/data/`.)
- ExoFOP (follow-up dispositions, useful context): https://exofop.ipac.caltech.edu/

**Stellar parameters (radius, Teff, logg) — via `astroquery`:**
- TESS Input Catalog (TIC), Gaia, and KIC — queried programmatically for the host-star radius used
  to convert transit depth into a planet radius.
  - astroquery: https://astroquery.readthedocs.io/

**Optional supplementary training set (stretch / CNN only):**
- **Kaggle "Exoplanet Hunting in Deep Space"** (Kepler-labelled flux time series; 5,087 stars,
  only 37 confirmed-planet positives → **heavily imbalanced**, use augmentation/SMOTE):
  https://www.kaggle.com/datasets/keplersmachines/kepler-labelled-time-series-data

---

## 2. Python libraries (backend / engine) — all `pip install`, all free

| Library | Purpose |
|---|---|
| `lightkurve` | Search/download MAST light curves; normalize, flatten/detrend, fold. |
| `astropy` | Core astronomy; `astropy.timeseries.BoxLeastSquares` for the BLS cross-check. |
| `astroquery` | Stellar parameters from TIC / Gaia / KIC. |
| `transitleastsquares` | **Primary transit search** — period, t0, depth, duration, SDE, FAP, odd/even, Rp/Rs. Docs: https://transitleastsquares.readthedocs.io/ · GitHub: https://github.com/hippke/tls |
| `batman-package` | Generate synthetic transit models for the Injection Sandbox. https://github.com/lkreidberg/batman |
| `numpy`, `scipy`, `pandas` | Numerics and tables. |
| `scikit-learn` | Utilities, metrics, preprocessing. |
| `xgboost` | The vetting classifier (multiclass). |
| `shap` | Feature-attribution for the explanation card. |
| `joblib` | Save/load the trained model. |
| `fastapi`, `uvicorn[standard]`, `pydantic` | The API. |
| `python-dotenv` | Config. |

> Version note: `transitleastsquares` depends on `numba` + `batman-package`. If install fails,
> target **Python 3.11** and pin a `numba` version compatible with it. Test the install early
> (Phase 0/1) so it never blocks you near the deadline.

---

## 3. JavaScript / frontend libraries — all free

| Library | Purpose |
|---|---|
| `next`, `react`, `typescript` | App framework (App Router). https://nextjs.org/ |
| `tailwindcss` | Styling + design tokens. https://tailwindcss.com/ |
| `plotly.js-dist-min` | Light-curve & folded-transit charts (WebGL `scattergl`), MVP. https://plotly.com/javascript/ |
| `uplot` | Faster canvas charts for the raw curve if Plotly lags. https://github.com/leeoniya/uPlot |
| `framer-motion` | Animations/transitions. https://www.framer.com/motion/ |
| `lucide-react` | Icons. https://lucide.dev/ |
| `zod` | Runtime validation of API responses. https://zod.dev/ |

---

## 4. Free compute (for training the model in `ml/`)

- **Google Colab** — free CPU + occasional free GPU; perfect for notebooks 01–03.
  https://colab.research.google.com/
- **Kaggle Notebooks** — free CPU and a weekly free GPU quota; also hosts the supplementary
  dataset. https://www.kaggle.com/code

> You do **not** need a GPU for the core product. TLS runs in ~10–30s on a CPU; the XGBoost vetting
> model trains in seconds on tabular features. GPU is only relevant for the optional CNN (notebook
> 03).

---

## 5. Free hosting & deployment

| Layer | Free option | Notes |
|---|---|---|
| **Backend (FastAPI)** | **Hugging Face Spaces** (Docker SDK), free **CPU Basic (2 vCPU, 16 GB RAM)** | Generous CPU box; ideal for the TLS pipeline. Free Spaces **sleep after extended inactivity** and cold-start on next request — hit the URL right before judging. No credit card to start. https://huggingface.co/spaces |
| Backend (alt) | **Render** free web service | Enough runtime for one small service; **spins down when idle**, cold-starts on request. https://render.com/ |
| Backend (alt) | Railway / Koyeb | Trial credits / scale-to-zero; check current terms. |
| **Frontend (Next.js)** | **Vercel** free Hobby | First-class Next.js host; set `NEXT_PUBLIC_API_BASE` to the backend URL; enable CORS for the Vercel domain. https://vercel.com/ |
| Database (only if needed) | **Supabase** free Postgres | v1 needs no DB — disk/in-memory job store + on-disk light-curve cache is enough. https://supabase.com/ |

> **Avoid Fly.io for new accounts** — it no longer offers a free tier to new sign-ups (pay-as-you-go,
> card required). Legacy accounts keep old allowances.

> **Demo-day tip:** "free + sleeps when idle" is fine if you **pre-warm**: open both URLs and run
> each gallery star a few minutes before judging so caches are hot and the Space is awake.

---

## 6. Optional free LLM for the narrative (the deterministic fallback is the $0 guarantee)

ExoSeer's explanation works with **zero** LLM (templated generator). If you want fluffier prose,
any of these have free tiers you can put behind `EXOSEER_LLM_PROVIDER`:
- **Google AI Studio (Gemini)** free tier: https://aistudio.google.com/
- **Groq** free tier (very fast): https://groq.com/
- **Hugging Face** Serverless Inference (free, rate-limited): https://huggingface.co/ (Inference)
- **Anthropic** — Claude credits via open-source / startup programs may apply: https://www.anthropic.com/
- **Default:** `none` (deterministic templated narrative). The app must be fully functional and
  demo-ready with no LLM key set.

> Send only the **structured dossier** (numbers + verdicts) to any LLM — never raw user data.

---

## 7. Learning references (free)

- **Lightkurve tutorials** (searching, detrending, folding, BLS): https://lightkurve.github.io/lightkurve/tutorials/
- **AstroPy Box Least Squares tutorial**: https://docs.astropy.org/en/stable/timeseries/bls.html
- **Transit Least Squares paper** (Hippke & Heller 2019, the method behind your detector):
  https://arxiv.org/abs/1901.02015
- **NASA Exoplanet Archive docs** (tables, columns, dispositions):
  https://exoplanetarchive.ipac.caltech.edu/docs/
- **MAST notebooks** (worked examples of accessing TESS/Kepler data):
  https://spacetelescope.github.io/mast_notebooks/

---

## 8. The hackathon

- **Bharatiya Antariksh Hackathon (BAH) 2026**, ISRO, powered by Hack2skill:
  https://hack2skill.com/event/bah2026/
- Free to participate; runs **proposal/idea first**, then a build/finale phase for shortlisted
  teams. Confirm the *current* eligibility, team rules (typically 3–4 students enrolled at Indian
  institutions), and deadlines on the official page before submitting.

> Because BAH submits an **idea/proposal first**, treat **Phase 1** of `AGENTS.md` (a working
> detect-and-fold console on a famous star) as the artifact that backs a strong proposal, then
> build Phases 2–5 for the finale.
