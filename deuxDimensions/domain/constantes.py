"""Constantes globales du simulateur 2D."""

# 1 Physique / temps
GRAVITY = 9.81  # m/s²
STRESS_DELTA_H_VISUAL_SCALE = 5000.0  # échelle visuelle delta_h (alignée canvas)
STRESS_VISUAL_MAX_COMPRESSION = 0.30  # limite écrasement affiché (fraction h0)
STRESS_VISUAL_MAX_EXTENSION = 0.05
GROUND_Y = 0.0
SNAP_TOL = 0.18  # tolérance contact (m)
FALL_STEP = 0.12  # pas chute / tick (m)
TIMER_MS = 30  # timer physique (~33 Hz)

# 2 Axes figés + grille carte pression
AXIS_XLIM = (-2.0, 12.0)
AXIS_YLIM = (-1.5, 12.0)
HEATMAP_CELLES_MAX = 48

# 3 Utilisation affichée (% de sigma_y)
UTIL_PHASE_OK_PCT = 80.0
UTIL_PHASE_ALERT_PCT = 100.0

# 4 Rupture — hystérésis %
FAILURE_UTIL_TRIGGER_PCT = 101.0
FAILURE_UTIL_REARM_PCT = 95.0

CONTACT_STRESS_REF_PA = 50e6  # référence teinte joints (Pa)

# 5 Animation rupture (Qt)
RUPTURE_TICK_MS = 20
RUPTURE_SHAKE_TICKS = 4
RUPTURE_FALL_TICKS = 12
RUPTURE_FADE_TICKS = 6
RUPTURE_TOTAL_TICKS = RUPTURE_SHAKE_TICKS + RUPTURE_FALL_TICKS
RUPTURE_SHARD_COUNT = 5
RUPTURE_SHARD_VX_RANGE = (-1.5, 1.5)
RUPTURE_SHARD_VY_RANGE = (-0.5, 1.5)
RUPTURE_SHAKE_AMPLITUDE = 0.04  # m

# 6 Toasts
TOAST_DUREE_MS = 4500
TOAST_MAX_VISIBLES = 4
TOAST_LARGEUR = 320

# 7 Matériaux — tau_lim = sigma_y/sqrt(3) dans calculs
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
