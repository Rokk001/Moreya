"""Toilet room after INGAME-QS-10 K25: textured stone seats with a hole and a wooden lid, solid seats in rows along the
walls with a free lane, a seated use of 10 to 30 s in the Relieve clip and the urge values of the toilet plan.

Calls (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
  python source/tests/check_toilet_k25.py               file checks and the compiled probe of the layout rules (cl)
  python source/tests/check_toilet_k25.py --no-compile  file checks only; the probe is left to the build
"""
import ast
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
START = time.monotonic()


def read(path):
    return (ROOT / path).read_text(encoding='utf-8', errors='replace')


def body(source, signature):
    """The text of a function from its signature to the closing brace at the start of a line."""
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 2]


bounds_h = read('source/gamemap/RoomObjectBounds.h')
row = re.search(r'\{"ToiletSeat", ([-.\d]+)f, ([-.\d]+)f, ([-.\d]+)f, ([-.\d]+)f\}', bounds_h)
assert row is not None, 'ToiletSeat is missing in the navigation catalog (the seats would be walked through)'
min_x, min_y, max_x, max_y = (float(v) for v in row.groups())
seat_top = float(re.search(r'constexpr float toiletSeatTop = ([.\d]+)f;', bounds_h).group(1))
place_y = float(re.search(r'constexpr float toiletSeatPlaceY = ([.\d]+)f;', bounds_h).group(1))

# 1. The shipped seat mesh: its bounds are the catalog bounds, it fits its tile with the back at the wall, the stone top is
#    at the height the user is drawn at, the hole goes down into a shaft under the place of the user, and the lid stands
#    up at the back with a real thickness.
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='toilet_k25_'))
target = work / 'ToiletSeat.mesh.xml'
subprocess.run([converter, '-q', '-log', str(target) + '.log', str(ROOT / 'models' / 'ToiletSeat.mesh'), str(target)],
               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=120, check=True)
tree = ET.parse(target).getroot()
submeshes = list(tree.iter('submesh'))
assert [s.get('material') for s in submeshes] == ['ToiletSeat'], 'the seat uses the one material ToiletSeat'


def corners(geometry):
    """Positions and texture coordinates of a geometry block (they may sit in separate vertex buffers)."""
    pos, tex = [], []
    for vb in geometry.iter('vertexbuffer'):
        for v in vb.iter('vertex'):
            p, t = v.find('position'), v.find('texcoord')
            if p is not None:
                pos.append((float(p.get('x')), float(p.get('y')), float(p.get('z'))))
            if t is not None:
                tex.append((float(t.get('u')), float(t.get('v'))))
    return pos, tex


positions, uvs, triangles = [], [], []
shared = tree.find('sharedgeometry')
if shared is not None:
    positions, uvs = corners(shared)
for sm in submeshes:
    base = 0
    own = sm.find('geometry')
    if own is not None:
        base = len(positions)
        pos, tex = corners(own)
        positions += pos
        uvs += tex
    for f in sm.iter('face'):
        triangles.append(tuple(base + int(f.get(k)) for k in ('v1', 'v2', 'v3')))
assert len(positions) == len(uvs) > 0, 'every vertex of the seat has a texture coordinate'
P = np.array(positions)
assert 400 <= len(triangles) <= 3000, 'triangles %d: detailed, but in the range of the other room furniture' % len(triangles)
lo, hi = P.min(0), P.max(0)
for got, want, name in ((lo[0], min_x, 'minX'), (lo[1], min_y, 'minY'), (hi[0], max_x, 'maxX'), (hi[1], max_y, 'maxY')):
    assert abs(got - want) <= 2e-5, 'catalog %s %.6f differs from the mesh %.6f' % (name, want, got)
