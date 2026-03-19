import pyvista as pv


class Sol:
    """Représente le sol de la scène 3D."""

    def __init__(self, plotter, hauteur=0.0, taille=50, couleur="lightgreen", opacite=0.5):
        """
        plotter  : le SafeQtInteractor de la scène
        hauteur  : position Z du sol (défaut = 0)
        taille   : largeur et longueur du plan (défaut = 50 unités)
        couleur  : couleur du sol
        opacite  : transparence (0.0 = invisible, 1.0 = opaque)
        """
        self.plotter = plotter
        self.hauteur = hauteur
        self.taille  = taille
        self.couleur = couleur
        self.opacite = opacite
        self.actor   = None

    def afficher(self):
        """Crée et affiche le sol dans la scène."""
        mesh = pv.Plane(
            center=(0, 0, self.hauteur),
            direction=(0, 0, 1),
            i_size=self.taille,
            j_size=self.taille
        )
        self.actor = self.plotter.add_mesh(
            mesh,
            color=self.couleur,
            opacity=self.opacite,
            show_edges=True
        )

    def masquer(self):
        """Retire le sol de la scène."""
        if self.actor:
            self.plotter.remove_actor(self.actor)
            self.actor = None