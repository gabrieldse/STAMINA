import unittest
from unittest.mock import patch
import numpy as np
from backend.horizon import basis, sector_angles, body_visibility, RADIUS


class HorizonTests(unittest.TestCase):
    def test_curvature_places_distant_level_ground_below_horizontal(self):
        up, east, north = basis(0, 0)
        theta = .01
        delta = RADIUS*np.array([[np.cos(theta)-1, np.sin(theta), 0]])
        sectors, angles = sector_angles(delta, up, east, north)
        self.assertEqual(sectors[0], 180)  # east
        self.assertAlmostEqual(angles[0], -theta/2)

    def test_ridge_blocks_body_above_flat_horizon(self):
        observer = np.array([RADIUS, 0, 0])
        skyline = np.full(720, np.radians(10))
        for angle, expected in [(5, False), (15, True)]:
            target = observer + 1e8*np.array([np.sin(np.radians(angle)), np.cos(np.radians(angle)), 0])
            with patch('backend.horizon.profile', return_value=(observer, skyline)):
                self.assertEqual(bool(body_visibility([target/1000], 0, 0)[0]), expected)

    def test_azimuth_wraps_at_north(self):
        sectors, _ = sector_angles(np.array([[0, -1e-9, 1], [0, 1e-9, 1]]), *basis(0, 0))
        self.assertEqual(sectors.tolist(), [719, 0])
