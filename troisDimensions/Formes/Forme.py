#1. Classe de base des formes
class Forme:
    """Classe de base — toutes les formes héritent."""

    #2. Initialisation des attributs communs
    def __init__(self, params):
        self.params = params  # dict : rayon, longueur, centre
        self.mesh = None      # Contiendra le mesh de la forme
        self.actor = None     # Contiendra l’acteur associé à la forme

    #3. Méthode à redéfinir dans les sous-classes
    def construire_mesh(self):
        """Chaque sous-classe implémente cette méthode et retourne un pv mesh."""
        raise NotImplementedError

    #4. Accès au rayon
    @property
    def r(self):
        return self.params["rayon"]

    #5. Accès à la longueur
    @property
    def l(self):
        return self.params["longueur"]

    #6. Accès au centre
    @property
    def c(self):
        return self.params["centre"]