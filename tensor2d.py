"""
tensor2D.py  —  Tensor Build
Simulateur 2D de résistance des matériaux.

On peut ajouter des blocs rectangulaires, les déplacer,
leur appliquer des forces, et voir les contraintes en temps réel.
"""

import sys
import functools
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyArrowPatch
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QDoubleSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QFormLayout, QGroupBox, QFrame, QScrollArea, QTabWidget, QComboBox,
    QCheckBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QGuiApplication


# ──────────────────────────────────────────────────────────────
#  Constantes globales
# ──────────────────────────────────────────────────────────────

GRAVITY = 9.81   # accélération gravitationnelle (m/s²)
GROUND_Y = 0.0    # position y du sol sur le canvas
SNAP_TOL = 0.18   # distance max pour considérer deux blocs en contact (m)
FALL_STEP = 0.12   # distance de chute par tick de physique (m)
TIMER_MS = 30     # intervalle du timer de physique (ms) — ~33 fps

# Limites fixes du repère (m) : la vue ne se rééchelonne pas avec la carte de pression
AXIS_XLIM = (-2.0, 12.0)
AXIS_YLIM = (-1.5, 12.0)
# Taille max. de la grille « carte de pression » (nombre de mailles par côté)
HEATMAP_CELLES_MAX = 16

# Matériaux : densité (kg/m³), E et σ_y (Pa) ; face / edge = couleurs du patch matplotlib
MATERIAUX = {
    "Acier": {
        "density": 7850, "E": 210e9, "sigma_y": 250e6,
        "face": "#b0bec5", "edge": "#37474f",
    },
    "Béton": {
        "density": 2400, "E": 30e9, "sigma_y": 30e6,
        "face": "#bdbdbd", "edge": "#424242",
    },
    "Aluminium": {
        "density": 2700, "E": 70e9, "sigma_y": 270e6,
        "face": "#e3f2fd", "edge": "#0277bd",
    },
    "Bois": {
        "density": 600, "E": 12e9, "sigma_y": 40e6,
        "face": "#a67c52", "edge": "#3e2723",
    },
    "Fonte": {
        "density": 7200, "E": 170e9, "sigma_y": 200e6,
        "face": "#78909c", "edge": "#263238",
    },
}


def _blue_plasma_cmap():
    """Colormap type « plasma » tronquée sur les bleus (base visuelle carte pression)."""
    base = cm.get_cmap("plasma", 256)
    return mcolors.ListedColormap(base(np.linspace(0.0, 0.52, 256)))


def _pressure_grid_pa(p_pa, nx, ny):
    """
    Matrice (ny, nx) des pressions par cellule (Pa), même logique que le dessin.
    Ligne 0 = bas du bloc, colonne 0 = gauche (repère monde, comme imshow).
    """
    ix = np.linspace(0.5 / nx, 1.0 - 0.5 / nx, nx, dtype=np.float64)
    iy = np.linspace(0.5 / ny, 1.0 - 0.5 / ny, ny, dtype=np.float64)
    u, v = np.meshgrid(ix, iy, indexing="xy")
    facteur_cellule = 0.5 + 0.5 * (u * v)
    return np.where(p_pa > 0, p_pa * facteur_cellule, 0.0)


def _pressure_grid_rgba_from_pa(pa, norme_pression, cmap_p):
    """Image (ny, nx, 4) RGBA à partir d’une matrice pression (Pa)."""
    return cmap_p(norme_pression(pa))


def _vider_serie_artists(serie):
    """Retire chaque artiste matplotlib de l’axe puis vide la liste."""
    for artiste in list(serie):
        try:
            artiste.remove()
        except Exception:
            pass
    serie.clear()


def _geom_patch(rd):
    """Coin bas-gauche et dimensions du rectangle matplotlib du bloc."""
    p = rd["patch"]
    x, y = p.get_xy()
    return x, y, p.get_width(), p.get_height()


def _charge_verticale_equivalente(rd):
    """Poids + charges appliquées, ramenées à une charge verticale « sur le dessous » du bloc (N)."""
    x, y, w, h = _geom_patch(rd)
    return (
        rd["density"] * w * h * GRAVITY
        + rd["ext_force"]
        + rd["pressure"] * w
    )


def _hauteur_appui_max(blocs, idx):
    """Plus haute surface sous ce bloc : sol ou sommet d’un autre bloc en recouvrement (m)."""
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


def _statistiques_globales_section(blocs):
    """Aire, centre de gravité, inerties et masse (blocs rectangles, 1 m d’épaisseur)."""
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
    XG = sx / aire_totale
    YG = sy / aire_totale
    Ixx = sum(
        (w * h**3) / 12 + w * h * (y + h / 2 - YG) ** 2
        for x, y, w, h, a in rectangles
    )
    Iyy = sum(
        (h * w**3) / 12 + w * h * (x + w / 2 - XG) ** 2
        for x, y, w, h, a in rectangles
    )
    return aire_totale, XG, YG, Ixx, Iyy, masse


def _statut_utilisation(util_pct):
    """Libellé et pictogramme selon le % d’utilisation par rapport à σ_y."""
    if util_pct < 80:
        return "OK", "✓"
    if util_pct < 100:
        return "⚠️ Attention", "!"
    return "❌ RUPTURE", "✗"


