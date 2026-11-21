/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

// Header-only Boost.Test, see test_DungeonHeartTier.cpp.
// OVERRIDE_BOOST_TEST_INCLUDED_WARNING
#define BOOST_TEST_MODULE WorkerDigOrder
#include <boost/test/included/unit_test.hpp>

#include "game/WorkerDigOrder.h"

#include <cstdint>
#include <cstdlib>
#include <vector>

namespace
{
//! Dig steps of an earth wall: fullness 100 at the Ziv dig rate 20 (DigRate of creatures.cfg)
const int32_t EARTH_DIG_STEPS = 5;
//! Gold of a gold wall at density 100 (GoldPerSeamTile of global.cfg)
const double GOLD_PER_WALL = 3000.0;
//! Gold of one dig step on a gold wall at density 100 (GoldPerDigStep of global.cfg)
const double GOLD_PER_STEP = 25.0;
//! Gold of one dig step on a gem wall (GemGoldPerDigStep of global.cfg)
const double GEM_GOLD_PER_STEP = 16.67;
//! Gold a Ziv carries before it takes its load to the treasury (MaxGoldCarryable of creatures.cfg)
const double GOLD_CAPACITY = 100.0;
//! Turns after which a run without the expected result counts as failed
const int32_t MAX_TURNS = 20000;

//! \brief The kind of a marked wall.
enum class WallKind
{
    earth,
    gold,
    gem
};

//! \brief A marked wall of the model map with its one dig place.
struct Wall
{
    WallKind kind;
    int32_t placeX;
    int32_t placeY;
    //! Dig steps left on an earth wall, gold left on a gold wall; a gem wall never runs out
    double left;
    bool loadTaken;
    int32_t diggers;
    //! The turn the wall was dug out, -1 while it stands
    int32_t dugTurn;
};

//! \brief What a Ziv of the model does in a turn.
enum class ZivState
{
    choosing,
    walkingToWall,
    digging,
    walkingToTreasury,
    walkingBack
};

//! \brief A Ziv of the model with the dig job.
struct Ziv
{
    int32_t x;
    int32_t y;
    ZivState state;
    int32_t wall;
    int32_t walkTurns;
    double carried;
    bool afterDelivery;
};

//! \brief The model run of the dig job: the walls, the Zivs, the treasury and what was dug.
struct DigRun
{
    std::vector<Wall> walls;
    std::vector<Ziv> zivs;
    int32_t treasuryX;
    int32_t treasuryY;
    bool goldFirst;
    //! false runs the rules of build 0.7.4.79: the Ziv keeps its gold wall during every delivery and the choice
    //! knows no wall a load was carried away from
    bool fixed;
    double goldMined;
};

//! \brief Returns the walking turns between two places of the model (one tile per turn).
int32_t walkTurns(int32_t fromX, int32_t fromY, int32_t toX, int32_t toY)
{
    return std::abs(fromX - toX) + std::abs(fromY - toY);
}

//! \brief Returns whether a wall still stands and can be dug.
bool stands(const Wall& wall)
{
    return wall.dugTurn < 0;
}

//! \brief Adds a marked wall to the model map.
void addWall(DigRun& run, WallKind kind, int32_t placeX, int32_t placeY)
{
    double left = 0.0;
    if(kind == WallKind::earth)
        left = static_cast<double>(EARTH_DIG_STEPS);
    else if(kind == WallKind::gold)
        left = GOLD_PER_WALL;
    Wall wall = {kind, placeX, placeY, left, false, 0, -1};
    run.walls.push_back(wall);
}

//! \brief Adds a Ziv with the dig job that has not chosen a wall yet.
void addZiv(DigRun& run, int32_t x, int32_t y)
{
    Ziv ziv = {x, y, ZivState::choosing, -1, 0, 0.0, false};
    run.zivs.push_back(ziv);
}

//! \brief Lets the Ziv choose its wall with the rules of WorkerDigOrder, as CreatureActionSearchTileToDig does.
//! Returns false when no wall is left.
bool chooseWall(DigRun& run, Ziv& ziv)
{
    int32_t best = -1;
    int bestGroup = 5;
    bool bestHere = false;
    float bestDistance = 0.0f;
    for(uint32_t index = 0; index < run.walls.size(); ++index)
    {
        const Wall& wall = run.walls[index];
        if(!stands(wall))
            continue;
        const bool goldOrGem = wall.kind != WallKind::earth;
        const bool afterDelivery = run.fixed && ziv.afterDelivery;
        const int group = WorkerDigOrder::group(run.goldFirst, goldOrGem, wall.diggers > 0, wall.loadTaken,
            afterDelivery);
        const bool here = ziv.x == wall.placeX && ziv.y == wall.placeY;
        const float dx = static_cast<float>(ziv.x - wall.placeX);
        const float dy = static_cast<float>(ziv.y - wall.placeY);
        const float distance = dx * dx + dy * dy;
        if(!WorkerDigOrder::ranksBefore(best >= 0, group, here, distance, bestGroup, bestHere, bestDistance))
            continue;
        best = static_cast<int32_t>(index);
        bestGroup = group;
        bestHere = here;
        bestDistance = distance;
    }
    if(best < 0)
        return false;
    Wall& wall = run.walls[static_cast<uint32_t>(best)];
    ++wall.diggers;
    ziv.wall = best;
    ziv.afterDelivery = false;
    ziv.walkTurns = walkTurns(ziv.x, ziv.y, wall.placeX, wall.placeY);
    ziv.state = ZivState::walkingToWall;
    return true;
}

//! \brief Sends the Ziv with its full load to the treasury, as CreatureActionDigTile does: with the fix and "gold
//! first" off it leaves its wall, otherwise it keeps it and comes back.
void startDelivery(DigRun& run, Ziv& ziv)
{
    Wall& wall = run.walls[static_cast<uint32_t>(ziv.wall)];
    const bool keepsWall = !run.fixed || WorkerDigOrder::keepsWallForDelivery(run.goldFirst);
    if(!keepsWall || !stands(wall))
    {
        if(run.fixed && !run.goldFirst)
        {
            wall.loadTaken = true;
            ziv.afterDelivery = true;
        }
        if(stands(wall))
            --wall.diggers;
        ziv.wall = -1;
    }
    ziv.walkTurns = walkTurns(ziv.x, ziv.y, run.treasuryX, run.treasuryY);
    ziv.state = ZivState::walkingToTreasury;
}

//! \brief Runs one dig step of the Ziv on its wall.
void digStep(DigRun& run, Ziv& ziv, int32_t turn)
{
    Wall& wall = run.walls[static_cast<uint32_t>(ziv.wall)];
    if(!stands(wall))
    {
        // Another Ziv dug the wall out
        ziv.wall = -1;
        ziv.state = ZivState::choosing;
        return;
    }
    if(wall.kind == WallKind::earth)
    {
        wall.left -= 1.0;
    }
    else
    {
        double gold = wall.kind == WallKind::gold ? GOLD_PER_STEP : GEM_GOLD_PER_STEP;
        if(wall.kind == WallKind::gold)
        {
            if(gold > wall.left)
                gold = wall.left;
            wall.left -= gold;
        }
        ziv.carried += gold;
        run.goldMined += gold;
    }
    if(wall.kind != WallKind::gem && wall.left <= 0.0)
    {
        wall.dugTurn = turn;
        wall.diggers = 0;
        ziv.state = ZivState::choosing;
    }
    if(ziv.carried >= GOLD_CAPACITY)
    {
        startDelivery(run, ziv);
        return;
    }
    if(!stands(wall))
        ziv.wall = -1;
}

//! \brief Runs one turn of every Ziv of the model.
void runTurn(DigRun& run, int32_t turn)
{
    for(Ziv& ziv : run.zivs)
    {
        switch(ziv.state)
        {
            case ZivState::choosing:
                chooseWall(run, ziv);
                break;
            case ZivState::walkingToWall:
            case ZivState::walkingBack:
                if(ziv.walkTurns > 0)
                {
                    --ziv.walkTurns;
                    break;
                }
                ziv.x = run.walls[static_cast<uint32_t>(ziv.wall)].placeX;
                ziv.y = run.walls[static_cast<uint32_t>(ziv.wall)].placeY;
                ziv.state = ZivState::digging;
                digStep(run, ziv, turn);
                break;
            case ZivState::digging:
                digStep(run, ziv, turn);
                break;
            case ZivState::walkingToTreasury:
                if(ziv.walkTurns > 0)
                {
                    --ziv.walkTurns;
                    break;
                }
                ziv.x = run.treasuryX;
                ziv.y = run.treasuryY;
                ziv.carried = 0.0;
                if(ziv.wall >= 0 && stands(run.walls[static_cast<uint32_t>(ziv.wall)]))
                {
                    const Wall& wall = run.walls[static_cast<uint32_t>(ziv.wall)];
                    ziv.walkTurns = walkTurns(ziv.x, ziv.y, wall.placeX, wall.placeY);
                    ziv.state = ZivState::walkingBack;
                }
                else
                {
                    if(ziv.wall >= 0)
                        ziv.wall = -1;
                    ziv.state = ZivState::choosing;
                }
                break;
        }
    }
}

//! \brief Returns the turn the first wall of a kind was dug out, -1 when none was.
int32_t firstDug(const DigRun& run, WallKind kind)
{
    int32_t first = -1;
    for(const Wall& wall : run.walls)
        if(wall.kind == kind && wall.dugTurn >= 0 && (first < 0 || wall.dugTurn < first))
            first = wall.dugTurn;
    return first;
}

//! \brief Returns the turn the last wall of a kind was dug out, -1 while one of them stands.
int32_t lastDug(const DigRun& run, WallKind kind)
{
    int32_t last = -1;
    for(const Wall& wall : run.walls)
    {
        if(wall.kind != kind)
            continue;
        if(wall.dugTurn < 0)
            return -1;
        if(wall.dugTurn > last)
            last = wall.dugTurn;
    }
    return last;
}

//! \brief Runs the model until the condition holds or MAX_TURNS passed; returns the turns run.
int32_t runUntilEarthDug(DigRun& run)
{
    int32_t turn = 0;
    while(turn < MAX_TURNS && lastDug(run, WallKind::earth) < 0)
    {
        runTurn(run, turn);
        ++turn;
    }
    return turn;
}

//! \brief The observed case: a corridor from the treasury, three Zivs at a gold vein of three marked gold walls next
//! to them and four marked earth walls further down the corridor, all reachable; Automatic gives the Zivs the dig job.
DigRun observedCase(bool goldFirst, bool fixed)
{
    DigRun run;
    run.treasuryX = 0;
    run.treasuryY = 0;
    run.goldFirst = goldFirst;
    run.fixed = fixed;
    run.goldMined = 0.0;
    // The gold vein: dig places on the corridor right at the Zivs
    addWall(run, WallKind::gold, 4, 0);
    addWall(run, WallKind::gold, 5, 0);
    addWall(run, WallKind::gold, 6, 0);
    // The earth walls at the end of the corridor
    addWall(run, WallKind::earth, 9, 0);
    addWall(run, WallKind::earth, 10, 0);
    addWall(run, WallKind::earth, 11, 0);
    addWall(run, WallKind::earth, 12, 0);
    addZiv(run, 5, 0);
    addZiv(run, 5, 0);
    addZiv(run, 5, 0);
    return run;
}

//! \brief The rank of build 0.7.4.79 in CreatureActionSearchTileToDig, kept here to compare with WorkerDigOrder.
bool oldRanksBefore(bool haveBest, int group, bool here, float dist, int bestGroup, bool bestStanding, float distBest)
{
    return !(haveBest && (group > bestGroup ||
        (group == bestGroup && bestStanding && !here) ||
        (group == bestGroup && bestStanding == here && dist >= distBest)));
}
}

