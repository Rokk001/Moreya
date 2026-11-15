"""Compare bounded seat geometry calculations with the unchanged full reference checks."""
import numpy as np

import check_tavern_seat_clips as check


# Every sampled frame must agree, including changing witnesses and a final loss of support.
def check_sequence():
    triangles = np.arange(6).reshape(2, 3)
    contact = np.array([[-0.1, -0.1, check.seats.BENCH_TOP],
                        [0.1, -0.1, check.seats.BENCH_TOP],
                        [0.0, 0.1, check.seats.BENCH_TOP]])
    frames = np.tile(np.concatenate((contact, contact + [2.0, 0.0, 0.0])), (385, 1, 1))
    frames[192:, :3] += [2.0, 0.0, 0.0]
    frames[192:, 3:] -= [2.0, 0.0, 0.0]
    frames[-1, 3:] += [2.0, 0.0, 0.0]
    for scale in (check.seats.LEVEL_SCALE_LOW, check.seats.LEVEL_SCALE_HIGH):
        witness = check.StoolSupportWitness(triangles, 6)
        actual = [witness(frame * scale) for frame in frames]
        expected = [check.has_stool_surface_support(frame * scale, triangles) for frame in frames]
        assert actual == expected
        assert all(actual[:-1]) and actual[-1] is False


# Exercise exact vertical/radial bounds, degeneracies, clipping and nonfinite vertices.
def check_boundaries():
    triangles = np.array([[0, 1, 2]])
    witness = check.StoolSupportWitness(triangles, 3)
    heights = (check.seats.BENCH_TOP - check.MAX_REST_GAP,
               check.seats.BENCH_TOP + check.MAX_REST_GAP)
    with np.errstate(invalid='ignore'):
        for boundary in heights:
            for height in (np.nextafter(boundary, -np.inf), boundary, np.nextafter(boundary, np.inf)):
                for radius in (np.nextafter(0.16, 0.0), 0.16, np.nextafter(0.16, np.inf)):
                    for points in (np.array([[radius, 0.0, height]] * 3),
                                   np.array([[-0.2, -0.2, height], [0.2, -0.2, height], [0.0, 0.2, height]]),
                                   np.array([[radius, 0.0, height - 0.1], [radius, 0.0, height + 0.1],
                                             [radius, 0.1, height]])):
                        assert witness(points) == check.has_stool_surface_support(points, triangles)
        for invalid in (np.nan, np.inf, -np.inf):
            points = np.array([[0.0, 0.0, check.seats.BENCH_TOP]] * 3)
            points[2, 0] = invalid
            assert witness(points) == check.has_stool_surface_support(points, triangles)


# Reject invalid unused indices before accepting a good witness; retain negative-index semantics.
def check_indices():
    points = np.array([[0.0, 0.0, check.seats.BENCH_TOP]] * 3)
    for invalid in (3, -4):
        triangles = np.array([[0, 1, 2], [0, 1, invalid]])
        for operation in (lambda: check.has_stool_surface_support(points, triangles),
                          lambda: check.StoolSupportWitness(triangles, 3)):
            try:
                operation()
            except IndexError:
                pass
            else:
                raise AssertionError('unused invalid triangle was accepted')
    triangles = np.array([[-3, -2, -1]])
    witness = check.StoolSupportWitness(triangles, 3)
    assert witness(points) == check.has_stool_surface_support(points, triangles)
    try:
        witness(points[:2])
    except IndexError:
        pass
    else:
        raise AssertionError('changed vertex count bypassed index validation')
    empty = np.empty((0, 3), dtype=int)
    assert check.StoolSupportWitness(empty, 3)(points) is False


# Cover many changing geometric candidates with a deterministic seed and unchanged reference predicate.
def check_generated():
    rng = np.random.default_rng(901)
    triangles = np.arange(90).reshape(30, 3)
    witness = check.StoolSupportWitness(triangles, 90)
    for _ in range(385):
        points = rng.uniform(-0.4, 0.4, (90, 3))
        points[:, 2] += check.seats.BENCH_TOP
        assert witness(points) == check.has_stool_surface_support(points, triangles)


# A cached valid triangle must not hide invalid scalar types in another triangle.
def check_malformed_points():
    points = np.array([[0.0, 0.0, check.seats.BENCH_TOP]] * 6)
    triangles = np.arange(6).reshape(2, 3)
    witness = check.StoolSupportWitness(triangles, 6)
    assert witness(points)
    assert witness(points)
    malformed = points.astype(object)
    malformed[5, 0] = 'invalid coordinate'
    try:
        check.has_stool_surface_support(malformed, triangles)
    except (TypeError, ValueError) as error:
        expected = type(error)
    else:
        raise AssertionError('reference did not reject malformed geometry')
    try:
        witness(malformed)
    except expected:
        pass
    else:
        raise AssertionError('cached witness concealed malformed geometry')


# Chunk boundaries, nonfinite values and late penetrations retain exact reference depth results.
def check_bench_chunks():
    rng = np.random.default_rng(385)
    saved = dict(check.seats.SCENE)
    try:
        for whole in (False, True):
            check.seats.SCENE['whole_bench'] = whole
            for count in (1, 15, 16, 17, 385):
                points = rng.uniform(-2.0, 2.0, (count, 19, 3))
                assert check.bench_clip_depth(points) == check.seats.level_depth(points)
                assert check.seats.SCENE['size'] == saved['size']
            for value in (np.nan, np.inf, -np.inf):
                for axis in range(3):
                    for frame in (0, -1):
                        points = rng.uniform(-2.0, 2.0, (17, 19, 3))
                        points[frame, -1, axis] = value
                        with np.errstate(invalid='ignore'):
                            assert check.bench_clip_depth(points) == check.seats.level_depth(points)
            points = np.full((385, 1, 3), 10.0)
            points[-1, 0] = [0.0, check.seats.TABLE_FAR_EDGE + 0.01,
                             (check.seats.TABLE_TOP + check.seats.TABLE_UNDERSIDE) / 2]
            assert check.bench_clip_depth(points) == check.seats.level_depth(points)
            assert check.bench_clip_depth(points) > check.MAX_TABLE_DEPTH
            for shape in ((0, 19, 3), (17, 0, 3)):
                for operation in (check.seats.level_depth, check.bench_clip_depth):
                    check.seats.SCENE['size'] = saved['size']
                    try:
                        operation(np.empty(shape))
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('empty geometry did not fail')
                    if operation is check.bench_clip_depth:
                        assert check.seats.SCENE['size'] == saved['size']
    finally:
        check.seats.SCENE.update(saved)


# Run only focused geometric equivalence checks without converters or game processes.
def main():
    check_sequence()
    check_boundaries()
    check_indices()
    check_generated()
    check_malformed_points()
    check_bench_chunks()
    print('tavern seat runtime equivalence ok')


if __name__ == '__main__':
    main()
