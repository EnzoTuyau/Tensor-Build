"""Calculs physiques et RDM pour la simulation 2D."""

from __future__ import annotations

from typing import Any

from deuxDimensions.domain.constantes import GRAVITY, GROUND_Y, MATERIAUX, SNAP_TOL


def _geom_patch(rd: dict[str, Any]) -> tuple[float, float, float, float]:
    """Coin bas-gauche et dimensions du rectangle matplotlib du bloc."""
    patch = rd["patch"]
    x, y = patch.get_xy()
    return x, y, patch.get_width(), patch.get_height()


def _charge_verticale_equivalente(rd: dict[str, Any]) -> float:
    """Poids + charges appliquees, ramenees a une charge verticale (N)."""
    _, _, w, h = _geom_patch(rd)
    return rd["density"] * w * h * GRAVITY + rd["ext_force"] + rd["pressure"] * w


def _hauteur_appui_max(blocs: list[dict[str, Any]], idx: int) -> float:
    """Plus haute surface sous ce bloc : sol ou sommet d'un autre bloc en recouvrement."""
    x_me, y_me, w_me, _ = _geom_patch(blocs[idx])
    plancher_y = GROUND_Y
    for i2, rd2 in enumerate(blocs):
        if i2 == idx:
            continue
        x2, y2, w2, h2 = _geom_patch(rd2)
        if x_me < x2 + w2 and x2 < x_me + w_me:
            sommet2 = y2 + h2
            if sommet2 <= y_me + 0.001:
                plancher_y = max(plancher_y, sommet2)
    return plancher_y


def _statistiques_globales_section(
    blocs: list[dict[str, Any]],
) -> tuple[float, float, float, float, float, float]:
    """Aire, centre de gravite, inerties et masse (epaisseur unite)."""
    aire_totale = 0.0
    sx = sy = 0.0
    masse = 0.0
    rectangles = []
    for rd in blocs:
        x, y, w, h = _geom_patch(rd)
        a = w * h
        rectangles.append((x, y, w, h, a))
        aire_totale += a
        sx += (x + w / 2) * a
        sy += (y + h / 2) * a
        masse += rd["density"] * a
    xg = sx / aire_totale
    yg = sy / aire_totale
    ixx = sum(
        (w * h**3) / 12 + w * h * (y + h / 2 - yg) ** 2
        for x, y, w, h, _ in rectangles
    )
    iyy = sum(
        (h * w**3) / 12 + w * h * (x + w / 2 - xg) ** 2
        for x, y, w, h, _ in rectangles
    )
    return aire_totale, xg, yg, ixx, iyy, masse


def _statut_utilisation(util_pct: float) -> tuple[str, str]:
    """Libelle et pictogramme selon le % d'utilisation par rapport a sigma_y."""
    if util_pct < 80:
        return "OK", "✓"
    if util_pct < 100:
        return "⚠️ Attention", "!"
    return "❌ RUPTURE", "✗"


def _overlaps_x(bloc_a: dict[str, Any], bloc_b: dict[str, Any]) -> bool:
    """Verifie si deux blocs se chevauchent horizontalement."""
    xa, _ = bloc_a["patch"].get_xy()
    wa = bloc_a["patch"].get_width()
    xb, _ = bloc_b["patch"].get_xy()
    wb = bloc_b["patch"].get_width()
    return xa < xb + wb and xb < xa + wa


def _contact_pairs(
    blocs: list[dict[str, Any]], tol: float = SNAP_TOL
) -> list[tuple[int, int, float]]:
    """
    Retourne les paires en contact vertical.
    Une paire (i_bas, i_haut, fraction) signifie que i_haut repose sur i_bas.
    """
    paires: list[tuple[int, int, float]] = []
    for i in range(len(blocs)):
        for j in range(len(blocs)):
            if i == j:
                continue

            xi, yi = blocs[i]["patch"].get_xy()
            wi, hi = blocs[i]["patch"].get_width(), blocs[i]["patch"].get_height()
            xj, yj = blocs[j]["patch"].get_xy()
            wj = blocs[j]["patch"].get_width()

            contact_vertical = abs((yi + hi) - yj) <= tol
            if contact_vertical and _overlaps_x(blocs[i], blocs[j]):
                largeur_contact = min(xi + wi, xj + wj) - max(xi, xj)
                fraction = largeur_contact / min(wi, wj)
                paires.append((i, j, fraction))
    return paires


