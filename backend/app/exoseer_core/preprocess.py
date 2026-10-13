"""Clean, normalize, and detrend a light curve (AGENTS.md §7.2).

Keeps BOTH the normalized curve (stellar variability visible) and the flattened
curve (detrended, transits preserved) — the UI shows both. Uses lightkurve's
Savitzky-Golay flatten when available; falls back to scipy so preprocessing
never blocks on the astro stack.
"""
from __future__ import annotations

import numpy as np

from .types import LightCurve, Preprocessed, ProgressFn, noop_progress

_WINDOW = 401
_POLYORDER = 2
_BREAK_TOLERANCE = 5
_SIGMA_UPPER = 5.0     # clip flares / positive outliers only


def _odd_window(n: int, target: int = _WINDOW) -> int:
    w = min(target, n - 1 if n % 2 == 0 else n)
    if w < 5:
        w = 5
    if w % 2 == 0:
        w -= 1
    return max(w, 5)


def _flatten_lightkurve(time: np.ndarray, flux: np.ndarray):
    import lightkurve as lk

    lc = lk.LightCurve(time=time, flux=flux).normalize()
    flat = lc.flatten(
        window_length=_odd_window(time.size),
        polyorder=_POLYORDER,
        break_tolerance=_BREAK_TOLERANCE,
    )
    return np.asarray(lc.flux.value, dtype=float), np.asarray(flat.flux.value, dtype=float)


def _flatten_scipy(flux_norm: np.ndarray) -> np.ndarray:
    from scipy.signal import savgol_filter

    win = _odd_window(flux_norm.size)
    trend = savgol_filter(flux_norm, window_length=win, polyorder=_POLYORDER, mode="interp")
    trend = np.where(np.abs(trend) < 1e-6, 1.0, trend)
    return flux_norm / trend


def preprocess(lc: LightCurve, on_progress: ProgressFn = noop_progress) -> Preprocessed:
    on_progress("detrending", 0.1)

    time, flux = lc.time, lc.flux
    good = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[good], flux[good]
    if time.size < 100:
        # Still return something usable rather than crashing the job.
        med = np.nanmedian(flux) if flux.size else 1.0
        fn = flux / med if med else flux
        return Preprocessed(time, fn, fn.copy(), 0.0, 0.0, {"warning": "very few points"})

    order = np.argsort(time)
    time, flux = time[order], flux[order]

    med = np.median(flux)
    flux_norm = flux / med if med else flux

    on_progress("detrending", 0.4)
    try:
        flux_norm, flux_flat = _flatten_lightkurve(time, flux)
    except Exception:  # noqa: BLE001 - fall back to scipy-only detrending
        flux_flat = _flatten_scipy(flux_norm)

    # Transit-safe sigma clipping: clip only POSITIVE outliers (flares/cosmic
    # rays). Transits are dips — the signal — so we never clip below the
    # baseline, only guard against absurd/non-physical negative spikes.
    on_progress("detrending", 0.75)
    resid = flux_flat - np.median(flux_flat)
    std = 1.4826 * np.median(np.abs(resid)) or np.std(resid) or 1.0
    keep = (resid < _SIGMA_UPPER * std) & np.isfinite(flux_flat) & (flux_flat > 0.0)
    time, flux_norm, flux_flat = time[keep], flux_norm[keep], flux_flat[keep]

    dt = np.diff(time)
    cadence = float(np.median(dt)) if dt.size else 0.0
    baseline = float(time[-1] - time[0]) if time.size else 0.0

    on_progress("detrending", 1.0)
    return Preprocessed(
        time=time,
        flux_norm=flux_norm,
        flux_flat=flux_flat,
        cadence_days=cadence,
        baseline_days=baseline,
        meta={**lc.meta, "n_points": int(time.size)},
    )