//! Checks that the rules of build 0.7.4.79 reproduce the observed case: with "gold first" off the three Zivs take
//! the three gold walls next to them, keep them through every delivery and dig no earth wall before a gold wall is
//! empty (a gold wall holds 30 loads).
BOOST_AUTO_TEST_CASE(test_observedCaseReproduced)
{
    DigRun run = observedCase(false, false);
    const int32_t turns = runUntilEarthDug(run);
    BOOST_REQUIRE(turns < MAX_TURNS);
    const int32_t firstEarth = firstDug(run, WallKind::earth);
    const int32_t firstGold = firstDug(run, WallKind::gold);
    BOOST_REQUIRE(firstGold >= 0);
    BOOST_REQUIRE(firstEarth >= 0);
    BOOST_CHECK(firstEarth > firstGold);
}

//! Checks the fix with "gold first" off in the observed case: earth walls are dug while gold is mined; every earth
//! wall is dug out while every gold wall still holds gold, so before all marked gold is dug out.
BOOST_AUTO_TEST_CASE(test_earthDugWithGoldFirstOff)
{
    DigRun run = observedCase(false, true);
    const int32_t turns = runUntilEarthDug(run);
    BOOST_REQUIRE(turns < MAX_TURNS);
    BOOST_REQUIRE(firstDug(run, WallKind::earth) >= 0);
    BOOST_REQUIRE(lastDug(run, WallKind::earth) >= 0);
    BOOST_CHECK(firstDug(run, WallKind::gold) < 0);
    BOOST_CHECK(run.goldMined > 0.0);
}

