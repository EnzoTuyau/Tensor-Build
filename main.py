import sys
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox,
                               QPushButton, QGroupBox, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt


class MaterialSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Configuration de la fenêtre ---
        self.setWindowTitle("Tensor Build - Simulateur de Structure")
        self.resize(1200, 800)

        # Widget central
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        # --- 1. Zone 3D (Gauche) ---
        # On utilise QtInteractor de pyvistaqt pour intégrer la 3D dans Qt
        self.plotter = QtInteractor(self.central_widget)
        self.plotter.set_background("white")
        self.plotter.add_axes()
        self.layout.addWidget(self.plotter.interactor, stretch=2)

        # --- 2. Panneau de Contrôle (Droite) ---
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        self.layout.addWidget(self.control_panel, stretch=1)

        self.setup_ui_controls()

        # Liste pour stocker nos objets (meshes)
        self.objects = []
        self.current_actor = None

    def setup_ui_controls(self):
        """Crée les boutons et menus à droite"""

        # --- Section : Ajouter une forme ---
        group_add = QGroupBox("1. Ajouter une Pièce")
        layout_add = QVBoxLayout()

        self.shape_selector = QComboBox()
        self.shape_selector.addItems(["Cylindre", "Poutre (Carrée)"])
        layout_add.addWidget(QLabel("Forme :"))
        layout_add.addWidget(self.shape_selector)

        self.btn_add = QPushButton("Ajouter à la scène")
        self.btn_add.clicked.connect(self.add_shape)
        layout_add.addWidget(self.btn_add)

        group_add.setLayout(layout_add)
        self.control_layout.addWidget(group_add)

        # --- Section : Propriétés Géométriques ---
        group_geo = QGroupBox("2. Dimensions & Position")
        layout_geo = QFormLayout()

        # Rayon / Largeur
        self.spin_radius = QDoubleSpinBox()
        self.spin_radius.setRange(0.1, 100.0)
        self.spin_radius.setValue(1.0)
        self.spin_radius.setSingleStep(0.1)
        self.spin_radius.valueChanged.connect(self.update_current_shape)
        layout_geo.addRow("Rayon / Largeur :", self.spin_radius)

        # Longueur
        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(0.1, 100.0)
        self.spin_length.setValue(5.0)
        self.spin_length.valueChanged.connect(self.update_current_shape)
        layout_geo.addRow("Longueur :", self.spin_length)

        # Position X, Y, Z (Pour l'assemblage)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.valueChanged.connect(self.update_current_shape)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.valueChanged.connect(self.update_current_shape)
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-100, 100)
        self.spin_z.valueChanged.connect(self.update_current_shape)

        layout_geo.addRow("Position X :", self.spin_x)
        layout_geo.addRow("Position Y :", self.spin_y)
        layout_geo.addRow("Position Z :", self.spin_z)

        group_geo.setLayout(layout_geo)
        self.control_layout.addWidget(group_geo)

        # --- Section : Matériau ---
        group_mat = QGroupBox("3. Matériau")
        layout_mat = QVBoxLayout()

        self.material_selector = QComboBox()
        # Nom, Module de Young (Pa), Couleur
        self.materials_db = {
            "Acier": (200e9, "grey"),
            "Aluminium": (69e9, "silver"),
            "Bois": (11e9, "tan"),
            "Plastique": (3e9, "lightblue")
        }
        self.material_selector.addItems(self.materials_db.keys())
        self.material_selector.currentTextChanged.connect(self.update_material)

        layout_mat.addWidget(QLabel("Type de matériau :"))
        layout_mat.addWidget(self.material_selector)

        group_mat.setLayout(layout_mat)
        self.control_layout.addWidget(group_mat)

        # --- Section : Simulation ---
        self.btn_sim = QPushButton("Lancer Simulation (Calcul SciPy)")
        self.btn_sim.setStyleSheet("background-color: #ffcccc; font-weight: bold; padding: 10px;")
        self.btn_sim.clicked.connect(self.run_dummy_simulation)
        self.control_layout.addWidget(self.btn_sim)

        self.control_layout.addStretch()

    def add_shape(self):
        """Ajoute une nouvelle forme à la scène"""
        shape_type = self.shape_selector.currentText()

        # On crée un dictionnaire pour stocker les infos de l'objet
        obj_data = {
            "type": shape_type,
            "mesh": None,
            "actor": None,
            "params": {
                "radius": self.spin_radius.value(),
                "length": self.spin_length.value(),
                "center": (self.spin_x.value(), self.spin_y.value(), self.spin_z.value())
            }
        }

        self.objects.append(obj_data)
        self.draw_shape(obj_data)

    def draw_shape(self, obj_data):
        """Génère le maillage PyVista et l'affiche"""
        # Nettoyer l'ancien acteur si on met à jour
        if obj_data["actor"]:
            self.plotter.remove_actor(obj_data["actor"])

        # Création de la géométrie
        if obj_data["type"] == "Cylindre":
            mesh = pv.Cylinder(
                radius=obj_data["params"]["radius"],
                height=obj_data["params"]["length"],
                center=obj_data["params"]["center"],
                direction=(1, 0, 0),  # Axe X par défaut
                resolution=30
            )
        else:  # Poutre Carrée (Box)
            r = obj_data["params"]["radius"]  # On utilise rayon comme demi-largeur
            l = obj_data["params"]["length"]
            c = obj_data["params"]["center"]
            # Création d'une boite : bounds=(x_min, x_max, y_min, y_max, z_min, z_max)
            mesh = pv.Cube(
                center=c,
                x_length=l,
                y_length=r * 2,
                z_length=r * 2
            )

        # Récupérer la couleur du matériau actuel
        mat_name = self.material_selector.currentText()
        color = self.materials_db[mat_name][1]

        # Ajouter à la scène
        actor = self.plotter.add_mesh(mesh, color=color, show_edges=True)

        # Mettre à jour les références
        obj_data["mesh"] = mesh
        obj_data["actor"] = actor
        self.current_actor = obj_data  # Le dernier objet modifié est celui-ci

    def update_current_shape(self):
        """Appelé quand on bouge les sliders"""
        if not self.objects:
            return

        # On modifie le DERNIER objet ajouté (pour l'exemple)
        # Idéalement, il faudrait une liste pour sélectionner quel objet modifier
        current_obj = self.objects[-1]

        current_obj["params"]["radius"] = self.spin_radius.value()
        current_obj["params"]["length"] = self.spin_length.value()
        current_obj["params"]["center"] = (self.spin_x.value(), self.spin_y.value(), self.spin_z.value())

        self.draw_shape(current_obj)

    def update_material(self):
        """Change la couleur selon le matériau"""
        if self.objects:
            self.draw_shape(self.objects[-1])

    def run_dummy_simulation(self):
        """C'est ici que tu connecteras ton code SciPy plus tard"""
        if not self.objects:
            return

        QMessageBox.information(self, "Simulation",
                                "Calcul de la matrice de rigidité K en cours...\n"
                                "Application des forces...\n"
                                "Résolution F = K * u avec SciPy...")

        # Simulation visuelle : Changer la couleur en "Stress Map" (Von Mises fictif)
        last_obj = self.objects[-1]
        mesh = last_obj["mesh"]

        # On invente des données de stress pour l'exemple
        # Dans ton vrai projet, ça viendra de tes calculs matriciels
        stress_values = np.linspace(0, 100, mesh.n_points)

        self.plotter.remove_actor(last_obj["actor"])
        self.plotter.add_mesh(mesh, scalars=stress_values, cmap="jet", show_edges=False)
        self.plotter.add_scalar_bar(title="Contrainte de Von Mises (MPa)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterialSimulationApp()
    window.show()
    sys.exit(app.exec())