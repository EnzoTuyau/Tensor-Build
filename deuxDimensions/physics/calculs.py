"""Calculs physiques et RDM pour la simulation 2D."""

from __future__ import annotations

from typing import Any

from deuxDimensions.domain.constantes import (
    GRAVITY,
    GROUND_Y,
    MATERIAUX,
    SNAP_TOL,
    STRESS_DELTA_H_VISUAL_SCALE,
    STRESS_VISUAL_MAX_COMPRESSION,
    STRESS_VISUAL_MAX_EXTENSION,
)
from deuxDimensions.domain.geometry import largeur_bloc, sommets_rectangle_ax


def _tau_limite(mat: dict[str, Any]) -> float:
    """Limite élastique en cisaillement (Pa), convention ductile : tau_lim = sigma_y / sqrt(3)."""
    return float(mat["sigma_y"]) / (3.0**0.5)


def _geom_patch(rd: dict[str, Any]) -> tuple[float, float, float, float]:
    """Coin bas-gauche et dimensions du rectangle matplotlib du bloc."""
     
    return rd["x"], rd["y"], rd["w"], rd["h0"]


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



def _fmt_force(val: float) -> str:
    """Formatte une force (N) en kN si > 1000, sinon N, avec 1 décimale max."""
    if abs(val) >= 1000:
        return f"{val/1000:.1f} kN"
    return f"{val:.0f} N"


def _bloc_carte_detail(
    *,
    numero: int,
    materiau: str,
    edge_color: str,
    etat_couleur: str,
    etat_libelle: str,
    f_axial: float,
    poids: float,
    f_contact: float,
    f_ext: float,
    f_pression: float,
    f_ext_x: float,
    sigma_axial: float,
    sigma_max_normal: float,
    tau_xy_max: float,
    sigma_y: float,
    tau_lim: float,
    util_axial: float,
    util_shear: float,
) -> str:
    """Carte HTML compacte par bloc (lisible dans un QTextEdit dark)."""

    def _ligne(label: str, valeur: str, mute_si_zero: float | None = None) -> str:
        coul = "#9eb4d9" if (mute_si_zero is not None and abs(mute_si_zero) < 1e-9) else "#eaf2ff"
        return (
            f"<tr>"
            f"<td style='color:#6c7c95;padding:2px 12px 2px 0;'>{label}</td>"
            f"<td align='right' style='color:{coul};'>{valeur}</td>"
            f"</tr>"
        )

    # Charges (toujours utiles à voir : poids, contact, externes)
    charges_rows = (
        _ligne("Poids propre",     _fmt_force(poids))
        + _ligne("Contact",        _fmt_force(f_contact), f_contact)
        + _ligne("Force ext. F<sub>z</sub>", _fmt_force(f_ext), f_ext)
        + _ligne("Pression",       _fmt_force(f_pression), f_pression)
        + _ligne("Force ext. F<sub>x</sub>", _fmt_force(f_ext_x), f_ext_x)
        + f"<tr><td colspan='2' style='border-top:1px solid #25304a;padding-top:4px;'>"
          f"<span style='color:#9eb4d9'>Total axial</span> "
          f"<span style='float:right;color:#f3f7ff;'><b>{_fmt_force(f_axial)}</b></span>"
          f"</td></tr>"
    )

    # Contraintes
    contraintes_rows = (
        _ligne("σ axiale",   f"{sigma_axial/1e6:.2f} MPa")
        + _ligne("σ max |normal|", f"<b style='color:#f3f7ff'>{sigma_max_normal/1e6:.2f} MPa</b>")
        + _ligne("τ max", f"{tau_xy_max/1e6:.3f} MPa", tau_xy_max)
        + _ligne("σ<sub>y</sub> · τ<sub>lim</sub>",
                 f"{sigma_y/1e6:.0f} · {tau_lim/1e6:.0f} MPa")
    )

    # Util pills
    def _pill(label: str, pct: float) -> str:
        if pct < 80:
            c = "#5ee1a1"
        elif pct < 100:
            c = "#ffb43a"
        else:
            c = "#ff6b6b"
        return (
            f"<span style='color:#9eb4d9'>{label}</span> "
            f"<span style='color:{c};font-weight:700;'>{pct:.0f}%</span>"
        )

    pills = (
        f"<div style='padding:4px 0 0 0;'>"
        f"{_pill('Axial', util_axial)}"
        f"<span style='color:#3b4b62;'> · </span>"
        f"{_pill('Cisaillement', util_shear)}"
        f"</div>"
    )

    return (
        f"<table width='100%' cellspacing='0' cellpadding='0' "
        f"style='margin:8px 0;border-left:3px solid {edge_color};'>"
        f"<tr>"
        f"<td style='padding:6px 0 4px 10px;'>"
        f"<b style='color:#f3f7ff;font-size:12px;'>Bloc {numero}</b>"
        f"<span style='color:#9eb4d9;'> · {materiau}</span>"
        f"</td>"
        f"<td align='right' nowrap "
        f"style='padding:6px 10px 4px 20px;color:{etat_couleur};font-weight:700;"
        f"vertical-align:baseline;'>"
        f"{etat_libelle}"
        f"</td>"
        f"</tr>"
        f"<tr><td colspan='2' style='padding:4px 0 2px 10px;'>"
        f"<span style='color:#6c7c95;font-size:10px;letter-spacing:1px;'>CHARGES</span>"
        f"</td></tr>"
        f"<tr><td colspan='2' style='padding-left:10px;'>"
        f"<table width='100%' cellspacing='0' cellpadding='0'>{charges_rows}</table>"
        f"</td></tr>"
        f"<tr><td colspan='2' style='padding:8px 0 2px 10px;'>"
        f"<span style='color:#6c7c95;font-size:10px;letter-spacing:1px;'>CONTRAINTES</span>"
        f"</td></tr>"
        f"<tr><td colspan='2' style='padding-left:10px;'>"
        f"<table width='100%' cellspacing='0' cellpadding='0'>{contraintes_rows}</table>"
        f"</td></tr>"
        f"<tr><td colspan='2' style='padding-left:10px;'>{pills}</td></tr>"
        f"</table>"
    )


