import sys
import math
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, FancyArrowPatch
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QDoubleSpinBox, QPushButton, QListWidget, QLabel,
    QFormLayout, QGroupBox, QFrame,
)
from PySide6.QtCore import Qt


ARROW_SCALE = 0.05  # unités de données par Newton
OVERLAP_EPSILON = 1e-9  # tolérance pour permettre le contact bord-à-bord (pas de chevauchement)


class Canvas2D(FigureCanvasQTAgg):
    def __init__(self, parent=None, on_rects_changed=None, on_forces_changed=None):
        fig = Figure(figsize=(12, 12), facecolor="white")
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self.axes = fig.add_subplot(111)
        self.axes.set_aspect("equal")
        self.axes.grid(True)
        self.axes.axis("off")
        self.axes.set_xlim(-5, 10)
        self.axes.set_ylim(-5, 10)
        super().__init__(fig)

        self.rects = []
        self.forces = []  # liste de {"arrow", "label", "base", "dx", "dy", "mag"}
        self._drag_rect_index = None
        self._drag_force_index = None
        self._rotate_force_index = None
        self._drag_offset = None
        self._on_rects_changed = on_rects_changed
        self._on_forces_changed = on_forces_changed

        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    def add_rectangle(self, w, h):
        x, y = 0, 0
        for ox, oy in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)]:
            if not self._rect_overlaps_any_arrow(ox, oy, w, h):
                x, y = ox, oy
                break
        rect = Rectangle((x, y), w, h, facecolor="steelblue", edgecolor="black")
        self.axes.add_patch(rect)
        self.rects.append(rect)
        self.draw_idle()
        if self._on_rects_changed:
            self._on_rects_changed()

    def remove_rectangle(self, index):
        if 0 <= index < len(self.rects):
            self.rects[index].remove()
            self.rects.pop(index)
            self.draw_idle()
            if self._on_rects_changed:
                self._on_rects_changed()

    def add_force(self, newtons, x=3, y=3):
        length = newtons * ARROW_SCALE
        dx, dy = length, 0  # par défaut : vers la droite
        for ox, oy in [(x, y), (x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)]:
            if not self._arrow_overlaps_any_rect(ox, oy, ox + dx, oy + dy):
                x, y = ox, oy
                break
        arrow = FancyArrowPatch((x, y), (x + dx, y + dy), arrowstyle="->,head_width=0.3",
                                color="red", linewidth=2, mutation_scale=12)
        self.axes.add_patch(arrow)
        tx, ty = x + dx * 0.5, y + dy * 0.5 + 0.15
        label = self.axes.text(tx, ty, f"{newtons:.0f} N", fontsize=6, color="red", ha="center", va="center")
        self.forces.append({"arrow": arrow, "label": label, "base": (x, y), "dx": dx, "dy": dy, "mag": newtons})
        self.draw_idle()
        if self._on_forces_changed:
            self._on_forces_changed()

    def remove_force(self, index):
        if 0 <= index < len(self.forces):
            f = self.forces[index]
            f["arrow"].remove()
            f["label"].remove()
            self.forces.pop(index)
            self.draw_idle()
            if self._on_forces_changed:
                self._on_forces_changed()

    def _hit_test(self, event):
        for i, rect in enumerate(reversed(self.rects)):
            idx = len(self.rects) - 1 - i
            xy = rect.get_xy()
            w, h = rect.get_width(), rect.get_height()
            if (xy[0] <= event.xdata <= xy[0] + w and
                    xy[1] <= event.ydata <= xy[1] + h):
                return idx
        return None

    def _dist_to_segment(self, px, py, x1, y1, x2, y2):
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len < 1e-9:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (seg_len * seg_len)))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        return math.hypot(px - proj_x, py - proj_y)

    def _segment_intersects_segment(self, x1, y1, x2, y2, x3, y3, x4, y4):
        def cross(ox, oy, ax, ay, bx, by):
            return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

        def on_segment(ax, ay, bx, by, cx, cy):
            return (min(ax, bx) <= cx <= max(ax, bx) and min(ay, by) <= cy <= max(ay, by))

        d1 = cross(x3, y3, x4, y4, x1, y1)
        d2 = cross(x3, y3, x4, y4, x2, y2)
        d3 = cross(x1, y1, x2, y2, x3, y3)
        d4 = cross(x1, y1, x2, y2, x4, y4)
        if d1 * d2 < 0 and d3 * d4 < 0:
            return True
        if abs(d1) < 1e-12 and on_segment(x3, y3, x4, y4, x1, y1):
            return True
        if abs(d2) < 1e-12 and on_segment(x3, y3, x4, y4, x2, y2):
            return True
        if abs(d3) < 1e-12 and on_segment(x1, y1, x2, y2, x3, y3):
            return True
        if abs(d4) < 1e-12 and on_segment(x1, y1, x2, y2, x4, y4):
            return True
        return False

    def _point_in_rect(self, px, py, rx, ry, rw, rh):
        return rx <= px <= rx + rw and ry <= py <= ry + rh

    def _point_in_rect_interior(self, px, py, rx, ry, rw, rh):
        e = OVERLAP_EPSILON
        return rx + e < px < rx + rw - e and ry + e < py < ry + rh - e

    def _segment_intersects_rect_interior(self, x1, y1, x2, y2, rx, ry, rw, rh):
        e = OVERLAP_EPSILON
        edges = [
            ((rx + e, ry + e), (rx + rw - e, ry + e)),
            ((rx + rw - e, ry + e), (rx + rw - e, ry + rh - e)),
            ((rx + rw - e, ry + rh - e), (rx + e, ry + rh - e)),
            ((rx + e, ry + rh - e), (rx + e, ry + e)),
        ]
        for (x3, y3), (x4, y4) in edges:
            if self._segment_intersects_segment(x1, y1, x2, y2, x3, y3, x4, y4):
                return True
        return False

    def _rect_overlaps_any_arrow(self, rx, ry, rw, rh):
        for f in self.forces:
            bx, by = f["base"]
            ex, ey = bx + f["dx"], by + f["dy"]
            if self._point_in_rect_interior(bx, by, rx, ry, rw, rh) or self._point_in_rect_interior(ex, ey, rx, ry, rw, rh):
                return True
            if self._segment_intersects_rect_interior(bx, by, ex, ey, rx, ry, rw, rh):
                return True
        return False

    def _arrow_overlaps_any_rect(self, bx, by, ex, ey):
        for rect in self.rects:
            xy = rect.get_xy()
            rw, rh = rect.get_width(), rect.get_height()
            rx, ry = xy[0], xy[1]
            if self._point_in_rect_interior(bx, by, rx, ry, rw, rh) or self._point_in_rect_interior(ex, ey, rx, ry, rw, rh):
                return True
            if self._segment_intersects_rect_interior(bx, by, ex, ey, rx, ry, rw, rh):
                return True
        return False

    def _hit_test_force(self, event):
        px, py = event.xdata, event.ydata
        pick_radius = 0.5
        for i, f in enumerate(reversed(self.forces)):
            idx = len(self.forces) - 1 - i
            bx, by = f["base"]
            ex, ey = bx + f["dx"], by + f["dy"]
            if self._dist_to_segment(px, py, bx, by, ex, ey) < pick_radius:
                return idx
        return None

    def _on_press(self, event):
        if event.inaxes != self.axes:
            return
        if event.button == 1:
            idx = self._hit_test(event)
            if idx is not None:
                rect = self.rects[idx]
                self._drag_rect_index = idx
                self._drag_force_index = None
                self._rotate_force_index = None
                self._drag_offset = (event.xdata - rect.get_xy()[0],
                                     event.ydata - rect.get_xy()[1])
                return
            fidx = self._hit_test_force(event)
            if fidx is not None:
                f = self.forces[fidx]
                self._drag_rect_index = None
                self._drag_force_index = fidx
                self._rotate_force_index = None
                self._drag_offset = (event.xdata - f["base"][0], event.ydata - f["base"][1])
        elif event.button == 3:
            fidx = self._hit_test_force(event)
            if fidx is not None:
                self._drag_rect_index = None
                self._drag_force_index = None
                self._rotate_force_index = fidx

    def _on_motion(self, event):
        if event.xdata is None or event.ydata is None:
            return
        xmin, xmax = self.axes.get_xlim()
        ymin, ymax = self.axes.get_ylim()

        if self._drag_rect_index is not None and event.inaxes == self.axes:
            rect = self.rects[self._drag_rect_index]
            w, h = rect.get_width(), rect.get_height()
            x = max(xmin, min(xmax - w, event.xdata - self._drag_offset[0]))
            y = max(ymin, min(ymax - h, event.ydata - self._drag_offset[1]))
            if not self._rect_overlaps_any_arrow(x, y, w, h):
                rect.set_xy((x, y))
                self.draw_idle()
        elif self._drag_force_index is not None and event.inaxes == self.axes:
            f = self.forces[self._drag_force_index]
            dx, dy = f["dx"], f["dy"]
            bx_lo, bx_hi = max(xmin, xmin - dx), min(xmax, xmax - dx)
            by_lo, by_hi = max(ymin, ymin - dy), min(ymax, ymax - dy)
            bx = max(bx_lo, min(bx_hi, event.xdata - self._drag_offset[0]))
            by = max(by_lo, min(by_hi, event.ydata - self._drag_offset[1]))
            ex, ey = bx + dx, by + dy
            if not self._arrow_overlaps_any_rect(bx, by, ex, ey):
                f["base"] = (bx, by)
                f["arrow"].set_positions((bx, by), (ex, ey))
                f["label"].set_position((bx + dx * 0.5, by + dy * 0.5 + 0.15))
                self.draw_idle()
        elif self._rotate_force_index is not None and event.inaxes == self.axes:
            f = self.forces[self._rotate_force_index]
            bx, by = f["base"]
            length = math.hypot(f["dx"], f["dy"])
            angle = math.atan2(event.ydata - by, event.xdata - bx)
            dx = length * math.cos(angle)
            dy = length * math.sin(angle)
            ex, ey = bx + dx, by + dy
            if not self._arrow_overlaps_any_rect(bx, by, ex, ey):
                f["dx"], f["dy"] = dx, dy
                f["arrow"].set_positions((bx, by), (ex, ey))
                f["label"].set_position((bx + dx * 0.5, by + dy * 0.5 + 0.15))
                self.draw_idle()

    def _on_release(self, event):
        self._drag_rect_index = None
        self._drag_force_index = None
        self._rotate_force_index = None
        self._drag_offset = None


