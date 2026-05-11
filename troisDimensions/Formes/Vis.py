import pyvista as pv
from .Forme import Forme

class Vis(Forme):
    NOM = "Vis"
    # Constructeur de la classe Vis, hérite de Forme
    def construire_mesh(self):
        r_vis = self.r * 0.15
        l_vis = self.l * 0.3
        cx, cy, cz = self.c

        # 1. Tête : cylindre très plat et large
        r_tete = r_vis * 2.5
        h_tete = l_vis * 0.12
        x_tete = cx - (l_vis / 2) - (h_tete / 2)
        tete = pv.Cylinder(center=(x_tete, cy, cz),
                           radius=r_tete,
                           height=h_tete,
                           direction=(1, 0, 0))

        # 2. Col : cylindre principal (~75 % de la longueur)
        h_col = l_vis * 0.75
        x_col = cx - (l_vis / 2) + (h_col / 2)
        col = pv.Cylinder(center=(x_col, cy, cz),
                          radius=r_vis,
                          height=h_col,
                          direction=(1, 0, 0))

        # 3. Cône de pointe (~25 % de la longueur)
        h_cone = l_vis * 0.25
        x_cone_base = cx - (l_vis / 2) + h_col
        x_cone_centre = x_cone_base + (h_cone / 2)
        cone = pv.Cone(center=(x_cone_centre, cy, cz),
                       direction=(1, 0, 0),
                       height=h_cone,
                       radius=r_vis,
                       resolution=30)

        return tete + col + cone