def _resoudre_collision(idx_mobile: int, blocs: list[dict[str, Any]]) -> bool:
    """
    Repousse un bloc mobile hors collision par l'axe de moindre penetration.
    """
    patch_mobile = blocs[idx_mobile]["patch"]
    mx, my = patch_mobile.get_xy()
    largeur, hauteur = patch_mobile.get_width(), patch_mobile.get_height()
    collision = False

    for i, autre_bloc in enumerate(blocs):
        if i == idx_mobile:
            continue

        patch_autre = autre_bloc["patch"]
        ox, oy = patch_autre.get_xy()
        ow, oh = patch_autre.get_width(), patch_autre.get_height()

        chevauche_x = mx < ox + ow and ox < mx + largeur
        chevauche_y = my < oy + oh and oy < my + hauteur

        if chevauche_x and chevauche_y:
            penet_haut = (oy + oh) - my
            penet_bas = (my + hauteur) - oy
            penet_droite = (ox + ow) - mx
            penet_gauche = (mx + largeur) - ox

            min_penet = min(penet_haut, penet_bas, penet_droite, penet_gauche)

            if min_penet == penet_haut:
                patch_mobile.set_xy((mx, oy + oh))
            elif min_penet == penet_bas:
                patch_mobile.set_xy((mx, oy - hauteur))
            elif min_penet == penet_droite:
                patch_mobile.set_xy((ox + ow, my))
            else:
                patch_mobile.set_xy((ox - largeur, my))

            mx, my = patch_mobile.get_xy()
            collision = True

    return collision


