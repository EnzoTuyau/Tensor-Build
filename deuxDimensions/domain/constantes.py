"""Constantes globales du simulateur 2D (version modulaire)."""

# Physique / temps
GRAVITY = 9.81  # acceleration gravitationnelle (m/s²)
GROUND_Y = 0.0  # position y du sol sur le canvas
SNAP_TOL = 0.18  # distance max pour considerer deux blocs en contact (m)
FALL_STEP = 0.12  # distance de chute par tick de physique (m)
TIMER_MS = 30  # intervalle du timer de physique (ms) — ~33 fps

# Limites fixes du repere (m) : la vue ne se reechelonne pas avec la carte de pression
AXIS_XLIM = (-2.0, 12.0)
AXIS_YLIM = (-1.5, 12.0)

# Taille max de la grille "carte de pression" (nombre de mailles par cote)
HEATMAP_CELLES_MAX = 48

# Feedback utilisation (von Mises vs sigma_y), pourcentages
UTIL_PHASE_OK_PCT = 80.0
UTIL_PHASE_ALERT_PCT = 100.0

# Rupture : hysteresis sur l'utilisation (%)
FAILURE_UTIL_TRIGGER_PCT = 101.0
FAILURE_UTIL_REARM_PCT = 95.0

# Reference pour teinter les joints (contrainte normale indicative ~ F/A), Pa
CONTACT_STRESS_REF_PA = 50e6

# Animation rupture (timer Qt)
RUPTURE_TICK_MS = 35
RUPTURE_TOTAL_TICKS = 18
RUPTURE_CRACK_PHASE_TICKS = 7

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
