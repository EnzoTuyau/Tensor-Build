import sys
import platform
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox,
                               QPushButton, QGroupBox, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt, QTimer


if platform.system() == "Darwin":
    class SafeQtInteractor(QtInteractor):
        """Works around the macOS + PySide6 6.10 infinite paintEvent/Render
        loop (VTK issue #19915) by deferring renders via QTimer."""

        _render_deferred = False

        def paintEvent(self, ev):
            if not self._render_deferred:
                self._render_deferred = True
                QTimer.singleShot(0, self._deferred_render)

        def _deferred_render(self):
            self._Iren.Render()
            self._render_deferred = False
else:
    SafeQtInteractor = QtInteractor


class MaterialSimulationApp(QMainWindow):
    # --- scene ---
    def __init__(scene):
        super().__init__()

        # --- Configuration de la fenêtre ---
        scene.setWindowTitle("Tensor Build - Simulateur de Structure")
        scene.resize(1200, 800)

        # Widget central
        # espace à droite réservé pour les boutons
        scene.central_widget = QWidget()
        # centre les boutons et les rends le coeur de l'interface
        scene.setCentralWidget(scene.central_widget)
        scene.layout = QHBoxLayout(scene.central_widget)

        # --- 1. Zone 3D (Gauche) ---
        # On utilise QtInteractor de pyvistaqt pour intégrer la 3D dans Qt
        scene.plotter = SafeQtInteractor(scene.central_widget)
        # plotter permet de montrer tout ce que l'utilisateur voit
        scene.plotter.set_background("white")
        scene.plotter.add_axes()
        # stretch=2 permet de gérer la proportion de l'interface d'utilisation
        scene.layout.addWidget(scene.plotter.interactor, stretch=2)

        # --- 2. Panneau de Contrôle (Droite) ---
        scene.control_panel = QWidget()
        scene.control_layout = QVBoxLayout(scene.control_panel)
        scene.layout.addWidget(scene.control_panel, stretch=1)

        scene.setup_ui_controls()

        # Liste pour stocker nos objets (meshes)
        scene.objects = []
        scene.current_actor = None

    def setup_ui_controls(scene):
        # Crée les boutons et menus à droite

        # Section : Ajouter une forme
        group_add = QGroupBox("1. Ajouter une Pièce")
        layout_add = QVBoxLayout()

        scene.shape_selector = QComboBox()
        scene.shape_selector.addItems(
            ["Cylindre", "Poutre (Carrée)", "Prisme Triangulaire", "Sphère", "Cube", "Vis"])
        layout_add.addWidget(QLabel("Forme :"))
        layout_add.addWidget(scene.shape_selector)

        scene.btn_add = QPushButton("Ajouter à la scène")
        scene.btn_add.clicked.connect(scene.add_shape)
        layout_add.addWidget(scene.btn_add)

        group_add.setLayout(layout_add)
        scene.control_layout.addWidget(group_add)

        # --- Section : Propriétés Géométriques ---
        group_geo = QGroupBox("2. Dimensions & Position")
        layout_geo = QFormLayout()

        # Rayon / Largeur
        scene.spin_radius = QDoubleSpinBox()
        scene.spin_radius.setRange(0.1, 100.0)
        scene.spin_radius.setValue(1.0)
        scene.spin_radius.setSingleStep(0.1)
        scene.spin_radius.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Rayon / Largeur :", scene.spin_radius)

        # Longueur
        scene.spin_length = QDoubleSpinBox()
        scene.spin_length.setRange(0.1, 100.0)
        scene.spin_length.setValue(5.0)
        scene.spin_length.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Longueur :", scene.spin_length)

        # Position X, Y, Z (Pour l'assemblage)
        scene.spin_x = QDoubleSpinBox()
        scene.spin_x.setRange(-100, 100)
        scene.spin_x.valueChanged.connect(scene.update_current_shape)
        scene.spin_y = QDoubleSpinBox()
        scene.spin_y.setRange(-100, 100)
        scene.spin_y.valueChanged.connect(scene.update_current_shape)
        scene.spin_z = QDoubleSpinBox()
        scene.spin_z.setRange(-100, 100)
        scene.spin_z.valueChanged.connect(scene.update_current_shape)

        layout_geo.addRow("Position X :", scene.spin_x)
        layout_geo.addRow("Position Y :", scene.spin_y)
        layout_geo.addRow("Position Z :", scene.spin_z)

        group_geo.setLayout(layout_geo)
        scene.control_layout.addWidget(group_geo)

        # --- Section : Matériau ---
        group_mat = QGroupBox("3. Matériau")
        layout_mat = QVBoxLayout()

        scene.material_selector = QComboBox()
        # Nom, Module de Young (Pa), Couleur
        scene.materials_db = {
            "Acier": (200e9, "grey"),
            "Aluminium": (69e9, "silver"),
            "Bois": (11e9, "tan"),
            "Plastique": (3e9, "lightblue")
        }
        scene.material_selector.addItems(scene.materials_db.keys())
        scene.material_selector.currentTextChanged.connect(
            scene.update_material)

        layout_mat.addWidget(QLabel("Type de matériau :"))
        layout_mat.addWidget(scene.material_selector)

        group_mat.setLayout(layout_mat)
        scene.control_layout.addWidget(group_mat)

        # --- Section : Simulation ---
        scene.btn_sim = QPushButton("Lancer Simulation (Calcul SciPy)")
        scene.btn_sim.setStyleSheet(
            "background-color: #ffcccc; font-weight: bold; padding: 10px;")
        scene.btn_sim.clicked.connect(scene.run_dummy_simulation)
        scene.control_layout.addWidget(scene.btn_sim)

        scene.control_layout.addStretch()

    def add_shape(scene):
        """Ajoute une nouvelle forme à la scène"""
        shape_type = scene.shape_selector.currentText()

        # On crée un dictionnaire pour stocker les infos de l'objet
        obj_data = {
            "type": shape_type,
            "mesh": None,
            "actor": None,
            "params": {
                "radius": scene.spin_radius.value(),
                "length": scene.spin_length.value(),
                "center": (scene.spin_x.value(), scene.spin_y.value(), scene.spin_z.value())
            }
        }

        scene.objects.append(obj_data)
        scene.draw_shape(obj_data)

    def draw_shape(scene, obj_data):
        """Génère le maillage PyVista et l'affiche"""
        # Nettoyer l'ancien acteur si on met à jour
        if obj_data["actor"]:
            scene.plotter.remove_actor(obj_data["actor"])

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
            # On utilise rayon comme demi-largeur
            r = obj_data["params"]["radius"]
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
        mat_name = scene.material_selector.currentText()
        color = scene.materials_db[mat_name][1]

        # Ajouter à la scène
        actor = scene.plotter.add_mesh(mesh, color=color, show_edges=True)

        # Mettre à jour les références
        obj_data["mesh"] = mesh
        obj_data["actor"] = actor
        scene.current_actor = obj_data  # Le dernier objet modifié est celui-ci

    def update_current_shape(scene):
        """Appelé quand on bouge les sliders"""
        if not scene.objects:
            return

        # On modifie le DERNIER objet ajouté (pour l'exemple)
        # Idéalement, il faudrait une liste pour sélectionner quel objet modifier
        current_obj = scene.objects[-1]

        current_obj["params"]["radius"] = scene.spin_radius.value()
        current_obj["params"]["length"] = scene.spin_length.value()
        current_obj["params"]["center"] = (
            scene.spin_x.value(), scene.spin_y.value(), scene.spin_z.value())

        scene.draw_shape(current_obj)

    def update_material(scene):
        """Change la couleur selon le matériau"""
        if scene.objects:
            scene.draw_shape(scene.objects[-1])

    def run_dummy_simulation(scene):
        """C'est ici que tu connecteras ton code SciPy plus tard"""
        if not scene.objects:
            return

        QMessageBox.information(scene, "Simulation",
                                "Calcul de la matrice de rigidité K en cours...\n"
                                "Application des forces...\n"
                                "Résolution F = K * u avec SciPy...")

        # Simulation visuelle : Changer la couleur en "Stress Map" (Von Mises fictif)
        last_obj = scene.objects[-1]
        mesh = last_obj["mesh"]

        # On invente des données de stress pour l'exemple
        # Dans ton vrai projet, ça viendra de tes calculs matriciels
        stress_values = np.linspace(0, 100, mesh.n_points)

        scene.plotter.remove_actor(last_obj["actor"])
        scene.plotter.add_mesh(mesh, scalars=stress_values,
                               cmap="jet", show_edges=False)
        scene.plotter.add_scalar_bar(title="Contrainte de Von Mises (MPa)")


# permet d'utiliser les fonctions du main sans ouvrir la fenêtre (l'interface)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterialSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
