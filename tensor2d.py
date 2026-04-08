"""
tensor2D.py  —  Tensor Build
Simulateur 2D de résistance des matériaux.

On peut ajouter des blocs rectangulaires, les déplacer,
leur appliquer des forces, et voir les contraintes en temps réel.
"""

import sys
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyArrowPatch
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QDoubleSpinBox, QPushButton, QListWidget, QLabel,
    QFormLayout, QGroupBox, QFrame, QScrollArea, QTabWidget, QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, QTimer


# ──────────────────────────────────────────────────────────────
#  Constantes globales
# ──────────────────────────────────────────────────────────────

GRAVITY   = 9.81   # accélération gravitationnelle (m/s²)
GROUND_Y  = 0.0    # position y du sol sur le canvas
SNAP_TOL  = 0.18   # distance max pour considérer deux blocs en contact (m)
FALL_STEP = 0.12   # distance de chute par tick de physique (m)
TIMER_MS  = 30     # intervalle du timer de physique (ms) — ~33 fps


# ──────────────────────────────────────────────────────────────
#  Fonctions utilitaires de physique
# ──────────────────────────────────────────────────────────────

def _overlaps_x(bloc_a, bloc_b):
    """
    Vérifie si deux blocs se chevauchent horizontalement.
    Utilisé pour savoir si un contact vertical est possible.
    """
    xa, _ = bloc_a["patch"].get_xy()
    wa    = bloc_a["patch"].get_width()
    xb, _ = bloc_b["patch"].get_xy()
    wb    = bloc_b["patch"].get_width()
    return xa < xb + wb and xb < xa + wa


def _contact_pairs(blocs, tol=SNAP_TOL):
    """
    Parcourt tous les blocs et retourne les paires en contact vertical.
    Une paire (i_bas, i_haut, fraction) signifie que le bloc i_haut
    repose sur le bloc i_bas, avec une fraction de surface en commun.
    """
    paires = []
    for i in range(len(blocs)):
        for j in range(len(blocs)):
            if i == j:
                continue

            xi, yi = blocs[i]["patch"].get_xy()
            wi, hi = blocs[i]["patch"].get_width(), blocs[i]["patch"].get_height()
            xj, yj = blocs[j]["patch"].get_xy()
            wj     = blocs[j]["patch"].get_width()

            # Le dessus du bloc i est-il proche du dessous du bloc j ?
            contact_vertical = abs((yi + hi) - yj) <= tol
            if contact_vertical and _overlaps_x(blocs[i], blocs[j]):
                largeur_contact = min(xi + wi, xj + wj) - max(xi, xj)
                fraction        = largeur_contact / min(wi, wj)
                paires.append((i, j, fraction))

    return paires


def _resoudre_collision(idx_mobile, blocs):
    """
    Quand un bloc en est glissé dans un autre, cette fonction
    le repousse vers la sortie la plus proche (axe de moindre pénétration).
    C'est ce qui empêche les blocs de se traverser pendant le drag.
    """
    patch_mobile    = blocs[idx_mobile]["patch"]
    mx, my          = patch_mobile.get_xy()
    largeur, hauteur = patch_mobile.get_width(), patch_mobile.get_height()
    collision       = False

    for i, autre_bloc in enumerate(blocs):
        if i == idx_mobile:
            continue

        patch_autre     = autre_bloc["patch"]
        ox, oy          = patch_autre.get_xy()
        ow, oh          = patch_autre.get_width(), patch_autre.get_height()

        # Test de chevauchement AABB (boîte englobante)
        chevauche_x = mx < ox + ow and ox < mx + largeur
        chevauche_y = my < oy + oh and oy < my + hauteur

        if chevauche_x and chevauche_y:
            # Calcule la profondeur de pénétration sur chaque côté
            penet_haut   = (oy + oh) - my      # bloc monte sur l'autre
            penet_bas    = (my + hauteur) - oy  # bloc descend sous l'autre
            penet_droite = (ox + ow) - mx
            penet_gauche = (mx + largeur) - ox

            # On choisit la sortie la moins coûteuse
            min_penet = min(penet_haut, penet_bas, penet_droite, penet_gauche)

            if min_penet == penet_haut:
                patch_mobile.set_xy((mx, oy + oh))      # pose par-dessus
            elif min_penet == penet_bas:
                patch_mobile.set_xy((mx, oy - hauteur)) # glisse en dessous
            elif min_penet == penet_droite:
                patch_mobile.set_xy((ox + ow, my))      # pousse à droite
            else:
                patch_mobile.set_xy((ox - largeur, my)) # pousse à gauche

            # Relit la position après correction (peut avoir changé)
            mx, my = patch_mobile.get_xy()
            collision = True

    return collision


# ──────────────────────────────────────────────────────────────
#  Canvas 2D  —  zone de dessin principale
# ──────────────────────────────────────────────────────────────

