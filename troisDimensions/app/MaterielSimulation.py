import sys
import time
import numpy as np
from PySide6.QtCore import QEvent, Qt
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
        # auto_update=False : sinon QTimer périodique + fermeture = race OpenGL/VTK (macOS).
        scene.plotter = SafeQtInteractor(scene.central_widget, auto_update=False)
        scene.plotter.set_background("#0a1018")
        scene.plotter.add_axes()
        scene.sol = Sol(scene.plotter)
        scene.sol.afficher()
        scene.sol.afficher()
        scene.camera = Camera(scene.plotter)
        scene.camera.initialiser()
        
        
        # Contraint la caméra au-dessus du sol après chaque mouvement souris
        def _on_camera_moved(*args):
            scene.camera._contraindre_au_dessus_sol()

        scene.plotter.interactor.GetInteractorStyle().AddObserver("InteractionEvent", _on_camera_moved)
        
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
                min-height: 24px;
            }

            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
                height: 12px;
                background: #1a3a5c;
                border: none;
                border-left: 1px solid #2f4d72;
                border-bottom: 1px solid #2f4d72;
            }
            QDoubleSpinBox::up-button:hover  { background: #0d8bff; }
            QDoubleSpinBox::up-button:pressed { background: #0a6fd4; }

            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
                height: 12px;
                background: #1a3a5c;
                border: none;
                border-left: 1px solid #2f4d72;
                border-top: 1px solid #2f4d72;
            }
            QDoubleSpinBox::down-button:hover  { background: #0d8bff; }
            QDoubleSpinBox::down-button:pressed { background: #0a6fd4; }

            QDoubleSpinBox::up-arrow {
                width: 0px; height: 0px;
                border-left:  4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #eaf2ff;
            }
            QDoubleSpinBox::down-arrow {
                width: 0px; height: 0px;
                border-left:  4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #eaf2ff;
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
            QPushButton[variant="secondary"] { background: #0d8bff; color: #ffffff; border: none; }
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
        scene._mode_contraintes_actif = False
        scene.plotter.interactor.installEventFilter(scene)
        scene.plotter.interactor.installEventFilter(scene)
        scene.plotter.interactor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # reçoit le focus clavier
        scene.plotter.interactor.setFocus()  # donne le focus immédiatement
        scene._refresh_action_buttons()

    def closeEvent(self, event):
        # Fermer explicitement le QtInteractor (render_timer, BasePlotter, QVTK) avant
        # que Qt ne détruisse l’arbre de widgets : sinon segfault en changeant de mode.
        if hasattr(self, "plotter") and self.plotter is not None:
            try:
                self.plotter.interactor.removeEventFilter(self)
            except RuntimeError:
                pass
            try:
                if not getattr(self.plotter, "_closed", False):
                    self.plotter.close()
            except RuntimeError:
                pass
        super().closeEvent(event)

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
        # Touches WASD pour la caméra
        if event.type() == QEvent.KeyPress:  # retire la condition sur obj
            key = event.text().lower()
            if key == "w":
                scene.camera.pan("haut")
                scene.plotter.render()
                return True
            elif key == "s":
                scene.camera.pan("bas")
                scene.plotter.render()
                return True
            elif key == "a":
                scene.camera.pan("gauche")
                scene.plotter.render()
                return True
            elif key == "d":
                scene.camera.pan("droite")
                scene.plotter.render()
                return True
        if obj is scene.plotter.interactor:            
                
            if event.type() == QEvent.MouseButtonPress and scene.forme_selectionnee is not None:
                if event.button() == 1:  # clic gauche
                    scene._resize_drag_active = True
                    scene._resize_drag_last_y = event.position().y()
                    return True
            elif event.type() == QEvent.MouseMove and scene._resize_drag_active and scene.forme_selectionnee is not None:
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
                scene._mode_contraintes_actif = False 
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

        # Reset à bleu avant chaque simulation si mode contraintes actif
        if scene._mode_contraintes_actif:
            for forme in scene.objects:
                if forme.mesh is None:
                    continue
                scene.plotter.remove_actor(forme.actor)
                forme.actor = scene.plotter.add_mesh(
                    forme.mesh,
                    scalars=np.zeros(forme.mesh.n_points),
                    cmap="coolwarm",
                    show_edges=False,
                    reset_camera=False,
                    clim=[0, 1]
                )
            scene.plotter.render()

        scene.animer_chute(scene.objects)


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
                "energie_totale": 0.0,
                "energie_sol": 0.0,        # onde qui part du bas
                "energie_collision": 0.0,  # onde qui part du haut
            })

        impacts = []
        dernier_t = time.perf_counter()

        while not all(etat["termine"] for etat in etats):
            frame_start = time.perf_counter()
            dt = min(0.05, frame_start - dernier_t)
            if dt <= 0:
                dt = dt_cible
            dernier_t = frame_start

            for etat in etats:
                if etat["termine"]:
                    continue
                forme = etat["forme"]
                etat["vitesse_z"] += g * dt
                nouvelle_z = etat["z"] - etat["vitesse_z"] * dt

                if nouvelle_z <= etat["z_sol"]:
                    nouvelle_z = etat["z_sol"]
                    etat["termine"] = True
                    energie = 0.5 * etat["masse"] * (etat["vitesse_z"] ** 2)
                    etat["energie_sol"]    += energie  # onde du bas
                    etat["energie_totale"] += energie
                    etat["vitesse_z"] *= -0.3
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

            scene._detecter_collisions(etats)

            scene.plotter.render()
            QApplication.processEvents()

            reste = dt_cible - (time.perf_counter() - frame_start)
            if reste > 0:
                time.sleep(reste)

        # 1. Heatmap pendant que les blocs sont AU SOL
        if scene._mode_contraintes_actif:
            scene._calculer_et_afficher_heatmap(etats)
            scene.plotter.render()
            QApplication.processEvents()

        # 2. Popup impact
        if impacts:
            lignes = [
                f"{nom} — {masse:.2f} kg | {energie:.2f} J"
                for nom, masse, energie in impacts
            ]
            QMessageBox.information(scene, "Impact", "\n".join(lignes))

        # 3. Remet les formes à leur position initiale
        for forme in formes:
            pos_init = positions_initiales[id(forme)]
            forme.params["centre"] = pos_init
            forme.mesh = None
            scene.dessiner_forme(forme)

        # 4. Réapplique le heatmap sur les mesh reconstruits
        if scene._mode_contraintes_actif:
            scene._calculer_et_afficher_heatmap(etats)

    def _calculer_et_afficher_heatmap(scene, etats):
        """
        Pour chaque forme, on accumule des sources d'ondes :
        - Chaque source a une position z_source (bas=0.0, haut=1.0 dans l'espace normalisé)
        et une intensité.
        - L'onde part de z_source et décroît avec la distance (gaussienne).
        - Toutes les ondes se superposent (interférence constructive).
        
        Exemple 3 blocs empilés :
        sol → bas bloc1    (onde_bas   sur bloc1, intensité E_sol1)
        bloc1→ haut bloc1  (onde_haut  sur bloc1, intensité E_col12)  [Newton: même force]
        bloc1→ bas bloc2   (onde_bas   sur bloc2, intensité E_col12)
        bloc2→ haut bloc2  (onde_haut  sur bloc2, intensité E_col23)
        bloc2→ bas bloc3   (onde_bas   sur bloc3, intensité E_col23)
        """

        # Énergie max globale pour normaliser toutes les intensités
        energie_max = max(
            (e["energie_sol"] + e["energie_collision"] for e in etats),
            default=1.0
        )
        energie_max = max(energie_max, 0.001)

        # Largeur de la gaussienne (fraction de la hauteur du bloc)
        # 0.35 = onde qui couvre ~35% de la hauteur avant de s'atténuer
        SIGMA = 0.35

        for etat in etats:
            forme = etat["forme"]
            mesh = forme.mesh
            if mesh is None:
                continue

            points = mesh.points
            z_points = points[:, 2]
            z_min, z_max = z_points.min(), z_points.max()
            hauteur = max(z_max - z_min, 1e-6)

            # z normalisé [0, 1] : 0 = bas du bloc, 1 = haut du bloc
            z_norm = (z_points - z_min) / hauteur

            # Distribution radiale : centre = plus comprimé
            centre_x = points[:, 0].mean()
            centre_y = points[:, 1].mean()
            dist_radiale = np.sqrt(
                (points[:, 0] - centre_x) ** 2 +
                (points[:, 1] - centre_y) ** 2
            )
            r_max = dist_radiale.max() if dist_radiale.max() > 0 else 1.0
            r_norm = 1.0 - (dist_radiale / r_max) * 0.3  # [0.7, 1.0]

            # ── Sources d'ondes pour ce bloc ──────────────────────────────
            # Chaque source = (z_source_normalisée, intensité)
            # z_source = 0.0 → onde part du bas
            # z_source = 1.0 → onde part du haut
            sources = []

            energie_sol       = etat.get("energie_sol", 0.0)
            energie_collision = etat.get("energie_collision", 0.0)

            if energie_sol > 0:
                # Impact venant du bas (sol ou rebond sur bloc inférieur)
                sources.append((0.0, energie_sol / energie_max))

            if energie_collision > 0:
                # Impact venant du haut (bloc supérieur qui tombe)
                sources.append((1.0, energie_collision / energie_max))

            if not sources:
                # Aucun impact → tout bleu
                stress_values = np.zeros(len(z_points))
            else:
                # Superposition gaussienne de toutes les ondes
                stress_values = np.zeros(len(z_points))
                for z_src, intensite in sources:
                    # Gaussienne centrée sur z_src
                    onde = intensite * np.exp(-((z_norm - z_src) ** 2) / (2 * SIGMA ** 2))
                    stress_values += onde

                # Applique la distribution radiale
                stress_values *= r_norm

                # Normalise pour que le max global reste cohérent entre les blocs
                intensite_totale = sum(i for _, i in sources)
                s_max = stress_values.max()
                if s_max > 0:
                    stress_values = stress_values / s_max * min(intensite_totale, 1.0)

            scene.plotter.remove_actor(forme.actor)
            forme.actor = scene.plotter.add_mesh(
                mesh,
                scalars=stress_values,
                cmap="coolwarm",
                show_edges=False,
                reset_camera=False,
                clim=[0, 1]
            )

        scene.plotter.render()

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

                demi_h_a = forme_a.r
                demi_h_b = forme_b.r
                demi_w_a = forme_a.l / 2
                demi_w_b = forme_b.l / 2

                dist_horiz = ((cx_a - cx_b)**2 + (cy_a - cy_b)**2) ** 0.5
                if dist_horiz >= demi_w_a + demi_w_b:
                    continue

                bas_a  = etat_a["z"] - demi_h_a
                haut_a = etat_a["z"] + demi_h_a
                bas_b  = etat_b["z"] - demi_h_b
                haut_b = etat_b["z"] + demi_h_b

                if bas_a >= haut_b or bas_b >= haut_a:
                    continue

                m_a = etat_a["masse"]
                m_b = etat_b["masse"]
                v_a = etat_a["vitesse_z"]
                v_b = etat_b["vitesse_z"]

                # Énergie cinétique relative à l'impact
                v_rel = abs(v_a - v_b)
                masse_reduite = (m_a * m_b) / (m_a + m_b)
                energie_collision = 0.5 * masse_reduite * v_rel ** 2

                # Forme du dessous → reçoit onde par le haut (poids qui tombe dessus)
                # Forme du dessus  → reçoit onde par le bas (rebond sur l'autre)
                if etat_a["z"] < etat_b["z"]:
                    etat_a["energie_collision"] += energie_collision
                    etat_b["energie_sol"]       += energie_collision
                else:
                    etat_b["energie_collision"] += energie_collision
                    etat_a["energie_sol"]       += energie_collision

                etat_a["energie_totale"] += energie_collision
                etat_b["energie_totale"] += energie_collision

                # Échange de vitesses
                etat_a["vitesse_z"] = (v_a * (m_a - m_b) + 2 * m_b * v_b) / (m_a + m_b)
                etat_b["vitesse_z"] = (v_b * (m_b - m_a) + 2 * m_a * v_a) / (m_a + m_b)

                # Sépare les formes
                overlap = min(haut_a, haut_b) - max(bas_a, bas_b)
                etat_a["z"] += overlap / 2
                etat_b["z"] -= overlap / 2


    def afficher_resistance(scene):
        scene._mode_contraintes_actif = True
        if not scene.objects:
            return

        for forme in scene.objects:
            if forme.mesh is None:
                continue
            stress_values = np.zeros(forme.mesh.n_points)
            scene.plotter.remove_actor(forme.actor)
            forme.actor = scene.plotter.add_mesh(
                forme.mesh,
                scalars=stress_values,
                cmap="coolwarm",
                show_edges=False,
                reset_camera=False,
                clim=[0, 1]
            )

        scene.plotter.add_scalar_bar(
            title="Contrainte (MPa)",
            color="white"
        )
        scene.plotter.render()

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
        scene._mode_contraintes_actif = False
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
