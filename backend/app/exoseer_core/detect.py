"""Transit detection: Transit Least Squares (primary) + Box Least Squares (cross-check).

TLS (Hippke & Heller 2019) is the primary search because it uses a realistic
limb-darkened transit template, giving better SDE and odd/even statistics than a
box. BLS (astropy) is an independent cross-check on the period; disagreement
beyond aliasing flags the period as ambiguous. A pure-numpy BLS is kept as a
last-resort fallback so detection runs even without the astro stack.
"""
from __future__ import annotations

import numpy as np

from .. import config
from .types import DetectionResult, Preprocessed, ProgressFn, noop_progress

_MAX_SEARCH_POINTS = 12000   # decimate the search array above this (perf guard)


# --- depth measured from the data (avoids library depth-convention ambiguity) ---
def measure_transit_depth(
    time: np.ndarray, flux: np.ndarray, period: float, t0: float, duration_days: float
) -> tuple[float, float, int]:
    """Return (depth_fraction, snr, n_transits) measured directly from the curve."""
    if period <= 0 or duration_days <= 0:
        return 0.0, 0.0, 0
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    half = 0.5 * duration_days
    in_tr = np.abs(phase) < half
    out_tr = np.abs(phase) > 2.0 * half
    if in_tr.sum() < 3 or out_tr.sum() < 10:
        return 0.0, 0.0, int(in_tr.sum())
    f_out = np.median(flux[out_tr])
    f_in = np.median(flux[in_tr])
    depth = max(f_out - f_in, 0.0)
    scatter = 1.4826 * np.median(np.abs(flux[out_tr] - f_out)) or np.std(flux[out_tr]) or 1e-9
    snr = depth / (scatter / np.sqrt(max(in_tr.sum(), 1)))
    # Count distinct transits covered by the baseline.
    n_epochs = int(round((time.max() - t0) / period)) - int(round((time.min() - t0) / period)) + 1
    return float(depth), float(snr), max(n_epochs, 1)


def _bls_astropy(time: np.ndarray, flux: np.ndarray, pmin: float, pmax: float) -> float | None:
    try:
        from astropy.timeseries import BoxLeastSquares

        durations = np.linspace(0.05, 0.3, 8)
        model = BoxLeastSquares(time, flux)
        res = model.autopower(
            durations, minimum_period=pmin, maximum_period=pmax, oversample=5
        )
        return float(np.asarray(res.period)[int(np.argmax(res.power))])
    except Exception:  # noqa: BLE001
        return None


def _bls_numpy(time: np.ndarray, flux: np.ndarray, pmin: float, pmax: float) -> tuple[float, float]:
    """Minimal BLS: scan a coarse period grid, score best box dip. Returns (period, sde)."""
    periods = np.geomspace(max(pmin, 0.3), max(pmax, pmin + 1.0), 1500)
    resid = flux - np.median(flux)
    powers = np.empty_like(periods)
    for i, p in enumerate(periods):
        phase = (time % p) / p
        nb = 50
        idx = np.clip((phase * nb).astype(int), 0, nb - 1)
        sums = np.bincount(idx, weights=resid, minlength=nb)
        counts = np.bincount(idx, minlength=nb).astype(float)
        counts[counts == 0] = np.nan
        means = sums / counts
        powers[i] = np.nanmin(means)  # deepest bin (most negative)
    powers = -powers  # deeper -> larger
    best = int(np.argmax(powers))
    sde = float((powers[best] - np.nanmean(powers)) / (np.nanstd(powers) or 1.0))
    return float(periods[best]), sde


def _is_alias(p1: float, p2: float, tol: float = 0.02) -> bool:
    if p1 <= 0 or p2 <= 0:
        return False
    for ratio in (1.0, 2.0, 0.5, 3.0, 1 / 3):
        if abs(p1 / p2 - ratio) < tol * max(ratio, 1.0):
            return True
    return False


