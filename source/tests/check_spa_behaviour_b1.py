"""Spa behaviour of INGAME-QS-10 B1: bathers step over the rim (K28), dropped creatures stay and bathe (K29) and the pool
attendant gets up for one outing, either the jump or a round around the pool (K30).

What is run (compiled probe; the real header functions and the real attendant functions, no copies)
  K28  SpaLayout::rimWalk + SpaLayout::nextBathLeg   every bather size (1x1, 1x2, 2x2) walks from every rim tile it can
                                                     arrive on to every free place of its size and back out, in rooms of
                                                     5x5, 6x6, 7x5 and 8x6 tiles: every leg stays on the rim or in the mud,
                                                     every crossing of the rim is a leg of its own of one tile, the way in
                                                     has exactly one step in and no step out, the way out exactly one step
                                                     out and no step in, every step goes to a neighbour tile of the room
       SpaLayout::rimStepLift / rimStepProgress      a step from the middle of a rim tile into the middle of a pool tile
                                                     and back: the lift is 0 in both middles, above the top of the real rim
                                                     mesh (models/SpaPoolRim.mesh) over the whole footprint of the rim
                                                     (RoomObjectBounds.h), without a jump, and the progress of the step goes
                                                     from 0 to 1 without a jump
  K29  SpaLayout::findDropBlock                      a drop on a free mud tile bathes there, a drop on a taken tile or on
                                                     the rim bathes at the nearest free place, a pool without a place of the
                                                     size gives none (the creature leaves as from every other room)
  K30  PoolAttendantOutings::choose                  both outings are chosen when both are possible, the only possible one
                                                     otherwise, none when neither is
       SpaLayout::attendantRound                     the round starts beside the chair on one side and ends beside it on the
                                                     other, goes over every rim tile but the chair once, never over the mud
       PoolAttendantEntity (upkeepSitting, startAct, upkeepAct, reserveCannonballPlace, startOuting, startClimb,
       upkeepClimb, upkeepWalkRound, upkeepWalkBack, sitDown, setState, rollActTurns, rollCannonballTurns; walks and the
       jump stubbed)                                 over 40000 turns: every outing is exactly one jump or one round, never
                                                     both; between two outings he sits the full pause of
                                                     SpaAttendantCannonballMinSeconds to SpaAttendantCannonballMaxSeconds
                                                     (acts on the chair do not lengthen it); both outings occur; without a
                                                     springboard only rounds, without a round only jumps, without both he
                                                     stays on the chair
What is checked on the source text (also with --no-compile)
  the walk of a bather uses the legs, the step clips, the client lift of bathers and of the attendant, the renderer builds
  the step clips; a drop uses canAcceptDrop and the place of the drop; the attendant chooses the outing with
  PoolAttendantOutings::choose, writes every phase to the log, counts the pause also during an act and sits the full pause
  after every outing; the configured pause is 120 to 180 seconds (answer to Q8: "as today").

Calls (from the repository root):
  python source/tests/check_spa_behaviour_b1.py              (the probe needs cl on the path, Visual Studio developer shell)
  python source/tests/check_spa_behaviour_b1.py --no-compile (source checks only)
"""
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The attendant values of config/rooms.cfg are own rows of the content package core-config: the values and the probe
#: built with them are checked only with the content
WITH_CONTENT = content_packages.has_content(root)

#: The assets of the spa come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(root, 'Spa')


def room_file(relative):
    """A file of the game data, or of the room package when it moved there."""
    return room_packages.resolve(root, relative)
started = time.monotonic()


def read(path):
    """Returns the text of a repository file; a mixed table comes with its own rows of the content."""
    return content_packages.read_text(root, path)


def body(text, signature):
    """Returns a function from its signature to its closing brace, nested braces included."""
    begin = text.index(signature)
    opening = text.index('{', begin)
    depth = 0
    for index in range(opening, len(text)):
        depth += (text[index] == '{') - (text[index] == '}')
        if depth == 0:
            return text[begin:index + 1]
    raise AssertionError('unclosed function: ' + signature)


def line(text, pattern):
    """Returns the one line of the text that matches the pattern."""
    found = re.findall(pattern, text, re.M)
    assert len(found) == 1, pattern
    return found[0]


