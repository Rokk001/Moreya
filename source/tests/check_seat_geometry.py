"""Compare accelerated seat collision geometry with the unchanged original predicate."""
import unittest

import numpy as np

import check_tavern_seat_clips as seat


# Keep independent fixture bounds fixed so an accidentally omitted furniture box is detected.
BOXES = [((-0.323, 0.323), (-0.588, 0.588), (0.37, 0.4425)),
         ((-0.193, 0.193), (0.135, 0.521), (0.0, 0.38)),
         ((-0.193, 0.193), (-0.521, -0.135), (0.0, 0.38)),
         ((0.3236, 0.4986), (-0.656, 0.656), (0.202, 0.2575)),
         ((-0.4986, -0.3236), (-0.656, 0.656), (0.202, 0.2575))]


# Verify exact results and error semantics, not a relaxed numerical tolerance.
class SeatGeometryTests(unittest.TestCase):
    # Every box and strict face boundary agrees, including next-representable values on each side.
    def test_boundaries(self):
        self.assertEqual(seat.drink.BENCH_OFFSET, 0.4116)
        self.assertEqual(seat.drink.STOOL_DISTANCE, 0.8)
        boxes = list(BOXES)
        for side in (1, -1):
            for end in (1, -1):
                boxes.append(((side * 0.4116 - 0.042,
                               side * 0.4116 + 0.042),
                              (0.515, 0.588) if end > 0 else (-0.588, -0.515), (0.0, 0.21)))
        self.assertEqual(len(boxes), 9)
        for box in boxes:
            middle = np.array([(low + high) / 2 for low, high in box])
            samples = [middle]
            for axis in range(3):
                for edge in box[axis]:
                    for value in (np.nextafter(edge, -np.inf), edge, np.nextafter(edge, np.inf)):
                        point = middle.copy()
                        point[axis] = value
                        samples.append(point)
            for point in samples:
                points = (point - [0, 0.8, 0])[None]
                self.assertEqual(seat.stool_geometry_depth(points), seat.drink.stool_depth(points))

    # Generated clouds, noncontiguous views, nonfinite coordinates and empty clouds retain exact results.
    def test_clouds(self):
        random = np.random.default_rng(385)
        for count in (0, 1, 17, 32768, 32769):
            points = random.uniform(-1.0, 1.0, (count, 3))
            points.flags.writeable = False
            for cloud in (points, points[::2], points[::-1]):
                original = cloud.copy()
                self.assertEqual(seat.stool_geometry_depth(cloud), seat.drink.stool_depth(cloud))
                np.testing.assert_array_equal(cloud, original)
        for invalid in (np.nan, np.inf, -np.inf):
            for axis in range(3):
                points = random.uniform(-1.0, 1.0, (19, 3))
                points[0, axis] = invalid
                self.assertEqual(seat.stool_geometry_depth(points), seat.drink.stool_depth(points))

    # Other numeric types and invalid shapes use the unchanged reference arithmetic/error handling.
    def test_fallbacks(self):
        for points in (np.zeros((3, 3), dtype=np.float32), np.ones((3, 3), dtype=int),
                       np.zeros((3, 3), dtype=object), np.zeros((3, 2)), np.zeros((3, 4)),
                       np.zeros((2, 3, 3)), np.array([['bad'] * 3]),
                       np.ma.array([[0.0, -0.5, 0.15]], mask=[[False, True, False]])):
            try:
                expected = seat.drink.stool_depth(points)
            except Exception as error:
                with self.assertRaises(type(error)):
                    seat.stool_geometry_depth(points)
            else:
                self.assertEqual(seat.stool_geometry_depth(points), expected)

    # A collision beyond the first chunk in the last sampled frame still exceeds the unchanged limit.
    def test_late_collision(self):
        points = np.full((385, 100, 3), 10.0)
        points[-1, -1] = [0.0, -0.5, 0.15]
        expected = max(seat.drink.stool_depth(frame * scale) for frame in points
                       for scale in (seat.seats.LEVEL_SCALE_LOW, seat.seats.LEVEL_SCALE_HIGH))
        self.assertEqual(seat.stool_clip_depth(points), expected)
        self.assertGreater(expected, seat.MAX_TABLE_DEPTH)


if __name__ == '__main__':
    unittest.main()
