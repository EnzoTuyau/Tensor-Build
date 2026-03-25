import sys
import functools
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyArrowPatch
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QDoubleSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QFormLayout, QGroupBox, QFrame, QScrollArea, QTabWidget,
    QComboBox, QCheckBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QGuiApplication
# ─────────────────────────────────────────────
GRAVITY = 9.81
GROUND_Y = 0.0
SNAP_TOL = 0.18   # tolérance de contact (m)
FALL_STEP = 0.12   # pas de chute par tick (m)
TIMER_MS = 30     # ms entre chaque tick de physique

# Matériaux 2D : densité, module E, limite σ, couleurs du patch (face / contour).
MATERIALS = {
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
}


def _overlaps_x(rd_a, rd_b):
    ax, _ = rd_a["patch"].get_xy()
    aw = rd_a["patch"].get_width()
    bx, _ = rd_b["patch"].get_xy()
    bw = rd_b["patch"].get_width()
    return ax < bx + bw and bx < ax + aw


def _contact_pairs(rects, tol=SNAP_TOL):
    """[(i_bottom, i_top, overlap_frac), ...]"""
    pairs = []
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i == j:
                continue
            xb, yb = rects[i]["patch"].get_xy()
            wb, hb = rects[i]["patch"].get_width(
            ), rects[i]["patch"].get_height()
            xt, yt = rects[j]["patch"].get_xy()
            wt = rects[j]["patch"].get_width()
            if abs((yb + hb) - yt) <= tol and _overlaps_x(rects[i], rects[j]):
                overlap = min(xb + wb, xt + wt) - max(xb, xt)
                frac = overlap / min(wb, wt)
                pairs.append((i, j, frac))
    return pairs


def _resolve_collision(moving_idx, rects):
    """
    Pousse le bloc moving_idx vers le haut s'il chevauche un autre bloc.
    Retourne True si une collision a été résolue.
    """
    rd_m = rects[moving_idx]
    pm = rd_m["patch"]
    mx, my = pm.get_xy()
    mw, mh = pm.get_width(), pm.get_height()
    collided = False

    for i, rd_o in enumerate(rects):
        if i == moving_idx:
            continue
        po = rd_o["patch"]
        ox, oy = po.get_xy()
        ow, oh = po.get_width(), po.get_height()

        # AABB overlap check
        x_overlap = mx < ox + ow and ox < mx + mw
        y_overlap = my < oy + oh and oy < my + mh

        if x_overlap and y_overlap:
            # Détermine la profondeur de pénétration sur chaque axe
            pen_top = (oy + oh) - my        # moving monte sur other
            pen_bottom = (my + mh) - oy        # moving descend sous other
            pen_right = (ox + ow) - mx
            pen_left = (mx + mw) - ox

            # Résolution : axe de moindre pénétration (vertical prioritaire)
            min_pen = min(pen_top, pen_bottom, pen_right, pen_left)

            if min_pen == pen_top:
                # Poser le bloc au-dessus de l'autre
                pm.set_xy((mx, oy + oh))
            elif min_pen == pen_bottom:
                pm.set_xy((mx, oy - mh))
            elif min_pen == pen_right:
                pm.set_xy((ox + ow, my))
            else:
                pm.set_xy((ox - mw, my))

            mx, my = pm.get_xy()  # mise à jour après résolution
            collided = True

    return collided


# ─────────────────────────────────────────────
#  Infobulle contact (fenêtre type tooltip + ×, déplaçable)
# ─────────────────────────────────────────────
class ContactTooltip(QWidget):
    def __init__(self, parent=None):
        # Fenêtre normale (pas Popup / pas seulement Tool) : sur macOS les Tool
        # sans parent peuvent ne pas s’afficher ; Popup se ferme au clic canvas.
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
        """Rectangle global des axes : l’infobulle ne sort pas de ce plan."""
        self._bounds = QRect(rect)

    def _clamp_top_left(self, top_left: QPoint) -> QPoint:
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
        self.move(self._clamp_top_left(self.pos()))

    def set_rich_text(self, html):
        self._lbl.setText(html)