//! Checks that with "gold first" on gold walls stay first as before: the Zivs keep their gold walls and the first
//! earth wall is dug only after every gold wall is dug out, although the earth walls lie nearer to the Zivs.
BOOST_AUTO_TEST_CASE(test_goldFirstOnKeepsGoldFirst)
{
    DigRun run;
    run.treasuryX = 0;
    run.treasuryY = 0;
    run.goldFirst = true;
    run.fixed = true;
    run.goldMined = 0.0;
    addWall(run, WallKind::earth, 5, 0);
    addWall(run, WallKind::earth, 6, 0);
    addWall(run, WallKind::gold, 9, 0);
    addWall(run, WallKind::gold, 10, 0);
    addZiv(run, 5, 0);
    addZiv(run, 5, 0);
    addZiv(run, 5, 0);
    const int32_t turns = runUntilEarthDug(run);
    BOOST_REQUIRE(turns < MAX_TURNS);
    const int32_t lastGold = lastDug(run, WallKind::gold);
    BOOST_REQUIRE(lastGold >= 0);
    BOOST_CHECK(firstDug(run, WallKind::earth) > lastGold);
    BOOST_CHECK(!WorkerDigOrder::keepsWallForDelivery(false));
    BOOST_CHECK(WorkerDigOrder::keepsWallForDelivery(true));
}