def _contraintes_et_detail_bloc(
    i: int,
    bloc: dict[str, Any],
    blocs: list[dict[str, Any]],
    paires: list[tuple[int, int, float]],
    memo_axiale_totale: dict[int, float],
) -> tuple[dict[str, Any], str, list[str]]:
    _, _, w, h = _geom_patch(bloc)
    aire = w * h  # surface de la face (m²) — utilisée pour la masse (volume = aire·1m)
    # Section transversale (m²) perpendiculaire au flux d'effort axial vertical, en
    # supposant une profondeur unitaire (1 m). C'est cette section qu'il faut utiliser
    # pour σ = F/A, pas la surface de la face.
    section_axiale = w
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
    sigma_axial = f_axial / section_axiale if section_axiale > 0 else 0.0

    tau_xy_moy = f_ext_x / section_axiale if section_axiale > 0 else 0.0
    tau_xy_max = 1.5 * tau_xy_moy

    sigma_max_normal = abs(sigma_axial)

    sigma_y = mat["sigma_y"]
    tau_lim = _tau_limite(mat)
    util_axial = sigma_max_normal / sigma_y * 100 if sigma_y > 0 else 0.0
    util_shear = abs(tau_xy_max) / tau_lim * 100 if tau_lim > 0 else 0.0

    E = mat["E"]
    nu = 0.3
    G = E / (2 * (1 + nu))

    # Raccourcissement axial: δ = F·L / (E·A) avec A = section transversale.
    delta_h = (f_axial * h) / (E * section_axiale) if section_axiale > 0 and E > 0 else 0.0
    delta_x = (f_ext_x * h) / (G * section_axiale) if section_axiale > 0 and G > 0 else 0.0

    util_max = max(util_axial, util_shear)
    if util_max < 80:
        couleur_util, libelle_etat = "#5ee1a1", "OK"
    elif util_max < 100:
        couleur_util, libelle_etat = "#ffb43a", "Limite"
    else:
        couleur_util, libelle_etat = "#ff6b6b", "Rupture"

    resume = (
        f"<tr>"
        f"<td style='padding:4px 0;'><b style='color:#f3f7ff'>Bloc {i + 1}</b>"
        f"<span style='color:#9eb4d9;'> · {bloc['material']}</span></td>"
        f"<td align='right' style='color:#eaf2ff;'>"
        f"<b>{sigma_max_normal/1e6:.1f}</b> "
        f"<span style='color:#6c7c95;font-size:10px'>MPa</span></td>"
        f"<td align='right' style='padding-left:10px;color:{couleur_util};'>"
        f"<b>{util_max:.0f}%</b></td>"
        f"</tr>"
    )

    lignes_detail = [
        _bloc_carte_detail(
            numero=i + 1,
            materiau=bloc["material"],
            edge_color=bloc.get("edgecolor", "#3b4b62"),
            etat_couleur=couleur_util,
            etat_libelle=libelle_etat,
            f_axial=f_axial,
            poids=poids,
            f_contact=f_contact,
            f_ext=f_ext,
            f_pression=f_pression,
            f_ext_x=f_ext_x,
            sigma_axial=sigma_axial,
            sigma_max_normal=sigma_max_normal,
            tau_xy_max=tau_xy_max,
            sigma_y=sigma_y,
            tau_lim=tau_lim,
            util_axial=util_axial,
            util_shear=util_shear,
        )
    ]

    stress = {
        "sigma_total": sigma_max_normal,
        "sigma_axial": sigma_axial,
        "sigma_max_normal": sigma_max_normal,
        "tau_xy_moy": tau_xy_moy,
        "tau_xy_max": tau_xy_max,
        "tau_lim": tau_lim,
        "util_axial": util_axial,
        "util_shear": util_shear,
        "ext_force": f_ext + f_pression,
        "ext_force_x": f_ext_x,
        "pressure": bloc["pressure"],
        "utilization": util_axial,
        "F_axial": f_axial,
        "delta_h": delta_h,
        "delta_x": delta_x,
    }
    return stress, resume, lignes_detail


