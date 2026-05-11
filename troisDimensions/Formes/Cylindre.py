from .Forme import Forme
import pyvista as pv

class Cylindre(Forme):
    NOM = "Cylindre"
    # Constructeur de la classe Cylindre, hérite de Forme
    def construire_mesh(self):
        return pv.Cylinder(center=self.c, radius=self.r,
                           height=self.l, direction=(1, 0, 0))
