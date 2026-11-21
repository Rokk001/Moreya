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

#include "utils/RaidSimGoalPlayer.h"

#include "creatureaction/CreatureAction.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "game/SkillManager.h"
#include "gamemap/GameMap.h"
#include "gamemap/LevelScript.h"
#include "rooms/Room.h"
#include "rooms/RoomManager.h"
#include "rooms/RoomType.h"
#include "traps/Trap.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "ODApplication.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <utility>

namespace
{
//! \brief Game seconds between two looks of the player at the goals.
const double ACT_SECONDS = 3.0;
//! \brief Game seconds between two room builds of the same room type.
const double ROOM_BUILD_SECONDS = 30.0;
//! \brief Room tiles the player adds at once for a room goal (a square of 3 by 3 tiles where the ground allows).
const size_t ROOM_BLOCK_TILES = 9;
//! \brief How deep flag, trigger and objective conditions are followed to the triggers behind them.
const int32_t MAX_DEPTH = 8;
//! \brief Tiles around a spawn point of a spawncleared condition within which its enemies are searched.
const int32_t SPAWN_RADIUS = 10;
//! \brief Path cost of a tile that has to be dug, against 1 for a tile that can be walked on.
const int32_t DIG_COST = 3;
//! \brief Goal regions (not counting rooms and fights) the player digs towards at the same time.
const size_t DIG_TARGETS = 3;
//! \brief A fighter that stands this near (largest of the x and y distance) to a fight target is not carried there.
const int32_t NEAR_TARGET = 5;
//! \brief Tiles (largest of the x and y distance) around a standing enemy creature that the way of a dig or visit
//! target avoids and that no worker is dropped into, so that the workers are not sent into the enemies.
const int32_t ENEMY_AVOID = 4;

//! \brief A rectangle of tiles.
struct Rect
{
    int32_t mX1;
    int32_t mY1;
    int32_t mX2;
    int32_t mY2;
};

//! \brief One trigger of the level file as text: its name, mode and the words of its conditions and actions.
struct TriggerText
{
    std::string mName;
    bool mRepeat;
    std::vector<std::vector<std::string> > mConds;
    std::vector<std::vector<std::string> > mActions;
};

//! \brief What the player does for one condition that does not hold.
enum class TargetKind
{
    //! \brief A creature of the seat has to stand in the tiles (a worker is dropped there once the way is open).
    visit,
    //! \brief The tiles have to be claimed: the diggable ones are dug, the way there is dug.
    claim,
    //! \brief The gold of the tiles has to be mined.
    mine,
    //! \brief The way to the tiles has to be dug (a connection).
    reach,
    //! \brief Enemies, doors or a heart on the tiles have to be defeated: fighters are dropped next to them.
    fight,
    //! \brief Rooms of a type have to be built.
    room
};

//! \brief One target of the player.
struct Target
{
    TargetKind mKind;
    std::vector<Tile*> mTiles;
    RoomType mRoom;
    std::string mText;
};

std::vector<std::string> sGoals;
std::map<std::string, std::vector<std::vector<std::string> > > sGoalConds;
std::map<std::string, Rect> sRegions;
std::vector<TriggerText> sTriggers;
int32_t sSeatId = -1;
int64_t sLastActTurn = -1;
uint32_t sCarried = 0;
std::map<RoomType, int64_t> sLastRoomBuild;

//! \brief Splits a line at tabs and blanks.
std::vector<std::string> words(const std::string& line)
{
    std::vector<std::string> result;
    std::istringstream ss(line);
    std::string word;
    while(ss >> word)
        result.push_back(word);
    return result;
}

//! \brief Reads an integer word, false when it is none.
bool toInt(const std::string& text, int32_t& value)
{
    std::istringstream ss(text);
    return static_cast<bool>(ss >> value) && ss.eof();
}

//! \brief The trigger with that name, nullptr when there is none.
const TriggerText* findTrigger(const std::string& name)
{
    for(const TriggerText& trigger : sTriggers)
    {
        if(trigger.mName == name)
            return &trigger;
    }
    return nullptr;
}

//! \brief How often the trigger of the running level script fired (0 when it is not there).
uint32_t timesFired(const GameMap& gameMap, const std::string& name)
{
    for(const LevelScriptTrigger& trigger : gameMap.getLevelScript().getTriggers())
    {
        if(trigger.mName == name)
            return trigger.mTimesFired;
    }
    return 0;
}

//! \brief The rectangle of a named region, or of four coordinate words from index first; false when there is none.
bool readRect(const std::vector<std::string>& cond, size_t first, Rect& rect, bool namedOnly)
{
    if(first >= cond.size())
        return false;

    std::map<std::string, Rect>::const_iterator it = sRegions.find(cond[first]);
    if(it != sRegions.end())
    {
        rect = it->second;
        return true;
    }
    if(namedOnly || (first + 3 >= cond.size()))
        return false;

    return toInt(cond[first], rect.mX1) && toInt(cond[first + 1], rect.mY1) && toInt(cond[first + 2], rect.mX2) &&
        toInt(cond[first + 3], rect.mY2);
}

//! \brief The tiles of the rectangle that are on the map.
std::vector<Tile*> rectTiles(GameMap& gameMap, const Rect& rect)
{
    std::vector<Tile*> tiles;
    for(int32_t x = std::min(rect.mX1, rect.mX2); x <= std::max(rect.mX1, rect.mX2); ++x)
    {
        for(int32_t y = std::min(rect.mY1, rect.mY2); y <= std::max(rect.mY1, rect.mY2); ++y)
        {
            Tile* tile = gameMap.getTile(x, y);
            if(tile != nullptr)
                tiles.push_back(tile);
        }
    }
    return tiles;
}

//! \brief True when a living creature of the seat stands on one of the tiles.
bool ownCreatureOn(GameMap& gameMap, Seat* seat, const std::vector<Tile*>& tiles)
{
    std::set<Tile*> wanted(tiles.begin(), tiles.end());
    for(Creature* creature : gameMap.getCreaturesBySeat(seat))
    {
        if(creature->isAlive() && (wanted.count(creature->getPositionTile()) > 0))
            return true;
    }
    return false;
}

//! \brief True when every tile that is not a full tile is claimed by the seat (and there is one).
bool groundClaimed(Seat* seat, const std::vector<Tile*>& tiles)
{
    bool any = false;
    for(Tile* tile : tiles)
    {
        if(tile->isFullTile())
            continue;
        any = true;
        if(!tile->isClaimedForSeat(seat))
            return false;
    }
    return any;
}

//! \brief The number of tiles claimed by the seat.
int32_t countClaimed(Seat* seat, const std::vector<Tile*>& tiles)
{
    int32_t count = 0;
    for(Tile* tile : tiles)
    {
        if(tile->isClaimedForSeat(seat))
            ++count;
    }
    return count;
}

//! \brief The tiles of the living creatures of seats that are enemies of the seat (rogue creatures included) that stand
//! within radius of the centre, or anywhere with a negative radius.
std::vector<Tile*> enemyTiles(GameMap& gameMap, Seat* seat, Tile* centre, int32_t radius)
{
    std::vector<Tile*> tiles;
    for(Creature* creature : gameMap.getCreatures())
    {
        Tile* tile = creature->getPositionTile();
        if(!creature->isAlive() || (tile == nullptr) || (creature->getSeat() == nullptr) ||
           (creature->getSeat() == seat) || seat->isAlliedSeat(creature->getSeat()))
            continue;
        if((radius >= 0) && (centre != nullptr) &&
           (std::max(std::abs(tile->getX() - centre->getX()), std::abs(tile->getY() - centre->getY())) > radius))
            continue;
        tiles.push_back(tile);
    }
    return tiles;
}

//! \brief The tiles of the dungeon hearts of the seat with that id.
std::vector<Tile*> heartTiles(GameMap& gameMap, int32_t seatId)
{
    std::vector<Tile*> tiles;
    Seat* seat = gameMap.getSeatById(seatId);
    if(seat == nullptr)
        return tiles;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        for(Tile* tile : room->getCoveredTiles())
            tiles.push_back(tile);
    }
    return tiles;
}

