import sys
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from tensor2D import MaterialSimulationApp as App2D
from tensor3D import MaterialSimulationApp as App3D


class MenuDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TensorBuild - Choix de la simulation")
        self.setFixedSize(820, 500)
        self.mode = None
        self.btn_2d = None
        self.btn_3d = None
        self.btn_start = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)

        header = self._build_header()
        body = self._build_body()

        root.addWidget(header)
        root.addLayout(body, 1)
        self.mode = "2D"
        self._refresh_mode_buttons()

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
            QLabel#tagline {
                color: #dbe8ff;
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#subtext {
                color: #9eb4d9;
                font-size: 13px;
            }
            QLabel#nav {
                color: #9eb4d9;
                font-size: 12px;
            }
            QWidget#heroPanel {
                background-color: transparent;
                border: none;
                border-radius: 0px;
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
            QPushButton#primaryCta {
                background-color: #0d8bff;
                color: #ffffff;
                border: none;
                border-radius: 18px;
                padding: 10px 18px;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton#primaryCta:hover {
                background-color: #2c9bff;
            }
            QPushButton#primaryCta:disabled {
                background-color: #6c7480;
                color: #d8dde6;
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
            QPushButton#modeCard[selected="true"] {
                border: 1px solid #2ea0ff;
                background-color: #17253a;
            }
            """
        )

    def _build_header(self):
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        brand_tensor = QLabel("Tensor<span style='color:#1f94ff;'>Build</span>")
        brand_tensor.setObjectName("brand")
        brand_tensor.setTextFormat(Qt.TextFormat.RichText)
        brand_build = QLabel("Build")
        brand_build.setObjectName("brandBuild")
        row.addWidget(brand_tensor, 0, Qt.AlignmentFlag.AlignVCenter)

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

        self.btn_start = QPushButton("  Commencer")
        self.btn_start.setObjectName("primaryCta")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._confirm_selection)

        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel_col = QVBoxLayout(left_panel)
        left_panel_col.setContentsMargins(34, 26, 24, 26)
        left_panel_col.setSpacing(8)
        left_panel_col.addStretch(1)
        left_panel_col.addWidget(hero_title)
        left_panel_col.addStretch(1)

        right_panel = QWidget()
        right_panel.setObjectName("heroPanel")
        right_col = QVBoxLayout(right_panel)
        right_col.setContentsMargins(0, 0, 12, 0)
        right_col.setSpacing(10)

        self.btn_2d = QPushButton("Simulation 2D\nAnalyse des contraintes\nen coupe")
        self.btn_2d.setObjectName("modeCard")
        self.btn_2d.setProperty("selected", False)
        self.btn_2d.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_2d.clicked.connect(self.select_2d)

        self.btn_3d = QPushButton("Simulation 3D\nAssemblage et visualisation\nspatiale")
        self.btn_3d.setObjectName("modeCard")
        self.btn_3d.setProperty("selected", False)
        self.btn_3d.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_3d.clicked.connect(self.select_3d)

        right_controls = QWidget()
        right_controls.setObjectName("rightControls")
        right_controls.setFixedWidth(320)
        controls_col = QVBoxLayout(right_controls)
        controls_col.setContentsMargins(0, 0, 0, 0)
        controls_col.setSpacing(10)
        controls_col.addStretch(9)
        controls_col.addWidget(self.btn_2d)
        controls_col.addWidget(self.btn_3d)
        controls_col.addWidget(self.btn_start)
        controls_col.addStretch(6)

        left_col.addWidget(left_panel)
        right_col.addStretch(1)
        right_col.addWidget(right_controls, 0, Qt.AlignmentFlag.AlignRight)
        right_col.addStretch(1)

        body.addWidget(left, 2)
        body.addWidget(right_panel, 1)
        return body

    def _confirm_selection(self):
        if self.mode is None:
            return
        self.accept()

    def _refresh_mode_buttons(self):
        is_2d = self.mode == "2D"
        is_3d = self.mode == "3D"
        self.btn_2d.setProperty("selected", is_2d)
        self.btn_3d.setProperty("selected", is_3d)
        self.btn_2d.style().unpolish(self.btn_2d)
        self.btn_2d.style().polish(self.btn_2d)
        self.btn_3d.style().unpolish(self.btn_3d)
        self.btn_3d.style().polish(self.btn_3d)
        self.btn_start.setEnabled(is_2d or is_3d)

    def select_2d(self):
        self.mode = None if self.mode == "2D" else "2D"
        self._refresh_mode_buttons()

    def select_3d(self):
        self.mode = None if self.mode == "3D" else "3D"
        self._refresh_mode_buttons()


class GestionnaireApplication:
    def __init__(self):
        self.current_window = None

    def open_2d(self):
        # Ouvrir la nouvelle fenêtre avant de fermer l'ancienne
        # pour qu'il n'y ait jamais zéro fenêtre visible
        old = self.current_window
        self.current_window = App2D(mode="2D", switch_callback=self.open_3d)
        self.current_window.show()
        self.current_window.raise_()
        self.current_window.activateWindow()
        if old:
            old.close()

    def open_3d(self):
        old = self.current_window
        self.current_window = App3D(switch_callback=self.open_2d)
        self.current_window.show()
        self.current_window.raise_()
        self.current_window.activateWindow()
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