"""The infirmary shaman never walks through a cot or other furniture (INGAME-QS-10 K23, owner finding "laeuft durch die
Betten hindurch").

Two parts:
  wiring (no compiler)  InfirmaryShamanEntity::walkToCot plans every walk with InfirmaryShamanWalk::plan against all room
                        furniture (RoomObjectNavigation::collect widened by InfirmaryShamanWalk::WALKING_RADIUS) and the
                        floor of its own room, and hands the planned waypoints to setWalkPath as an exact route; the old
                        tile-centre search over cot tiles is gone. RoomInfirmary::getShamanWalkTargets offers the floor
                        tile beside each cot (InfirmaryShamanWalk::besideCot), never a cot tile; updateShaman places a new
                        figure on the free standing point of the instrument table tile; poses are played beside a
                        patient's cot (isBesidePatient).
  probe (cl)            the unchanged production header source/rooms/InfirmaryShamanWalk.h with the production furniture
                        bounds (RoomObjectBounds.h) and route search (RoomObjectPath.h) is compiled with a 5 x 5
                        infirmary (one large, three medium and two small cots, cabinet, instrument table, wash basin,
                        herb shelf) and asserts the outcome:
                        - every cot gets a target tile that touches it by a side and holds no cot;
                        - a cot tile has no standing point (the old walk target, the cot itself, is impossible);
                        - from every free tile to every target a route exists, and every waypoint and every leg of it
                          keeps the walking radius away from every piece of furniture and stays on the room floor;
                        - a figure saved on a cot (old save) walks off it and then never enters furniture again;
                        - a target outside the room is refused.
Fixed expected values of this branch (counted once): WALKING_RADIUS 0.15 tiles, 6 cots and 4 wall pieces in the probe
room, 13 free tiles x 7 targets = 91 routes.
The probe compiles with cl (needs CMAKE_PREFIX_PATH with OGRE), so it runs in the compile phase of the integration;
`--no-compile` runs the wiring part only.

Call (from the repository root): python source/tests/check_infirmary_shaman_walk.py [--no-compile]
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def body(source, signature):
    """Returns the production text from the signature to the end of its braces block."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


fails = []
entity = read('source/entities/InfirmaryShamanEntity.cpp')
room = read('source/rooms/RoomInfirmaryShaman.cpp')
header = read('source/rooms/InfirmaryShamanWalk.h')

walk = body(entity, 'bool InfirmaryShamanEntity::walkToCot(')
if 'RoomObjectNavigation::collect(*getGameMap(), InfirmaryShamanWalk::WALKING_RADIUS)' not in walk:
    fails.append('wiring: walkToCot does not plan against all room furniture widened by the walking radius')
if not re.search(r'InfirmaryShamanWalk::plan\(start, InfirmaryShamanWalk::Cell\(destination->getX\(\), '
                 r'destination->getY\(\)\), floor,\s*furniture, path\)', walk):
    fails.append('wiring: walkToCot does not plan its route with InfirmaryShamanWalk::plan')
if 'setWalkPath("Walk", "Idle", true, true, path, false, true)' not in walk:
    fails.append('wiring: the planned route is not handed to setWalkPath as an exact route')
if 'pending' in walk or 'previous' in walk:
    fails.append('wiring: the old tile-centre search over the cot tiles is still there')
targets = body(room, 'std::vector<Tile*> RoomInfirmary::getShamanWalkTargets(')
if 'InfirmaryShamanWalk::besideCot(cot, floor, cots, accessories, beside)' not in targets:
    fails.append('wiring: the walk targets are not the tiles beside the cots')
if 'getPositionTile()' in targets or 'tiles.front()' in targets:
    fails.append('wiring: a cot tile (or the patient lying on it) is still offered as a walk target')
spawn = body(room, 'void RoomInfirmary::updateShaman(')
if 'InfirmaryShamanWalk::standingPoint(' not in spawn:
    fails.append('wiring: a new figure is not placed on a free standing point of its tile')
upkeep = body(entity, 'void InfirmaryShamanEntity::doUpkeep(')
if 'room.isBesidePatient(*getPositionTile())' not in upkeep:
    fails.append('wiring: poses are not played beside a patient cot')
