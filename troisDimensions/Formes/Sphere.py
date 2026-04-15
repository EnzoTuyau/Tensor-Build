from Formes.Forme import Forme
import pyvista as pv

class Sphere(Forme):
    NOM = "Sphère"

    def construire_mesh(self):
        return pv.Sphere(center=self.c, radius=self.r)