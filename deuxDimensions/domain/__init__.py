"""Domaine 2D : constantes et donnees metier partagees."""

from deuxDimensions.domain.geometry import sommets_quad_depuis_xy_patch, sommets_rectangle_ax
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
