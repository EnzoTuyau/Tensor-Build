class Forme:
    """Classe de base — toutes les formes héritent d'ici."""

    def __init__(self, params):
        self.params = params  # dict : rayon, longueur, centre
        self.mesh = None
        self.actor = None

    def construire_mesh(self):
        """Chaque sous-classe implémente cette méthode et retourne un pv mesh."""
        raise NotImplementedError

    @property
    def r(self):
        return self.params["rayon"]

    @property
    def l(self):
        return self.params["longueur"]

    @property
    def c(self):
        return self.params["centre"]