def mesh_top(path):
    """Highest z of the positions of an Ogre binary mesh, read with the mesh reader of check_spa_owner_837."""
    source = read('source/tests/check_spa_owner_837.py')
    begin = source.index('def read_mesh(path):')
    reader = source[begin:source.index('\ndef ', begin + 1)]
    scope = {'struct': struct}
    exec(reader, scope)
    submeshes, _ = scope['read_mesh'](path)
    return max(point[2] for _, points in submeshes for point in points)


layout_h = read('source/rooms/RoomSpaLayout.h')
state_h = read('source/entities/PoolAttendantState.h')
spa_cpp = read('source/rooms/RoomSpa.cpp')
attendant_cpp = read('source/entities/PoolAttendantEntity.cpp')
creature_cpp = read('source/entities/Creature.cpp')
render_cpp = read('source/render/RenderManager.cpp')
rooms_cfg = read('config/rooms.cfg')
bounds_h = read('source/gamemap/RoomObjectBounds.h')

# ---- K28 source wiring ---------------------------------------------------------------------------------------------
walk = body(spa_cpp, 'bool RoomSpa::walkBather(')
for contract in ('SpaLayout::nextBathLeg(pool,', 'steps, SpaLayout::RIM_CROSSING_COST)', 'case SpaLayout::BathLeg::stepIn:', 'walkClip = SPA_STEP_IN_CLIP;',
                 'case SpaLayout::BathLeg::stepOut:', 'walkClip = SPA_STEP_OUT_CLIP;', 'walkClip = SPA_WADE_CLIP;',
                 'creature.setWalkPath(walkClip, endClip,'):
    assert contract in walk, contract
assert 'const std::string SPA_STEP_IN_CLIP = "SpaStepIn";' in spa_cpp and 'const std::string SPA_STEP_OUT_CLIP = "SpaStepOut";' in spa_cpp
update = body(creature_cpp, 'void Creature::update(')
assert 'updateSpaStepLift();' in update and update.index('updateSpaStepLift();') > update.index('showJumpClipPhase();')
step = body(creature_cpp, 'void Creature::updateSpaStepLift(')
for contract in ('RoomSpa::getRimStepLift(getGameMap(), getPosition(), edgeDistance, onPool)',
                 'SpaLayout::rimStepProgress(edgeDistance, onPool == stepIn)', 'setTimePosition(',
                 'position.z += lift - mSpaStepLift;'):
    assert contract in step, contract
attendant_update = body(attendant_cpp, 'void PoolAttendantEntity::update(')
assert 'RoomSpa::getRimStepLift(getGameMap(), getPosition(), edgeDistance, onPool)' in attendant_update
assert 'position.z += lift - mRimLift;' in attendant_update
lift = body(spa_cpp, 'double RoomSpa::getRimStepLift(')
assert 'SpaLayout::rimStepLift(' in lift and 'isPoolTile(gameMap->getTile(x + SIDE_DX[side], y + SIDE_DY[side]))' in lift
prepare = body(render_cpp, 'void prepareSpaAnimation(')
assert 'const bool stepIn = name == "SpaStepIn";' in prepare and 'const bool stepOut = name == "SpaStepOut";' in prepare
assert 'sink *= depth;' in prepare
assert '(animation == "SpaStepIn") || (animation == "SpaStepOut")' in body(render_cpp, 'void RenderManager::rrSetObjectAnimationState(')
search = read('source/creatureaction/CreatureActionSearchSpa.cpp')
assert 'cannot reach the rim of spa=' in search and 'OD_LOG_ERR("creature=" + creature.getName() + ", spa="' not in search

# ---- K29 source wiring ---------------------------------------------------------------------------------------------
drop = body(spa_cpp, 'void RoomSpa::creatureDropped(')
assert 'canAcceptDrop(creature, *tile, block)' in drop and 'mDroppedCreature = &creature;' in drop
assert drop.index('mDropBlock = block;') < drop.index('CreatureActionUseRoom>(creature, *this, true)') < drop.index('mDroppedCreature = nullptr;')
accept = body(spa_cpp, 'bool RoomSpa::canAcceptDrop(')
assert 'SpaLayout::findDropBlock(' in accept and 'canPay(creature)' in accept and 'canUsePleasureRoom' not in accept
add = body(spa_cpp, 'bool RoomSpa::addCreatureUsingRoom(')
assert '(creature == mDroppedCreature) && SpaLayout::isBlockFree(getPoolSet(), getTakenSet(), mDropBlock)' in add
assert '(creature != mDroppedCreature) && !isPoolTile(creatureTile)' in add, 'a dropped creature never takes the jump'

