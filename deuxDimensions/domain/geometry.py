"""Geometrie 2D partagee (rectangles axis-aligned comme polygones)."""


def sommets_rectangle_ax(x: float, y: float, largeur: float, hauteur: float):
    """Sommets du rectangle [bas-gauche, bas-droit, haut-droit, haut-gauche]."""
    return [
        (x, y),
        (x + largeur, y),
        (x + largeur, y + hauteur),
        (x, y + hauteur),
    ]
