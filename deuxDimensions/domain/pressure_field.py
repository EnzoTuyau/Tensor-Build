"""
Champ scalaire pour la carte thermique / pression sur un bloc 2D.

Le rendu combine :
- une estimation RDM de la contrainte normale selon la hauteur :
  sigma_normale(y) = sigma_axial + M * z' / I  (z' depuis la fibre neutre horizontale) ;
- une contribution pédagogique liée à la pression surfacique ``bloc[\"pressure\"]`` :
  intensité maximale en tête du bloc et décroissance linéaire vers la base.

La valeur affichée est en Pa (contrainte et ordre de grandeur pression).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def scalar_field_for_heatmap(
    bloc: dict[str, Any],
    stress: dict[str, Any],
    *,
    y_coin_bas: float,
    h: float,
    nx: int,
    ny: int,
) -> np.ndarray:
    """
    Matrice (ny, nx) : |sigma_normale(y)| + charge répartie modélisée (Pa).

    **Modèle pédagogique** : rampe liée à ``pressure`` (max en tête du bloc).
    **Données RDM** : ``stress`` (sigma_axial) et ``moment`` du bloc pour la flexion.

    Ligne iy=0 correspond au bas du bloc (``origin='lower'`` pour imshow).
    """
    w = float(bloc["largeur"])
    h = max(float(h), 1e-9)
    nx = max(2, nx)
    ny = max(2, ny)

    sigma_axial = float(stress.get("sigma_axial", 0.0))
    moment = float(bloc.get("moment", 0.0))
    p_surf = float(bloc.get("pressure", 0.0))

    i_local = (w * h**3) / 12.0
    iy = np.arange(ny, dtype=np.float64)
    y_cell = y_coin_bas + (iy + 0.5) / ny * h
    y_neutre = y_coin_bas + h / 2.0
    z_prime = y_cell - y_neutre
    if i_local > 1e-30:
        sigma_norm = sigma_axial + moment * z_prime / i_local
    else:
        sigma_norm = np.full(ny, sigma_axial, dtype=np.float64)

    ramp = (iy + 0.5) / ny
    surf_term = p_surf * ramp

    col = np.abs(sigma_norm) + surf_term
    field_1d = col.astype(np.float64)
    return np.broadcast_to(field_1d[:, np.newaxis], (ny, nx)).copy()
