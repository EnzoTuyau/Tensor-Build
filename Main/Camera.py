class Camera:
    """Gère la position et le comportement de la caméra."""

    def __init__(self, plotter, position=(30, 30, 20), focal_point=(0, 0, 0), up=(0, 0, 1)):
        self.plotter = plotter
        self.position_initiale = position
        self.focal_point_initial = focal_point
        self.up_initial = up

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