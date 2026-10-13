"""Ingest light curves from NASA MAST (via lightkurve), CSV upload, or synthesis.

The frontend never talks to MAST; only this module does. Downloads are cached on
disk keyed by target+mission so the demo never re-downloads (pre-warm with
`make warm`). All failures raise IngestError with a user-friendly message.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from .types import IngestError, LightCurve, ProgressFn, noop_progress

_MAX_PRODUCTS = 2   # cap stitched sectors/quarters to bound download+search time.
                    # TLS's period-grid density scales with baseline, so fewer
                    # quarters keeps the search ~10-40s; 2 quarters still give
                    # tens of transits for the short-period gallery planets.


def _cache_key(target: str, mission: Optional[str], seq: Optional[int]) -> str:
    raw = f"{target.strip().lower()}|{(mission or 'auto').lower()}|{seq if seq is not None else 'all'}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_paths(key: str) -> tuple[Path, Path]:
    return config.CACHE_DIR / f"{key}.npz", config.CACHE_DIR / f"{key}.json"


def _load_cache(key: str) -> Optional[LightCurve]:
    npz, meta = _cache_paths(key)
    if npz.exists() and meta.exists():
        try:
            d = np.load(npz)
            m = json.loads(meta.read_text())
            return LightCurve(
                time=d["time"],
                flux=d["flux"],
                flux_err=d["flux_err"] if "flux_err" in d and d["flux_err"].size else None,
                meta=m,
            )
        except Exception:  # noqa: BLE001 - corrupt cache -> re-fetch
            return None
    return None


def _save_cache(key: str, lc: LightCurve) -> None:
    npz, meta = _cache_paths(key)
    try:
        np.savez_compressed(
            npz,
            time=lc.time,
            flux=lc.flux,
            flux_err=lc.flux_err if lc.flux_err is not None else np.array([]),
        )
        meta.write_text(json.dumps(lc.meta))
    except Exception:  # noqa: BLE001 - caching is best-effort
        pass


def from_mast(
    target: str,
    mission: Optional[str] = None,
    sector_or_quarter: Optional[int] = None,
    on_progress: ProgressFn = noop_progress,
) -> LightCurve:
    """Download and stitch a light curve for `target` from MAST via lightkurve.

    Prefers PDCSAP flux. Accepts names ("Kepler-10"), KIC/TIC IDs, TOI numbers.
    """
    if not target or not target.strip():
        raise IngestError("Please enter a star name or ID.")
    target = target.strip()
    key = _cache_key(target, mission, sector_or_quarter)

    cached = _load_cache(key)
    if cached is not None:
        on_progress("fetching", 1.0)
        cached.meta.setdefault("from_cache", True)
        return cached

    try:
        import lightkurve as lk  # lazy: keeps the engine importable without it
    except Exception as exc:  # noqa: BLE001
        raise IngestError(
            "The MAST client (lightkurve) is not installed on the server; "
            "try a Gallery star or upload a CSV."
        ) from exc

    on_progress("fetching", 0.1)
    try:
        search = lk.search_lightcurve(target, mission=mission) if mission else lk.search_lightcurve(target)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(
            "Couldn't reach the archive just now. Try again, or explore a Gallery star (cached)."
        ) from exc

    if search is None or len(search) == 0:
        raise IngestError(
            f"No light curve found for “{target}”. Check the name/ID, or pick a Gallery star."
        )

    # Optional sector/quarter filter (best-effort across mission column names).
    if sector_or_quarter is not None:
        try:
            tbl = search.table
            for col in ("sequence_number", "sector", "quarter", "campaign"):
                if col in tbl.colnames:
                    mask = np.asarray(tbl[col]) == sector_or_quarter
                    if mask.any():
                        search = search[mask]
                        break
        except Exception:  # noqa: BLE001
            pass

    # Prefer long cadence: far fewer points (Kepler LC ~30 min vs SC ~1 min),
    # so the search is fast and the download small. Filter to the max exptime.
    try:
        tbl = search.table
        if "exptime" in tbl.colnames and len(search) > 1:
            expt = np.asarray(tbl["exptime"], dtype=float)
            long_mask = expt >= (np.nanmax(expt) - 1.0)
            if long_mask.any() and long_mask.sum() < len(search):
                search = search[long_mask]
    except Exception:  # noqa: BLE001
        pass

    # Bound the demo: cap the number of downloaded products.
    if len(search) > _MAX_PRODUCTS:
        search = search[:_MAX_PRODUCTS]

    on_progress("fetching", 0.35)
    try:
        collection = search.download_all(quality_bitmask="default")
    except Exception:  # noqa: BLE001
        try:
            single = search[0].download(quality_bitmask="default")
            collection = None
        except Exception as exc:  # noqa: BLE001
            raise IngestError(
                "Download from the archive failed. Try again or use a Gallery star."
            ) from exc
    else:
        single = None

    on_progress("fetching", 0.8)
    try:
        if collection is not None and len(collection) > 0:
            lc = collection.stitch()          # normalizes each then concatenates
        elif single is not None:
            lc = single.normalize()
        else:
            raise IngestError(f"No usable data returned for “{target}”.")

        lc = lc.remove_nans()
        time = np.asarray(lc.time.value, dtype=float)
        flux = np.asarray(lc.flux.value, dtype=float)
        try:
            flux_err = np.asarray(lc.flux_err.value, dtype=float)
        except Exception:  # noqa: BLE001
            flux_err = None

        # Detected mission label for the dossier.
        detected_mission = mission
        try:
            detected_mission = str(lc.meta.get("MISSION") or lc.meta.get("TELESCOP") or mission or "")
        except Exception:  # noqa: BLE001
            pass
    except IngestError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IngestError("Failed to parse the downloaded light curve.") from exc

    if time.size < 200:
        raise IngestError(f"Too few valid points for “{target}” to search reliably.")

    result = LightCurve(
        time=time,
        flux=flux,
        flux_err=flux_err,
        meta={"target": target, "mission": detected_mission, "n_products": len(search)},
    )
    _save_cache(key, result)
    on_progress("fetching", 1.0)
    return result


def from_csv(raw: bytes | str, on_progress: ProgressFn = noop_progress) -> LightCurve:
    """Parse an uploaded CSV with columns time, flux[, flux_err]."""
    on_progress("fetching", 0.2)
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001
        raise IngestError("Could not parse the CSV. Expected columns: time, flux[, flux_err].") from exc

    # Normalize column names.
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return cols[n]
        return None

    t_col = pick("time", "t", "bjd", "btjd", "jd", "days")
    f_col = pick("flux", "f", "pdcsap_flux", "sap_flux", "brightness", "relative_flux")
    e_col = pick("flux_err", "err", "error", "flux_error", "sigma")
    if t_col is None or f_col is None:
        raise IngestError("CSV must contain at least 'time' and 'flux' columns.")

    time = pd.to_numeric(df[t_col], errors="coerce").to_numpy(dtype=float)
    flux = pd.to_numeric(df[f_col], errors="coerce").to_numpy(dtype=float)
    flux_err = (
        pd.to_numeric(df[e_col], errors="coerce").to_numpy(dtype=float) if e_col else None
    )

    good = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[good], flux[good]
    if flux_err is not None:
        flux_err = flux_err[good]

    if time.size < 500:
        raise IngestError("Upload rejected: need at least 500 valid rows to search for transits.")

    order = np.argsort(time)
    time, flux = time[order], flux[order]
    if flux_err is not None:
        flux_err = flux_err[order]

    # Reject grossly non-monotonic / duplicated timestamps.
    if np.any(np.diff(time) <= 0):
        keep = np.concatenate(([True], np.diff(time) > 0))
        time, flux = time[keep], flux[keep]
        if flux_err is not None:
            flux_err = flux_err[keep]
    if time.size < 500:
        raise IngestError("After cleaning, too few unique timestamps remain (need ≥ 500).")

    on_progress("fetching", 1.0)
    return LightCurve(
        time=time, flux=flux, flux_err=flux_err, meta={"target": "Uploaded CSV", "mission": "user"}
    )


def synthetic(host, planet, noise, on_progress: ProgressFn = noop_progress) -> LightCurve:
    """Generate a synthetic light curve (a quiet host + injected planet + noise).

    Delegates to inject.py (imported lazily to avoid a circular import).
    """
    from .inject import make_synthetic_lightcurve

    return make_synthetic_lightcurve(host, planet, noise, on_progress=on_progress, prefer_real=False)


def looks_like_tic(target: str) -> bool:
    return bool(re.match(r"^\s*(tic\s*)?\d{5,}\s*$", target.lower()))
