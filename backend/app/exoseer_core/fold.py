"""Phase-fold the detrended curve and build the hero folded-transit chart data.

Produces the folded scatter (downsampled for payload size), a binned overlay
(~200 bins), and a best-fit model curve computed from the measured depth and
duration via transitmodel — so the overlay is always available regardless of
which search library ran.
"""
from __future__ import annotations

import numpy as np

from . import transitmodel
from .types import DetectionResult, FoldResult, Preprocessed, ProgressFn, noop_progress

_MAX_SCATTER = 6000
_N_BINS = 200
_RNG = np.random.default_rng(42)


def fold(
    pre: Preprocessed,
    det: DetectionResult,
    on_progress: ProgressFn = noop_progress,
) -> FoldResult:
    on_progress("folding", 0.2)
    period = det.period_days or 1.0
    t0 = det.t0 or 0.0
    time, flux = pre.time, pre.flux_flat

    phase = ((time - t0 + 0.5 * period) % period) / period - 0.5

    # Downsample the scatter cloud (keep full data upstream; this is display only).
    if phase.size > _MAX_SCATTER:
        sel = _RNG.choice(phase.size, _MAX_SCATTER, replace=False)
        sel.sort()
        phase_s, flux_s = phase[sel], flux[sel]
    else:
        phase_s, flux_s = phase, flux

    # Binned overlay (median per bin, robust to outliers).
    edges = np.linspace(-0.5, 0.5, _N_BINS + 1)
    idx = np.clip(np.digitize(phase, edges) - 1, 0, _N_BINS - 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    binned_flux = np.full(_N_BINS, np.nan)
    for b in range(_N_BINS):
        m = idx == b
        if m.any():
            binned_flux[b] = np.median(flux[m])
    keep = np.isfinite(binned_flux)
    phase_binned, flux_binned = centers[keep], binned_flux[keep]

    on_progress("folding", 0.7)

    # Model overlay from measured depth + duration (self-consistent, always available).
    depth = det.depth or 0.0
    rp_rs = float(np.sqrt(depth)) if depth > 0 else 0.0
    duration_days = (det.duration_hours or 0.0) / 24.0
    if duration_days > 0:
        a_rs = max(period / (np.pi * duration_days), 2.0)
    else:
        a_rs = 10.0
    model_phase = np.linspace(-0.5, 0.5, 1000)
    model_time = model_phase * period  # t - t0 in days
    model_flux = transitmodel.transit_flux(
        model_time, t0=0.0, period_days=period, rp_rs=rp_rs, a_rs=a_rs, inc_deg=90.0
    )

    det.model_phase = model_phase
    det.model_flux = model_flux
    on_progress("folding", 1.0)
    return FoldResult(
        phase=phase_s,
        flux=flux_s,
        phase_binned=phase_binned,
        flux_binned=flux_binned,
        model_phase=model_phase,
        model_flux=model_flux,
    )
