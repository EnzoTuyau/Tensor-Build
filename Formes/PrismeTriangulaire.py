from Formes.Forme import Forme
import pyvista as pv

class PrismeTriangulaire(Forme):
    NOM = "Prisme Triangulaire"

    def construire_mesh(self):
        # Cylindre à 3 côtés = prisme triangulaire
        return pv.Cylinder(center=self.c, radius=self.r,
                           height=self.l, resolution=3,
                           direction=(1, 0, 0))