namespace
{
//! \brief A model map with a gem wall and two earth walls behind it; the Zivs stand at the gem wall.
DigRun gemCase(bool goldFirst, bool fixed, uint32_t zivs)
{
    DigRun run;
    run.treasuryX = 0;
    run.treasuryY = 0;
    run.goldFirst = goldFirst;
    run.fixed = fixed;
    run.goldMined = 0.0;
    addWall(run, WallKind::gem, 5, 0);
    addWall(run, WallKind::earth, 7, 0);
    addWall(run, WallKind::earth, 8, 0);
    for(uint32_t ziv = 0; ziv < zivs; ++ziv)
        addZiv(run, 5, 0);
    return run;
}
}

//! Checks gem walls, which never run out: with "gold first" on the Zivs stay on the gem wall and dig no earth wall,
//! as before; with it off a Ziv that stands at the gem wall digs the earth walls while it mines the gem wall, where
//! the rules of build 0.7.4.79 kept it on the gem wall for good.
BOOST_AUTO_TEST_CASE(test_gemWall)
{
    DigRun on = gemCase(true, true, 2);
    for(int32_t turn = 0; turn < 2000; ++turn)
        runTurn(on, turn);
    BOOST_CHECK(firstDug(on, WallKind::earth) < 0);
    BOOST_CHECK(on.goldMined > 0.0);

    DigRun before = gemCase(false, false, 1);
    for(int32_t turn = 0; turn < 2000; ++turn)
        runTurn(before, turn);
    BOOST_CHECK(firstDug(before, WallKind::earth) < 0);

    DigRun off = gemCase(false, true, 1);
    const int32_t turns = runUntilEarthDug(off);
    BOOST_CHECK(turns < 2000);
    BOOST_CHECK(off.goldMined > 0.0);
}

