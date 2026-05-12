"""Infobulles pour charges dessinées : F_z, pression, F_x."""

from __future__ import annotations

from typing import Any

from deuxDimensions.domain.geometry import largeur_bloc


def texte_infobulle_force_verticale(idx_bloc: int, bloc: dict[str, Any], stress: dict[str, Any] | None) -> str:
    """Force verticale ponctuelle ; effort axial total si ``stress``."""
    f_n = float(bloc.get("ext_force", 0.0))
    lignes = [
        f"Force ponctuelle — bloc {idx_bloc + 1}",
        f"Valeur : {f_n:.0f} N (compression vers le bas)",
        "Application : fibre supérieure, axe médian du bloc",
    ]
    if stress:
        lignes.append(f"Effort axial total (RDM) : {stress.get('F_axial', 0.0):.0f} N")
    return "\n".join(lignes)


def texte_infobulle_pression(idx_bloc: int, bloc: dict[str, Any], k: int, n_tot: int) -> str:
    """Bande k/n d’une pression répartie équivalente."""
    p_pa = float(bloc.get("pressure", 0.0))
    w = largeur_bloc(bloc)
    resultante = p_pa * w
    return (
        f"Pression répartie — bloc {idx_bloc + 1}\n"
        f"Bande {k + 1}/{n_tot} (représentation équivalente)\n"
        f"Pression : {p_pa:.0f} Pa\n"
        f"Résultante verticale indic.: ~ {resultante:.0f} N sur largeur {w:.2f} m\n"
        "Application : face supérieure du bloc"
    )


def texte_infobulle_force_horizontale(idx_bloc: int, bloc: dict[str, Any], stress: dict[str, Any] | None) -> str:
    """Fx sur face latérale ; τ moyen si ``stress``."""
    fx = float(bloc.get("ext_force_x", 0.0))
    sens = "vers la droite (+x)" if fx > 0 else "vers la gauche (−x)"
    lignes = [
        f"Effort horizontal Fx — bloc {idx_bloc + 1}",
        f"Valeur : {fx:.0f} N ({sens})",
        "Application : milieu de hauteur, sur la face latérale libre",
    ]
    if stress:
        tau = stress.get("tau_xy_moy", 0.0)
        lignes.append(f"τ moyen indicatif : {tau / 1e6:.4f} MPa")
    return "\n".join(lignes)