class Canvas2D(FigureCanvasQTAgg):
    """
    Fenêtre matplotlib embarquée dans Qt.
    Gère l'affichage des blocs, le drag & drop, la gravité,
    et le rendu visuel des contraintes.
    """

    def __init__(self, parent=None, on_blocs_changes=None):
        # Création de la figure matplotlib avec fond blanc
        fig = Figure(figsize=(12, 12), facecolor="white")
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

        self.axes = fig.add_subplot(111)
        self.axes.set_aspect("equal")
        self.axes.set_facecolor("white")
        self.axes.grid(True, color="#dddddd", linewidth=0.6, linestyle="--")
        self.axes.set_xlim(-2, 12)
        self.axes.set_ylim(-1.5, 12)
        self.axes.set_xticks(range(-2, 13))
        self.axes.set_yticks(range(-1, 13))
        self.axes.tick_params(colors="#aaaaaa", labelsize=7)
        for bordure in self.axes.spines.values():
            bordure.set_edgecolor("#cccccc")

        super().__init__(fig)

        # État interne
        self.blocs              = []      # liste de dicts {patch, material, density, ...}
        self._idx_drag          = None    # index du bloc en cours de drag
        self._offset_drag       = None    # décalage souris/coin du bloc
        self._on_blocs_changes  = on_blocs_changes
        self.gravite_active     = False

        # Artistes matplotlib à nettoyer à chaque redraw
        self._patches_stress    = []
        self._artistes_fleches  = []
        self._artiste_cg        = None
        self._patch_sol         = None
        self._ligne_sol         = None

        # Timer pour la simulation de chute (gravité)
        self._timer_physique = QTimer()
        self._timer_physique.setInterval(TIMER_MS)
        self._timer_physique.timeout.connect(self._tick_physique)

        self._dessiner_sol()

        # Connexion des événements souris matplotlib
        self.mpl_connect("button_press_event",   self._souris_appui)
        self.mpl_connect("motion_notify_event",  self._souris_mouvement)
        self.mpl_connect("button_release_event", self._souris_relache)

    # ── Sol ──────────────────────────────────────────────────

    def _dessiner_sol(self):
        """Dessine la bande verte hachurée représentant le sol encastré."""
        xmin, xmax = self.axes.get_xlim()

        if self._patch_sol:
            self._patch_sol.remove()
        if self._ligne_sol:
            self._ligne_sol.remove()

        self._patch_sol = Rectangle(
            (xmin, GROUND_Y - 0.5), xmax - xmin, 0.5,
            facecolor="#e8f5e9", edgecolor="#388e3c",
            linewidth=2, hatch="////", zorder=0
        )
        self.axes.add_patch(self._patch_sol)

        # Ligne épaisse marquant la surface du sol
        self._ligne_sol, = self.axes.plot(
            [xmin, xmax], [GROUND_Y, GROUND_Y],
            color="#388e3c", linewidth=2.5, zorder=1
        )

    # ── Gravité ──────────────────────────────────────────────

    def activer_gravite(self, active):
        """Active ou désactive la simulation de chute libre."""
        self.gravite_active = active
        if active:
            self._timer_physique.start()
        else:
            self._timer_physique.stop()

    def _tick_physique(self):
        """
        Appelé ~33 fois par seconde quand la gravité est active.
        Fait descendre chaque bloc vers son plancher naturel
        (sol ou dessus du bloc le plus proche en dessous).
        """
        if not self.blocs:
            return

        a_bouge = False

        # On traite les blocs du bas vers le haut pour éviter les conflits
        ordre = sorted(
            range(len(self.blocs)),
            key=lambda i: self.blocs[i]["patch"].get_xy()[1]
        )

        for idx in ordre:
            if idx == self._idx_drag:
                continue  # le bloc qu'on tient en main ne tombe pas

            patch = self.blocs[idx]["patch"]
            x, y  = patch.get_xy()

            # Cherche le plancher effectif : sol ou sommet d'un bloc en dessous
            plancher = GROUND_Y
            for i2, autre in enumerate(self.blocs):
                if i2 == idx:
                    continue
                x2, y2 = autre["patch"].get_xy()
                w2, h2 = autre["patch"].get_width(), autre["patch"].get_height()
                x_moi  = patch.get_xy()[0]
                w_moi  = patch.get_width()

                # Ne compte que les blocs qui chevauchent horizontalement
                if x_moi < x2 + w2 and x2 < x_moi + w_moi:
                    sommet_autre = y2 + h2
                    if sommet_autre <= y + 0.001:  # l'autre est bien en dessous
                        plancher = max(plancher, sommet_autre)

            # Si le bloc est encore au-dessus de son plancher, il descend
            if y > plancher + 0.001:
                nouvelle_y = max(plancher, y - FALL_STEP)
                patch.set_xy((x, nouvelle_y))
                a_bouge = True

        if a_bouge:
            self.draw_idle()
            self._notifier()

    # ── Gestion des blocs ────────────────────────────────────

    def ajouter_bloc(self, largeur, hauteur, materiau="Acier", densite=7850):
        """
        Crée un nouveau bloc rectangulaire et l'ajoute au canvas.
        Si la gravité est active, il apparaît en haut et tombe.
        Sinon, il se pose directement au-dessus de la pile.
        """
        if self.gravite_active:
            y_depart = 9.0
            x_depart = 1.0
        else:
            y_depart = GROUND_Y
            if self.blocs:
                sommets  = [b["patch"].get_xy()[1] + b["patch"].get_height() for b in self.blocs]
                y_depart = max(sommets)
            x_depart = 0.5

        patch = Rectangle(
            (x_depart, y_depart), largeur, hauteur,
            facecolor="#bbdefb", edgecolor="#1565c0",
            linewidth=1.8, zorder=5, alpha=0.9
        )
        self.axes.add_patch(patch)

        self.blocs.append({
            "patch":      patch,
            "material":   materiau,
            "density":    densite,
            "ext_force":  0.0,   # force ponctuelle appliquée (N)
            "moment":     0.0,   # moment fléchissant (N·m)
            "pressure":   0.0,   # pression distribuée (Pa)
        })
        self._notifier()

    def supprimer_bloc(self, index):
        """Supprime le bloc à l'index donné du canvas et de la liste."""
        if 0 <= index < len(self.blocs):
            self.blocs[index]["patch"].remove()
            self.blocs.pop(index)
            self._notifier()

    # ── Drag & drop ──────────────────────────────────────────

    def _tester_clic(self, event):
        """
        Retourne l'index du bloc cliqué, en partant du dessus (dernier ajouté).
        Retourne None si le clic est dans le vide.
        """
        for i, bloc in enumerate(reversed(self.blocs)):
            idx  = len(self.blocs) - 1 - i
            xy   = bloc["patch"].get_xy()
            w, h = bloc["patch"].get_width(), bloc["patch"].get_height()

            dans_le_bloc = (
                event.xdata is not None and event.ydata is not None and
                xy[0] <= event.xdata <= xy[0] + w and
                xy[1] <= event.ydata <= xy[1] + h
            )
            if dans_le_bloc:
                return idx
        return None

    def _souris_appui(self, event):
        if event.inaxes != self.axes or event.button != 1:
            return
        idx = self._tester_clic(event)
        if idx is not None:
            self._idx_drag    = idx
            xy                = self.blocs[idx]["patch"].get_xy()
            # On mémorise où dans le bloc on a cliqué pour un drag naturel
            self._offset_drag = (event.xdata - xy[0], event.ydata - xy[1])

    def _souris_mouvement(self, event):
        if self._idx_drag is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return

        patch    = self.blocs[self._idx_drag]["patch"]
        xmin, xmax = self.axes.get_xlim()
        _, ymax    = self.axes.get_ylim()
        w, h       = patch.get_width(), patch.get_height()

        # Limite le déplacement aux bords du canvas
        x = max(xmin,     min(xmax - w, event.xdata - self._offset_drag[0]))
        y = max(GROUND_Y, min(ymax - h, event.ydata - self._offset_drag[1]))
        patch.set_xy((x, y))

        # Empêche la traversée d'autres blocs en temps réel
        _resoudre_collision(self._idx_drag, self.blocs)

        self.draw_idle()
        self._notifier()

    def _souris_relache(self, event):
        self._idx_drag    = None
        self._offset_drag = None

    def _notifier(self):
        """Informe l'application principale qu'un bloc a bougé ou changé."""
        if self._on_blocs_changes:
            self._on_blocs_changes()

    # ── Rendu visuel des contraintes ─────────────────────────

    def dessiner_contraintes(self, donnees_stress, paires_contact):
        """
        Redessine toute la couche de visualisation physique :
        - heatmap colorée sur chaque bloc (vert = OK, rouge = danger)
        - flèches de forces et de pression
        - flèches d'interaction aux interfaces de contact
        - centre de gravité global (boule jaune)
        """
        # Nettoyage de l'ancien rendu
        for p in self._patches_stress:
            try: p.remove()
            except Exception: pass
        self._patches_stress.clear()

        for a in self._artistes_fleches:
            try: a.remove()
            except Exception: pass
        self._artistes_fleches.clear()

        if self._artiste_cg:
            for a in self._artiste_cg:
                try: a.remove()
                except Exception: pass
            self._artiste_cg = None

        if not self.blocs or not donnees_stress:
            self.draw_idle()
            return

        # Normalisation de la colormap sur la contrainte max observée
        toutes_sigmas    = [abs(d["sigma_total"]) for d in donnees_stress if d]
        sigma_max_global = max(toutes_sigmas) if any(s > 0 for s in toutes_sigmas) else 1.0
        colormap         = cm.get_cmap("RdYlGn_r")
        normaliseur      = mcolors.Normalize(vmin=0, vmax=sigma_max_global)

        # ── Dessin de chaque bloc ──
        for bloc, stress in zip(self.blocs, donnees_stress):
            if stress is None:
                continue

            patch    = bloc["patch"]
            x, y     = patch.get_xy()
            w, h     = patch.get_width(), patch.get_height()

            # Si flexion active : dégradé haut/bas (fibre tendue vs comprimée)
            if abs(stress.get("sigma_bending_top", 0)) > 1:
                for decalage, sigma in [(0, stress["sigma_bending_bot"]),
                                        (h/2, stress["sigma_bending_top"])]:
                    couleur = colormap(normaliseur(abs(sigma)))
                    rect    = Rectangle((x, y + decalage), w, h/2,
                                        facecolor=couleur, edgecolor="none",
                                        alpha=0.55, zorder=6)
                    self.axes.add_patch(rect)
                    self._patches_stress.append(rect)
            else:
                # Couleur uniforme selon la contrainte totale
                couleur = colormap(normaliseur(abs(stress["sigma_total"])))
                rect    = Rectangle((x, y), w, h,
                                    facecolor=couleur, edgecolor="none",
                                    alpha=0.55, zorder=6)
                self.axes.add_patch(rect)
                self._patches_stress.append(rect)

            # Contour du bloc
            contour = Rectangle((x, y), w, h,
                                 facecolor="none", edgecolor="#1565c0",
                                 linewidth=1.5, zorder=7)
            self.axes.add_patch(contour)
            self._patches_stress.append(contour)

            # Étiquette : valeur de σ et taux d'utilisation
            util    = stress["utilization"]
            symbole = "✓" if util < 80 else ("!" if util < 100 else "✗")
            label   = self.axes.text(
                x + w/2, y + h/2,
                f"σ = {stress['sigma_total']/1e6:.2f} MPa\n{util:.0f}% {symbole}",
                ha="center", va="center", fontsize=7.5,
                color="black", fontweight="bold", zorder=10,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          alpha=0.65, edgecolor="none")
            )
            self._patches_stress.append(label)

            # Flèche pour force ponctuelle
            if abs(stress.get("ext_force", 0)) > 0:
                cx     = x + w/2
                fleche = FancyArrowPatch(
                    (cx, y + h + 0.7), (cx, y + h + 0.05),
                    arrowstyle="-|>", mutation_scale=16,
                    color="#d32f2f", linewidth=2.5, zorder=11
                )
                self.axes.add_patch(fleche)
                self._artistes_fleches.append(fleche)

                lbl_force = self.axes.text(
                    cx, y + h + 0.8, f"F = {stress['ext_force']:.0f} N",
                    ha="center", va="bottom", fontsize=7.5,
                    color="#d32f2f", fontweight="bold", zorder=11
                )
                self._artistes_fleches.append(lbl_force)

            # Petites flèches pour pression distribuée
            if abs(stress.get("pressure", 0)) > 0:
                nb_fleches = max(3, int(w * 2))
                for k in range(nb_fleches):
                    x_fleche = x + (k + 0.5) * w / nb_fleches
                    f = FancyArrowPatch(
                        (x_fleche, y + h + 0.35), (x_fleche, y + h + 0.02),
                        arrowstyle="-|>", mutation_scale=9,
                        color="#e65100", linewidth=1.2, zorder=11
                    )
                    self.axes.add_patch(f)
                    self._artistes_fleches.append(f)

        # ── Interactions de contact entre blocs ──
        for (i_bas, i_haut, fraction) in paires_contact:
            bloc_bas  = self.blocs[i_bas]
            bloc_haut = self.blocs[i_haut]

            xb, yb = bloc_bas["patch"].get_xy()
            wb, hb = bloc_bas["patch"].get_width(), bloc_bas["patch"].get_height()
            xh, _  = bloc_haut["patch"].get_xy()
            wh     = bloc_haut["patch"].get_width()

            y_interface = yb + hb  # la ligne de contact

            # Zone de contact surlignée en orange
            x_gauche = max(xb, xh)
            x_droite = min(xb + wb, xh + wh)
            zone_contact = Rectangle(
                (x_gauche, y_interface - 0.05), x_droite - x_gauche, 0.10,
                facecolor="#ff6f00", edgecolor="none", alpha=0.9, zorder=12
            )
            self.axes.add_patch(zone_contact)
            self._patches_stress.append(zone_contact)

            # Force transmise à l'interface
            F_contact = donnees_stress[i_haut]["F_axial"]
            cx        = (x_gauche + x_droite) / 2

            # Flèche rouge ↓ : le bloc du haut comprime le bas
            fleche_bas = FancyArrowPatch(
                (cx - 0.12, y_interface + 0.55), (cx - 0.12, y_interface + 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#d32f2f", linewidth=2.5, zorder=13
            )
            self.axes.add_patch(fleche_bas)
            self._artistes_fleches.append(fleche_bas)

            # Flèche bleue ↑ : réaction du bas (3e loi de Newton)
            fleche_haut = FancyArrowPatch(
                (cx + 0.12, y_interface - 0.55), (cx + 0.12, y_interface - 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#1565c0", linewidth=2.5, zorder=13
            )
            self.axes.add_patch(fleche_haut)
            self._artistes_fleches.append(fleche_haut)

            # Étiquette de la force de contact
            lbl_contact = self.axes.text(
                cx + 0.3, y_interface,
                f"Fc = {F_contact:.0f} N\n({fraction*100:.0f}% contact)",
                ha="left", va="center", fontsize=7,
                color="#bf360c", fontweight="bold", zorder=14,
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="#fff3e0", alpha=0.92, edgecolor="#ff6f00")
            )
            self._artistes_fleches.append(lbl_contact)

            # Surlignes orange sur les deux blocs impliqués
            for b in (bloc_bas, bloc_haut):
                px, py = b["patch"].get_xy()
                pw, ph = b["patch"].get_width(), b["patch"].get_height()
                surligne = Rectangle((px, py), pw, ph,
                                     facecolor="none", edgecolor="#ff6f00",
                                     linewidth=3, linestyle="--", zorder=8)
                self.axes.add_patch(surligne)
                self._patches_stress.append(surligne)

        # ── Centre de gravité (boule jaune) ──
        aire_totale = sum(b["patch"].get_width() * b["patch"].get_height() for b in self.blocs)
        if aire_totale > 0:
            xg = sum(
                (b["patch"].get_xy()[0] + b["patch"].get_width()/2) *
                b["patch"].get_width() * b["patch"].get_height()
                for b in self.blocs
            ) / aire_totale

            yg = sum(
                (b["patch"].get_xy()[1] + b["patch"].get_height()/2) *
                b["patch"].get_width() * b["patch"].get_height()
                for b in self.blocs
            ) / aire_totale

            # Axes d'inertie en pointillé jaune
            ligne_h = self.axes.axhline(yg, color="#f9a825", lw=0.9,
                                        ls="--", zorder=15, alpha=0.6)
            ligne_v = self.axes.axvline(xg, color="#f9a825", lw=0.9,
                                        ls="--", zorder=15, alpha=0.6)

            # Boule jaune au centre de gravité
            point_cg, = self.axes.plot(
                xg, yg, "o", color="#f9a825", markersize=13,
                zorder=16, markeredgecolor="#e65100", markeredgewidth=2
            )

            # Étiquette du centre de gravité
            texte_cg = self.axes.text(
                xg + 0.18, yg + 0.18,
                f"⊕ Centre de\n   Gravité\n   ({xg:.2f}, {yg:.2f})",
                color="#e65100", fontsize=7.5, fontweight="bold", zorder=17,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff9c4",
                          alpha=0.92, edgecolor="#f9a825")
            )
            self._artiste_cg = [point_cg, ligne_h, ligne_v, texte_cg]

        self.draw_idle()


