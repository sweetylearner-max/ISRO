# ExoSeer — App Guide ("the biography")

> This document is the source of truth for **what the app is, how it feels, what the user sees
> first, and exactly what they do step by step.** The coding agent must follow this for all UI
> copy, layout, flow, and design tokens. Engineering rules live in `AGENTS.md`.

---

## 1. The one-liner

**ExoSeer finds worlds hidden in starlight — and tells you why it believes they're real.**

Point it at a star. It watches the star's brightness flicker over months of real NASA data,
catches the faint, regular dimming of a planet crossing in front, and then does the hard part:
it decides whether that dip is a *planet*, a pair of *eclipsing stars*, a restless *starspot*, or
just *noise* — and explains its verdict in plain language a human can check.

**Tagline:** *See worlds hidden in starlight.*

---

## 2. Why it matters (the pitch in three sentences)

Most of humanity's confirmed planets were found by spotting tiny, periodic dips in starlight — but
the signal is buried in noise, and most candidate dips turn out **not** to be planets. Vetting
those candidates is slow, expert-only work. ExoSeer automates the vetting *and* shows its reasoning
— democratizing planet-hunting for students and citizen scientists, on $0 of infrastructure, using
only open NASA data.

---

## 3. Who it's for

- **Hackathon judges (primary, day-of):** they need to *get it in 30 seconds* and see it *work
  live*. Every design choice optimizes for an unforgettable 3-minute demo.
- **Students & citizen scientists:** the curious who want to actually *do* the thing astronomers
  do, without a PhD or a cluster.
- **Educators:** a visual, interactive way to teach the transit method and false positives.
- **Researchers (aspirational):** a fast first-pass triage tool over archive light curves.

---

## 4. The magic moment

The instant that wins the room: the user drags the **planet-size slider** in the Injection Sandbox
down, down, down — and watches ExoSeer's confidence hold… hold… then *collapse* exactly when the
planet gets too small to see through the noise. In one gesture they understand both *how detection
works* and *that ExoSeer is honest about its limits*. That's the screenshot they remember.

The runner-up moment: ExoSeer looking at a famous false positive and saying, calmly,
**"This is not a planet — there's a secondary eclipse at phase 0.5; it's a pair of stars."**

---

## 5. Visual design system

**Mood:** a quiet, modern **observatory at night** — deep space, instrument glow, scientific
precision. Calm and confident, never cartoonish. The light curve itself is the hero visual.

**Color tokens** (mirror in `frontend/lib/tokens.ts`):
- Background base `#070b14`, panel `#0e1422`, panel-raised `#141c2e`, hairline border `#1f2a40`.
- Text primary `#e6edf6`, secondary `#9fb0c7`, muted `#5f7088`.
- Accent (discovery) cyan `#22d3ee`; secondary accent violet `#8b5cf6`.
- Verdict semantics: planet/pass **emerald `#34d399`**, caution/flag **amber `#fbbf24`**,
  reject/fail **rose `#fb7185`**, neutral/low-confidence **slate `#94a3b8`**.
- Subtle glows: accent and verdict colors at ~12% opacity as box-shadows on key cards.

**Typography:**
- Headings: **Space Grotesk** (geometric, a quiet nod to "space"). 
- Body/UI: **Inter**.
- **All numbers and measured values: a monospace** (JetBrains Mono / IBM Plex Mono) so periods,
  depths, and SDE read like instrument readouts. This single choice makes the app feel scientific.

**Motion (Framer Motion):** purposeful, never bouncy. Charts draw in (line traces in over ~600ms);
stat values count up; the verdict badge fades+scales in once; stepper stages tick over smoothly. A
faint, slow-parallax **starfield** (`Starfield.tsx`, canvas, low CPU, `prefers-reduced-motion`
aware) sits behind the landing and console — atmosphere, not distraction.

**Layout:** generous spacing, max content width ~1200px on the console, rounded-2xl panels with
hairline borders and soft inner glow. Dark-first; the whole product lives in dark mode.

**Accessibility:** WCAG-AA contrast on text; never rely on color alone for verdicts (always pair a
color with an icon + label); full keyboard nav; respect reduced-motion; tooltips reachable by
focus.

---

## 6. The screens (every detail)

### Screen 1 — Landing (`/`) — *the first thing the user sees*

A full-height dark hero over the slow starfield. **Above the fold, in order, top to bottom:**

1. **Wordmark** top-left: `✦ ExoSeer` (the ✦ glyph glows faint cyan). Minimal top nav on the
   right: *Console · Sandbox · Gallery · About*.
