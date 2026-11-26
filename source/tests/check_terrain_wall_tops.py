"""Level tops of the earth and rock wall tiles: no spikes, gables or notches.

Every tile of the earth, rock, gold and gem walls (turned as the tile set says, oneOf variants included) must end flat at
the wall height: no vertex above it, the top edge on all four borders straight and exactly at the wall height up to the
corners, and no place of the tile surface lower than the shallow dips of the top. The claimed walls are not covered:
their battlement stones stand above the wall top on purpose. The check reads the real mesh files; no compilation and no
game start.

Usage: python source/tests/check_terrain_wall_tops.py
"""
import math
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


def wall_entries(tileset):
    """(section, side mask, mesh name, turn) of every entry of the four wall kinds that share the earth meshes."""
    result = []
    for section in ('dirtFull', 'rockFull', 'goldFull', 'gemFull'):
        body = tileset.split('[%s]' % section, 1)[1].split('[/%s]' % section, 1)[0]
        result += [(section,) + entry for entry in walls.tile_entries('[dirtFull]%s[/dirtFull]' % body)]
    return result


def main():
    """Every wall tile ends flat at the wall height, on its borders and across its whole surface."""
    tileset = walls.content_packages.read_text(walls.ROOT, 'config/tilesets.cfg')
    entries = wall_entries(tileset)
    meshes = {}
    seen = set()
    bad = []
    for section, mask, name, degrees in entries:
        if name not in meshes:
            meshes[name] = walls.triangles(walls.content_packages.resolve(walls.ROOT, 'models/' + name))
        if (name, degrees) in seen:
            continue
        seen.add((name, degrees))
        mesh = turned(meshes[name], degrees)
        top = max(p[2] for triangle in mesh for p in triangle)
        if top > WALL_TOP + HEIGHT:
            bad.append((section, name, degrees, 'vertex above the wall', round(top, 4)))
        for axis, side in ((1, -0.5), (0, 0.5), (1, 0.5), (0, -0.5)):
            segments, _ = walls.side_view(meshes[name], degrees, axis, side)
            for t in walls.SAMPLES:
                height = walls.edge_height(segments, t)
                if abs(height - WALL_TOP) > HEIGHT:
                    bad.append((section, name, degrees, 'top edge', axis, side, round(t, 3), round(height, 4)))
                    break
        upper = [triangle for triangle in mesh if max(p[2] for p in triangle) > WALL_TOP - TOP_DIP - HEIGHT]
        for x in GRID:
            low = [(y, highest(upper, x, y)) for y in GRID]
            low = [(y, z) for y, z in low if z < WALL_TOP - TOP_DIP - HEIGHT]
            if low:
                bad.append((section, name, degrees, 'notch', round(x, 3), round(low[0][0], 3), round(low[0][1], 4)))
                break
    assert not bad, '%d wall tile tops are not flat, for example %s' % (len(bad), bad[:3])
    assert len(entries) == ENTRIES, 'wall tile set entries: %d, expected %d' % (len(entries), ENTRIES)
    print('check_terrain_wall_tops ok: %d entries, %d turned meshes, all tops flat' % (len(entries), len(seen)))


if __name__ == '__main__':
    main()
