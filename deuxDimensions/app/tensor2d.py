"""
Façade de compatibilité du mode 2D.

Historique:
- Le projet exposait toute l'application via ce seul fichier.
- La logique est maintenant répartie dans `domain/`, `physics/`, `rendering/`, `ui/` et `app/`.

Ce module conserve l'import historique:
`from deuxDimensions.app.tensor2d import MaterialSimulationApp`
"""

from __future__ import annotations

from deuxDimensions.app.main_window import MaterialSimulationApp, lancer_application
from deuxDimensions.domain.constantes import (
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
from deuxDimensions.physics.calculs import (
    _charge_verticale_equivalente,
    _contact_pairs,
    _geom_patch,
    _hauteur_appui_max,
    _resoudre_collision,
    _statistiques_globales_section,
    _statut_utilisation,
    calculer_donnees_physiques,
)
from deuxDimensions.rendering.canvas2d import Canvas2D
from deuxDimensions.ui.contact_tooltip import ContactTooltip
from deuxDimensions.ui.panneau_controle import PanneauControle

__all__ = [
    "AXIS_XLIM",
    "AXIS_YLIM",
    "Canvas2D",
    "ContactTooltip",
    "FALL_STEP",
    "GRAVITY",
    "GROUND_Y",
    "HEATMAP_CELLES_MAX",
    "MATERIAUX",
    "MaterialSimulationApp",
    "PanneauControle",
    "SNAP_TOL",
    "TIMER_MS",
    "_charge_verticale_equivalente",
    "_contact_pairs",
    "_geom_patch",
    "_hauteur_appui_max",
    "_resoudre_collision",
    "_statistiques_globales_section",
    "_statut_utilisation",
    "calculer_donnees_physiques",
    "lancer_application",
]


if __name__ == "__main__":
    lancer_application()
