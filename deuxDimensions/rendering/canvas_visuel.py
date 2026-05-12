"""Couleurs, hit-test écran et colormap pour le canvas 2D."""

from __future__ import annotations

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from deuxDimensions.domain.constantes import CONTACT_STRESS_REF_PA, UTIL_PHASE_ALERT_PCT, UTIL_PHASE_OK_PCT


def bleu_plasma_cmap():
    """« Plasma » tronqué vers les bleus."""
    base = cm.get_cmap("plasma", 256)
    return mcolors.ListedColormap(base(np.linspace(0.0, 0.52, 256)))


def _hex_vers_rgb(h: str) -> tuple[float, float, float]:
    """``#RRGGBB`` → RVB 0..1."""
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _rgb_vers_hex(rgb: tuple[float, float, float]) -> str:
    """RVB 0..1 → ``#rrggbb``."""
    return "#" + "".join(f"{int(round(max(0.0, min(1.0, x)) * 255)):02x}" for x in rgb)


def melanger_hex(ca: str, cb: str, t: float) -> str:
    """Mélange linéaire deux hex ; ``t`` = part de ``cb``."""
    t = max(0.0, min(1.0, t))
    a = _hex_vers_rgb(ca)
    b = _hex_vers_rgb(cb)
    return _rgb_vers_hex(tuple(a[i] * (1 - t) + b[i] * t for i in range(3)))


def teintes_face_et_contour_selon_util(face_hex: str, edge_hex: str, util_pct: float) -> tuple[str, str]:
    """Face + contour selon utilisation uniaxiale (%)."""
    if util_pct < UTIL_PHASE_OK_PCT:
        return face_hex, edge_hex
    if util_pct < UTIL_PHASE_ALERT_PCT:
        span = UTIL_PHASE_ALERT_PCT - UTIL_PHASE_OK_PCT
        t = (util_pct - UTIL_PHASE_OK_PCT) / span if span > 0 else 1.0
        return (
            melanger_hex(face_hex, "#ffe0b2", min(1.0, t * 0.5)),
            melanger_hex(edge_hex, "#ef6c00", min(1.0, t * 1.1)),
        )
    span = 40.0
    t = min(1.0, max(0.0, (util_pct - UTIL_PHASE_ALERT_PCT) / span))
    return (
        melanger_hex(face_hex, "#ffcdd2", 0.35 + 0.45 * t),
        melanger_hex(edge_hex, "#c62828", 0.75 + 0.25 * t),
    )


def teinte_contour_contrainte(ec_base: str, util_pct: float) -> str:
    """Contour seul ; mêmes seuils que teintes_face_et_contour_selon_util."""
    if util_pct < UTIL_PHASE_OK_PCT:
        return ec_base
    if util_pct < UTIL_PHASE_ALERT_PCT:
        t = (util_pct - UTIL_PHASE_OK_PCT) / (UTIL_PHASE_ALERT_PCT - UTIL_PHASE_OK_PCT)
        return melanger_hex(ec_base, "#ef6c00", min(1.0, t * 1.2))
    t = min(1.0, (util_pct - UTIL_PHASE_ALERT_PCT) / 25.0)
    return melanger_hex(ec_base, "#b71c1c", 0.85 + 0.15 * t)


def distance_px_point_au_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Distance px du point au segment AB."""
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-18:
        return float(np.hypot(px - ax, py - ay))
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    qx, qy = ax + t * abx, ay + t * aby
    return float(np.hypot(px - qx, py - qy))


def ratio_effort_contact_visuel(f_axial: float, largeur: float, hb: float, ht: float) -> float:
    """0..1 pour teinte joint ; estimation F/A vs CONTACT_STRESS_REF_PA."""
    aire = max(largeur * min(hb, ht), 1e-9)
    sigma_est = abs(f_axial) / aire
    return float(max(0.0, min(1.0, sigma_est / CONTACT_STRESS_REF_PA)))


def vider_serie_artists(serie):
    """``remove()`` sur chaque artiste puis ``clear()``."""
    for artiste in list(serie):
        try:
            artiste.remove()
        except Exception:
            pass
    serie.clear()
