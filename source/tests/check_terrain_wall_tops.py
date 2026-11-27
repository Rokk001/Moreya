"""Level tops of the earth and rock wall tiles: no spikes, gables or notches.

Every tile of the earth, rock, gold and gem walls (turned as the tile set says, oneOf variants included) must end flat at
the wall height: no vertex above it, the top edge on all four borders straight and exactly at the wall height up to the
corners, and no place of the tile surface lower than the shallow dips of the top. At an outer corner (a tile corner
between two unlinked sides) the vertical edge is a quarter circle of a fixed radius with normals pointing out from its
axis, the tile ends there and only the floor lies beyond it; corners with a linked side stay sharp. The claimed walls
are not covered:
their battlement stones stand above the wall top on purpose. The check reads the real mesh files; no compilation and no
game start.

Usage: python source/tests/check_terrain_wall_tops.py
"""
import math
import struct
import sys

import check_terrain_wall_gaps as walls

#: Height of the top of a wall tile
WALL_TOP = 1.415
#: Deepest allowed dip of the top surface below the wall height (the soft dips away from the borders)
TOP_DIP = 0.0105
#: Tolerance for vertex heights stored as floats
HEIGHT = 1e-4
#: Tile set entries of the four wall kinds (oneOf variants included), counted once from the committed tile set
ENTRIES = 75
#: Radius of the rounded outer corners in tile widths
RADIUS = 0.07
#: Rounded outer corners over all tile set entries of the four wall kinds, counted once from the committed tile set
ROUNDED_CORNERS = 64
#: Tile corners as (x sign, y sign, the two mask bits of the sides that meet there); bit 0 south, 1 east, 2 north, 3 west
CORNERS = ((1, -1, 0, 1), (1, 1, 1, 2), (-1, 1, 2, 3), (-1, -1, 3, 0))
#: Sample positions across a tile in x and y (the ends just inside the tile corners)
GRID = [-0.499] + [-0.475 + 0.05 * i for i in range(20)] + [0.499]


def turned(mesh, degrees):
    """The triangles of a mesh turned about z by the given angle."""
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return [[(x * c - y * s, x * s + y * c, z) for x, y, z in triangle] for triangle in mesh]


