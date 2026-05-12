"""Rupture avec hystérésis sur le pourcentage d’utilisation (critère uniaxial vs sigma_y)."""

from __future__ import annotations

from deuxDimensions.domain.constantes import FAILURE_UTIL_REARM_PCT, FAILURE_UTIL_TRIGGER_PCT


def evaluer_latch_rupture(util_pct: float, armed: bool) -> tuple[bool, bool]:
    """Retourne (déclencher_rupture, latch_armé). Réarmement sous REARM ; rupture si TRIGGER et latch actif."""
    if util_pct <= FAILURE_UTIL_REARM_PCT:
        return False, True
    if util_pct >= FAILURE_UTIL_TRIGGER_PCT and armed:
        return True, False
    return False, armed
