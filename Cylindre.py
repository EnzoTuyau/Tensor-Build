import numpy as np


class Cylindre:
    def __init__(self, rayon, longueur, materiau, epaisseur=None):
        self.r = rayon
        self.l = longueur
        self.mat = materiau  # Objet contenant E et Poisson
        self.epaisseur = epaisseur

    def calculer_aire(self):
        if self.epaisseur:
            return np.pi * (self.r ** 2 - (self.r - self.epaisseur) ** 2)
        return np.pi * self.r ** 2

    def obtenir_matrice_rigidite_elementaire(self):
        # Cette méthode sera appelée par ton solveur SciPy
        # Elle utilise E, l'Aire, et le Moment d'Inertie
        A = self.calculer_aire()
        E = self.mat.module_young
        # Formule simplifiée pour la rigidité axiale : K = (A*E)/L
        k_axiale = (A * E) / self.l
        return k_axiale