# ──────────────────────────────────────────────────────────────
#  Panneau de contrôle  —  interface utilisateur droite
# ──────────────────────────────────────────────────────────────

class PanneauControle(QFrame):
    """
    Panneau latéral avec :
    - bouton switch vers le mode 3D
    - activation de la gravité
    - ajout/suppression de blocs
    - application de charges
    - affichage des résultats physiques
    """

    # Propriétés physiques des matériaux disponibles
    MATERIAUX = {
        "Acier":     {"density": 7850, "E": 210e9, "sigma_y": 250e6},
        "Béton":     {"density": 2400, "E":  30e9, "sigma_y":  30e6},
        "Aluminium": {"density": 2700, "E":  70e9, "sigma_y": 270e6},
        "Bois":      {"density":  600, "E":  12e9, "sigma_y":  40e6},
        "Fonte":     {"density": 7200, "E": 170e9, "sigma_y": 200e6},
    }

    def __init__(self, canvas, callback_physique, parent=None):
        super().__init__(parent)
        self.canvas            = canvas
        self.callback_physique = callback_physique
        self._bloc_selectionne = None
        self._construire_ui()

    def _construire_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Bouton pour basculer en mode 3D
        # Le signal clicked sera branché par MaterialSimulationApp
        self.btn_switch_3d = QPushButton("🧊  Passer en mode 3D")
        self.btn_switch_3d.setStyleSheet(
            "background-color: #ef6c00; color: white; font-size: 12px; padding: 8px;"
        )
        layout.addWidget(self.btn_switch_3d)

        # ── Gravité ──
        grp_gravite = QGroupBox("Simulation physique")
        lay_grav    = QVBoxLayout(grp_gravite)

        self.chk_gravite = QCheckBox("🌍  Activer la gravité")
        self.chk_gravite.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.chk_gravite.toggled.connect(self._toggle_gravite)
        lay_grav.addWidget(self.chk_gravite)

        info_gravite = QLabel(
            "Quand activée : les nouveaux blocs\n"
            "tombent et s'empilent sur les autres.\n"
            "Les blocs ne peuvent pas se traverser."
        )
        info_gravite.setStyleSheet("color: #555; font-size: 8px;")
        lay_grav.addWidget(info_gravite)

        grp_gravite.setLayout(lay_grav)
        layout.addWidget(grp_gravite)

        # ── Onglets Blocs / Charges ──
        onglets = QTabWidget()

        # Onglet "Blocs"
        tab_blocs = QWidget()
        lay_blocs = QVBoxLayout(tab_blocs)

        grp_nouveau = QGroupBox("Nouveau bloc")
        form_nouveau = QFormLayout()
        self.spin_largeur = QDoubleSpinBox()
        self.spin_largeur.setRange(0.1, 20); self.spin_largeur.setValue(2); self.spin_largeur.setSingleStep(0.25)
        self.spin_hauteur = QDoubleSpinBox()
        self.spin_hauteur.setRange(0.1, 20); self.spin_hauteur.setValue(1); self.spin_hauteur.setSingleStep(0.25)
        self.combo_materiau = QComboBox()
        for nom in self.MATERIAUX:
            self.combo_materiau.addItem(nom)
        form_nouveau.addRow("Largeur (m):", self.spin_largeur)
        form_nouveau.addRow("Hauteur (m):", self.spin_hauteur)
        form_nouveau.addRow("Matériau:",    self.combo_materiau)
        grp_nouveau.setLayout(form_nouveau)
        lay_blocs.addWidget(grp_nouveau)

        btn_ajouter = QPushButton("➕  Ajouter bloc")
        btn_ajouter.clicked.connect(self._ajouter_bloc)
        lay_blocs.addWidget(btn_ajouter)

        grp_liste = QGroupBox("Blocs présents")
        lay_liste = QVBoxLayout(grp_liste)
        self.liste_blocs = QListWidget()
        self.liste_blocs.setMaximumHeight(150)
        self.liste_blocs.currentRowChanged.connect(self._selectionner_bloc)
        lay_liste.addWidget(self.liste_blocs)
        btn_supprimer = QPushButton("🗑  Supprimer sélectionné")
        btn_supprimer.clicked.connect(self._supprimer_bloc)
        lay_liste.addWidget(btn_supprimer)
        grp_liste.setLayout(lay_liste)
        lay_blocs.addWidget(grp_liste)
        lay_blocs.addStretch()
        onglets.addTab(tab_blocs, "Blocs")

        # Onglet "Charges"
        tab_charges = QWidget()
        lay_charges = QVBoxLayout(tab_charges)
        grp_charges = QGroupBox("Charges — bloc sélectionné")
        form_charges = QFormLayout()

        self.spin_force    = QDoubleSpinBox()
        self.spin_force.setRange(0, 1e7); self.spin_force.setSuffix(" N"); self.spin_force.setSingleStep(100)
        self.spin_pression = QDoubleSpinBox()
        self.spin_pression.setRange(0, 1e6); self.spin_pression.setSuffix(" Pa"); self.spin_pression.setSingleStep(500)
        self.spin_moment   = QDoubleSpinBox()
        self.spin_moment.setRange(-1e6, 1e6); self.spin_moment.setSuffix(" N·m"); self.spin_moment.setSingleStep(100)

        form_charges.addRow("Force ponctuelle:",  self.spin_force)
        form_charges.addRow("Pression dist.:",    self.spin_pression)
        form_charges.addRow("Moment fléch.:",     self.spin_moment)
        grp_charges.setLayout(form_charges)
        lay_charges.addWidget(grp_charges)

        btn_appliquer = QPushButton("✅  Appliquer charges")
        btn_appliquer.clicked.connect(self._appliquer_charges)
        lay_charges.addWidget(btn_appliquer)
        lay_charges.addStretch()
        onglets.addTab(tab_charges, "Charges")

        layout.addWidget(onglets)

        # ── Résultats physiques ──
        grp_resultats = QGroupBox("Résultats physiques")
        lay_resultats = QVBoxLayout(grp_resultats)

        self.lbl_resultats = QLabel("—")
        self.lbl_resultats.setWordWrap(True)
        self.lbl_resultats.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_resultats.setStyleSheet("font-family: Consolas; font-size: 9px; color: #222;")

        zone_scroll = QScrollArea()
        zone_scroll.setWidget(self.lbl_resultats)
        zone_scroll.setWidgetResizable(True)
        zone_scroll.setMinimumHeight(240)
        lay_resultats.addWidget(zone_scroll)
        grp_resultats.setLayout(lay_resultats)
        layout.addWidget(grp_resultats)

        self.setStyleSheet("""
            QFrame        { background: #f5f5f5; }
            QGroupBox     { color: #1565c0; border: 1px solid #bbdefb; margin-top: 8px;
                            padding-top: 6px; border-radius: 4px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; }
            QLabel        { color: #333; }
            QDoubleSpinBox{ background: white; color: #222; border: 1px solid #90caf9;
                            border-radius: 3px; padding: 2px; }
            QPushButton   { background: #1565c0; color: white; border: none;
                            border-radius: 4px; padding: 7px; font-weight: bold; }
            QPushButton:hover { background: #1976d2; }
            QListWidget   { background: white; color: #222; border: 1px solid #bbdefb; }
            QComboBox     { background: white; color: #222; border: 1px solid #90caf9;
                            border-radius: 3px; padding: 2px; }
            QTabWidget::pane { border: 1px solid #bbdefb; background: white; }
            QTabBar::tab  { background: #e3f2fd; color: #555; padding: 6px 14px; }
            QTabBar::tab:selected { background: white; color: #1565c0; font-weight: bold; }
            QScrollArea   { border: none; }
            QCheckBox     { color: #1565c0; }
        """)

    # ── Slots ────────────────────────────────────────────────

    def _toggle_gravite(self, active):
        self.canvas.activer_gravite(active)

    def _ajouter_bloc(self):
        nom_mat = self.combo_materiau.currentText()
        mat     = self.MATERIAUX[nom_mat]
        self.canvas.ajouter_bloc(
            self.spin_largeur.value(),
            self.spin_hauteur.value(),
            materiau=nom_mat,
            densite=mat["density"]
        )

    def _supprimer_bloc(self):
        ligne = self.liste_blocs.currentRow()
        if ligne >= 0:
            self.canvas.supprimer_bloc(ligne)

    def _selectionner_bloc(self, ligne):
        self._bloc_selectionne = ligne
        if 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            self.spin_force.setValue(bloc["ext_force"])
            self.spin_pression.setValue(bloc["pressure"])
            self.spin_moment.setValue(bloc["moment"])

    def _appliquer_charges(self):
        ligne = self._bloc_selectionne
        if ligne is not None and 0 <= ligne < len(self.canvas.blocs):
            bloc              = self.canvas.blocs[ligne]
            bloc["ext_force"] = self.spin_force.value()
            bloc["pressure"]  = self.spin_pression.value()
            bloc["moment"]    = self.spin_moment.value()
            self.callback_physique()

    def rafraichir_liste(self):
        """Met à jour la liste des blocs dans le panneau."""
        self.liste_blocs.clear()
        for i, bloc in enumerate(self.canvas.blocs):
            p = bloc["patch"]
            self.liste_blocs.addItem(
                f"[{i+1}] {bloc['material']}  {p.get_width():.1f} × {p.get_height():.1f} m"
            )

    def afficher_resultats(self, html):
        self.lbl_resultats.setText(html)


