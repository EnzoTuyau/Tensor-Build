import sys
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox,
                               QPushButton, QGroupBox, QFormLayout, QMessageBox)
from .SafeQtInteractor import SafeQtInteractor
from .Camera import Camera
from ..Environnement import Sol, Gravite
from ..Formes import Cube, Cylindre, PoutreCarree, PrismeTriangulaire, Sphere, Vis

FORMES_DISPONIBLES = {
    cls.NOM: cls
    for cls in [Cylindre, PoutreCarree, PrismeTriangulaire, Sphere, Cube, Vis]
}


class MaterielSimulationApp(QMainWindow):

    def __init__(scene, switch_callback=None):
        super().__init__()
        scene.switch_callback = switch_callback
        scene.showMaximized()


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
        scene.sol.afficher()
        scene.camera = Camera(scene.plotter)
        scene.camera.initialiser()
        # Branche les touches WASD
        scene.plotter.add_key_event("w", lambda: scene.camera.pan("haut"))
        scene.plotter.add_key_event("s", lambda: scene.camera.pan("bas"))
        scene.plotter.add_key_event("a", lambda: scene.camera.pan("gauche"))
        scene.plotter.add_key_event("d", lambda: scene.camera.pan("droite"))
        scene.gravite = Gravite(g=9.81)
        scene.layout.addWidget(scene.plotter.interactor, stretch=2)

        # Panneau de contrôle (droite)
        scene.control_panel = QWidget()
        scene.control_layout = QVBoxLayout(scene.control_panel)
        scene.layout.addWidget(scene.control_panel, stretch=1)

        scene.setup_ui_controls()
        scene.setStyleSheet("""
            QMainWindow, QWidget { background: #050607; color: #eaf2ff; }
            QGroupBox {
                color: #dbe8ff;
                border: 1px solid #223753;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 6px;
                font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #9ec8ff; }
            QLabel { color: #dbe8ff; }
            QComboBox, QDoubleSpinBox {
                background: #0f1723;
                color: #eaf2ff;
                border: 1px solid #2f4d72;
                border-radius: 4px;
                padding: 2px;
            }
            QPushButton {
                background: #0d8bff;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2c9bff; }
        """)

        # Liste d'objets Forme
        scene.objects = []

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def setup_ui_controls(scene):
        # --- Retour mode 2D ---
        scene.btn_switch_2d = QPushButton("🖥️  Retourner en mode 2D")
        scene.btn_switch_2d.setStyleSheet(
            "background-color: #1565c0; color: white; font-size: 12px; padding: 8px;"
        )
        if scene.switch_callback is not None:
            scene.btn_switch_2d.clicked.connect(scene.switch_callback)
        else:
            scene.btn_switch_2d.setEnabled(False)
        scene.control_layout.addWidget(scene.btn_switch_2d)

        # --- 1. Ajouter une forme ---
        group_add = QGroupBox("1. Ajouter une Pièce")
        layout_add = QVBoxLayout()

        scene.forme_selectionnee = None
        scene.shape_selector = QComboBox()
        scene.shape_selector.addItem("Choisir une forme")
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
        scene.selecteur_materiaux.currentTextChanged.connect(
            scene.update_materiel)

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
        scene.btn_resistance_reset.clicked.connect(
            scene.reinitialiser_couleurs)
        layout_resistance.addWidget(scene.btn_resistance_reset)

        group_resistance.setLayout(layout_resistance)
        scene.control_layout.addWidget(group_resistance)

        # --- 6. Inspecter une forme ---
        group_inspect = QGroupBox("6. Inspecter une Pièce")
        layout_inspect = QVBoxLayout()

        scene.btn_inspect = QPushButton("Mode Inspecter : OFF")
        scene.btn_inspect.setCheckable(True)
        scene.btn_inspect.setStyleSheet(
            "background-color: #dddddd; font-weight: bold; padding: 8px;")
        scene.btn_inspect.toggled.connect(scene.toggle_inspect_mode)
        layout_inspect.addWidget(scene.btn_inspect)

        group_inspect.setLayout(layout_inspect)
        scene.control_layout.addWidget(group_inspect)

        # --- 7. Position caméra ---
        group_cam = QGroupBox("7. Position Caméra")
        layout_cam = QVBoxLayout()

        scene.label_cam_pos = QLabel("x=0, y=0, z=0")
        layout_cam.addWidget(scene.label_cam_pos)

        group_cam.setLayout(layout_cam)
        scene.control_layout.addWidget(group_cam)

        group_geo.setEnabled(False)  # grisé au départ
        scene.group_geo = group_geo  # garde une référence

        scene.shape_selector.currentIndexChanged.connect(
            scene.on_forme_choisie)

        scene.control_layout.addStretch()  # toujours en dernier

    # ------------------------------------------------------------------ #
    #  Ajouter / Dessiner                                                  #
    # ------------------------------------------------------------------ #

    def add_shape(scene):
        nom = scene.shape_selector.currentText()
        if nom not in FORMES_DISPONIBLES:
            return

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
        scene.forme_selectionnee = forme  # ← pointe sur la nouvelle forme

        # Remet le sélecteur à 0 SANS déclencher on_forme_choisie
        scene.shape_selector.blockSignals(True)
        scene.shape_selector.setCurrentIndex(0)
        scene.shape_selector.blockSignals(False)

        # Garde le groupe dimensions actif et la forme surlignée
        scene.group_geo.setEnabled(True)
        scene.plotter.remove_actor(forme.actor)
        forme.actor = scene.plotter.add_mesh(
            forme.mesh, color="yellow", show_edges=True, reset_camera=False)
        scene.camera.activer_suivi(forme.params["centre"])

    def dessiner_forme(scene, forme):
        scene.camera.sauvegarder()  # ← sauvegarde avant

        if forme.actor:
            scene.plotter.remove_actor(forme.actor)

        forme.mesh = forme.construire_mesh()
        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        forme.actor = scene.plotter.add_mesh(
            forme.mesh,
            color=color,
            show_edges=True,
            reset_camera=False
        )

        scene.camera.restaurer()  # ← restaure après

    # ------------------------------------------------------------------ #
    #  Mise à jour                                                         #
    # ------------------------------------------------------------------ #

    def update_current_shape(scene):
        forme = scene.forme_selectionnee
        if forme is None:
            return

        nouvelle_pos = (scene.spin_x.value(),
                        scene.spin_y.value(),
                        scene.spin_z.value())

        scene.camera.suivre_objet(nouvelle_pos)  # ← déplace la caméra avant

        forme.params["rayon"] = scene.spin_radius.value()
        forme.params["longueur"] = scene.spin_length.value()
        forme.params["centre"] = nouvelle_pos
        scene.dessiner_forme(forme)

        scene.plotter.remove_actor(forme.actor)
        forme.actor = scene.plotter.add_mesh(
            forme.mesh, color="yellow", show_edges=True, reset_camera=False)

    def update_materiel(scene):
        """Recolore uniquement la forme sélectionnée."""
        if scene.forme_selectionnee is None:
            return  # aucune forme active, on ne touche à rien

        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]
        scene.plotter.remove_actor(scene.forme_selectionnee.actor)
        scene.forme_selectionnee.actor = scene.plotter.add_mesh(
            scene.forme_selectionnee.mesh, color=color, show_edges=True)

        # Remet le surlignage jaune si c'est la forme en cours d'édition
        scene.plotter.remove_actor(scene.forme_selectionnee.actor)
        scene.forme_selectionnee.actor = scene.plotter.add_mesh(
            scene.forme_selectionnee.mesh, color="yellow", show_edges=True)

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
        import time

        mat_name = scene.selecteur_materiaux.currentText()
        masse = scene.gravite.calculer_masse(forme, mat_name)  # kg
        g = scene.gravite.g  # utilise le g de l'objet Gravite

        z_actuel = forme.params["centre"][2]
        z_sol = -10.0 + forme.r
        nb_frames = 100
        dt = 0.05
        vitesse_z = 0.0

        for i in range(nb_frames):
            vitesse_z += g * dt
            z_nouv = z_actuel - vitesse_z * dt
            z_actuel = z_nouv

            if z_nouv <= z_sol:
                z_nouv = z_sol

            forme.params["centre"] = (
                forme.params["centre"][0],
                forme.params["centre"][1],
                z_nouv
            )
            scene.dessiner_forme(forme)
            scene.plotter.render()
            time.sleep(0.000001)

            if z_nouv <= z_sol:
                break

        # afficher l'énergie d'impact
        energie = 0.5 * masse * vitesse_z ** 2  # E = ½mv²
        QMessageBox.information(
            scene,
            "Impact",
            f"{forme.NOM}\nMasse : {masse:.2f} kg\nÉnergie d'impact : {energie:.2f} J"
        )

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

    # ------------------------------------------------------------------ #
    #  Mode données sur la forme                                         #
    # ------------------------------------------------------------------ #

    def toggle_inspect_mode(scene, active):
        if active:
            scene.btn_inspect.setText("Mode Inspecter : ON")
            scene.btn_inspect.setStyleSheet(
                "background-color: #66bb66; color: white; font-weight: bold; padding: 8px;")
            scene.plotter.enable_mesh_picking(
                callback=scene.on_inspect,
                use_mesh=True,
                show=False,
                left_clicking=True,
                show_message=False,
            )
        else:
            scene.btn_inspect.setText("Mode Inspecter : OFF")
            scene.btn_inspect.setStyleSheet(
                "background-color: #dddddd; font-weight: bold; padding: 8px;")
            scene.plotter.disable_picking()

    def on_inspect(scene, picked_mesh):
        if picked_mesh is None:
            return
        for forme in scene.objects:
            if forme.mesh is picked_mesh:
                scene.forme_selectionnee = forme

                # Surligne en jaune la forme sélectionnée
                for f in scene.objects:
                    mat_name = scene.selecteur_materiaux.currentText()
                    color = scene.materials_db[mat_name][1]
                    scene.plotter.remove_actor(f.actor)
                    f.actor = scene.plotter.add_mesh(
                        f.mesh, color=color, show_edges=True)

                scene.plotter.remove_actor(forme.actor)
                forme.actor = scene.plotter.add_mesh(
                    forme.mesh, color="yellow", show_edges=True)

                # Bloque les signaux
                for spin in [scene.spin_radius, scene.spin_length,
                             scene.spin_x, scene.spin_y, scene.spin_z]:
                    spin.blockSignals(True)

                scene.spin_radius.setValue(forme.r)
                scene.spin_length.setValue(forme.l)
                scene.spin_x.setValue(forme.c[0])
                scene.spin_y.setValue(forme.c[1])
                scene.spin_z.setValue(forme.c[2])

                for spin in [scene.spin_radius, scene.spin_length,
                             scene.spin_x, scene.spin_y, scene.spin_z]:
                    spin.blockSignals(False)
                break
        scene.camera.activer_suivi(forme.params["centre"])

    def on_forme_choisie(scene, index):
        scene.camera.desactiver_suivi()
        if index == 0:
            scene.group_geo.setEnabled(False)
            scene.forme_selectionnee = None
        else:
            # Remet la couleur normale sur l'ancienne forme sélectionnée
            if scene.forme_selectionnee is not None:
                mat_name = scene.selecteur_materiaux.currentText()
                color = scene.materials_db[mat_name][1]
                scene.plotter.remove_actor(scene.forme_selectionnee.actor)
                scene.forme_selectionnee.actor = scene.plotter.add_mesh(
                    scene.forme_selectionnee.mesh, color=color, show_edges=True)
                scene.forme_selectionnee = None

            scene.group_geo.setEnabled(True)


# ================================================================== #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterielSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
