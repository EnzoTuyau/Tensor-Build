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

# ─────────────────────────────────────────────
GRAVITY    = 9.81
GROUND_Y   = 0.0
SNAP_TOL   = 0.18   # tolérance de contact (m)
FALL_STEP  = 0.12   # pas de chute par tick (m)
TIMER_MS   = 30     # ms entre chaque tick de physique


def _overlaps_x(rd_a, rd_b):
    ax, _ = rd_a["patch"].get_xy(); aw = rd_a["patch"].get_width()
    bx, _ = rd_b["patch"].get_xy(); bw = rd_b["patch"].get_width()
    return ax < bx + bw and bx < ax + aw


def _contact_pairs(rects, tol=SNAP_TOL):
    """[(i_bottom, i_top, overlap_frac), ...]"""
    pairs = []
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i == j:
                continue
            xb, yb = rects[i]["patch"].get_xy()
            wb, hb = rects[i]["patch"].get_width(), rects[i]["patch"].get_height()
            xt, yt = rects[j]["patch"].get_xy()
            wt     = rects[j]["patch"].get_width()
            if abs((yb + hb) - yt) <= tol and _overlaps_x(rects[i], rects[j]):
                overlap = min(xb + wb, xt + wt) - max(xb, xt)
                frac    = overlap / min(wb, wt)
                pairs.append((i, j, frac))
    return pairs


