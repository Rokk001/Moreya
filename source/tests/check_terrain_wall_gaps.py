"""No open gaps between neighbouring rock wall tiles.

Two wall tiles of one block share a border on which both are linked. Their top edges there must not differ in height (a
tile dropping where an unlinked side of its own meets that border leaves a hole next to a neighbour at full height); any
difference must at least be closed by vertical faces (skirts) in the border plane, else the empty space shows through as a black
wedge. The check reads the real mesh files of the dirt wall tile set, turns them as the tile set says and tries every
pair of tiles that can meet, in both directions. No compilation and no game start.

Usage: python source/tests/check_terrain_wall_gaps.py
"""
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: Places (a pair of tiles and a point on their shared border) where the two top edges differ in height, counted once
#: from the committed earth meshes and tile set; every one of them must be closed. None since the walls are boxes whose
#: linked borders are at full height everywhere (3360 with the former sloped walls); a profile that drops towards a linked
#: border again shows here
DIFFERING_PLACES = 0
#: Tolerance for a point lying in the border plane and for equal heights
PLANE = 1e-4
LEVEL = 2e-3
#: Sample points along a shared border (the ends just inside the tile corners)
SAMPLES = [-0.499] + [-0.48 + 0.04 * i for i in range(25)] + [0.499]


def triangles(path):
    """Triangles (three positions each) of every submesh of an OGRE mesh file."""
    data = path.read_bytes()

    def chunks(start, end):
        while start < end:
            kind, size = struct.unpack_from('<HI', data, start)
            assert size >= 6
            yield kind, start + 6, min(start + size, end)
            start += size

    def geometry(start, end):
        count, = struct.unpack_from('<I', data, start)
        position = None
        buffers = {}
        for kind, body, stop in chunks(start + 4, end):
            if kind == 0x5100:
                for entry, element, _ in chunks(body, stop):
                    source, value_type, semantic, offset, _ = struct.unpack_from('<5H', data, element)
                    if semantic == 1:
                        assert entry == 0x5110 and value_type == 2
                        position = source, offset
            elif kind == 0x5200:
                binding, stride = struct.unpack_from('<HH', data, body)
                raw = list(chunks(body + 4, stop))[0][1]
                buffers[binding] = raw, stride
        raw, stride = buffers[position[0]]
        return [struct.unpack_from('<3f', data, raw + index * stride + position[1]) for index in range(count)]

    result = []
    shared_points = None
    for kind, body, end in chunks(data.index(b'\n') + 1, len(data)):
        assert kind == 0x3000
        for child, start, stop in chunks(body + 1, end):
            if child == 0x5000:
                shared_points = geometry(start, stop)
            elif child == 0x4000:
                cursor = data.index(b'\n', start) + 1
                shared, count, wide = struct.unpack_from('<?I?', data, cursor)
                cursor += 6
                indices = struct.unpack_from('<%d%s' % (count, 'I' if wide else 'H'), data, cursor)
                cursor += count * (4 if wide else 2)
                points = shared_points
                if not shared:
                    for sub, local, limit in chunks(cursor, stop):
                        if sub == 0x5000:
                            points = geometry(local, limit)
                result += [tuple(points[i] for i in indices[k:k + 3]) for k in range(0, count, 3)]
    assert result, path
    return result


def tile_entries(tileset):
    """(side mask, mesh name, turn about z in degrees) of every entry of the dirt wall tile set, oneOf blocks included."""
    section = tileset.split('[dirtFull]', 1)[1].split('[/dirtFull]', 1)[0]
    mask = None
    result = []
    for line in section.splitlines():
        fields = line.split()
        if not fields:
            continue
        if re.fullmatch('[01]{4}', fields[0]):
            mask = int(fields.pop(0), 2)
        if fields and fields[0].endswith('.mesh'):
            result.append((mask, fields[0], float(fields[4])))
    assert result
    return sorted(set(result))


def side_view(mesh, degrees, axis, side):
    """What a turned tile shows in the border plane axis = side: its top edge segments and its vertical faces, as (t, z)."""
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    top, faces = [], []
    for triangle in mesh:
        turned = [(x * c - y * s, x * s + y * c, z) for x, y, z in triangle]
        on = [(p[1 - axis], p[2]) for p in turned if abs(p[axis] - side) < PLANE]
        if len(on) == 3:
            faces.append(on)
        elif len(on) == 2:
            top.append(on)
    return top, faces


def edge_height(segments, t):
    """Height of the top edge at the point t of the border (the floor where no segment reaches)."""
    height = 0.0
    for (t0, z0), (t1, z1) in segments:
        low, high = min(t0, t1), max(t0, t1)
        if low - PLANE <= t <= high + PLANE and high - low > PLANE:
            height = max(height, z0 + (z1 - z0) * (t - t0) / (t1 - t0))
    return height


def covered(faces, t, z):
    """True when a vertical face of the border plane covers the point (t, z)."""
    for (a, b, c) in faces:
        area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(area) < 1e-12:
            continue
        w1 = ((t - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (z - a[1])) / area
        w2 = ((b[0] - a[0]) * (z - a[1]) - (t - a[0]) * (b[1] - a[1])) / area
        if w1 >= -1e-3 and w2 >= -1e-3 and w1 + w2 <= 1 + 1e-3:
            return True
    return False


def main():
    """Try every pair of tiles that can meet; every height difference on the shared border must be closed."""
    tileset = content_packages.read_text(ROOT, 'config/tilesets.cfg')
    entries = tile_entries(tileset)
    meshes = {name: triangles(content_packages.resolve(ROOT, 'models/' + name)) for _, name, _ in entries}
    # bits of the mask: 0 = linked south (y = -0.5), 1 = east (x = +0.5), 2 = north (y = +0.5), 3 = west (x = -0.5)
    differing = 0
    gaps = []
    for axis, first_bit, first_side, second_bit, second_side in ((0, 1, 0.5, 3, -0.5), (1, 2, 0.5, 0, -0.5)):
        firsts = [(e, side_view(meshes[e[1]], e[2], axis, first_side)) for e in entries if e[0] & (1 << first_bit)]
        seconds = [(e, side_view(meshes[e[1]], e[2], axis, second_side)) for e in entries if e[0] & (1 << second_bit)]
        assert firsts and seconds
        for first, (first_top, first_faces) in firsts:
            for second, (second_top, second_faces) in seconds:
                for t in SAMPLES:
                    a, b = edge_height(first_top, t), edge_height(second_top, t)
                    if abs(a - b) <= LEVEL:
                        continue
                    differing += 1
                    low, high = min(a, b), max(a, b)
                    faces = first_faces + second_faces
                    for z in (low + 0.001, (low + high) / 2, high - 0.001):
                        if not covered(faces, t, z):
                            gaps.append((first[1], first[2], second[1], second[2], axis, round(t, 3), round(low, 3),
                                         round(high, 3)))
                            break
    assert not gaps, '%d open places between neighbouring wall tiles, for example %s' % (len(gaps), gaps[:3])
    assert differing == DIFFERING_PLACES, 'places with differing edge heights: %d, expected %d' % (differing, DIFFERING_PLACES)
    print('check_terrain_wall_gaps ok: %d entries, %d places with differing edge heights, all closed'
          % (len(entries), differing))


if __name__ == '__main__':
    main()