//! \brief True when the current value of the flag passes the comparison of the flag condition (flag name value or flag
//! name op value). A comparison with another flag is taken as not holding.
bool flagHolds(const GameMap& gameMap, const std::vector<std::string>& cond)
{
    if(cond.size() < 3)
        return true;
    const int64_t current = gameMap.getLevelScript().getFlag(cond[1]);
    std::string op = "==";
    std::string valueText = cond[2];
    if(cond.size() >= 4)
    {
        op = cond[2];
        valueText = cond[3];
    }
    int32_t value = 0;
    if(!toInt(valueText, value))
        return false;
    if(op == "==")
        return current == value;
    if(op == "!=")
        return current != value;
    if(op == "<")
        return current < value;
    if(op == "<=")
        return current <= value;
    if(op == ">")
        return current > value;
    return current >= value;
}

//! \brief True when the room condition of the seat (furniture, roomtiles, roomsize, room) holds now.
bool roomCondHolds(GameMap& gameMap, Seat* seat, const std::vector<std::string>& cond, RoomType roomType)
{
    int64_t value = 0;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(roomType, seat))
    {
        if(cond[0] == "furniture")
            value += static_cast<int64_t>(room->getBuildingObjects().size());
        else if(cond[0] == "roomtiles")
            value += static_cast<int64_t>(room->getCoveredTiles().size());
        else if(cond[0] == "roomsize")
            value = std::max(value, static_cast<int64_t>(room->getCoveredTiles().size()));
        else
            ++value;
    }
    std::string op = ">=";
    std::string numberText = cond[3];
    if((cond[0] != "room") && (cond.size() >= 5))
    {
        op = cond[3];
        numberText = cond[4];
    }
    int32_t number = 0;
    if(!toInt(numberText, number))
        return true;
    if(op == "<=")
        return value <= number;
    if(op == "<")
        return value < number;
    if(op == ">")
        return value > number;
    if(op == "==")
        return value == number;
    return value >= number;
}

