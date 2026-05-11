"""Geometrie 2D partagee (rectangles axis-alignes comme polygones)."""

from __future__ import annotations

from typing import Any

import numpy as np


def largeur_bloc(bloc: dict[str, Any]) -> float:
    """Largeur (m) : clé canonique ``w``, alias historique ``largeur``."""
    if "largeur" in bloc:
        return float(bloc["largeur"])
    return float(bloc.get("w", 0.0))


def sommets_rectangle_ax(x: float, y: float, largeur: float, hauteur: float):
    """Sommets du rectangle [bas-gauche, bas-droit, haut-droit, haut-gauche]."""
    return [
        (x, y),
        (x + largeur, y),
        (x + largeur, y + hauteur),
        (x, y + hauteur),
    ]


def sommets_quad_depuis_xy_patch(xy) -> list[tuple[float, float]]:
    """
    Jusqu'à 4 sommets distincts à partir du tableau ``get_xy()`` d'un Polygone matplotlib.

    Si le polygone est fermé, le dernier point duplique souvent le premier : on l'exclut.
    Avec exactement 4 points sans duplication, les quatre sommets sont conservés (éviter len(xy)-1).
    """
    arr = np.asarray(xy, dtype=np.float64)
    n = int(arr.shape[0])
    if n < 1:
        return []
    if n >= 2:
        dx = float(arr[0, 0] - arr[n - 1, 0])
        dy = float(arr[0, 1] - arr[n - 1, 1])
        if dx * dx + dy * dy <= 1e-20:
            n -= 1
    return [(float(arr[j, 0]), float(arr[j, 1])) for j in range(min(4, n))]
