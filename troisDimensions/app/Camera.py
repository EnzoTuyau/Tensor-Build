import math


class Camera:
    """Gère la position et le comportement de la caméra."""

    def __init__(self, plotter, position=(30, 30, 20), focal_point=(0, 0, 0), up=(0, 0, 1)):
        self.plotter = plotter
        self.position_initiale = position
        self.focal_point_initial = focal_point
        self.up_initial = up
        self._position = position
        self._focal_point = focal_point
        self._up = up
        self._suivi_actif = False
        self._derniere_pos_objet = None  # dernière position connue de l'objet suivi

    @property
    def position(self):
        return self.plotter.camera.position


    def initialiser(self):
        """Applique la position de départ."""
        self.plotter.camera.position = self.position_initiale
        self.plotter.camera.focal_point = self.focal_point_initial
        self.plotter.camera.up = self.up_initial

    def sauvegarder(self):
        """Sauvegarde la position actuelle de la caméra."""
        self._position = self.plotter.camera.position
        self._focal_point = self.plotter.camera.focal_point
        self._up = self.plotter.camera.up

    def restaurer(self):
        """Restaure la dernière position sauvegardée."""
        self.plotter.camera.position = self._position
        self.plotter.camera.focal_point = self._focal_point
        self.plotter.camera.up = self._up

    def reset(self):
        """Revient à la position initiale."""
        self.initialiser()

    def activer_suivi(self, position_objet):
        """Active le suivi d'un objet à partir de sa position."""
        self._suivi_actif = True
        self._derniere_pos_objet = position_objet

    def desactiver_suivi(self):
        """Désactive le suivi."""
        self._suivi_actif = False
        self._derniere_pos_objet = None

    def suivre_objet(self, nouvelle_position_objet):
        """
        Déplace la caméra pour suivre l'objet.
        Permet à la caméra de suivre l'objet.
        """
        if not self._suivi_actif or self._derniere_pos_objet is None:
            return

        # Calcule le déplacement de l'objet
        dx = nouvelle_position_objet[0] - self._derniere_pos_objet[0]
        dy = nouvelle_position_objet[1] - self._derniere_pos_objet[1]
        dz = nouvelle_position_objet[2] - self._derniere_pos_objet[2]

        # Déplace la caméra et le focal_point du même delta
        cam_pos = self.plotter.camera.position
        foc = self.plotter.camera.focal_point

        self.plotter.camera.position = (
            cam_pos[0] + dx,
            cam_pos[1] + dy,
            cam_pos[2] + dz
        )
        self.plotter.camera.focal_point = (
            foc[0] + dx,
            foc[1] + dy,
            foc[2] + dz
        )

        self._derniere_pos_objet = nouvelle_position_objet

    def pan(self, direction, pas=1.0):
        """
        Déplace la caméra latéralement/verticalement sans changer l'angle.
        direction : 'haut', 'bas', 'gauche', 'droite'
        pas       : distance de déplacement click
        """
        cam_pos = list(self.plotter.camera.position)
        foc = list(self.plotter.camera.focal_point)

        if direction == "haut":
            cam_pos[2] += pas
            foc[2] += pas
        elif direction == "bas":
            cam_pos[2] -= pas
            foc[2] -= pas
        elif direction == "gauche":
            cam_pos[0] -= pas
            foc[0] -= pas
        elif direction == "droite":
            cam_pos[0] += pas
            foc[0] += pas

        

    def orbit_horizontal(self, angle_deg):
        """
        Tourne la caméra autour du focal point dans le plan XY (Z fixe).
        angle_deg : degrés de rotation (positif = sens antihoraire)
        """
        cam_pos = self.plotter.camera.position
        foc = self.plotter.camera.focal_point

        # Offset caméra par rapport au focal point
        dx = cam_pos[0] - foc[0]
        dy = cam_pos[1] - foc[1]
        # Z reste intact
        z = cam_pos[2]

        # Rotation dans le plan XY
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        new_dx = dx * cos_a - dy * sin_a
        new_dy = dx * sin_a + dy * cos_a

        self.plotter.camera.position = (
            foc[0] + new_dx,
            foc[1] + new_dy,
            z  # Z bloqué
        )
        self.plotter.camera.focal_point = foc  # focal point ne bouge pas
        self.plotter.render()
    
    

        self.plotter.camera.position = tuple(cam_pos)
        self.plotter.camera.focal_point = tuple(foc)
        self.plotter.render()