def highest(triangles, x, y):
    """Height of the highest surface of the triangles above the point (x, y), 0.0 where there is none."""
    height = 0.0
    for a, b, c in triangles:
        area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(area) < 1e-9:
            continue
        w1 = ((x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (y - a[1])) / area
        w2 = ((b[0] - a[0]) * (y - a[1]) - (x - a[0]) * (b[1] - a[1])) / area
        if w1 >= -1e-5 and w2 >= -1e-5 and w1 + w2 <= 1 + 1e-5:
            height = max(height, a[2] + w1 * (b[2] - a[2]) + w2 * (c[2] - a[2]))
    return height


def beyond_corner(x, y, corners, margin):
    """True where (x, y) lies outside the rounded edge of one of the corners by more than the margin."""
    centre = 0.5 - RADIUS
    for sx, sy in corners:
        dx, dy = sx * x - centre, sy * y - centre
        if dx > 0 and dy > 0 and math.hypot(dx, dy) > RADIUS + margin:
            return True
    return False


def vertex_normals(path):
    """(position, normal) of every vertex of an OGRE mesh file."""
    data = path.read_bytes()
    result = []

    def chunks(start, end):
        while start < end:
            kind, size = struct.unpack_from('<HI', data, start)
            assert size >= 6
            yield kind, start + 6, min(start + size, end)
            start += size

    def geometry(start, end):
        count, = struct.unpack_from('<I', data, start)
        elements, buffers = {}, {}
        for kind, body, stop in chunks(start + 4, end):
            if kind == 0x5100:
                for _, element, _ in chunks(body, stop):
                    source, _, semantic, offset, _ = struct.unpack_from('<5H', data, element)
                    elements.setdefault(semantic, (source, offset))
            elif kind == 0x5200:
                binding, stride = struct.unpack_from('<HH', data, body)
                buffers[binding] = list(chunks(body + 4, stop))[0][1], stride
        for index in range(count):
            values = []
            for semantic in (1, 4):
                source, offset = elements[semantic]
                raw, stride = buffers[source]
                values.append(struct.unpack_from('<3f', data, raw + index * stride + offset))
            result.append(tuple(values))

    for kind, body, end in chunks(data.index(b'\n') + 1, len(data)):
        assert kind == 0x3000
        for child, start, stop in chunks(body + 1, end):
            if child == 0x5000:
                geometry(start, stop)
            elif child == 0x4000:
                cursor = data.index(b'\n', start) + 1
                _, count, wide = struct.unpack_from('<?I?', data, cursor)
                cursor += 6 + count * (4 if wide else 2)
                for sub_kind, local, limit in chunks(cursor, stop):
                    if sub_kind == 0x5000:
                        geometry(local, limit)
    return result


def edge_normals_wrong(vertices, degrees, corners):
    """Number of faults of the normals on the rounded edges: a vertex of an edge face whose normal does not point out from
    the axis of the edge, or a corner without such vertices."""
    centre = 0.5 - RADIUS
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    found = dict((corner, 0) for corner in corners)
    wrong = 0
    for position, normal in vertices:
        x, y = position[0] * c - position[1] * s, position[0] * s + position[1] * c
        nx, ny = normal[0] * c - normal[1] * s, normal[0] * s + normal[1] * c
        for sx, sy in corners:
            dx, dy = x - sx * centre, y - sy * centre
            if sx * dx > 0.01 and sy * dy > 0.01 and abs(math.hypot(dx, dy) - RADIUS) < HEIGHT and abs(normal[2]) < 0.5:
                found[sx, sy] += 1
                length = math.hypot(dx, dy)
                if abs(nx - dx / length) > 1e-3 or abs(ny - dy / length) > 1e-3:
                    wrong += 1
    return wrong + sum(1 for count in found.values() if count == 0)


def wall_entries(tileset):
    """(section, side mask, mesh name, turn) of every entry of the four wall kinds that share the earth meshes."""
    result = []
    for section in ('dirtFull', 'rockFull', 'goldFull', 'gemFull'):
        body = tileset.split('[%s]' % section, 1)[1].split('[/%s]' % section, 1)[0]
        result += [(section,) + entry for entry in walls.tile_entries('[dirtFull]%s[/dirtFull]' % body)]
    return result


def main():
    """Every wall tile ends flat at the wall height, on its borders and across its whole surface."""
    if not walls.content_packages.has_content(walls.ROOT):
        walls.content_packages.unchecked('check_terrain_wall_tops', ['config/tilesets.cfg wall rows and the wall tile meshes'])
        return
    tileset = walls.content_packages.read_text(walls.ROOT, 'config/tilesets.cfg')
    entries = wall_entries(tileset)
    meshes = {}
    seen = set()
    bad = []
    normals = {}
    rounded = 0
    for section, mask, name, degrees in entries:
        if name not in meshes:
            meshes[name] = walls.triangles(walls.content_packages.resolve(walls.ROOT, 'models/' + name))
        corners = [(sx, sy) for sx, sy, a, b in CORNERS if not mask & (1 << a) and not mask & (1 << b)]
        rounded += len(corners)
        if (name, degrees) in seen:
            continue
        seen.add((name, degrees))
        mesh = turned(meshes[name], degrees)
        if corners:
            if name not in normals:
                normals[name] = vertex_normals(walls.content_packages.resolve(walls.ROOT, 'models/' + name))
            if edge_normals_wrong(normals[name], degrees, corners):
                bad.append((section, name, degrees, 'rounded edge normals'))
        top = max(p[2] for triangle in mesh for p in triangle)
        if top > WALL_TOP + HEIGHT:
            bad.append((section, name, degrees, 'vertex above the wall', round(top, 4)))
        for axis, side in ((1, -0.5), (0, 0.5), (1, 0.5), (0, -0.5)):
            segments, _ = walls.side_view(meshes[name], degrees, axis, side)
            for t in walls.SAMPLES:
                x, y = (side, t) if axis == 0 else (t, side)
                if any(sx * x > 0.5 - RADIUS and sy * y > 0.5 - RADIUS for sx, sy in corners):
                    continue
                height = walls.edge_height(segments, t)
                if abs(height - WALL_TOP) > HEIGHT:
                    bad.append((section, name, degrees, 'top edge', axis, side, round(t, 3), round(height, 4)))
                    break
        upper = [triangle for triangle in mesh if max(p[2] for p in triangle) > WALL_TOP - TOP_DIP - HEIGHT]
        for sx, sy in corners:
            centre = 0.5 - RADIUS
            for step in (1, 3, 5):
                angle = step * math.pi / 12
                for distance, wanted in ((RADIUS - 0.004, True), (RADIUS + 0.004, False)):
                    x = sx * (centre + distance * math.cos(angle))
                    y = sy * (centre + distance * math.sin(angle))
                    if (highest(upper, x, y) > WALL_TOP - TOP_DIP - HEIGHT) != wanted:
                        bad.append((section, name, degrees, 'rounded corner', sx, sy, step, wanted))
        for x in GRID:
            low = [(y, highest(upper, x, y)) for y in GRID if not beyond_corner(x, y, corners, -0.002)]
            low = [(y, z) for y, z in low if z < WALL_TOP - TOP_DIP - HEIGHT]
            if low:
                bad.append((section, name, degrees, 'notch', round(x, 3), round(low[0][0], 3), round(low[0][1], 4)))
                break
    assert not bad, '%d wall tile tops are not flat, for example %s' % (len(bad), bad[:3])
    assert len(entries) == ENTRIES, 'wall tile set entries: %d, expected %d' % (len(entries), ENTRIES)
    assert rounded == ROUNDED_CORNERS, 'rounded outer corners: %d, expected %d' % (rounded, ROUNDED_CORNERS)
    print('check_terrain_wall_tops ok: %d entries, %d turned meshes, all tops flat' % (len(entries), len(seen)))


if __name__ == '__main__':
    main()
