import sys
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox,
                               QPushButton, QGroupBox, QFormLayout, QMessageBox)
from SafeQtInteractor import SafeQtInteractor
from Formes import Cube, Cylindre, PoutreCarree, PrismeTriangulaire, Sphere, Vis
from Environnement import Sol, Gravite

FORMES_DISPONIBLES = {
    cls.NOM: cls
    for cls in [Cylindre, PoutreCarree, PrismeTriangulaire, Sphere, Cube, Vis]
}
class MaterielSimulationApp(QMainWindow):

    def __init__(scene):
        super().__init__()

        scene.setWindowTitle("Tensor Build - Simulateur de Structure")
        scene.resize(1200, 800)

        scene.central_widget = QWidget()
        scene.setCentralWidget(scene.central_widget)
        scene.layout = QHBoxLayout(scene.central_widget)

        # Zone 3D (gauche)
        scene.plotter = SafeQtInteractor(scene.central_widget)
        scene.plotter.set_background("white")
        scene.plotter.add_axes()
        scene.sol = Sol(scene.plotter)
        scene.sol.afficher()
        scene.gravite = Gravite(g=9.81)
        scene.layout.addWidget(scene.plotter.interactor, stretch=2)

        # Panneau de contrôle (droite)
        scene.control_panel = QWidget()
        scene.control_layout = QVBoxLayout(scene.control_panel)
        scene.layout.addWidget(scene.control_panel, stretch=1)

        scene.setup_ui_controls()

        # Liste d'objets Forme
        scene.objects = []

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def setup_ui_controls(scene):

        # --- 1. Ajouter une forme ---
        group_add = QGroupBox("1. Ajouter une Pièce")
        layout_add = QVBoxLayout()

        scene.shape_selector = QComboBox()
        scene.shape_selector.addItems(FORMES_DISPONIBLES.keys())
        layout_add.addWidget(QLabel("Forme :"))
        layout_add.addWidget(scene.shape_selector)

        scene.btn_add = QPushButton("Ajouter à la scène")
        scene.btn_add.clicked.connect(scene.add_shape)
        layout_add.addWidget(scene.btn_add)

        group_add.setLayout(layout_add)
        scene.control_layout.addWidget(group_add)

        # --- 2. Dimensions & Position ---
        group_geo = QGroupBox("2. Dimensions & Position")
        layout_geo = QFormLayout()

        scene.spin_radius = QDoubleSpinBox()
        scene.spin_radius.setRange(0.1, 1000.0)
        scene.spin_radius.setValue(1.0)
        scene.spin_radius.setSingleStep(0.1)
        scene.spin_radius.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Rayon / Largeur :", scene.spin_radius)

        scene.spin_length = QDoubleSpinBox()
        scene.spin_length.setRange(0.1, 1000.0)
        scene.spin_length.setValue(5.0)
        scene.spin_length.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Longueur :", scene.spin_length)

        scene.spin_x = QDoubleSpinBox()
        scene.spin_x.setRange(-1000, 1000)
        scene.spin_x.valueChanged.connect(scene.update_current_shape)
        scene.spin_y = QDoubleSpinBox()
        scene.spin_y.setRange(-1000, 1000)
        scene.spin_y.valueChanged.connect(scene.update_current_shape)
        scene.spin_z = QDoubleSpinBox()
        scene.spin_z.setRange(-1000, 1000)
        scene.spin_z.valueChanged.connect(scene.update_current_shape)

        layout_geo.addRow("Position X :", scene.spin_x)
        layout_geo.addRow("Position Y :", scene.spin_y)
        layout_geo.addRow("Position Z :", scene.spin_z)

        group_geo.setLayout(layout_geo)
        scene.control_layout.addWidget(group_geo)

        # --- 3. Matériau ---
        group_mat = QGroupBox("3. Matériau")
        layout_mat = QVBoxLayout()

        scene.selecteur_materiaux = QComboBox()
        scene.materials_db = {
            "Acier": (200e9, "grey"),
            "Aluminium": (69e9, "silver"),
            "Bois": (11e9, "tan"),
            "Plastique": (3e9, "lightblue"),
        }
        scene.selecteur_materiaux.addItems(scene.materials_db.keys())
        scene.selecteur_materiaux.currentTextChanged.connect(scene.update_materiel)

        layout_mat.addWidget(QLabel("Type de matériau :"))
        layout_mat.addWidget(scene.selecteur_materiaux)

        group_mat.setLayout(layout_mat)
        scene.control_layout.addWidget(group_mat)

        # --- Simulation ---
        scene.btn_sim = QPushButton("Lancer Simulation (Calcul SciPy)")
        scene.btn_sim.setStyleSheet(
            "background-color: #ffcccc; font-weight: bold; padding: 10px;")
        scene.btn_sim.clicked.connect(scene.run_dummy_simulation)
        scene.control_layout.addWidget(scene.btn_sim)

        # --- 4. Effacer une forme ---
        group_erase = QGroupBox("4. Effacer une Pièce")
        layout_erase = QVBoxLayout()

        scene.btn_erase = QPushButton("Mode Effacer : OFF")
        scene.btn_erase.setCheckable(True)
        scene.btn_erase.setStyleSheet(
            "background-color: #dddddd; font-weight: bold; padding: 8px;")
        scene.btn_erase.toggled.connect(scene.toggle_erase_mode)
        layout_erase.addWidget(scene.btn_erase)

        scene.erase_label = QLabel("Clique sur une forme pour l'effacer.")
        scene.erase_label.setVisible(False)
        layout_erase.addWidget(scene.erase_label)

        group_erase.setLayout(layout_erase)
        scene.control_layout.addWidget(group_erase)

        # --- 5. Vue de la résistance ---
        group_resistance = QGroupBox("5. Vue de la Résistance")
        layout_resistance = QVBoxLayout()

        scene.btn_resistance = QPushButton("Afficher les contraintes")
        scene.btn_resistance.setStyleSheet(
            "background-color: #cce5ff; font-weight: bold; padding: 8px;")
        scene.btn_resistance.clicked.connect(scene.afficher_resistance)
        layout_resistance.addWidget(scene.btn_resistance)

        scene.btn_resistance_reset = QPushButton("Réinitialiser les couleurs")
        scene.btn_resistance_reset.setStyleSheet(
            "background-color: #dddddd; font-weight: bold; padding: 8px;")
        scene.btn_resistance_reset.clicked.connect(scene.reinitialiser_couleurs)
        layout_resistance.addWidget(scene.btn_resistance_reset)

        group_resistance.setLayout(layout_resistance)
        scene.control_layout.addWidget(group_resistance)

        scene.control_layout.addStretch()  # toujours en dernier

    # ------------------------------------------------------------------ #
    #  Ajouter / Dessiner                                                  #
    # ------------------------------------------------------------------ #

    def add_shape(scene):
        """Instancie la bonne classe de forme et l'ajoute à la scène."""
        nom = scene.shape_selector.currentText()
        classe = FORMES_DISPONIBLES[nom]

        params = {
            "rayon": scene.spin_radius.value(),
            "longueur": scene.spin_length.value(),
            "centre": (scene.spin_x.value(),
                       scene.spin_y.value(),
                       scene.spin_z.value()),
        }

        forme = classe(params)
        scene.objects.append(forme)
        scene.dessiner_forme(forme)

    def dessiner_forme(scene, forme):
        """Construit le mesh via la classe et l'affiche dans le plotter."""
        if forme.actor:
            scene.plotter.remove_actor(forme.actor)

        forme.mesh = forme.construire_mesh()

        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        forme.actor = scene.plotter.add_mesh(forme.mesh, color=color, show_edges=True)

    # ------------------------------------------------------------------ #
    #  Mise à jour                                                         #
    # ------------------------------------------------------------------ #

    def update_current_shape(scene):
        """Met à jour le dernier objet quand on change les spinbox."""
        if not scene.objects:
            return
        forme = scene.objects[-1]
        forme.params["rayon"] = scene.spin_radius.value()
        forme.params["longueur"] = scene.spin_length.value()
        forme.params["centre"] = (scene.spin_x.value(),
                                  scene.spin_y.value(),
                                  scene.spin_z.value())
        scene.dessiner_forme(forme)

    def update_materiel(scene):
        """Recolore le dernier objet selon le matériau choisi."""
        if scene.objects:
            scene.dessiner_forme(scene.objects[-1])

    # ------------------------------------------------------------------ #
    #  Simulation                                                          #
    # ------------------------------------------------------------------ #

    def run_dummy_simulation(scene):
        if not scene.objects:
            return

        mat_name = scene.selecteur_materiaux.currentText()
        rapport = scene.gravite.rapport_complet(scene.objects, mat_name)
        QMessageBox.information(scene, "Simulation", rapport)

        # Anime la chute de toutes les formes
        for forme in scene.objects:
            scene.animer_chute(forme)

    def animer_chute(scene, forme):
        """Anime la forme qui tombe vers Z=0 (le sol)."""
        import time

        z_actuel = forme.params["centre"][2]
        z_sol = 0.0  # hauteur du sol
        nb_frames = 60  # nombre d'étapes de l'animation
        vitesse = 0.3  # m/s² simulé (purement visuel)

        for i in range(nb_frames):
            # Calcule la nouvelle position Z avec accélération
            t = i / nb_frames
            z_nouv = z_actuel - (z_actuel - z_sol) * (t ** 2)

            # Stop si on touche le sol
            if z_nouv <= z_sol:
                z_nouv = z_sol

            # Met à jour la position et redessine
            forme.params["centre"] = (
                forme.params["centre"][0],
                forme.params["centre"][1],
                z_nouv
            )
            scene.dessiner_forme(forme)
            scene.plotter.render()
            time.sleep(0.016)  # ~60 fps

            if z_nouv <= z_sol:
                break

    # ------------------------------------------------------------------ #
    #  Mode Effacer                                                        #
    # ------------------------------------------------------------------ #

    def toggle_erase_mode(scene, active):
        if active:
            scene.btn_erase.setText("Mode Effacer : ON")
            scene.btn_erase.setStyleSheet(
                "background-color: #ff6666; color: white; font-weight: bold; padding: 8px;")
            scene.erase_label.setVisible(True)
            scene.plotter.enable_mesh_picking(
                callback=scene.on_pick,
                use_mesh=True,
                show=False,
                left_clicking=True,
                show_message=False,
            )
        else:
            scene.btn_erase.setText("Mode Effacer : OFF")
            scene.btn_erase.setStyleSheet(
                "background-color: #dddddd; font-weight: bold; padding: 8px;")
            scene.erase_label.setVisible(False)
            scene.plotter.disable_picking()

    def on_pick(scene, picked_mesh):
        if picked_mesh is None:
            return
        for forme in scene.objects:
            if forme.mesh is picked_mesh:
                scene.plotter.remove_actor(forme.actor)
                scene.objects.remove(forme)
                break

    def afficher_resistance(scene):
        """Affiche la carte de contraintes sur toutes les formes."""
        if not scene.objects:
            return

        for forme in scene.objects:
            mesh = forme.mesh
            stress_values = np.linspace(0, 100, mesh.n_points)

            scene.plotter.remove_actor(forme.actor)
            forme.actor = scene.plotter.add_mesh(
                mesh,
                scalars=stress_values,
                cmap="jet",
                show_edges=False
            )

        scene.plotter.add_scalar_bar(title="Contrainte de Von Mises (MPa)")

    def reinitialiser_couleurs(scene):
        """Remet les couleurs originales du matériau sur toutes les formes."""
        if not scene.objects:
            return

        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        for forme in scene.objects:
            scene.plotter.remove_actor(forme.actor)
            forme.actor = scene.plotter.add_mesh(
                forme.mesh,
                color=color,
                show_edges=True
            )


# ================================================================== #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterielSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())