//! \brief Adds the targets of the conditions of the trigger (unless it fired already).
void expandConds(GameMap& gameMap, Seat* seat, const std::vector<std::vector<std::string> >& conds, int32_t depth,
    std::set<std::string>& seen, std::vector<Target>& out);

//! \brief Adds the target of one condition that does not hold, following flag, trigger and objective conditions to the
//! triggers behind them.
void expandCond(GameMap& gameMap, Seat* seat, const std::vector<std::string>& cond, int32_t depth,
    std::set<std::string>& seen, std::vector<Target>& out)
{
    if(cond.empty() || (depth > MAX_DEPTH))
        return;

    const std::string& type = cond[0];
    int32_t condSeat = sSeatId;
    if((cond.size() >= 2) && (type != "flag") && (type != "trigger") && (type != "event") && (type != "trapgone") &&
       (type != "spawncleared"))
        toInt(cond[1], condSeat);

    Target target;
    target.mKind = TargetKind::visit;
    target.mRoom = RoomType::nullRoomType;
    target.mText = type + (cond.size() >= 3 ? (" " + cond[2]) : std::string());
    Rect rect;
    if((type == "region") || (type == "crossed"))
    {
        if(((condSeat != sSeatId) && (condSeat != -1)) || !readRect(cond, 2, rect, false))
            return;
        target.mTiles = rectTiles(gameMap, rect);
        if(ownCreatureOn(gameMap, seat, target.mTiles) && (type == "region"))
            return;
        // A crossing needs the region claimed and walked through; a visit needs a creature in it
        target.mKind = (type == "crossed") ? TargetKind::claim : TargetKind::visit;
        out.push_back(target);
        return;
    }
    if((type == "claimed") || (type == "groundclaimed") || (type == "roomclaimed") || (type == "slabs"))
    {
        if((condSeat != sSeatId) || !readRect(cond, 2, rect, (type == "claimed") || (type == "slabs")))
            return;
        target.mTiles = rectTiles(gameMap, rect);
        target.mKind = TargetKind::claim;
        if((type == "claimed") && (cond.size() >= 4))
        {
            int32_t count = 0;
            if((cond[3] != "all") && toInt(cond[3], count) && (countClaimed(seat, target.mTiles) >= count))
                return;
            if((cond[3] == "all") && groundClaimed(seat, target.mTiles))
                return;
        }
        else if(((type == "groundclaimed") || (type == "roomclaimed")) && groundClaimed(seat, target.mTiles))
        {
            if(type == "groundclaimed")
                return;
            bool rooms = true;
            for(Tile* tile : target.mTiles)
            {
                Room* room = tile->getCoveringRoom();
                if(!tile->isFullTile() && ((room == nullptr) || (room->getSeat() != seat)))
                    rooms = false;
            }
            if(rooms)
                return;
        }
        out.push_back(target);
        return;
    }
    if(type == "minedregion")
    {
        if((condSeat != sSeatId) || !readRect(cond, 2, rect, true))
            return;
        target.mTiles = rectTiles(gameMap, rect);
        target.mKind = TargetKind::mine;
        out.push_back(target);
        return;
    }
    if(type == "groundconnected")
    {
        Rect points;
        if((condSeat != sSeatId) || !readRect(cond, 2, points, false))
            return;
        Tile* first = gameMap.getTile(points.mX1, points.mY1);
        Tile* second = gameMap.getTile(points.mX2, points.mY2);
        target.mKind = TargetKind::reach;
        if(first != nullptr)
            target.mTiles.push_back(first);
        if(second != nullptr)
            target.mTiles.push_back(second);
        out.push_back(target);
        return;
    }
    if(type == "attackedregion")
    {
        if((condSeat != sSeatId) || !readRect(cond, 3, rect, true))
            return;
        target.mTiles = rectTiles(gameMap, rect);
        target.mKind = TargetKind::fight;
        out.push_back(target);
        return;
    }
    if((type == "event") && (cond.size() >= 3) && ((cond[2] == "killed") || (cond[2] == "incapacitated")))
    {
        Creature* creature = gameMap.getCreature(cond[1]);
        if((creature == nullptr) || !creature->isAlive() || (creature->getPositionTile() == nullptr))
            return;
        target.mTiles.push_back(creature->getPositionTile());
        target.mKind = TargetKind::fight;
        target.mText = "kill " + cond[1];
        out.push_back(target);
        return;
    }
    if((type == "spawncleared") && (cond.size() >= 2))
    {
        const TriggerText* trigger = findTrigger(cond[1]);
        if(trigger == nullptr)
            return;
        if(timesFired(gameMap, trigger->mName) == 0)
        {
            if(seen.insert(trigger->mName).second)
                expandConds(gameMap, seat, trigger->mConds, depth + 1, seen, out);
            return;
        }
        // The spawn point: the action of that index, else the first spawn action
        int32_t index = -1;
        if(cond.size() >= 3)
            toInt(cond[2], index);
        const std::vector<std::string>* spawn = nullptr;
        if((index >= 0) && (static_cast<size_t>(index) < trigger->mActions.size()) &&
           (trigger->mActions[index].size() >= 4) && (trigger->mActions[index][0] == "spawn"))
            spawn = &trigger->mActions[index];
        for(size_t i = 0; (spawn == nullptr) && (i < trigger->mActions.size()); ++i)
        {
            if((trigger->mActions[i].size() >= 4) && (trigger->mActions[i][0] == "spawn"))
                spawn = &trigger->mActions[i];
        }
        int32_t x = 0;
        int32_t y = 0;
        if((spawn == nullptr) || !toInt((*spawn)[2], x) || !toInt((*spawn)[3], y))
            return;
        target.mTiles = enemyTiles(gameMap, seat, gameMap.getTile(x, y), SPAWN_RADIUS);
        target.mKind = TargetKind::fight;
        if(!target.mTiles.empty())
            out.push_back(target);
        return;
    }
    if((type == "trapgone") && (cond.size() >= 2))
    {
        Trap* trap = gameMap.getTrapByName(cond[1]);
        if(trap == nullptr)
            return;
        target.mTiles = trap->getCoveredTiles();
        target.mKind = TargetKind::fight;
        target.mText = "break " + cond[1];
        if(!target.mTiles.empty())
            out.push_back(target);
        return;
    }
    if(((type == "roomtiles") || (type == "roomsize") || (type == "furniture") || (type == "room")) &&
       (cond.size() >= 4))
    {
        const RoomType roomType = RoomManager::getRoomTypeFromRoomName(cond[2]);
        if(condSeat != sSeatId)
        {
            // A rival heart that has to go
            if((roomType == RoomType::dungeonTemple) && (cond[3] == "<="))
            {
                target.mTiles = heartTiles(gameMap, condSeat);
                target.mKind = TargetKind::fight;
                target.mText = "heart of seat " + cond[1];
                if(!target.mTiles.empty())
                    out.push_back(target);
            }
            return;
        }
        if((roomType == RoomType::nullRoomType) || (roomType == RoomType::dungeonTemple) ||
           roomCondHolds(gameMap, seat, cond, roomType))
            return;
        target.mKind = TargetKind::room;
        target.mRoom = roomType;
        out.push_back(target);
        return;
    }
    if((type == "defeated") && (cond.size() >= 2) && (condSeat != sSeatId))
    {
        target.mTiles = heartTiles(gameMap, condSeat);
        target.mKind = TargetKind::fight;
        target.mText = "defeat seat " + cond[1];
        if(!target.mTiles.empty())
            out.push_back(target);
        return;
    }
    if((type == "goalmet") && (cond.size() >= 3) && (cond[2] == "KillAllEnemies"))
    {
        target.mTiles = enemyTiles(gameMap, seat, nullptr, -1);
        target.mKind = TargetKind::fight;
        target.mText = "kill all enemies";
        if(!target.mTiles.empty())
            out.push_back(target);
        return;
    }
    if(type == "flag")
    {
        if(flagHolds(gameMap, cond))
            return;
        // The first trigger that sets the flag and did not fire yet
        for(const TriggerText& trigger : sTriggers)
        {
            bool sets = false;
            for(const std::vector<std::string>& action : trigger.mActions)
            {
                if((action.size() >= 2) && ((action[0] == "setflag") || (action[0] == "addflag")) &&
                   (action[1] == cond[1]))
                    sets = true;
            }
            if(!sets || (!trigger.mRepeat && (timesFired(gameMap, trigger.mName) > 0)))
                continue;
            if(seen.insert(trigger.mName).second)
                expandConds(gameMap, seat, trigger.mConds, depth + 1, seen, out);
            return;
        }
        return;
    }
    if((type == "trigger") && (cond.size() >= 2))
    {
        if(((cond.size() >= 3) && (cond[2] == "0")) || (timesFired(gameMap, cond[1]) > 0))
            return;
        const TriggerText* trigger = findTrigger(cond[1]);
        if((trigger != nullptr) && seen.insert(trigger->mName).second)
            expandConds(gameMap, seat, trigger->mConds, depth + 1, seen, out);
        return;
    }
    if((type == "objective") && (cond.size() >= 4) && (cond[3] == "reached"))
    {
        if(gameMap.getLevelScript().getObjectiveState(sSeatId, cond[2]) == LevelScriptObjectiveState::reached)
            return;
        std::map<std::string, std::vector<std::vector<std::string> > >::const_iterator it = sGoalConds.find(cond[2]);
        if((it != sGoalConds.end()) && seen.insert("objective " + cond[2]).second)
            expandConds(gameMap, seat, it->second, depth + 1, seen, out);
        return;
    }
}