def _resolve_collision(moving_idx, rects):
    """
    Pousse le bloc moving_idx vers le haut s'il chevauche un autre bloc.
    Retourne True si une collision a été résolue.
    """
    rd_m  = rects[moving_idx]
    pm    = rd_m["patch"]
    mx, my = pm.get_xy()
    mw, mh = pm.get_width(), pm.get_height()
    collided = False

    for i, rd_o in enumerate(rects):
        if i == moving_idx:
            continue
        po    = rd_o["patch"]
        ox, oy = po.get_xy()
        ow, oh = po.get_width(), po.get_height()

        # AABB overlap check
        x_overlap = mx < ox + ow and ox < mx + mw
        y_overlap = my < oy + oh and oy < my + mh

        if x_overlap and y_overlap:
            # Détermine la profondeur de pénétration sur chaque axe
            pen_top    = (oy + oh) - my        # moving monte sur other
            pen_bottom = (my + mh) - oy        # moving descend sous other
            pen_right  = (ox + ow) - mx
            pen_left   = (mx + mw) - ox

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

        self.rects             = []
        self._drag_index       = None
        self._drag_offset      = None
        self._on_rects_changed = on_rects_changed
        self.gravity_on        = False

        self._stress_patches   = []
        self._arrow_artists    = []
        self._cg_artist        = None
        self._ground_patch     = None
        self._ground_line      = None

        # Timer de physique
        self._timer = QTimer()
        self._timer.setInterval(TIMER_MS)
        self._timer.timeout.connect(self._physics_tick)

        self._draw_ground()
        self.mpl_connect("button_press_event",   self._on_press)
        self.mpl_connect("motion_notify_event",  self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

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
            rd    = self.rects[idx]
            patch = rd["patch"]
            x, y  = patch.get_xy()
            h     = patch.get_height()

            # Calcul du sol effectif pour ce bloc :
            # c'est le max du sol et du sommet de tout bloc en dessous
            floor_y = GROUND_Y
            for i2, rd2 in enumerate(self.rects):
                if i2 == idx:
                    continue
                x2, y2  = rd2["patch"].get_xy()
                w2, h2  = rd2["patch"].get_width(), rd2["patch"].get_height()
                x_me, _ = patch.get_xy()
                w_me    = patch.get_width()
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
    def add_rectangle(self, w, h, material="Acier", density=7850):
        # Spawn en haut au centre si gravité active, sinon au-dessus de la pile
        if self.gravity_on:
            y_start = 9.0
            x_start = 1.0
        else:
            y_start = GROUND_Y
            if self.rects:
                tops    = [r["patch"].get_xy()[1] + r["patch"].get_height() for r in self.rects]
                y_start = max(tops)
            x_start = 0.5
        patch = Rectangle(
            (x_start, y_start), w, h,
            facecolor="#bbdefb", edgecolor="#1565c0",
            linewidth=1.8, zorder=5, alpha=0.9
        )
        self.axes.add_patch(patch)
        self.rects.append({
            "patch":     patch,
            "material":  material,
            "density":   density,
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
    def _hit_test(self, event):
        for i, rd in enumerate(reversed(self.rects)):
            idx  = len(self.rects) - 1 - i
            xy   = rd["patch"].get_xy()
            w, h = rd["patch"].get_width(), rd["patch"].get_height()
            if (event.xdata is not None and event.ydata is not None and
                    xy[0] <= event.xdata <= xy[0] + w and
                    xy[1] <= event.ydata <= xy[1] + h):
                return idx
        return None

    def _on_press(self, event):
        if event.inaxes != self.axes or event.button != 1:
            return
        idx = self._hit_test(event)
        if idx is not None:
            self._drag_index  = idx
            xy = self.rects[idx]["patch"].get_xy()
            self._drag_offset = (event.xdata - xy[0], event.ydata - xy[1])

    def _on_motion(self, event):
        if self._drag_index is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return
        rd    = self.rects[self._drag_index]
        patch = rd["patch"]
        xmin, xmax = self.axes.get_xlim()
        _, ymax_ax  = self.axes.get_ylim()
        w, h = patch.get_width(), patch.get_height()
        x = max(xmin,     min(xmax - w,     event.xdata - self._drag_offset[0]))
        y = max(GROUND_Y, min(ymax_ax - h,  event.ydata - self._drag_offset[1]))
        patch.set_xy((x, y))

        # Résolution de collision pendant le drag
        _resolve_collision(self._drag_index, self.rects)

        self.draw_idle()
        self._notify()

    def _on_release(self, event):
        self._drag_index  = None
        self._drag_offset = None

    def _notify(self):
        if self._on_rects_changed:
            self._on_rects_changed()

    # ── Dessin stress + contacts ──────────────
    def draw_stress(self, stress_data, contact_pairs):
        for p in self._stress_patches:
            try: p.remove()
            except Exception: pass
        self._stress_patches.clear()
        for a in self._arrow_artists:
            try: a.remove()
            except Exception: pass
        self._arrow_artists.clear()
        if self._cg_artist:
            for a in self._cg_artist:
                try: a.remove()
                except Exception: pass
            self._cg_artist = None

        if not self.rects or not stress_data:
            self.draw_idle()
            return

        all_sigma        = [abs(d["sigma_total"]) for d in stress_data if d]
        sigma_max_global = max(all_sigma) if any(s > 0 for s in all_sigma) else 1.0
        cmap = cm.get_cmap("RdYlGn_r")
        norm = mcolors.Normalize(vmin=0, vmax=sigma_max_global)

        # ── Blocs ────────────────────────────
        for i, (rd, sd) in enumerate(zip(self.rects, stress_data)):
            if sd is None:
                continue
            patch = rd["patch"]
            x, y  = patch.get_xy()
            w, h  = patch.get_width(), patch.get_height()

            if abs(sd.get("sigma_bending_top", 0)) > 1:
                for dy, sig in [(0, sd["sigma_bending_bot"]), (h/2, sd["sigma_bending_top"])]:
                    c = cmap(norm(abs(sig)))
                    r = Rectangle((x, y + dy), w, h/2,
                                  facecolor=c, edgecolor="none", alpha=0.55, zorder=6)
                    self.axes.add_patch(r)
                    self._stress_patches.append(r)
            else:
                c = cmap(norm(abs(sd["sigma_total"])))
                r = Rectangle((x, y), w, h,
                               facecolor=c, edgecolor="none", alpha=0.55, zorder=6)
                self.axes.add_patch(r)
                self._stress_patches.append(r)

            border = Rectangle((x, y), w, h,
                                facecolor="none", edgecolor="#1565c0",
                                linewidth=1.5, zorder=7)
            self.axes.add_patch(border)
            self._stress_patches.append(border)

            util = sd["utilization"]
            sym  = "✓" if util < 80 else ("!" if util < 100 else "✗")
            txt  = self.axes.text(
                x + w/2, y + h/2,
                f"σ={sd['sigma_total']/1e6:.2f} MPa\n{util:.0f}% {sym}",
                ha="center", va="center", fontsize=7.5,
                color="black", fontweight="bold", zorder=10,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.65, edgecolor="none")
            )
            self._stress_patches.append(txt)

            if abs(sd.get("ext_force", 0)) > 0:
                cx  = x + w/2
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
                    arr  = FancyArrowPatch(
                        (ax_x, y + h + 0.35), (ax_x, y + h + 0.02),
                        arrowstyle="-|>", mutation_scale=9,
                        color="#e65100", linewidth=1.2, zorder=11
                    )
                    self.axes.add_patch(arr)
                    self._arrow_artists.append(arr)

        # ── Contacts ─────────────────────────
        for (i_bot, i_top, frac) in contact_pairs:
            rd_b   = self.rects[i_bot]
            rd_t   = self.rects[i_top]
            xb, yb = rd_b["patch"].get_xy()
            wb, hb = rd_b["patch"].get_width(), rd_b["patch"].get_height()
            xt, yt = rd_t["patch"].get_xy()
            wt     = rd_t["patch"].get_width()
            y_if   = yb + hb

            x_l = max(xb, xt); x_r = min(xb + wb, xt + wt)
            cr  = Rectangle(
                (x_l, y_if - 0.05), x_r - x_l, 0.10,
                facecolor="#ff6f00", edgecolor="none", alpha=0.9, zorder=12
            )
            self.axes.add_patch(cr)
            self._stress_patches.append(cr)

            F_c = stress_data[i_top]["F_axial"]
            cx  = (x_l + x_r) / 2

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

            lbl = self.axes.text(
                cx + 0.3, y_if,
                f"Fc = {F_c:.0f} N\n({frac*100:.0f}% contact)",
                ha="left", va="center", fontsize=7,
                color="#bf360c", fontweight="bold", zorder=14,
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="#fff3e0", alpha=0.92, edgecolor="#ff6f00")
            )
            self._arrow_artists.append(lbl)

            for rd_hl in (rd_b, rd_t):
                px, py = rd_hl["patch"].get_xy()
                pw, ph = rd_hl["patch"].get_width(), rd_hl["patch"].get_height()
                hl = Rectangle((px, py), pw, ph,
                                facecolor="none", edgecolor="#ff6f00",
                                linewidth=3, linestyle="--", zorder=8)
                self.axes.add_patch(hl)
                self._stress_patches.append(hl)

        # ── Centre de gravité (boule jaune) ──
        total_area = sum(rd["patch"].get_width() * rd["patch"].get_height() for rd in self.rects)
        if total_area > 0:
            xg = sum((rd["patch"].get_xy()[0] + rd["patch"].get_width()/2) *
                     rd["patch"].get_width() * rd["patch"].get_height() for rd in self.rects) / total_area
            yg = sum((rd["patch"].get_xy()[1] + rd["patch"].get_height()/2) *
                     rd["patch"].get_width() * rd["patch"].get_height() for rd in self.rects) / total_area

            # Axes d'inertie (traits pointillés jaunes)
            hl = self.axes.axhline(yg, color="#f9a825", lw=0.9, ls="--", zorder=15, alpha=0.6)
            vl = self.axes.axvline(xg, color="#f9a825", lw=0.9, ls="--", zorder=15, alpha=0.6)

            # Boule jaune = Centre de Gravité
            dot, = self.axes.plot(xg, yg, "o", color="#f9a825", markersize=13,
                                  zorder=16, markeredgecolor="#e65100", markeredgewidth=2)

            # Étiquette au nord-ouest du point (les Fc sont à droite de l'interface → évite chevauchement)
            lbl_cg = self.axes.text(
                xg - 0.20, yg + 0.38,
                f"⊕ Centre de\n   Gravité\n   ({xg:.2f}, {yg:.2f})",
                ha="right", va="bottom",
                color="#e65100", fontsize=7.5, fontweight="bold", zorder=17,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff9c4",
                          alpha=0.92, edgecolor="#f9a825")
            )
            self._cg_artist = [dot, hl, vl, lbl_cg]

        self.draw_idle()


