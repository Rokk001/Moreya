"""Every piece of tavern furniture stands with its whole footprint on tiles of its own room (INGAME-QS-11 K9).

Coordinator finding on Mario's screenshot ODscreenshot_2026-11-18_165308_9: a table and a stool seemed to reach over
the room edge onto the earth beside it. This check lays out tavern rooms of several shapes the way
RoomTavern::updateActiveSpots does (counter on the first tile, kegs at walls, two-tile tables with their benches, a
stool at each end of a table) and asserts for every counter, keg, table with its benches and stool that its footprint
lies on tiles of that room. The footprints are the vertex bounds of the shipped meshes (OgreXMLConverter converts
them), scaled and turned as the game places them (the table scale of RoomTavern.cpp, the counter scale of
RoomObjectPath::furnitureScale); the placement constants are read from RoomTavern.cpp. Before this change the counter
(1.04 tiles wide) reached 0.02 tiles off its tile in every room.

Rooms: 3 x 3, 4 x 3, 2 x 4 and 2 x 6 (two tiles wide), 3 x 5, 5 x 5, an L, a U, a room with a pillar inside and a room
that is open to claimed floor on one side. Fixed expected values of this branch (counted once): the number of tables
of each room (TABLES below) and the number of rooms (10).

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_tavern_furniture_in_room.py
"""
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ROOM_CPP = (ROOT / 'source' / 'rooms' / 'RoomTavern.cpp').read_text(encoding='utf-8', errors='replace')
# A footprint may touch the edge of its tiles (the table with its benches is exactly one tile wide)
EDGE_TOLERANCE = 1e-3
# Points along the outline and inside a footprint that must lie on room tiles, in tiles
SAMPLE_STEP = 0.02

# Rooms as text: R = tile of the room, # = wall (full tile), . = claimed floor that is not part of the room.
# Row 0 is the top (largest y), as on the screen; x grows to the right.
ROOMS = {
    '3x3': ['#####', '#RRR#', '#RRR#', '#RRR#', '#####'],
    '4x3': ['######', '#RRRR#', '#RRRR#', '#RRRR#', '######'],
    '2x4': ['####', '#RR#', '#RR#', '#RR#', '#RR#', '####'],
    '2x6': ['####', '#RR#', '#RR#', '#RR#', '#RR#', '#RR#', '#RR#', '####'],
    '3x5': ['#####', '#RRR#', '#RRR#', '#RRR#', '#RRR#', '#RRR#', '#####'],
    '5x5': ['#######', '#RRRRR#', '#RRRRR#', '#RRRRR#', '#RRRRR#', '#RRRRR#', '#######'],
    'L': ['######', '#RR###', '#RR###', '#RRRR#', '#RRRR#', '######'],
    'U': ['#######', '#RR#RR#', '#RR#RR#', '#RRRRR#', '#RRRRR#', '#######'],
    'pillar': ['######', '#RRRR#', '#R#RR#', '#RRRR#', '#RRRR#', '######'],
    'open': ['#....#', '#RRRR#', '#RRRR#', '#RRRR#', '######'],
}
# Tables each room gets (fixed, counted once on this branch)
TABLES = {'3x3': 1, '4x3': 1, '2x4': 1, '2x6': 1, '3x5': 1, '5x5': 3, 'L': 1, 'U': 2, 'pillar': 1, 'open': 1}


def constant(name):
    """A float constant of RoomTavern.cpp."""
    match = re.search(r'const (?:float|double|size_t) ' + name + r' = ([0-9.]+)f?;', ROOM_CPP)
    assert match, name + ' missing in RoomTavern.cpp'
    return float(match.group(1))


TABLE_SCALE = constant('TAVERN_TABLE_SCALE')
STOOL_DISTANCE = constant('TAVERN_STOOL_DISTANCE')
TILES_PER_KEG = int(constant('TAVERN_TILES_PER_KEG'))
TILES_PER_TABLE = int(constant('TAVERN_TILES_PER_TABLE'))
assert 'const double TABLE_ANGLES[] = { 0.0, 90.0 };' in ROOM_CPP, 'tables are tried long along y, then along x'
BOUNDS_H = (ROOT / 'source' / 'gamemap' / 'RoomObjectBounds.h').read_text(encoding='utf-8', errors='replace')


