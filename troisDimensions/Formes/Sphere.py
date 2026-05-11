from .Forme import Forme
import pyvista as pv

class Sphere(Forme):
    NOM = "Sphère"
    # Constructeur de la classe Sphere, hérite de Forme
    def construire_mesh(self):
        return pv.Sphere(center=self.c, radius=self.r)