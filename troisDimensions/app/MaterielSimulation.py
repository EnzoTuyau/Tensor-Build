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

# Dictionnaire associant le nom de chaque forme à sa classe
FORMES_DISPONIBLES = {
    cls.NOM: cls
    for cls in [Cylindre, PoutreCarree, PrismeTriangulaire, Sphere, Cube, Vis]
}


# Classe principale de l'application de simulation 3D
class MaterielSimulationApp(QMainWindow):

    # Initialisation de la fenêtre principale
    def __init__(scene, switch_callback=None):
        super().__init__()

        # Callback pour retourner au mode 2D
        scene.switch_callback = switch_callback

        # Titre de la fenêtre
        scene.setWindowTitle("Tensor Build - Simulateur de Structure")

        # Taille initiale de la fenêtre
        scene.resize(1200, 800)

        # Widget central de la fenêtre
        scene.central_widget = QWidget()
        scene.setCentralWidget(scene.central_widget)

        # Disposition horizontale principale
        scene.layout = QHBoxLayout(scene.central_widget)

        # Zone 3D (gauche)
        # vérifie si utiliser par mac ou windows
        scene.plotter = SafeQtInteractor(scene.central_widget, auto_update=False)

        # Couleur de fond de la scène 3D
        scene.plotter.set_background("#0a1018")

        # Affichage des axes de référence
        scene.plotter.add_axes()

        # Création et affichage du sol
        scene.sol = Sol(scene.plotter)
        scene.sol.afficher()
        scene.sol.afficher()

        # Initialisation de la caméra
        scene.camera = Camera(scene.plotter)
        scene.camera.initialiser()

        # Contraint la caméra au-dessus du sol après chaque mouvement souris
        def _on_camera_moved(*args):
            scene.camera._contraindre_au_dessus_sol()

        # Branche l'observateur de mouvement de caméra sur l'interacteur VTK
        scene.plotter.interactor.GetInteractorStyle().AddObserver("InteractionEvent", _on_camera_moved)

        # Initialisation de la gravité avec g = 9.81 m/s²
        scene.gravite = Gravite()

        # Ajout de la vue 3D dans la disposition principale
        scene.layout.addWidget(scene.plotter.interactor, stretch=2)

        # Panneau de contrôle (droite)
        scene.control_panel = QWidget()
        scene.control_layout = QVBoxLayout(scene.control_panel)
        scene.layout.addWidget(scene.control_panel, stretch=1)

        # Construction de l'interface utilisateur
        scene.setup_ui_controls()

        # Feuille de style de l'application
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

        # Liste des formes présentes dans la scène
        scene.objects = []

        # État du drag de redimensionnement par la souris
        scene._resize_drag_active = False

        # Dernière position Y lors du drag
        scene._resize_drag_last_y = None

        # Indicateur d'activation du mode contraintes
        scene._mode_contraintes_actif = False

        # Installation du filtre d'événements sur l'interacteur 3D
        scene.plotter.interactor.installEventFilter(scene)
        scene.plotter.interactor.installEventFilter(scene)

        # Politique de focus clavier : l'interacteur peut recevoir les touches
        scene.plotter.interactor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Donne immédiatement le focus à l'interacteur
        scene.plotter.interactor.setFocus()

        # Mise à jour initiale de l'état des boutons
        scene._refresh_action_buttons()

    # Fermeture propre de la fenêtre pour éviter les segfaults
    def closeEvent(self, event):
        # Fermer explicitement le QtInteractor (render_timer, BasePlotter, QVTK) avant
        # que Qt ne détruisse l'arbre de widgets : sinon segfault en changeant de mode.
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

    # Construction du panneau de contrôle
    def setup_ui_controls(scene):

        # Bouton de retour au mode 2D
        scene.btn_switch_2d = QPushButton("Retourner en mode 2D")
        scene.btn_switch_2d.setProperty("variant", "launch")
        if scene.switch_callback is not None:
            scene.btn_switch_2d.clicked.connect(scene.switch_callback)
        else:
            scene.btn_switch_2d.setEnabled(False)
        scene.control_layout.addWidget(scene.btn_switch_2d)

        # Groupe 1 : sélection et ajout d'une forme
        group_add = QGroupBox("1. Ajouter une Pièce")
        layout_add = QVBoxLayout()

        # Forme sélectionnée dans la scène (None si aucune)
        scene.forme_selectionnee = None

        # Menu déroulant de sélection de forme
        scene.shape_selector = QComboBox()
        scene.shape_selector.addItem("Choisir une forme")
        scene.shape_selector.addItems(FORMES_DISPONIBLES.keys())
        layout_add.addWidget(QLabel("Forme :"))
        layout_add.addWidget(scene.shape_selector)

        # Bouton d'ajout de la forme à la scène
        scene.btn_add = QPushButton("Ajouter à la scène")
        scene.btn_add.clicked.connect(scene.add_shape)
        layout_add.addWidget(scene.btn_add)

        group_add.setLayout(layout_add)
        scene.control_layout.addWidget(group_add)

        # Groupe 2 : dimensions et position de la forme
        group_geo = QGroupBox("2. Dimensions & Position")
        layout_geo = QFormLayout()

        # Spinbox pour le rayon ou la largeur
        scene.spin_radius = QDoubleSpinBox()
        scene.spin_radius.setRange(0.1, 1000.0)
        scene.spin_radius.setValue(1.0)
        scene.spin_radius.setSingleStep(0.1)
        scene.spin_radius.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Rayon / Largeur :", scene.spin_radius)

        # Spinbox pour la longueur
        scene.spin_length = QDoubleSpinBox()
        scene.spin_length.setRange(0.1, 1000.0)
        scene.spin_length.setValue(5.0)
        scene.spin_length.valueChanged.connect(scene.update_current_shape)
        layout_geo.addRow("Longueur :", scene.spin_length)

        # Spinbox pour la position X
        scene.spin_x = QDoubleSpinBox()
        scene.spin_x.setRange(-1000, 1000)
        scene.spin_x.valueChanged.connect(scene.update_current_shape)

        # Spinbox pour la position Y
        scene.spin_y = QDoubleSpinBox()
        scene.spin_y.setRange(-1000, 1000)
        scene.spin_y.valueChanged.connect(scene.update_current_shape)

        # Spinbox pour la position Z
        scene.spin_z = QDoubleSpinBox()
        scene.spin_z.setRange(-1000, 1000)
        scene.spin_z.valueChanged.connect(scene.update_current_shape)

        layout_geo.addRow("Position X :", scene.spin_x)
        layout_geo.addRow("Position Y :", scene.spin_y)
        layout_geo.addRow("Position Z :", scene.spin_z)

        group_geo.setLayout(layout_geo)
        scene.control_layout.addWidget(group_geo)

        # Groupe 3 : sélection du matériau
        group_mat = QGroupBox("3. Matériau")
        layout_mat = QVBoxLayout()

        # Menu déroulant de sélection du matériau
        scene.selecteur_materiaux = QComboBox()

        # Base de données des matériaux : module de Young et couleur
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

        # Bouton de lancement de la simulation
        scene.btn_sim = QPushButton("Lancer simulation")
        scene.btn_sim.setProperty("variant", "success")
        scene.btn_sim.clicked.connect(scene.run_dummy_simulation)
        scene.control_layout.addWidget(scene.btn_sim)

        # Groupe 4 : suppression d'une forme par clic
        group_erase = QGroupBox("4. Effacer une Pièce")
        layout_erase = QVBoxLayout()

        # Bouton bascule pour activer ou désactiver le mode effacement
        scene.btn_erase = QPushButton("Mode Effacer : OFF")
        scene.btn_erase.setCheckable(True)
        scene.btn_erase.setProperty("variant", "secondary")
        scene.btn_erase.toggled.connect(scene.toggle_erase_mode)
        layout_erase.addWidget(scene.btn_erase)

        # Label d'instruction affiché en mode effacement
        scene.erase_label = QLabel("Clique sur une forme pour l'effacer.")
        scene.erase_label.setVisible(False)
        layout_erase.addWidget(scene.erase_label)

        group_erase.setLayout(layout_erase)
        scene.control_layout.addWidget(group_erase)

        # Groupe 5 : visualisation des contraintes
        group_resistance = QGroupBox("5. Vue de la Résistance")
        layout_resistance = QVBoxLayout()

        # Bouton pour afficher la carte de chaleur des contraintes
        scene.btn_resistance = QPushButton("Afficher les contraintes")
        scene.btn_resistance.setProperty("variant", "secondary")
        scene.btn_resistance.clicked.connect(scene.afficher_resistance)
        layout_resistance.addWidget(scene.btn_resistance)

        # Bouton pour réinitialiser les couleurs des formes
        scene.btn_resistance_reset = QPushButton("Réinitialiser les couleurs")
        scene.btn_resistance_reset.setProperty("variant", "secondary")
        scene.btn_resistance_reset.clicked.connect(scene.reinitialiser_couleurs)
        layout_resistance.addWidget(scene.btn_resistance_reset)

        group_resistance.setLayout(layout_resistance)
        scene.control_layout.addWidget(group_resistance)

        # Groupe 6 : inspection d'une forme par clic
        group_inspect = QGroupBox("6. Inspecter une Pièce")
        layout_inspect = QVBoxLayout()

        # Bouton bascule pour activer ou désactiver le mode inspection
        scene.btn_inspect = QPushButton("Mode Inspecter : OFF")
        scene.btn_inspect.setCheckable(True)
        scene.btn_inspect.setProperty("variant", "secondary")
        scene.btn_inspect.toggled.connect(scene.toggle_inspect_mode)
        layout_inspect.addWidget(scene.btn_inspect)

        group_inspect.setLayout(layout_inspect)
        scene.control_layout.addWidget(group_inspect)

        # Le groupe dimensions est grisé par défaut tant qu'aucune forme n'est choisie
        group_geo.setEnabled(False)

        # Référence gardée pour pouvoir activer ou désactiver le groupe
        scene.group_geo = group_geo

        # Connexion du sélecteur de forme à la logique d'activation du groupe dimensions
        scene.shape_selector.currentIndexChanged.connect(
            scene.on_forme_choisie)

        # Espace flexible en bas du panneau
        scene.control_layout.addStretch()

    # ------------------------------------------------------------------ #
    #  Ajouter / Dessiner                                                  #
    # ------------------------------------------------------------------ #

    # Instancie la forme choisie et l'ajoute à la scène
    def add_shape(scene):
        nom = scene.shape_selector.currentText()
        if nom not in FORMES_DISPONIBLES:
            return

        # Classe correspondant à la forme sélectionnée
        classe = FORMES_DISPONIBLES[nom]

        # Paramètres géométriques lus depuis les spinbox
        params = {
            "rayon": scene.spin_radius.value(),
            "longueur": scene.spin_length.value(),
            "centre": (scene.spin_x.value(),
                       scene.spin_y.value(),
                       scene.spin_z.value()),
        }

        # Création de la forme et ajout à la liste
        forme = classe(params)
        scene.objects.append(forme)
        scene.dessiner_forme(forme)

        # La forme nouvellement ajoutée devient la forme sélectionnée
        scene.forme_selectionnee = forme

        # Remet le sélecteur à 0 SANS déclencher on_forme_choisie
        scene.shape_selector.blockSignals(True)
        scene.shape_selector.setCurrentIndex(0)
        scene.shape_selector.blockSignals(False)

        # Garde le groupe dimensions actif et la forme surlignée en jaune
        scene.group_geo.setEnabled(True)
        scene.plotter.remove_actor(forme.actor)
        forme.actor = scene.plotter.add_mesh(
            forme.mesh, color="yellow", show_edges=True, reset_camera=False)

        # Active le suivi de caméra sur la nouvelle forme
        scene.camera.activer_suivi(forme.params["centre"])

        # Met à jour l'état des boutons
        scene._refresh_action_buttons()

    # Construit et affiche le mesh d'une forme dans la scène
    def dessiner_forme(scene, forme):

        # Sauvegarde la position de la caméra avant de redessiner
        scene.camera.sauvegarder()

        # Supprime l'ancien acteur si présent
        if forme.actor:
            scene.plotter.remove_actor(forme.actor)

        # Reconstruction du mesh depuis les paramètres de la forme
        forme.mesh = forme.construire_mesh()

        # Couleur correspondant au matériau sélectionné
        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        # Ajout du mesh dans la scène
        forme.actor = scene.plotter.add_mesh(
            forme.mesh,
            color=color,
            show_edges=True,
            reset_camera=False
        )

        # Restaure la position de la caméra après le redessinage
        scene.camera.restaurer()

    # ------------------------------------------------------------------ #
    #  Mise à jour                                                         #
    # ------------------------------------------------------------------ #

    # Met à jour la forme sélectionnée quand les spinbox changent
    def update_current_shape(scene):
        forme = scene.forme_selectionnee
        if forme is None:
            return

        # Nouvelle position lue depuis les spinbox
        nouvelle_pos = (scene.spin_x.value(),
                        scene.spin_y.value(),
                        scene.spin_z.value())

        # Déplace la caméra avant de reconstruire la forme
        scene.camera.suivre_objet(nouvelle_pos)

        # Mise à jour des paramètres géométriques
        forme.params["rayon"] = scene.spin_radius.value()
        forme.params["longueur"] = scene.spin_length.value()
        forme.params["centre"] = nouvelle_pos

        # Reconstruction et affichage de la forme
        scene.dessiner_forme(forme)

        # Remet le surlignage jaune sur la forme sélectionnée
        scene.plotter.remove_actor(forme.actor)
        forme.actor = scene.plotter.add_mesh(
            forme.mesh, color="yellow", show_edges=True, reset_camera=False)

    # Filtre d'événements pour les touches WASD et le drag souris
    def eventFilter(scene, obj, event):

        # Touches WASD pour déplacer la caméra
        if event.type() == QEvent.KeyPress:
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

            # Début du drag de redimensionnement au clic gauche, cette partie permet de redimensionner les objets avec le click gauche, mais cela faisit de l'interférence avec la caméra, donc c'est toujours désactivé. Cependant le code est là
            if event.type() == QEvent.MouseButtonPress and scene.forme_selectionnee is not None:
                if event.button() == 1:
                    scene._resize_drag_active = True
                    scene._resize_drag_last_y = event.position().y()
                    return True

            # Déplacement de la souris pendant le drag de redimensionnement
            elif event.type() == QEvent.MouseMove and scene._resize_drag_active and scene.forme_selectionnee is not None:
                y_now = event.position().y()
                dy = scene._resize_drag_last_y - y_now
                if abs(dy) >= 1:

                    # Calcul du facteur de redimensionnement
                    facteur = 1.0 + (dy * 0.008)
                    facteur = max(0.2, min(5.0, facteur))

                    forme = scene.forme_selectionnee

                    # Nouveaux rayon et longueur après redimensionnement
                    new_r = max(0.1, forme.params["rayon"] * facteur)
                    new_l = max(0.1, forme.params["longueur"] * facteur)
                    forme.params["rayon"] = new_r
                    forme.params["longueur"] = new_l

                    # Mise à jour des spinbox sans déclencher update_current_shape
                    scene.spin_radius.blockSignals(True)
                    scene.spin_length.blockSignals(True)
                    scene.spin_radius.setValue(new_r)
                    scene.spin_length.setValue(new_l)
                    scene.spin_radius.blockSignals(False)
                    scene.spin_length.blockSignals(False)

                    # Reconstruction et surlignage de la forme redimensionnée
                    scene.dessiner_forme(forme)
                    scene.plotter.remove_actor(forme.actor)
                    forme.actor = scene.plotter.add_mesh(
                        forme.mesh, color="yellow", show_edges=True, reset_camera=False)
                    scene._resize_drag_last_y = y_now
                return True

            # Fin du drag de redimensionnement au relâchement du bouton
            elif event.type() == QEvent.MouseButtonRelease and scene._resize_drag_active:
                scene._resize_drag_active = False
                scene._resize_drag_last_y = None
                scene._mode_contraintes_actif = False
                return True

        return super().eventFilter(obj, event)

    # Recolore uniquement la forme sélectionnée selon le matériel choisi
    def update_materiel(scene):
        if scene.forme_selectionnee is None:
            return

        # Couleur du matériel sélectionné
        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        # Supprime l'ancien acteur et recrée avec la nouvelle couleur
        scene.plotter.remove_actor(scene.forme_selectionnee.actor)
        scene.forme_selectionnee.actor = scene.plotter.add_mesh(
            scene.forme_selectionnee.mesh, color=color, show_edges=True)

        # Remet le surlignage jaune sur la forme sélectionnée
        scene.plotter.remove_actor(scene.forme_selectionnee.actor)
        scene.forme_selectionnee.actor = scene.plotter.add_mesh(
            scene.forme_selectionnee.mesh, color="yellow", show_edges=True)

    # ------------------------------------------------------------------ #
    #  Simulation                                                          #
    # ------------------------------------------------------------------ #

    # Lance le rapport de simulation puis l'animation de chute
    def run_dummy_simulation(scene):
        if not scene.objects:
            return

        # Génère et affiche le rapport de masse et de poids
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

        # Lance l'animation de chute libre
        scene.animer_chute(scene.objects)

    # Animation de la chute libre avec physique et collisions
    def animer_chute(scene, formes):

        # Matériau sélectionné pour le calcul des masses
        mat_name = scene.selecteur_materiaux.currentText()

        # Accélération gravitationnelle
        g = scene.gravite.g

        # Fréquence cible de l'animation
        target_fps = 60.0

        # Durée d'une frame cible en secondes
        dt_cible = 1.0 / target_fps

        # Sauvegarde des positions initiales pour restauration après simulation
        positions_initiales = {
            id(forme): forme.params["centre"]
            for forme in formes
        }

        # Initialisation des états physiques de chaque forme
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

        # Liste des impacts détectés pendant la simulation
        impacts = []

        # Temps de la dernière frame
        dernier_t = time.perf_counter()

        # Boucle principale de simulation
        while not all(etat["termine"] for etat in etats):
            frame_start = time.perf_counter()

            # Calcul du delta temps réel entre deux frames
            dt = min(0.05, frame_start - dernier_t)
            if dt <= 0:
                dt = dt_cible
            dernier_t = frame_start

            # Mise à jour physique de chaque forme
            for etat in etats:
                if etat["termine"]:
                    continue

                forme = etat["forme"]

                # Accélération gravitationnelle : v = v + g*dt
                etat["vitesse_z"] += g * dt

                # Nouvelle position : z = z - v*dt
                nouvelle_z = etat["z"] - etat["vitesse_z"] * dt

                # Détection du contact avec le sol
                if nouvelle_z <= etat["z_sol"]:
                    nouvelle_z = etat["z_sol"]
                    etat["termine"] = True

                    # Calcul de l'énergie cinétique à l'impact : E = 1/2 * m * v²
                    energie = 0.5 * etat["masse"] * (etat["vitesse_z"] ** 2)

                    # Accumulation de l'énergie d'impact venant du bas
                    etat["energie_sol"]    += energie
                    etat["energie_totale"] += energie

                    # Rebond partiel avec coefficient de restitution
                    etat["vitesse_z"] *= -0.3
                    impacts.append((forme.NOM, etat["masse"], energie))

                # Déplacement réel de la frame
                dz = nouvelle_z - etat["z"]
                etat["z"] = nouvelle_z

                # Mise à jour du centre de la forme
                forme.params["centre"] = (
                    forme.params["centre"][0],
                    forme.params["centre"][1],
                    nouvelle_z,
                )

                # Translation directe du mesh pour éviter remove/add à chaque frame
                if forme.mesh is not None:
                    forme.mesh.translate((0.0, 0.0, dz), inplace=True)

            # Détection et résolution des collisions entre formes
            scene._detecter_collisions(etats)

            # Rendu de la frame et traitement des événements Qt
            scene.plotter.render()
            QApplication.processEvents()

            # Attente pour respecter la fréquence cible
            reste = dt_cible - (time.perf_counter() - frame_start)
            if reste > 0:
                time.sleep(reste)

        # Affichage de la heatmap pendant que les blocs sont au sol
        if scene._mode_contraintes_actif:
            scene._calculer_et_afficher_heatmap(etats)
            scene.plotter.render()
            QApplication.processEvents()

        # Affichage du popup récapitulatif des impacts
        if impacts:
            lignes = [
                f"{nom} — {masse:.2f} kg | {energie:.2f} J"
                for nom, masse, energie in impacts
            ]
            QMessageBox.information(scene, "Impact", "\n".join(lignes))

        # Restauration des positions initiales de toutes les formes
        for forme in formes:
            pos_init = positions_initiales[id(forme)]
            forme.params["centre"] = pos_init
            forme.mesh = None
            scene.dessiner_forme(forme)

        # Réapplication de la heatmap sur les mesh reconstruits
        if scene._mode_contraintes_actif:
            scene._calculer_et_afficher_heatmap(etats)

    # Calcule et affiche la carte de chaleur des contraintes sur chaque forme
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

        # Énergie maximale globale
        energie_max = max(
            (e["energie_sol"] + e["energie_collision"] for e in etats),
            default=1.0
        )
        energie_max = max(energie_max, 0.001)

        # Largeur de la gaussienne en fraction de la hauteur du bloc
        SIGMA = 0.35

        for etat in etats:
            forme = etat["forme"]
            mesh = forme.mesh
            if mesh is None:
                continue

            # Coordonnées des points du mesh
            points = mesh.points
            z_points = points[:, 2]
            z_min, z_max = z_points.min(), z_points.max()
            hauteur = max(z_max - z_min, 1e-6)

            # Coordonnée Z normalisée entre 0 (bas) et 1 (haut)
            z_norm = (z_points - z_min) / hauteur

            # Distance radiale des points par rapport au centre du mesh
            centre_x = points[:, 0].mean()
            centre_y = points[:, 1].mean()
            dist_radiale = np.sqrt(
                (points[:, 0] - centre_x) ** 2 +
                (points[:, 1] - centre_y) ** 2
            )
            r_max = dist_radiale.max() if dist_radiale.max() > 0 else 1.0

            # Facteur radial : le centre est plus comprimé que les bords
            r_norm = 1.0 - (dist_radiale / r_max) * 0.3

            # Sources d'ondes pour cette forme : (z_source normalisée, intensité)
            sources = []

            energie_sol       = etat.get("energie_sol", 0.0)
            energie_collision = etat.get("energie_collision", 0.0)

            # Source en bas : impact venant du sol ou d'un bloc inférieur
            if energie_sol > 0:
                sources.append((0.0, energie_sol / energie_max))

            # Source en haut : impact venant d'un bloc supérieur
            if energie_collision > 0:
                sources.append((1.0, energie_collision / energie_max))

            if not sources:
                # Aucun impact : la forme reste entièrement bleue
                stress_values = np.zeros(len(z_points))
            else:
                # Superposition de toutes les ondes gaussiennes
                stress_values = np.zeros(len(z_points))
                for z_src, intensite in sources:
                    onde = intensite * np.exp(-((z_norm - z_src) ** 2) / (2 * SIGMA ** 2))
                    stress_values += onde

                # Application du facteur radial
                stress_values *= r_norm

                # Normalisation pour cohérence entre les blocs
                intensite_totale = sum(i for _, i in sources)
                s_max = stress_values.max()
                if s_max > 0:
                    stress_values = stress_values / s_max * min(intensite_totale, 1.0)

            # Affichage de la heatmap sur le mesh
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

    # Détection et résolution des collisions entre formes
    def _detecter_collisions(scene, etats):
        for i, etat_a in enumerate(etats):
            for j, etat_b in enumerate(etats):
                if i >= j:
                    continue

                forme_a = etat_a["forme"]
                forme_b = etat_b["forme"]

                # Centres horizontaux des deux formes
                cx_a, cy_a = forme_a.params["centre"][0], forme_a.params["centre"][1]
                cx_b, cy_b = forme_b.params["centre"][0], forme_b.params["centre"][1]

                # Demi-hauteurs et demi-largeurs des formes
                demi_h_a = forme_a.r
                demi_h_b = forme_b.r
                demi_w_a = forme_a.l / 2
                demi_w_b = forme_b.l / 2

                # Vérifie le chevauchement horizontal
                dist_horiz = ((cx_a - cx_b)**2 + (cy_a - cy_b)**2) ** 0.5
                if dist_horiz >= demi_w_a + demi_w_b:
                    continue

                # Limites verticales de chaque forme
                bas_a  = etat_a["z"] - demi_h_a
                haut_a = etat_a["z"] + demi_h_a
                bas_b  = etat_b["z"] - demi_h_b
                haut_b = etat_b["z"] + demi_h_b

                # Vérifie le chevauchement vertical
                if bas_a >= haut_b or bas_b >= haut_a:
                    continue

                # Masses et vitesses des deux formes
                m_a = etat_a["masse"]
                m_b = etat_b["masse"]
                v_a = etat_a["vitesse_z"]
                v_b = etat_b["vitesse_z"]

                # Énergie cinétique relative à la collision
                v_rel = abs(v_a - v_b)
                masse_reduite = (m_a * m_b) / (m_a + m_b)
                energie_collision = 0.5 * masse_reduite * v_rel ** 2

                # Attribution de l'énergie selon quelle forme est au-dessus
                if etat_a["z"] < etat_b["z"]:
                    etat_a["energie_collision"] += energie_collision
                    etat_b["energie_sol"]       += energie_collision
                else:
                    etat_b["energie_collision"] += energie_collision
                    etat_a["energie_sol"]       += energie_collision

                # Accumulation de l'énergie totale pour chaque forme
                etat_a["energie_totale"] += energie_collision
                etat_b["energie_totale"] += energie_collision

                # Échange de vitesses par conservation de la quantité de mouvement
                etat_a["vitesse_z"] = (v_a * (m_a - m_b) + 2 * m_b * v_b) / (m_a + m_b)
                etat_b["vitesse_z"] = (v_b * (m_b - m_a) + 2 * m_a * v_a) / (m_a + m_b)

                # Séparation des formes pour éviter l'interpénétration
                overlap = min(haut_a, haut_b) - max(bas_a, bas_b)
                etat_a["z"] += overlap / 2
                etat_b["z"] -= overlap / 2

    # Affiche la carte de chaleur statique des contraintes sur toutes les formes
    def afficher_resistance(scene):

        # Active le mode contraintes
        scene._mode_contraintes_actif = True
        if not scene.objects:
            return

        # Initialisation de toutes les formes en bleu (aucune contrainte)
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

        # Barre de couleur indiquant l'échelle des contraintes
        scene.plotter.add_scalar_bar(
            title="Contrainte (MPa)",
            color="white"
        )
        scene.plotter.render()

    # ------------------------------------------------------------------ #
    #  Mode Effacer                                                        #
    # ------------------------------------------------------------------ #

    # Active ou désactive le mode d'effacement de formes par clic
    def toggle_erase_mode(scene, active):
        if active:
            scene.btn_erase.setText("Mode Effacer : ON")
            scene.btn_erase.setProperty("variant", "danger")
            scene.erase_label.setVisible(True)

            # Active le picking de mesh au clic gauche
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

        # Force le rafraîchissement du style du bouton
        scene.style().unpolish(scene.btn_erase)
        scene.style().polish(scene.btn_erase)

    # Supprime la forme dont le mesh a été cliqué
    def on_pick(scene, picked_mesh):
        if picked_mesh is None:
            return
        for forme in scene.objects:
            if forme.mesh is picked_mesh:
                scene.plotter.remove_actor(forme.actor)
                scene.objects.remove(forme)

                # Désélectionne si c'était la forme active
                if scene.forme_selectionnee is forme:
                    scene.forme_selectionnee = None
                break

        # Met à jour l'état des boutons
        scene._refresh_action_buttons()

    # Remet les couleurs originales du matériau sur toutes les formes
    def reinitialiser_couleurs(scene):

        # Désactive le mode contraintes
        scene._mode_contraintes_actif = False
        if not scene.objects:
            return

        # Couleur correspondant au matériau sélectionné
        mat_name = scene.selecteur_materiaux.currentText()
        color = scene.materials_db[mat_name][1]

        # Redessine chaque forme avec sa couleur de matériau
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

    # Active ou désactive le mode d'inspection de formes
    def toggle_inspect_mode(scene, active):
        if active:
            scene.btn_inspect.setText("Mode Inspecter : ON")
            scene.btn_inspect.setProperty("variant", "success")

            # Active le picking de mesh au clic gauche
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

        # Force le rafraîchissement du style du bouton
        scene.style().unpolish(scene.btn_inspect)
        scene.style().polish(scene.btn_inspect)

    # Sélectionne la forme cliquée et remplit les spinbox avec ses paramètres
    def on_inspect(scene, picked_mesh):
        if picked_mesh is None:
            return
        for forme in scene.objects:
            if forme.mesh is picked_mesh:

                # La forme cliquée devient la forme sélectionnée
                scene.forme_selectionnee = forme

                # Remet la couleur de matériau sur toutes les autres formes
                for f in scene.objects:
                    mat_name = scene.selecteur_materiaux.currentText()
                    color = scene.materials_db[mat_name][1]
                    scene.plotter.remove_actor(f.actor)
                    f.actor = scene.plotter.add_mesh(
                        f.mesh, color=color, show_edges=True)

                # Surligne la forme sélectionnée en jaune
                scene.plotter.remove_actor(forme.actor)
                forme.actor = scene.plotter.add_mesh(
                    forme.mesh, color="yellow", show_edges=True)

                # Bloque les signaux pour éviter des mises à jour pendant le remplissage
                for spin in [scene.spin_radius, scene.spin_length,
                             scene.spin_x, scene.spin_y, scene.spin_z]:
                    spin.blockSignals(True)

                # Remplit les spinbox avec les paramètres de la forme
                scene.spin_radius.setValue(forme.r)
                scene.spin_length.setValue(forme.l)
                scene.spin_x.setValue(forme.c[0])
                scene.spin_y.setValue(forme.c[1])
                scene.spin_z.setValue(forme.c[2])

                # Rétablit les signaux
                for spin in [scene.spin_radius, scene.spin_length,
                             scene.spin_x, scene.spin_y, scene.spin_z]:
                    spin.blockSignals(False)
                break

        # Active le suivi de caméra sur la forme inspectée
        scene.camera.activer_suivi(forme.params["centre"])

    # Réagit au changement de sélection dans le menu déroulant de formes
    def on_forme_choisie(scene, index):

        # Désactive le suivi de caméra
        scene.camera.desactiver_suivi()

        if index == 0:
            # Retour à l'option neutre : désactive le groupe dimensions
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

            # Active le groupe dimensions pour la nouvelle forme
            scene.group_geo.setEnabled(True)

    # Grise ou active les boutons selon la présence d'objets dans la scène
    def _refresh_action_buttons(scene):
        has_objects = len(scene.objects) > 0

        # Si aucun objet : réinitialise les modes actifs
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

            # Désactive le picking si aucun objet
            scene.plotter.disable_picking()

        # Active ou grise les boutons selon la présence d'objets
        scene.btn_sim.setEnabled(has_objects)
        scene.btn_erase.setEnabled(has_objects)
        scene.btn_resistance.setEnabled(has_objects)
        scene.btn_resistance_reset.setEnabled(has_objects)
        scene.btn_inspect.setEnabled(has_objects)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MaterielSimulationApp()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())