assert -0.5 < lo[0] and hi[0] < 0.5 and hi[1] <= 0.5 and lo[1] >= -0.1, 'the seat stands in its tile, back at the wall (+y)'
assert abs(lo[2]) < 1e-4, 'the seat stands on the floor'
stone = P[P[:, 1] < 0.35]
assert abs(stone[:, 2].max() - seat_top) <= 0.006, 'stone top %.3f, users are drawn at %.3f' % (stone[:, 2].max(), seat_top)
# hole: an oval opening around the place of the user that goes down at least 10 cm
inside = P[(P[:, 2] < seat_top - 0.10) & (np.abs(P[:, 0]) < 0.08) & (P[:, 1] > place_y - 0.1) & (P[:, 1] < place_y + 0.12)]
assert len(inside) >= 8, 'no shaft below the hole'
hole_centre_y = inside[:, 1].mean()
assert abs(hole_centre_y - place_y) <= 0.06, 'the user sits over the hole (place %.3f, hole %.3f)' % (place_y, hole_centre_y)
top_ring = P[(np.abs(P[:, 2] - seat_top) < 0.02) & (np.abs(P[:, 0]) < 0.12) & (np.abs(P[:, 1] - hole_centre_y) < 0.12)]
assert len(top_ring) >= 16, 'the rim of the hole lies in the stone top'
# lid: standing at the back, higher than the seat, with thickness
lid = P[P[:, 2] > seat_top + 0.15]
assert len(lid) >= 16 and lid[:, 1].min() >= 0.36, 'the wooden lid stands up at the back of the seat'
assert lid[:, 1].max() - lid[:, 1].min() >= 0.03, 'the lid has a thickness and leans back'
assert hi[2] - seat_top >= 0.2, 'the lid rises at least 20 cm above the stone top'
# depth: the outline of the stone is not flat (cap slab over the base, rough blocks)
assert len(set(np.round(P[:, 2], 3))) >= 20, 'the seat has relief, not a flat box'

# 2. The texture: every face samples one part of the atlas; stone, wood, iron and hole each have surface detail, colours
#    in the dark dungeon range of the style guide and no near-white texel.
decals = (ROOT / 'tools' / 'gen_dirt_decals.py').read_text(encoding='utf-8')
regions = ast.literal_eval(re.search(r'^SEAT_REGIONS = (\{.*?\})$', decals, re.M | re.S).group(1))
image = np.asarray(Image.open(ROOT / 'materials' / 'textures' / 'ToiletSeat.png').convert('RGB')).astype(float)
assert image.shape[:2] == (512, 512), 'the seat atlas is 512 x 512'
assert image.max() <= 200, 'near-white texels in the seat texture (max %d)' % image.max()
used = {name: 0 for name in regions}
for tri in triangles:
    px = [(uvs[i][0] * 512.0, uvs[i][1] * 512.0) for i in tri]
    owner = [name for name, (x0, y0, x1, y1) in regions.items()
             if all(x0 - 0.5 <= x <= x1 + 0.5 and y0 - 0.5 <= y <= y1 + 0.5 for x, y in px)]
    assert owner, 'a face of the seat samples across atlas parts: %s' % (px,)
    used[owner[0]] += 1
assert all(used[name] > 0 for name in ('stone_top', 'stone_side', 'lid', 'iron', 'hole')), used


def region_stats(name):
    x0, y0, x1, y1 = regions[name]
    part = image[y0:y1, x0:x1].reshape(-1, 3)
    lum = part @ np.array([0.299, 0.587, 0.114])
    sat = (part.max(1) - part.min(1)) / np.maximum(part.max(1), 1.0)
    return lum.mean(), lum.std(), sat.mean()


for name, (y_lo, y_hi, sat_hi, detail) in {'stone_top': (55, 90, 0.30, 6), 'stone_side': (45, 90, 0.30, 6),
                                          'lid': (35, 65, 0.45, 5), 'iron': (35, 65, 0.30, 3)}.items():
    lum, std, sat = region_stats(name)
    assert y_lo <= lum <= y_hi and sat <= sat_hi, '%s: luminance %.1f sat %.2f outside the dark dungeon range' % (name, lum, sat)
    assert std >= detail, '%s: luminance spread %.1f, the surface is flat' % (name, std)
