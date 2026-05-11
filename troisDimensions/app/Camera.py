import math
import numpy as np


#1. Classe représentant une caméra 3D orbitale
class Camera:
    """Caméra 3D orbitale et contraintes au-dessus du sol."""

    # Hauteur du sol
    SOL_Z = -10.0

    # Hauteur minimale de la caméra au-dessus du sol
    ELEV_MIN = 5.0

    #2. Initialisation de la caméra
    def __init__(self, plotter, position=(30, 30, 20), focal_point=(0, 0, 0), up=(0, 0, 1)):

        # Référence vers le plotter PyVista
        self.plotter = plotter

        # Position initiale de la caméra
        self.position_initiale = position

        # Point observé par la caméra
        self.focal_point_initial = focal_point

        # Vecteur vertical de la caméra
        self.up_initial = up

        # État du mode suivi
        self._suivi_actif = False

        # Dernière position connue de l’objet suivi
        self._derniere_pos_objet = None

    #3. Configuration initiale de la caméra
    def initialiser(self):

        # Position de départ
        self.plotter.camera.position = self.position_initiale

        # Point regardé par la caméra (point focal)
        self.plotter.camera.focal_point = self.focal_point_initial

        # Orientation verticale
        self.plotter.camera.up = self.up_initial

        # Active la rotation orbitale native de PyVista (la caméra tourne autour du point focal de manière à former un demi-cercle)
        self.plotter.camera.position = self.position_initiale
        self.plotter.camera.focal_point = self.focal_point_initial
        self.plotter.camera.up = self.up_initial

        # Style orbital : le vecteur "up" reste vertical
        self.plotter.enable_terrain_style(mouse_wheel_zooms=True)

    #4. Empêche la caméra de passer sous le sol
    def _contraindre_au_dessus_sol(self):
        """Empêche la caméra de passer sous le sol."""

        # Hauteur minimale autorisée
        z_min = self.SOL_Z + self.ELEV_MIN

        # Position actuelle de la caméra
        cam_pos = list(self.plotter.camera.position)

        # Point observé par la caméra
        foc = list(self.plotter.camera.focal_point)

        # Vérifie si la caméra est trop basse
        if cam_pos[2] < z_min:

            # Calcule le vecteur caméra (point focal - position caméra)
            dx = foc[0] - cam_pos[0]
            dy = foc[1] - cam_pos[1]
            dz = foc[2] - cam_pos[2]

            # Distance horizontale
            dist_horiz = (dx**2 + dy**2) ** 0.5

            # Replace la caméra à la hauteur minimale
            cam_pos[2] = z_min

            # Ajuste l’angle de vue
            if dist_horiz > 0:

                ratio = abs(cam_pos[2] - foc[2]) / dist_horiz

                # Garde le point focal intact
                # seule la caméra remonte

            # Met à jour la position de la caméra
            self.plotter.camera.position = tuple(cam_pos)

    #5. Sauvegarde de la position actuelle de la caméra
    def sauvegarder(self):

        # Sauvegarde de la position
        self._position = self.plotter.camera.position

        # Sauvegarde du point observé
        self._focal_point = self.plotter.camera.focal_point

        # Sauvegarde du vecteur vertical
        self._up = self.plotter.camera.up

    #6. Restauration de la caméra sauvegardée
    def restaurer(self):

        # Restaure la position
        self.plotter.camera.position = self._position

        # Restaure le point observé
        self.plotter.camera.focal_point = self._focal_point

        # Restaure l’orientation verticale
        self.plotter.camera.up = self._up

    #7. Réinitialisation complète de la caméra
    def reset(self):

        self.initialiser()

    #8. Activation du suivi d’objet
    def activer_suivi(self, position_objet):

        # Active le mode suivi
        self._suivi_actif = True

        # Sauvegarde la position actuelle de l’objet
        self._derniere_pos_objet = position_objet

    #9. Désactivation du suivi d’objet
    def desactiver_suivi(self):

        # Désactive le mode suivi
        self._suivi_actif = False

        # Efface la dernière position connue
        self._derniere_pos_objet = None

    #10. Déplacement automatique de la caméra avec un objet
    def suivre_objet(self, nouvelle_position_objet):

        # Vérifie que le suivi est actif
        if not self._suivi_actif or self._derniere_pos_objet is None:
            return

        # Différence de position sur X
        dx = nouvelle_position_objet[0] - self._derniere_pos_objet[0]

        # Différence de position sur Y
        dy = nouvelle_position_objet[1] - self._derniere_pos_objet[1]

        # Différence de position sur Z
        dz = nouvelle_position_objet[2] - self._derniere_pos_objet[2]

        # Position actuelle de la caméra
        cam_pos = self.plotter.camera.position

        # Point observé actuel
        foc = self.plotter.camera.focal_point

        # Déplace la caméra
        self.plotter.camera.position = (
            cam_pos[0] + dx,
            cam_pos[1] + dy,
            cam_pos[2] + dz
        )

        # Déplace aussi le point observé
        self.plotter.camera.focal_point = (
            foc[0] + dx,
            foc[1] + dy,
            foc[2] + dz
        )

        # Vérifie que la caméra reste au-dessus du sol
        self._contraindre_au_dessus_sol()

        # Met à jour la dernière position connue
        self._derniere_pos_objet = nouvelle_position_objet

    #11. Déplacement manuel de la caméra
    def pan(self, direction, pas=1.0):

        # Position actuelle de la caméra
        cam_pos = np.array(self.plotter.camera.position)

        # Point observé actuel
        foc = np.array(self.plotter.camera.focal_point)

        # Vecteur vertical
        up = np.array([0, 0, 1])

        # Vecteur avant
        avant = foc - cam_pos

        # Garde le déplacement horizontal
        avant[2] = 0

        # Normalisation du vecteur
        avant = avant / (np.linalg.norm(avant) + 1e-9)

        # Vecteur droite perpendiculaire à avant
        droite = np.cross(avant, up)

        # Normalisation du vecteur
        droite = droite / (np.linalg.norm(droite) + 1e-9)

        # Déplacement vers le haut
        if direction == "haut":
            delta = np.array([0, 0, pas])

        # Déplacement vers le bas
        elif direction == "bas":
            delta = np.array([0, 0, -pas])

        # Déplacement vers la gauche
        elif direction == "gauche":
            delta = -droite * pas

        # Déplacement vers la droite
        elif direction == "droite":
            delta = droite * pas

        else:
            return

        # Nouvelle position de la caméra
        nouvelle_pos = tuple(cam_pos + delta)

        # Nouveau point observé
        nouveau_foc = tuple(foc + delta)

        # Mise à jour de la caméra
        self.plotter.camera.position = nouvelle_pos
        self.plotter.camera.focal_point = nouveau_foc

        # Vérifie que la caméra reste au-dessus du sol
        self._contraindre_au_dessus_sol()