def _hauteur_affichee_ecrasement(h0: float, stress: dict[str, Any] | None) -> float:
    """
    Hauteur (m) du polygone bloc telle que rendu sous charge : meme regle que le canvas
    (h0 - scale * delta_h), bornee pour eviter la pseudo-disparition du bloc.
    """
    if stress is None:
        return h0
    dh = float(stress.get("delta_h", 0.0))
    v_dh = dh * STRESS_DELTA_H_VISUAL_SCALE
    v_dh = max(-h0 * STRESS_VISUAL_MAX_EXTENSION, min(v_dh, h0 * STRESS_VISUAL_MAX_COMPRESSION))
    return h0 - v_dh


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
    Le contact est validé si la base de i_haut tombe dans la plage logique du sommet
    de i_bas (du sommet réel ``yi + hi`` jusqu'au sommet écrasé ``yi``), avec une
    marge ``tol``. Cela rend la détection insensible à la compression visuelle
    capée du bloc support, et évite que les blocs supérieurs « traversent » un
    bloc écrasé sans qu'aucune force ne soit transmise.
    """
    paires: list[tuple[int, int, float]] = []
    for i in range(len(blocs)):
        for j in range(len(blocs)):
            if i == j:
                continue

            xi, yi, wi, hi = _geom_patch(blocs[i])
            xj, yj, wj, hj = _geom_patch(blocs[j])

            sommet_min = yi + hi - hi * STRESS_VISUAL_MAX_COMPRESSION
            sommet_max = yi + hi + tol
            if sommet_min <= yj <= sommet_max and _overlaps_x(blocs[i], blocs[j]):
                largeur_contact = min(xi + wi, xj + wj) - max(xi, xj)
                fraction = largeur_contact / min(wi, wj)
                paires.append((i, j, fraction))
    return paires


def _resoudre_collision(idx_mobile: int, blocs: list[dict[str, Any]]) -> bool:
    """
    Repousse un bloc mobile hors collision par l'axe de moindre penetration.
    """
    bloc_m = blocs[idx_mobile]
    mx, my = bloc_m["x"], bloc_m["y"]
    largeur, hauteur = largeur_bloc(bloc_m), bloc_m["h0"]
    collision = False

    for i, autre_bloc in enumerate(blocs):
        if i == idx_mobile:
            continue

        patch_autre = autre_bloc["patch"]
        ox, oy, ow, oh = _geom_patch(autre_bloc)

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

    bloc_m["x"] = mx
    bloc_m["y"] = my
    bloc_m["patch"].set_xy([
        (mx,          my),
        (mx + largeur, my),
        (mx + largeur, my + hauteur),
        (mx,          my + hauteur),
                            ])
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

    paires = _contact_pairs(blocs) if gravite_active else []
    memo_axiale_totale: dict[int, float] = {}
    donnees_stress: list[dict[str, Any]] = []
    resumes_rows: list[str] = []
    lignes_detail: list[str] = []

    for i, bloc in enumerate(blocs):
        stress, resume_row, detail_fragments = _contraintes_et_detail_bloc(
            i, bloc, blocs, paires, memo_axiale_totale
        )
        donnees_stress.append(stress)
        resumes_rows.append(resume_row)
        lignes_detail.extend(detail_fragments)

    entete_html = (
        "<div style='padding:2px 0 8px 0;'>"
        "<span style='color:#6c7c95;font-size:10px;letter-spacing:1.2px;'>"
        "SECTION GLOBALE</span>"
        "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:6px;'>"
        f"<tr><td style='color:#9eb4d9;padding:2px 0;'>Aire</td>"
        f"<td align='right' style='color:#eaf2ff;'>{aire_totale:.3f} m²</td></tr>"
        f"<tr><td style='color:#9eb4d9;padding:2px 0;'>Masse linéique</td>"
        f"<td align='right' style='color:#eaf2ff;'>{masse:.0f} kg/m</td></tr>"
        f"<tr><td style='color:#9eb4d9;padding:2px 0;'>I<sub>xx</sub> / I<sub>yy</sub></td>"
        f"<td align='right' style='color:#eaf2ff;'>"
        f"{ixx:.3f} / {iyy:.3f} m⁴</td></tr>"
        "</table>"
        "</div>"
    )

    resume_html = (
        "<div style='padding:8px 0 4px 0;'>"
        "<span style='color:#6c7c95;font-size:10px;letter-spacing:1.2px;'>"
        "RÉSUMÉ PAR BLOC</span>"
        "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:6px;'>"
        + "".join(resumes_rows)
        + "</table>"
        "</div>"
    )

    contacts_html = ""
    if paires:
        rows = []
        for ib, ih, frac in paires:
            fc = donnees_stress[ih]["F_axial"]
            rows.append(
                f"<tr>"
                f"<td style='color:#9eb4d9;padding:2px 0;'>"
                f"<b style='color:#f3f7ff'>{ih + 1}</b> "
                f"<span style='color:#6c7c95'>→</span> "
                f"<b style='color:#f3f7ff'>{ib + 1}</b>"
                f"</td>"
                f"<td align='right' style='color:#eaf2ff;'>{_fmt_force(fc)}</td>"
                f"<td align='right' style='color:#9eb4d9;padding-left:10px;'>"
                f"{frac*100:.0f}%</td>"
                f"</tr>"
            )
        contacts_html = (
            "<div style='padding:10px 0 4px 0;'>"
            "<span style='color:#6c7c95;font-size:10px;letter-spacing:1.2px;'>"
            "CONTACTS</span>"
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:6px;'>"
            + "".join(rows)
            + "</table>"
            "</div>"
        )

    detail_html = (
        "<div style='padding:10px 0 4px 0;'>"
        "<span style='color:#6c7c95;font-size:10px;letter-spacing:1.2px;'>"
        "DÉTAIL</span>"
        + "".join(lignes_detail)
        + "</div>"
    )

    rapport = entete_html + resume_html + contacts_html + detail_html

    html_cdgr = (
        "<div>"
        "<span style='color:#9eb4d9;font-size:10px;letter-spacing:1.2px;'>"
        "CENTRE DE GRAVITÉ</span><br>"
        f"<span style='color:#f3f7ff;font-size:17px;font-weight:700;'>"
        f"({xg:.2f}, {yg:.2f})</span> "
        "<span style='color:#9eb4d9;font-size:11px;'>m</span>"
        "</div>"
    )

    return {
        "donnees_stress": donnees_stress,
        "paires": paires,
        "html_cdgr": html_cdgr,
        "html_rapport": rapport,
    }
