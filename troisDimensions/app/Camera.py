import math


class Camera:
    """Laisse PyVista gérer la caméra nativement."""

    def __init__(self, plotter, position=(30, 30, 20), focal_point=(0, 0, 0), up=(0, 0, 1)):
        self.plotter = plotter
        self.position_initiale = position
        self.focal_point_initial = focal_point
        self.up_initial = up
        self._suivi_actif = False
        self._derniere_pos_objet = None

    def initialiser(self):
        self.plotter.camera.position = self.position_initiale
        self.plotter.camera.focal_point = self.focal_point_initial
        self.plotter.camera.up = self.up_initial

    def sauvegarder(self):
        self._position = self.plotter.camera.position
        self._focal_point = self.plotter.camera.focal_point
        self._up = self.plotter.camera.up

    def restaurer(self):
        self.plotter.camera.position = self._position
        self.plotter.camera.focal_point = self._focal_point
        self.plotter.camera.up = self._up

    def reset(self):
        self.initialiser()

    def activer_suivi(self, position_objet):
        self._suivi_actif = True
        self._derniere_pos_objet = position_objet

    def desactiver_suivi(self):
        self._suivi_actif = False
        self._derniere_pos_objet = None

    def suivre_objet(self, nouvelle_position_objet):
        if not self._suivi_actif or self._derniere_pos_objet is None:
            return
        dx = nouvelle_position_objet[0] - self._derniere_pos_objet[0]
        dy = nouvelle_position_objet[1] - self._derniere_pos_objet[1]
        dz = nouvelle_position_objet[2] - self._derniere_pos_objet[2]
        cam_pos = self.plotter.camera.position
        foc = self.plotter.camera.focal_point
        self.plotter.camera.position = (cam_pos[0]+dx, cam_pos[1]+dy, cam_pos[2]+dz)
        self.plotter.camera.focal_point = (foc[0]+dx, foc[1]+dy, foc[2]+dz)
        self._derniere_pos_objet = nouvelle_position_objet

    def pan(self, direction, pas=1.0):
        cam_pos = list(self.plotter.camera.position)
        foc = list(self.plotter.camera.focal_point)
        if direction == "haut":
            cam_pos[2] += pas; foc[2] += pas
        elif direction == "bas":
            cam_pos[2] -= pas; foc[2] -= pas
        elif direction == "gauche":
            cam_pos[0] -= pas; foc[0] -= pas
        elif direction == "droite":
            cam_pos[0] += pas; foc[0] += pas
        self.plotter.camera.position = tuple(cam_pos)
        self.plotter.camera.focal_point = tuple(foc)