def placed_scale(name, bounds):
    """The (x, y) scale RoomObjectPath::furnitureScale gives a mesh that has its own rule there, else (1, 1)."""
    match = re.search(r'if\(name == "' + name + r'"\)\s*return \{([^;]*)\};', BOUNDS_H)
    if not match:
        return 1.0, 1.0
    min_x, min_y, max_x, max_y = bounds
    values = {'bounds.minX': min_x, 'bounds.minY': min_y, 'bounds.maxX': max_x, 'bounds.maxY': max_y}
    parts = []
    for part in match.group(1).split(','):
        text = part
        for key, value in values.items():
            text = text.replace(key, repr(value))
        parts.append(float(eval(re.sub(r'(\d)f\b', r'\1', text), {'__builtins__': {}})))
    return parts[0], parts[1]


def mesh_bounds(name, work):
    """(min x, min y, max x, max y) of the vertices of a shipped mesh."""
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    source = Path(work) / (name + '.mesh')
    source.write_bytes((ROOT / 'models' / (name + '.mesh')).read_bytes())
    target = Path(work) / (name + '.mesh.xml')
    subprocess.run([converter, '-q', str(source), str(target)], check=True, capture_output=True)
    xs, ys = [], []
    for position in ET.parse(str(target)).getroot().iter('position'):
        xs.append(float(position.get('x')))
        ys.append(float(position.get('y')))
    return min(xs), min(ys), max(xs), max(ys)


def parse(rows):
    """Room tiles and wall tiles of a room drawn as text."""
    room, walls = [], set()
    height = len(rows)
    for r, row in enumerate(rows):
        for x, c in enumerate(row):
            y = height - 1 - r
            if c == 'R':
                room.append((x, y))
            elif c == '#':
                walls.add((x, y))
    return room, walls


def rotate(px, py, angle):
    """Turns a point by angle degrees like Ogre's roll and RoomTavern's seatOffset."""
    a = math.radians(angle)
    return px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)


def table_step(angle):
    """tableStep of RoomTavern.cpp."""
    a = math.radians(angle)
    return int(math.floor(-math.sin(a) + 0.5)), int(math.floor(math.cos(a) + 0.5))


def back_to_wall(tile, room):
    """RoomTavern::getBackToWallAngle: the first side (top, bottom, left, right) whose neighbour is not of the room."""
    x, y = tile
    for (dx, dy), angle in (((0, 1), 0.0), ((0, -1), 180.0), ((-1, 0), 90.0), ((1, 0), 270.0)):
        if (x + dx, y + dy) not in room:
            return angle
    return 0.0


def bench_behind_wall(tile, angle, bench, walls):
    """isBenchBehindWall of RoomTavern.cpp (a wall or the map edge behind the bench)."""
    a = math.radians(angle)
    side = 1 if bench == 0 else -1
    dx = side * int(math.floor(math.cos(a) + 0.5))
    dy = side * int(math.floor(math.sin(a) + 0.5))
    sx, sy = table_step(angle)
    for px, py in (tile, (tile[0] + sx, tile[1] + sy)):
        if (px + dx, py + dy) in walls:
            return True
    return False


def bench_sides_free(tile, second, room, furniture):
    """areBenchSidesFree of RoomTavern.cpp."""
    ax, ay = second[1] - tile[1], tile[0] - second[0]
    for px, py in (tile, second):
        for side in (-1, 1):
            n = (px + side * ax, py + side * ay)
            if n not in room or n in furniture:
                return False
    return True


