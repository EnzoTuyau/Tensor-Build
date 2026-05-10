"""Canvas matplotlib 2D et rendu des contraintes."""

from __future__ import annotations

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.cm import ScalarMappable
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QToolTip

from deuxDimensions.domain.constantes import (
    AXIS_XLIM,
    AXIS_YLIM,
    FALL_STEP,
    GRAVITY,
    GROUND_Y,
    HEATMAP_CELLES_MAX,
    MATERIAUX,
    RUPTURE_FADE_TICKS,
    RUPTURE_FALL_TICKS,
    RUPTURE_SHAKE_AMPLITUDE,
    RUPTURE_SHAKE_TICKS,
    RUPTURE_SHARD_COUNT,
    RUPTURE_SHARD_VX_RANGE,
    RUPTURE_SHARD_VY_RANGE,
    RUPTURE_TICK_MS,
    RUPTURE_TOTAL_TICKS,
    SNAP_TOL,
    STRESS_DELTA_H_VISUAL_SCALE,
    STRESS_VISUAL_MAX_COMPRESSION,
    STRESS_VISUAL_MAX_EXTENSION,
    TIMER_MS,
    UTIL_PHASE_ALERT_PCT,
    UTIL_PHASE_OK_PCT,
)
from deuxDimensions.domain import bloc_etat as etat_bloc
from deuxDimensions.domain.failure import evaluer_latch_rupture
from deuxDimensions.domain.geometry import sommets_quad_depuis_xy_patch, sommets_rectangle_ax
from deuxDimensions.domain.pressure_field import scalar_field_for_heatmap
from deuxDimensions.physics.calculs import _geom_patch, _hauteur_appui_max, _resoudre_collision
from deuxDimensions.rendering.canvas_visuel import (
    bleu_plasma_cmap,
    distance_px_point_au_segment,
    melanger_hex,
    ratio_effort_contact_visuel,
    teinte_contour_contrainte,
    teintes_face_et_contour_selon_util,
    vider_serie_artists,
)
from deuxDimensions.ui.bloc_tooltip import texte_infobulle_bloc
from deuxDimensions.ui.charge_tooltip import (
    texte_infobulle_force_horizontale,
    texte_infobulle_force_verticale,
    texte_infobulle_moment,
    texte_infobulle_pression,
)

# Style polygone « bloc sélectionné » (liste ou clic graphe)
_COULEUR_CONTOUR_SELECTION = "#ffb300"
_EP_POLY_SELECTION = 3.2
_EP_POLY_NORMAL = 1.8
_EP_RECT_CONTOUR_SELECTION = 3.4
_EP_RECT_CONTOUR_NORMAL = 1.5


def _generer_eclats(
    quad: list[tuple[float, float]],
    seed: int,
    n: int,
    vx_range: tuple[float, float],
    vy_range: tuple[float, float],
) -> list[dict]:
    """
    Découpe le quad en n éclats triangulaires (éventail depuis le centre) et leur
    affecte une vitesse initiale + une vitesse angulaire aléatoires.

    Retourne une liste de dicts: {polygon: [(x,y)...], cx, cy, vx, vy, omega, theta}
    """
    if len(quad) < 4:
        return []
    rng = np.random.default_rng(seed)
    cx = sum(p[0] for p in quad[:4]) / 4.0
    cy = sum(p[1] for p in quad[:4]) / 4.0

    perim: list[tuple[float, float]] = []
    for a in range(4):
        b = (a + 1) % 4
        perim.append(quad[a])
        perim.append(((quad[a][0] + quad[b][0]) / 2.0, (quad[a][1] + quad[b][1]) / 2.0))

    n = max(3, min(8, n))
    step = len(perim) / float(n)
    eclats: list[dict] = []
    for k in range(n):
        i0 = int(k * step) % len(perim)
        i1 = int((k + 1) * step) % len(perim)
        p0 = perim[i0]
        p1 = perim[i1]
        ex = (p0[0] + p1[0] + cx) / 3.0
        ey = (p0[1] + p1[1] + cy) / 3.0
        eclats.append(
            {
                "polygon": [(cx, cy), p0, p1],
                "cx": ex,
                "cy": ey,
                "vx": float(rng.uniform(*vx_range)),
                "vy": float(rng.uniform(*vy_range)),
                "omega": float(rng.uniform(-6.0, 6.0)),
                "theta": 0.0,
            }
        )
    return eclats


def _rotate_around(
    points: list[tuple[float, float]], cx: float, cy: float, theta: float
) -> list[tuple[float, float]]:
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    out: list[tuple[float, float]] = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return out


