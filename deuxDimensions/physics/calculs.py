"""Calculs physiques et RDM pour la simulation 2D."""

from __future__ import annotations

from typing import Any

from deuxDimensions.domain.constantes import (
    GRAVITY,
    GROUND_Y,
    MATERIAUX,
    SNAP_TOL,
    STRESS_DELTA_H_VISUAL_SCALE,
)
from deuxDimensions.domain.geometry import sommets_rectangle_ax


def _tau_limite(mat: dict[str, Any]) -> float:
    """Limite élastique en cisaillement (Pa), convention ductile : tau_lim = sigma_y / sqrt(3)."""
    return float(mat["sigma_y"]) / (3.0**0.5)


def _geom_patch(rd: dict[str, Any]) -> tuple[float, float, float, float]:
    """Coin bas-gauche et dimensions du rectangle matplotlib du bloc."""
     
    return rd["x"], rd["y"], rd["largeur"], rd["h0"]


def _charge_verticale_equivalente(rd: dict[str, Any]) -> float:
    """Poids + charges appliquees, ramenees a une charge verticale (N)."""
    _, _, w, h = _geom_patch(rd)
    return rd["density"] * w * h * GRAVITY + rd["ext_force"] + rd["pressure"] * w


def _charge_verticale_au_bas_de_la_pile(
    blocs: list[dict[str, Any]],
    idx: int,
    paires: list[tuple[int, int, float]],
    memo: dict[int, float],
) -> float:
    """Charge verticale totale au bas du bloc (pile comprise).

    Inclut le poids/charges du bloc et tout ce qui lui est superposé au-dessus,
    via récurrence sur les paires de contact.
    """
    if idx in memo:
        return memo[idx]
    own = _charge_verticale_equivalente(blocs[idx])
    from_above = sum(
        _charge_verticale_au_bas_de_la_pile(blocs, ih, paires, memo)
        for (ib, ih, _) in paires
        if ib == idx
    )
    memo[idx] = own + from_above
    return memo[idx]


def _statut_utilisation(util_pct: float) -> tuple[str, str]:
    """Libelle et pictogramme selon le % d'utilisation par rapport a sigma_y."""
    if util_pct < 80:
        return "OK", "✓"
    if util_pct < 100:
        return "⚠️ Attention", "!"
    return "❌ RUPTURE", "✗"