assert region_stats('hole')[0] <= 25, 'the hole is dark'
assert region_stats('lid')[0] < region_stats('stone_top')[0], 'dark wood against lighter stone'
material = read('materials/scripts/ToiletSeat.material')
assert re.search(r'^\s*texture ToiletSeat\.png\s*$', material, re.M) and 'tex_address_mode clamp' in material

# 3. Solid seats in the navigation and the user drawn on top of the seat
nav = read('source/gamemap/RoomObjectNavigation.cpp')
collect = body(nav, 'std::vector<RoomObjectPath::Obstacle> RoomObjectNavigation::collect(')
assert 'ToiletSeat' not in collect and 'TOILET_SEAT_MESH' not in collect, 'the seats must not be skipped as walkable'
steppable = body(bounds_h, 'inline bool isSteppableMesh(')
assert 'Toilet' not in steppable, 'nobody steps over a seat'
render = read('source/render/RenderManager.cpp')
lift = body(render, 'static float toiletSeatLift(Creature* creature)')
assert 'EntityAnimation::relieve_anim' in lift and 'RoomObjectPath::onToiletSeat(' in lift and 'toiletSeatTop' in lift
step = body(render, 'void RenderManager::updateCreatureStep(Creature* creature)')
assert 'toiletSeatLift(creature)' in step and 'std::max(lift, seatLift)' in step
assert 'if((animation == EntityAnimation::relieve_anim) || (mSteppingCreatures.count(dropCreature) != 0))' in render

# 4. The room places the seats by the layout and the use walks onto the seat, sits a random 10 to 30 s and steps off
room = read('source/rooms/RoomToilet.cpp')
spots = body(room, 'void RoomToilet::updateActiveSpots(GameMap* gameMap)')
assert 'ToiletLayout::chooseSeats(coords, wanted);' in spots and 'RoomObjectPath::TOILET_SEAT_MESH' in spots
assert 'room->getSeatStagingPoints(creature, tile).empty()' in body(room, 'Tile* RoomToilet::findFreeToiletTile(')
use = read('source/creatureaction/CreatureActionUseToilet.cpp')
squat = body(use, 'void CreatureActionUseToilet::startSquat(bool onSeat, const Ogre::Vector2& facing)')
for needle in ('"ToiletUseSecondsMin"', '"ToiletUseSecondsMax"', 'Random::Double(0.0, 1.0)', 'ToiletLayout::useTurns(',
               'ODApplication::turnsPerSecond', 'EntityAnimation::relieve_anim'):
    assert needle in squat, needle
seat_turn = body(use, 'bool CreatureActionUseToilet::handleSeat(')
assert 'startSquat(true, facing);' in seat_turn and 'mPhase = Phase::leave;' in seat_turn and 'mStagingPoint' in seat_turn
assert 'path.push_back(place);' in body(use, 'bool CreatureActionUseToilet::walkOntoSeat(RoomToilet& room)')

# 5. The urge values of the toilet plan: the threshold after about 9.5 minutes of urge growth, 4 chickens to the threshold
dirt = dict(re.findall(r'^\s+(\w+)\t([-.\d]+)\s*$', re.search(r'^\[Dirt\]$(.*?)^\[/Dirt\]$', read('config/global.cfg'),
                                                                 re.M | re.S).group(1), re.M))
tavern = dict(re.findall(r'^\s+(\w+)\t([-.\d]+)\s*$', re.search(r'^\[Tavern\]$(.*?)^\[/Tavern\]$', read('config/global.cfg'),
                                                                   re.M | re.S).group(1), re.M))