void expandConds(GameMap& gameMap, Seat* seat, const std::vector<std::vector<std::string> >& conds, int32_t depth,
    std::set<std::string>& seen, std::vector<Target>& out)
{
    for(const std::vector<std::string>& cond : conds)
        expandCond(gameMap, seat, cond, depth, seen, out);
}

//! \brief The targets of every goal that is not reached, goal after goal in the order of the level.
std::vector<Target> openTargets(GameMap& gameMap, Seat* seat)
{
    std::vector<Target> out;
    std::set<std::string> seen;
    for(const std::string& goal : sGoals)
    {
        if(gameMap.getLevelScript().getObjectiveState(sSeatId, goal) == LevelScriptObjectiveState::reached)
            continue;
        std::map<std::string, std::vector<std::vector<std::string> > >::const_iterator it = sGoalConds.find(goal);
        if(it != sGoalConds.end())
            expandConds(gameMap, seat, it->second, 0, seen, out);
    }
    return out;
}

//! \brief The cheapest way from the tiles a worker of the seat reaches on claimed ground to one of the target tiles:
//! walking costs 1 per tile, a tile that has to be dug DIG_COST. Returns the tiles of the way (target included,
//! start excluded); empty when there is no way or a target tile is reached already.
std::vector<Tile*> findWay(GameMap& gameMap, Seat* seat, Creature* worker, const std::vector<Tile*>& targets,
    const std::set<Tile*>& avoid)
{
    std::vector<Tile*> way;
    if((worker == nullptr) || targets.empty())
        return way;

    std::set<Tile*> wanted(targets.begin(), targets.end());
    typedef std::pair<int32_t, Tile*> Entry;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry> > open;
    std::map<Tile*, int32_t> cost;
    std::map<Tile*, Tile*> from;
    for(int32_t x = 0; x < gameMap.getMapSizeX(); ++x)
    {
        for(int32_t y = 0; y < gameMap.getMapSizeY(); ++y)
        {
            Tile* tile = gameMap.getTile(x, y);
            if((tile != nullptr) && tile->isClaimedForSeat(seat) && worker->canGoThroughTile(tile))
            {
                if(wanted.count(tile) > 0)
                    return way;
                cost[tile] = 0;
                open.push(Entry(0, tile));
            }
        }
    }

    Tile* found = nullptr;
    while(!open.empty())
    {
        Entry entry = open.top();
        open.pop();
        if(entry.first > cost[entry.second])
            continue;
        if(wanted.count(entry.second) > 0)
        {
            found = entry.second;
            break;
        }
        // A tile that has to be dug leads on only to further tiles (the way goes through it once it is dug)
        for(Tile* neighbor : entry.second->getAllNeighbors())
        {
            if((neighbor == nullptr) || (avoid.count(neighbor) > 0))
                continue;
            int32_t step = 0;
            if(worker->canGoThroughTile(neighbor))
                step = 1;
            else if(neighbor->isDiggable(seat))
                step = DIG_COST;
            else if(wanted.count(neighbor) > 0)
                step = DIG_COST;
            else
                continue;
            const int32_t next = entry.first + step;
            std::map<Tile*, int32_t>::iterator it = cost.find(neighbor);
            if((it != cost.end()) && (it->second <= next))
                continue;
            cost[neighbor] = next;
            from[neighbor] = entry.second;
            open.push(Entry(next, neighbor));
        }
    }
    for(Tile* tile = found; (tile != nullptr) && (cost[tile] > 0); tile = from[tile])
        way.push_back(tile);
    return way;
}

