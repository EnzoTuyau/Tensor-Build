import sys
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout


class Canvas2D(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        fig = Figure(figsize=(8, 6), facecolor="white")
        self.axes = fig.add_subplot(111)
        self.axes.set_aspect("equal")
        self.axes.grid(True)
        super().__init__(fig)


class MaterialSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tensor Build - Simulateur de Structure")
        self.resize(1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        self.canvas = Canvas2D(self.central_widget)
        self.layout.addWidget(self.canvas, stretch=1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterialSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