# ---- K30 source wiring ---------------------------------------------------------------------------------------------
outing = body(attendant_cpp, 'bool PoolAttendantEntity::startOuting(')
assert 'PoolAttendantOutings::choose(Random::Double(0.0, 1.0), canJump, canWalkRound)' in outing
assert 'getAttendantRound(round)' in body(attendant_cpp, 'void PoolAttendantEntity::startWalkRound(')
assert 'mCannonballTurnsLeft -= 1.0;' in body(attendant_cpp, 'void PoolAttendantEntity::upkeepAct(')
sit = body(attendant_cpp, 'void PoolAttendantEntity::sitDown(')
assert 'mOuting = PoolAttendantOuting::none;' in sit and 'mCannonballTurnsLeft = rollCannonballTurns();' in sit
log = body(attendant_cpp, 'void PoolAttendantEntity::setState(')
assert 'OD_LOG_INF("PoolAttendant " + getName() + " phase=" + PoolAttendantStateNames::toString(state) + " outing="' in log
assert re.search(r'^\s*mState = ', attendant_cpp.replace(log, ''), re.M) is None, 'every change of the phase goes through setState'
assert 'case PoolAttendantState::walkingRound:' in body(attendant_cpp, 'void PoolAttendantEntity::restoreFromSave(')
if WITH_CONTENT:
    config = dict(re.findall(r'^\s+(SpaAttendant\w+|PoolAttendantClipSeconds)\t+([0-9.]+)', rooms_cfg, re.M))
    # Fixed values of the answer to Q8 ("every 120 to 180 s as today") and of the acts
    assert config['SpaAttendantCannonballMinSeconds'] == '120' and config['SpaAttendantCannonballMaxSeconds'] == '180', config
    assert config['SpaAttendantActMinSeconds'] == '10' and config['SpaAttendantActMaxSeconds'] == '20', config
    assert config['PoolAttendantClipSeconds'] == '2', config
turns_per_second = float(line(read('source/ODApplication.cpp'), r'^double ODApplication::turnsPerSecond = ([0-9.]+);$'))

# ---- The rim the lift has to clear: the real mesh and its footprint ------------------------------------------------
# The rim mesh is in the spa package; without it the height the mesh measures (fixed value below) stands in
rim_top = mesh_top(room_file('models/SpaPoolRim.mesh')) if ROOM_ASSETS else 0.3
rim_row = re.search(r'\{"SpaPoolRim", ([-.0-9]+)f, ([-.0-9]+)f, ([-.0-9]+)f, ([-.0-9]+)f\}', bounds_h)
rim_near, rim_far = float(rim_row.group(2)), float(rim_row.group(4))
assert abs(rim_top - 0.3) < 1e-4 and abs(rim_near + 0.575) < 1e-6 and abs(rim_far + 0.425) < 1e-6, (rim_top, rim_near, rim_far)

if '--no-compile' in sys.argv:
    print('spa behaviour B1 source checks ok; compiled probe deferred explicitly (--no-compile)')
    print('ODP_TEST_PHASE {"name":"source","seconds":%.3f}' % (time.monotonic() - started))
    sys.exit(0)
if not WITH_CONTENT:
    content_packages.unchecked('check_spa_behaviour_b1', ['attendant values of config/rooms.cfg (own rows)',
                                                          'compiled probe built with them'])
    print('spa behaviour B1 source checks ok')
    print('ODP_TEST_PHASE {"name":"source","seconds":%.3f}' % (time.monotonic() - started))
    sys.exit(0)

constants = '\n'.join(
    re.findall(r'^const (?:uint32_t|double|std::string|Ogre::Vector3) (?:NB_ACTS_WITHOUT_BATHER|NB_ACTS_WITH_BATHER|ACT_TOWEL|'
               r'ACT_DOZE|WHISTLE_BLOW_SECONDS|SOUND_WHISTLE|TOWARDS_POOL|TOWARDS_CHAIR)\b[^\n]*$', attendant_cpp, re.M))