def _contraintes_et_detail_bloc(
    i: int,
    bloc: dict[str, Any],
    blocs: list[dict[str, Any]],
    paires: list[tuple[int, int, float]],
    memo_axiale_totale: dict[int, float],
) -> tuple[dict[str, Any], str, list[str]]:
    _, _, w, h = _geom_patch(bloc)
    aire = w * h
    mat = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])

    poids = bloc["density"] * aire * GRAVITY
    f_ext = bloc["ext_force"]
    f_ext_x = bloc.get("ext_force_x", 0.0)
    f_pression = bloc["pressure"] * w

    f_contact = sum(
        _charge_verticale_au_bas_de_la_pile(blocs, ih, paires, memo_axiale_totale)
        for (i_bas, ih, _) in paires
        if i_bas == i
    )

    f_axial = poids + f_ext + f_pression + f_contact
    sigma_axial = f_axial / aire

    tau_xy_moy = f_ext_x / aire if aire > 0 else 0.0
    tau_xy_max = 1.5 * tau_xy_moy

    moment = bloc["moment"]
    i_local = (w * h**3) / 12
    sig_haut = moment * (h / 2) / i_local if i_local > 0 else 0.0
    sig_bas = moment * (-h / 2) / i_local if i_local > 0 else 0.0

    sigma_normal_top = sigma_axial + sig_haut
    sigma_normal_bot = sigma_axial + sig_bas
    sigma_max_normal = max(abs(sigma_normal_top), abs(sigma_normal_bot))

    sigma_y = mat["sigma_y"]
    tau_lim = _tau_limite(mat)
    util_axial_flex = sigma_max_normal / sigma_y * 100 if sigma_y > 0 else 0.0
    util_shear = abs(tau_xy_max) / tau_lim * 100 if tau_lim > 0 else 0.0

    statut, sym = _statut_utilisation(util_axial_flex)

    E = mat["E"]
    nu = 0.3
    G = E / (2 * (1 + nu))

    delta_h = (f_axial * h) / (E * aire) if aire > 0 and E > 0 else 0.0
    delta_x = (f_ext_x * h) / (G * aire) if aire > 0 and G > 0 else 0.0

    resume = (
        f"  Bloc <b>{i + 1}</b> ({bloc['material']}) : "
        f"max |σ normal| = <b>{sigma_max_normal/1e6:.2f} MPa</b>, "
        f"<b>{util_axial_flex:.0f}%</b> {sym}"
    )

    lignes_detail = [
        f"<b style='color:#e65100'>── Bloc {i+1} ({bloc['material']}) ──</b>",
        "<span style='color:#546e7a'><b>Compression / traction axiale</b> (σ<sub>axial</sub> &gt; 0 : compression sous charges descendantes)</span>",
        f"  F axiale totale : <b>{f_axial:.1f} N</b> (poids + F<sub>z</sub> + pression×w + contact)",
        f"  σ axiale        : {sigma_axial/1e6:.3f} MPa",
        "",
        "<span style='color:#546e7a'><b>Flexion</b></span>",
        f"  Moment M        : {moment:.1f} N·m",
        f"  σ flex fibre haut : {sig_haut/1e6:.3f} MPa",
        f"  σ flex fibre bas  : {sig_bas/1e6:.3f} MPa",
        f"  σ normal haut (σ<sub>ax</sub>+σ<sub>flex</sub>) : {sigma_normal_top/1e6:.3f} MPa",
        f"  σ normal bas      : {sigma_normal_bot/1e6:.3f} MPa",
        f"  max |σ normal| fibres : {sigma_max_normal/1e6:.3f} MPa — util. {util_axial_flex:.1f}% / σ<sub>y</sub>",
        "",
        "<span style='color:#546e7a'><b>Cisaillement</b> (effort F<sub>x</sub>, section rect., τ<sub>max</sub> ≈ 1.5 τ<sub>moy</sub>)</span>",
        f"  F<sub>x</sub>           : {f_ext_x:.1f} N",
        f"  τ moy            : {tau_xy_moy/1e6:.4f} MPa",
        f"  τ max            : {tau_xy_max/1e6:.4f} MPa",
        f"  τ limite (σ<sub>y</sub>/√3) : {tau_lim/1e6:.3f} MPa — util. cisaillement {util_shear:.1f}%",
        "",
        "<span style='color:#546e7a'><b>Critère uniaxial (max |σ normal|, axial + flexion)</b></span>",
        f"  σ<sub>y</sub> limite    : {sigma_y/1e6:.0f} MPa",
        f"  <b>Utilisation globale : {util_axial_flex:.1f}% {statut}</b>",
        "",
        f"  Poids propre   : {poids:.1f} N",
        f"  Charge contact : {f_contact:.1f} N",
        f"  Force vert. ext.: {f_ext:.1f} N",
        f"  Pression       : {f_pression:.1f} N",
        "",
    ]

    stress = {
        "sigma_total": sigma_max_normal,
        "sigma_axial": sigma_axial,
        "sigma_bending_top": sig_haut,
        "sigma_bending_bot": sig_bas,
        "sigma_normal_top": sigma_normal_top,
        "sigma_normal_bot": sigma_normal_bot,
        "sigma_max_normal": sigma_max_normal,
        "tau_xy_moy": tau_xy_moy,
        "tau_xy_max": tau_xy_max,
        "tau_lim": tau_lim,
        "util_axial_flex": util_axial_flex,
        "util_shear": util_shear,
        "ext_force": f_ext + f_pression,
        "ext_force_x": f_ext_x,
        "pressure": bloc["pressure"],
        "utilization": util_axial_flex,
        "F_axial": f_axial,
        "delta_h": delta_h,
        "delta_x": delta_x,
    }
    return stress, resume, lignes_detail