2. **Headline (centered, large, Space Grotesk):** *"See worlds hidden in starlight."*
3. **Sub-headline (one line, secondary text):** *"An explainable AI that detects exoplanets in
   real NASA light curves — and tells you why."*
4. **A live mini light-curve** animating across the hero: a faint flux line ticking left-to-right
   with a visible periodic **dip**; on each dip, a tiny planet-and-star glyph crosses. Pure
   decoration, looped, lightweight. (If perf is a concern, a pre-rendered SVG/Lottie is fine.)
5. **Primary CTA button (cyan, glowing):** **"Begin discovery →"** → routes to `/console`.
   **Secondary CTA (ghost):** **"Try a demo star"** → routes to `/console?demo=Kepler-8` and
   auto-runs the pipeline.
6. **Trust line (muted, small):** *"Powered by real data from NASA's Kepler, K2 & TESS missions
   via the MAST archive."*

**Below the fold (optional, scroll):** a three-step "how it works" strip — *Detect · Vet · Explain*
— each with a one-line description and a tiny illustration; then a single sentence on impact and a
footer crediting NASA/MAST. Keep it short; the landing's job is to get the user into the console.

**First-time intent:** most users will click "Try a demo star." Design for that path to feel
instant and magical.

---

### Screen 2 — Discovery Console (`/console`) — *the core workspace*

Three-column layout on desktop (stacks vertically on mobile):

**Left column — Input panel (`StarSearchPanel` + `UploadPanel`):**
- A segmented control: **Search · Upload · Surprise me**.
  - **Search:** a text field — *"Enter a star: name (Kepler-10), KIC/TIC ID, or TOI number"* — with
    a mission dropdown (Auto · Kepler · K2 · TESS) and an **Analyze** button.
  - **Upload:** drag-and-drop for a CSV (`time, flux[, flux_err]`); shows a tiny preview plot on
    drop; **Analyze** button.
  - **Surprise me:** picks a random gallery system and runs it.
- A small **"Open Injection Sandbox →"** link at the bottom of the panel.
- Below: a **Recent runs** list (optional, localStorage) — click to reload a past dossier.

**Center column — The light curve (`LightCurveChart` + `FoldedTransitChart`):**
- **Top chart — the full light curve.** A toggle: **Raw (variability) · Detrended**. Time on x
  (days), normalized flux on y. Pan/zoom. This is where the user *sees the dips* in the long
  stream of data.
- **Bottom chart — the phase-folded transit** (appears after analysis). All observations folded
  onto one orbital period: a cloud of faint points forming the transit shape, solid **binned**
  points on top, and the **best-fit model curve** overlaid in cyan. *This is the chart that makes
  people lean in* — the messy stream collapses into one clean dip.

**Right column — The verdict (`VerdictPanel`):**
- Before analysis: an empty state — *"Choose a star and hit Analyze to begin."*
- During analysis: the **ProgressStepper** (see Screen 2b).
- After analysis (the **dossier**):
  - **VerdictBadge** at the top: a pill with icon + label + color — e.g. ✅ **Planet candidate**
    (emerald), ⚠️ **Likely eclipsing binary** (amber), ◌ **Stellar variability** (slate),
    ✖ **No significant signal** (slate).
  - **ConfidenceMeter:** a horizontal 0–100% bar, colored by verdict, with the % in monospace.
  - **StatCards** (a 2- or 3-up grid, monospace values): **Period** (days), **Transit depth**
    (ppm), **Duration** (hours), **Implied radius** (R⊕), **SDE**, **Transits seen** (count).
  - **DiagnosticsPanel:** one row per vetting check — *Odd–even depth · Secondary eclipse ·
    Transit shape · Implied radius · Signal strength* — each with a **pass/flag/fail chip**
    (color + icon), the value (monospace), and a one-line reason. A **(?)** on each opens a tooltip
    explaining the test in human terms (see §8 microcopy).
  - **ExplanationCard:** the plain-English narrative ("Why this verdict"), followed by a small
    **ShapBar** showing which features drove the model most.
  - **DossierExport:** buttons — **Export JSON** and **Save as PDF** (print stylesheet) — plus a
    **Copy link** if you implement shareable run IDs.

**On first visit to `/console`** (no query param): auto-load and auto-run a guaranteed-good system
(e.g. **Kepler-8 b**, a clean hot Jupiter) so the user's *very first* sight is a full, beautiful,
successful dossier — not an empty form.

