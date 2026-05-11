"""Champ Pa pour la carte bloc : sigma_axial, rampe pression, pics gaussiens sur F_z / F_x."""

from __future__ import annotations

from typing import Any

import numpy as np

from deuxDimensions.domain.geometry import largeur_bloc


def scalar_field_for_heatmap(
    bloc: dict[str, Any],
    stress: dict[str, Any],
    *,
    h: float,
    nx: int,
    ny: int,
) -> np.ndarray:
    """Matrice (ny, nx) en Pa ; ligne 0 = bas du bloc. ``stress`` fournit surtout sigma_axial."""
    w = largeur_bloc(bloc)
    h = max(float(h), 1e-9)
    nx = max(2, nx)
    ny = max(2, ny)

    sigma_axial = float(stress.get("sigma_axial", 0.0))
    p_surf = float(bloc.get("pressure", 0.0))
    f_ext = float(bloc.get("ext_force", 0.0))
    f_ext_x = float(bloc.get("ext_force_x", 0.0))
    x_offset = float(bloc.get("ext_force_x_offset", 0.5))
    y_offset = float(bloc.get("ext_force_x_y_offset", 0.5))
    side = str(bloc.get("ext_force_x_side", "left"))

    iy = np.arange(ny, dtype=np.float64)
    sigma_norm = np.full(ny, sigma_axial, dtype=np.float64)

    ramp = (iy + 0.5) / ny
    surf_term = p_surf * ramp

    col = np.abs(sigma_norm) + surf_term
    field = np.broadcast_to(col.astype(np.float64)[:, np.newaxis], (ny, nx)).copy()

    # Noyaux gaussiens sur les points d’application (~ tiers de la petite dimension).
    if abs(f_ext) > 1e-6 or abs(f_ext_x) > 1e-6:
        ix_norm = (np.arange(nx, dtype=np.float64) + 0.5) / nx
        iy_norm = (np.arange(ny, dtype=np.float64) + 0.5) / ny
        Xn, Yn = np.meshgrid(ix_norm, iy_norm)  # coords normalisées 0–1
        scale = max(min(w, h), 1e-3)
        sigma_kernel = 0.35 * scale
        # Section 1 m (comme calculs)
        section = max(w, 1e-6)

        if abs(f_ext) > 1e-6:
            # F_z en tête : x normalisé = x_offset
            dx_m = (Xn - x_offset) * w
            dy_m = (Yn - 1.0) * h  # haut → bas
            d_fz = np.hypot(dx_m, dy_m)
            kernel_fz = np.exp(-((d_fz / sigma_kernel) ** 2))
            field += (abs(f_ext) / section) * kernel_fz

        if abs(f_ext_x) > 1e-6:
            x_cote = 0.0 if side == "left" else 1.0
            dx_m = (Xn - x_cote) * w
            dy_m = (Yn - y_offset) * h  # F_x : hauteur normalisée y_offset
            d_fx = np.hypot(dx_m, dy_m)
            kernel_fx = np.exp(-((d_fx / sigma_kernel) ** 2))
            field += (abs(f_ext_x) / section) * kernel_fx

    return field
