"""Texte d'infobulle pour le survol d'un bloc sur le canvas 2D."""

from __future__ import annotations

from typing import Any

from deuxDimensions.domain.geometry import largeur_bloc


def texte_infobulle_bloc(index: int, bloc: dict[str, Any], stress: dict[str, Any] | None) -> str:
    """Résumé compact : géométrie, charges appliquées, contraintes si disponibles."""
    w = largeur_bloc(bloc)
    lig = [
        f"Bloc {index + 1} — {bloc['material']}",
        f"{w:.2f} × {bloc['h0']:.2f} m",
        "",
        "Charges sur ce bloc",
        f"  F vertical : {bloc['ext_force']:.0f} N",
        f"  F horizontal : {bloc.get('ext_force_x', 0.0):.0f} N",
        f"  Pression : {bloc['pressure']:.0f} Pa",
    ]
    if stress:
        sig_max_n = stress.get("sigma_max_normal", stress.get("sigma_total", 0.0))
        sig_ax = stress.get("sigma_axial", 0.0)
        tau_m = stress.get("tau_xy_moy", 0.0)
        util = stress.get("utilization", 0.0)
        lig += [
            "",
            "Sollicitations / contraintes",
            f"  F axial total : {stress.get('F_axial', 0.0):.0f} N",
            f"  σ axial : {sig_ax / 1e6:.2f} MPa",
            f"  τ moy : {tau_m / 1e6:.3f} MPa",
            f"  max |σ normal| : {sig_max_n / 1e6:.2f} MPa",
            f"  Utilisation : {util:.0f} %",
        ]
    else:
        lig += ["", "(Simulez ou ajoutez des blocs pour le détail RDM)"]
    return "\n".join(lig)