# ──────────────────────────────────────────────────────────────
#  Fenêtre principale
# ──────────────────────────────────────────────────────────────

class MaterialSimulationApp(QMainWindow):
    """
    Fenêtre principale de la simulation 2D.
    Assemble le canvas et le panneau de contrôle,
    et orchestre les calculs physiques.
    """

    def __init__(self, mode="2D", switch_callback=None):
        super().__init__()
        self.setWindowTitle("Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        mise_en_page = QHBoxLayout(central)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)

        # Zone de dessin (gauche)
        self.canvas = Canvas2D(central, on_blocs_changes=self._on_changed)
        mise_en_page.addWidget(self.canvas, stretch=1)

        # Panneau de contrôle (droite, dans un dock)
        self.panneau = PanneauControle(self.canvas, self._on_changed)

        # On branche le bouton switch ici (pas dans le panneau)
        # pour garder accès direct au callback
        if switch_callback:
            self.panneau.btn_switch_3d.clicked.connect(switch_callback)

        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panneau)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _on_changed(self):
        """Appelé à chaque modification : recalcule et redessine."""
        self.panneau.rafraichir_liste()
        donnees_stress, paires = self._calculer_physique()
        self.canvas.dessiner_contraintes(donnees_stress, paires)

    def _calculer_physique(self):
        """
        Calcule pour chaque bloc :
        - poids propre, force axiale totale (avec contact)
        - contraintes de compression et de flexion (σ = M·y/I)
        - taux d'utilisation par rapport à la limite élastique σ_y
        Retourne les données de stress et les paires de contact.
        """
        blocs = self.canvas.blocs
        if not blocs:
            self.panneau.afficher_resultats("Aucun bloc.")
            return [], []

        MAT   = PanneauControle.MATERIAUX
        lignes = []

        # ── Propriétés globales de la section ──
        aire_totale = sum(b["patch"].get_width() * b["patch"].get_height() for b in blocs)

        XG = sum(
            (b["patch"].get_xy()[0] + b["patch"].get_width()/2) *
            b["patch"].get_width() * b["patch"].get_height()
            for b in blocs
        ) / aire_totale

        YG = sum(
            (b["patch"].get_xy()[1] + b["patch"].get_height()/2) *
            b["patch"].get_width() * b["patch"].get_height()
            for b in blocs
        ) / aire_totale

        # Moments d'inertie par rapport au centre de gravité (Steiner)
        Ixx = sum(
            (b["patch"].get_width() * b["patch"].get_height()**3) / 12 +
            b["patch"].get_width() * b["patch"].get_height() *
            (b["patch"].get_xy()[1] + b["patch"].get_height()/2 - YG)**2
            for b in blocs
        )
        Iyy = sum(
            (b["patch"].get_height() * b["patch"].get_width()**3) / 12 +
            b["patch"].get_width() * b["patch"].get_height() *
            (b["patch"].get_xy()[0] + b["patch"].get_width()/2 - XG)**2
            for b in blocs
        )
        masse_totale = sum(b["density"] * b["patch"].get_width() * b["patch"].get_height() for b in blocs)

        lignes += [
            "<b style='color:#1565c0'>══ Section globale ══</b>",
            f"Aire   : <b>{aire_totale:.4f} m²</b>",
            f"CG     : <b>({XG:.3f}, {YG:.3f}) m</b>",
            f"Ixx    : <b>{Ixx:.4f} m⁴</b>",
            f"Iyy    : <b>{Iyy:.4f} m⁴</b>",
            f"Masse  : <b>{masse_totale:.1f} kg/m</b>",
            "",
        ]

        paires = _contact_pairs(blocs)
        donnees_stress = []

        for i, bloc in enumerate(blocs):
            patch = bloc["patch"]
            w, h  = patch.get_width(), patch.get_height()
            x, y  = patch.get_xy()
            aire  = w * h
            mat   = MAT.get(bloc["material"], MAT["Acier"])

            # Forces appliquées sur ce bloc
            poids          = bloc["density"] * aire * GRAVITY
            F_ext          = bloc["ext_force"]
            F_pression     = bloc["pressure"] * w  # pression × largeur = force totale

            # Charge venant des blocs posés dessus (transfert de contact)
            F_contact = sum(
                blocs[j]["density"] * blocs[j]["patch"].get_width() *
                blocs[j]["patch"].get_height() * GRAVITY +
                blocs[j]["ext_force"] +
                blocs[j]["pressure"] * blocs[j]["patch"].get_width()
                for (i_bas, j, _) in paires if i_bas == i
            )

            # Contrainte axiale de compression : σ = F / A
            F_axial     = poids + F_ext + F_pression + F_contact
            sigma_axial = F_axial / aire

            # Contraintes de flexion : σ = M × y / I
            M       = bloc["moment"]
            I_local = (w * h**3) / 12
            sig_haut = M * (h/2)  / I_local if I_local > 0 else 0  # fibre haute
            sig_bas  = M * (-h/2) / I_local if I_local > 0 else 0  # fibre basse

            # Superposition : contrainte totale maximale
            sigma_max = max(abs(sigma_axial + sig_haut), abs(sigma_axial + sig_bas))

            # Taux d'utilisation par rapport à la limite élastique
            sigma_y = mat["sigma_y"]
            taux    = sigma_max / sigma_y * 100
            statut  = "✅ OK" if taux < 80 else ("⚠️ Attention" if taux < 100 else "❌ RUPTURE")

            lignes += [
                f"<b style='color:#e65100'>── Bloc {i+1} ({bloc['material']}) ──</b>",
                f"  Poids propre   : {poids:.1f} N",
                f"  Charge contact : {F_contact:.1f} N",
                f"  Force ext.     : {F_ext:.1f} N",
                f"  Pression       : {F_pression:.1f} N",
                f"  <b>F axiale total : {F_axial:.1f} N</b>",
                f"  σ axiale       : {sigma_axial/1e6:.3f} MPa",
            ]
            if abs(M) > 0:
                lignes += [
                    f"  σ flex haut    : {sig_haut/1e6:.3f} MPa",
                    f"  σ flex bas     : {sig_bas/1e6:.3f} MPa",
                ]
            lignes += [
                f"  <b>σ max          : {sigma_max/1e6:.3f} MPa</b>",
                f"  σ_y limite     : {sigma_y/1e6:.0f} MPa",
                f"  Utilisation    : {taux:.1f}% {statut}",
                "",
            ]

            donnees_stress.append({
                "sigma_total":       sigma_max,
                "sigma_axial":       sigma_axial,
                "sigma_bending_top": sig_haut,
                "sigma_bending_bot": sig_bas,
                "ext_force":         F_ext + F_pression,
                "pressure":          bloc["pressure"],
                "utilization":       taux,
                "F_axial":           F_axial,
            })

        # Résumé des contacts dans le panneau
        if paires:
            lignes.append("<b style='color:#ff6f00'>══ Contacts détectés ══</b>")
            for (i_bas, i_haut, frac) in paires:
                Fc = donnees_stress[i_haut]["F_axial"]
                lignes.append(
                    f"  Bloc {i_haut+1} → Bloc {i_bas+1} : "
                    f"<b>{Fc:.0f} N</b> ({frac*100:.0f}% surface)"
                )
            lignes.append("")

        self.panneau.afficher_resultats("<br>".join(lignes))
        return donnees_stress, paires


# ──────────────────────────────────────────────────────────────
#  Point d'entrée (lancement direct du fichier)
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fenetre = MaterialSimulationApp()
    fenetre.show()
    sys.exit(app.exec()) 