def layout(room_tiles, walls, counter_scale):
    """The furniture RoomTavern::updateActiveSpots places for a new room: [(mesh, x, y, angle, scale)]."""
    ordered = sorted(room_tiles)
    room = set(ordered)
    counter = ordered[0]
    wanted = {counter: ('TavernCounter', back_to_wall(counter, room))}
    furniture = [counter]
    pieces = []
    for kind, limit in ((0, len(ordered) // TILES_PER_KEG), (1, len(ordered) // TILES_PER_TABLE)):
        for _ in range(limit):
            best = None
            best_distance = -1
            best_free = False
            for tile in ordered:
                if tile in furniture:
                    continue
                x, y = tile
                for angle_index in range(1 if kind == 0 else 2):
                    second = None
                    free = False
                    if kind == 0:
                        angle = None
                        adjacent_keg = False
                        for (dx, dy), a in (((0, 1), 0.0), ((0, -1), 180.0), ((-1, 0), 90.0), ((1, 0), 270.0)):
                            n = (x + dx, y + dy)
                            if n in walls and angle is None:
                                angle = a
                            if wanted.get(n, ('',))[0] == 'TavernKeg':
                                adjacent_keg = True
                        if angle is None or adjacent_keg:
                            continue
                    else:
                        angle = (0.0, 90.0)[angle_index]
                        sx, sy = table_step(angle)
                        second = (x + sx, y + sy)
                        if second not in room or second in furniture:
                            continue
                        if bench_behind_wall(tile, angle, 0, walls) and bench_behind_wall(tile, angle, 1, walls):
                            continue
                        free = bench_sides_free(tile, second, room, furniture)
                    distance = min(min((x - fx) ** 2 + (y - fy) ** 2 for fx, fy in furniture),
                                   min((second[0] - fx) ** 2 + (second[1] - fy) ** 2 for fx, fy in furniture) if second else 1 << 30)
                    if (free and not best_free) or (free == best_free and distance > best_distance):
                        best, best_distance, best_free = (tile, second, angle), distance, free
            if best is None:
                break
            tile, second, angle = best
            wanted[tile] = ('TavernKeg' if kind == 0 else 'TavernTable', angle)
            furniture.append(tile)
            if second:
                furniture.append(second)
    for tile, (mesh, angle) in wanted.items():
        if mesh == 'TavernTable':
            sx, sy = table_step(angle)
            mx, my = tile[0] + 0.5 * sx, tile[1] + 0.5 * sy
            pieces.append(('TavernTable', mx, my, angle, (TABLE_SCALE, TABLE_SCALE)))
            for end in (STOOL_DISTANCE, -STOOL_DISTANCE):
                ox, oy = rotate(0.0, end, angle)
                pieces.append(('TavernStool', mx + ox, my + oy, angle, (1.0, 1.0)))
        else:
            pieces.append((mesh, float(tile[0]), float(tile[1]), angle, counter_scale if mesh == 'TavernCounter' else (1.0, 1.0)))
    return pieces


def footprint_points(bounds, x, y, angle, scale):
    """Points along the outline and inside a footprint, in map coordinates."""
    x0, x1 = bounds[0] * scale[0], bounds[2] * scale[0]
    y0, y1 = bounds[1] * scale[1], bounds[3] * scale[1]
    points = []
    nx = max(2, int((x1 - x0) / SAMPLE_STEP) + 1)
    ny = max(2, int((y1 - y0) / SAMPLE_STEP) + 1)
    for i in range(nx):
        for j in range(ny):
            px = x0 + (x1 - x0) * i / (nx - 1)
            py = y0 + (y1 - y0) * j / (ny - 1)
            rx, ry = rotate(px, py, angle)
            points.append((x + rx, y + ry))
    return points


def on_room(point, room):
    """True when the point lies on a tile of the room (a tile spans +-0.5 around its centre)."""
    px, py = point
    for tx in {math.floor(px + 0.5 - EDGE_TOLERANCE), math.floor(px + 0.5 + EDGE_TOLERANCE)}:
        for ty in {math.floor(py + 0.5 - EDGE_TOLERANCE), math.floor(py + 0.5 + EDGE_TOLERANCE)}:
            if (tx, ty) in room:
                return True
    return False


def main():
    """Lays out every room and checks every footprint; prints one line per room."""
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='tavern_room_fit_') as work:
        bounds = {name: mesh_bounds(name, work) for name in ('TavernCounter', 'TavernKeg', 'TavernTable', 'TavernStool')}
    setup = time.monotonic() - start
    failures = []
    assert len(ROOMS) == 10 and set(ROOMS) == set(TABLES), 'ten rooms with a fixed table count each'
    for name, rows in ROOMS.items():
        room_tiles, walls = parse(rows)
        room = set(room_tiles)
        pieces = layout(room_tiles, walls, placed_scale('TavernCounter', bounds['TavernCounter']))
        tables = sum(1 for p in pieces if p[0] == 'TavernTable')
        if tables != TABLES[name]:
            failures.append('%s: %d tables, expected %d' % (name, tables, TABLES[name]))
        for mesh, x, y, angle, scale in pieces:
            outside = [p for p in footprint_points(bounds[mesh], x, y, angle, scale) if not on_room(p, room)]
            if outside:
                failures.append('%s: %s at (%.2f, %.2f) angle %.0f reaches off the room at (%.2f, %.2f)' % (
                    name, mesh, x, y, angle, outside[0][0], outside[0][1]))
        print('%-7s %2d tiles: %d tables, %d stools, %d kegs, counter; all footprints on room tiles%s' % (
            name, len(room_tiles), tables, sum(1 for p in pieces if p[0] == 'TavernStool'),
            sum(1 for p in pieces if p[0] == 'TavernKeg'), '' if not failures else ' (see failures)'))
    print('ODP_TEST_PHASE {"name":"setup","seconds":%.2f}' % setup)
    print('ODP_TEST_PHASE {"name":"test","seconds":%.2f}' % (time.monotonic() - start - setup))
    if failures:
        print('\n'.join(failures))
        sys.exit(1)
    print('tavern furniture in room ok')


if __name__ == '__main__':
    main()