//! \brief Marks the tiles that have to be dug for digging by the player (nothing when none).
void markDiggable(Player* keeper, const std::vector<Tile*>& tiles, bool goldOnly)
{
    std::vector<Tile*> marked;
    for(Tile* tile : tiles)
    {
        if(!tile->isDiggable(keeper->getSeat()) || tile->getMarkedForDigging(keeper))
            continue;
        if(goldOnly && (tile->getType() != TileType::gold))
            continue;
        marked.push_back(tile);
    }
    if(!marked.empty())
        keeper->markTilesForDigging(true, marked, true);
}

//! \brief True when no tile of the way has to be dug any more.
bool wayIsOpen(Creature* worker, const std::vector<Tile*>& way, const std::vector<Tile*>& targets)
{
    std::set<Tile*> wanted(targets.begin(), targets.end());
    for(Tile* tile : way)
    {
        if(!worker->canGoThroughTile(tile) && (wanted.count(tile) == 0))
            return false;
    }
    return true;
}

//! \brief The tiles within ENEMY_AVOID of a standing enemy creature of the seat (rogue creatures included).
std::set<Tile*> enemyZone(GameMap& gameMap, Seat* seat)
{
    std::set<Tile*> zone;
    for(Tile* tile : enemyTiles(gameMap, seat, nullptr, -1))
    {
        for(int32_t dx = -ENEMY_AVOID; dx <= ENEMY_AVOID; ++dx)
        {
            for(int32_t dy = -ENEMY_AVOID; dy <= ENEMY_AVOID; ++dy)
            {
                Tile* near = gameMap.getTile(tile->getX() + dx, tile->getY() + dy);
                if(near != nullptr)
                    zone.insert(near);
            }
        }
    }
    return zone;
}

