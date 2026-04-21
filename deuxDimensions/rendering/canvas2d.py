"""Canvas matplotlib 2D et rendu des contraintes."""

from __future__ import annotations

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, Rectangle
from PySide6.QtCore import QPoint, QRect, QTimer

from deuxDimensions.domain.constantes import (
    AXIS_XLIM,
    AXIS_YLIM,
    FALL_STEP,
    GROUND_Y,
    HEATMAP_CELLES_MAX,
    MATERIAUX,
    SNAP_TOL,
    TIMER_MS,
)
from deuxDimensions.physics.calculs import _geom_patch, _hauteur_appui_max, _resoudre_collision


def _blue_plasma_cmap():
    """Colormap type "plasma" tronquee sur les bleus."""
    base = cm.get_cmap("plasma", 256)
    return mcolors.ListedColormap(base(np.linspace(0.0, 0.52, 256)))


def _pressure_grid_pa(p_pa, nx, ny):
    """
    Matrice (ny, nx) des pressions par cellule (Pa), meme logique que le dessin.
    Ligne 0 = bas du bloc, colonne 0 = gauche.
    """
    ix = np.linspace(0.5 / nx, 1.0 - 0.5 / nx, nx, dtype=np.float64)
    iy = np.linspace(0.5 / ny, 1.0 - 0.5 / ny, ny, dtype=np.float64)
    u, v = np.meshgrid(ix, iy, indexing="xy")
    facteur_cellule = 0.5 + 0.5 * (u * v)
    return np.where(p_pa > 0, p_pa * facteur_cellule, 0.0)


def _pressure_grid_rgba_from_pa(pa, norme_pression, cmap_p):
    """Image (ny, nx, 4) RGBA a partir d'une matrice pression (Pa)."""
    return cmap_p(norme_pression(pa))


def _vider_serie_artists(serie):
    """Retire chaque artiste matplotlib de l'axe puis vide la liste."""
    for artiste in list(serie):
        try:
            artiste.remove()
        except Exception:
            pass
    serie.clear()


