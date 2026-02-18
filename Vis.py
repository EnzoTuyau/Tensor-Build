class Vis:
    def __init__(self, diametre, longueur, grade="8.8"):
        self.d = diametre
        self.l = longueur
        self.grade = grade
        # Calcul auto de la limite élastique selon le grade (ex: 8.8 -> 640 MPa)
        self.limite_elastique = self._definir_resistance(grade)

    def _definir_resistance(self, grade):
        data = {"8.8": 640, "10.9": 940, "12.9": 1080}
        return data.get(grade, 400)

    def calculer_contrainte(self, force_traction):
        # Aire de la section (simplifiée)
        aire = 3.1415 * (self.d / 2) ** 2
        return force_traction / aire

    def est_rompue(self, force_actuelle):
        return self.calculer_contrainte(force_actuelle) > self.limite_elastique