//! \brief The claimed tile of the seat a worker can walk on (where the player can drop a creature) outside the avoided
//! tiles that lies nearest to one of the target tiles, nullptr when there is none.
Tile* dropTileNear(GameMap& gameMap, Player* keeper, Creature* worker, const std::vector<Tile*>& targets,
    const std::set<Tile*>& avoid)
{
    Tile* best = nullptr;
    int32_t bestDistance = -1;
    for(int32_t x = 0; x < gameMap.getMapSizeX(); ++x)
    {
        for(int32_t y = 0; y < gameMap.getMapSizeY(); ++y)
        {
            Tile* tile = gameMap.getTile(x, y);
            if((tile == nullptr) || !tile->isClaimedForSeat(keeper->getSeat()))
                continue;
            int32_t distance = -1;
            for(Tile* target : targets)
            {
                const int32_t d = std::max(std::abs(tile->getX() - target->getX()), std::abs(tile->getY() - target->getY()));
                if((distance < 0) || (d < distance))
                    distance = d;
            }
            if((bestDistance >= 0) && (distance >= bestDistance))
                continue;
            if(!worker->canGoThroughTile(tile) || (avoid.count(tile) > 0))
                continue;
            best = tile;
            bestDistance = distance;
        }
    }
    return best;
}

//! \brief Picks up a creature of the seat (a fighter, or a worker when worker is true) that stands away from the
//! targets and drops it on the tile. Returns true when it was dropped.
bool carry(GameMap& gameMap, Player* keeper, const std::vector<Tile*>& targets, Tile* dropTile, bool worker)
{
    Seat* seat = keeper->getSeat();
    Creature* chosen = nullptr;
    for(Creature* creature : gameMap.getCreaturesBySeat(seat))
    {
        Tile* tile = creature->getPositionTile();
        if((tile == nullptr) || !creature->isAlive() || creature->isKo() ||
           (creature->getDefinition()->isWorker() != worker) || creature->isActionInList(CreatureActionType::fight))
            continue;
        bool near = false;
        for(Tile* target : targets)
        {
            if(std::max(std::abs(tile->getX() - target->getX()), std::abs(tile->getY() - target->getY())) <= NEAR_TARGET)
                near = true;
        }
        if(near || !keeper->isHandLimitPickupAllowed(creature) || !creature->tryPickup(seat))
            continue;
        if((chosen == nullptr) || (creature->getLevel() > chosen->getLevel()))
            chosen = creature;
    }
    if(chosen == nullptr)
        return false;

    Tile* origin = chosen->getPositionTile();
    keeper->pickUpEntity(chosen);
    if(keeper->numObjectsInHand() == 0)
        return false;
    ++sCarried;
    // Where the creature cannot be dropped it goes back where it was picked up
    if(keeper->isDropHandPossible(dropTile))
        keeper->dropHand(dropTile);
    else if(keeper->isDropHandPossible(origin))
        keeper->dropHand(origin);
    return true;
}

//! \brief Builds ROOM_BLOCK_TILES tiles (or fewer) of the room on buildable claimed tiles nearest the dungeon heart,
//! when the room is available and ROOM_BUILD_SECONDS passed since the last build of that type.
void buildRoom(GameMap& gameMap, Player* keeper, RoomType type)
{
    Seat* seat = keeper->getSeat();
    const int64_t turn = gameMap.getTurnNumber();
    std::map<RoomType, int64_t>::iterator last = sLastRoomBuild.find(type);
    if((last != sLastRoomBuild.end()) &&
       (static_cast<double>(turn - last->second) < ROOM_BUILD_SECONDS * ODApplication::turnsPerSecond))
        return;
    if(!SkillManager::isRoomAvailable(type, seat))
        return;

    std::vector<Tile*> hearts = heartTiles(gameMap, seat->getId());
    if(hearts.empty())
        return;
    // Breadth-first from the heart over claimed ground; the first square of 3 by 3 buildable tiles, else the nearest
    // buildable tiles
    std::vector<Tile*> frontier = hearts;
    std::set<Tile*> seen(hearts.begin(), hearts.end());
    std::vector<Tile*> buildable;
    while(!frontier.empty() && (buildable.size() < 200))
    {
        std::vector<Tile*> next;
        for(Tile* tile : frontier)
        {
            for(Tile* neighbor : tile->getAllNeighbors())
            {
                if((neighbor == nullptr) || !seen.insert(neighbor).second || !neighbor->isClaimedForSeat(seat))
                    continue;
                next.push_back(neighbor);
                if(neighbor->isBuildableUpon(seat))
                    buildable.push_back(neighbor);
            }
        }
        frontier.swap(next);
    }
    std::vector<Tile*> chosen;
    for(Tile* corner : buildable)
    {
        std::vector<Tile*> square;
        for(int32_t dx = 0; dx < 3; ++dx)
        {
            for(int32_t dy = 0; dy < 3; ++dy)
            {
                Tile* tile = gameMap.getTile(corner->getX() + dx, corner->getY() + dy);
                if((tile != nullptr) && tile->isClaimedForSeat(seat) && tile->isBuildableUpon(seat))
                    square.push_back(tile);
            }
        }
        if(square.size() == ROOM_BLOCK_TILES)
        {
            chosen = square;
            break;
        }
    }
    if(chosen.empty())
    {
        for(size_t i = 0; (i < buildable.size()) && (chosen.size() < ROOM_BLOCK_TILES); ++i)
            chosen.push_back(buildable[i]);
    }
    if(chosen.empty())
        return;
    sLastRoomBuild[type] = turn;
    RoomManager::buildRoomOnTiles(&gameMap, type, keeper, chosen, false);
}
}

