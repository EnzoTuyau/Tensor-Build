import sys
import time
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox,
                               QPushButton, QGroupBox, QFormLayout, QMessageBox)
from PySide6.QtCore import QEvent
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

        scene.setWindowTitle("Tensor Build - Simulateur de Structure")
        scene.resize(1200, 800)

        scene.central_widget = QWidget()
        scene.setCentralWidget(scene.central_widget)
        scene.layout = QHBoxLayout(scene.central_widget)

        # Zone 3D (gauche)
        scene.plotter = SafeQtInteractor(scene.central_widget)
        scene.plotter.set_background("#0a1018")
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
        scene.gravite = Gravite()
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
            QPushButton[variant="secondary"] {
                background: #0d8bff;
                color: #ffffff;
                border: none;
            }
            QPushButton[variant="secondary"]:hover { background: #2c9bff; }
            QPushButton[variant="danger"] { background: #9b2432; color: #ffffff; border: none; }
            QPushButton[variant="danger"]:hover { background: #b12b3a; }
            QPushButton[variant="success"] { background: #2e7d32; color: #ffffff; border: none; }
            QPushButton[variant="success"]:hover { background: #3f9144; }
            QPushButton[variant="launch"] { background: #e67e22; color: #ffffff; border: none; }
            QPushButton[variant="launch"]:hover { background: #f08f35; }
            QPushButton:disabled { background: #4d5662; color: #c3c8cf; }
        """)

        # Liste d'objets Forme
        scene.objects = []
        scene._resize_drag_active = False
        scene._resize_drag_last_y = None
        scene.plotter.interactor.installEventFilter(scene)
        scene._refresh_action_buttons()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def setup_ui_controls(scene):
        # --- Retour mode 2D ---
        scene.btn_switch_2d = QPushButton("Retourner en mode 2D")
        scene.btn_switch_2d.setProperty("variant", "launch")
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
        scene.btn_sim = QPushButton("Lancer simulation")
        scene.btn_sim.setProperty("variant", "success")
        scene.btn_sim.clicked.connect(scene.run_dummy_simulation)
        scene.control_layout.addWidget(scene.btn_sim)

        # --- 4. Effacer une forme ---
        group_erase = QGroupBox("4. Effacer une Pièce")
        layout_erase = QVBoxLayout()

        scene.btn_erase = QPushButton("Mode Effacer : OFF")
        scene.btn_erase.setCheckable(True)
        scene.btn_erase.setProperty("variant", "secondary")
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
        scene.btn_resistance.setProperty("variant", "secondary")
        scene.btn_resistance.clicked.connect(scene.afficher_resistance)
        layout_resistance.addWidget(scene.btn_resistance)

        scene.btn_resistance_reset = QPushButton("Réinitialiser les couleurs")
        scene.btn_resistance_reset.setProperty("variant", "secondary")
        scene.btn_resistance_reset.clicked.connect(scene.reinitialiser_couleurs)
        layout_resistance.addWidget(scene.btn_resistance_reset)

        group_resistance.setLayout(layout_resistance)
        scene.control_layout.addWidget(group_resistance)

        # --- 6. Inspecter une forme ---
        group_inspect = QGroupBox("6. Inspecter une Pièce")
        layout_inspect = QVBoxLayout()

        scene.btn_inspect = QPushButton("Mode Inspecter : OFF")
        scene.btn_inspect.setCheckable(True)
        scene.btn_inspect.setProperty("variant", "secondary")
        scene.btn_inspect.toggled.connect(scene.toggle_inspect_mode)
        layout_inspect.addWidget(scene.btn_inspect)

        group_inspect.setLayout(layout_inspect)
        scene.control_layout.addWidget(group_inspect)


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
        scene._refresh_action_buttons()

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

    def eventFilter(scene, obj, event):
        if obj is scene.plotter.interactor:
            # Clic DROIT pour redimensionner (libère le clic gauche pour la caméra)
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == 2 and scene.forme_selectionnee is not None:
                    scene._resize_drag_active = True
                    scene._resize_drag_last_y = event.position().y()
                    return True
            elif event.type() == QEvent.MouseMove and scene._resize_drag_active:
                y_now = event.position().y()
                dy = scene._resize_drag_last_y - y_now
                if abs(dy) >= 1:
                    facteur = 1.0 + (dy * 0.008)
                    facteur = max(0.2, min(5.0, facteur))
                    forme = scene.forme_selectionnee
                    new_r = max(0.1, forme.params["rayon"] * facteur)
                    new_l = max(0.1, forme.params["longueur"] * facteur)
                    forme.params["rayon"] = new_r
                    forme.params["longueur"] = new_l
                    scene.spin_radius.blockSignals(True)
                    scene.spin_length.blockSignals(True)
                    scene.spin_radius.setValue(new_r)
                    scene.spin_length.setValue(new_l)
                    scene.spin_radius.blockSignals(False)
                    scene.spin_length.blockSignals(False)
                    scene.dessiner_forme(forme)
                    scene.plotter.remove_actor(forme.actor)
                    forme.actor = scene.plotter.add_mesh(
                        forme.mesh, color="yellow", show_edges=True, reset_camera=False)
                    scene._resize_drag_last_y = y_now
                return True
            elif event.type() == QEvent.MouseButtonRelease and scene._resize_drag_active:
                scene._resize_drag_active = False
                scene._resize_drag_last_y = None
                return True

        return super().eventFilter(obj, event)

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

        # Anime la chute de toutes les formes avec une boucle à FPS stable.
        scene.animer_chute(scene.objects)

    #---- Collision entre formes  ----#
    def _detecter_collisions(scene, etats):

        for i, etat_a in enumerate(etats):
            for j, etat_b in enumerate(etats):
                if i >= j:
                    continue
                
                forme_a = etat_a["forme"]
                forme_b = etat_b["forme"]
                
                cx_a, cy_a = forme_a.params["centre"][0], forme_a.params["centre"][1]
                cx_b, cy_b = forme_b.params["centre"][0], forme_b.params["centre"][1]
                
                # Distance horizontale entre les deux formes
                dist_horiz = ((cx_a - cx_b)**2 + (cy_a - cy_b)**2) ** 0.5
                dist_min = forme_a.r + forme_b.r  # somme des rayons
                
                # Distance verticale entre bas de A et haut de B
                bas_a = etat_a["z"] - forme_a.l / 2
                haut_b = etat_b["z"] + forme_b.l / 2
                bas_b = etat_b["z"] - forme_b.l / 2
                haut_a = etat_a["z"] + forme_a.l / 2
                
                # Collision si chevauchement horizontal ET vertical
                chevauchement_horiz = dist_horiz < dist_min
                chevauchement_vert = bas_a < haut_b and haut_a > bas_b
                
                if chevauchement_horiz and chevauchement_vert:
                    # Échange des vitesses (collision élastique simplifiée)
                    m_a = etat_a["masse"]
                    m_b = etat_b["masse"]
                    v_a = etat_a["vitesse_z"]
                    v_b = etat_b["vitesse_z"]
                    
                    # Conservation de la quantité de mouvement
                    etat_a["vitesse_z"] = (v_a * (m_a - m_b) + 2 * m_b * v_b) / (m_a + m_b)
                    etat_b["vitesse_z"] = (v_b * (m_b - m_a) + 2 * m_a * v_a) / (m_a + m_b)

        #------ Animation de la chute libre avec gestion du temps -----#

    def animer_chute(scene, formes):
        mat_name = scene.selecteur_materiaux.currentText()
        g = scene.gravite.g
        target_fps = 60.0
        dt_cible = 1.0 / target_fps

        positions_initiales = {
            id(forme): forme.params["centre"]
            for forme in formes
        }

        etats = []
        for forme in formes:
            etats.append({
                "forme": forme,
                "masse": scene.gravite.calculer_masse(forme, mat_name),
                "z": forme.params["centre"][2],
                "z_sol": -10.0 + forme.r,
                "vitesse_z": 0.0,
                "termine": False,
            })

        impacts = []
        dernier_t = time.perf_counter()
        frame_count = 0
        CONTRAINTES_INTERVAL = 5

        while not all(etat["termine"] for etat in etats):
            frame_start = time.perf_counter()
            dt = min(0.05, frame_start - dernier_t)
            if dt <= 0:
                dt = dt_cible
            dernier_t = frame_start

            # Physique
            for etat in etats:
                if etat["termine"]:
                    continue
                forme = etat["forme"]
                etat["vitesse_z"] += g * dt
                nouvelle_z = etat["z"] - etat["vitesse_z"] * dt

                if nouvelle_z <= etat["z_sol"]:
                    nouvelle_z = etat["z_sol"]
                    etat["termine"] = True
                    etat["vitesse_z"] *= -0.3
                    energie = 0.5 * etat["masse"] * (etat["vitesse_z"] ** 2)
                    impacts.append((forme.NOM, etat["masse"], energie))

                dz = nouvelle_z - etat["z"]
                etat["z"] = nouvelle_z
                forme.params["centre"] = (
                    forme.params["centre"][0],
                    forme.params["centre"][1],
                    nouvelle_z,
                )
                if forme.mesh is not None:
                    forme.mesh.translate((0.0, 0.0, dz), inplace=True)

            # Collisions forme-forme
            scene._detecter_collisions(etats)

            # ← tout ce bloc DOIT être dans le while
            frame_count += 1
            if frame_count % CONTRAINTES_INTERVAL == 0:
                for etat in etats:
                    forme = etat["forme"]
                    mesh = forme.mesh
                    if mesh is None:
                        continue
                    points = mesh.points
                    masse = etat["masse"]
                    poids = masse * g
                    aire = 3.14159 * forme.r ** 2
                    contrainte_max = poids / aire
                    z_points = points[:, 2]
                    z_min, z_max = z_points.min(), z_points.max()
                    if z_max > z_min:
                        z_norm = 1.0 - (z_points - z_min) / (z_max - z_min)
                    else:
                        z_norm = np.ones(len(z_points))
                    facteur_impact = 1.0 + abs(etat["vitesse_z"]) * 0.1
                    stress_values = (z_norm * contrainte_max * facteur_impact) / 1e6
                    scene.plotter.remove_actor(forme.actor)
                    forme.actor = scene.plotter.add_mesh(
                        mesh,
                        scalars=stress_values,
                        cmap="coolwarm",
                        show_edges=False,
                        reset_camera=False,
                        clim=[0, max(stress_values.max(), 0.001)]
                    )

            scene.plotter.render()
            QApplication.processEvents()

            reste = dt_cible - (time.perf_counter() - frame_start)
            if reste > 0:
                time.sleep(reste)

        if impacts:
            lignes = [
                f"{nom} — {masse:.2f} kg | {energie:.2f} J"
                for nom, masse, energie in impacts
            ]
            QMessageBox.information(scene, "Impact", "\n".join(lignes))

        for forme in formes:
            pos_init = positions_initiales[id(forme)]
            forme.params["centre"] = pos_init
            forme.mesh = None
            scene.dessiner_forme(forme)

    #---- méthodes pour la vue de résistance -----#
    
    def afficher_resistance(scene):
        if not scene.objects:
            return

        mat_name = scene.selecteur_materiaux.currentText()

        for forme in scene.objects:
            mesh = forme.mesh
            points = mesh.points  # tableau numpy (N, 3) des points du mesh

            # --- Calcul physique ---
            masse = scene.gravite.calculer_masse(forme, mat_name)
            poids = masse * scene.gravite.g          # F = mg (N)
            aire = 3.14159 * forme.r ** 2            # section transversale (m²)
            contrainte_max = poids / aire            # σ = F/A (Pa)

            # --- Distribution réaliste selon Z ---
            # Plus bas dans l'objet = plus de contrainte (supporte le poids du dessus)
            z_points = points[:, 2]
            z_min = z_points.min()
            z_max = z_points.max()

            if z_max > z_min:
                # Normalise Z : bas = 1.0 (max contrainte), haut = 0.0 (min contrainte)
                z_norm = 1.0 - (z_points - z_min) / (z_max - z_min)
            else:
                z_norm = np.ones(len(z_points))

            # Ajoute variation radiale : centre sous plus de compression que les bords
            centre_x = points[:, 0].mean()
            centre_y = points[:, 1].mean()
            dist_radiale = np.sqrt(
                (points[:, 0] - centre_x) ** 2 +
                (points[:, 1] - centre_y) ** 2
            )
            r_max = dist_radiale.max() if dist_radiale.max() > 0 else 1.0
            r_norm = 1.0 - (dist_radiale / r_max) * 0.3  # centre +30% de contrainte

            # Contrainte finale en MPa
            stress_values = (z_norm * r_norm * contrainte_max) / 1e6

            scene.plotter.remove_actor(forme.actor)
            forme.actor = scene.plotter.add_mesh(
                mesh,
                scalars=stress_values,
                cmap="coolwarm",       # bleu = faible, rouge = élevé
                show_edges=False,
                reset_camera=False,
                clim=[0, stress_values.max() if stress_values.max() > 0 else 1]
            )

        scene.plotter.add_scalar_bar(
            title="Contrainte de compression (MPa)",
            color="white"
        )

    # ------------------------------------------------------------------ #
    #  Mode Effacer                                                        #
    # ------------------------------------------------------------------ #

    def toggle_erase_mode(scene, active):
        if active:
            scene.btn_erase.setText("Mode Effacer : ON")
            scene.btn_erase.setProperty("variant", "danger")
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
            scene.btn_erase.setProperty("variant", "secondary")
            scene.erase_label.setVisible(False)
            scene.plotter.disable_picking()
        scene.style().unpolish(scene.btn_erase)
        scene.style().polish(scene.btn_erase)

    def on_pick(scene, picked_mesh):
        if picked_mesh is None:
            return
        for forme in scene.objects:
            if forme.mesh is picked_mesh:
                scene.plotter.remove_actor(forme.actor)
                scene.objects.remove(forme)
                if scene.forme_selectionnee is forme:
                    scene.forme_selectionnee = None
                break
        scene._refresh_action_buttons()

    

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
            scene.btn_inspect.setProperty("variant", "success")
            scene.plotter.enable_mesh_picking(
                callback=scene.on_inspect,
                use_mesh=True,
                show=False,
                left_clicking=True,
                show_message=False,
            )
        else:
            scene.btn_inspect.setText("Mode Inspecter : OFF")
            scene.btn_inspect.setProperty("variant", "secondary")
            scene.plotter.disable_picking()
        scene.style().unpolish(scene.btn_inspect)
        scene.style().polish(scene.btn_inspect)

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

    def _refresh_action_buttons(scene):
        """Grise les boutons indisponibles tant qu'il n'y a pas d'objet."""
        has_objects = len(scene.objects) > 0

        if not has_objects:
            if scene.btn_erase.isChecked():
                scene.btn_erase.blockSignals(True)
                scene.btn_erase.setChecked(False)
                scene.btn_erase.blockSignals(False)
                scene.btn_erase.setText("Mode Effacer : OFF")
                scene.btn_erase.setProperty("variant", "secondary")
                scene.erase_label.setVisible(False)

            if scene.btn_inspect.isChecked():
                scene.btn_inspect.blockSignals(True)
                scene.btn_inspect.setChecked(False)
                scene.btn_inspect.blockSignals(False)
                scene.btn_inspect.setText("Mode Inspecter : OFF")
                scene.btn_inspect.setProperty("variant", "secondary")

            scene.plotter.disable_picking()

        scene.btn_sim.setEnabled(has_objects)
        scene.btn_erase.setEnabled(has_objects)
        scene.btn_resistance.setEnabled(has_objects)
        scene.btn_resistance_reset.setEnabled(has_objects)
        scene.btn_inspect.setEnabled(has_objects)

# ================================================================== #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterielSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