class Canvas2D(FigureCanvasQTAgg):
    """
    Fenetre matplotlib embarquee dans Qt.
    Gere l'affichage des blocs, le drag & drop, la gravite,
    et le rendu visuel des contraintes.
    """

    def __init__(self, parent=None, on_blocs_changes=None):
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
        self.gravite_active = False
        self.carte_chaleur = False

        self._patches_stress = []
        self._artistes_fleches = []
        self._patch_sol = None
        self._ligne_sol = None
        self._zones_contact_clic = []
        self._images_chaleur = []
        self._callback_contact = None

        self._timer_physique = QTimer()
        self._timer_physique.setInterval(TIMER_MS)
        self._timer_physique.timeout.connect(self._tick_physique)

        self._dessiner_sol()

        self.mpl_connect("button_press_event", self._souris_appui)
        self.mpl_connect("motion_notify_event", self._souris_mouvement)
        self.mpl_connect("button_release_event", self._souris_relache)

    # ── Sol ──────────────────────────────────────────────────

    def _dessiner_sol(self):
        """Dessine la bande verte hachuree representant le sol encastre."""
        xmin, xmax = self.axes.get_xlim()

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
        """Active ou non la carte de pression (visuel) sur les blocs."""
        self.carte_chaleur = bool(active)

    def matrice_heatmap_bloc(self, index):
        """Retourne (matrice Pa, (nx, ny)) pour export ou scripts, ou (None, None)."""
        if not (0 <= index < len(self.blocs)):
            return None, None
        rd = self.blocs[index]
        return rd.get("heatmap_matrice"), rd.get("heatmap_cellules")

    def set_callback_contact_clic(self, callback):
        """Callback appele quand l'utilisateur clique une zone de contact."""
        self._callback_contact = callback

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
        ordre = sorted(range(len(self.blocs)), key=lambda i: self.blocs[i]["patch"].get_xy()[1])

        for idx in ordre:
            if idx == self._idx_drag:
                continue

            patch = self.blocs[idx]["patch"]
            x, y = patch.get_xy()
            plancher = _hauteur_appui_max(self.blocs, idx)

            if y > plancher + 0.001:
                nouvelle_y = max(plancher, y - FALL_STEP)
                patch.set_xy((x, nouvelle_y))
                a_bouge = True

        if a_bouge:
            self.draw_idle()
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
                sommets = [b["patch"].get_xy()[1] + b["patch"].get_height() for b in self.blocs]
                y_depart = max(sommets)
            x_depart = 0.5

        patch = Rectangle(
            (x_depart, y_depart),
            largeur,
            hauteur,
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
                "material": materiau,
                "density": densite,
                "h0": hauteur, 
                "edgecolor": ec,
                "ext_force": 0.0,
                "moment": 0.0,
                "pressure": 0.0,
                "heatmap_matrice": None,
                "heatmap_cellules": None,
            }
        )
        self._notifier()

    def supprimer_bloc(self, index):
        """Supprime le bloc a l'index donne du canvas et de la liste."""
        if 0 <= index < len(self.blocs):
            self.blocs[index]["patch"].remove()
            self.blocs.pop(index)
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
        for i, bloc in enumerate(reversed(self.blocs)):
            idx = len(self.blocs) - 1 - i
            xy = bloc["patch"].get_xy()
            w, h = bloc["patch"].get_width(), bloc["patch"].get_height()

            dans_le_bloc = (
                event.xdata is not None
                and event.ydata is not None
                and xy[0] <= event.xdata <= xy[0] + w
                and xy[1] <= event.ydata <= xy[1] + h
            )
            if dans_le_bloc:
                return idx
        return None

    def _souris_appui(self, event):
        if event.inaxes != self.axes or event.button != 1:
            return
        hit_c = self._tester_clic_contact(event)
        if hit_c is not None and self._callback_contact:
            pg = self._souris_vers_global(event)
            if pg is not None:
                hit_c["_press_global"] = pg
            self._callback_contact(hit_c)
            return
        idx = self._tester_clic(event)
        if idx is not None:
            self._idx_drag = idx
            xy = self.blocs[idx]["patch"].get_xy()
            self._offset_drag = (event.xdata - xy[0], event.ydata - xy[1])

    def _souris_mouvement(self, event):
        if self._idx_drag is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return

        patch = self.blocs[self._idx_drag]["patch"]
        xmin, xmax = self.axes.get_xlim()
        _, ymax = self.axes.get_ylim()
        w, h = patch.get_width(), patch.get_height()

        x = max(xmin, min(xmax - w, event.xdata - self._offset_drag[0]))
        y = max(GROUND_Y, min(ymax - h, event.ydata - self._offset_drag[1]))
        patch.set_xy((x, y))

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

    # ── Rendu visuel des contraintes ─────────────────────────

    def dessiner_contraintes(self, donnees_stress, paires_contact):
        """
        Couche contraintes : carte de pression (Pa) ou barres RdYlGn selon sigma.
        Joints cliquables, effort affiche.
        """
        # Configuration de l'animation
        VISUAL_SCALE = 5000.0 
        _vider_serie_artists(self._images_chaleur)

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

        self._zones_contact_clic.clear()

        if not self.blocs or not donnees_stress:
            for bloc in self.blocs:
                bloc["heatmap_matrice"] = None
                bloc["heatmap_cellules"] = None
            self._verrouiller_vue()
            self.draw_idle()
            return

        for bloc in self.blocs:
            bloc["heatmap_matrice"] = None
            bloc["heatmap_cellules"] = None

        p_list = [float(b["pressure"]) for b in self.blocs]
        p_max = max(p_list) if p_list else 0.0
        if self.carte_chaleur:
            norme_pression = mcolors.Normalize(vmin=0.0, vmax=max(p_max, 1.0))
            carte_couleurs = _blue_plasma_cmap()
        else:
            norme_pression = None
            carte_couleurs = None
            toutes_sigmas = [abs(d["sigma_total"]) for d in donnees_stress if d]
            sigma_max_global = max(toutes_sigmas) if any(s > 0 for s in toutes_sigmas) else 1.0
            colormap = cm.get_cmap("RdYlGn_r")
            normaliseur = mcolors.Normalize(vmin=0, vmax=sigma_max_global)

        for bloc, stress in zip(self.blocs, donnees_stress):
            if stress is None:
                continue

            h0 = bloc["h0"]
            dh = stress.get("delta_h", 0.0)

            nouveau_h = max(0.01, h0 - (dh*VISUAL_SCALE))
            bloc["patch"].set_height(nouveau_h)

            x, y, w, h = _geom_patch(bloc)

            if self.carte_chaleur and norme_pression is not None:
                p_pa = float(bloc["pressure"])
                nx = max(2, min(HEATMAP_CELLES_MAX, int(w * 10)))
                ny = max(2, min(HEATMAP_CELLES_MAX, int(h * 10)))
                pa = _pressure_grid_pa(p_pa, nx, ny)
                bloc["heatmap_matrice"] = pa
                bloc["heatmap_cellules"] = (nx, ny)
                rgba = _pressure_grid_rgba_from_pa(pa, norme_pression, carte_couleurs)
                im = self.axes.imshow(
                    rgba,
                    extent=(x, x + w, y, y + h),
                    origin="lower",
                    aspect="auto",
                    interpolation="nearest",
                    zorder=6,
                    clip_on=True,
                )
                im.set_alpha(0.93)
                self._images_chaleur.append(im)
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

            ec = bloc.get("edgecolor") or MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])[
                "edge"
            ]
            contour = Rectangle(
                (x, y),
                w,
                h,
                facecolor="none",
                edgecolor=ec,
                linewidth=1.5,
                zorder=7,
            )
            self.axes.add_patch(contour)
            self._patches_stress.append(contour)

            if abs(y - GROUND_Y) < SNAP_TOL * 2.0:
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

            if not self.carte_chaleur:
                util = stress["utilization"]
                symbole = "✓" if util < 80 else ("!" if util < 100 else "✗")
                label = self.axes.text(
                    x + w / 2,
                    y + h / 2,
                    f"σ = {stress['sigma_total']/1e6:.2f} MPa\n{util:.0f}% {symbole}",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color="black",
                    fontweight="bold",
                    zorder=10,
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor="white",
                        alpha=0.65,
                        edgecolor="none",
                    ),
                )
                self._patches_stress.append(label)

            if abs(stress.get("ext_force", 0)) > 0:
                cx = x + w / 2
                fleche = FancyArrowPatch(
                    (cx, y + h + 0.7),
                    (cx, y + h + 0.05),
                    arrowstyle="-|>",
                    mutation_scale=16,
                    color="#d32f2f",
                    linewidth=2.5,
                    zorder=11,
                )
                self.axes.add_patch(fleche)
                self._artistes_fleches.append(fleche)
                lbl_force = self.axes.text(
                    cx,
                    y + h + 0.8,
                    f"F = {stress['ext_force']:.0f} N",
                    ha="center",
                    va="bottom",
                    fontsize=7.5,
                    color="#d32f2f",
                    fontweight="bold",
                    zorder=11,
                )
                self._artistes_fleches.append(lbl_force)

            if abs(stress.get("pressure", 0)) > 0:
                nb_fleches = max(3, int(w * 2))
                for k in range(nb_fleches):
                    x_fleche = x + (k + 0.5) * w / nb_fleches
                    f = FancyArrowPatch(
                        (x_fleche, y + h + 0.35),
                        (x_fleche, y + h + 0.02),
                        arrowstyle="-|>",
                        mutation_scale=9,
                        color="#e65100",
                        linewidth=1.2,
                        zorder=11,
                    )
                    self.axes.add_patch(f)
                    self._artistes_fleches.append(f)

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

            shade_d = min(0.08, hb * 0.38, ht * 0.38)
            y_bot0 = max(yb, y_interface - shade_d)
            h_bot = y_interface - y_bot0
            if h_bot > 1e-4:
                sb = Rectangle(
                    (x_gauche, y_bot0),
                    x_droite - x_gauche,
                    h_bot,
                    facecolor="#000000",
                    edgecolor="none",
                    alpha=0.36,
                    zorder=9,
                )
                self.axes.add_patch(sb)
                self._patches_stress.append(sb)
            y_top1 = min(yt + ht, y_interface + shade_d)
            h_top = y_top1 - y_interface
            if h_top > 1e-4:
                st = Rectangle(
                    (x_gauche, y_interface),
                    x_droite - x_gauche,
                    h_top,
                    facecolor="#000000",
                    edgecolor="none",
                    alpha=0.36,
                    zorder=9,
                )
                self.axes.add_patch(st)
                self._patches_stress.append(st)

            cr = Rectangle(
                (x_gauche, y_interface - 0.05),
                x_droite - x_gauche,
                0.10,
                facecolor="#1a1a1a",
                edgecolor="none",
                alpha=0.88,
                zorder=12,
            )
            self.axes.add_patch(cr)
            self._patches_stress.append(cr)

            f_contact = donnees_stress[i_haut]["F_axial"]
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

        self._verrouiller_vue()
        self.draw_idle()