# ──────────────────────────────────────────────────────────────
#  Fonctions utilitaires de physique
# ──────────────────────────────────────────────────────────────

def _overlaps_x(bloc_a, bloc_b):
    """
    Vérifie si deux blocs se chevauchent horizontalement.
    Utilisé pour savoir si un contact vertical est possible.
    """
    xa, _ = bloc_a["patch"].get_xy()
    wa = bloc_a["patch"].get_width()
    xb, _ = bloc_b["patch"].get_xy()
    wb = bloc_b["patch"].get_width()
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
            wi, hi = blocs[i]["patch"].get_width(
            ), blocs[i]["patch"].get_height()
            xj, yj = blocs[j]["patch"].get_xy()
            wj = blocs[j]["patch"].get_width()

            # Le dessus du bloc i est-il proche du dessous du bloc j ?
            contact_vertical = abs((yi + hi) - yj) <= tol
            if contact_vertical and _overlaps_x(blocs[i], blocs[j]):
                largeur_contact = min(xi + wi, xj + wj) - max(xi, xj)
                fraction = largeur_contact / min(wi, wj)
                paires.append((i, j, fraction))

    return paires


def _resoudre_collision(idx_mobile, blocs):
    """
    Quand un bloc en est glissé dans un autre, cette fonction
    le repousse vers la sortie la plus proche (axe de moindre pénétration).
    C'est ce qui empêche les blocs de se traverser pendant le drag.
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

        # Test de chevauchement AABB (boîte englobante)
        chevauche_x = mx < ox + ow and ox < mx + largeur
        chevauche_y = my < oy + oh and oy < my + hauteur

        if chevauche_x and chevauche_y:
            # Calcule la profondeur de pénétration sur chaque côté
            penet_haut = (oy + oh) - my      # bloc monte sur l'autre
            penet_bas = (my + hauteur) - oy  # bloc descend sous l'autre
            penet_droite = (ox + ow) - mx
            penet_gauche = (mx + largeur) - ox

            # On choisit la sortie la moins coûteuse
            min_penet = min(penet_haut, penet_bas, penet_droite, penet_gauche)

            if min_penet == penet_haut:
                patch_mobile.set_xy((mx, oy + oh))      # pose par-dessus
            elif min_penet == penet_bas:
                patch_mobile.set_xy((mx, oy - hauteur))  # glisse en dessous
            elif min_penet == penet_droite:
                patch_mobile.set_xy((ox + ow, my))      # pousse à droite
            else:
                patch_mobile.set_xy((ox - largeur, my))  # pousse à gauche

            # Relit la position après correction (peut avoir changé)
            mx, my = patch_mobile.get_xy()
            collision = True

    return collision


class ContactTooltip(QWidget):
    """Petite fenêtre HTML déplaçable pour détailler un contact (effort, recouvrement)."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("ContactTooltip")
        self._bounds = QRect()
        self._drag_offset = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(6)
        self._drag_hint = QWidget()
        self._drag_hint.setMinimumHeight(18)
        self._drag_hint.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drag_hint.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_hint.setToolTip(
            "Glisser pour déplacer (reste dans le plan de dessin)")
        head.addWidget(self._drag_hint, stretch=1)
        self._btn_close = QPushButton("×")
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setStyleSheet(
            "QPushButton { background:#ff6f00; color:white; font-size:14px; "
            "font-weight:bold; border:none; border-radius:3px; } "
            "QPushButton:hover { background:#e65100; }")
        self._btn_close.setToolTip("Fermer")
        self._btn_close.clicked.connect(self.hide)
        head.addWidget(self._btn_close)
        lay.addLayout(head)
        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        self._lbl.setTextFormat(Qt.TextFormat.RichText)
        self._lbl.setStyleSheet(
            "font-family: Consolas; font-size: 10px; color: #1a1a1a;")
        lay.addWidget(self._lbl)
        self.setStyleSheet(
            "QWidget#ContactTooltip { background:#fffef0; color:#1a1a1a; "
            "border:1px solid #c9a000; border-radius:5px; }")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumSize(180, 72)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()

    def _drag_blocked_widget(self, child):
        if child is None:
            return False
        return (
            child is self._btn_close
            or self._btn_close.isAncestorOf(child))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ch = self.childAt(event.position().toPoint())
            if not self._drag_blocked_widget(ch):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.pos())
                self.grabMouse()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            p = event.globalPosition().toPoint() - self._drag_offset
            self.move(self._clamp_top_left(p))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_offset is not None:
                self.releaseMouse()
                self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def set_plot_bounds_global(self, rect: QRect):
        """Rectangle global (écran) dans lequel l’infobulle peut glisser."""
        self._bounds = QRect(rect)

    def _clamp_top_left(self, top_left: QPoint) -> QPoint:
        """Recadre le coin haut-gauche pour rester dans _bounds, avec une marge."""
        x, y = top_left.x(), top_left.y()
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            self.adjustSize()
            w, h = self.width(), self.height()
        if self._bounds.isNull() or self._bounds.isEmpty():
            return QPoint(x, y)
        m = 2
        r = self._bounds
        x_min, y_min = r.left() + m, r.top() + m
        x_max = r.right() - w - m
        y_max = r.bottom() - h - m
        if x_max < x_min:
            x = r.left() + m
        else:
            x = min(max(x_min, x), x_max)
        if y_max < y_min:
            y = r.top() + m
        else:
            y = min(max(y_min, y), y_max)
        return QPoint(x, y)

    def clamp_to_bounds(self):
        """Après redimensionnement : garde la fenêtre visible dans la zone autorisée."""
        self.move(self._clamp_top_left(self.pos()))

    def set_rich_text(self, html):
        """Affiche du texte riche (HTML) dans le corps de l’infobulle."""
        self._lbl.setText(html)


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

    def _verrouiller_vue(self):
        """Réapplique les limites d’axes (vue figée, pas d’auto-échelle)."""
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
        """Callback appelé quand l’utilisateur clique dans une zone de contact (dict hit)."""
        self._callback_contact = callback

    def _donnees_vers_global(self, xd, yd):
        """Convertit des coordonnées « données » matplotlib en QPoint global écran."""
        disp = self.axes.transData.transform((xd, yd))
        x_disp, y_disp = float(disp[0]), float(disp[1])
        h = float(self.figure.bbox.height)
        x_qt = int(round(x_disp))
        y_qt = int(round(h - y_disp))
        return self.mapToGlobal(QPoint(x_qt, y_qt))

    def _souris_vers_global(self, event):
        """Position souris événement mpl → coordonnées globales Qt (ou None)."""
        try:
            x, y = float(event.x), float(event.y)
        except (TypeError, ValueError):
            return None
        h = float(self.figure.bbox.height)
        if h < 1:
            return None
        return self.mapToGlobal(
            QPoint(int(round(x)), int(round(h - y))))

    def rectangle_axes_global(self):
        """Rectangle écran couvrant la zone tracée des axes (pour borner l’infobulle)."""
        fig = self.figure
        try:
            self.draw()
        except Exception:
            pass
        try:
            r = self.axes.get_window_extent(renderer=self.get_renderer())
        except Exception:
            r = self.axes.get_window_extent()
        H = float(fig.bbox.height)
        if H < 1 or r.width < 2 or r.height < 2:
            g = self.mapToGlobal(QPoint(0, 0))
            return QRect(g.x(), g.y(), max(1, self.width()), max(1, self.height()))
        x0 = int(round(r.x0))
        y0 = int(round(H - r.y1))
        w = max(1, int(round(r.width)))
        h = max(1, int(round(r.height)))
        tl = self.mapToGlobal(QPoint(x0, y0))
        return QRect(tl.x(), tl.y(), w, h)

    def point_contact_global(self, hit):
        """Point global au centre horizontal de l’interface de contact."""
        return self._donnees_vers_global(hit["cx"], hit["y_if"])

    def rafraichir_position_infobulle_contact(self, tip):
        """Recalcule les limites de glissement après resize / redraw du graphe."""
        tip.set_plot_bounds_global(self.rectangle_axes_global())
        tip.clamp_to_bounds()

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
        Crée un nouveau bloc rectangulaire et l'ajoute au canvas.
        Si la gravité est active, il apparaît en haut et tombe.
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
                sommets = [
                    b["patch"].get_xy()[1] + b["patch"].get_height()
                    for b in self.blocs]
                y_depart = max(sommets)
            x_depart = 0.5

        patch = Rectangle(
            (x_depart, y_depart), largeur, hauteur,
            facecolor=fc, edgecolor=ec,
            linewidth=1.8, zorder=5, alpha=0.9
        )
        self.axes.add_patch(patch)

        self.blocs.append({
            "patch":      patch,
            "material":   materiau,
            "density":    densite,
            "edgecolor":  ec,
            "ext_force":  0.0,
            "moment":     0.0,
            "pressure":   0.0,
            "heatmap_matrice":  None,
            "heatmap_cellules": None,
        })
        self._notifier()

    def supprimer_bloc(self, index):
        """Supprime le bloc à l'index donné du canvas et de la liste."""
        if 0 <= index < len(self.blocs):
            self.blocs[index]["patch"].remove()
            self.blocs.pop(index)
            self._notifier()

    # ── Drag & drop ──────────────────────────────────────────

    def _tester_clic_contact(self, event):
        """Si le clic tombe dans la bande cliquable d’un joint, retourne le dict pour le callback."""
        if event.xdata is None or event.ydata is None:
            return None
        xd, yd = event.xdata, event.ydata
        for z in reversed(self._zones_contact_clic):
            if (z["x0"] <= xd <= z["x1"] and z["y0"] <= yd <= z["y1"]):
                return {
                    "i_bot": z["i_bot"],
                    "i_top": z["i_top"],
                    "frac":  z["frac"],
                    "F_c":   z["F_c"],
                    "cx":    z["cx"],
                    "y_if":  z["y_if"],
                }
        return None

    def _tester_clic(self, event):
        """
        Retourne l'index du bloc cliqué, en partant du dessus (dernier ajouté).
        Retourne None si le clic est dans le vide.
        """
        for i, bloc in enumerate(reversed(self.blocs)):
            idx = len(self.blocs) - 1 - i
            xy = bloc["patch"].get_xy()
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

        # Limite le déplacement aux bords du canvas
        x = max(xmin,     min(xmax - w, event.xdata - self._offset_drag[0]))
        y = max(GROUND_Y, min(ymax - h, event.ydata - self._offset_drag[1]))
        patch.set_xy((x, y))

        # Empêche la traversée d'autres blocs en temps réel
        _resoudre_collision(self._idx_drag, self.blocs)

        self.draw_idle()

    def _souris_relache(self, event):
        self._idx_drag = None
        self._offset_drag = None
        self._notifier()

    def _notifier(self, refresh_list=True):
        """Prévient l’app (rafraîchir la liste des blocs ou non, puis physique)."""
        if self._on_blocs_changes:
            self._on_blocs_changes(refresh_list=refresh_list)

    # ── Rendu visuel des contraintes ─────────────────────────

    def dessiner_contraintes(self, donnees_stress, paires_contact):
        """
        Couche contraintes : si carte de pression activée, grille de couleurs (Pa) ;
        sinon barres RdYlGn selon σ. Joints cliquables, effort affiché.
        Le centre de gravité n’est affiché que dans le panneau Résultats.
        """
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
            toutes_sigmas = [
                abs(d["sigma_total"]) for d in donnees_stress if d]
            sigma_max_global = (
                max(toutes_sigmas)
                if any(s > 0 for s in toutes_sigmas) else 1.0)
            colormap = cm.get_cmap("RdYlGn_r")
            normaliseur = mcolors.Normalize(vmin=0, vmax=sigma_max_global)

        for bloc, stress in zip(self.blocs, donnees_stress):
            if stress is None:
                continue

            x, y, w, h = _geom_patch(bloc)

            if self.carte_chaleur and norme_pression is not None:
                p_pa = float(bloc["pressure"])
                nx = max(2, min(HEATMAP_CELLES_MAX, int(w * 10)))
                ny = max(2, min(HEATMAP_CELLES_MAX, int(h * 10)))
                pa = _pressure_grid_pa(p_pa, nx, ny)
                bloc["heatmap_matrice"] = pa
                bloc["heatmap_cellules"] = (nx, ny)
                rgba = _pressure_grid_rgba_from_pa(
                    pa, norme_pression, carte_couleurs)
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
                        (x, y + decalage), w, h / 2,
                        facecolor=couleur, edgecolor="none",
                        alpha=0.55, zorder=6)
                    self.axes.add_patch(rect)
                    self._patches_stress.append(rect)
            else:
                couleur = colormap(normaliseur(abs(stress["sigma_total"])))
                rect = Rectangle(
                    (x, y), w, h,
                    facecolor=couleur, edgecolor="none",
                    alpha=0.55, zorder=6)
                self.axes.add_patch(rect)
                self._patches_stress.append(rect)

            ec = bloc.get("edgecolor") or MATERIAUX.get(
                bloc["material"], MATERIAUX["Acier"])["edge"]
            contour = Rectangle(
                (x, y), w, h,
                facecolor="none", edgecolor=ec,
                linewidth=1.5, zorder=7)
            self.axes.add_patch(contour)
            self._patches_stress.append(contour)

            if abs(y - GROUND_Y) < SNAP_TOL * 2.0:
                sh = min(0.09, max(0.04, h * 0.22))
                sol_sh = Rectangle(
                    (x, y), w, sh,
                    facecolor="#000000", edgecolor="none", alpha=0.34,
                    zorder=8)
                self.axes.add_patch(sol_sh)
                self._patches_stress.append(sol_sh)

            if not self.carte_chaleur:
                util = stress["utilization"]
                symbole = "✓" if util < 80 else ("!" if util < 100 else "✗")
                label = self.axes.text(
                    x + w / 2, y + h / 2,
                    f"σ = {stress['sigma_total']/1e6:.2f} MPa\n"
                    f"{util:.0f}% {symbole}",
                    ha="center", va="center", fontsize=7.5,
                    color="black", fontweight="bold", zorder=10,
                    bbox=dict(
                        boxstyle="round,pad=0.2", facecolor="white",
                        alpha=0.65, edgecolor="none"))
                self._patches_stress.append(label)

            if abs(stress.get("ext_force", 0)) > 0:
                cx = x + w / 2
                fleche = FancyArrowPatch(
                    (cx, y + h + 0.7), (cx, y + h + 0.05),
                    arrowstyle="-|>", mutation_scale=16,
                    color="#d32f2f", linewidth=2.5, zorder=11)
                self.axes.add_patch(fleche)
                self._artistes_fleches.append(fleche)
                lbl_force = self.axes.text(
                    cx, y + h + 0.8, f"F = {stress['ext_force']:.0f} N",
                    ha="center", va="bottom", fontsize=7.5,
                    color="#d32f2f", fontweight="bold", zorder=11)
                self._artistes_fleches.append(lbl_force)

            if abs(stress.get("pressure", 0)) > 0:
                nb_fleches = max(3, int(w * 2))
                for k in range(nb_fleches):
                    x_fleche = x + (k + 0.5) * w / nb_fleches
                    f = FancyArrowPatch(
                        (x_fleche, y + h + 0.35), (x_fleche, y + h + 0.02),
                        arrowstyle="-|>", mutation_scale=9,
                        color="#e65100", linewidth=1.2, zorder=11)
                    self.axes.add_patch(f)
                    self._artistes_fleches.append(f)

        def _y_interface(pa):
            i_bot, _, _ = pa
            _, yb, _, hb = _geom_patch(self.blocs[i_bot])
            return yb + hb

        paires_triees = sorted(paires_contact, key=_y_interface)

        for (i_bas, i_haut, fraction) in paires_triees:
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
                    (x_gauche, y_bot0), x_droite - x_gauche, h_bot,
                    facecolor="#000000", edgecolor="none", alpha=0.36,
                    zorder=9)
                self.axes.add_patch(sb)
                self._patches_stress.append(sb)
            y_top1 = min(yt + ht, y_interface + shade_d)
            h_top = y_top1 - y_interface
            if h_top > 1e-4:
                st = Rectangle(
                    (x_gauche, y_interface), x_droite - x_gauche, h_top,
                    facecolor="#000000", edgecolor="none", alpha=0.36,
                    zorder=9)
                self.axes.add_patch(st)
                self._patches_stress.append(st)

            cr = Rectangle(
                (x_gauche, y_interface - 0.05), x_droite - x_gauche, 0.10,
                facecolor="#1a1a1a", edgecolor="none", alpha=0.88, zorder=12)
            self.axes.add_patch(cr)
            self._patches_stress.append(cr)

            F_contact = donnees_stress[i_haut]["F_axial"]
            cx = (x_gauche + x_droite) / 2

            pad_x, pad_y = 0.04, 0.05
            self._zones_contact_clic.append({
                "x0": x_gauche - pad_x,
                "x1": x_droite + pad_x,
                "y0": y_interface - 0.05 - pad_y,
                "y1": y_interface + 0.05 + pad_y,
                "i_bot": i_bas,
                "i_top": i_haut,
                "frac":  fraction,
                "F_c":   F_contact,
                "cx":    cx,
                "y_if":  y_interface,
            })

            fleche_bas = FancyArrowPatch(
                (cx - 0.12, y_interface + 0.55),
                (cx - 0.12, y_interface + 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#d32f2f", linewidth=2.5, zorder=13)
            self.axes.add_patch(fleche_bas)
            self._artistes_fleches.append(fleche_bas)

            fleche_haut = FancyArrowPatch(
                (cx + 0.12, y_interface - 0.55),
                (cx + 0.12, y_interface - 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#1565c0", linewidth=2.5, zorder=13)
            self.axes.add_patch(fleche_haut)
            self._artistes_fleches.append(fleche_haut)

            lbl_contact = self.axes.text(
                cx + 0.3, y_interface,
                f"Fc = {F_contact:.0f} N\n({fraction*100:.0f}% recouvrement)",
                ha="left", va="center", fontsize=7,
                color="#bf360c", fontweight="bold", zorder=14,
                bbox=dict(
                    boxstyle="round,pad=0.25",
                    facecolor="#fff3e0", alpha=0.92, edgecolor="#ff6f00"))
            self._artistes_fleches.append(lbl_contact)

        self._verrouiller_vue()
        self.draw_idle()


def _ligne_liste_bloc(panneau, index: int, libelle: str) -> QWidget:
    """Une ligne de liste : libellé du bloc + bouton × pour supprimer."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(2, 2, 2, 2)
    lbl = QLabel(libelle)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    btn = QPushButton("×")
    btn.setFixedSize(22, 22)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Supprimer ce bloc")
    btn.clicked.connect(functools.partial(panneau._supprimer_a_index, index))
    h.addWidget(lbl, stretch=1)
    h.addWidget(btn)

    def _press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            panneau.liste_blocs.setCurrentRow(index)
        QWidget.mousePressEvent(w, event)

    w.mousePressEvent = _press
    return w


PANEL_QSS = """
    QFrame        { background: #f5f5f5; }
    QGroupBox     { color:#1565c0; border:1px solid #bbdefb; margin-top:8px;
                    padding-top:6px; border-radius:4px; font-weight:bold; }
    QGroupBox::title { subcontrol-origin:margin; left:8px; }
    QLabel        { color:#333; }
    QDoubleSpinBox{ background:white; color:#222; border:1px solid #90caf9;
                    border-radius:3px; padding:2px; }
    QPushButton   { background:#1565c0; color:white; border:none;
                    border-radius:4px; padding:7px; font-weight:bold; }
    QPushButton:hover { background:#1976d2; }
    QListWidget   { background:white; color:#222; border:1px solid #bbdefb; }
    QComboBox     { background:white; color:#222; border:1px solid #90caf9;
                    border-radius:3px; padding:2px; }
    QTabWidget::pane { border:1px solid #bbdefb; background:white; }
    QTabBar::tab  { background:#e3f2fd; color:#555; padding:6px 14px; }
    QTabBar::tab:selected { background:white; color:#1565c0; font-weight:bold; }
    QScrollArea   { border:none; }
    QCheckBox     { color:#1565c0; spacing: 6px; }
    QCheckBox::indicator { width: 18px; height: 18px; }
    QCheckBox::indicator:unchecked {
        background: white;
        border: 2px solid #90caf9;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background: #1565c0;
        border: 2px solid #1565c0;
        border-radius: 3px;
    }
"""


# ──────────────────────────────────────────────────────────────
#  Panneau de contrôle  —  interface utilisateur droite
# ──────────────────────────────────────────────────────────────

class PanneauControle(QFrame):
    """Panneau latéral : 3D, gravité, carte de pression, blocs, charges, résultats."""

    def __init__(self, canvas, callback_physique, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.callback_physique = callback_physique
        self._bloc_selectionne = None
        self._contact_sel = None
        self._infobulle_contact = None
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
        lay_grav = QVBoxLayout(grp_gravite)

        self.chk_gravite = QCheckBox("🌍  Activer la gravité")
        self.chk_gravite.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.chk_gravite.toggled.connect(self._toggle_gravite)
        lay_grav.addWidget(self.chk_gravite)

        self.chk_carte_chaleur = QCheckBox("Carte de pression (Pa)")
        self.chk_carte_chaleur.setStyleSheet(
            "font-weight: bold; font-size: 11px;")
        self.chk_carte_chaleur.setToolTip(
            "Grille de couleurs sur chaque bloc selon la pression (pascals) ; décoratif.")
        self.chk_carte_chaleur.toggled.connect(self._toggle_carte_chaleur)
        lay_grav.addWidget(self.chk_carte_chaleur)

        info_gravite = QLabel(
            "Quand la gravité est activée : les nouveaux blocs\n"
            "tombent et s'empilent. Les blocs ne se traversent pas."
        )
        info_gravite.setStyleSheet("color: #555; font-size: 8px;")
        lay_grav.addWidget(info_gravite)

        grp_gravite.setLayout(lay_grav)
        layout.addWidget(grp_gravite)

        lbl_hint = QLabel(
            "<span style='color:#888;font-size:8px'>"
            "Cliquez sur une surface de contact pour afficher les détails.</span>"
        )
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        onglets = QTabWidget()

        # Onglet "Blocs"
        tab_blocs = QWidget()
        lay_blocs = QVBoxLayout(tab_blocs)

        grp_nouveau = QGroupBox("Nouveau bloc")
        form_nouveau = QFormLayout()
        self.spin_largeur = QDoubleSpinBox()
        self.spin_largeur.setRange(0.1, 20)
        self.spin_largeur.setValue(2)
        self.spin_largeur.setSingleStep(0.25)
        self.spin_hauteur = QDoubleSpinBox()
        self.spin_hauteur.setRange(0.1, 20)
        self.spin_hauteur.setValue(1)
        self.spin_hauteur.setSingleStep(0.25)
        self.combo_materiau = QComboBox()
        for nom in MATERIAUX:
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
        self.liste_blocs.setMaximumHeight(180)
        self.liste_blocs.currentRowChanged.connect(self._selectionner_bloc)
        lay_liste.addWidget(self.liste_blocs)
        grp_liste.setLayout(lay_liste)
        lay_blocs.addWidget(grp_liste)
        lay_blocs.addStretch()
        onglets.addTab(tab_blocs, "Blocs")

        # Onglet "Charges"
        tab_charges = QWidget()
        lay_charges = QVBoxLayout(tab_charges)
        grp_charges = QGroupBox("Charges — bloc sélectionné")
        form_charges = QFormLayout()

        self.spin_force = QDoubleSpinBox()
        self.spin_force.setRange(0, 1e7)
        self.spin_force.setSuffix(" N")
        self.spin_force.setSingleStep(100)
        self.spin_pression = QDoubleSpinBox()
        self.spin_pression.setRange(0, 1e6)
        self.spin_pression.setSuffix(" Pa")
        self.spin_pression.setSingleStep(500)
        self.spin_moment = QDoubleSpinBox()
        self.spin_moment.setRange(-1e6, 1e6)
        self.spin_moment.setSuffix(" N·m")
        self.spin_moment.setSingleStep(100)

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

        tab_resultats = QWidget()
        lay_res = QVBoxLayout(tab_resultats)
        lay_res.setContentsMargins(4, 4, 4, 4)
        lay_res.setSpacing(8)

        grp_cdgr = QGroupBox("Centre de gravité")
        lay_cdgr = QVBoxLayout(grp_cdgr)
        self.lbl_cdgr = QLabel(
            "<i style='color:#888'>Ajoutez des blocs pour afficher le CdG.</i>")
        self.lbl_cdgr.setWordWrap(True)
        self.lbl_cdgr.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_cdgr.setStyleSheet(
            "font-family: Consolas; font-size: 9px; color: #222;")
        scroll_cdgr = QScrollArea()
        scroll_cdgr.setWidget(self.lbl_cdgr)
        scroll_cdgr.setWidgetResizable(True)
        scroll_cdgr.setMaximumHeight(140)
        lay_cdgr.addWidget(scroll_cdgr)
        grp_cdgr.setLayout(lay_cdgr)
        lay_res.addWidget(grp_cdgr)

        grp_detail = QGroupBox("Détail physique & contacts")
        lay_d = QVBoxLayout(grp_detail)
        self.lbl_rapport = QLabel(
            "<i style='color:#888'>Ajoutez des blocs pour afficher le détail.</i>")
        self.lbl_rapport.setWordWrap(True)
        self.lbl_rapport.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_rapport.setStyleSheet(
            "font-family: Consolas; font-size: 9px; color: #222;")
        scroll_r = QScrollArea()
        scroll_r.setWidget(self.lbl_rapport)
        scroll_r.setWidgetResizable(True)
        scroll_r.setMinimumHeight(200)
        lay_d.addWidget(scroll_r)
        grp_detail.setLayout(lay_d)
        lay_res.addWidget(grp_detail, stretch=1)

        onglets.addTab(tab_resultats, "Résultats")

        layout.addWidget(onglets)
        self.setStyleSheet(PANEL_QSS)

    def _toggle_gravite(self, active):
        self.canvas.activer_gravite(active)

    def _toggle_carte_chaleur(self, active):
        """Bascule l’affichage carte de pression et relance le calcul / dessin."""
        self.canvas.activer_carte_chaleur(active)
        self.callback_physique()

    def _ajouter_bloc(self):
        nom_mat = self.combo_materiau.currentText()
        mat = MATERIAUX[nom_mat]
        self.canvas.ajouter_bloc(
            self.spin_largeur.value(),
            self.spin_hauteur.value(),
            materiau=nom_mat,
            densite=mat["density"],
        )

    def _supprimer_a_index(self, index):
        if 0 <= index < len(self.canvas.blocs):
            self.canvas.supprimer_bloc(index)

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
            bloc = self.canvas.blocs[ligne]
            bloc["ext_force"] = self.spin_force.value()
            bloc["pressure"] = self.spin_pression.value()
            bloc["moment"] = self.spin_moment.value()
            self.callback_physique()

    def rafraichir_liste(self):
        self.liste_blocs.clear()
        for i, bloc in enumerate(self.canvas.blocs):
            p = bloc["patch"]
            libelle = (
                f"[{i+1}] {bloc['material']}  "
                f"{p.get_width():.1f}×{p.get_height():.1f} m")
            row = _ligne_liste_bloc(self, i, libelle)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.liste_blocs.addItem(item)
            self.liste_blocs.setItemWidget(item, row)

    def afficher_cdgr(self, html):
        self.lbl_cdgr.setText(html)

    def afficher_rapport_detail(self, html):
        self.lbl_rapport.setText(html)

    def _infobulle_contact_assuree(self):
        """Crée l’infobulle au premier besoin (parent = canvas)."""
        if self._infobulle_contact is None:
            self._infobulle_contact = ContactTooltip(self.canvas)
        return self._infobulle_contact

    def _html_infobulle_contact(self, d):
        """HTML pour i_bot, i_top, frac, F_c."""
        ib, it = d["i_bot"], d["i_top"]
        frac, fc = d["frac"], d["F_c"]
        return (
            "<b style='color:#bf360c'>Surface de contact</b><br>"
            f"Bloc supérieur <b>{it + 1}</b> → bloc inférieur <b>{ib + 1}</b><br>"
            f"Effort transmis <b>Fc = {fc:.0f} N</b><br>"
            f"Recouvrement : <b>{frac * 100:.0f} %</b> "
        )

    def _placer_infobulle_contact(self, tip, centre_contact_global: QPoint):
        """Centre horizontalement au-dessus du point de contact."""
        tip.adjustSize()
        gap_px = 6
        w, h = tip.width(), tip.height()
        x = centre_contact_global.x() - w // 2
        y = centre_contact_global.y() - h - gap_px
        tip.move(tip._clamp_top_left(QPoint(x, y)))

    def on_contact_pick(self, d):
        """Appelé par le canvas : affiche l’infobulle pour le contact décrit par d."""
        self._contact_sel = (d["i_bot"], d["i_top"])
        tip = self._infobulle_contact_assuree()

        def _open():
            tip.set_plot_bounds_global(self.canvas.rectangle_axes_global())
            tip.set_rich_text(self._html_infobulle_contact(d))
            pt = d.get("_press_global")
            if pt is None:
                pt = self.canvas.point_contact_global(d)
            self._placer_infobulle_contact(tip, pt)
            tip.setWindowOpacity(1.0)
            tip.show()
            tip.raise_()
            self.canvas.rafraichir_position_infobulle_contact(tip)
            c = tip.frameGeometry().center()
            if QGuiApplication.screenAt(c) is None:
                ps = QGuiApplication.primaryScreen()
                if ps is not None:
                    fr = tip.frameGeometry()
                    fr.moveCenter(ps.availableGeometry().center())
                    tip.move(fr.topLeft())
            QApplication.processEvents()

        QTimer.singleShot(10, _open)

    def _masquer_infobulle_contact(self):
        if self._infobulle_contact is not None:
            self._infobulle_contact.hide()
        self._contact_sel = None

    def rafraichir_infobulle_contact(self, paires, donnees_stress):
        """Met à jour le texte si la géométrie a changé ; sinon masque."""
        tip = self._infobulle_contact
        if tip is None or not tip.isVisible() or self._contact_sel is None:
            return
        ib, it = self._contact_sel
        for p in paires:
            if p[0] == ib and p[1] == it:
                frac = p[2]
                sd = donnees_stress[it] if it < len(donnees_stress) else None
                if sd is None:
                    self._masquer_infobulle_contact()
                    return
                fc = sd["F_axial"]
                tip.set_rich_text(self._html_infobulle_contact({
                    "i_bot": ib, "i_top": it, "frac": frac, "F_c": fc}))
                tip.adjustSize()
                self.canvas.rafraichir_position_infobulle_contact(tip)
                return
        self._masquer_infobulle_contact()


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
        self.setWindowTitle(
            "Tensor Build — Simulateur de Résistance des Matériaux")
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
        self.canvas.set_callback_contact_clic(self.panneau.on_contact_pick)

        if switch_callback:
            self.panneau.btn_switch_3d.clicked.connect(switch_callback)

        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panneau)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _on_changed(self, *, refresh_list=True):
        """Recalcule la physique et redessine ; met à jour la liste si demandé."""
        if refresh_list:
            self.panneau.rafraichir_liste()
        donnees_stress, paires = self._calculer_physique()
        self.canvas.dessiner_contraintes(donnees_stress, paires)
        self.panneau.rafraichir_infobulle_contact(paires, donnees_stress)

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
            self.panneau.afficher_cdgr("Aucun bloc.")
            self.panneau.afficher_rapport_detail("Aucun bloc.")
            self.panneau._masquer_infobulle_contact()
            return [], []

        aire_totale, XG, YG, Ixx, Iyy, masse = _statistiques_globales_section(
            blocs)

        entete = [
            "<b style='color:#1565c0'>══ Section globale ══</b>",
            f"Aire totale : <b>{aire_totale:.4f} m²</b>",
            f"CG (section) : <b>({XG:.3f}, {YG:.3f}) m</b>",
            f"Ixx (global) : <b>{Ixx:.4f} m⁴</b>",
            f"Iyy (global) : <b>{Iyy:.4f} m⁴</b>",
            f"Masse linéique : <b>{masse:.1f} kg/m</b>",
            "",
        ]

        paires = _contact_pairs(blocs)
        donnees_stress = []
        resumes = []
        lignes_detail = []

        for i, bloc in enumerate(blocs):
            _, _, w, h = _geom_patch(bloc)
            aire = w * h
            mat = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])

            poids = bloc["density"] * aire * GRAVITY
            F_ext = bloc["ext_force"]
            F_pression = bloc["pressure"] * w

            F_contact = sum(
                _charge_verticale_equivalente(blocs[j])
                for (i_bas, j, _) in paires if i_bas == i
            )

            F_axial = poids + F_ext + F_pression + F_contact
            sigma_axial = F_axial / aire

            M = bloc["moment"]
            I_local = (w * h**3) / 12
            sig_haut = M * (h / 2) / I_local if I_local > 0 else 0
            sig_bas = M * (-h / 2) / I_local if I_local > 0 else 0
            sigma_max = max(
                abs(sigma_axial + sig_haut), abs(sigma_axial + sig_bas))

            sigma_y = mat["sigma_y"]
            taux = sigma_max / sigma_y * 100
            statut, sym = _statut_utilisation(taux)

            resumes.append(
                f"  Bloc <b>{i + 1}</b> ({bloc['material']}) : "
                f"σ = <b>{sigma_max/1e6:.2f} MPa</b>, "
                f"<b>{taux:.0f}%</b> {sym}")

            lignes_detail += [
                f"<b style='color:#e65100'>── Bloc {i+1} ({bloc['material']}) ──</b>",
                f"  Poids propre   : {poids:.1f} N",
                f"  Charge contact : {F_contact:.1f} N",
                f"  Force ext.     : {F_ext:.1f} N",
                f"  Pression       : {F_pression:.1f} N",
                f"  <b>F axiale total : {F_axial:.1f} N</b>",
                f"  σ axiale       : {sigma_axial/1e6:.3f} MPa",
            ]
            if abs(M) > 0:
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

        lignes_contact = []
        if paires:
            lignes_contact.append(
                "<b style='color:#ff6f00'>══ Contacts détectés ══</b>")
            for (ib, ih, frac) in paires:
                fc = donnees_stress[ih]["F_axial"]
                lignes_contact.append(
                    f"  Bloc {ih+1} (sup.) → Bloc {ib+1} (inf.) : "
                    f"<b>{fc:.0f} N</b> — recouvrement "
                    f"<b>{frac*100:.0f}%</b> de la largeur du plus petit bloc")
            lignes_contact.append("")

        rapport = (
            entete
            + [
                "<b style='color:#2e7d32'>══ Contraintes sur les blocs ══</b>",
                "<span style='color:#666;font-size:9px'>"
                "Résumé σ / utilisation.</span>",
            ]
            + resumes
            + ["", "<b style='color:#1565c0'>══ Détail par bloc ══</b>", ""]
            + lignes_detail
            + lignes_contact
        )

        self.panneau.afficher_rapport_detail("<br>".join(rapport))
        self.panneau.afficher_cdgr(
            "<div style='padding:4px;'>"
            "<b style='color:#f9a825'>⊕ Centre de gravité</b><br><br>"
            "<span style='color:#555'>Position (x, y) en mètres<br>"
            f"<b style='color:#e65100;font-size:13px'>({XG:.2f}, {YG:.2f})</b>"
            "</div>"
        )
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