class Canvas2D(FigureCanvasQTAgg):
    """
    Fenetre matplotlib embarquee dans Qt.
    Gere l'affichage des blocs, le drag & drop, la gravite,
    et le rendu visuel des contraintes.
    """

    def __init__(self, parent=None, on_blocs_changes=None, on_rupture=None):
        fig = Figure(figsize=(12, 12), facecolor="white")
        fig.subplots_adjust(left=0.08, bottom=0.08, right=0.99, top=0.99)

        self.axes = fig.add_subplot(111)
        self.axes.set_aspect("auto")
        self.axes.set_facecolor("white")
        self.axes.grid(True, color="#dddddd", linewidth=0.6, linestyle="--")
        self.axes.set_xlim(*AXIS_XLIM)
        self.axes.set_ylim(*AXIS_YLIM)
        self.axes.set_autoscale_on(False)
        self.axes.set_autoscalex_on(False)
        self.axes.set_autoscaley_on(False)
        self.axes.set_xticks(range(-2, 13))
        self.axes.set_yticks(range(-1, 13))
        self.axes.tick_params(colors="#aaaaaa", labelsize=7)
        for bordure in self.axes.spines.values():
            bordure.set_edgecolor("#cccccc")

        super().__init__(fig)

        self.blocs = []
        self._idx_drag = None
        self._offset_drag = None
        self._on_blocs_changes = on_blocs_changes
        self._on_rupture = on_rupture
        self.gravite_active = False
        self.carte_chaleur = False
        self.animer_rupture = True
        self.reduce_motion = False

        self._patches_stress = []
        self._artistes_fleches = []
        self._patch_sol = None
        self._ligne_sol = None
        self._zones_contact_clic = []
        self._images_chaleur = []
        self._colorbar_heatmap = None
        self._callback_contact = None
        self.selection_charges_au_clic = False
        self._callback_bloc_pour_charges = None
        self._mode_placement_charge: str | None = None
        self._callback_placement_charge = None
        self._index_bloc_souligne = None
        self._cache_donnees_stress: list = []
        self._cache_paires_contact: list = []
        self._idx_tooltip_survol: int | None = None
        self._zones_charge_tooltip: list[dict] = []
        self._tooltip_ctx: tuple | None = None

        self._file_rupture: list[int] = []
        self._index_rupture_actif: int | None = None
        self._rupture_tick = 0
        self._rupture_quad_ref: list[tuple[float, float]] | None = None
        self._rupture_anchor_xy: tuple[float, float] | None = None
        self._rupture_info: dict | None = None
        self._eclats: list[dict] = []
        self._artistes_fx_rupture: list = []
        self._timer_rupture = QTimer()
        self._timer_rupture.setSingleShot(False)
        self._timer_rupture.timeout.connect(self._tick_rupture)

        self._timer_physique = QTimer()
        self._timer_physique.setInterval(TIMER_MS)
        self._timer_physique.timeout.connect(self._tick_physique)

        self._dessiner_sol()

        self.mpl_connect("button_press_event", self._souris_appui)
        self.mpl_connect("motion_notify_event", self._souris_mouvement)
        self.mpl_connect("button_release_event", self._souris_relache)
        self.mpl_connect("figure_leave_event", self._figure_quitte_canvas)

    def _point_global_infobulle_survol(self) -> QPoint:
        """Position globale pour infobulles au survol : suit le curseur (évite décalage canvas/Qt)."""
        return QCursor.pos() + QPoint(10, 14)

    def _figure_quitte_canvas(self, event):
        QToolTip.hideText()
        self._idx_tooltip_survol = None
        self._tooltip_ctx = None

    def _stress_pour_index_tooltip(self, idx: int):
        if idx < 0 or idx >= len(self._cache_donnees_stress):
            return None
        return self._cache_donnees_stress[idx]

    def _tooltip_si_survol_charge(self, event) -> tuple[str, tuple] | None:
        """Infobulle charges : segment ou disque en coordonnées écran."""
        if event.xdata is None or event.ydata is None:
            return None
        if not self._zones_charge_tooltip:
            return None
        dm = self.axes.transData.transform((event.xdata, event.ydata))
        px, py = float(dm[0]), float(dm[1])
        tol = 18.0
        best_d = tol + 1.0
        best: tuple[str, tuple] | None = None
        for z in self._zones_charge_tooltip:
            if z.get("disk"):
                cx, cy, r_data = z["disk"]
                c = self.axes.transData.transform((cx, cy))
                e = self.axes.transData.transform((cx + r_data, cy))
                r_px = float(np.hypot(e[0] - c[0], e[1] - c[1]))
                d = float(np.hypot(px - c[0], py - c[1]))
                lim = r_px + tol * 0.5
                if d <= lim and d < best_d:
                    best_d = d
                    best = (z["text"], z["ctx"])
                continue
            p0 = self.axes.transData.transform(z["p0"])
            p1 = self.axes.transData.transform(z["p1"])
            d = distance_px_point_au_segment(px, py, float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1]))
            if d <= tol and d < best_d:
                best_d = d
                best = (z["text"], z["ctx"])
        return best

    def _mettre_a_jour_tooltip_survol_bloc(self, event):
        """Infobulle : charges (flèches / moment) puis bloc sous le curseur."""
        if self._idx_drag is not None:
            return
        if event.inaxes != self.axes:
            if self._idx_tooltip_survol is not None:
                QToolTip.hideText()
                self._idx_tooltip_survol = None
            self._tooltip_ctx = None
            return

        hit_charge = self._tooltip_si_survol_charge(event)
        if hit_charge is not None:
            texte, ctx = hit_charge
            pg = self._point_global_infobulle_survol()
            QToolTip.showText(pg, texte, self)
            self._tooltip_ctx = ctx
            self._idx_tooltip_survol = None
            return

        idx = self._tester_clic(event)
        if idx is None:
            if self._idx_tooltip_survol is not None:
                QToolTip.hideText()
                self._idx_tooltip_survol = None
            self._tooltip_ctx = None
            return
        pg = self._point_global_infobulle_survol()
        ctx_bloc = ("bloc", idx)
        txt = texte_infobulle_bloc(
            idx,
            self.blocs[idx],
            self._stress_pour_index_tooltip(idx),
        )
        QToolTip.showText(pg, txt, self)
        self._tooltip_ctx = ctx_bloc
        self._idx_tooltip_survol = idx

    # ── Sol ──────────────────────────────────────────────────

    def _dessiner_sol(self):
        """Dessine la bande verte hachuree representant le sol encastre."""
        xmin, xmax = AXIS_XLIM

        if self._patch_sol:
            self._patch_sol.remove()
        if self._ligne_sol:
            self._ligne_sol.remove()

        self._patch_sol = Rectangle(
            (xmin, GROUND_Y - 0.5),
            xmax - xmin,
            0.5,
            facecolor="#e8f5e9",
            edgecolor="#388e3c",
            linewidth=2,
            hatch="////",
            zorder=0,
        )
        self.axes.add_patch(self._patch_sol)

        self._ligne_sol, = self.axes.plot(
            [xmin, xmax], [GROUND_Y, GROUND_Y], color="#388e3c", linewidth=2.5, zorder=1
        )

    def _verrouiller_vue(self):
        """Reapplique les limites d'axes (vue figee, pas d'auto-echelle)."""
        self.axes.set_xlim(*AXIS_XLIM)
        self.axes.set_ylim(*AXIS_YLIM)

    def activer_carte_chaleur(self, active):
        """Active ou non la carte scalaire contrainte/charge (Pa) sur les blocs."""
        self.carte_chaleur = bool(active)

    def matrice_heatmap_bloc(self, index):
        """Retourne (matrice Pa, (nx, ny)) pour export ou scripts, ou (None, None)."""
        if not (0 <= index < len(self.blocs)):
            return None, None
        rd = self.blocs[index]
        return rd.get(etat_bloc.CLE_MATRICE_THERMIQUE), rd.get(etat_bloc.CLE_MAILLAGE_THERMIQUE)

    def set_callback_contact_clic(self, callback):
        """Callback appele quand l'utilisateur clique une zone de contact."""
        self._callback_contact = callback

    def set_callback_bloc_pour_charges(self, callback):
        """Callback(index) quand l'utilisateur choisit un bloc pour les charges (sans drag)."""
        self._callback_bloc_pour_charges = callback

    def set_callback_placement_charge(self, callback):
        """Callback(mode_termine: str) quand l'utilisateur a place une charge via clic."""
        self._callback_placement_charge = callback

    def activer_mode_placement(self, mode: str | None):
        """Active/desactive le mode de placement par clic d'une charge.

        ``mode`` ∈ {None, "F_z", "F_x"}. Quand actif, le prochain clic sur un bloc
        ecrit la position dans le dict du bloc et le mode est desactive (one-shot).
        """
        if mode not in (None, "F_z", "F_x"):
            mode = None
        self._mode_placement_charge = mode
        if mode is None:
            self.unsetCursor()
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def _appliquer_placement_charge(self, idx: int, xdata: float, ydata: float) -> None:
        """Ecrit la position normalisee de la charge sur le bloc et sort du mode."""
        if not (0 <= idx < len(self.blocs)):
            return
        mode = self._mode_placement_charge
        bloc = self.blocs[idx]
        w = max(1e-6, float(bloc["largeur"]))
        h = max(1e-6, float(bloc["h0"]))
        x_norm = (float(xdata) - float(bloc["x"])) / w
        y_norm = (float(ydata) - float(bloc["y"])) / h
        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))
        if mode == "F_z":
            bloc["ext_force_x_offset"] = x_norm
        elif mode == "F_x":
            bloc["ext_force_x_y_offset"] = y_norm
            bloc["ext_force_x_side"] = "left" if x_norm < 0.5 else "right"
        self.activer_mode_placement(None)
        if callable(self._callback_placement_charge):
            self._callback_placement_charge(mode)
        self._notifier(refresh_list=False)

    def definir_surlignage_bloc(self, index):
        """
        Met en évidence le bloc index (contour du Polygon).
        index None ou hors limite : aucun surlignage.
        """
        if index is None or not (0 <= index < len(self.blocs)):
            self._index_bloc_souligne = None
        else:
            self._index_bloc_souligne = index
        self._appliquer_styles_polygones_blocs()
        self.draw_idle()

    def _appliquer_styles_polygones_blocs(self):
        """Contour du patch bloc : feedback utilisation, puis surlignage selection."""
        for i, bloc in enumerate(self.blocs):
            patch = bloc["patch"]
            mp = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])
            ec_mat = bloc.get("edgecolor") or mp["edge"]
            ec_fb = bloc.get(etat_bloc.CLE_CONTOUR_UTIL_DESSIN, ec_mat)
            selectionne = self._index_bloc_souligne is not None and i == self._index_bloc_souligne
            if selectionne:
                patch.set_edgecolor(_COULEUR_CONTOUR_SELECTION)
                patch.set_linewidth(_EP_POLY_SELECTION)
            elif bloc.get(etat_bloc.CLE_RUPTURE_EN_COURS):
                patch.set_edgecolor(ec_fb)
                patch.set_linewidth(_EP_POLY_NORMAL + 0.2)
            else:
                patch.set_edgecolor(ec_fb)
                extra = 0.0
                if UTIL_PHASE_OK_PCT <= bloc.get(etat_bloc.CLE_DERNIER_UTIL_DESSIN, 0.0) < UTIL_PHASE_ALERT_PCT:
                    extra = 0.4
                elif bloc.get(etat_bloc.CLE_DERNIER_UTIL_DESSIN, 0.0) >= UTIL_PHASE_ALERT_PCT:
                    extra = 0.9
                patch.set_linewidth(_EP_POLY_NORMAL + extra)

    def _donnees_vers_global(self, xd, yd):
        """Convertit des coordonnees "donnees" matplotlib en QPoint global ecran."""
        disp = self.axes.transData.transform((xd, yd))
        x_disp, y_disp = float(disp[0]), float(disp[1])
        h = float(self.figure.bbox.height)
        x_qt = int(round(x_disp))
        y_qt = int(round(h - y_disp))
        return self.mapToGlobal(QPoint(x_qt, y_qt))

    def _souris_vers_global(self, event):
        """Position souris evenement mpl -> coordonnees globales Qt (ou None)."""
        try:
            x, y = float(event.x), float(event.y)
        except (TypeError, ValueError):
            return None
        h = float(self.figure.bbox.height)
        if h < 1:
            return None
        return self.mapToGlobal(QPoint(int(round(x)), int(round(h - y))))

    def rectangle_axes_global(self):
        """Rectangle ecran couvrant la zone tracee des axes."""
        fig = self.figure
        try:
            self.draw()
        except Exception:
            pass
        try:
            r = self.axes.get_window_extent(renderer=self.get_renderer())
        except Exception:
            r = self.axes.get_window_extent()
        h_fig = float(fig.bbox.height)
        if h_fig < 1 or r.width < 2 or r.height < 2:
            g = self.mapToGlobal(QPoint(0, 0))
            return QRect(g.x(), g.y(), max(1, self.width()), max(1, self.height()))
        x0 = int(round(r.x0))
        y0 = int(round(h_fig - r.y1))
        w = max(1, int(round(r.width)))
        h = max(1, int(round(r.height)))
        tl = self.mapToGlobal(QPoint(x0, y0))
        return QRect(tl.x(), tl.y(), w, h)

    def point_contact_global(self, hit):
        """Point global au centre horizontal de l'interface de contact."""
        return self._donnees_vers_global(hit["cx"], hit["y_if"])

    def rafraichir_position_infobulle_contact(self, tip):
        """Recalcule les limites de glissement apres resize / redraw du graphe."""
        tip.set_plot_bounds_global(self.rectangle_axes_global())
        tip.clamp_to_bounds()

    # ── Gravite ──────────────────────────────────────────────

    def activer_gravite(self, active):
        """Active ou desactive la simulation de chute libre."""
        self.gravite_active = active
        if active:
            self._timer_physique.start()
        else:
            self._timer_physique.stop()

    def _tick_physique(self):
        """
        Appelle periodiquement quand la gravite est active.
        Fait descendre chaque bloc vers son plancher naturel
        (sol ou dessus du bloc le plus proche en dessous).
        """
        if not self.blocs:
            return

        a_bouge = False
        ordre = sorted(range(len(self.blocs)), key=lambda i: self.blocs[i]["y"])
        stress_cache = self._cache_donnees_stress
        if len(stress_cache) != len(self.blocs):
            stress_cache = None

        for idx in ordre:
            if idx == self._idx_drag:
                continue

            bloc = self.blocs[idx]
            if bloc.get(etat_bloc.CLE_RUPTURE_EN_COURS):
                continue
            patch = bloc["patch"]
            x = bloc["x"]
            y = bloc["y"]
            plancher = _hauteur_appui_max(self.blocs, idx, stress_cache)

            if y > plancher + 0.001:
                nouvelle_y = max(plancher, y - FALL_STEP)
                bloc["y"] = nouvelle_y
                patch.set_xy(sommets_rectangle_ax(x, nouvelle_y, bloc["largeur"], bloc["h0"]))
                a_bouge = True

        if a_bouge:
            self._notifier(refresh_list=False)

    # ── Gestion des blocs ────────────────────────────────────

    def ajouter_bloc(self, largeur, hauteur, materiau="Acier", densite=None):
        """
        Cree un nouveau bloc rectangulaire et l'ajoute au canvas.
        Si la gravite est active, il apparait en haut et tombe.
        Sinon, il se pose directement au-dessus de la pile.
        """
        mp = MATERIAUX.get(materiau, MATERIAUX["Acier"])
        if densite is None:
            densite = mp["density"]
        fc, ec = mp["face"], mp["edge"]

        if self.gravite_active:
            y_depart = 9.0
            x_depart = 1.0
        else:
            y_depart = GROUND_Y
            if self.blocs:
                y_depart = max(b["y"] + b["h0"] for b in self.blocs)
            x_depart = 0.5

        points = sommets_rectangle_ax(x_depart, y_depart, largeur, hauteur)

        patch = Polygon(
            points,
            closed=True,
            facecolor=fc,
            edgecolor=ec,
            linewidth=1.8,
            zorder=5,
            alpha=0.9,
        )
        self.axes.add_patch(patch)

        self.blocs.append(
            {
                "patch": patch,
                "x": x_depart,
                "y": y_depart,
                "largeur": largeur,
                "h0": hauteur,
                "material": materiau,
                "density": densite,
                "edgecolor": ec,
                "ext_force": 0.0,
                "ext_force_x": 0.0,
                "ext_force_x_offset": 0.5,
                "ext_force_x_y_offset": 0.5,
                "ext_force_x_side": "left",
                "moment": 0.0,
                "pressure": 0.0,
                etat_bloc.CLE_MATRICE_THERMIQUE: None,
                etat_bloc.CLE_MAILLAGE_THERMIQUE: None,
                etat_bloc.CLE_ARMEMENT_RUPTURE: True,
                etat_bloc.CLE_RUPTURE_EN_COURS: False,
            }
        )
        self._notifier()

    def supprimer_bloc(self, index, notifier=True):
        """Supprime le bloc a l'index donne du canvas et de la liste."""
        if 0 <= index < len(self.blocs):
            self._retirer_index_file_rupture(index)
            self.blocs[index]["patch"].remove()
            self.blocs.pop(index)
            if self._index_bloc_souligne is not None:
                if index == self._index_bloc_souligne:
                    self._index_bloc_souligne = None
                elif index < self._index_bloc_souligne:
                    self._index_bloc_souligne -= 1
            if notifier:
                self._notifier()

    # ── Drag & drop ──────────────────────────────────────────

    def _tester_clic_contact(self, event):
        """Si le clic tombe dans la bande d'un joint, retourne le dict de hit."""
        if event.xdata is None or event.ydata is None:
            return None
        xd, yd = event.xdata, event.ydata
        for z in reversed(self._zones_contact_clic):
            if z["x0"] <= xd <= z["x1"] and z["y0"] <= yd <= z["y1"]:
                return {
                    "i_bot": z["i_bot"],
                    "i_top": z["i_top"],
                    "frac": z["frac"],
                    "F_c": z["F_c"],
                    "cx": z["cx"],
                    "y_if": z["y_if"],
                }
        return None

    def _tester_clic(self, event):
        """
        Retourne l'index du bloc clique, en partant du dessus (dernier ajoute).
        Retourne None si le clic est dans le vide.
        """

        if event.xdata is None or event.ydata is None:
            return None
        

        for i, bloc in enumerate(reversed(self.blocs)):
            idx = len(self.blocs) - 1 - i
            patch = bloc["patch"]
            # contains_point(xdata,ydata) est faux ici : il faut les coords display,
            # ou patch.contains(event) qui applique le bon transform.
            dedans, _ = patch.contains(event)
            if dedans:
                return idx
        return None

    def _souris_appui(self, event):
        if event.inaxes != self.axes or event.button != 1:
            return
        # Mode placement de charge : prioritaire sur tout le reste.
        if self._mode_placement_charge is not None and event.xdata is not None:
            idx_p = self._tester_clic(event)
            if idx_p is not None:
                self._appliquer_placement_charge(idx_p, event.xdata, event.ydata)
                return
            # Clic en dehors d'un bloc : sortir du mode sans rien changer.
            self.activer_mode_placement(None)
            if callable(self._callback_placement_charge):
                self._callback_placement_charge(None)
            return
        hit_c = self._tester_clic_contact(event)
        if hit_c is not None and self._callback_contact:
            QToolTip.hideText()
            self._idx_tooltip_survol = None
            self._tooltip_ctx = None
            pg = self._souris_vers_global(event)
            if pg is not None:
                hit_c["_press_global"] = pg
            self._callback_contact(hit_c)
            return
        idx = self._tester_clic(event)
        if (
            idx is not None
            and self.selection_charges_au_clic
            and self._callback_bloc_pour_charges is not None
        ):
            QToolTip.hideText()
            self._idx_tooltip_survol = None
            self._tooltip_ctx = None
            self._callback_bloc_pour_charges(idx)
            return
        if idx is not None:
            QToolTip.hideText()
            self._idx_tooltip_survol = None
            self._tooltip_ctx = None
            self._idx_drag = idx

            self._offset_drag = (
                event.xdata - self.blocs[idx]["x"],
                event.ydata - self.blocs[idx]["y"],
            )
            

    def _souris_mouvement(self, event):
        if event.inaxes == self.axes and self._idx_drag is None:
            self._mettre_a_jour_tooltip_survol_bloc(event)
        if self._idx_drag is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return

        bloc = self.blocs[self._idx_drag]
        patch = bloc["patch"]

        w = bloc["largeur"]
        h = bloc["h0"]

        xmin, xmax = self.axes.get_xlim()
        _, ymax = self.axes.get_ylim()
        

        x = max(xmin, min(xmax - w, event.xdata - self._offset_drag[0]))
        y = max(GROUND_Y, min(ymax - h, event.ydata - self._offset_drag[1]))

        bloc["x"] = x
        bloc["y"] = y

        patch.set_xy(sommets_rectangle_ax(x, y, w, h))
    


        _resoudre_collision(self._idx_drag, self.blocs)
        self.draw_idle()

    def _souris_relache(self, event):
        self._idx_drag = None
        self._offset_drag = None
        self._notifier()

    def _notifier(self, refresh_list=True):
        """Previent l'app (rafraichir la liste des blocs ou non, puis physique)."""
        if self._on_blocs_changes:
            self._on_blocs_changes(refresh_list=refresh_list)

    def _retirer_index_file_rupture(self, removed_idx: int):
        """Met a jour la file et l'animation si un bloc est supprime manuellement."""
        if self._index_rupture_actif == removed_idx:
            self._timer_rupture.stop()
            self._index_rupture_actif = None
            self._vider_fx_rupture()
            self._rupture_tick = 0
            self._rupture_quad_ref = None
            self._rupture_anchor_xy = None
            self._rupture_info = None
            self._eclats.clear()
        elif self._index_rupture_actif is not None and self._index_rupture_actif > removed_idx:
            self._index_rupture_actif -= 1
        new_file: list[int] = []
        for j in self._file_rupture:
            if j == removed_idx:
                continue
            new_file.append(j if j < removed_idx else j - 1)
        self._file_rupture = new_file

    def _vider_fx_rupture(self):
        vider_serie_artists(self._artistes_fx_rupture)
        self._eclats.clear()

    def verifier_ruptures_apres_physique(self, donnees_stress: list) -> None:
        """Appele apres calcul des contraintes : enqueue ruptures selon latch."""
        for i, (bloc, stress) in enumerate(zip(self.blocs, donnees_stress)):
            if stress is None:
                continue
            if i == self._index_rupture_actif:
                continue
            if bloc.get(etat_bloc.CLE_RUPTURE_EN_COURS):
                continue
            if i in self._file_rupture:
                continue
            util = float(stress.get("utilization", stress.get("util_axial_flex", 0.0)))
            armed = bool(bloc.get(etat_bloc.CLE_ARMEMENT_RUPTURE, True))
            declenche, nouvel_armed = evaluer_latch_rupture(util, armed)
            bloc[etat_bloc.CLE_ARMEMENT_RUPTURE] = nouvel_armed
            if declenche:
                bloc["_util_rupture"] = util
                self._enfiler_rupture(i)

    def _enfiler_rupture(self, idx: int) -> None:
        if not (0 <= idx < len(self.blocs)):
            return
        if idx == self._index_rupture_actif or idx in self._file_rupture:
            return
        self._file_rupture.append(idx)
        self._demarrer_traitement_file_rupture()

    def _demarrer_traitement_file_rupture(self) -> None:
        if self._index_rupture_actif is not None or not self._file_rupture:
            return
        idx = self._file_rupture.pop(0)
        if not (0 <= idx < len(self.blocs)):
            self._demarrer_traitement_file_rupture()
            return
        bloc = self.blocs[idx]
        bloc[etat_bloc.CLE_RUPTURE_EN_COURS] = True
        self._index_rupture_actif = idx
        self._rupture_tick = 0
        self._vider_fx_rupture()

        xy = bloc["patch"].get_xy()
        quad = sommets_quad_depuis_xy_patch(xy)
        self._rupture_quad_ref = [tuple(p) for p in quad] if len(quad) >= 4 else None
        self._rupture_anchor_xy = (bloc["x"], bloc["y"])

        util_pct = float(bloc.get("_util_rupture", 0.0))
        self._rupture_info = {
            "idx": idx,
            "material": bloc.get("material", "?"),
            "util_pct": util_pct,
            "x": bloc["x"],
            "y": bloc["y"],
            "w": bloc["largeur"],
            "h": bloc["h0"],
        }

        if not self.animer_rupture or self.reduce_motion:
            self._fin_animation_rupture()
            return
        self._timer_rupture.start(RUPTURE_TICK_MS)

    def _tick_rupture(self) -> None:
        idx = self._index_rupture_actif
        if idx is None or not (0 <= idx < len(self.blocs)):
            self._timer_rupture.stop()
            self._vider_fx_rupture()
            self._index_rupture_actif = None
            self._rupture_quad_ref = None
            self._rupture_anchor_xy = None
            self._demarrer_traitement_file_rupture()
            return
        bloc = self.blocs[idx]
        patch = bloc["patch"]
        self._rupture_tick += 1
        t = self._rupture_tick

        ref = self._rupture_quad_ref
        anchor = self._rupture_anchor_xy
        if ref is None or anchor is None:
            self._fin_animation_rupture()
            return

        n_shake = RUPTURE_SHAKE_TICKS
        n_fall = RUPTURE_FALL_TICKS
        dt = RUPTURE_TICK_MS / 1000.0

        if t <= n_shake:
            sign = 1.0 if (t % 2) else -1.0
            decay = 1.0 - (t - 1) / max(1.0, float(n_shake))
            offset = sign * RUPTURE_SHAKE_AMPLITUDE * decay
            shaken = [(p[0] + offset, p[1]) for p in ref]
            patch.set_xy(shaken)
            patch.set_edgecolor("#b71c1c")
            patch.set_alpha(0.85)
        elif t == n_shake + 1:
            patch.set_alpha(0.0)
            self._eclats = _generer_eclats(
                ref,
                seed=8200 + idx,
                n=RUPTURE_SHARD_COUNT,
                vx_range=RUPTURE_SHARD_VX_RANGE,
                vy_range=RUPTURE_SHARD_VY_RANGE,
            )
            for shard in self._eclats:
                poly = Polygon(
                    shard["polygon"],
                    closed=True,
                    facecolor=bloc.get("edgecolor", "#7a1f1f"),
                    edgecolor="#3e2723",
                    linewidth=1.1,
                    alpha=0.95,
                    zorder=14,
                )
                self.axes.add_patch(poly)
                shard["artist"] = poly
                self._artistes_fx_rupture.append(poly)
        else:
            tf = (t - n_shake) / float(n_fall)
            alpha_phase_start = (n_fall - RUPTURE_FADE_TICKS) / float(n_fall)
            for shard in self._eclats:
                shard["vy"] -= GRAVITY * dt
                shard["cx"] += shard["vx"] * dt
                shard["cy"] += shard["vy"] * dt
                shard["theta"] += shard["omega"] * dt
                base = shard["polygon"]
                bx = sum(p[0] for p in base) / len(base)
                by = sum(p[1] for p in base) / len(base)
                translated = [
                    (p[0] - bx + shard["cx"], p[1] - by + shard["cy"]) for p in base
                ]
                rotated = _rotate_around(
                    translated, shard["cx"], shard["cy"], shard["theta"]
                )
                shard["artist"].set_xy(rotated)
                if tf > alpha_phase_start:
                    fade_t = (tf - alpha_phase_start) / max(
                        1e-6, 1.0 - alpha_phase_start
                    )
                    shard["artist"].set_alpha(max(0.0, 0.95 * (1.0 - min(1.0, fade_t))))

        if self._rupture_tick >= RUPTURE_TOTAL_TICKS:
            self._fin_animation_rupture()
            return
        self.draw_idle()

    def _fin_animation_rupture(self) -> None:
        self._timer_rupture.stop()
        idx = self._index_rupture_actif
        info = self._rupture_info
        self._index_rupture_actif = None
        self._rupture_tick = 0
        self._rupture_quad_ref = None
        self._rupture_anchor_xy = None
        self._rupture_info = None
        self._vider_fx_rupture()
        if callable(self._on_rupture) and info is not None:
            self._on_rupture(
                info["idx"] + 1,
                info["material"],
                info["util_pct"],
            )
        if idx is not None and 0 <= idx < len(self.blocs):
            self.supprimer_bloc(idx, notifier=False)
            self._notifier()
        self._demarrer_traitement_file_rupture()

    def activer_animer_rupture(self, active: bool) -> None:
        self.animer_rupture = bool(active)

    def activer_reduce_motion(self, active: bool) -> None:
        self.reduce_motion = bool(active)

    def _retirer_colorbar_heatmap(self):
        """Retire la colorbar carte thermique pour eviter accumulation d'artistes."""
        if self._colorbar_heatmap is not None:
            try:
                self._colorbar_heatmap.remove()
            except Exception:
                pass
            self._colorbar_heatmap = None
        try:
            self.figure.subplots_adjust(left=0.08, bottom=0.08, right=0.99, top=0.99)
        except Exception:
            pass

    # ── Rendu visuel des contraintes ─────────────────────────

    def dessiner_contraintes(self, donnees_stress, paires_contact):
        """
        Couche contraintes : carte scalaire (σ normale + charge répartie, Pa)
        ou barres RdYlGn selon sigma. Joints cliquables, effort affiche.
        """
        # Configuration de l'animation (delta_h en m, meme echelle que la gravite / appui)
        v_scale = STRESS_DELTA_H_VISUAL_SCALE
        self._verrouiller_vue()
        vider_serie_artists(self._images_chaleur)
        if not self.carte_chaleur:
            self._retirer_colorbar_heatmap()

        for p in self._patches_stress:
            try:
                p.remove()
            except Exception:
                pass
        self._patches_stress.clear()

        for a in self._artistes_fleches:
            try:
                a.remove()
            except Exception:
                pass
        self._artistes_fleches.clear()
        self._zones_charge_tooltip.clear()

        self._zones_contact_clic.clear()

        if not self.blocs or not donnees_stress:
            for bloc in self.blocs:
                bloc[etat_bloc.CLE_MATRICE_THERMIQUE] = None
                bloc[etat_bloc.CLE_MAILLAGE_THERMIQUE] = None
            self._cache_donnees_stress = []
            self._cache_paires_contact = []
            self._retirer_colorbar_heatmap()
            self._appliquer_styles_polygones_blocs()
            self._verrouiller_vue()
            self.draw_idle()
            return

        for bloc in self.blocs:
            bloc[etat_bloc.CLE_MATRICE_THERMIQUE] = None
            bloc[etat_bloc.CLE_MAILLAGE_THERMIQUE] = None

        self._cache_donnees_stress = list(donnees_stress)
        self._cache_paires_contact = list(paires_contact)

        norm_hm = None
        carte_couleurs_hm = None
        heatmap_any = False

        if self.carte_chaleur:
            vmax_hm = 0.0
            for bloc, stress in zip(self.blocs, donnees_stress):
                if stress is None:
                    continue
                if bloc.get(etat_bloc.CLE_RUPTURE_EN_COURS):
                    continue
                h0 = bloc["h0"]
                w = bloc["largeur"]
                x, y = bloc["x"], bloc["y"]
                dh = stress.get("delta_h", 0.0)
                v_dh = dh * v_scale
                h_animee = max(0.01, h0 - v_dh)
                nx = max(2, min(HEATMAP_CELLES_MAX, int(w * 10)))
                ny = max(2, min(HEATMAP_CELLES_MAX, int(h_animee * 10)))
                pa_pre = scalar_field_for_heatmap(bloc, stress, y_coin_bas=y, h=h_animee, nx=nx, ny=ny)
                vmax_hm = max(vmax_hm, float(np.max(pa_pre)))
            vmax_hm = max(vmax_hm, 1.0)
            norm_hm = mcolors.Normalize(vmin=0.0, vmax=vmax_hm)
            carte_couleurs_hm = bleu_plasma_cmap()
        else:
            self.figure.subplots_adjust(left=0.08, bottom=0.08, right=0.99, top=0.99)
            toutes_sigmas = [abs(d["sigma_total"]) for d in donnees_stress if d]
            sigma_max_global = max(toutes_sigmas) if any(s > 0 for s in toutes_sigmas) else 1.0
            colormap = cm.get_cmap("RdYlGn_r")
            normaliseur = mcolors.Normalize(vmin=0, vmax=sigma_max_global)

        for i, (bloc, stress) in enumerate(zip(self.blocs, donnees_stress)):
            if stress is None:
                continue

            h0 = bloc["h0"]
            w = bloc["largeur"]
            x, y = bloc["x"], bloc["y"]

            dh = stress.get("delta_h", 0.0)
            dx = stress.get("delta_x", 0.0)

            v_dh = dh * v_scale
            v_dh = max(
                -h0 * STRESS_VISUAL_MAX_EXTENSION,
                min(v_dh, h0 * STRESS_VISUAL_MAX_COMPRESSION),
            )
            v_dx = dx * v_scale
            v_dx = max(-w * 0.15, min(v_dx, w * 0.15))

            h_animee = h0 - v_dh

            nouveaux_points = [
                (x, y),
                (x + w, y),
                (x + w + v_dx, y + h_animee),
                (x + v_dx, y + h_animee),
            ]
            breaking = bool(bloc.get(etat_bloc.CLE_RUPTURE_EN_COURS))
            if not breaking:
                bloc["patch"].set_xy(nouveaux_points)
            h = h_animee if not breaking else h0

            util = float(stress.get("utilization", stress.get("util_axial_flex", 0.0)))
            bloc[etat_bloc.CLE_DERNIER_UTIL_DESSIN] = util
            mp_mat = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])
            ec = bloc.get("edgecolor") or mp_mat["edge"]
            fc_u, ec_u = teintes_face_et_contour_selon_util(mp_mat["face"], ec, util)
            bloc[etat_bloc.CLE_CONTOUR_UTIL_DESSIN] = ec_u
            if not breaking:
                bloc["patch"].set_facecolor(fc_u)
                bloc["patch"].set_alpha(0.9)

            if not breaking:
                if self.carte_chaleur and norm_hm is not None:
                    nx = max(2, min(HEATMAP_CELLES_MAX, int(w * 10)))
                    ny = max(2, min(HEATMAP_CELLES_MAX, int(h * 10)))
                    pa = scalar_field_for_heatmap(bloc, stress, y_coin_bas=y, h=h, nx=nx, ny=ny)
                    bloc[etat_bloc.CLE_MATRICE_THERMIQUE] = pa
                    bloc[etat_bloc.CLE_MAILLAGE_THERMIQUE] = (nx, ny)
                    xs = [p[0] for p in nouveaux_points]
                    ys = [p[1] for p in nouveaux_points]
                    extent = (min(xs), max(xs), min(ys), max(ys))
                    im = self.axes.imshow(
                        pa,
                        extent=extent,
                        origin="lower",
                        aspect="auto",
                        interpolation="bilinear",
                        cmap=carte_couleurs_hm,
                        norm=norm_hm,
                        zorder=6,
                        clip_on=True,
                    )
                    clip_poly = Polygon(nouveaux_points, closed=True)
                    im.set_clip_path(clip_poly.get_path(), transform=self.axes.transData)
                    im.set_alpha(0.93)
                    self._images_chaleur.append(im)
                    heatmap_any = True
                elif abs(stress.get("sigma_bending_top", 0)) > 1:
                    for decalage, sigma in [
                        (0, stress["sigma_bending_bot"]),
                        (h / 2, stress["sigma_bending_top"]),
                    ]:
                        couleur = colormap(normaliseur(abs(sigma)))
                        rect = Rectangle(
                            (x, y + decalage),
                            w,
                            h / 2,
                            facecolor=couleur,
                            edgecolor="none",
                            alpha=0.55,
                            zorder=6,
                        )
                        self.axes.add_patch(rect)
                        self._patches_stress.append(rect)
                else:
                    couleur = colormap(normaliseur(abs(stress["sigma_total"])))
                    rect = Rectangle(
                        (x, y),
                        w,
                        h,
                        facecolor=couleur,
                        edgecolor="none",
                        alpha=0.55,
                        zorder=6,
                    )
                    self.axes.add_patch(rect)
                    self._patches_stress.append(rect)

            selectionne = self._index_bloc_souligne is not None and i == self._index_bloc_souligne
            if breaking:
                ec_rect = "#546e7a"
                lw_rect = _EP_RECT_CONTOUR_NORMAL
            elif selectionne:
                ec_rect = _COULEUR_CONTOUR_SELECTION
                lw_rect = _EP_RECT_CONTOUR_SELECTION
            else:
                ec_rect = teinte_contour_contrainte(ec, util)
                lw_rect = _EP_RECT_CONTOUR_NORMAL

            contour = Rectangle(
                (x, y),
                w,
                h,
                facecolor="none",
                edgecolor=ec_rect,
                linewidth=lw_rect,
                linestyle="--" if breaking else "solid",
                zorder=7,
            )
            self.axes.add_patch(contour)
            self._patches_stress.append(contour)

            if not breaking and abs(y - GROUND_Y) < SNAP_TOL * 2.0:
                sh = min(0.09, max(0.04, h * 0.22))
                sol_sh = Rectangle(
                    (x, y),
                    w,
                    sh,
                    facecolor="#000000",
                    edgecolor="none",
                    alpha=0.34,
                    zorder=8,
                )
                self.axes.add_patch(sol_sh)
                self._patches_stress.append(sol_sh)

            if not breaking and abs(bloc.get("ext_force", 0.0)) > 1e-6:
                cx = x + w * float(bloc.get("ext_force_x_offset", 0.5))
                y_top = y + h
                tail_y = y_top + max(0.28, min(0.75, h * 0.32))
                fleche = FancyArrowPatch(
                    (cx, tail_y),
                    (cx, y_top),
                    arrowstyle="-|>",
                    mutation_scale=16,
                    color="#d32f2f",
                    linewidth=2.5,
                    zorder=11,
                )
                self.axes.add_patch(fleche)
                self._artistes_fleches.append(fleche)
                mr = max(0.02, min(w, h) * 0.032)
                pt_f = Circle(
                    (cx, y_top),
                    radius=mr,
                    facecolor="#ffcdd2",
                    edgecolor="#b71c1c",
                    linewidth=1.8,
                    zorder=12,
                )
                self.axes.add_patch(pt_f)
                self._patches_stress.append(pt_f)
                self._zones_charge_tooltip.append(
                    {
                        "p0": (cx, tail_y),
                        "p1": (cx, y_top),
                        "text": texte_infobulle_force_verticale(i, bloc, stress),
                        "ctx": ("Fv", i),
                    }
                )

            if not breaking and abs(bloc.get("pressure", 0.0)) > 1e-6:
                nb_fleches = max(3, int(w * 2))
                y_top = y + h
                for k in range(nb_fleches):
                    xf = x + (k + 0.5) * w / nb_fleches
                    yt = y_top + max(0.18, min(0.42, h * 0.22))
                    f = FancyArrowPatch(
                        (xf, yt),
                        (xf, y_top),
                        arrowstyle="-|>",
                        mutation_scale=9,
                        color="#e65100",
                        linewidth=1.2,
                        zorder=11,
                    )
                    self.axes.add_patch(f)
                    self._artistes_fleches.append(f)
                    mr = max(0.015, min(w, h) * 0.024)
                    pt_p = Circle(
                        (xf, y_top),
                        radius=mr,
                        facecolor="#ffe0b2",
                        edgecolor="#e65100",
                        linewidth=1.2,
                        zorder=12,
                    )
                    self.axes.add_patch(pt_p)
                    self._patches_stress.append(pt_p)
                    self._zones_charge_tooltip.append(
                        {
                            "p0": (xf, yt),
                            "p1": (xf, y_top),
                            "text": texte_infobulle_pression(i, bloc, k, nb_fleches),
                            "ctx": ("p", i, k),
                        }
                    )

            if not breaking:
                fx_b = float(bloc.get("ext_force_x", 0.0))
                if abs(fx_b) > 1e-6:
                    cy = y + h * float(bloc.get("ext_force_x_y_offset", 0.5))
                    side = str(bloc.get("ext_force_x_side", "left"))
                    overhang = max(0.35, min(0.9, w * 0.35))
                    # La direction de la flèche dépend de side: depuis l'extérieur
                    # de la face cliquée vers l'intérieur du bloc.
                    if side == "left":
                        x_tip, x_tail = x, x - overhang
                    else:
                        x_tip, x_tail = x + w, x + w + overhang
                    fh = FancyArrowPatch(
                        (x_tail, cy),
                        (x_tip, cy),
                        arrowstyle="-|>",
                        mutation_scale=14,
                        color="#6a1b9a",
                        linewidth=2.2,
                        zorder=11,
                    )
                    self.axes.add_patch(fh)
                    self._artistes_fleches.append(fh)
                    mr = max(0.02, min(w, h) * 0.03)
                    pt_x = Circle(
                        (x_tip, cy),
                        radius=mr,
                        facecolor="#ede7f6",
                        edgecolor="#4a148c",
                        linewidth=1.6,
                        zorder=12,
                    )
                    self.axes.add_patch(pt_x)
                    self._patches_stress.append(pt_x)
                    self._zones_charge_tooltip.append(
                        {
                            "p0": (x_tail, cy),
                            "p1": (x_tip, cy),
                            "text": texte_infobulle_force_horizontale(i, bloc, stress),
                            "ctx": ("Fx", i),
                        }
                    )

            if not breaking and abs(bloc.get("moment", 0.0)) > 1e-6:
                cx_m = x + w / 2
                cy_m = y + h / 2
                mom = float(bloc["moment"])
                arc_r = -0.5 if mom > 0 else 0.5
                arc_patch = FancyArrowPatch(
                    (cx_m + 0.26 * w, cy_m - 0.02 * h),
                    (cx_m - 0.26 * w, cy_m - 0.02 * h),
                    connectionstyle=f"arc3,rad={arc_r}",
                    arrowstyle="-|>",
                    mutation_scale=13,
                    color="#f9a825",
                    linewidth=2.3,
                    zorder=11,
                )
                self.axes.add_patch(arc_patch)
                self._artistes_fleches.append(arc_patch)
                r_disk = max(0.12, min(w, h) * 0.28)
                self._zones_charge_tooltip.append(
                    {
                        "disk": (cx_m, cy_m, r_disk),
                        "text": texte_infobulle_moment(i, bloc),
                        "ctx": ("M", i),
                    }
                )

        def _y_interface(pa):
            i_bot, _, _ = pa
            _, yb, _, hb = _geom_patch(self.blocs[i_bot])
            return yb + hb

        paires_triees = sorted(paires_contact, key=_y_interface)

        for i_bas, i_haut, fraction in paires_triees:
            xb, yb, wb, hb = _geom_patch(self.blocs[i_bas])
            xt, yt, wt, ht = _geom_patch(self.blocs[i_haut])
            y_interface = yb + hb

            x_gauche = max(xb, xt)
            x_droite = min(xb + wb, xt + wt)
            if x_droite <= x_gauche:
                continue

            if i_haut >= len(donnees_stress) or donnees_stress[i_haut] is None:
                continue

            lc = x_droite - x_gauche
            f_contact = donnees_stress[i_haut]["F_axial"]
            ratio_ct = ratio_effort_contact_visuel(f_contact, lc, hb, ht)

            shade_d = min(0.08, hb * 0.38, ht * 0.38)
            y_bot0 = max(yb, y_interface - shade_d)
            h_bot = y_interface - y_bot0
            if h_bot > 1e-4:
                sb = Rectangle(
                    (x_gauche, y_bot0),
                    lc,
                    h_bot,
                    facecolor="#000000",
                    edgecolor="none",
                    alpha=min(0.72, 0.24 + 0.48 * ratio_ct),
                    zorder=9,
                )
                self.axes.add_patch(sb)
                self._patches_stress.append(sb)
            y_top1 = min(yt + ht, y_interface + shade_d)
            h_top = y_top1 - y_interface
            if h_top > 1e-4:
                st = Rectangle(
                    (x_gauche, y_interface),
                    lc,
                    h_top,
                    facecolor="#000000",
                    edgecolor="none",
                    alpha=min(0.72, 0.24 + 0.48 * ratio_ct),
                    zorder=9,
                )
                self.axes.add_patch(st)
                self._patches_stress.append(st)

            face_joint = melanger_hex("#1a1a1a", "#c62828", ratio_ct * 0.65)
            cr = Rectangle(
                (x_gauche, y_interface - 0.05),
                lc,
                0.10,
                facecolor=face_joint,
                edgecolor="none",
                alpha=min(0.96, 0.76 + 0.22 * ratio_ct),
                zorder=12,
            )
            self.axes.add_patch(cr)
            self._patches_stress.append(cr)

            cx = (x_gauche + x_droite) / 2

            pad_x, pad_y = 0.04, 0.05
            self._zones_contact_clic.append(
                {
                    "x0": x_gauche - pad_x,
                    "x1": x_droite + pad_x,
                    "y0": y_interface - 0.05 - pad_y,
                    "y1": y_interface + 0.05 + pad_y,
                    "i_bot": i_bas,
                    "i_top": i_haut,
                    "frac": fraction,
                    "F_c": f_contact,
                    "cx": cx,
                    "y_if": y_interface,
                }
            )

            fleche_bas = FancyArrowPatch(
                (cx - 0.12, y_interface + 0.55),
                (cx - 0.12, y_interface + 0.06),
                arrowstyle="-|>",
                mutation_scale=18,
                color="#d32f2f",
                linewidth=2.5,
                zorder=13,
            )
            self.axes.add_patch(fleche_bas)
            self._artistes_fleches.append(fleche_bas)

            fleche_haut = FancyArrowPatch(
                (cx + 0.12, y_interface - 0.55),
                (cx + 0.12, y_interface - 0.06),
                arrowstyle="-|>",
                mutation_scale=18,
                color="#1565c0",
                linewidth=2.5,
                zorder=13,
            )
            self.axes.add_patch(fleche_haut)
            self._artistes_fleches.append(fleche_haut)

            lbl_contact = self.axes.text(
                cx + 0.3,
                y_interface,
                f"Fc = {f_contact:.0f} N\n({fraction*100:.0f}% recouvrement)",
                ha="left",
                va="center",
                fontsize=7,
                color="#bf360c",
                fontweight="bold",
                zorder=14,
                bbox=dict(
                    boxstyle="round,pad=0.25",
                    facecolor="#fff3e0",
                    alpha=0.92,
                    edgecolor="#ff6f00",
                ),
            )
            self._artistes_fleches.append(lbl_contact)

        if self.carte_chaleur:
            if heatmap_any:
                sm = ScalarMappable(norm=norm_hm, cmap=carte_couleurs_hm)
                sm.set_array([])
                if self._colorbar_heatmap is None:
                    self.figure.subplots_adjust(
                        left=0.08, bottom=0.08, right=0.92, top=0.99
                    )
                    cb = self.figure.colorbar(
                        sm, ax=self.axes, fraction=0.046, pad=0.02
                    )
                    cb.set_label("|σ_normale| + charge répartie (Pa)")
                    self._colorbar_heatmap = cb
                else:
                    self._colorbar_heatmap.update_normal(sm)
            else:
                self._retirer_colorbar_heatmap()

        self._appliquer_styles_polygones_blocs()
        self._verrouiller_vue()
        self.draw_idle()
