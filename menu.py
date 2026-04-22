from troisDimensions.app.MaterielSimulation import MaterielSimulationApp as App3D
from deuxDimensions.app.tensor2d import MaterialSimulationApp as App2D
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QWidget,
)
import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_main = os.path.join(_root, "Main")
if _main not in sys.path:
    sys.path.insert(0, _main)
if _root not in sys.path:
    sys.path.insert(0, _root)


class MenuDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TensorBuild - Choix de la simulation")
        self.setFixedSize(820, 500)
        self.mode = None
        self.btn_2d = None
        self.btn_3d = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)

        root.addWidget(self._build_header())
        root.addLayout(self._build_body(), 1)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #050607;
            }
            QLabel#brand {
                color: #f3f7ff;
                font-size: 36px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QLabel#nav {
                color: #9eb4d9;
                font-size: 12px;
            }
            QWidget#heroPanel {
                background-color: transparent;
                border: none;
            }
            QWidget#leftPanel {
                background-color: transparent;
                border: none;
            }
            QWidget#rightControls {
                background-color: transparent;
                border: none;
            }
            QLabel#heroTitle {
                color: #eaf2ff;
                font-size: 40px;
                font-weight: 800;
            }
            QLabel#heroSubtitle {
                color: #9eb4d9;
                font-size: 15px;
            }
            QPushButton#modeCard {
                background-color: #06080c;
                color: #eaf2ff;
                border: 1px solid #3b4b62;
                border-radius: 10px;
                padding: 12px;
                text-align: left;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#modeCard:hover {
                border: 1px solid #2ea0ff;
                background-color: #131f31;
            }
            """
        )

    def _build_header(self):
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        brand = QLabel("Tensor<span style='color:#1f94ff;'>Build</span>")
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(brand, 0, Qt.AlignmentFlag.AlignVCenter)

        row.addStretch(1)
        nav_items = ("A propos", "Support")
        for idx, text in enumerate(nav_items):
            nav = QLabel(text)
            nav.setObjectName("nav")
            row.addWidget(nav, 0, Qt.AlignmentFlag.AlignVCenter)
            if idx < len(nav_items) - 1:
                row.addSpacing(24)

        return header

    def _build_body(self):
        body = QHBoxLayout()
        body.setSpacing(26)

        left = QWidget()
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(0)

        hero_title = QLabel(
            "Simulez les forces.<br>"
            "Construisez avec<br>"
            "<span style='color:#1f94ff;'>confiance.</span>"
        )
        hero_title.setObjectName("heroTitle")
        hero_title.setWordWrap(True)

        hero_subtitle = QLabel(
            "Choisissez votre mode de simulation et lancez l'analyse."
        )
        hero_subtitle.setObjectName("heroSubtitle")
        hero_subtitle.setWordWrap(True)

        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel_col = QVBoxLayout(left_panel)
        left_panel_col.setContentsMargins(34, 26, 24, 26)
        left_panel_col.setSpacing(10)
        left_panel_col.addStretch(1)
        left_panel_col.addWidget(hero_title)
        left_panel_col.addWidget(hero_subtitle)
        left_panel_col.addStretch(1)

        right_panel = QWidget()
        right_panel.setObjectName("heroPanel")
        right_col = QVBoxLayout(right_panel)
        right_col.setContentsMargins(0, 0, 12, 0)
        right_col.setSpacing(10)

        self.btn_2d = QPushButton("Simulation 2D\nAnalyse des contraintes\nen coupe")
        self.btn_2d.setObjectName("modeCard")
        self.btn_2d.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_2d.clicked.connect(self.launch_2d)

        self.btn_3d = QPushButton("Simulation 3D\nAssemblage et visualisation\nspatiale")
        self.btn_3d.setObjectName("modeCard")
        self.btn_3d.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_3d.clicked.connect(self.launch_3d)

        right_controls = QWidget()
        right_controls.setObjectName("rightControls")
        right_controls.setFixedWidth(320)
        controls_col = QVBoxLayout(right_controls)
        controls_col.setContentsMargins(0, 0, 0, 0)
        controls_col.setSpacing(10)
        controls_col.addStretch(8)
        controls_col.addWidget(self.btn_2d)
        controls_col.addWidget(self.btn_3d)
        controls_col.addStretch(7)

        left_col.addWidget(left_panel)
        right_col.addStretch(1)
        right_col.addWidget(right_controls, 0, Qt.AlignmentFlag.AlignRight)
        right_col.addStretch(1)

        body.addWidget(left, 2)
        body.addWidget(right_panel, 1)
        return body

    def launch_2d(self):
        self.mode = "2D"
        self.accept()

    def launch_3d(self):
        self.mode = "3D"
        self.accept()


class GestionnaireApplication:
    def __init__(self):
        self.current_window = None

    def open_2d(self):
        # Ouvrir la nouvelle fenêtre avant de fermer l'ancienne
        # pour qu'il n'y ait jamais zéro fenêtre visible
        old = self.current_window
        self.current_window = App2D(mode="2D", switch_callback=self.open_3d)
        self.current_window.show()
        if old:
            old.close()

    def open_3d(self):
        old = self.current_window
        self.current_window = App3D(switch_callback=self.open_2d)
        self.current_window.show()
        if old:
            old.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    manager = GestionnaireApplication()
    menu = MenuDialog()

    if menu.exec() == QDialog.Accepted:
        if menu.mode == "2D":
            manager.open_2d()
        elif menu.mode == "3D":
            manager.open_3d()
        sys.exit(app.exec())
    else:
        sys.exit(0)