### Screen 2b — The running state (the stepper)

While a job runs, the right column shows `ProgressStepper` with six labeled stages that light up in
sequence as `GET /jobs/{id}` reports them:
**Fetching starlight → Detrending → Searching for transits → Folding the orbit → Vetting the
signal → Writing the verdict.**
Each completed stage gets a check; the active one pulses faintly. The wait (10–30s for the TLS
search) should feel like an instrument working, not a spinner hanging.

---

### Screen 3 — Injection Sandbox (`/sandbox`) — *the showstopper*

Headline: **"Can ExoSeer find your hidden world?"** Sub: *"Plant a fake planet in a real, quiet
star and watch the engine try to recover it."*

- **`InjectionControls`** (left): a **host star** picker (quiet stars from the catalog) and four
  sliders, each with a live monospace readout:
  - **Planet radius** (0.5 – 12 R⊕)
  - **Orbital period** (0.5 – 30 days)
  - **Impact parameter** (0 = central, 1 = grazing)
  - **Noise / difficulty** (Easy ↔ Hard)
  - A big **"Inject & recover"** button.
- **Result (center/right):** a side-by-side — *Injected* (the truth) vs *Recovered* (what ExoSeer
  found) — as a small parameter table, plus the folded chart of the injected curve with the
  recovered model overlaid, and a prominent **recovery indicator**: ✅ **Recovered** (recovered
  period within tolerance, SDE above threshold) or ✖ **Lost in the noise.**
- The intended interaction (call it out with a subtle hint): *"Shrink the planet until ExoSeer
  loses it — that's the detection limit."*

---

### Screen 4 — Gallery (`/gallery`)

Headline: **"A field guide to other worlds."** A responsive grid of `GalleryGrid` cards, each a
famous system: name, mission badge, a one-line blurb, and an expected-verdict hint. Click → opens
`/console?demo=<id>` pre-loaded. **Must include at least one known false positive / eclipsing
binary** so visitors can see ExoSeer *correctly reject* a non-planet, not just confirm planets.

Seed set (verify each loads fast and behaves before the demo):
- **Kepler-8 b** — a clean hot Jupiter (great first impression).
- **Kepler-10 b** — a tiny rocky world (shows sensitivity to small planets).
- **Kepler-90 / TRAPPIST-1** — a multi-planet system (wow factor).
- **A known eclipsing binary / false positive** — the "ExoSeer says no" case.

---

### Screen 5 — About & Honesty (`/about`)

- **How it works** — the transit method and the detect → vet → explain pipeline, in a few short
  paragraphs with the same illustrations as the landing strip.
- **The data** — NASA Kepler/K2/TESS via the MAST archive; the NASA Exoplanet Archive labels used
  to train the vetting model. Links out.
- **Limitations (state plainly):** single-sector or faint-star data is noisy; grazing geometries
  and blended/contaminated sources can fool any automated vetter; ExoSeer reports *candidates*, not
  confirmations — real confirmation needs follow-up observations and human review. *This honesty is
  a feature; judges reward calibrated confidence.*
- **Credits** — NASA, the mission teams, and the open-source `lightkurve` / `transitleastsquares`
  communities.

---

## 7. The user journey, step by step

This is the canonical happy path — "user does this, then this, then this."

1. **Land.** User arrives on `/`. They see the headline, the live dipping light-curve, and two
   buttons.
2. **Enter.** They click **"Try a demo star."** (Or "Begin discovery" → lands on a console that has
   *already* auto-run a famous planet, so they still see a full result immediately.)
3. **See the data.** The console loads. The top chart animates in: a long, faint stream of
   brightness with visible periodic dips. They toggle **Raw ↔ Detrended** and watch the stellar
   wobble flatten away, leaving the transits.
4. **Analyze.** (On the demo path this already fired.) The right column runs the **stepper**:
   Fetching → Detrending → Searching → Folding → Vetting → Verdict.
5. **The reveal.** The **folded transit** draws in — the messy stream collapses into one clean,
   U-shaped dip with the model curve through it. The **verdict badge** fades in (✅ Planet
   candidate), the **confidence meter** fills, and the **stat cards** count up (Period 3.52 d,
   Depth 8,400 ppm, Radius 1.3 R𝙅, …).
6. **Understand why.** They read the **DiagnosticsPanel** — each check green with a one-line
   reason — and hover the **(?)** on "Secondary eclipse" to learn what it means. They read the
   **plain-English narrative** and glance at the **SHAP bar**.