namespace RaidSimGoalPlayer
{
//! \brief Reads regions and triggers of the [Triggers] section, then the goals of the seat and the conditions of the
//! first trigger that sets each of them reached.
void load(const std::string& levelFile, int32_t seatId)
{
    sGoals.clear();
    sGoalConds.clear();
    sRegions.clear();
    sTriggers.clear();
    sLastRoomBuild.clear();
    sLastActTurn = -1;
    sCarried = 0;
    sSeatId = seatId;

    std::ifstream level(levelFile.c_str());
    std::string line;
    bool inTriggers = false;
    TriggerText* current = nullptr;
    while(std::getline(level, line))
    {
        std::vector<std::string> fields = words(line);
        if(fields.empty())
            continue;
        if(fields[0] == "[Triggers]")
            inTriggers = true;
        else if(fields[0] == "[/Triggers]")
            inTriggers = false;
        if(!inTriggers)
            continue;
        if((fields[0] == "Region") && (fields.size() >= 6))
        {
            Rect rect;
            if(toInt(fields[2], rect.mX1) && toInt(fields[3], rect.mY1) && toInt(fields[4], rect.mX2) &&
               toInt(fields[5], rect.mY2))
                sRegions[fields[1]] = rect;
        }
        else if(fields[0] == "[Trigger]")
        {
            sTriggers.push_back(TriggerText());
            current = &sTriggers.back();
            current->mRepeat = false;
        }
        else if(fields[0] == "[/Trigger]")
            current = nullptr;
        else if(current != nullptr)
        {
            std::vector<std::string> rest(fields.begin() + 1, fields.end());
            if((fields[0] == "Name") && !rest.empty())
                current->mName = rest[0];
            else if((fields[0] == "Mode") && !rest.empty())
                current->mRepeat = (rest[0] == "repeat");
            else if(fields[0] == "Cond")
                current->mConds.push_back(rest);
            else if(fields[0] == "Action")
                current->mActions.push_back(rest);
        }
    }

    const std::string raidSuffix = "-raid";
    for(const TriggerText& trigger : sTriggers)
    {
        for(const std::vector<std::string>& action : trigger.mActions)
        {
            int32_t goalSeat = -1;
            if((action.size() < 3) || ((action[0] != "mainobjectiveid") && (action[0] != "optionalobjectiveid")) ||
               !toInt(action[1], goalSeat) || ((goalSeat != seatId) && (goalSeat != -1)))
                continue;
            const std::string& id = action[2];
            if((id.size() >= raidSuffix.size()) &&
               (id.compare(id.size() - raidSuffix.size(), raidSuffix.size(), raidSuffix) == 0))
                continue;
            if(std::find(sGoals.begin(), sGoals.end(), id) == sGoals.end())
                sGoals.push_back(id);
        }
    }
    for(const std::string& goal : sGoals)
    {
        for(const TriggerText& trigger : sTriggers)
        {
            bool sets = false;
            for(const std::vector<std::string>& action : trigger.mActions)
            {
                if((action.size() >= 4) && (action[0] == "objectivestate") && (action[2] == goal) &&
                   (action[3] == "reached"))
                    sets = true;
            }
            if(sets && (sGoalConds.count(goal) == 0))
                sGoalConds[goal] = trigger.mConds;
        }
    }
}

const std::vector<std::string>& getGoals()
{
    return sGoals;
}

uint32_t getCarried()
{
    return sCarried;
}

//! \brief Counts the goals in state reached.
uint32_t countReached(const GameMap& gameMap, int32_t seatId)
{
    uint32_t reached = 0;
    for(const std::string& goal : sGoals)
    {
        if(gameMap.getLevelScript().getObjectiveState(seatId, goal) == LevelScriptObjectiveState::reached)
            ++reached;
    }
    return reached;
}

//! \brief Every ACT_SECONDS: builds the rooms the open goals ask for, digs the way to the first DIG_TARGETS goal
//! regions (and the tiles to claim or mine in them), then uses the hand once: a fighter dropped next to the first fight
//! target that is open to walk, else a worker dropped next to the first region to visit that is open to walk.
void act(GameMap& gameMap, Player* keeper)
{
    if((keeper == nullptr) || (keeper->getSeat() == nullptr) || keeper->getHasLost() || sGoals.empty())
        return;
    const int64_t turn = gameMap.getTurnNumber();
    if((sLastActTurn >= 0) && (static_cast<double>(turn - sLastActTurn) < ACT_SECONDS * ODApplication::turnsPerSecond))
        return;
    sLastActTurn = turn;

    Seat* seat = keeper->getSeat();
    Creature* worker = gameMap.getWorkerForPathFinding(seat);
    std::vector<Target> targets = openTargets(gameMap, seat);
    const std::set<Tile*> zone = enemyZone(gameMap, seat);
    const std::set<Tile*> none;
    size_t digs = 0;
    bool handUsed = (keeper->numObjectsInHand() > 0);
    for(Target& target : targets)
    {
        if(target.mKind == TargetKind::room)
        {
            buildRoom(gameMap, keeper, target.mRoom);
            continue;
        }
        if(target.mTiles.empty() || (worker == nullptr))
            continue;

        // The way to a fight leads to the enemies; every other way keeps the workers away from them
        const bool fight = (target.mKind == TargetKind::fight);
        std::vector<Tile*> way;
        if(digs < DIG_TARGETS)
        {
            way = findWay(gameMap, seat, worker, target.mTiles, fight ? none : zone);
            markDiggable(keeper, way, false);
            if(target.mKind == TargetKind::claim)
                markDiggable(keeper, target.mTiles, false);
            else if(target.mKind == TargetKind::mine)
                markDiggable(keeper, target.mTiles, true);
            ++digs;
        }
        if(handUsed || ((target.mKind != TargetKind::fight) && (target.mKind != TargetKind::visit)))
            continue;
        if(!wayIsOpen(worker, way, target.mTiles))
            continue;
        // A worker visits a region only away from the enemies; a fighter is dropped next to them
        Tile* dropTile = dropTileNear(gameMap, keeper, worker, target.mTiles, fight ? none : zone);
        if(dropTile == nullptr)
            continue;
        handUsed = carry(gameMap, keeper, target.mTiles, dropTile, !fight);
    }
}

//! \brief Gold, room tiles per type and creatures per class of the seat.
std::string describeKeeper(GameMap& gameMap, int32_t seatId)
{
    Seat* seat = gameMap.getSeatById(seatId);
    if(seat == nullptr)
        return std::string();
    std::map<std::string, uint32_t> rooms;
    double gold = 0.0;
    for(Room* room : gameMap.getRooms())
    {
        if(room->getSeat() == seat)
            gold += room->getTotalGoldStored();
        if(room->getSeat() == seat)
            rooms[RoomManager::getRoomNameFromRoomType(room->getType())] +=
                static_cast<uint32_t>(room->getCoveredTiles().size());
    }
    std::map<std::string, uint32_t> creatures;
    for(Creature* creature : gameMap.getCreaturesBySeat(seat))
    {
        if(creature->isAlive())
            ++creatures[creature->getDefinition()->getClassName()];
    }
    std::string text = "gold=" + Helper::toString(gold) + " rooms=";
    for(const std::pair<const std::string, uint32_t>& room : rooms)
        text += room.first + ":" + Helper::toString(room.second) + ",";
    text += " creatures=";
    for(const std::pair<const std::string, uint32_t>& creature : creatures)
        text += creature.first + ":" + Helper::toString(creature.second) + ",";
    return text;
}

//! \brief For every goal not reached: its id and the texts of its targets now.
std::string describeOpenGoals(GameMap& gameMap, int32_t seatId)
{
    std::string text;
    Seat* seat = gameMap.getSeatById(seatId);
    if(seat == nullptr)
        return text;
    for(const std::string& goal : sGoals)
    {
        if(gameMap.getLevelScript().getObjectiveState(seatId, goal) == LevelScriptObjectiveState::reached)
            continue;
        std::vector<Target> targets;
        std::set<std::string> seen;
        std::map<std::string, std::vector<std::vector<std::string> > >::const_iterator it = sGoalConds.find(goal);
        if(it != sGoalConds.end())
            expandConds(gameMap, seat, it->second, 0, seen, targets);
        text += " " + goal + "[";
        for(size_t i = 0; i < targets.size(); ++i)
            text += (i > 0 ? "," : "") + targets[i].mText;
        text += "]";
    }
    return text;
}
}