if 'rooms/InfirmaryShamanWalk.h' not in read('CMakeLists.txt'):
    fails.append('wiring: InfirmaryShamanWalk.h is not in the source list')
if not re.search(r'static const float WALKING_RADIUS = 0\.15f;', header):
    fails.append('wiring: WALKING_RADIUS must be 0.15 tiles')
if fails:
    print('FAIL')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('infirmary shaman walk wiring ok')

PROBE = r'''
#include "rooms/InfirmaryShamanWalk.h"
#include "gamemap/RoomObjectBounds.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>

using InfirmaryShamanWalk::Cell;
static int checks = 0, failures = 0;
//! Counts one assertion and reports a failed one.
static void check(bool ok, const std::string& what)
{
    ++checks;
    if(!ok)
    {
        ++failures;
        std::printf("FAIL %s\n", what.c_str());
    }
}

//! One placed piece of furniture: mesh, centre and angle in degrees.
struct Piece { const char* mesh; float x, y, angle; };

//! Builds the obstacle of a piece the same way RoomObjectNavigation::collect does.
static RoomObjectPath::Obstacle obstacle(const Piece& piece, float clearance)
{
    for(const RoomObjectPath::MeshBounds& bounds : RoomObjectPath::meshBounds)
    {
        if(std::strcmp(bounds.name, piece.mesh) != 0)
            continue;
        const RoomObjectPath::FurnitureScale scale = RoomObjectPath::furnitureScale(bounds);
        const float angle = piece.angle * RoomObjectPath::degreesToRadians;
        RoomObjectPath::Obstacle result{{bounds.minX * scale.x - clearance, bounds.minY * scale.y - clearance},
            {bounds.maxX * scale.x + clearance, bounds.maxY * scale.y + clearance},
            {piece.x, piece.y}, std::cos(angle), std::sin(angle)};
        return result;
    }
    std::printf("FAIL no measured bounds for %s\n", piece.mesh);
    ++failures;
    return RoomObjectPath::Obstacle{{0, 0}, {0, 0}, {piece.x, piece.y}, 1, 0};
}

//! Runs the 5 x 5 infirmary of the docstring.
int main()
{
    std::set<Cell> floor;
    for(int x = 0; x < 5; ++x)
        for(int y = 0; y < 5; ++y)
            floor.insert(Cell(x, y));
    // cots: tiles and placement (centre of the footprint, 0 = long side along +Y, 90 = along X)
    const std::vector<std::vector<Cell>> cots = {
        {Cell(3, 3), Cell(4, 3), Cell(3, 4), Cell(4, 4)},
        {Cell(0, 3), Cell(0, 4)}, {Cell(2, 1), Cell(2, 2)}, {Cell(4, 0), Cell(4, 1)},
        {Cell(0, 0)}, {Cell(0, 1)}};
    const std::vector<Piece> pieces = {
        {"InfirmaryCotLarge", 3.5f, 3.5f, 0.0f}, {"InfirmaryCotMedium", 0.0f, 3.5f, 0.0f},
        {"InfirmaryCotMedium", 2.0f, 1.5f, 0.0f}, {"InfirmaryCotMedium", 4.0f, 0.5f, 0.0f},
        {"InfirmaryCotSmall", 0.0f, 0.0f, 0.0f}, {"InfirmaryCotSmall", 0.0f, 1.0f, 0.0f},
        {"MedicineCabinet", 1.0f, 4.0f, 0.0f}, {"InstrumentTable", 2.0f, 4.0f, 0.0f},
        {"WashBasin", 0.0f, 2.0f, 90.0f}, {"HerbShelf", 4.0f, 2.0f, 270.0f}};
    const std::set<Cell> accessories = {Cell(1, 4), Cell(2, 4), Cell(0, 2), Cell(4, 2)};
    std::set<Cell> cotCells;
    for(const std::vector<Cell>& cot : cots)
        cotCells.insert(cot.begin(), cot.end());
    std::vector<RoomObjectPath::Obstacle> furniture, exact;
    for(const Piece& piece : pieces)
    {
        furniture.push_back(obstacle(piece, InfirmaryShamanWalk::WALKING_RADIUS));
        exact.push_back(obstacle(piece, 0.0f));
    }
    check(furniture.size() == 10, "10 pieces of furniture");

    // targets beside the cots, never on them
    std::vector<Cell> targets;
    for(const std::vector<Cell>& cot : cots)
    {
        Cell beside;
        check(InfirmaryShamanWalk::besideCot(cot, floor, cotCells, accessories, beside), "every cot has a tile beside it");
        check(cotCells.count(beside) == 0, "the target beside a cot is no cot tile");
        bool touches = false;
        for(const Cell& c : cot)
            touches = touches || std::abs(c.first - beside.first) + std::abs(c.second - beside.second) == 1;
        check(touches, "the target touches its cot by a side");
        targets.push_back(beside);
    }
    targets.push_back(Cell(2, 4));   // the instrument table tile
    check(targets.size() == 7, "6 cot targets and the instrument table");

    // the cot itself (the old target) has no standing point
    for(const Cell& c : cotCells)
    {
        Ogre::Vector2 point;
        check(!InfirmaryShamanWalk::standingPoint(furniture, c, point), "no standing point on a cot tile");
    }

    // every route from every free tile to every target clears the furniture and stays in the room
    int routes = 0;
    for(const Cell& from : floor)
    {
        if(cotCells.count(from) != 0)
            continue;
        Ogre::Vector2 start;
        if(!InfirmaryShamanWalk::standingPoint(furniture, from, start))
        {
            check(false, "every free tile has a standing point");
            continue;
        }
        for(const Cell& target : targets)
        {
            std::vector<Ogre::Vector2> path;
            const bool planned = InfirmaryShamanWalk::plan(start, target, floor, furniture, path);
            check(planned && !path.empty(), "a route to every target");
            if(!planned)
                continue;
            ++routes;
            Ogre::Vector2 previous = start;
            for(const Ogre::Vector2& p : path)
            {
                check(RoomObjectPath::clearPoint(furniture, p), "waypoint keeps the walking radius from the furniture");
                check(RoomObjectPath::clearSegment(furniture, previous, p), "leg keeps the walking radius from the furniture");
                check(RoomObjectPath::clearSegment(exact, previous, p), "leg never crosses a piece of furniture");
                check(InfirmaryShamanWalk::insideRoom(floor, previous, p), "leg stays on the room floor");
                previous = p;
            }
            const Cell end(int(std::floor(path.back().x + 0.5f)), int(std::floor(path.back().y + 0.5f)));
            check(end == target, "the route ends in the target tile");
        }
    }
    check(routes == 13 * 7, "13 free tiles x 7 targets");

    // an old save left the figure on a cot: it walks off and then never enters furniture again
    {
        std::vector<Ogre::Vector2> path;
        const Ogre::Vector2 onCot(3.5f, 3.5f);
        check(InfirmaryShamanWalk::plan(onCot, targets[1], floor, furniture, path) && !path.empty(),
            "a figure on a cot finds a way off it");
        Ogre::Vector2 previous = onCot;
        for(size_t i = 0; i < path.size(); ++i)
        {
            check(RoomObjectPath::clearSegment(furniture, previous, path[i], i == 0), "after leaving the cot no furniture");
            previous = path[i];
        }
    }

    // outside the room
    {
        std::vector<Ogre::Vector2> path;
        check(!InfirmaryShamanWalk::plan(Ogre::Vector2(2, 3), Cell(7, 3), floor, furniture, path), "no target outside the room");
    }
    std::printf("infirmary shaman walk probe: %d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
'''


def main():
    """Compiles and runs the probe of the production walk planning."""
    if '--no-compile' in sys.argv:
        print('infirmary shaman walk compiled probe deferred explicitly (--no-compile)')
        return
    prefix = Path(os.environ['CMAKE_PREFIX_PATH'])
    with tempfile.TemporaryDirectory(prefix='odp-shaman-walk-') as directory:
        work = Path(directory)
        (work / 'check.cpp').write_text(PROBE, encoding='utf-8')
        subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/O2', '/std:c++17', f'/I{ROOT / "source"}',
                        f'/I{prefix / "include/OGRE"}', 'check.cpp', '/Fecheck.exe', '/link',
                        f'/LIBPATH:{prefix / "lib"}', 'OgreMain.lib'], cwd=work, check=True)
        subprocess.run([str(work / 'check.exe')], cwd=work, check=True)
    print('infirmary shaman walk passes the checks')


if __name__ == '__main__':
    main()
