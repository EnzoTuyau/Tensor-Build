"""Réexporte géométrie + constantes."""

from deuxDimensions.domain.geometry import (
    largeur_bloc,
    sommets_quad_depuis_xy_patch,
    sommets_rectangle_ax,
)
from .constantes import (
    AXIS_XLIM,
    AXIS_YLIM,
    FALL_STEP,
    GRAVITY,
    GROUND_Y,
    HEATMAP_CELLES_MAX,
    MATERIAUX,
    SNAP_TOL,
    TIMER_MS,
)

__all__ = [
    "largeur_bloc",
    "sommets_quad_depuis_xy_patch",
    "sommets_rectangle_ax",
    "AXIS_XLIM",
    "AXIS_YLIM",
    "FALL_STEP",
    "GRAVITY",
    "GROUND_Y",
    "HEATMAP_CELLES_MAX",
    "MATERIAUX",
    "SNAP_TOL",
    "TIMER_MS",
]
