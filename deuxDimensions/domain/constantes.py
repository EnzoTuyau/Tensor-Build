"""Constantes globales du simulateur 2D (version modulaire)."""

#1. Physique et temps
GRAVITY = 9.81  # Accélération gravitationnelle (m/s²)

#2. Échelle visuelle de l'écrasement axial (delta_h en mètres)
# Même référence que _tick_physique et dessiner_contraintes sur le canvas.
STRESS_DELTA_H_VISUAL_SCALE = 5000.0

#3. Bornes visuelles de l'écrasement axial (fraction de h0)
# Évite que le polygone se réduise au point que les blocs au-dessus semblent traverser le bloc chargé.
STRESS_VISUAL_MAX_COMPRESSION = 0.30
STRESS_VISUAL_MAX_EXTENSION = 0.05

GROUND_Y = 0.0  # Ordonnée du sol dans le repère du canvas
SNAP_TOL = 0.18  # Distance maximale pour considérer deux blocs en contact (m)
FALL_STEP = 0.12  # Pas de chute par tick de physique (m)
TIMER_MS = 30  # Intervalle du timer de physique (ms), soit environ 33 images par seconde

#4. Limites fixes du repère (m) : la vue ne se rééchelonne pas avec la carte de pression
AXIS_XLIM = (-2.0, 12.0)
AXIS_YLIM = (-1.5, 12.0)

#5. Carte de pression : nombre maximal de mailles par côté
HEATMAP_CELLES_MAX = 48

#6. Seuils d'affichage du critère d'utilisation (max |σ normal| vs σ_y), en pourcentages
UTIL_PHASE_OK_PCT = 80.0
UTIL_PHASE_ALERT_PCT = 100.0

#7. Rupture : hystérésis sur le pourcentage d'utilisation
FAILURE_UTIL_TRIGGER_PCT = 101.0
FAILURE_UTIL_REARM_PCT = 95.0

#8. Référence pour teinter les joints (contrainte normale indicative ≈ F/A), en Pa
CONTACT_STRESS_REF_PA = 50e6

#9. Animation de rupture (timer Qt) : secousse, éclatement, chute des éclats sous gravité, puis fondu
RUPTURE_TICK_MS = 20
RUPTURE_SHAKE_TICKS = 4
RUPTURE_FALL_TICKS = 12
RUPTURE_FADE_TICKS = 6
RUPTURE_TOTAL_TICKS = RUPTURE_SHAKE_TICKS + RUPTURE_FALL_TICKS
RUPTURE_SHARD_COUNT = 5
RUPTURE_SHARD_VX_RANGE = (-1.5, 1.5)
RUPTURE_SHARD_VY_RANGE = (-0.5, 1.5)
RUPTURE_SHAKE_AMPLITUDE = 0.04  # Amplitude de la secousse (m)

#10. Notifications toast (rupture, etc.)
TOAST_DUREE_MS = 4500
TOAST_MAX_VISIBLES = 4
TOAST_LARGEUR = 320

#11. Matériaux : densité (kg/m³), module E et limite σ_y (Pa), couleurs de face et de contour
# Critère de cisaillement ductile : τ_lim = σ_y / √3 (voir calculs._tau_limite).
MATERIAUX = {
    "Acier": {
        "density": 7850,
        "E": 210e9,
        "sigma_y": 250e6,
        "face": "#b0bec5",
        "edge": "#37474f",
    },
    "Béton": {
        "density": 2400,
        "E": 30e9,
        "sigma_y": 30e6,
        "face": "#bdbdbd",
        "edge": "#424242",
    },
    "Aluminium": {
        "density": 2700,
        "E": 70e9,
        "sigma_y": 270e6,
        "face": "#e3f2fd",
        "edge": "#0277bd",
    },
    "Bois": {
        "density": 600,
        "E": 12e9,
        "sigma_y": 40e6,
        "face": "#a67c52",
        "edge": "#3e2723",
    },
    "Fonte": {
        "density": 7200,
        "E": 170e9,
        "sigma_y": 200e6,
        "face": "#78909c",
        "edge": "#263238",
    },
}
