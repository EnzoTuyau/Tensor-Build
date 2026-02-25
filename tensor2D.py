import sys
import numpy as np  # Importé au début, c'est plus propre
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QDoubleSpinBox, QPushButton, QListWidget, QLabel,
    QFormLayout, QGroupBox, QFrame,
)
from PySide6.QtCore import Qt

class Canvas2D(FigureCanvasQTAgg):
    def __init__(self, parent=None, on_rects_changed=None):
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
        self._drag_index = None
        self._drag_offset = None
        self._on_rects_changed = on_rects_changed

        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    def add_rectangle(self, w, h):
        rect = Rectangle((0, 0), w, h, facecolor="steelblue", edgecolor="black")
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

    def _hit_test(self, event):
        for i, rect in enumerate(reversed(self.rects)):
            idx = len(self.rects) - 1 - i
            xy = rect.get_xy()
            w, h = rect.get_width(), rect.get_height()
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
            rect = self.rects[idx]
            self._drag_index = idx
            self._drag_offset = (event.xdata - rect.get_xy()[0],
                                 event.ydata - rect.get_xy()[1])

    def _on_motion(self, event):
        if self._drag_index is None or event.inaxes != self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return
        rect = self.rects[self._drag_index]
        xmin, xmax = self.axes.get_xlim()
        ymin, ymax = self.axes.get_ylim()
        w, h = rect.get_width(), rect.get_height()
        x = max(xmin, min(xmax - w, event.xdata - self._drag_offset[0]))
        y = max(ymin, min(ymax - h, event.ydata - self._drag_offset[1]))
        rect.set_xy((x, y))
        self.draw_idle()
        # On notifie le changement pendant le mouvement pour voir la physique en temps réel
        if self._on_rects_changed:
            self._on_rects_changed()

    def _on_release(self, event):
        self._drag_index = None
        self._drag_offset = None


class RectPanel(QFrame):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Add rectangle")
        form = QFormLayout()
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(0.1, 100)
        self.spin_w.setValue(2)
        self.spin_w.setSingleStep(0.5)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(0.1, 100)
        self.spin_h.setValue(1)
        self.spin_h.setSingleStep(0.5)
        form.addRow("Width (x):", self.spin_w)
        form.addRow("Height (y):", self.spin_h)
        group.setLayout(form)
        layout.addWidget(group)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._on_add)
        layout.addWidget(self.btn_add)

        layout.addWidget(QLabel("Rectangles:"))
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(150)
        layout.addWidget(self.list_widget)

        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.clicked.connect(self._on_remove)
        layout.addWidget(self.btn_remove)

        layout.addStretch()

    def _on_add(self):
        w, h = self.spin_w.value(), self.spin_h.value()
        self.canvas.add_rectangle(w, h)

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.canvas.remove_rectangle(row)

    def refresh_list(self):
        self.list_widget.clear()
        for i in range(len(self.canvas.rects)):
            r = self.canvas.rects[i]
            self.list_widget.addItem(
                f"Rect {i + 1}: {r.get_width():.1f} × {r.get_height():.1f}"
            )


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
        self.canvas = Canvas2D(self.central_widget, on_rects_changed=self._rects_changed)
        self.panel.canvas = self.canvas

        self.layout.addWidget(self.canvas, stretch=1)

        self.dock = QDockWidget("Rectangle controls", self)
        self.dock.setWidget(self.panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

    def _rects_changed(self):
        """Appelé à chaque modification ou mouvement"""
        self.panel.refresh_list()
        self.calculate_physics() # On appelle la méthode ici

    def calculate_physics(self):
        """Calcule les propriétés de la section (Aire, Centre de Gravité, Inertie)"""
        rects = self.canvas.rects
        if not rects:
            return

        total_area = 0
        sum_ax = 0
        sum_ay = 0

        # 1. Calcul de l'Aire et du Centre de Gravité
        for r in rects:
            w = r.get_width()
            h = r.get_height()
            x, y = r.get_xy()
            cx, cy = x + w/2, y + h/2
            
            area = w * h
            total_area += area
            sum_ax += area * cx
            sum_ay += area * cy

        XG = sum_ax / total_area
        YG = sum_ay / total_area

        # 2. Calcul des Moments d'Inertie (Théorème de Steiner)
        Ixx = 0
        Iyy = 0
        for r in rects:
            w = r.get_width()
            h = r.get_height()
            x, y = r.get_xy()
            cx, cy = x + w/2, y + h/2
            area = w * h

            # Formule : Inertie propre + (Aire * distance^2)
            Ixx += (w * h**3) / 12 + area * (cy - YG)**2
            Iyy += (h * w**3) / 12 + area * (cx - XG)**2

        print(f"--- Calcul Physique ---")
        print(f"Centre de Gravité : XG={XG:.2f}, YG={YG:.2f}")
        print(f"Inertie Ixx: {Ixx:.2f}, Iyy: {Iyy:.2f}")
        print(f"------------------------")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterialSimulationApp()
    window.show()
    sys.exit(app.exec())