# ─────────────────────────────────────────────
#  Panneau de contrôle
# ─────────────────────────────────────────────
class ControlPanel(QFrame):
    MATERIALS = {
        "Acier":     {"density": 7850, "E": 210e9, "sigma_y": 250e6},
        "Béton":     {"density": 2400, "E":  30e9, "sigma_y":  30e6},
        "Aluminium": {"density": 2700, "E":  70e9, "sigma_y": 270e6},
        "Bois":      {"density":  600, "E":  12e9, "sigma_y":  40e6},
        "Fonte":     {"density": 7200, "E": 170e9, "sigma_y": 200e6},
    }

    def __init__(self, canvas, physics_callback, parent=None):
        super().__init__(parent)
        self.canvas           = canvas
        self.physics_callback = physics_callback
        self._selected_rect   = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Gravité toggle ───────────────────
        grp_grav = QGroupBox("Simulation physique")
        lay_grav = QVBoxLayout(grp_grav)
        self.chk_gravity = QCheckBox("🌍  Activer la gravité")
        self.chk_gravity.setStyleSheet("font-weight:bold; font-size:11px;")
        self.chk_gravity.toggled.connect(self._on_gravity_toggle)
        lay_grav.addWidget(self.chk_gravity)
        lbl_info = QLabel(
            "Quand activée : les nouveaux blocs\n"
            "tombent et s'empilent sur les autres.\n"
            "Les blocs ne peuvent pas se traverser."
        )
        lbl_info.setStyleSheet("color:#555; font-size:8px;")
        lay_grav.addWidget(lbl_info)
        grp_grav.setLayout(lay_grav)
        layout.addWidget(grp_grav)

        tabs = QTabWidget()

        # ── Blocs ────────────────────────────
        tab_b = QWidget()
        lay_b = QVBoxLayout(tab_b)

        grp1  = QGroupBox("Nouveau bloc")
        form1 = QFormLayout()
        self.spin_w    = QDoubleSpinBox(); self.spin_w.setRange(0.1, 20); self.spin_w.setValue(2); self.spin_w.setSingleStep(0.25)
        self.spin_h    = QDoubleSpinBox(); self.spin_h.setRange(0.1, 20); self.spin_h.setValue(1); self.spin_h.setSingleStep(0.25)
        self.combo_mat = QComboBox()
        for m in self.MATERIALS: self.combo_mat.addItem(m)
        form1.addRow("Largeur (m):", self.spin_w)
        form1.addRow("Hauteur (m):", self.spin_h)
        form1.addRow("Matériau:",    self.combo_mat)
        grp1.setLayout(form1)
        lay_b.addWidget(grp1)

        btn_add = QPushButton("➕  Ajouter bloc")
        btn_add.clicked.connect(self._on_add)
        lay_b.addWidget(btn_add)

        grp2   = QGroupBox("Blocs présents")
        lay_b2 = QVBoxLayout(grp2)
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(150)
        self.list_widget.currentRowChanged.connect(self._on_select)
        lay_b2.addWidget(self.list_widget)
        btn_rem = QPushButton("🗑  Supprimer sélectionné")
        btn_rem.clicked.connect(self._on_remove)
        lay_b2.addWidget(btn_rem)
        grp2.setLayout(lay_b2)
        lay_b.addWidget(grp2)
        lay_b.addStretch()
        tabs.addTab(tab_b, "Blocs")

        # ── Charges ──────────────────────────
        tab_l = QWidget()
        lay_l = QVBoxLayout(tab_l)
        grp_l = QGroupBox("Charges — bloc sélectionné")
        form_l = QFormLayout()
        self.spin_force    = QDoubleSpinBox(); self.spin_force.setRange(0, 1e7);     self.spin_force.setSuffix(" N");    self.spin_force.setSingleStep(100)
        self.spin_pressure = QDoubleSpinBox(); self.spin_pressure.setRange(0, 1e6);  self.spin_pressure.setSuffix(" Pa"); self.spin_pressure.setSingleStep(500)
        self.spin_moment   = QDoubleSpinBox(); self.spin_moment.setRange(-1e6, 1e6); self.spin_moment.setSuffix(" N·m"); self.spin_moment.setSingleStep(100)
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

        layout.addWidget(tabs)

        # ── Résultats ────────────────────────
        grp_r = QGroupBox("Résultats physiques")
        lay_r = QVBoxLayout(grp_r)
        self.lbl_results = QLabel("—")
        self.lbl_results.setWordWrap(True)
        self.lbl_results.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_results.setStyleSheet("font-family: Consolas; font-size: 9px; color: #222;")
        scroll = QScrollArea()
        scroll.setWidget(self.lbl_results)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(240)
        lay_r.addWidget(scroll)
        grp_r.setLayout(lay_r)
        layout.addWidget(grp_r)

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
        mn  = self.combo_mat.currentText()
        mat = self.MATERIALS[mn]
        self.canvas.add_rectangle(self.spin_w.value(), self.spin_h.value(),
                                  material=mn, density=mat["density"])

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.canvas.remove_rectangle(row)

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
            rd["pressure"]  = self.spin_pressure.value()
            rd["moment"]    = self.spin_moment.value()
            self.physics_callback()

    def refresh_list(self):
        self.list_widget.clear()
        for i, rd in enumerate(self.canvas.rects):
            p = rd["patch"]
            self.list_widget.addItem(
                f"[{i+1}] {rd['material']}  {p.get_width():.1f}×{p.get_height():.1f} m"
            )

    def update_results(self, html):
        self.lbl_results.setText(html)


