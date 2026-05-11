"""Clés optionnelles sur les dict blocs (canvas, thermique, latch rupture)."""

from __future__ import annotations

# État visuel / latch (préfixe underscore pour compatibilité avec pickles ou données externes existantes)
CLE_ARMEMENT_RUPTURE = "_rupture_armed"
CLE_RUPTURE_EN_COURS = "_breaking"
CLE_CONTOUR_UTIL_DESSIN = "_edge_util_draw"
CLE_DERNIER_UTIL_DESSIN = "_last_util_draw"

CLE_MATRICE_THERMIQUE = "heatmap_matrice"
CLE_MAILLAGE_THERMIQUE = "heatmap_cellules"
