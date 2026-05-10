"""Extraction des 4 sommets d'un polygone patch (rupture / fissures)."""

from __future__ import annotations

import unittest

import numpy as np

from deuxDimensions.domain.geometry import sommets_quad_depuis_xy_patch


class TestSommetsQuadPatch(unittest.TestCase):
    def test_quatre_points_sans_fermeture(self):
        xy = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 2.0], [0.0, 2.0]], dtype=np.float64)
        q = sommets_quad_depuis_xy_patch(xy)
        self.assertEqual(len(q), 4)
        self.assertEqual(q[3], (0.0, 2.0))

    def test_cinq_points_avec_duplicata_fermeture(self):
        xy = np.array(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 2.0], [0.0, 2.0], [0.0, 0.0]],
            dtype=np.float64,
        )
        q = sommets_quad_depuis_xy_patch(xy)
        self.assertEqual(len(q), 4)
        self.assertEqual(q[3], (0.0, 2.0))


if __name__ == "__main__":
    unittest.main()