//! Checks the rank groups: with "gold first" off the kind of a wall never changes the group, an occupied wall ranks
//! after a free one, and a wall a load was carried away from ranks with the occupied ones only in the choice right
//! after a delivery; with it on gold and gem walls rank before all others as before.
BOOST_AUTO_TEST_CASE(test_groups)
{
    for(int occupied = 0; occupied < 2; ++occupied)
        for(int loadTaken = 0; loadTaken < 2; ++loadTaken)
            for(int afterDelivery = 0; afterDelivery < 2; ++afterDelivery)
                BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, true, occupied != 0, loadTaken != 0, afterDelivery != 0),
                    WorkerDigOrder::group(false, false, occupied != 0, loadTaken != 0, afterDelivery != 0));
    BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, true, false, false, false), 0);
    BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, true, true, false, false), 1);
    BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, true, false, true, false), 0);
    BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, true, false, true, true), 1);
    BOOST_CHECK_EQUAL(WorkerDigOrder::group(false, false, false, false, true), 0);
    // Gold first on: the groups of build 0.7.4.79
    for(int loadTaken = 0; loadTaken < 2; ++loadTaken)
        for(int afterDelivery = 0; afterDelivery < 2; ++afterDelivery)
        {
            BOOST_CHECK_EQUAL(WorkerDigOrder::group(true, true, false, loadTaken != 0, afterDelivery != 0), 0);
            BOOST_CHECK_EQUAL(WorkerDigOrder::group(true, true, true, loadTaken != 0, afterDelivery != 0), 1);
            BOOST_CHECK_EQUAL(WorkerDigOrder::group(true, false, false, loadTaken != 0, afterDelivery != 0), 2);
            BOOST_CHECK_EQUAL(WorkerDigOrder::group(true, false, true, loadTaken != 0, afterDelivery != 0), 3);
        }
}

//! Checks that the order inside the groups is the one of build 0.7.4.79: lower group, then the place the worker
//! stands on, then the nearer place; compared over all combinations with the former rank.
BOOST_AUTO_TEST_CASE(test_rankUnchanged)
{
    const float distances[3] = {0.0f, 1.0f, 4.0f};
    for(int haveBest = 0; haveBest < 2; ++haveBest)
        for(int group = 0; group < 4; ++group)
            for(int bestGroup = 0; bestGroup < 4; ++bestGroup)
                for(int here = 0; here < 2; ++here)
                    for(int bestHere = 0; bestHere < 2; ++bestHere)
                        for(int distance = 0; distance < 3; ++distance)
                            for(int bestDistance = 0; bestDistance < 3; ++bestDistance)
                                BOOST_CHECK_EQUAL(WorkerDigOrder::ranksBefore(haveBest != 0, group, here != 0,
                                    distances[distance], bestGroup, bestHere != 0, distances[bestDistance]),
                                    oldRanksBefore(haveBest != 0, group, here != 0, distances[distance], bestGroup,
                                    bestHere != 0, distances[bestDistance]));
}