def _hauteur_affichee_ecrasement(h0: float, stress: dict[str, Any] | None) -> float:
    """
    Hauteur (m) du polygone bloc telle que rendu sous charge : meme regle que le canvas
    (h0 - scale * delta_h), pour que la gravite pose les blocs sur le sommet visible.
    """
    if stress is None:
        return h0
    dh = float(stress.get("delta_h", 0.0))
    v_dh = dh * STRESS_DELTA_H_VISUAL_SCALE
    return max(0.01, h0 - v_dh)


def _hauteur_appui_max(
    blocs: list[dict[str, Any]],
    idx: int,
    donnees_stress: list[dict[str, Any]] | None = None,
) -> float:
    """Plus haute surface sous ce bloc : sol ou sommet d'un autre bloc en recouvrement."""
    x_me, y_me, w_me, _ = _geom_patch(blocs[idx])
    plancher_y = GROUND_Y
    for i2, rd2 in enumerate(blocs):
        if i2 == idx:
            continue
        x2, y2, w2, h2 = _geom_patch(rd2)
        st2 = None
        if donnees_stress is not None and i2 < len(donnees_stress):
            st2 = donnees_stress[i2]
        h2_eff = _hauteur_affichee_ecrasement(h2, st2)
        if x_me < x2 + w2 and x2 < x_me + w_me:
            sommet2 = y2 + h2_eff
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


def _overlaps_x(bloc_a: dict[str, Any], bloc_b: dict[str, Any]) -> bool:
    """Verifie si deux blocs se chevauchent horizontalement."""
    xa, _, wa, _ = _geom_patch(bloc_a)
    xb, _, wb, _ = _geom_patch(bloc_b)

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

            xi, yi, wi, hi = _geom_patch(blocs[i])
            xj, yj, wj, hj = _geom_patch(blocs[j])

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
    mobile = blocs[idx_mobile]
    patch_mobile = mobile["patch"]
    mx = mobile["x"]
    my = mobile["y"]
    largeur = mobile["largeur"]
    hauteur = mobile["h0"]
    collision = False

    for i, autre_bloc in enumerate(blocs):
        if i == idx_mobile:
            continue

        ox = autre_bloc["x"]
        oy = autre_bloc["y"]
        ow = autre_bloc["largeur"]
        oh = autre_bloc["h0"]

        chevauche_x = mx < ox + ow and ox < mx + largeur
        chevauche_y = my < oy + oh and oy < my + hauteur

        if chevauche_x and chevauche_y:
            penet_haut = (oy + oh) - my
            penet_bas = (my + hauteur) - oy
            penet_droite = (ox + ow) - mx
            penet_gauche = (mx + largeur) - ox

            min_penet = min(penet_haut, penet_bas, penet_droite, penet_gauche)

            if min_penet == penet_haut:
                my = oy + oh
            elif min_penet == penet_bas:
                my = oy - hauteur
            elif min_penet == penet_droite:
                mx = ox + ow
            else:
                mx = ox - largeur

            mobile["x"] = mx
            mobile["y"] = my
            patch_mobile.set_xy(sommets_rectangle_ax(mx, my, largeur, hauteur))
            collision = True

    return collision


def calculer_donnees_physiques(
    blocs: list[dict[str, Any]], gravite_active: bool = True
) -> dict[str, Any]:
    """
    Calcule les contraintes de tous les blocs et genere les contenus HTML.

    Si gravite_active est False : pas de paires de contact ni de transmission
    verticale par superposition (chaque bloc ne voit que son propre poids et
    les charges explicites). La gravité simulée (chute) est pilotée par le canvas.

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

    paires = _contact_pairs(blocs) if gravite_active else []
    memo_axiale_totale: dict[int, float] = {}
    donnees_stress: list[dict[str, Any]] = []
    resumes = []
    lignes_detail = []

    for i, bloc in enumerate(blocs):
        stress, resume, detail_fragments = _contraintes_et_detail_bloc(
            i, bloc, blocs, paires, memo_axiale_totale
        )
        donnees_stress.append(stress)
        resumes.append(resume)
        lignes_detail.extend(detail_fragments)

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
            "<span style='color:#666;font-size:9px'>Résumé max |σ normal| (axial + flexion) / utilisation globale.</span>",
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
