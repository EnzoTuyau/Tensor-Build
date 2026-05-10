"""Contrat des sorties contraintes (critère uniaxial)."""

from __future__ import annotations

import unittest

from deuxDimensions.physics.calculs import _hauteur_appui_max, calculer_donnees_physiques


def _bloc_minimal(**overrides):
    b = {
        "x": 0.0,
        "y": 0.0,
        "largeur": 1.0,
        "h0": 1.0,
        "material": "Acier",
        "density": 7850,
        "ext_force": 0.0,
        "ext_force_x": 0.0,
        "moment": 0.0,
        "pressure": 0.0,
    }
    b.update(overrides)
    return b


class TestStressUniaxialContract(unittest.TestCase):
    def test_utilization_egal_util_axial_flex(self):
        out = calculer_donnees_physiques([_bloc_minimal()], gravite_active=False)
        s = out["donnees_stress"][0]
        self.assertEqual(s["utilization"], s["util_axial_flex"])
        self.assertEqual(s["sigma_total"], s["sigma_max_normal"])
        self.assertNotIn("sigma_eq_von_mises", s)
        self.assertNotIn("util_von_mises", s)

    def test_cisaillement_ne_modifie_pas_utilization(self):
        """F_x élevé augmente τ mais l'utilisation globale reste axiale + flexion."""
        sans_fx = calculer_donnees_physiques(
            [_bloc_minimal(ext_force_x=0.0)], gravite_active=False
        )["donnees_stress"][0]
        avec_fx = calculer_donnees_physiques(
            [_bloc_minimal(ext_force_x=50e6)], gravite_active=False
        )["donnees_stress"][0]
        self.assertGreater(avec_fx["util_shear"], sans_fx["util_shear"])
    def test_hauteur_appui_max_utilise_ecrasement_affiche(self):
        blocs = [
            {"x": 0.0, "y": 0.0, "largeur": 1.0, "h0": 1.0},
            {"x": 0.0, "y": 1.0, "largeur": 1.0, "h0": 1.0},
        ]
        # delta_h = 1e-4 m -> raccourcissement visuel 0.5 m -> sommet a 0.5 m
        stress = [{"delta_h": 0.0001}, {"delta_h": 0.0}]
        self.assertAlmostEqual(_hauteur_appui_max(blocs, 1, stress), 0.5)
        self.assertAlmostEqual(_hauteur_appui_max(blocs, 1, None), 1.0)

if __name__ == "__main__":
    unittest.main()