7. **Test their own.** They switch the input to **Search**, type **"Kepler-10"**, and hit
   **Analyze** — and watch ExoSeer detect a *tiny* rocky planet, proving sensitivity.
8. **Stress-test it.** They click **Open Injection Sandbox**, pick a quiet host, set a 2 R⊕ planet,
   and **Inject & recover** → ✅ Recovered. Then they drag **radius** down until it reads
   ✖ **Lost in the noise** — the detection limit, felt in the hand.
9. **See it say "no."** From the Gallery they open the **known eclipsing binary** → ExoSeer returns
   ⚠️ **Likely eclipsing binary**, pointing at the secondary eclipse. (Crucial: the tool isn't a
   yes-machine.)
10. **Take it with them.** Back in the console, they **Export the dossier** (PDF/JSON) or **Copy
    link** to share the candidate.

---

## 8. Microcopy & tooltips (the science, in human words)

Use these (or close paraphrases) for the diagnostic tooltips — they make ExoSeer feel expert *and*
teach the user:

- **Transit depth / SDE:** *"How much the star dims, and how confidently we see it above the noise.
  Higher is stronger."*
- **Odd–even depth:** *"We compare every other dip. If alternating dips have different depths, it's
  usually two stars eclipsing each other — not a planet."*
- **Secondary eclipse:** *"A second, shallower dip halfway around the orbit means a glowing
  companion is being blocked — a sign of an eclipsing binary, not a planet."*
- **Transit shape:** *"Planets make a flat-bottomed dip; a sharp V-shape often means a grazing
  pass or a stellar companion."*
- **Implied radius:** *"From how much the star dims and how big the star is, we estimate the
  object's size. Bigger than a few Jupiters and it's probably a star, not a planet."*
- **Verdict labels:** keep them honest — *Planet candidate* (never "planet discovered"),
  *Likely eclipsing binary*, *Stellar variability*, *Low confidence*, *No significant signal*.

Empty/edge states:
- No signal: *"No significant transit found in this data. Try another sector, or a different
  star."*
- MAST hiccup: *"Couldn't reach the archive just now. Try again, or explore a Gallery star
  (cached)."*
- Single transit: *"Only one dip seen — not enough to confirm a period. Treat as preliminary."*

---

## 9. The 3-minute judge demo script

Rehearse this. Pre-warm the MAST cache for every star you'll touch.

- **0:00 — Hook (15s).** Open the landing. *"Almost every planet humanity has found around another
  star was found by watching its star flicker. The catch: most flickers aren't planets. ExoSeer
  finds the flicker — and tells you whether it's real."* Click **Try a demo star.**
- **0:15 — Detection (35s).** Console shows the light curve. Toggle Raw→Detrended. *"This is real
  NASA data. There's the dimming, every few days — a planet crossing its star."* The folded transit
  draws in. *"Folded onto one orbit, the planet's shadow is unmistakable."*
- **0:50 — Vetting + explanation (45s).** *"But a dip alone isn't proof."* Walk the diagnostics —
  odd-even, secondary eclipse, shape, radius — green. Read the one-line narrative. *"ExoSeer
  doesn't just say 'planet' — it shows the evidence a scientist would check."*
- **1:35 — It says NO (30s).** Open the Gallery's eclipsing binary. *"Here's a famous impostor."*
  ExoSeer returns *Likely eclipsing binary* and points at the secondary eclipse. *"It caught the
  trap. The tool isn't a yes-machine."*
- **2:05 — The showstopper (40s).** Injection Sandbox. Inject a 2 R⊕ planet → Recovered. Drag the
  radius down live until it's *Lost in the noise.* *"This is the detection limit — and ExoSeer is
  honest about exactly where it lives."*
- **2:45 — Close (15s).** *"Real NASA data. Explainable AI. Zero infrastructure cost. We've put
  planet-hunting in anyone's browser."* — show the public URL.

---

## 10. What to build first (UI priority, mirrors AGENTS.md phases)

1. The **console center charts** + **stat cards** + the **stepper** (Phase 1) — this is 70% of the
   wow with the least code.
2. The **VerdictBadge + DiagnosticsPanel + ConfidenceMeter** (Phase 2).
3. The **ExplanationCard + ShapBar** (Phase 3).
4. The **Sandbox** (Phase 4).
5. The **landing hero + starfield + gallery + export + about** (Phase 5).

If you are ever short on time, a *complete console for one famous star with a clean folded transit
and a correct, explained verdict* beats a half-finished five-page app. Depth on the core beats
breadth.