def calculer_donnees_physiques(blocs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calcule les contraintes de tous les blocs et genere les contenus HTML.

    Sortie:
      - donnees_stress: liste des dictionnaires de contraintes
      - paires: contacts detectes
      - html_cdgr: contenu HTML "centre de gravite"
      - html_rapport: contenu HTML detaille
    """
    if not blocs:
        return {
            "donnees_stress": [],
            "paires": [],
            "html_cdgr": "Aucun bloc.",
            "html_rapport": "Aucun bloc.",
        }

    aire_totale, xg, yg, ixx, iyy, masse = _statistiques_globales_section(blocs)
    entete = [
        "<b style='color:#1565c0'>══ Section globale ══</b>",
        f"Aire totale : <b>{aire_totale:.4f} m²</b>",
        f"CG (section) : <b>({xg:.3f}, {yg:.3f}) m</b>",
        f"Ixx (global) : <b>{ixx:.4f} m⁴</b>",
        f"Iyy (global) : <b>{iyy:.4f} m⁴</b>",
        f"Masse linéique : <b>{masse:.1f} kg/m</b>",
        "",
    ]

    paires = _contact_pairs(blocs)
    donnees_stress: list[dict[str, Any]] = []
    resumes = []
    lignes_detail = []

    for i, bloc in enumerate(blocs):
        _, _, w, h = _geom_patch(bloc)
        aire = w * h
        mat = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])

        poids = bloc["density"] * aire * GRAVITY
        f_ext = bloc["ext_force"]
        f_ext_x = bloc.get("ext_force_x", 0.0)  # force horizontale externe
        f_pression = bloc["pressure"] * w

        f_contact = sum(
            _charge_verticale_equivalente(blocs[j]) for (i_bas, j, _) in paires if i_bas == i
        )

        f_axial = poids + f_ext + f_pression + f_contact
        sigma_axial = f_axial / aire

        tau = f_ext_x/ aire  # contrainte de cisaillement horizontale

        moment = bloc["moment"]
        i_local = (w * h**3) / 12
        sig_haut = moment * (h / 2) / i_local if i_local > 0 else 0
        sig_bas = moment * (-h / 2) / i_local if i_local > 0 else 0

        sigma_max = max(abs(sigma_axial + sig_haut), abs(sigma_axial + sig_bas))

        sigma_eq = (sigma_max**2 + 3 * tau**2)**0.5  # contrainte équivalente de von Mises

        sigma_y = mat["sigma_y"]
        taux = sigma_eq / sigma_y * 100
        statut, sym = _statut_utilisation(taux)

        #Recuperer les proprietes du materiau
        E = mat["E"]
        nu = 0.3  # coefficient de Poisson (hypothese)
        G = E / (2 * (1 + nu))  # module de cisail

        #Calcul des deformations
        delta_h = (f_axial * h) / (E * aire)  # deformation axiale
        delta_x = (f_ext_x * h) / (G * aire)  # deformation de cisaillement

        resumes.append(
            f"  Bloc <b>{i + 1}</b> ({bloc['material']}) : "
            f"σ = <b>{sigma_max/1e6:.2f} MPa</b>, "
            f"<b>{taux:.0f}%</b> {sym}"
        )

        lignes_detail += [
            f"<b style='color:#e65100'>── Bloc {i+1} ({bloc['material']}) ──</b>",
            f"  Poids propre   : {poids:.1f} N",
            f"  Charge contact : {f_contact:.1f} N",
            f"  Force ext.     : {f_ext:.1f} N",
            f"  Pression       : {f_pression:.1f} N",
            f"  <b>F axiale total : {f_axial:.1f} N</b>",
            f"  σ axiale       : {sigma_axial/1e6:.3f} MPa",
        ]
        if abs(moment) > 0:
            lignes_detail += [
                f"  σ flex haut    : {sig_haut/1e6:.3f} MPa",
                f"  σ flex bas     : {sig_bas/1e6:.3f} MPa",
            ]
        lignes_detail += [
            f"  <b>σ max          : {sigma_max/1e6:.3f} MPa</b>",
            f"  σ_y limite     : {sigma_y/1e6:.0f} MPa",
            f"  Utilisation    : {taux:.1f}% {statut}",
            "",
        ]

        donnees_stress.append(
            {
                "sigma_total": sigma_max,
                "sigma_axial": sigma_axial,
                "sigma_bending_top": sig_haut,
                "sigma_bending_bot": sig_bas,
                "ext_force": f_ext + f_pression,
                "pressure": bloc["pressure"],
                "utilization": taux,
                "F_axial": f_axial,
                "delta_h": delta_h,
                "delta_x": delta_x,
            }
        )

    lignes_contact = []
    if paires:
        lignes_contact.append("<b style='color:#ff6f00'>══ Contacts détectés ══</b>")
        for ib, ih, frac in paires:
            fc = donnees_stress[ih]["F_axial"]
            lignes_contact.append(
                f"  Bloc {ih+1} (sup.) → Bloc {ib+1} (inf.) : "
                f"<b>{fc:.0f} N</b> — recouvrement "
                f"<b>{frac*100:.0f}%</b> de la largeur du plus petit bloc"
            )
        lignes_contact.append("")

    rapport = (
        entete
        + [
            "<b style='color:#2e7d32'>══ Contraintes sur les blocs ══</b>",
            "<span style='color:#666;font-size:9px'>Résumé σ / utilisation.</span>",
        ]
        + resumes
        + ["", "<b style='color:#1565c0'>══ Détail par bloc ══</b>", ""]
        + lignes_detail
        + lignes_contact
    )

    html_cdgr = (
        "<div style='padding:4px;'>"
        "<b style='color:#f9a825'>⊕ Centre de gravité</b><br><br>"
        "<span style='color:#555'>Position (x, y) en mètres<br>"
        f"<b style='color:#e65100;font-size:13px'>({xg:.2f}, {yg:.2f})</b>"
        "</div>"
    )

    return {
        "donnees_stress": donnees_stress,
        "paires": paires,
        "html_cdgr": html_cdgr,
        "html_rapport": "<br>".join(rapport),
    }
