import sys
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

from tensor2D import MaterialSimulationApp as App2D
from tensor3D import MaterialSimulationApp as App3D


class MenuDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tensor Build - Choix de la Simulation")
        self.setFixedSize(300, 200)
        self.mode = None

        layout = QVBoxLayout()
        layout.setSpacing(20)

        label = QLabel("Bienvenue dans TensorBuild!\nVeuillez choisir une simulation :")
        label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1565c0;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        btn_2d = QPushButton("Simulation 2D")
        btn_3d = QPushButton("Simulation 3D")
        btn_2d.setStyleSheet("padding: 10px; font-size: 13px;")
        btn_3d.setStyleSheet("padding: 10px; font-size: 13px;")
        layout.addWidget(btn_2d)
        layout.addWidget(btn_3d)

        btn_2d.clicked.connect(self.launch_2d)
        btn_3d.clicked.connect(self.launch_3d)

        self.setLayout(layout)

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