turns_per_second = float(re.search(r'double ODApplication::turnsPerSecond = ([\d.]+);', read('source/ODApplication.cpp')).group(1))
assert float(dirt['UrgePerChicken']) == 20.0 and float(tavern['UrgeFromWater']) == 15.0
assert math.ceil(float(dirt['UrgeSeek']) / float(dirt['UrgePerChicken'])) == 4
assert (float(dirt['ToiletUseSecondsMin']), float(dirt['ToiletUseSecondsMax'])) == (10.0, 30.0)
growing = 0
for block in re.findall(r'\[Creature\](.*?)\[/Creature\]', read('config/creatures.cfg'), re.S):
    fields = dict(line.split()[:2] for line in block.splitlines() if len(line.split()) >= 2 and not line.split()[0].startswith('#'))
    if 'Name' not in fields:
        continue  # the empty [Creature] [/Creature] pair of the file header
    growth = float(fields.get('UrgeGrowth/Turn', '0'))
    if float(fields['HungerGrowth/Turn']) == 0.0:
        assert growth == 0.0, fields.get('Name')
        continue
    growing += 1
    minutes = float(dirt['UrgeSeek']) / growth / turns_per_second / 60.0
    assert 9.0 <= minutes <= 10.0, '%s reaches the toilet threshold after %.1f minutes' % (fields.get('Name'), minutes)
assert growing == 30, growing