# ─────────────────────────────────────────────
#  Canvas 2D
# ─────────────────────────────────────────────
class Canvas2D(FigureCanvasQTAgg):
    def __init__(self, parent=None, on_rects_changed=None):
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
        for spine in self.axes.spines.values():
            spine.set_edgecolor("#cccccc")
        super().__init__(fig)

        self.rects = []
        self._drag_index = None
        self._drag_offset = None
        self._on_rects_changed = on_rects_changed
        self.gravity_on = False

        self._stress_patches = []
        self._arrow_artists = []
        self._cg_artist = None
        self._ground_patch = None
        self._ground_line = None
        self._contact_hit_zones = []
        self._on_contact_clicked = None

        # Timer de physique
        self._timer = QTimer()
        self._timer.setInterval(TIMER_MS)
        self._timer.timeout.connect(self._physics_tick)

        self._draw_ground()
        self.mpl_connect("button_press_event",   self._on_press)
        self.mpl_connect("motion_notify_event",  self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    def set_on_contact_clicked(self, callback):
        """callback(dict) — dict : i_bot, i_top, frac, F_c, cx, y_if ; None pour désactiver."""
        self._on_contact_clicked = callback

    def _data_to_global(self, xd, yd):
        """Point données (m) → coordonnées globales écran du canvas."""
        fig = self.figure
        disp = self.axes.transData.transform((xd, yd))
        x_disp, y_disp = float(disp[0]), float(disp[1])
        h = float(fig.bbox.height)
        x_qt = int(round(x_disp))
        y_qt = int(round(h - y_disp))
        return self.mapToGlobal(QPoint(x_qt, y_qt))

    def _mpl_press_to_global(self, event):
        """Clic matplotlib (pixels figure, origine bas-gauche) → global Qt."""
        try:
            x, y = float(event.x), float(event.y)
        except (TypeError, ValueError):
            return None
        h = float(self.figure.bbox.height)
        if h < 1:
            return None
        return self.mapToGlobal(
            QPoint(int(round(x)), int(round(h - y))))

    def ground_global_rect(self):
        """Rectangle écran (global) couvrant le sol dessiné (approx. boîte englobante)."""
        xmin, xmax = self.axes.get_xlim()
        y_lo = GROUND_Y - 0.52
        y_hi = GROUND_Y + 0.02
        pts = [
            self._data_to_global(xmin, y_lo),
            self._data_to_global(xmax, y_lo),
            self._data_to_global(xmax, y_hi),
            self._data_to_global(xmin, y_hi),
        ]
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        return QRect(
            min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def axes_global_rect(self):
        """Rectangle global du plan de dessin (zone des axes matplotlib)."""
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

    def contact_point_global(self, hit_c):
        """Centre du joint (contact) en coordonnées globales écran."""
        return self._data_to_global(hit_c["cx"], hit_c["y_if"])

    def refine_contact_tooltip_position(self, tip):
        """Recadre l’infobulle dans le plan de dessin (utile après resize / refresh)."""
        tip.set_plot_bounds_global(self.axes_global_rect())
        tip.clamp_to_bounds()

    # ── Sol ──────────────────────────────────
    def _draw_ground(self):
        xmin, xmax = self.axes.get_xlim()
        if self._ground_patch:
            self._ground_patch.remove()
        if self._ground_line:
            self._ground_line.remove()
        self._ground_patch = Rectangle(
            (xmin, GROUND_Y - 0.5), xmax - xmin, 0.5,
            facecolor="#e8f5e9", edgecolor="#388e3c",
            linewidth=2, hatch="////", zorder=0
        )
        self.axes.add_patch(self._ground_patch)
        self._ground_line, = self.axes.plot(
            [xmin, xmax], [GROUND_Y, GROUND_Y],
            color="#388e3c", linewidth=2.5, zorder=1
        )

    # ── Gravité ──────────────────────────────
    def set_gravity(self, enabled):
        self.gravity_on = enabled
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def _physics_tick(self):
        """Fait tomber chaque bloc d'un pas, résout les collisions."""
        if not self.rects:
            return
        moved = False
        # On trie par hauteur croissante pour traiter les blocs du bas en premier
        order = sorted(range(len(self.rects)),
                       key=lambda i: self.rects[i]["patch"].get_xy()[1])
        for idx in order:
            if idx == self._drag_index:
                continue  # on ne bouge pas le bloc en cours de drag
            rd = self.rects[idx]
            patch = rd["patch"]
            x, y = patch.get_xy()
            h = patch.get_height()

            # Calcul du sol effectif pour ce bloc :
            # c'est le max du sol et du sommet de tout bloc en dessous
            floor_y = GROUND_Y
            for i2, rd2 in enumerate(self.rects):
                if i2 == idx:
                    continue
                x2, y2 = rd2["patch"].get_xy()
                w2, h2 = rd2["patch"].get_width(), rd2["patch"].get_height()
                x_me, _ = patch.get_xy()
                w_me = patch.get_width()
                # chevauchement horizontal ?
                if x_me < x2 + w2 and x2 < x_me + w_me:
                    top2 = y2 + h2
                    if top2 <= y + 0.001:          # bloc2 est en dessous
                        floor_y = max(floor_y, top2)

            if y > floor_y + 0.001:
                new_y = max(floor_y, y - FALL_STEP)
                patch.set_xy((x, new_y))
                moved = True

        if moved:
            self.draw_idle()
            if self._on_rects_changed:
                self._on_rects_changed()

    # ── Blocs ────────────────────────────────
    def add_rectangle(self, w, h, material="Acier", density=None):
        mp = MATERIALS.get(material, MATERIALS["Acier"])
        if density is None:
            density = mp["density"]
        fc, ec = mp["face"], mp["edge"]
        # Spawn en haut au centre si gravité active, sinon au-dessus de la pile
        if self.gravity_on:
            y_start = 9.0
            x_start = 1.0
        else:
            y_start = GROUND_Y
            if self.rects:
                tops = [r["patch"].get_xy()[1] + r["patch"].get_height()
                        for r in self.rects]
                y_start = max(tops)
            x_start = 0.5
        patch = Rectangle(
            (x_start, y_start), w, h,
            facecolor=fc, edgecolor=ec,
            linewidth=1.8, zorder=5, alpha=0.9
        )
        self.axes.add_patch(patch)
        self.rects.append({
            "patch":     patch,
            "material":  material,
            "density":   density,
            "edgecolor": ec,
            "ext_force": 0.0,
            "moment":    0.0,
            "pressure":  0.0,
        })
        self._notify()

    def remove_rectangle(self, index):
        if 0 <= index < len(self.rects):
            self.rects[index]["patch"].remove()
            self.rects.pop(index)
            self._notify()

    # ── Drag ─────────────────────────────────
    def _hit_test_contact(self, event):
        if event.xdata is None or event.ydata is None:
            return None
        xd, yd = event.xdata, event.ydata
        for z in reversed(self._contact_hit_zones):
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

    def _hit_test(self, event):
        for i, rd in enumerate(reversed(self.rects)):
            idx = len(self.rects) - 1 - i
            xy = rd["patch"].get_xy()
            w, h = rd["patch"].get_width(), rd["patch"].get_height()
            if (event.xdata is not None and event.ydata is not None and
                    xy[0] <= event.xdata <= xy[0] + w and
                    xy[1] <= event.ydata <= xy[1] + h):
                return idx
        return None

    def _on_press(self, event):
        if event.inaxes != self.axes or event.button != 1:
            return
        hit_c = self._hit_test_contact(event)
        if hit_c is not None and self._on_contact_clicked:
            pg = self._mpl_press_to_global(event)
            if pg is not None:
                hit_c["_press_global"] = pg
            self._on_contact_clicked(hit_c)
            return
        idx = self._hit_test(event)
        if idx is not None:
            self._drag_index = idx
            xy = self.rects[idx]["patch"].get_xy()
            self._drag_offset = (event.xdata - xy[0], event.ydata - xy[1])

    def _on_motion(self, event):
        if self._drag_index is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return
        rd = self.rects[self._drag_index]
        patch = rd["patch"]
        xmin, xmax = self.axes.get_xlim()
        _, ymax_ax = self.axes.get_ylim()
        w, h = patch.get_width(), patch.get_height()
        x = max(xmin,     min(
            xmax - w,     event.xdata - self._drag_offset[0]))
        y = max(GROUND_Y, min(ymax_ax - h,
                event.ydata - self._drag_offset[1]))
        patch.set_xy((x, y))

        # Résolution de collision pendant le drag
        _resolve_collision(self._drag_index, self.rects)

        self.draw_idle()
        self._notify()

    def _on_release(self, event):
        self._drag_index = None
        self._drag_offset = None

    def _notify(self):
        if self._on_rects_changed:
            self._on_rects_changed()

    # ── Dessin stress + contacts ──────────────
    def draw_stress(self, stress_data, contact_pairs):
        for p in self._stress_patches:
            try:
                p.remove()
            except Exception:
                pass
        self._stress_patches.clear()
        for a in self._arrow_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._arrow_artists.clear()
        if self._cg_artist:
            for a in self._cg_artist:
                try:
                    a.remove()
                except Exception:
                    pass
            self._cg_artist = None

        self._contact_hit_zones.clear()

        if not self.rects or not stress_data:
            self.draw_idle()
            return

        # ── Blocs : teinte matériau fixe (pas de colormap σ sur le dessin)
        for i, (rd, sd) in enumerate(zip(self.rects, stress_data)):
            if sd is None:
                continue
            patch = rd["patch"]
            x, y = patch.get_xy()
            w, h = patch.get_width(), patch.get_height()

            mat = rd["material"]
            fc = MATERIALS.get(mat, MATERIALS["Acier"])["face"]
            if abs(sd.get("sigma_bending_top", 0)) > 1:
                for dy in (0, h / 2):
                    r = Rectangle(
                        (x, y + dy), w, h / 2,
                        facecolor=fc, edgecolor="none", alpha=0.96, zorder=6)
                    self.axes.add_patch(r)
                    self._stress_patches.append(r)
            else:
                r = Rectangle(
                    (x, y), w, h,
                    facecolor=fc, edgecolor="none", alpha=0.96, zorder=6)
                self.axes.add_patch(r)
                self._stress_patches.append(r)

            ec = rd.get("edgecolor") or MATERIALS.get(
                rd["material"], MATERIALS["Acier"])["edge"]
            border = Rectangle((x, y), w, h,
                               facecolor="none", edgecolor=ec,
                               linewidth=1.5, zorder=7)
            self.axes.add_patch(border)
            self._stress_patches.append(border)

            # Assombrissement au contact avec le sol
            if abs(y - GROUND_Y) < SNAP_TOL * 2.0:
                sh = min(0.09, max(0.04, h * 0.22))
                sol_sh = Rectangle(
                    (x, y), w, sh,
                    facecolor="#000000", edgecolor="none", alpha=0.34,
                    zorder=8)
                self.axes.add_patch(sol_sh)
                self._stress_patches.append(sol_sh)

            # σ / utilisation : uniquement dans l’onglet « Résultats »

            if abs(sd.get("ext_force", 0)) > 0:
                cx = x + w/2
                arr = FancyArrowPatch(
                    (cx, y + h + 0.7), (cx, y + h + 0.05),
                    arrowstyle="-|>", mutation_scale=16,
                    color="#d32f2f", linewidth=2.5, zorder=11
                )
                self.axes.add_patch(arr)
                self._arrow_artists.append(arr)
                lbl = self.axes.text(
                    cx, y + h + 0.8, f"F={sd['ext_force']:.0f} N",
                    ha="center", va="bottom", fontsize=7.5,
                    color="#d32f2f", fontweight="bold", zorder=11
                )
                self._arrow_artists.append(lbl)

            if abs(sd.get("pressure", 0)) > 0:
                n = max(3, int(w * 2))
                for k in range(n):
                    ax_x = x + (k + 0.5) * w / n
                    arr = FancyArrowPatch(
                        (ax_x, y + h + 0.35), (ax_x, y + h + 0.02),
                        arrowstyle="-|>", mutation_scale=9,
                        color="#e65100", linewidth=1.2, zorder=11
                    )
                    self.axes.add_patch(arr)
                    self._arrow_artists.append(arr)

        # ── Contacts : bande sombre + noircissement local au joint
        # Clic sur la bande : infobulle (× pour fermer).

        def _y_interface(pair):
            i_bot, _, _ = pair
            xb, yb = self.rects[i_bot]["patch"].get_xy()
            return yb + self.rects[i_bot]["patch"].get_height()

        sorted_pairs = sorted(contact_pairs, key=_y_interface)

        for (i_bot, i_top, frac) in sorted_pairs:
            rd_b = self.rects[i_bot]
            rd_t = self.rects[i_top]
            xb, yb = rd_b["patch"].get_xy()
            wb, hb = rd_b["patch"].get_width(), rd_b["patch"].get_height()
            xt, yt = rd_t["patch"].get_xy()
            wt, ht = rd_t["patch"].get_width(), rd_t["patch"].get_height()
            y_if = yb + hb

            x_l = max(xb, xt)
            x_r = min(xb + wb, xt + wt)
            if x_r <= x_l:
                continue

            shade_d = min(0.08, hb * 0.38, ht * 0.38)
            y_bot0 = max(yb, y_if - shade_d)
            h_bot = y_if - y_bot0
            if h_bot > 1e-4:
                sb = Rectangle(
                    (x_l, y_bot0), x_r - x_l, h_bot,
                    facecolor="#000000", edgecolor="none", alpha=0.36,
                    zorder=9)
                self.axes.add_patch(sb)
                self._stress_patches.append(sb)
            y_top1 = min(yt + ht, y_if + shade_d)
            h_top = y_top1 - y_if
            if h_top > 1e-4:
                st = Rectangle(
                    (x_l, y_if), x_r - x_l, h_top,
                    facecolor="#000000", edgecolor="none", alpha=0.36,
                    zorder=9)
                self.axes.add_patch(st)
                self._stress_patches.append(st)

            cr = Rectangle(
                (x_l, y_if - 0.05), x_r - x_l, 0.10,
                facecolor="#1a1a1a", edgecolor="none", alpha=0.88, zorder=12
            )
            self.axes.add_patch(cr)
            self._stress_patches.append(cr)

            sd_top = (
                stress_data[i_top] if i_top < len(stress_data) else None)
            F_c = float(sd_top["F_axial"]) if sd_top else 0.0
            cx = (x_l + x_r) / 2

            # Zone cliquable (légèrement élargie pour faciliter le viser)
            pad_x, pad_y = 0.04, 0.05
            self._contact_hit_zones.append({
                "x0": x_l - pad_x,
                "x1": x_r + pad_x,
                "y0": y_if - 0.05 - pad_y,
                "y1": y_if + 0.05 + pad_y,
                "i_bot": i_bot,
                "i_top": i_top,
                "frac":  frac,
                "F_c":   F_c,
                "cx":    cx,
                "y_if":  y_if,
            })

            arr_d = FancyArrowPatch(
                (cx - 0.12, y_if + 0.55), (cx - 0.12, y_if + 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#d32f2f", linewidth=2.5, zorder=13
            )
            self.axes.add_patch(arr_d)
            self._arrow_artists.append(arr_d)

            arr_u = FancyArrowPatch(
                (cx + 0.12, y_if - 0.55), (cx + 0.12, y_if - 0.06),
                arrowstyle="-|>", mutation_scale=18,
                color="#1565c0", linewidth=2.5, zorder=13
            )
            self.axes.add_patch(arr_u)
            self._arrow_artists.append(arr_u)

        # ── Centre de gravité (boule jaune) ──
        total_area = sum(rd["patch"].get_width() *
                         rd["patch"].get_height() for rd in self.rects)
        if total_area > 0:
            xg = sum((rd["patch"].get_xy()[0] + rd["patch"].get_width()/2) *
                     rd["patch"].get_width() * rd["patch"].get_height() for rd in self.rects) / total_area
            yg = sum((rd["patch"].get_xy()[1] + rd["patch"].get_height()/2) *
                     rd["patch"].get_width() * rd["patch"].get_height() for rd in self.rects) / total_area

            # Axes d'inertie (traits pointillés jaunes)
            hl = self.axes.axhline(yg, color="#f9a825",
                                   lw=0.9, ls="--", zorder=15, alpha=0.6)
            vl = self.axes.axvline(xg, color="#f9a825",
                                   lw=0.9, ls="--", zorder=15, alpha=0.6)

            # Boule jaune = Centre de Gravité (coordonnées dans le panneau « Centre de gravité »)
            dot, = self.axes.plot(xg, yg, "o", color="#f9a825", markersize=13,
                                  zorder=16, markeredgecolor="#e65100", markeredgewidth=2)
            self._cg_artist = [dot, hl, vl]

        self.draw_idle()


def _block_list_row(panel, index: int, text: str) -> QWidget:
    """Une ligne : libellé + × qui supprime l’entrée « index »."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(2, 2, 2, 2)
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    btn = QPushButton("×")
    btn.setFixedSize(22, 22)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Supprimer ce bloc")
    btn.clicked.connect(functools.partial(panel._on_remove_at, index))
    h.addWidget(lbl, stretch=1)
    h.addWidget(btn)

    def _press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            panel.list_widget.setCurrentRow(index)
        QWidget.mousePressEvent(w, event)

    w.mousePressEvent = _press
    return w


# ─────────────────────────────────────────────
#  Panneau de contrôle
# ─────────────────────────────────────────────
class ControlPanel(QFrame):
    MATERIALS = MATERIALS

    def __init__(self, canvas, physics_callback, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.physics_callback = physics_callback
        self._selected_rect = None
        self._contact_sel = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Gravité toggle ───────────────────
        grp_grav = QGroupBox("Simulation physique")
        lay_grav = QVBoxLayout(grp_grav)
        self.chk_gravity = QCheckBox("Gravité")
        self.chk_gravity.setStyleSheet("font-weight:bold; font-size:11px;")
        self.chk_gravity.toggled.connect(self._on_gravity_toggle)
        lay_grav.addWidget(self.chk_gravity)
        grp_grav.setLayout(lay_grav)
        layout.addWidget(grp_grav)

        self._contact_tooltip = None

        lbl_hint = QLabel(
            "<span style='color:#888;font-size:8px'>"
            "Cliquez sur une surface de contact pour afficher les détails."
        )
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        tabs = QTabWidget()

        # ── Blocs ────────────────────────────
        tab_b = QWidget()
        lay_b = QVBoxLayout(tab_b)

        grp1 = QGroupBox("Nouveau bloc")
        form1 = QFormLayout()
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(0.1, 20)
        self.spin_w.setValue(2)
        self.spin_w.setSingleStep(0.25)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(0.1, 20)
        self.spin_h.setValue(1)
        self.spin_h.setSingleStep(0.25)
        self.combo_mat = QComboBox()
        for m in self.MATERIALS:
            self.combo_mat.addItem(m)
        form1.addRow("Largeur (m):", self.spin_w)
        form1.addRow("Hauteur (m):", self.spin_h)
        form1.addRow("Matériau:",    self.combo_mat)
        grp1.setLayout(form1)
        lay_b.addWidget(grp1)

        btn_add = QPushButton("➕  Ajouter bloc")
        btn_add.clicked.connect(self._on_add)
        lay_b.addWidget(btn_add)

        grp2 = QGroupBox("Blocs présents")
        lay_b2 = QVBoxLayout(grp2)
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(180)
        self.list_widget.currentRowChanged.connect(self._on_select)
        lay_b2.addWidget(self.list_widget)
        grp2.setLayout(lay_b2)
        lay_b.addWidget(grp2)
        lay_b.addStretch()
        tabs.addTab(tab_b, "Blocs")

        # ── Charges ──────────────────────────
        tab_l = QWidget()
        lay_l = QVBoxLayout(tab_l)
        grp_l = QGroupBox("Charges — bloc sélectionné")
        form_l = QFormLayout()
        self.spin_force = QDoubleSpinBox()
        self.spin_force.setRange(0, 1e7)
        self.spin_force.setSuffix(" N")
        self.spin_force.setSingleStep(100)
        self.spin_pressure = QDoubleSpinBox()
        self.spin_pressure.setRange(0, 1e6)
        self.spin_pressure.setSuffix(" Pa")
        self.spin_pressure.setSingleStep(500)
        self.spin_moment = QDoubleSpinBox()
        self.spin_moment.setRange(-1e6, 1e6)
        self.spin_moment.setSuffix(" N·m")
        self.spin_moment.setSingleStep(100)
        form_l.addRow("Force ponctuelle:",  self.spin_force)
        form_l.addRow("Pression dist.:",    self.spin_pressure)
        form_l.addRow("Moment fléch.:",     self.spin_moment)
        grp_l.setLayout(form_l)
        lay_l.addWidget(grp_l)
        btn_apply = QPushButton("✅  Appliquer charges")
        btn_apply.clicked.connect(self._on_apply_loads)
        lay_l.addWidget(btn_apply)
        lay_l.addStretch()
        tabs.addTab(tab_l, "Charges")

        # ── Résultats : CdG + détail physique & contacts (uniquement dans cet onglet)
        tab_phys = QWidget()
        lay_phys = QVBoxLayout(tab_phys)
        lay_phys.setContentsMargins(4, 4, 4, 4)
        lay_phys.setSpacing(8)

        grp_cg = QGroupBox("Centre de gravité")
        lay_cg = QVBoxLayout(grp_cg)
        self.lbl_results = QLabel(
            "<i style='color:#888'>Ajoutez des blocs pour afficher le CdG.</i>")
        self.lbl_results.setWordWrap(True)
        self.lbl_results.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_results.setStyleSheet(
            "font-family: Consolas; font-size: 9px; color: #222;")
        scroll_cg = QScrollArea()
        scroll_cg.setWidget(self.lbl_results)
        scroll_cg.setWidgetResizable(True)
        scroll_cg.setMaximumHeight(140)
        lay_cg.addWidget(scroll_cg)
        grp_cg.setLayout(lay_cg)
        lay_phys.addWidget(grp_cg)

        grp_detail = QGroupBox("Détail physique & contacts")
        lay_detail = QVBoxLayout(grp_detail)
        self.lbl_physics_report = QLabel(
            "<i style='color:#888'>Ajoutez des blocs pour afficher le détail.</i>")
        self.lbl_physics_report.setWordWrap(True)
        self.lbl_physics_report.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_physics_report.setStyleSheet(
            "font-family: Consolas; font-size: 9px; color: #222;")
        scroll_phys = QScrollArea()
        scroll_phys.setWidget(self.lbl_physics_report)
        scroll_phys.setWidgetResizable(True)
        scroll_phys.setMinimumHeight(200)
        lay_detail.addWidget(scroll_phys)
        grp_detail.setLayout(lay_detail)
        lay_phys.addWidget(grp_detail, stretch=1)

        tabs.addTab(tab_phys, "Résultats")

        layout.addWidget(tabs)

        self.setStyleSheet("""
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
            QCheckBox     { color:#1565c0; }
        """)

    def _on_gravity_toggle(self, checked):
        self.canvas.set_gravity(checked)

    def _on_add(self):
        mn = self.combo_mat.currentText()
        self.canvas.add_rectangle(
            self.spin_w.value(), self.spin_h.value(), material=mn)

    def _on_remove_at(self, idx):
        if 0 <= idx < len(self.canvas.rects):
            self.canvas.remove_rectangle(idx)

    def _on_select(self, row):
        self._selected_rect = row
        if 0 <= row < len(self.canvas.rects):
            rd = self.canvas.rects[row]
            self.spin_force.setValue(rd["ext_force"])
            self.spin_pressure.setValue(rd["pressure"])
            self.spin_moment.setValue(rd["moment"])

    def _on_apply_loads(self):
        row = self._selected_rect
        if row is not None and 0 <= row < len(self.canvas.rects):
            rd = self.canvas.rects[row]
            rd["ext_force"] = self.spin_force.value()
            rd["pressure"] = self.spin_pressure.value()
            rd["moment"] = self.spin_moment.value()
            self.physics_callback()

    def refresh_list(self):
        self.list_widget.clear()
        for i, rd in enumerate(self.canvas.rects):
            p = rd["patch"]
            text = (
                f"[{i+1}] {rd['material']}  "
                f"{p.get_width():.1f}×{p.get_height():.1f} m")
            row = _block_list_row(self, i, text)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    def update_results(self, html):
        self.lbl_results.setText(html)

    def update_physics_report(self, html):
        self.lbl_physics_report.setText(html)

    def _ensure_contact_tooltip(self):
        if self._contact_tooltip is None:
            # Parent = canvas : ancrage WM correct sur macOS ; move() reste global.
            self._contact_tooltip = ContactTooltip(self.canvas)
        return self._contact_tooltip

    def _contact_tooltip_html(self, d):
        ib, it = d["i_bot"], d["i_top"]
        frac, Fc = d["frac"], d["F_c"]
        return (
            "<b style='color:#bf360c'>Surface de contact</b><br>"
            f"Bloc supérieur <b>{it + 1}</b> → bloc inférieur <b>{ib + 1}</b><br>"
            f"Effort transmis <b>Fc = {Fc:.0f} N</b><br>"
            f"Recouvrement : <b>{frac * 100:.0f} %</b> "
        )

    def _place_contact_tooltip(self, tip, contact_center_global: QPoint):
        """Quelques pixels au-dessus du centre du contact ; reste dans _bounds (plan)."""
        tip.adjustSize()
        gap_px = 6
        w, h = tip.width(), tip.height()
        x = contact_center_global.x() - w // 2
        y = contact_center_global.y() - h - gap_px
        tip.move(tip._clamp_top_left(QPoint(x, y)))

    def on_contact_pick(self, d):
        self._contact_sel = (d["i_bot"], d["i_top"])
        tip = self._ensure_contact_tooltip()

        def _open():
            tip.set_plot_bounds_global(self.canvas.axes_global_rect())
            tip.set_rich_text(self._contact_tooltip_html(d))
            pt = d.get("_press_global")
            if pt is None:
                pt = self.canvas.contact_point_global(d)
            self._place_contact_tooltip(tip, pt)
            tip.setWindowOpacity(1.0)
            tip.show()
            tip.raise_()
            self.canvas.refine_contact_tooltip_position(tip)
            # Si le centre est hors de tout écran (coords incorrectes), ramener visible.
            c = tip.frameGeometry().center()
            if QGuiApplication.screenAt(c) is None:
                ps = QGuiApplication.primaryScreen()
                if ps is not None:
                    fr = tip.frameGeometry()
                    fr.moveCenter(ps.availableGeometry().center())
                    tip.move(fr.topLeft())
            QApplication.processEvents()

        # Après le relâchement du clic sur le canvas (évite fermeture Popup).
        QTimer.singleShot(10, _open)

    def _hide_contact_popup(self):
        if self._contact_tooltip is not None:
            self._contact_tooltip.hide()
        self._contact_sel = None

    def refresh_contact_popup_if_open(self, pairs, stress_data):
        tip = self._contact_tooltip
        if tip is None or not tip.isVisible() or self._contact_sel is None:
            return
        ib, it = self._contact_sel
        for p in pairs:
            if p[0] == ib and p[1] == it:
                frac = p[2]
                sd = stress_data[it] if it < len(stress_data) else None
                if sd is None:
                    self._hide_contact_popup()
                    return
                Fc = sd["F_axial"]
                tip.set_rich_text(self._contact_tooltip_html({
                    "i_bot": ib, "i_top": it, "frac": frac, "F_c": Fc}))
                tip.adjustSize()
                self.canvas.refine_contact_tooltip_position(tip)
                return
        self._hide_contact_popup()


# ─────────────────────────────────────────────
#  Application principale
# ─────────────────────────────────────────────
class MaterialSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.canvas = Canvas2D(central, on_rects_changed=self._on_changed)
        ml.addWidget(self.canvas, stretch=1)

        self.panel = ControlPanel(self.canvas, self._on_changed)
        self.canvas.set_on_contact_clicked(self.panel.on_contact_pick)
        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panel)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _on_changed(self):
        self.panel.refresh_list()
        stress_data, pairs = self._calculate_physics()
        self.canvas.draw_stress(stress_data, pairs)
        self.panel.refresh_contact_popup_if_open(pairs, stress_data)

    def _calculate_physics(self):
        rects = self.canvas.rects
        if not rects:
            self.panel.update_results("Aucun bloc.")
            self.panel.update_physics_report("Aucun bloc.")
            self.panel._hide_contact_popup()
            return [], []

        MAT = ControlPanel.MATERIALS
        lines = []

        total_area = sum(rd["patch"].get_width() *
                         rd["patch"].get_height() for rd in rects)
        XG = sum((rd["patch"].get_xy()[0] + rd["patch"].get_width()/2) *
                 rd["patch"].get_width() * rd["patch"].get_height() for rd in rects) / total_area
        YG = sum((rd["patch"].get_xy()[1] + rd["patch"].get_height()/2) *
                 rd["patch"].get_width() * rd["patch"].get_height() for rd in rects) / total_area
        Ixx = sum(
            (rd["patch"].get_width() * rd["patch"].get_height()**3) / 12 +
            rd["patch"].get_width() * rd["patch"].get_height() *
            (rd["patch"].get_xy()[1] + rd["patch"].get_height()/2 - YG)**2
            for rd in rects
        )
        Iyy = sum(
            (rd["patch"].get_height() * rd["patch"].get_width()**3) / 12 +
            rd["patch"].get_width() * rd["patch"].get_height() *
            (rd["patch"].get_xy()[0] + rd["patch"].get_width()/2 - XG)**2
            for rd in rects
        )
        masse = sum(rd["density"] * rd["patch"].get_width() *
                    rd["patch"].get_height() for rd in rects)

        head = [
            "<b style='color:#1565c0'>══ Section globale ══</b>",
            f"Aire totale : <b>{total_area:.4f} m²</b>",
            f"CG (section) : <b>({XG:.3f}, {YG:.3f}) m</b>",
            f"Ixx (global) : <b>{Ixx:.4f} m⁴</b>",
            f"Iyy (global) : <b>{Iyy:.4f} m⁴</b>",
            f"Masse linéique : <b>{masse:.1f} kg/m</b>",
            "",
        ]

        pairs = _contact_pairs(rects)

        stress_data = []
        summaries = []
        detail_lines = []
        for i, rd in enumerate(rects):
            patch = rd["patch"]
            w, h = patch.get_width(), patch.get_height()
            area = w * h
            mat = MAT.get(rd["material"], MAT["Acier"])

            weight = rd["density"] * area * GRAVITY
            F_ext = rd["ext_force"]
            F_pressure = rd["pressure"] * w

            F_contact = sum(
                rects[j]["density"] * rects[j]["patch"].get_width() *
                rects[j]["patch"].get_height() * GRAVITY +
                rects[j]["ext_force"] + rects[j]["pressure"] *
                rects[j]["patch"].get_width()
                for (ib, j, _) in pairs if ib == i
            )

            F_axial = weight + F_ext + F_pressure + F_contact
            sigma_axial = F_axial / area

            M = rd["moment"]
            I_local = (w * h**3) / 12
            sig_bt = M * (h/2) / I_local if I_local > 0 else 0
            sig_bb = M * (-h/2) / I_local if I_local > 0 else 0
            sig_max = max(abs(sigma_axial + sig_bt), abs(sigma_axial + sig_bb))

            sigma_y = mat["sigma_y"]
            util = sig_max / sigma_y * 100
            status = "OK" if util < 80 else (
                "⚠️ Attention" if util < 100 else "❌ RUPTURE")
            sym = "✓" if util < 80 else ("!" if util < 100 else "✗")

            summaries.append(
                f"  Bloc <b>{i + 1}</b> ({rd['material']}) : "
                f"σ = <b>{sig_max/1e6:.2f} MPa</b>, "
                f"<b>{util:.0f}%</b> {sym}")

            detail_lines += [
                f"<b style='color:#e65100'>── Bloc {i+1} ({rd['material']}) ──</b>",
                f"  Poids propre   : {weight:.1f} N",
                f"  Charge contact : {F_contact:.1f} N",
                f"  Force ext.     : {F_ext:.1f} N",
                f"  Pression       : {F_pressure:.1f} N",
                f"  <b>F axiale total : {F_axial:.1f} N</b>",
                f"  σ axiale       : {sigma_axial/1e6:.3f} MPa",
            ]
            if abs(M) > 0:
                detail_lines += [
                    f"  σ flex haut    : {sig_bt/1e6:.3f} MPa",
                    f"  σ flex bas     : {sig_bb/1e6:.3f} MPa",
                ]
            detail_lines += [
                f"  <b>σ max          : {sig_max/1e6:.3f} MPa</b>",
                f"  σ_y limite     : {sigma_y/1e6:.0f} MPa",
                f"  Utilisation    : {util:.1f}% {status}",
                "",
            ]

            stress_data.append({
                "sigma_total":       sig_max,
                "sigma_axial":       sigma_axial,
                "sigma_bending_top": sig_bt,
                "sigma_bending_bot": sig_bb,
                "ext_force":         F_ext + F_pressure,
                "pressure":          rd["pressure"],
                "utilization":       util,
                "F_axial":           F_axial,
            })

        contact_lines = []
        if pairs:
            contact_lines.append(
                "<b style='color:#ff6f00'>══ Contacts détectés ══</b>")
            for (ib, it, frac) in pairs:
                Fc = stress_data[it]["F_axial"]
                contact_lines.append(
                    f"  Bloc {it+1} (sup.) → Bloc {ib+1} (inf.) : "
                    f"<b>{Fc:.0f} N</b> — recouvrement "
                    f"<b>{frac*100:.0f}%</b> de la largeur du plus petit bloc"
                )
            contact_lines.append("")

        lines = (
            head
            + [
                "<b style='color:#2e7d32'>══ Contraintes sur les blocs ══</b>",
                "<span style='color:#666;font-size:9px'>"
                "Résumé σ / utilisation (affiché auparavant sur le schéma).</span>",
            ]
            + summaries
            + ["", "<b style='color:#1565c0'>══ Détail par bloc ══</b>", ""]
            + detail_lines
            + contact_lines
        )

        self.panel.update_physics_report("<br>".join(lines))

        self.panel.update_results(
            "<div style='padding:4px;'>"
            "<b style='color:#f9a825'>⊕ Centre de gravité</b><br><br>"
            "<span style='color:#555'>Position (x, y) en mètres<br>"
            f"<b style='color:#e65100;font-size:13px'>({XG:.2f}, {YG:.2f})</b>"
            "</div>"
        )
        return stress_data, pairs


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MaterialSimulationApp()
    window.show()
    sys.exit(app.exec())
