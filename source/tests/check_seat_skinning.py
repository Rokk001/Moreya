"""Preserve exact skinned vertices while bounding temporary animation arrays."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

import check_tavern_seat_clips as seat
from check_asset_runtime_equivalence import skeleton_xml


# Exercise the real rig evaluator with independent, deterministic geometry and weights.
class SeatSkinningTests(unittest.TestCase):
    # Prepare a small animated two-bone rig, not a mock of the production FK implementation.
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / 'rig.xml'
        path.write_text(skeleton_xml(), encoding='utf-8')
        self.skeleton = seat.feet.Skel(str(path))

    # Require bitwise equality, including signed zeros, rather than a geometric tolerance.
    def compare(self, local, vertices, weights):
        expected = seat.rest.skin_vertices(self.skeleton, local, vertices, weights)
        actual = seat.seat_skin_vertices(self.skeleton, local, vertices, weights)
        self.assertEqual(actual.dtype, expected.dtype)
        self.assertTrue(actual.flags.c_contiguous and actual.flags.owndata)
        np.testing.assert_array_equal(actual.view(np.uint64), expected.view(np.uint64))
        return actual

    # Retain every frame and vertex across chunk boundaries, mixed influences and fallback root weights.
    def test_frames_and_weights(self):
        random = np.random.default_rng(385)
        for frames, count in ((1, 7), (2, 7), (33, 1001), (385, 1001), (17, 32769)):
            local = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.linspace(0, 2, frames))
            vertices = random.normal(size=(count, 3))
            weights = [[(0, 0.25), (1, 0.75)] if i % 3 == 0 else [(1, 1.0)] if i % 3 == 1 else []
                       for i in range(count)]
            vertices.flags.writeable = False
            result = self.compare(local, vertices, weights)
            self.assertEqual(result.shape, (frames, count, 3))

    # Duplicate and negative bone assignments retain the reference advanced-index update behavior.
    def test_duplicate_negative_and_nonfinite(self):
        local = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.linspace(0, 2, 385))
        vertices = np.tile(np.array([[0.0, -0.0, 1.0], [np.nan, 1.0, 2.0], [np.inf, 2.0, 3.0]]), (334, 1))
        weights = [[(0, 0.2), (0, 0.8), (-1, 0.3)] for _ in vertices]
        with np.errstate(invalid='ignore'):
            self.compare(local, vertices, weights)

    # Empty, unusual and invalid inputs preserve the reference values or exception types.
    def test_errors_and_fallbacks(self):
        local = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.linspace(0, 2, 385))
        for vertices, weights in ((np.zeros((0, 3)), []), (np.zeros((3, 3), dtype=np.float32), [[], [], []]),
                                  (np.zeros((3, 2)), [[], [], []]), (np.zeros((3, 3)), [[(2, 1.0)]]),
                                  (np.zeros((3, 3)), [[], [], [], []]),
                                  (np.ma.array(np.zeros((3, 3))), [[], [], []])):
            try:
                expected = seat.rest.skin_vertices(self.skeleton, local, vertices, weights)
            except Exception as error:
                with self.assertRaises(type(error)):
                    seat.seat_skin_vertices(self.skeleton, local, vertices, weights)
            else:
                np.testing.assert_array_equal(seat.seat_skin_vertices(self.skeleton, local, vertices, weights), expected)

    # Strided frame/vertex views stay bitwise equal; unusual local arrays retain reference failures.
    def test_local_views_and_fallbacks(self):
        local = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.linspace(0, 2, 385))
        vertices = np.random.default_rng(901).normal(size=(2002, 3))[::2]
        weights = [[(0, 0.3), (1, 0.7)] for _ in vertices]
        for stride in (-1, 2):
            view = [tuple(value[::stride] for value in item) for item in local]
            saved = [tuple(value.copy() for value in item) for item in view]
            self.compare(view, vertices, weights)
            for actual, expected in zip(view, saved):
                for actual_value, expected_value in zip(actual, expected):
                    np.testing.assert_array_equal(actual_value, expected_value)
        empty = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.zeros(0))
        bad_width = list(local)
        bad_width[0] = (local[0][0][:, :2], local[0][1], local[0][2])
        single_root = list(local)
        single_root[0] = tuple(value[:1] for value in local[0])
        narrow = [tuple(value.astype(np.float32) for value in item) for item in local]
        for candidate in (empty, bad_width, single_root, narrow, []):
            try:
                expected = seat.rest.skin_vertices(self.skeleton, candidate, vertices, weights)
            except Exception as error:
                with self.assertRaises(type(error)):
                    seat.seat_skin_vertices(self.skeleton, candidate, vertices, weights)
            else:
                np.testing.assert_array_equal(seat.seat_skin_vertices(self.skeleton, candidate, vertices, weights), expected)

    # Promoted weight dtypes must not be rounded through the float64 scratch buffers.
    def test_weight_precision(self):
        local = self.skeleton.locals_at(self.skeleton.clips['SitDrink'], np.linspace(0, 2, 385))
        vertices = np.random.default_rng(210).normal(size=(1001, 3))
        for cast in (int, np.float32, np.longdouble):
            weights = [[(0, cast(1)), (1, cast(2))] for _ in vertices]
            self.compare(local, vertices, weights)
        weights = [[(0, 1.0 + 0.0j)] for _ in vertices]
        try:
            seat.rest.skin_vertices(self.skeleton, local, vertices, weights)
        except Exception as error:
            with self.assertRaises(type(error)):
                seat.seat_skin_vertices(self.skeleton, local, vertices, weights)
        else:
            self.fail('reference unexpectedly accepted complex weights')


if __name__ == '__main__':
    unittest.main()