class RectPanel(QFrame):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Ajouter un rectangle")
        form = QFormLayout()
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(0.1, 100)
        self.spin_w.setValue(2)
        self.spin_w.setSingleStep(0.5)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(0.1, 100)
        self.spin_h.setValue(1)
        self.spin_h.setSingleStep(0.5)
        form.addRow("Largeur (x) :", self.spin_w)
        form.addRow("Hauteur (y) :", self.spin_h)
        group.setLayout(form)
        layout.addWidget(group)

        self.btn_add = QPushButton("Ajouter")
        self.btn_add.clicked.connect(self._on_add)
        layout.addWidget(self.btn_add)

        layout.addWidget(QLabel("Rectangles :"))
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(150)
        layout.addWidget(self.list_widget)

        self.btn_remove = QPushButton("Supprimer la sélection")
        self.btn_remove.clicked.connect(self._on_remove)
        layout.addWidget(self.btn_remove)

        group_force = QGroupBox("Ajouter une force")
        form_force = QFormLayout()
        self.spin_newtons = QDoubleSpinBox()
        self.spin_newtons.setRange(0.1, 10000)
        self.spin_newtons.setValue(10)
        self.spin_newtons.setSuffix(" N")
        form_force.addRow("Force :", self.spin_newtons)
        group_force.setLayout(form_force)
        layout.addWidget(group_force)

        self.btn_add_force = QPushButton("Ajouter")
        self.btn_add_force.clicked.connect(self._on_add_force)
        layout.addWidget(self.btn_add_force)
        layout.addWidget(QLabel("Clic gauche : déplacer  ·  Clic droit : pivoter"))

        layout.addWidget(QLabel("Forces :"))
        self.force_list = QListWidget()
        self.force_list.setMaximumHeight(120)
        layout.addWidget(self.force_list)

        self.btn_remove_force = QPushButton("Supprimer la sélection")
        self.btn_remove_force.clicked.connect(self._on_remove_force)
        layout.addWidget(self.btn_remove_force)

        layout.addStretch()

    def _on_add(self):
        w, h = self.spin_w.value(), self.spin_h.value()
        self.canvas.add_rectangle(w, h)

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.canvas.remove_rectangle(row)

    def _on_add_force(self):
        n = self.spin_newtons.value()
        self.canvas.add_force(n)

    def _on_remove_force(self):
        row = self.force_list.currentRow()
        if row >= 0:
            self.canvas.remove_force(row)

    def refresh_list(self):
        self.list_widget.clear()
        for i in range(len(self.canvas.rects)):
            r = self.canvas.rects[i]
            self.list_widget.addItem(
                f"Rect {i + 1} : {r.get_width():.1f} × {r.get_height():.1f}"
            )

    def refresh_forces(self):
        self.force_list.clear()
        for i, f in enumerate(self.canvas.forces):
            self.force_list.addItem(f"Force {i + 1} : {f['mag']:.1f} N")


class MaterialSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tensor Build - Simulateur de Structure")
        self.resize(1200, 1200)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.panel = RectPanel(None)
        self.canvas = Canvas2D(
            self.central_widget,
            on_rects_changed=self._rects_changed,
            on_forces_changed=self._forces_changed,
        )
        self.panel.canvas = self.canvas

        self.layout.addWidget(self.canvas, stretch=1)

        self.dock = QDockWidget("Contrôles", self)
        self.dock.setWidget(self.panel)
        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

        view_menu = self.menuBar().addMenu("Affichage")
        view_menu.addAction(self.dock.toggleViewAction())

    def _rects_changed(self):
        self.panel.refresh_list()

    def _forces_changed(self):
        self.panel.refresh_forces()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterialSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
