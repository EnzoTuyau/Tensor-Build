"""Constantes globales du simulateur 2D (version modulaire)."""

# Physique / temps
GRAVITY = 9.81  # acceleration gravitationnelle (m/s²)
# Echelle commune (avec delta_h en m) pour l'allongement visuel de l'ecrasement axial
# dans le canvas ; doit rester alignee avec _tick_physique / dessiner_contraintes.
STRESS_DELTA_H_VISUAL_SCALE = 5000.0
# Borne visuelle de l'ecrasement axial (fraction de h0) pour eviter que le polygone
# se reduise au point que les blocs sus-jacents semblent traverser le bloc charge.
STRESS_VISUAL_MAX_COMPRESSION = 0.30
STRESS_VISUAL_MAX_EXTENSION = 0.05
GROUND_Y = 0.0  # position y du sol sur le canvas
SNAP_TOL = 0.18  # distance max pour considerer deux blocs en contact (m)
FALL_STEP = 0.12  # distance de chute par tick de physique (m)
TIMER_MS = 30  # intervalle du timer de physique (ms) — ~33 fps

# Limites fixes du repere (m) : la vue ne se reechelonne pas avec la carte de pression
AXIS_XLIM = (-2.0, 12.0)
AXIS_YLIM = (-1.5, 12.0)

# Taille max de la grille "carte de pression" (nombre de mailles par cote)
HEATMAP_CELLES_MAX = 48

# Feedback utilisation (critere uniaxial max |sigma normal| vs sigma_y), pourcentages
UTIL_PHASE_OK_PCT = 80.0
UTIL_PHASE_ALERT_PCT = 100.0

# Rupture : hysteresis sur l'utilisation (%)
FAILURE_UTIL_TRIGGER_PCT = 101.0
FAILURE_UTIL_REARM_PCT = 95.0

# Reference pour teinter les joints (contrainte normale indicative ~ F/A), Pa
CONTACT_STRESS_REF_PA = 50e6

# Animation rupture (timer Qt) : shake -> shatter -> chute des eclats sous gravite + fondu
RUPTURE_TICK_MS = 20
RUPTURE_SHAKE_TICKS = 4
RUPTURE_FALL_TICKS = 12
RUPTURE_FADE_TICKS = 6
RUPTURE_TOTAL_TICKS = RUPTURE_SHAKE_TICKS + RUPTURE_FALL_TICKS
RUPTURE_SHARD_COUNT = 5
RUPTURE_SHARD_VX_RANGE = (-1.5, 1.5)
RUPTURE_SHARD_VY_RANGE = (-0.5, 1.5)
RUPTURE_SHAKE_AMPLITUDE = 0.04  # m

# Toasts de notification (rupture, etc.)
TOAST_DUREE_MS = 4500
TOAST_MAX_VISIBLES = 4
TOAST_LARGEUR = 320

# Materiaux : densite (kg/m³), E et sigma_y (Pa), couleurs face/contour
# Critere cisaillement ductile : tau_lim = sigma_y / sqrt(3) (voir calculs._tau_limite).
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