# ─────────────────────────────────────────────
#  Application principale
# ─────────────────────────────────────────────
class MaterialSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.canvas = Canvas2D(central, on_rects_changed=self._on_changed)
        ml.addWidget(self.canvas, stretch=1)

        self.panel = ControlPanel(self.canvas, self._on_changed)
        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panel)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _on_changed(self):
        self.panel.refresh_list()
        stress_data, pairs = self._calculate_physics()
        self.canvas.draw_stress(stress_data, pairs)

    def _calculate_physics(self):
        rects = self.canvas.rects
        if not rects:
            self.panel.update_results("Aucun bloc.")
            return [], []

        MAT   = ControlPanel.MATERIALS
        lines = []

        total_area = sum(rd["patch"].get_width() * rd["patch"].get_height() for rd in rects)
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
        masse = sum(rd["density"] * rd["patch"].get_width() * rd["patch"].get_height() for rd in rects)

        lines += [
            "<b style='color:#1565c0'>══ Section globale ══</b>",
            f"Aire   : <b>{total_area:.4f} m²</b>",
            f"CG     : <b>({XG:.3f}, {YG:.3f}) m</b>",
            f"Ixx    : <b>{Ixx:.4f} m⁴</b>",
            f"Iyy    : <b>{Iyy:.4f} m⁴</b>",
            f"Masse  : <b>{masse:.1f} kg/m</b>",
            "",
        ]

        pairs = _contact_pairs(rects)

        stress_data = []
        for i, rd in enumerate(rects):
            patch = rd["patch"]
            w, h  = patch.get_width(), patch.get_height()
            x, y  = patch.get_xy()
            area  = w * h
            mat   = MAT.get(rd["material"], MAT["Acier"])

            weight     = rd["density"] * area * GRAVITY
            F_ext      = rd["ext_force"]
            F_pressure = rd["pressure"] * w

            F_contact = sum(
                rects[j]["density"] * rects[j]["patch"].get_width() *
                rects[j]["patch"].get_height() * GRAVITY +
                rects[j]["ext_force"] + rects[j]["pressure"] * rects[j]["patch"].get_width()
                for (ib, j, _) in pairs if ib == i
            )

            F_axial     = weight + F_ext + F_pressure + F_contact
            sigma_axial = F_axial / area

            M       = rd["moment"]
            I_local = (w * h**3) / 12
            sig_bt  = M * (h/2)  / I_local if I_local > 0 else 0
            sig_bb  = M * (-h/2) / I_local if I_local > 0 else 0
            sig_max = max(abs(sigma_axial + sig_bt), abs(sigma_axial + sig_bb))

            sigma_y = mat["sigma_y"]
            util    = sig_max / sigma_y * 100
            status  = "✅ OK" if util < 80 else ("⚠️ Attention" if util < 100 else "❌ RUPTURE")

            lines += [
                f"<b style='color:#e65100'>── Bloc {i+1} ({rd['material']}) ──</b>",
                f"  Poids propre   : {weight:.1f} N",
                f"  Charge contact : {F_contact:.1f} N",
                f"  Force ext.     : {F_ext:.1f} N",
                f"  Pression       : {F_pressure:.1f} N",
                f"  <b>F axiale total : {F_axial:.1f} N</b>",
                f"  σ axiale       : {sigma_axial/1e6:.3f} MPa",
            ]
            if abs(M) > 0:
                lines += [
                    f"  σ flex haut    : {sig_bt/1e6:.3f} MPa",
                    f"  σ flex bas     : {sig_bb/1e6:.3f} MPa",
                ]
            lines += [
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

        if pairs:
            lines.append("<b style='color:#ff6f00'>══ Contacts détectés ══</b>")
            for (ib, it, frac) in pairs:
                Fc = stress_data[it]["F_axial"]
                lines.append(
                    f"  Bloc {it+1} → Bloc {ib+1} : "
                    f"<b>{Fc:.0f} N</b> ({frac*100:.0f}% surface)"
                )
            lines.append("")

        self.panel.update_results("<br>".join(lines))
        return stress_data, pairs


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MaterialSimulationApp()
    window.show()
    sys.exit(app.exec())