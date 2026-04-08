"""materiaux.py — Propriétés mécaniques des matériaux."""

class Materiau:
    PRESETS = {
        "Acier":   dict(module_young=200e9, poisson=0.30, limite_elastique=250e6, densite=7850),
        "Alum.":   dict(module_young=69e9,  poisson=0.33, limite_elastique=270e6, densite=2700),
        "Titane":  dict(module_young=114e9, poisson=0.34, limite_elastique=880e6, densite=4510),
        "Carbone": dict(module_young=70e9,  poisson=0.10, limite_elastique=600e6, densite=1600),
        "Béton":   dict(module_young=30e9,  poisson=0.20, limite_elastique=30e6,  densite=2400),
        "Bois":    dict(module_young=12e9,  poisson=0.35, limite_elastique=40e6,  densite=600),
    }

    def __init__(self, nom, module_young, poisson, limite_elastique, densite):
        self.nom = nom
        self.module_young = module_young
        self.poisson = poisson
        self.limite_elastique = limite_elastique
        self.densite = densite

    @classmethod
    def depuis_preset(cls, nom):
        if nom not in cls.PRESETS:
            return cls("Inconnu", 1e9, 0.3, 1e6, 1000)
        return cls(nom, **cls.PRESETS[nom])