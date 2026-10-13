"""Host-star parameters (radius, Teff, logg, mass) via astroquery.

Used to convert transit depth into an implied planet radius. Order:
1. A small vendored table of literature values for the gallery stars (so demos
   work with zero network and are exact).
2. A best-effort astroquery TIC lookup (cached on disk).
3. Empty params -> caller marks radius "indeterminate" and proceeds (never crash).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .. import config
from .types import StellarParams

# --- Vendored literature values for gallery / common hosts -----------------
_KNOWN: dict[str, StellarParams] = {
    "kepler-8": StellarParams(1.486, 6213, 4.28, 1.213, "literature"),
    "kepler-10": StellarParams(1.065, 5627, 4.34, 0.910, "literature"),
    "kepler-90": StellarParams(1.200, 6080, 4.30, 1.130, "literature"),
    "kepler-11": StellarParams(1.065, 5680, 4.30, 0.961, "literature"),
    "kepler-16": StellarParams(0.649, 4450, 4.65, 0.690, "literature"),
    "trappist-1": StellarParams(0.119, 2566, 5.24, 0.089, "literature"),
    "kepler-7": StellarParams(1.966, 5933, 3.98, 1.360, "literature"),
    "kepler-6": StellarParams(1.391, 5647, 4.24, 1.209, "literature"),
    "hat-p-7": StellarParams(1.840, 6350, 4.02, 1.470, "literature"),
    "kic 9246715": StellarParams(4.900, 5030, 3.10, 2.170, "literature"),  # red-giant EB
}


def _normalize(target: str) -> str:
    t = target.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "_", key)
    return config.CACHE_DIR / f"stellar_{safe}.json"


def _load_cache(key: str) -> Optional[StellarParams]:
    p = _cache_path(key)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            return StellarParams(**d)
        except Exception:  # noqa: BLE001
            return None
    return None


def _save_cache(key: str, sp: StellarParams) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps(
                {
                    "radius_rsun": sp.radius_rsun,
                    "teff": sp.teff,
                    "logg": sp.logg,
                    "mass_msun": sp.mass_msun,
                    "source": sp.source,
                }
            )
        )
    except Exception:  # noqa: BLE001
        pass


def _clean(v) -> Optional[float]:
    try:
        import numpy as np

        f = float(v)
        return None if (np.isnan(f) or f <= 0) else f
    except Exception:  # noqa: BLE001
        return None


def _query_tic(target: str) -> Optional[StellarParams]:
    try:
        from astroquery.mast import Catalogs

        cat = Catalogs.query_object(target, catalog="TIC", radius=0.02)
        if cat is None or len(cat) == 0:
            return None
        row = cat[0]  # nearest match
        return StellarParams(
            radius_rsun=_clean(row["rad"]),
            teff=_clean(row["Teff"]),
            logg=_clean(row["logg"]),
            mass_msun=_clean(row["mass"]),
            source="TIC",
        )
    except Exception:  # noqa: BLE001
        return None


def lookup(target: str, mission: Optional[str] = None) -> StellarParams:
    key = _normalize(target)
    if key in _KNOWN:
        return _KNOWN[key]

    cached = _load_cache(key)
    if cached is not None:
        return cached

    sp = _query_tic(target)
    if sp is not None and sp.radius_rsun:
        _save_cache(key, sp)
        return sp

    return StellarParams(source="indeterminate")
