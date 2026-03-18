import pyvista as pv
from Formes.Forme import Forme

class Cube(Forme):
    NOM = "Cube"

    def construire_mesh(self):
        cote = self.r * 2
        return pv.Cube(center=self.c,
                       x_length=cote,
                       y_length=cote,
                       z_length=cote)