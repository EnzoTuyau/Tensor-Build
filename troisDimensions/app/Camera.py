import math
import numpy as np

class Camera:
    """Caméra 3D orbitale contrainte au-dessus du sol."""

    SOL_Z = -10.0          # hauteur du sol
    ELEV_MIN = 5.0         # hauteur minimale de la caméra au-dessus du sol

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
        # Active la rotation orbitale native de PyVista
        self.plotter.camera.position = self.position_initiale
        self.plotter.camera.focal_point = self.focal_point_initial
        self.plotter.camera.up = self.up_initial
        # Style orbital : le vecteur "up" est toujours (0,0,1), le sol reste plat
        self.plotter.enable_terrain_style(mouse_wheel_zooms=True)

    def _contraindre_au_dessus_sol(self):
        """Empêche la caméra de passer sous le sol."""
        z_min = self.SOL_Z + self.ELEV_MIN
        cam_pos = list(self.plotter.camera.position)
        foc = list(self.plotter.camera.focal_point)

        if cam_pos[2] < z_min:
            # Calcule le vecteur caméra → focal point
            dx = foc[0] - cam_pos[0]
            dy = foc[1] - cam_pos[1]
            dz = foc[2] - cam_pos[2]

            # Distance horizontale
            dist_horiz = (dx**2 + dy**2) ** 0.5

            # Recalcule Z de la caméra pour qu'elle soit au niveau z_min
            # en gardant la même direction horizontale
            cam_pos[2] = z_min

            # Ajuste le focal point pour garder le même angle
            if dist_horiz > 0:
                ratio = abs(cam_pos[2] - foc[2]) / dist_horiz
                # garde le focal point intact, seule la caméra remonte
            
            self.plotter.camera.position = tuple(cam_pos)

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
        self._contraindre_au_dessus_sol()
        self._derniere_pos_objet = nouvelle_position_objet

    def pan(self, direction, pas=1.0):
        
        cam_pos = np.array(self.plotter.camera.position)
        foc = np.array(self.plotter.camera.focal_point)
        up = np.array([0, 0, 1])

        # Vecteur "avant" (de la caméra vers le focal point)
        avant = foc - cam_pos
        avant[2] = 0  # garde le mouvement horizontal
        avant = avant / (np.linalg.norm(avant) + 1e-9)

        # Vecteur "droite" perpendiculaire à avant
        droite = np.cross(avant, up)
        droite = droite / (np.linalg.norm(droite) + 1e-9)

        if direction == "haut":
            delta = np.array([0, 0, pas])
        elif direction == "bas":
            delta = np.array([0, 0, -pas])
        elif direction == "gauche":
            delta = -droite * pas
        elif direction == "droite":
            delta = droite * pas
        else:
            return

        nouvelle_pos = tuple(cam_pos + delta)
        nouveau_foc = tuple(foc + delta)

        self.plotter.camera.position = nouvelle_pos
        self.plotter.camera.focal_point = nouveau_foc
        self._contraindre_au_dessus_sol()