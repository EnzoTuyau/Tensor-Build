"""Textes d'infobulle pour les charges dessinées sur le canvas 2D."""

from __future__ import annotations

from typing import Any


def texte_infobulle_force_verticale(idx_bloc: int, bloc: dict[str, Any], stress: dict[str, Any] | None) -> str:
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
    p_pa = float(bloc.get("pressure", 0.0))
    w = float(bloc["largeur"])
    resultante = p_pa * w
    return (
        f"Pression répartie — bloc {idx_bloc + 1}\n"
        f"Bande {k + 1}/{n_tot} (représentation équivalente)\n"
        f"Pression : {p_pa:.0f} Pa\n"
        f"Résultante verticale indic.: ~ {resultante:.0f} N sur largeur {w:.2f} m\n"
        "Application : face supérieure du bloc"
    )


def texte_infobulle_force_horizontale(idx_bloc: int, bloc: dict[str, Any], stress: dict[str, Any] | None) -> str:
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


def texte_infobulle_moment(idx_bloc: int, bloc: dict[str, Any]) -> str:
    m = float(bloc.get("moment", 0.0))
    signe = "sens antihoraire (+)" if m > 0 else "sens horaire (−)"
    return (
        f"Moment fléchissant — bloc {idx_bloc + 1}\n"
        f"Valeur : {abs(m):.0f} N·m ({signe})\n"
        "Schéma : arc au centre du bloc (référence pédagogique)"
    )
