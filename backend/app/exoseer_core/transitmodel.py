"""Transit light-curve model + orbital geometry helpers.

Primary path uses `batman` (Mandel & Agol 2002, quadratic limb darkening) exactly
as the spec's injection sandbox requires. If batman is unavailable, we fall back
to a pure-numpy uniform-source Mandel & Agol occultation so the whole engine
(synthetic generation, injection sandbox) still runs with zero heavy deps.
Shared by ingest.py and inject.py to avoid a circular import.
"""
from __future__ import annotations

import numpy as np

# Physical constants (in solar / earth units).
RSUN_IN_REARTH = 109.076       # R_sun / R_earth
AU_IN_RSUN = 215.032           # 1 AU / R_sun
DAYS_PER_YEAR = 365.25

try:  # pragma: no cover - exercised at runtime depending on install
    import batman  # type: ignore

    _HAS_BATMAN = True
except Exception:  # noqa: BLE001
    _HAS_BATMAN = False


def has_batman() -> bool:
    return _HAS_BATMAN


def rp_rs_from_radii(radius_rearth: float, radius_rsun: float | None) -> float:
    """Planet/star radius ratio. Falls back to a Sun-like star if radius unknown."""
    r_star = radius_rsun if (radius_rsun and radius_rsun > 0) else 1.0
    return (radius_rearth / RSUN_IN_REARTH) / r_star


def a_over_rstar(period_days: float, mass_msun: float | None, radius_rsun: float | None) -> float:
    """Scaled semi-major axis a/R_star from Kepler's third law.

    a_AU^3 = P_yr^2 * M_star(Msun);  a/R_star = a_AU * (AU/Rsun) / R_star(Rsun).
    """
    m_star = mass_msun if (mass_msun and mass_msun > 0) else 1.0
    r_star = radius_rsun if (radius_rsun and radius_rsun > 0) else 1.0
    p_yr = period_days / DAYS_PER_YEAR
    a_au = (p_yr ** 2 * m_star) ** (1.0 / 3.0)
    return a_au * AU_IN_RSUN / r_star


def inclination_deg(a_rs: float, impact: float) -> float:
    """Orbital inclination from impact parameter b = (a/R_star) cos i."""
    a_rs = max(a_rs, 1.0 + 1e-6)
    cos_i = np.clip(impact / a_rs, 0.0, 1.0)
    return float(np.degrees(np.arccos(cos_i)))


def _uniform_mandel_agol(z: np.ndarray, p: float) -> np.ndarray:
    """Closed-form flux for a uniform (no limb-darkening) source. z = d / R_star."""
    z = np.asarray(z, dtype=float)
    flux = np.ones_like(z)
    p2 = p * p

    # Fully outside.
    outside = z >= 1.0 + p
    # Fully inside the stellar disk.
    inside = (z <= 1.0 - p) & (~outside)
    flux[inside] = 1.0 - p2

    # Partial overlap.
    partial = (~outside) & (~inside) & (z > abs(1.0 - p))
    zp = z[partial]
    if zp.size:
        k1 = np.arccos(np.clip((1.0 - p2 + zp ** 2) / (2.0 * zp), -1.0, 1.0))
        k0 = np.arccos(np.clip((p2 + zp ** 2 - 1.0) / (2.0 * p * zp), -1.0, 1.0))
        tri = np.sqrt(np.clip(4.0 * zp ** 2 - (1.0 + zp ** 2 - p2) ** 2, 0.0, None)) / 2.0
        lam = (p2 * k0 + k1 - tri) / np.pi
        flux[partial] = 1.0 - lam

    # Planet larger than star and fully covering (rare in our regime).
    engulf = (z <= p - 1.0)
    flux[engulf] = 0.0
    return flux


def transit_flux(
    time: np.ndarray,
    t0: float,
    period_days: float,
    rp_rs: float,
    a_rs: float,
    inc_deg: float,
    ecc: float = 0.0,
    omega_deg: float = 90.0,
    u1: float = 0.4,
    u2: float = 0.2,
) -> np.ndarray:
    """Return relative flux (baseline 1.0) for a transiting planet.

    Uses batman with quadratic limb darkening when available; otherwise a
    uniform-source analytic occultation (still U-shaped / flat-bottomed for
    small planets, V-shaped for grazing geometries — the features vetting needs).
    """
    time = np.asarray(time, dtype=float)
    if rp_rs <= 0 or period_days <= 0:
        return np.ones_like(time)

    if _HAS_BATMAN:
        params = batman.TransitParams()
        params.t0 = t0
        params.per = period_days
        params.rp = rp_rs
        params.a = a_rs
        params.inc = inc_deg
        params.ecc = ecc
        params.w = omega_deg
        params.u = [u1, u2]
        params.limb_dark = "quadratic"
        model = batman.TransitModel(params, time)
        return np.asarray(model.light_curve(params), dtype=float)

    # --- numpy fallback: sky-projected separation then uniform-disk occultation.
    phase = 2.0 * np.pi * (time - t0) / period_days
    inc = np.radians(inc_deg)
    # Distance of planet from star centre in the sky plane, in units of R_star.
    z = a_rs * np.sqrt(np.sin(phase) ** 2 + (np.cos(inc) * np.cos(phase)) ** 2)
    # Only the transiting half of the orbit (planet in front of the star).
    in_front = np.cos(phase) > 0
    flux = np.ones_like(time)
    flux[in_front] = _uniform_mandel_agol(z[in_front], rp_rs)
    return flux
