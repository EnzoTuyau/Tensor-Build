"""
Logique pure : seuil de rupture et hysteresis sur l'utilisation (%) par rapport
a sigma_y (ici : critere uniaxial max |sigma normal|).

Le declenchement utilise un latch pour eviter les re-declenchements tant que
l'utilisation reste au-dessus du seuil ; le rearmement se fait lorsque
l'utilisation retombe sous le plancher d'hysteresis.
"""

from __future__ import annotations

from deuxDimensions.domain.constantes import FAILURE_UTIL_REARM_PCT, FAILURE_UTIL_TRIGGER_PCT


def evaluer_latch_rupture(util_pct: float, armed: bool) -> tuple[bool, bool]:
    """
    Retourne (declencher_rupture_maintenant, nouvel_etat_armed).

    - Si util <= REARM : armed repasse a True (reactivation du latch).
    - Si util >= TRIGGER et armed : rupture declenchee, latch desarme.
    """
    if util_pct <= FAILURE_UTIL_REARM_PCT:
        return False, True
    if util_pct >= FAILURE_UTIL_TRIGGER_PCT and armed:
        return True, False
    return False, armed