# 6. The probe: the layout and the use time compiled from the headers the game uses
PROBE = r'''
#include "rooms/ToiletLayout.h"
#include "gamemap/RoomObjectBounds.h"
#include <cstdio>
#include <vector>
static int failures = 0;
static void expect(bool ok, const char* what) { if(!ok) { ++failures; std::printf("FAIL %s\n", what); } }
static std::vector<ToiletLayout::Coord> rect(int w, int h)
{
    std::vector<ToiletLayout::Coord> tiles;
    for(int x = 0; x < w; ++x) for(int y = 0; y < h; ++y) tiles.push_back(ToiletLayout::Coord(x + 10, y + 20));
    return tiles;
}
static bool inRoom(const std::vector<ToiletLayout::Coord>& tiles, int x, int y)
{
    for(const ToiletLayout::Coord& t : tiles) if(t.first == x && t.second == y) return true;
    return false;
}
// The tile in front of a seat (away from its back) for an angle
static ToiletLayout::Coord front(const ToiletLayout::Coord& seat, double angle)
{
    const double a = angle * 0.01745329252;
    return ToiletLayout::Coord(seat.first + static_cast<int>(std::lround(std::sin(a))), seat.second - static_cast<int>(std::lround(std::cos(a))));
}
int main()
{
    std::map<ToiletLayout::Coord, double> seats;
    // Rectangular rooms from 3 x 3: seats only on edge tiles, never in the corners, the back outside the room, the tile in
    // front inside the room and free, about half as many seats as tiles
    const int sizes[][2] = { {3, 3}, {4, 4}, {5, 4}, {6, 6}, {7, 3}, {9, 8} };
    for(const int* size : sizes)
    {
        const std::vector<ToiletLayout::Coord> tiles = rect(size[0], size[1]);
        ToiletLayout::chooseSeats(tiles, seats);
        const int expected = 2 * (size[0] - 2) + 2 * (size[1] - 2);
        expect(static_cast<int>(seats.size()) == expected, "rectangle: one seat per edge tile without the corners");
        const double share = static_cast<double>(seats.size()) / tiles.size();
        expect(share >= 0.3 && share <= 0.6, "rectangle: about half as many seats as tiles");
        for(const std::pair<const ToiletLayout::Coord, double>& s : seats)
        {
            const ToiletLayout::Coord back = front(s.first, s.second + 180.0);
            const ToiletLayout::Coord ahead = front(s.first, s.second);
            expect(!inRoom(tiles, back.first, back.second), "the back of a seat is at the edge of the room");
            expect(inRoom(tiles, ahead.first, ahead.second), "a seat faces into the room");
            expect(seats.count(ahead) == 0 || size[0] < 3 || size[1] < 3, "the tile in front of a seat is part of the lane");
        }
        // every tile that is not at the edge stays free: the lane
        for(const ToiletLayout::Coord& t : tiles)
        {
            const bool edge = t.first == 10 || t.second == 20 || t.first == 10 + size[0] - 1 || t.second == 20 + size[1] - 1;
            if(!edge) expect(seats.count(t) == 0, "no seat in the middle of the room");
        }
    }
    // Narrow and tiny rooms still get seats, every second tile, each with a free tile beside it
    const int narrow[][2] = { {1, 1}, {1, 4}, {2, 2}, {5, 1} };
    for(const int* size : narrow)
    {
        const std::vector<ToiletLayout::Coord> tiles = rect(size[0], size[1]);
        ToiletLayout::chooseSeats(tiles, seats);
        expect(!seats.empty() && seats.size() <= (tiles.size() + 1) / 2, "narrow room: every second tile");
    }
    // Every seat angle: the seat stands in its tile, its user sits on it, a point in front of it is off the seat
    for(double angle : {0.0, 90.0, 180.0, 270.0})
    {
        const float a = static_cast<float>(angle) * RoomObjectPath::degreesToRadians;
        const float placeX = -std::sin(a) * RoomObjectPath::toiletSeatPlaceY, placeY = std::cos(a) * RoomObjectPath::toiletSeatPlaceY;
        expect(RoomObjectPath::onToiletSeat(5.0f + placeX, 7.0f + placeY, 5.0f, 7.0f, static_cast<float>(angle)), "the user sits on the seat");
        expect(!RoomObjectPath::onToiletSeat(5.0f + std::sin(a) * 0.45f, 7.0f - std::cos(a) * 0.45f, 5.0f, 7.0f, static_cast<float>(angle)),
            "the lane in front of the seat is not on the seat");
    }
    for(const RoomObjectPath::MeshBounds& b : RoomObjectPath::meshBounds)
    {
        if(RoomObjectPath::TOILET_SEAT_MESH != b.name) continue;
        const RoomObjectPath::FurnitureScale scale = RoomObjectPath::furnitureScale(b);
        expect(scale.x == 1.0f && scale.y == 1.0f, "the seat keeps its authored size");
        expect(!RoomObjectPath::isSteppableMesh(b.name), "the seat is solid");
        expect(!RoomObjectPath::isWalkableSpaMesh(b.name), "the seat is no walkable spa piece");
    }
    // Use time: 10 to 30 s, drawn per use, in turns of the game
    expect(ToiletLayout::useSeconds(10.0, 30.0, 0.0) == 10.0 && ToiletLayout::useSeconds(10.0, 30.0, 1.0) == 30.0, "10 to 30 s");
    expect(ToiletLayout::useSeconds(10.0, 30.0, 0.5) == 20.0, "the draw maps linearly");
    expect(ToiletLayout::useTurns(10.0, 1.4) == 14 && ToiletLayout::useTurns(30.0, 1.4) == 42, "seconds to turns");
    expect(ToiletLayout::useTurns(0.1, 1.4) == 1, "at least one turn");
    std::printf("CHECKS FAILURES=%d\n", failures);
    return failures == 0 ? 0 : 1;
}
'''

if '--no-compile' not in sys.argv:
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='toilet_k25_probe_') as directory:
        directory = Path(directory)
        cpp = directory / 'probe.cpp'
        cpp.write_text(PROBE, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++14 /I"{ROOT / "source"}" "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}"\nexit /b %errorlevel%\n', encoding='utf-8')
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)
else:
    print('toilet layout probe deferred explicitly (--no-compile)')

print('ODP_TEST_PHASE {"name": "toilet k25 checks", "seconds": %.3f}' % (time.monotonic() - START))
print('toilet k25 ok')
