#1. Classe gérant les calculs liés à la gravité
class Gravite:
    """Gère la constante gravitationnelle et calcule les forces sur les formes."""

    #2. Densités approximatives des matériaux en kg/m³
    DENSITES = {
        "Acier":     7850,
        "Aluminium": 2700,
        "Bois":      600,
        "Plastique": 1200,
    }

    #3. Initialisation de la gravité
    def __init__(self, g=9.81):

        # g : accélération gravitationnelle en m/s² (défaut = 9.81)
        self.g = g

    #4. Calcul de la masse d’une forme et retourne la masse en kg.
    def calculer_masse(self, forme, materiau):

        # Recherche de la densité du matériau
        # Si le matériau est inconnu, utilise 1000 par défaut
        rho = self.DENSITES.get(materiau, 1000)

        # Calcul du volume de la forme
        volume = self._calculer_volume(forme)

        # Masse = densité × volume
        return rho * volume

    #5. Calcul du poids d’une forme, calcule le poids (force gravitationnelle) d'une forme en Newtons. et retourne le poids en N.
    def calculer_poids(self, forme, materiau):

        # Calcul de la masse
        masse = self.calculer_masse(forme, materiau)

        # Poids = masse × gravité
        return masse * self.g

    #6. Génération d’un rapport complet
    def rapport_complet(self, formes, materiau):
        """
        Génère un rapport texte avec masse et poids pour une liste de formes.

        formes   : liste d'instances de Forme
        materiau : nom du matériau sélectionné

        Retourne une chaîne de caractères formatée avec les détails de chaque forme et les totaux.
        """

        # Création de la première ligne du rapport
        lignes = [f"Gravité appliquée  (g = {self.g} m/s²)\n"]

        # Variables pour accumuler les totaux
        total_masse = 0.0
        total_poids = 0.0

        # Parcours de toutes les formes
        for forme in formes:

            # Calcul de la masse et du poids
            masse = self.calculer_masse(forme, materiau)
            poids = self.calculer_poids(forme, materiau)

            # Ajout aux totaux
            total_masse += masse
            total_poids += poids

            # Ajout des informations de la forme au rapport
            lignes.append(
                f"  • {forme.NOM} "
                f"| masse ≈ {masse:.2f} kg "
                f"| poids ≈ {poids:.2f} N"
            )

        # Ajout des valeurs totales
        lignes.append(f"\nTotal : {total_masse:.2f} kg  |  {total_poids:.2f} N")

        # Transformation de la liste en texte final
        return "\n".join(lignes)

    # Méthodes privées

    #7. Calcul du volume selon le type de forme
    def _calculer_volume(self, forme):
        """
        Calcule un volume approximatif selon le type de forme.
        Utilise les paramètres rayon (r) et longueur (l) de la forme.
        """

        import math

        # Récupération des dimensions de la forme
        r = forme.r
        l = forme.l

        # Nom de la forme
        nom = forme.NOM

        # Volume d’un cylindre ou d’un prisme triangulaire
        if nom == "Cylindre" or nom == "Prisme Triangulaire":
            return math.pi * r**2 * l

        # Volume d’une poutre carrée
        elif nom == "Poutre (Carrée)":

            # section carrée × longueur
            return (r * 2) * (r * 2) * l

        # Volume d’une sphère
        elif nom == "Sphère":
            return (4/3) * math.pi * r**3

        # Volume d’un cube
        elif nom == "Cube":
            cote = r * 2
            return cote**3

        # Volume approximatif d’une vis
        elif nom == "Vis":

            # Volume approximatif du col seulement
            r_vis = r * 0.15
            l_vis = l * 0.3

            return math.pi * r_vis**2 * l_vis

        # Volume par défaut si la forme est inconnue
        else:

            # Fallback : cylindre
            return math.pi * r**2 * l