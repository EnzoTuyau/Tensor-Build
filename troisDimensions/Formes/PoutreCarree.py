import pyvista as pv
from .Forme import Forme


class PoutreCarree(Forme):
    NOM = "Poutre (Carrée)"

    def construire_mesh(self):
        return pv.Cube(center=self.c,
                       x_length=self.l,
                       y_length=self.r * 2,
                       z_length=self.r * 2)