assert constants.count('\n') == 7, constants
functions = '\n'.join(body(attendant_cpp, signature).replace('PoolAttendantEntity::', 'AttendantSim::', 1)
                      for signature in ('double PoolAttendantEntity::rollActTurns(', 'double PoolAttendantEntity::rollCannonballTurns(',
                                        'void PoolAttendantEntity::setState(', 'void PoolAttendantEntity::upkeepSitting(',
                                        'void PoolAttendantEntity::startAct(', 'void PoolAttendantEntity::upkeepAct(',
                                        'bool PoolAttendantEntity::reserveCannonballPlace(', 'bool PoolAttendantEntity::startOuting(',
                                        'void PoolAttendantEntity::startClimb(', 'void PoolAttendantEntity::upkeepClimb(',
                                        'void PoolAttendantEntity::upkeepWalkBack(', 'void PoolAttendantEntity::upkeepWalkRound(',
                                        'void PoolAttendantEntity::sitDown('))

probe = r'''
#include "RoomSpaLayout.h"
#include "PoolAttendantState.h"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <vector>

static int failures = 0;
static void expect(bool condition, const std::string& what) { if(!condition) { ++failures; std::cout << "FAIL " << what << std::endl; } }
typedef std::pair<int32_t, int32_t> P;
static SpaTileSet rect(int32_t x, int32_t y, int32_t w, int32_t h)
{ SpaTileSet s; for(int32_t i = 0; i < w; ++i) for(int32_t j = 0; j < h; ++j) s.insert(P(x + i, y + j)); return s; }

// ---- K28 -----------------------------------------------------------------------------------------------------------
static bool walkLegs(const SpaTileSet& passable, const SpaTileSet& pool, P here, const P& to, int& stepsIn, int& stepsOut, const std::string& what)
{
    stepsIn = 0; stepsOut = 0;
    for(int leg = 0; leg < 200; ++leg)
    {
        std::vector<P> steps;
        if(!SpaLayout::rimWalk(passable, pool, here, to, steps, SpaLayout::RIM_CROSSING_COST)) { expect(false, what + ": no way"); return false; }
        SpaLayout::BathLeg kind = SpaLayout::BathLeg::rim;
        const std::size_t count = SpaLayout::nextBathLeg(pool, here, steps, kind);
        if(steps.empty()) { expect(count == 0, what + ": no leg at the target"); return true; }
        expect(count >= 1 && count <= steps.size(), what + ": a leg walks");
        const bool hereInPool = pool.count(here) != 0;
        P previous = here;
        for(std::size_t i = 0; i < count; ++i)
        {
            const bool inPool = pool.count(steps[i]) != 0;
            expect(std::abs(steps[i].first - previous.first) + std::abs(steps[i].second - previous.second) == 1, what + ": neighbour steps");
            expect(passable.count(steps[i]) == 1, what + ": steps on the room");
            if(kind == SpaLayout::BathLeg::rim) expect(!hereInPool && !inPool, what + ": a rim leg stays on the rim");
            if(kind == SpaLayout::BathLeg::wade) expect(hereInPool && inPool, what + ": a wading leg stays in the mud");
            if(kind == SpaLayout::BathLeg::stepIn) expect(count == 1 && !hereInPool && inPool, what + ": a step in is one step from the rim into the mud");
            if(kind == SpaLayout::BathLeg::stepOut) expect(count == 1 && hereInPool && !inPool, what + ": a step out is one step from the mud onto the rim");
            previous = steps[i];
        }
        stepsIn += (kind == SpaLayout::BathLeg::stepIn); stepsOut += (kind == SpaLayout::BathLeg::stepOut);
        here = steps[count - 1];
    }
    expect(false, what + ": the walk ends");
    return false;
}

static void checkLegs()
{
    const int32_t rooms[][2] = { {5, 5}, {6, 6}, {7, 5}, {8, 6} };
    const int32_t sizes[][2] = { {1, 1}, {1, 2}, {2, 2} };
    int walks = 0;
    for(const int32_t* room : rooms)
    {
        const SpaTileSet covered = rect(0, 0, room[0], room[1]);
        const SpaTileSet pool = SpaLayout::poolTiles(covered);
        P chair, board; SpaLayout::chairTile(pool, chair); SpaLayout::springboardTile(pool, board);
        for(const int32_t* size : sizes)
        {
            for(const P& anchor : pool)
            {
                SpaBlock block; block.mX = anchor.first; block.mY = anchor.second; block.mWidth = size[0]; block.mHeight = size[1];
                if(!SpaLayout::isBlockFree(pool, SpaTileSet(), block)) continue;
                for(const P& arrival : covered)
                {
                    if(pool.count(arrival) || arrival == chair || arrival == board) continue;
                    // The walk of RoomSpa::walkBather: the room without the chair and the springboard, the tile it stands on
                    SpaTileSet passable = covered; passable.erase(chair); passable.erase(board); passable.insert(arrival);
                    const std::string what = "room " + std::to_string(room[0]) + "x" + std::to_string(room[1]) + " size " +
                        std::to_string(size[0]) + "x" + std::to_string(size[1]);
                    int in = 0, out = 0;
                    if(walkLegs(passable, pool, arrival, anchor, in, out, what + " in"))
                        expect(in == 1 && out == 0, what + ": the way in steps over the rim once");
                    if(walkLegs(passable, pool, anchor, arrival, in, out, what + " out"))
                        expect(in == 0 && out == 1, what + ": the way out climbs over the rim once");
                    ++walks;
                }
            }
        }
    }
    expect(walks > 500, "enough walks");
}

static void checkLift()
{
    // A rim tile at y -1 and a pool tile at y 0: the rim edge at -0.5, the rim mesh on the pool tile from RIM_NEAR to RIM_FAR
    double previousLift = 0.0, previousProgress = -1.0;
    for(int i = 0; i <= 1000; ++i)
    {
        const double s = -1.0 + i / 1000.0;
        const bool onPool = s > -0.5;
        const double offset = onPool ? s : s + 1.0;
        // Sides -y, +x, +y, -x: the pool tile has the rim on -y and pool elsewhere, the rim tile has the pool on +y
        const bool poolTileSides[4] = { false, true, true, true };
        const bool rimTileSides[4] = { false, false, true, false };
        const bool* sides = onPool ? poolTileSides : rimTileSides;
        double edge = 0.0;
        const double lift = SpaLayout::rimStepLift(0.0, offset, onPool, sides, edge);
        const double progress = SpaLayout::rimStepProgress(edge, onPool);
        if(i == 0 || i == 1000) expect(std::fabs(lift) < 1e-9, "no lift in the middles of the tiles");
        if(s >= RIM_NEAR - 1e-9 && s <= RIM_FAR + 1e-9) expect(lift > RIM_MESH_TOP, "the feet clear the rim mesh over its footprint");
        if(i > 0) expect(std::fabs(lift - previousLift) < 0.01, "the lift has no jump");
        if(i > 0) expect(progress >= previousProgress - 1e-9 && progress - previousProgress < 0.01, "the step goes on without a jump");
        previousLift = lift; previousProgress = progress;
    }
    expect(std::fabs(previousProgress - 1.0) < 1e-9, "the step ends in the middle of the pool tile");
    // Walking along the rim (in the middle of the rim tile next to the pool) is no step
    bool sides[4] = { false, false, true, false }; double edge = 0.0;
    expect(SpaLayout::rimStepLift(0.3, 0.0, false, sides, edge) == 0.0, "walking along the rim lifts nobody");
}

// ---- K29 -----------------------------------------------------------------------------------------------------------
static void checkDrop()
{
    const SpaTileSet pool = SpaLayout::poolTiles(rect(0, 0, 5, 5));   // 1..3 x 1..3
    SpaBlock b;
    expect(SpaLayout::findDropBlock(pool, SpaTileSet(), 1, 1, P(3, 3), b) && b.mX == 3 && b.mY == 3, "a drop on free mud bathes there");
    SpaTileSet taken; taken.insert(P(3, 3));
    expect(SpaLayout::findDropBlock(pool, taken, 1, 1, P(3, 3), b) && std::abs(b.mX - 3) + std::abs(b.mY - 3) == 1, "a drop on a taken tile bathes next to it");
    expect(SpaLayout::findDropBlock(pool, SpaTileSet(), 1, 1, P(4, 2), b) && b.mX == 3 && b.mY == 2, "a drop on the rim bathes at the nearest place");
    expect(SpaLayout::findDropBlock(pool, SpaTileSet(), 2, 2, P(3, 3), b) && b.mX == 2 && b.mY == 2, "a large creature bathes at the place that holds the drop");
    SpaTileSet middle; middle.insert(P(2, 2));
    expect(!SpaLayout::findDropBlock(pool, middle, 2, 2, P(3, 3), b), "no place of its size: it leaves");
    SpaTileSet full = pool;
    expect(!SpaLayout::findDropBlock(pool, full, 1, 1, P(2, 2), b), "a full pool has no place");
}

// ---- K30 -----------------------------------------------------------------------------------------------------------
static void checkChoiceAndRound()
{
    int jumps = 0, rounds = 0;
    for(int i = 0; i < 1000; ++i)
    {
        const double roll = i / 1000.0;
        const PoolAttendantOuting both = PoolAttendantOutings::choose(roll, true, true);
        expect(both != PoolAttendantOuting::none, "an outing when both are possible");
        jumps += (both == PoolAttendantOuting::cannonball); rounds += (both == PoolAttendantOuting::round);
        expect(PoolAttendantOutings::choose(roll, true, false) == PoolAttendantOuting::cannonball, "only the jump");
        expect(PoolAttendantOutings::choose(roll, false, true) == PoolAttendantOuting::round, "only the round");
        expect(PoolAttendantOutings::choose(roll, false, false) == PoolAttendantOuting::none, "no outing");
    }
    expect(jumps > 300 && rounds > 300, "both outings are chosen");
    const int32_t rooms[][2] = { {4, 4}, {5, 5}, {6, 6}, {7, 5}, {8, 6} };
    for(const int32_t* room : rooms)
    {
        const SpaTileSet covered = rect(0, 0, room[0], room[1]);
        const SpaTileSet pool = SpaLayout::poolTiles(covered);
        P chair; SpaLayout::chairTile(pool, chair);
        std::vector<P> path;
        expect(SpaLayout::attendantRound(covered, pool, chair, path), "a round exists");
        if(path.empty()) continue;
        expect(path.front() == P(chair.first - 1, chair.second) && path.back() == P(chair.first + 1, chair.second), "the round goes from one side of the chair to the other");
        SpaTileSet seen;
        for(std::size_t i = 0; i < path.size(); ++i)
        {
            expect(pool.count(path[i]) == 0 && path[i] != chair && covered.count(path[i]) == 1, "the round stays on the rim");
            if(i > 0) expect(std::abs(path[i].first - path[i - 1].first) + std::abs(path[i].second - path[i - 1].second) == 1, "neighbour steps");
            seen.insert(path[i]);
        }
        expect(seen.size() == path.size() && seen.size() == covered.size() - pool.size() - 1, "the round passes every rim tile but the chair once");
    }
}

// ---- K30: the real attendant functions against stubs ---------------------------------------------------------------
namespace Ogre { typedef float Real; struct Vector3 { Real x, y, z; Vector3(Real a = 0, Real b = 0, Real c = 0) : x(a), y(b), z(c) {} static const Vector3 ZERO; }; const Vector3 Vector3::ZERO; }
namespace PoolAttendantPose { static const std::string sit = "Sit", whistle = "Whistle", towelWave = "TowelWave", doze = "Doze", climb = "Climb"; }
struct ODApplication { static constexpr double turnsPerSecond = TURNS_PER_SECOND; };
static std::mt19937 generator(7);
struct Random
{
    static double Double(double a, double b) { return std::uniform_real_distribution<double>(a, b)(generator); }
    static uint32_t Uint(uint32_t a, uint32_t b) { return std::uniform_int_distribution<uint32_t>(a, b)(generator); }
};
static std::map<std::string, double> CONFIG = { @@CONFIG@@ };
static double getClipTurns() { return CONFIG["PoolAttendantClipSeconds"] * ODApplication::turnsPerSecond; }
static double getConfigTurns(const std::string& key) { return CONFIG.at(key) * ODApplication::turnsPerSecond; }
struct Helper { static std::string toString(long long value) { return std::to_string(value); } };
#define OD_LOG_INF(message) (void)(message)
struct Tile { };
struct RoomSpa { static void playSoundAt(Tile*, const std::string&) { } };
@@CONSTANTS@@
struct ProbeMap { long long turn = 0; long long getTurnNumber() const { return turn; } };
struct ProbeRoom
{
    bool board = true, place = true, round = true; Tile boardTile;
    bool getAttendantRound(std::vector<P>& path) const { path.assign(round ? 1 : 0, P(0, 0)); return round; }
    Tile* getSpringboardTile() { return board ? &boardTile : nullptr; }
    bool findAttendantPlace(int32_t& x, int32_t& y) const { x = 2; y = 2; return place; }
    bool hasBatherInPool() const { return false; }
};
struct AttendantSim
{
    ProbeRoom* mRoom; Tile chair; Tile* mChairTile = &chair; PoolAttendantState mState = PoolAttendantState::sitting;
    double mTurnsLeft = 0.0; bool mWhistleSounded = false; double mActTurnsLeft = 0.0, mCannonballTurnsLeft = 0.0;
    PoolAttendantOuting mOuting = PoolAttendantOuting::none; bool mHasPlace = false; int32_t mPlaceX = 0, mPlaceY = 0;
    uint32_t mJumpTurnsLeft = 0; ProbeMap map; int walkTurns = 0;
    explicit AttendantSim(ProbeRoom* room) : mRoom(room) { mActTurnsLeft = rollActTurns(); mCannonballTurnsLeft = rollCannonballTurns(); }
    std::string getName() const { return "probe"; }
    ProbeMap* getGameMap() { return &map; }
    void setAnimationState(const std::string&, bool, const Ogre::Vector3&, bool) { }
    void clearDestinations(const std::string&, bool, bool) { }
    void moveTo(const Ogre::Vector3&) { }
    void placeOnLadder(double) { }
    Ogre::Vector3 getSeatPosition() const { return Ogre::Vector3(); }
    bool isMoving() { if(walkTurns > 0) { --walkTurns; return true; } return false; }
    void startWalkToBoard() { setState(PoolAttendantState::walkingToBoard); walkTurns = 6; }
    void startWalkRound(bool) { setState(PoolAttendantState::walkingRound); walkTurns = 14; }
    void abortToChair() { sitDown(); }
    double rollActTurns() const; double rollCannonballTurns() const; void setState(PoolAttendantState state);
    void upkeepSitting(); void startAct(); void upkeepAct(); bool reserveCannonballPlace(); bool startOuting();
    void startClimb(bool down); void upkeepClimb(); void upkeepWalkBack(); void upkeepWalkRound(); void sitDown();
};
@@FUNCTIONS@@

// One turn of the attendant as PoolAttendantEntity::doUpkeep; the walk to the board ends in the jump, the landing starts
// the walk back (stubbed like the walks)
static void turn(AttendantSim& a, int& jumpTurns)
{
    ++a.map.turn;
    switch(a.mState)
    {
        case PoolAttendantState::sitting: a.upkeepSitting(); break;
        case PoolAttendantState::whistling: case PoolAttendantState::towelWaving: case PoolAttendantState::dozing: a.upkeepAct(); break;
        case PoolAttendantState::climbingDown: case PoolAttendantState::climbingUp: a.upkeepClimb(); break;
        case PoolAttendantState::walkingToBoard: if(!a.isMoving()) { a.setState(PoolAttendantState::jumping); jumpTurns = 2; } break;
        case PoolAttendantState::jumping: if(--jumpTurns == 0) { a.setState(PoolAttendantState::walkingBack); a.walkTurns = 5; } break;
        case PoolAttendantState::walkingBack: a.upkeepWalkBack(); break;
        case PoolAttendantState::walkingRound: a.upkeepWalkRound(); break;
    }
}

static void simulate(bool board, bool round, int& jumps, int& rounds, int& outings)
{
    ProbeRoom room; room.board = board; room.round = round;
    AttendantSim a(&room);
    const double minPause = CONFIG["SpaAttendantCannonballMinSeconds"] * ODApplication::turnsPerSecond;
    const double maxPause = CONFIG["SpaAttendantCannonballMaxSeconds"] * ODApplication::turnsPerSecond;
    const double clip = getClipTurns();
    jumps = 0; rounds = 0; outings = 0;
    long long seatedSince = 0; bool out = false; bool jumped = false, walkedRound = false; int jumpTurns = 0;
    for(int t = 0; t < 40000; ++t)
    {
        const PoolAttendantState before = a.mState;
        turn(a, jumpTurns);
        if(before == a.mState) continue;
        if(a.mState == PoolAttendantState::climbingDown)
        {
            const long long pause = a.map.turn - seatedSince;
            // The first pause starts at the spawn; an outing that falls due in an act waits for its end (one clip)
            expect(pause >= std::floor(minPause) && pause <= std::ceil(maxPause) + std::ceil(clip) + 1,
                "he sits the full pause between two outings: " + std::to_string(pause));
            expect(!out, "no outing starts in an outing");
            expect(a.mOuting != PoolAttendantOuting::none, "an outing has its kind");
            expect((a.mOuting == PoolAttendantOuting::cannonball) == a.mHasPlace, "only the jump holds a place");
            out = true; jumped = false; walkedRound = false; ++outings;
        }
        if(a.mState == PoolAttendantState::jumping) { jumped = true; expect(a.mOuting == PoolAttendantOuting::cannonball, "the jump belongs to a jump outing"); }
        if(a.mState == PoolAttendantState::walkingRound) { walkedRound = true; expect(a.mOuting == PoolAttendantOuting::round, "the round belongs to a round outing"); }
        if(a.mState == PoolAttendantState::sitting && out && before == PoolAttendantState::climbingUp)
        {
            expect(jumped != walkedRound, "every outing is either the jump or the round, never both");
            jumps += jumped; rounds += walkedRound; out = false; seatedSince = a.map.turn;
            expect(a.mOuting == PoolAttendantOuting::none && !a.mHasPlace, "back on the chair without an outing and a place");
        }
    }
}

static void checkAttendant()
{
    int jumps = 0, rounds = 0, outings = 0;
    simulate(true, true, jumps, rounds, outings);
    expect(outings >= 100 && jumps >= 30 && rounds >= 30 && jumps + rounds + 1 >= outings, "both outings occur, each outing is one of them");
    simulate(false, true, jumps, rounds, outings);
    expect(outings >= 100 && jumps == 0 && rounds + 1 >= outings, "without a springboard only rounds");
    simulate(true, false, jumps, rounds, outings);
    expect(outings >= 100 && rounds == 0 && jumps + 1 >= outings, "without a round only jumps");
    simulate(false, false, jumps, rounds, outings);
    expect(outings == 0, "without both he stays on the chair");
}

int main()
{
    checkLegs();
    checkLift();
    checkDrop();
    checkChoiceAndRound();
    checkAttendant();
    if(failures == 0) std::cout << "spa behaviour B1 ok" << std::endl;
    return failures == 0 ? 0 : 1;
}
'''
config_text = ', '.join('{"%s", %s}' % (key, value) for key, value in sorted(config.items()))
probe = (probe.replace('@@CONFIG@@', config_text).replace('@@CONSTANTS@@', constants).replace('@@FUNCTIONS@@', functions)
         .replace('TURNS_PER_SECOND', repr(turns_per_second)).replace('RIM_MESH_TOP', repr(rim_top))
         .replace('RIM_NEAR', repr(rim_near)).replace('RIM_FAR', repr(rim_far)))
setup_seconds = time.monotonic() - started
with tempfile.TemporaryDirectory(prefix='odp-spa-b1-') as directory:
    work = Path(directory)
    (work / 'check.cpp').write_text(probe, encoding='utf-8')
    compile_started = time.monotonic()
    subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/O2', '/std:c++17', '/W3', '/I' + str(root / 'source' / 'rooms'),
                    '/I' + str(root / 'source' / 'entities'), 'check.cpp', '/Fecheck.exe'], cwd=work, check=True)
    run_started = time.monotonic()
    subprocess.run([str(work / 'check.exe')], cwd=work, check=True)
    finished = time.monotonic()
print('ODP_TEST_PHASE {"name":"setup","seconds":%.3f}' % setup_seconds)
print('ODP_TEST_PHASE {"name":"compile","seconds":%.3f}' % (run_started - compile_started))
print('ODP_TEST_PHASE {"name":"run","seconds":%.3f}' % (finished - run_started))
print('spa behaviour B1 ok')