def detect(
    pre: Preprocessed,
    sde_threshold: float = 7.0,
    period_min: float = 0.5,
    period_max: float = 50.0,
    on_progress: ProgressFn = noop_progress,
) -> DetectionResult:
    time = pre.time          # full curve (depth, transit count, vetting)
    flux = pre.flux_flat
    on_progress("searching", 0.05)

    # Search on a capped baseline for speed; TLS cost scales with baseline.
    cap = config.SEARCH_BASELINE_DAYS
    if pre.baseline_days > cap * 1.2:
        smask = time <= (time.min() + cap)
        ts, fs = time[smask], flux[smask]
        search_baseline = cap
    else:
        ts, fs = time, flux
        search_baseline = pre.baseline_days

    # Decimate the search array so short-cadence data (e.g. Kepler 1-min, ~130k
    # pts/quarter) doesn't blow up TLS. Transits last hours, so ~10-30 min
    # effective sampling is plenty. Full curve is untouched for depth/vetting.
    if ts.size > _MAX_SEARCH_POINTS:
        stride = int(np.ceil(ts.size / _MAX_SEARCH_POINTS))
        ts, fs = ts[::stride], fs[::stride]

    pmax = float(min(period_max, max(search_baseline / 2.0, period_min + 1.0)))
    pmin = float(max(period_min, 3.0 * pre.cadence_days)) if pre.cadence_days else period_min

    # Independent BLS period first (cheap, used as cross-check).
    bls_period = _bls_astropy(ts, fs, pmin, pmax)

    # --- Primary: Transit Least Squares ------------------------------------
    result: DetectionResult | None = None
    try:
        from transitleastsquares import transitleastsquares

        on_progress("searching", 0.2)
        model = transitleastsquares(ts, fs)
        r = model.power(
            period_min=pmin,
            period_max=pmax,
            oversampling_factor=2,   # 2 keeps the demo search ~10-40s (3 is slower)
            duration_grid_step=1.15,
            use_threads=1,           # >1 spawns multiprocessing.Pool -> hangs on macOS/threadpool
            show_progress_bar=False,
        )
        on_progress("searching", 0.85)

        period = float(r.period)
        t0 = float(r.T0)
        duration_days = float(r.duration)
        sde = float(r.SDE)
        depth, snr_data, n_tr = measure_transit_depth(time, flux, period, t0, duration_days)
        snr = float(getattr(r, "snr", snr_data) or snr_data)
        fap = float(getattr(r, "FAP", np.nan))
        odd_even = getattr(r, "odd_even_mismatch", None)
        try:
            n_transits = int(getattr(r, "distinct_transit_count", 0)) or n_tr
        except Exception:  # noqa: BLE001
            n_transits = n_tr
        transit_times = list(np.asarray(getattr(r, "transit_times", []), dtype=float))
        rp_rs = float(np.sqrt(depth)) if depth > 0 else float(getattr(r, "rp_rs", 0.0) or 0.0)

        result = DetectionResult(
            found=sde >= sde_threshold,
            period_days=period,
            t0=t0,
            duration_hours=duration_days * 24.0,
            depth=depth,
            depth_ppm=depth * 1e6,
            sde=sde,
            fap=None if np.isnan(fap) else fap,
            snr=snr,
            n_transits=n_transits,
            rp_rs=rp_rs,
            odd_even_mismatch=float(odd_even) if odd_even is not None else None,
            bls_period_days=bls_period,
            transit_times=transit_times,
            method="tls",
        )
    except Exception:  # noqa: BLE001 - TLS unavailable or failed; fall back to BLS
        result = None

    # --- Fallback: BLS as primary -----------------------------------------
    if result is None:
        on_progress("searching", 0.5)
        period = bls_period
        sde_est = 0.0
        if period is None:
            period, sde_est = _bls_numpy(ts, fs, pmin, pmax)
        else:
            _, sde_est = _bls_numpy(ts, fs, pmin, pmax)
        # Estimate duration ~ 0.05 * period, then refine via depth measurement.
        duration_days = 0.06 * period
        depth, snr, n_tr = measure_transit_depth(time, flux, period, time.min(), duration_days)
        result = DetectionResult(
            found=sde_est >= sde_threshold,
            period_days=float(period),
            t0=float(time.min()),
            duration_hours=duration_days * 24.0,
            depth=depth,
            depth_ppm=depth * 1e6,
            sde=float(sde_est),
            fap=None,
            snr=float(snr),
            n_transits=n_tr,
            rp_rs=float(np.sqrt(depth)) if depth > 0 else 0.0,
            odd_even_mismatch=None,
            bls_period_days=bls_period,
            transit_times=[],
            method="bls",
        )

    # --- Period ambiguity cross-check -------------------------------------
    if result.period_days and bls_period:
        rel = abs(result.period_days - bls_period) / result.period_days
        if rel > 0.01 and not _is_alias(result.period_days, bls_period):
            result.period_ambiguous = True

    on_progress("searching", 1.0)
    return result
