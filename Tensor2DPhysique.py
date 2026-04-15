"""
Tensor2DPhysique.py  —  Tensor Build
Toute la physique 2D de résistance des matériaux, dissociée de l'UI.
"""

import numpy as np

# ──────────────────────────────────────────────────────────────
#  Constantes
# ──────────────────────────────────────────────────────────────

GRAVITY   = 9.81
GROUND_Y  = 0.0
SNAP_TOL  = 0.18

MATERIAUX = {
    "Acier":     {"density": 7850, "E": 210e9, "sigma_y": 250e6, "nu": 0.30},
    "Béton":     {"density": 2400, "E":  30e9, "sigma_y":  30e6, "nu": 0.20},
    "Aluminium": {"density": 2700, "E":  70e9, "sigma_y": 270e6, "nu": 0.33},
    "Bois":      {"density":  600, "E":  12e9, "sigma_y":  40e6, "nu": 0.35},
    "Fonte":     {"density": 7200, "E": 170e9, "sigma_y": 200e6, "nu": 0.26},
}


# ──────────────────────────────────────────────────────────────
#  Classe principale
# ──────────────────────────────────────────────────────────────

class Tensor2DPhysique:
    """
    Moteur physique 2D de résistance des matériaux.
    Indépendant de toute UI (matplotlib, Qt, etc.).

    Chaque bloc est un dict avec les clés :
        patch       — objet matplotlib Rectangle (pour lire x, y, w, h)
        material    — nom du matériau (clé dans MATERIAUX)
        density     — densité kg/m³
        ext_force   — force ponctuelle appliquée (N)
        pressure    — pression distribuée (Pa)
        moment      — moment fléchissant (N·m)
    """

    # ── Géométrie de patch ────────────────────────────────────

    @staticmethod
    def geom(bloc):
        """Retourne (x, y, w, h) du patch matplotlib du bloc."""
        p = bloc["patch"]
        x, y = p.get_xy()
        return x, y, p.get_width(), p.get_height()

    # ── Charge verticale équivalente ──────────────────────────

    def charge_verticale(self, bloc):
        """
        Charge verticale totale transmise vers le bas par ce bloc (N).
        Comprend : poids propre + force ext. + pression distribuée.
        """
        x, y, w, h = self.geom(bloc)
        return (
            bloc["density"] * w * h * GRAVITY
            + bloc["ext_force"]
            + bloc["pressure"] * w
        )

    # ── Détection des contacts ────────────────────────────────

    @staticmethod
    def overlaps_x(bloc_a, bloc_b):
        """Vérifie le chevauchement horizontal entre deux blocs."""
        xa, _ = bloc_a["patch"].get_xy()
        wa    = bloc_a["patch"].get_width()
        xb, _ = bloc_b["patch"].get_xy()
        wb    = bloc_b["patch"].get_width()
        return xa < xb + wb and xb < xa + wa

    def contact_pairs(self, blocs, tol=SNAP_TOL):
        """
        Retourne la liste des paires en contact vertical :
        (i_bas, i_haut, fraction_recouvrement).
        """
        paires = []
        for i in range(len(blocs)):
            for j in range(len(blocs)):
                if i == j:
                    continue
                xi, yi = blocs[i]["patch"].get_xy()
                wi     = blocs[i]["patch"].get_width()
                hi     = blocs[i]["patch"].get_height()
                xj, yj = blocs[j]["patch"].get_xy()
                wj     = blocs[j]["patch"].get_width()

                contact_vertical = abs((yi + hi) - yj) <= tol
                if contact_vertical and self.overlaps_x(blocs[i], blocs[j]):
                    largeur_contact = min(xi + wi, xj + wj) - max(xi, xj)
                    fraction = largeur_contact / min(wi, wj)
                    paires.append((i, j, fraction))
        return paires

    # ── Hauteur d'appui (gravité) ─────────────────────────────

    def hauteur_appui_max(self, blocs, idx):
        """
        Plus haute surface sous le bloc idx :
        sol (GROUND_Y) ou sommet du bloc le plus proche en dessous.
        """
        x_me, y_me, w_me, _ = self.geom(blocs[idx])
        plancher = GROUND_Y
        for i2, rd2 in enumerate(blocs):
            if i2 == idx:
                continue
            x2, y2, w2, h2 = self.geom(rd2)
            if x_me < x2 + w2 and x2 < x_me + w_me:
                sommet2 = y2 + h2
                if sommet2 <= y_me + 0.001:
                    plancher = max(plancher, sommet2)
        return plancher

    # ── Résolution de collision (drag) ────────────────────────

    def resoudre_collision(self, idx_mobile, blocs):
        """
        Repousse le bloc mobile hors de tout autre bloc qu'il traverse.
        Utilise l'axe de pénétration minimale (AABB).
        Retourne True si une collision a été résolue.
        """
        patch  = blocs[idx_mobile]["patch"]
        mx, my = patch.get_xy()
        larg   = patch.get_width()
        haut   = patch.get_height()
        collision = False

        for i, autre in enumerate(blocs):
            if i == idx_mobile:
                continue
            pa = autre["patch"]
            ox, oy = pa.get_xy()
            ow, oh = pa.get_width(), pa.get_height()

            chev_x = mx < ox + ow and ox < mx + larg
            chev_y = my < oy + oh and oy < my + haut

            if chev_x and chev_y:
                pen_haut   = (oy + oh) - my
                pen_bas    = (my + haut) - oy
                pen_droite = (ox + ow) - mx
                pen_gauche = (mx + larg) - ox
                m = min(pen_haut, pen_bas, pen_droite, pen_gauche)

                if m == pen_haut:
                    patch.set_xy((mx, oy + oh))
                elif m == pen_bas:
                    patch.set_xy((mx, oy - haut))
                elif m == pen_droite:
                    patch.set_xy((ox + ow, my))
                else:
                    patch.set_xy((ox - larg, my))

                mx, my = patch.get_xy()
                collision = True

        return collision

    # ── Statistiques globales de section ─────────────────────

    def statistiques_section(self, blocs):
        """
        Calcule les propriétés géométriques et mécaniques de la section
        formée par l'ensemble des blocs.

        Retourne :
            aire_totale (m²), XG (m), YG (m),
            Ixx (m⁴), Iyy (m⁴), masse (kg/m)
        """
        aire_totale = sx = sy = masse = 0.0
        rectangles = []

        for bloc in blocs:
            x, y, w, h = self.geom(bloc)
            a = w * h
            rectangles.append((x, y, w, h, a))
            aire_totale += a
            sx += (x + w / 2) * a
            sy += (y + h / 2) * a
            masse += bloc["density"] * a

        XG = sx / aire_totale
        YG = sy / aire_totale

        Ixx = sum(
            (w * h**3) / 12 + w * h * (y + h / 2 - YG) ** 2
            for x, y, w, h, a in rectangles
        )
        Iyy = sum(
            (h * w**3) / 12 + w * h * (x + w / 2 - XG) ** 2
            for x, y, w, h, a in rectangles
        )
        return aire_totale, XG, YG, Ixx, Iyy, masse

    # ── Contrainte de Von Mises ───────────────────────────────

    @staticmethod
    def von_mises(sigma_x, sigma_y=0.0, tau_xy=0.0):
        """
        Contrainte équivalente de Von Mises (Pa).
        σ_vm = √(σx² - σx·σy + σy² + 3·τxy²)
        """
        return np.sqrt(
            sigma_x**2
            - sigma_x * sigma_y
            + sigma_y**2
            + 3 * tau_xy**2
        )

    # ── Taux d'utilisation ────────────────────────────────────

    @staticmethod
    def statut_utilisation(util_pct):
        """Libellé et symbole selon le % par rapport à σ_y."""
        if util_pct < 80:
            return "OK", "✓"
        if util_pct < 100:
            return "⚠️ Attention", "!"
        return "❌ RUPTURE", "✗"

    # ── Calcul principal des contraintes ─────────────────────

    def calculer_contraintes(self, blocs):
        """
        Calcule pour chaque bloc :
          - force axiale totale (poids + contacts + charges ext.)
          - contrainte axiale et de flexion
          - contrainte de Von Mises
          - taux d'utilisation / σ_y

        Retourne (donnees_stress, paires, stats_section).

        donnees_stress : liste de dicts, un par bloc :
            sigma_total, sigma_axial,
            sigma_bending_top, sigma_bending_bot,
            sigma_von_mises,
            ext_force, pressure, utilization, F_axial

        paires         : liste de (i_bas, i_haut, fraction)
        stats_section  : dict avec aire, XG, YG, Ixx, Iyy, masse
        """
        if not blocs:
            return [], [], {}

        aire, XG, YG, Ixx, Iyy, masse = self.statistiques_section(blocs)
        stats = {
            "aire": aire, "XG": XG, "YG": YG,
            "Ixx": Ixx, "Iyy": Iyy, "masse": masse,
        }

        paires = self.contact_pairs(blocs)
        donnees = []

        for i, bloc in enumerate(blocs):
            _, _, w, h = self.geom(bloc)
            aire_loc = w * h
            mat = MATERIAUX.get(bloc["material"], MATERIAUX["Acier"])

            # ── Forces ──
            poids      = bloc["density"] * aire_loc * GRAVITY
            F_ext      = bloc["ext_force"]
            F_pression = bloc["pressure"] * w

            # Charge transmise par les blocs posés dessus
            F_contact = sum(
                self.charge_verticale(blocs[j])
                for (i_bas, j, _) in paires if i_bas == i
            )

            F_axial    = poids + F_ext + F_pression + F_contact
            sigma_axial = F_axial / aire_loc

            # ── Flexion ──
            M       = bloc["moment"]
            I_local = (w * h**3) / 12
            sig_top = M * ( h / 2) / I_local if I_local > 0 else 0.0
            sig_bot = M * (-h / 2) / I_local if I_local > 0 else 0.0

            sigma_max = max(
                abs(sigma_axial + sig_top),
                abs(sigma_axial + sig_bot),
            )

            # ── Von Mises (cisaillement nul ici, extensible) ──
            tau_xy = 0.0  # à enrichir si forces horizontales ajoutées
            svm = self.von_mises(sigma_axial, sigma_y=0.0, tau_xy=tau_xy)

            # ── Taux d'utilisation ──
            sigma_y_lim = mat["sigma_y"]
            taux = sigma_max / sigma_y_lim * 100

            donnees.append({
                "sigma_total":       sigma_max,
                "sigma_axial":       sigma_axial,
                "sigma_bending_top": sig_top,
                "sigma_bending_bot": sig_bot,
                "sigma_von_mises":   svm,
                "ext_force":         F_ext + F_pression,
                "pressure":          bloc["pressure"],
                "utilization":       taux,
                "F_axial":           F_axial,
            })

        return donnees, paires, stats