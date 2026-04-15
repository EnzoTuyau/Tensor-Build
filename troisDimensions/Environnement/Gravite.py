class Gravite:
    """Gère la constante gravitationnelle et calcule les forces sur les formes."""

    # Densités approximatives en kg/m³
    DENSITES = {
        "Acier":     7850,
        "Aluminium": 2700,
        "Bois":      600,
        "Plastique": 1200,
    }

    def __init__(self, g=9.81):
        """
        g : accélération gravitationnelle en m/s² (défaut = 9.81)
        """
        self.g = g

    def calculer_masse(self, forme, materiau):
        """
        Calcule la masse approximative d'une forme selon son volume et son matériau.

        forme    : instance d'une sous-classe de Forme
        materiau : nom du matériau (str) ex: "Acier"

        Retourne la masse en kg.
        """
        rho    = self.DENSITES.get(materiau, 1000)  # défaut = eau si inconnu
        volume = self._calculer_volume(forme)
        return rho * volume

    def calculer_poids(self, forme, materiau):
        """
        Calcule le poids (force gravitationnelle) d'une forme en Newtons.

        Retourne le poids en N.
        """
        masse = self.calculer_masse(forme, materiau)
        return masse * self.g

    def rapport_complet(self, formes, materiau):
        """
        Génère un rapport texte avec masse et poids pour une liste de formes.

        formes   : liste d'instances de Forme
        materiau : nom du matériau sélectionné

        Retourne une chaîne de caractères formatée.
        """
        lignes = [f"Gravité appliquée  (g = {self.g} m/s²)\n"]
        total_masse = 0.0
        total_poids = 0.0

        for forme in formes:
            masse  = self.calculer_masse(forme, materiau)
            poids  = self.calculer_poids(forme, materiau)
            total_masse += masse
            total_poids += poids
            lignes.append(
                f"  • {forme.NOM} "
                f"| masse ≈ {masse:.2f} kg "
                f"| poids ≈ {poids:.2f} N"
            )

        lignes.append(f"\nTotal : {total_masse:.2f} kg  |  {total_poids:.2f} N")
        return "\n".join(lignes)

    # ------------------------------------------------------------------ #
    #  Privé                                                               #
    # ------------------------------------------------------------------ #

    def _calculer_volume(self, forme):
        """
        Calcule un volume approximatif selon le type de forme.
        Utilise les paramètres rayon (r) et longueur (l) de la forme.
        """
        import math
        r = forme.r
        l = forme.l

        nom = forme.NOM

        if nom == "Cylindre" or nom == "Prisme Triangulaire":
            return math.pi * r**2 * l

        elif nom == "Poutre (Carrée)":
            return (r * 2) * (r * 2) * l        # section carrée × longueur

        elif nom == "Sphère":
            return (4/3) * math.pi * r**3

        elif nom == "Cube":
            cote = r * 2
            return cote**3

        elif nom == "Vis":
            # Volume approximatif du col seulement
            r_vis = r * 0.15
            l_vis = l * 0.3
            return math.pi * r_vis**2 * l_vis

        else:
            # Fallback : cylindre
            return math.pi * r**2 * l