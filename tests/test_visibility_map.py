import unittest
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from backend.api import app
from backend.horizon import RADIUS
from backend.visibility_map import trace, visibility_map
from backend.visibility_map import observers, trace_optimized
from backend.visibility_kernel import NUMBA_AVAILABLE
from backend.horizon import DEM


class VisibilityMapTests(unittest.TestCase):
    @unittest.skipUnless(NUMBA_AVAILABLE and DEM.exists(), 'Numba and local LOLA DEM required')
    def test_accelerator_matches_reference_for_multiple_body_directions(self):
        points = observers(64)[1]
        for target in [[1e8, 2e7, -1e6], [300000, 100000, 1000], [-300000, 200000, -15000]]:
            with self.subTest(target=target):
                np.testing.assert_array_equal(trace(points, target), trace_optimized(points, target))

    def test_bitset_round_trip_preserves_row_order_and_partial_last_byte(self):
        from base64 import b64decode
        valid = np.ones((3, 3), dtype=bool)
        expected = np.array([1, 0, 0, 1, 0, 1, 1, 0, 1], dtype=bool)
        with patch('backend.visibility_map.observers', return_value=(valid, np.zeros((9, 3)), np.zeros(9))), \
             patch('backend.visibility_map.body_map', return_value=expected):
            visibility_map.cache_clear()
            result = visibility_map(3, (1e8, 0, 0), None, 'bitset')
            decoded = np.unpackbits(np.frombuffer(b64decode(result['visiblePacked']), dtype=np.uint8))[:9]
            np.testing.assert_array_equal(decoded, expected)
            visibility_map.cache_clear()

    def test_surface_blocks_downward_ray_but_not_upward_ray(self):
        observer = np.array([[RADIUS, 0., 0.]])
        with patch('backend.visibility_map.terrain', return_value=(np.array([0.]), None)), \
             patch('backend.visibility_map.sample', side_effect=lambda p: np.zeros(len(p))):
            self.assertTrue(trace(observer, [1e8, 0, 0])[0])
            self.assertFalse(trace(observer, [-1e8, 0, 0])[0])

    def test_ridge_blocks_an_otherwise_clear_direction(self):
        observer = np.array([[RADIUS, 0., 0.]])
        direction = np.array([np.sin(np.radians(5)), np.cos(np.radians(5)), 0.])
        target = (observer[0]+1e8*direction)/1000
        with patch('backend.visibility_map.terrain', return_value=(np.array([1000.]), None)):
            with patch('backend.visibility_map.sample', side_effect=lambda p: np.zeros(len(p))):
                self.assertTrue(trace(observer, target)[0])
            with patch('backend.visibility_map.sample', side_effect=lambda p: np.where((p[:, 1] > 400) & (p[:, 1] < 1000), 1000., 0.)):
                self.assertFalse(trace(observer, target)[0])

    def test_combined_mask_is_intersection_and_excludes_unknown_terrain(self):
        sun, earth = (1e8, 0, 0), (0, 1e6, 0)
        valid = np.ones((2, 2), dtype=bool)
        with patch('backend.visibility_map.observers', return_value=(valid, np.zeros((4, 3)), np.array([0., 0., 0., np.nan]))), \
             patch('backend.visibility_map.body_map', side_effect=lambda size, target: np.array([True, True, False, True]) if target == sun else np.array([False, True, True, True])):
            visibility_map.cache_clear()
            self.assertEqual(visibility_map(2, sun, earth)['visible'], [0, 1, 0, 0])
            visibility_map.cache_clear()

    def test_request_rejects_empty_or_invalid_body_vectors(self):
        client = TestClient(app)
        for body in [{}, {'sun': [0, 0, 0]}, {'earth': [1, 2]}, {'earth': [0, 0, 1e6], 'size': 4096}]:
            self.assertEqual(client.post('/api/visibility-map', json=body).status_code, 422)

    def test_api_accepts_high_resolution_and_caps_only_without_compiler(self):
        client = TestClient(app)
        for accelerated, expected in [(True, 1536), (False, 512)]:
            with patch('backend.api.NUMBA_AVAILABLE', accelerated), \
                 patch('backend.api.visibility_map', return_value={'size': expected}) as compute:
                response = client.post('/api/visibility-map', json={'earth': [300000, 0, 0], 'size': 1536, 'encoding': 'bitset'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(compute.call_args.args, (expected, None, (300000., 0., 0.), 'bitset'))
