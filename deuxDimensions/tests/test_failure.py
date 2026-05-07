"""Tests seuil / hysteresis rupture (von Mises %)."""

from __future__ import annotations

import unittest

from deuxDimensions.domain.failure import evaluer_latch_rupture


class TestLatchRupture(unittest.TestCase):
    def test_rearm_quand_util_basse(self):
        declenche, armed = evaluer_latch_rupture(90.0, False)
        self.assertFalse(declenche)
        self.assertTrue(armed)

    def test_pas_de_declenchement_si_desarme_et_encore_eleve(self):
        declenche, armed = evaluer_latch_rupture(105.0, False)
        self.assertFalse(declenche)
        self.assertFalse(armed)

    def test_declenchement_si_arme_et_au_dessus_seuil(self):
        declenche, armed = evaluer_latch_rupture(101.0, True)
        self.assertTrue(declenche)
        self.assertFalse(armed)

    def test_zone_intermediaire_conserve_armed(self):
        declenche, armed = evaluer_latch_rupture(97.0, True)
        self.assertFalse(declenche)
        self.assertTrue(armed)


if __name__ == "__main__":
    unittest.main()
