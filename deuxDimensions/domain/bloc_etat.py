"""Clés optionnelles sur les dict blocs (canvas, thermique, latch rupture)."""

from __future__ import annotations

# Clés d'état visuel et de verrouillage rupture ; préfixe underscore pour rester compatibles
# avec les pickles ou les données externes déjà sérialisées.
CLE_ARMEMENT_RUPTURE = "_rupture_armed"
CLE_RUPTURE_EN_COURS = "_breaking"
CLE_CONTOUR_UTIL_DESSIN = "_edge_util_draw"
CLE_DERNIER_UTIL_DESSIN = "_last_util_draw"

CLE_MATRICE_THERMIQUE = "heatmap_matrice"
CLE_MAILLAGE_THERMIQUE = "heatmap_cellules"
