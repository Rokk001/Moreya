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

#include "game/RaidManager.h"

#include "creatureaction/CreatureAction.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntityType.h"
#include "entities/ItemBagEntity.h"
#include "entities/ItemInstance.h"
#include "entities/Tile.h"
#include "game/Campaign.h"
#include "game/CombatGroupManager.h"
#include "game/ItemDrops.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/LevelScript.h"
#include "gamemap/LevelScriptRunner.h"
#include "network/ODServer.h"
#include "network/ServerNotification.h"
#include "rooms/Room.h"
#include "rooms/RoomPortalWave.h"
#include "rooms/RoomType.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "ODApplication.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <istream>
#include <memory>
#include <ostream>
#include <sstream>

namespace
{
//! \brief Written instead of an empty name or a value the level leaves to the config in the [Raid] section.
const std::string NO_VALUE = "-";

//! \brief Returns the text, "-" for an empty one.
std::string textOrDash(const std::string& text)
{
    return text.empty() ? NO_VALUE : text;
}

//! \brief Returns the text read from the section, empty for "-".
std::string dashToEmpty(const std::string& token)
{
    return (token == NO_VALUE) ? std::string() : token;
}

//! \brief Reads a number of the section; "-" gives -1 (the config value applies).
bool parseOptionalNumber(const std::string& token, double& value)
{
    if(token == NO_VALUE)
    {
        value = -1.0;
        return true;
    }

    std::stringstream ss(token);
    double number = 0.0;
    if(!(ss >> number))
        return false;

    value = number;
    return true;
}

//! \brief Writes a number of the section; a negative value (the config value applies) is written as "-".
std::string optionalNumberText(double value)
{
    if(value < 0.0)
        return NO_VALUE;

    std::ostringstream ss;
    ss.precision(17);
    ss << value;
    return ss.str();
}

//! \brief Returns a number of the [Raid] block of global.cfg.
double raidConfig(const std::string& key)
{
    return ConfigManager::getSingleton().getRaidConfigDouble(key);
}

//! \brief The distance between two tiles in tiles: the largest of the x and y distance.
int32_t tileDistance(const Tile& first, const Tile& second)
{
    return std::max(std::abs(first.getX() - second.getX()), std::abs(first.getY() - second.getY()));
}

//! \brief The tiles of the candidates the creature reaches from its tile in at most maxSteps steps from tile to
//! neighbour tile over tiles it can walk on (a breadth-first search: walls, earth and lava without a bridge stop it).
std::vector<Tile*> reachableWithin(const Creature& creature, Tile* start, const std::set<Tile*>& candidates,
    int32_t maxSteps)
{
    std::vector<Tile*> reached;
    if((start == nullptr) || candidates.empty() || (maxSteps < 0))
        return reached;

    std::set<Tile*> seen;
    std::vector<Tile*> frontier(1, start);
    seen.insert(start);
    for(int32_t step = 0; !frontier.empty(); ++step)
    {
        std::vector<Tile*> next;
        for(Tile* tile : frontier)
        {
            if(candidates.count(tile) > 0)
                reached.push_back(tile);

            if(step >= maxSteps)
                continue;

            for(Tile* neighbor : tile->getAllNeighbors())
            {
                if((neighbor == nullptr) || (seen.count(neighbor) > 0) || !creature.canGoThroughTile(neighbor))
                    continue;

                seen.insert(neighbor);
                next.push_back(neighbor);
            }
        }
        frontier.swap(next);
    }
    return reached;
}
}

//! \brief Creates the manager of the map without a raid.
RaidManager::RaidManager(GameMap& gameMap) :
    mGameMap(gameMap),
    mHasGate(false),
    mGateX(0),
    mGateY(0),
    mGateRotation(0.0),
    mRaidSeatId(0),
    mTargetSeatId(-1),
    mCountdownSeconds(-1.0),
    mIntervalSeconds(-1.0),
    mEscapeShare(-1.0),
    mStarted(false),
    mLost(false),
    mGateShown(false),
    mBonusLogged(false)
{
}

//! \brief Forgets the level data, the running state (followers, escaped members and loot included) and the transient
//! state.
void RaidManager::clear()
{
    mHasGate = false;
    mGateX = 0;
    mGateY = 0;
    mGateRotation = 0.0;
    mRaidSeatId = 0;
    mTargetSeatId = -1;
    mCountdownSeconds = -1.0;
    mIntervalSeconds = -1.0;
    mEscapeShare = -1.0;
    mGroups.clear();
    mStarted = false;
    mSchedule = RaidRules::Schedule();
    mLost = false;
    mPlundered.clear();
    mLoot.clear();
    mGateShown = false;
    mBonusLogged = false;
}

//! \brief The countdown of the level, else RaidCountdownSeconds.
double RaidManager::countdownSeconds() const
{
    return (mCountdownSeconds >= 0.0) ? mCountdownSeconds : raidConfig("RaidCountdownSeconds");
}

//! \brief The interval of the level, else RaidWaveIntervalSeconds.
double RaidManager::intervalSeconds() const
{
    return (mIntervalSeconds >= 0.0) ? mIntervalSeconds : raidConfig("RaidWaveIntervalSeconds");
}

//! \brief The escape share of the level, else RaidLeaderEscapeShare.
double RaidManager::escapeShare() const
{
    return (mEscapeShare >= 0.0) ? mEscapeShare : raidConfig("RaidLeaderEscapeShare");
}

//! \brief Runs the raid for one turn: gate, countdown, arrivals, loot bags, plundering and the leaders with their
//! followers.
void RaidManager::update()
{
    if(!mHasGate || !mGameMap.isServerGameMap())
        return;

    // A campaign bonus level has no raid
    if(Campaign::getSingleton().isPlayedLevelBonus())
    {
        if(!mBonusLogged)
        {
            OD_LOG_WRN("The level has a [Raid] section but is a campaign bonus level: no raid comes");
            mBonusLogged = true;
        }
        return;
    }

    if(!mStarted)
    {
        RaidRules::start(mSchedule, static_cast<uint32_t>(mGroups.size()), countdownSeconds());
        mStarted = true;
        OD_LOG_INF("Raid countdown starts: " + Helper::toString(mSchedule.mSecondsToNext) + " s, groups="
            + Helper::toString(static_cast<uint32_t>(mGroups.size())));
    }

    if(!mGateShown)
    {
        setUpGate();
        // The first turn of a level or of a loaded game: the creatures of a saved flight exist now and run again
        restoreFlightSpeed();
    }

    if(!mLost)
        advanceSchedule(1.0 / ODApplication::turnsPerSecond);

    forgetMissingLoot();
    plunder();
    updateLeaders();
}

//! \brief Lets the seconds pass on the schedule; a group whose countdown ended comes through the gate, and the
//! portcullis sinks when the gate opens.
void RaidManager::advanceSchedule(double seconds)
{
    const bool wasOpen = mSchedule.mGateOpen;
    if(RaidRules::advance(mSchedule, seconds, intervalSeconds()))
        spawnGroup(mSchedule.mNextGroup - 1);

    if(!wasOpen && mSchedule.mGateOpen)
    {
        RoomPortalWave* gate = getGateRoom();
        if(gate != nullptr)
            gate->setMoreyaGateOpen(true, raidConfig("RaidGatePortcullisSink"));
    }
}

//! \brief Only the attacked keeper (or the level script) may open the gate, and only while it is closed.
bool RaidManager::openGateEarly(int32_t seatId)
{
    if(!mHasGate || mLost || Campaign::getSingleton().isPlayedLevelBonus())
        return false;

    if((seatId >= 0) && (mTargetSeatId >= 0) && (seatId != mTargetSeatId))
    {
        OD_LOG_WRN("Seat " + Helper::toString(seatId) + " may not open the gate of the raid against seat "
            + Helper::toString(mTargetSeatId));
        return false;
    }

    if(!mStarted)
    {
        RaidRules::start(mSchedule, static_cast<uint32_t>(mGroups.size()), countdownSeconds());
        mStarted = true;
    }

    if(!RaidRules::openEarly(mSchedule))
        return false;

    OD_LOG_INF("The Moreya gate is opened early by seat " + Helper::toString(seatId));
    // The raid comes at once
    advanceSchedule(0.0);
    return true;
}

//! \brief Sets the countdown of the waiting group, starting the schedule first when it did not start yet.
void RaidManager::setSecondsToNextGroup(double seconds)
{
    if(!mHasGate)
        return;

    if(!mStarted)
    {
        RaidRules::start(mSchedule, static_cast<uint32_t>(mGroups.size()), countdownSeconds());
        mStarted = true;
    }
    RaidRules::setSecondsToNext(mSchedule, seconds);
}

//! \brief The countdown of the HUD; before the first update the countdown of the level start.
int32_t RaidManager::getCountdownToShow() const
{
    if(!mHasGate || mLost || mGroups.empty() || Campaign::getSingleton().isPlayedLevelBonus())
        return -1;

    if(!mStarted)
        return static_cast<int32_t>(std::ceil(std::max(0.0, countdownSeconds())));

    return RaidRules::displaySeconds(mSchedule);
}

//! \brief The gate is closed until the first group comes.
bool RaidManager::isGateClosed() const
{
    return !mSchedule.mGateOpen;
}

//! \brief Looks for a fleeing leader with that name, or a follower of a leader who fled that did not escape yet.
bool RaidManager::isEscaping(const std::string& creatureName) const
{
    for(const RaidGroupData& group : mGroups)
    {
        if((group.mLeaderState == RaidLeaderState::fleeing) && (group.mLeaderSpawned == creatureName))
            return true;

        if((std::find(group.mFollowers.begin(), group.mFollowers.end(), creatureName) != group.mFollowers.end()) &&
           (std::find(group.mEscapedMembers.begin(), group.mEscapedMembers.end(), creatureName) ==
            group.mEscapedMembers.end()))
            return true;
    }
    return false;
}

//! \brief Finds the raid group whose arrived members include the creature.
const RaidGroupData* RaidManager::findGroupOfSpawned(const std::string& creatureName) const
{
    for(const RaidGroupData& group : mGroups)
    {
        if(std::find(group.mSpawned.begin(), group.mSpawned.end(), creatureName) != group.mSpawned.end())
            return &group;
    }
    return nullptr;
}

//! \brief A fleeing leader and his followers run to the gate; the leader of a group loots a dropped item he sees,
//! turns aside to a treasury on the way that he did not plunder yet, else walks to the dungeon heart of the attacked
//! keeper as the killplayer order does.
bool RaidManager::doCreatureOrder(Creature& creature)
{
    if(!mHasGate || !creature.getIsOnServerMap())
        return false;

    const std::string& name = creature.getName();
    if(findGroupOfSpawned(name) == nullptr)
        return false;

    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
        return false;

    if(isEscaping(name))
    {
        // The flight ends at the gate (update); until then the leader and his followers run there and do nothing else
        if(isAtGate(creature))
            return true;

        std::vector<Tile*> gateTiles;
        RoomPortalWave* gate = getGateRoom();
        if(gate != nullptr)
            gateTiles = gate->getCoveredTiles();
        Tile* gateTile = mGameMap.getTile(mGateX, mGateY);
        if(gateTiles.empty() && (gateTile != nullptr))
            gateTiles.push_back(gateTile);

        if(!LevelScriptRunner::walkToNearestTile(creature, gateTiles))
            OD_LOG_WRN("Fleeing raid member " + name + " finds no way to the gate");

        return true;
    }

    // The members keep their place in the formation of their raid group; its leader leads them
    if(mGameMap.getCombatGroups().shouldKeepFormation(creature))
        return false;

    // RA12: the leader loots the items fallen keeper creatures dropped, as his members do in the formation
    if(doLoot(creature))
        return true;

    if(mTargetSeatId < 0)
        return false;

    // A treasury holding gold that lies on the way and that the leader did not plunder yet: he reaches one of its
    // tiles within RaidPlunderDetourTiles steps over walkable tiles (a treasury behind a wall or earth is not on the
    // way, however near it is). The x and y distance only sorts out the tiles that are too far for any walk.
    const double detour = raidConfig("RaidPlunderDetourTiles");
    std::set<Tile*> nearTiles;
    for(Room* room : plunderableRooms())
    {
        if(mPlundered.count(std::make_pair(name, room->getName())) > 0)
            continue;

        for(Tile* tile : room->getCoveredTiles())
        {
            if(static_cast<double>(tileDistance(*myTile, *tile)) <= detour)
                nearTiles.insert(tile);
        }
    }
    const std::vector<Tile*> plunderTiles = reachableWithin(creature, myTile, nearTiles,
        static_cast<int32_t>(std::floor(detour)));
    if(!plunderTiles.empty())
    {
        // Standing in it, the leader plunders it at the next update
        if(std::find(plunderTiles.begin(), plunderTiles.end(), myTile) != plunderTiles.end())
            return true;

        if(LevelScriptRunner::walkToNearestTile(creature, plunderTiles))
            return true;
    }

    // As heroes do with the killplayer order: to the dungeon heart, and near it they fight
    return LevelScriptRunner::walkToDungeonHeart(creature, mTargetSeatId);
}

//! \brief Evaluates the words of the raid condition.
bool RaidManager::isStateMet(const std::string& state, uint32_t raidGroupId) const
{
    if(!mHasGate)
        return false;

    if(state == "open")
        return mSchedule.mGateOpen;

    bool leaderEscaped = false;
    bool leaderFleeing = false;
    bool arrived = true;
    bool found = false;
    uint32_t spawned = 0;
    uint32_t standing = 0;
    for(const RaidGroupData& group : mGroups)
    {
        if((raidGroupId != 0) && (group.mRaidGroupId != raidGroupId))
            continue;

        found = true;
        arrived = arrived && group.mArrived;
        leaderEscaped = leaderEscaped || (group.mLeaderState == RaidLeaderState::escaped);
        leaderFleeing = leaderFleeing || (group.mLeaderState == RaidLeaderState::fleeing);
        for(const std::string& member : group.mSpawned)
        {
            ++spawned;
            if(isStanding(member))
                ++standing;
        }
    }
    if(!found)
        return false;

    if(state == "arrived")
        return arrived;
    if(state == "escaped")
        return leaderEscaped;
    if(state == "fleeing")
        return leaderFleeing;
    if(state == "defeated")
        return RaidRules::isRaidDefeated(arrived, spawned, standing, leaderEscaped);

    return false;
}

//! \brief The gate room on the gate tile, if it is a hero portal room.
RoomPortalWave* RaidManager::getGateRoom() const
{
    Tile* tile = mGameMap.getTile(mGateX, mGateY);
    if(tile == nullptr)
        return nullptr;

    Room* room = tile->getCoveringRoom();
    if((room == nullptr) || (room->getType() != RoomType::portalWave))
        return nullptr;

    return static_cast<RoomPortalWave*>(room);
}

//! \brief Lets the hero portal room on the gate tile show the gate; without one the raid comes on the tile.
void RaidManager::setUpGate()
{
    mGateShown = true;
    RoomPortalWave* gate = getGateRoom();
    if(gate == nullptr)
    {
        OD_LOG_WRN("No hero portal room on the gate tile " + Helper::toString(mGateX) + "," + Helper::toString(mGateY)
            + ": the raid comes on the tile without the gate model");
        return;
    }

    gate->setMoreyaGate(mGateRotation, mSchedule.mGateOpen, raidConfig("RaidGatePortcullisSink"));
}

//! \brief Creates the members of the group on the gate tile, registers them as a raid group and tells the keepers.
void RaidManager::spawnGroup(uint32_t index)
{
    if(index >= mGroups.size())
        return;

    RaidGroupData& group = mGroups[index];
    group.mArrived = true;
    Seat* seat = mGameMap.getSeatById(mRaidSeatId);
    Tile* tile = mGameMap.getTile(mGateX, mGateY);
    if((seat == nullptr) || (tile == nullptr))
    {
        OD_LOG_ERR("Raid group " + Helper::toString(group.mRaidGroupId) + " cannot come: seat="
            + Helper::toString(mRaidSeatId) + ", gate=" + Helper::toString(mGateX) + "," + Helper::toString(mGateY));
        return;
    }

    CombatGroupManager& combatGroups = mGameMap.getCombatGroups();
    const std::string party = "Raid" + Helper::toString(group.mRaidGroupId);
    Ogre::Vector3 spawnPosition(static_cast<Ogre::Real>(tile->getX()), static_cast<Ogre::Real>(tile->getY()), 0.0f);
    for(const RaidMemberSpec& spec : group.mMembers)
    {
        const CreatureDefinition* definition = mGameMap.getClassDescription(spec.mClassName);
        if(definition == nullptr)
        {
            OD_LOG_ERR("Raid member of unknown creature class=" + spec.mClassName);
            continue;
        }

        Creature* creature = new Creature(&mGameMap, definition, seat, spawnPosition);
        // A member that the level names gets that name, if it is free
        if(!spec.mName.empty() && (mGameMap.getCreature(spec.mName) == nullptr))
            creature->setName(spec.mName);
        creature->setLevel(spec.mLevel);
        creature->setHP(creature->getMaxHp());
        creature->addToGameMap();
        ItemDrops::outfit(*creature, "hero");
        creature->createMesh();
        creature->setPosition(creature->getPosition());
        seat->notifyCreatureArrival(definition->getClassName());

        const std::string& name = creature->getName();
        group.mSpawned.push_back(name);
        combatGroups.registerRaidMember(name, group.mRaidGroupId, spec.mTemplate);
        mGameMap.getLevelScript().addPartyMember(party, name);
        if(!group.mLeaderName.empty() && (spec.mName == group.mLeaderName))
        {
            group.mLeaderSpawned = name;
            combatGroups.setRaidLeader(group.mRaidGroupId, name);
        }
        OD_LOG_INF("Raid member comes through the gate: name=" + name + ", class=" + spec.mClassName + ", level="
            + Helper::toString(spec.mLevel) + ", raidGroup=" + Helper::toString(group.mRaidGroupId));
    }

    if(group.mLeaderSpawned.empty())
        tellKeepers("A raid group comes through the Moreya gate!");
    else
        tellKeepers("A raid group led by " + group.mLeaderSpawned + " comes through the Moreya gate!");
}

//! \brief The treasuries and dungeon hearts holding gold of every keeper that is an enemy of the raid.
std::vector<Room*> RaidManager::plunderableRooms() const
{
    std::vector<Room*> rooms;
    Seat* raidSeat = mGameMap.getSeatById(mRaidSeatId);
    if(raidSeat == nullptr)
        return rooms;

    const RoomType types[] = { RoomType::treasury, RoomType::dungeonTemple };
    for(RoomType type : types)
    {
        for(Room* room : mGameMap.getRoomsByType(type))
        {
            Seat* owner = room->getSeat();
            if((owner == nullptr) || !CombatGroupManager::isKeeperSeat(owner) || owner->isAlliedSeat(raidSeat))
                continue;

            if(room->getTotalGoldStored() <= 0.0)
                continue;

            rooms.push_back(room);
        }
    }
    return rooms;
}

//! \brief Each standing member in a plunderable room takes what it can still carry (carryCapacity, RA7); the gold
//! leaves the keeper at once and the member carries it (a fallen member drops it, as every creature drops the gold it
//! carries; a member escaping through the gate takes it along). The rooms a member entered are remembered for the
//! detour of the leader and the first plunder of a room is told to the keeper.
void RaidManager::plunder()
{
    if(mGroups.empty())
        return;

    std::vector<Room*> rooms = plunderableRooms();
    if(rooms.empty())
        return;

    for(const RaidGroupData& group : mGroups)
    {
        for(const std::string& name : group.mSpawned)
        {
            if(!isStanding(name) || isEscaping(name))
                continue;

            Creature* creature = mGameMap.getCreature(name);
            Tile* tile = creature->getPositionTile();
            if(tile == nullptr)
                continue;

            Room* room = tile->getCoveringRoom();
            if((room == nullptr) || (std::find(rooms.begin(), rooms.end(), room) == rooms.end()))
                continue;

            bool firstInRoom = true;
            for(const std::pair<std::string, std::string>& done : mPlundered)
            {
                if(done.second == room->getName())
                {
                    firstInRoom = false;
                    break;
                }
            }

            // The room counts as visited also when the member can carry nothing more, so that the leader does not
            // turn aside to it again
            mPlundered.insert(std::make_pair(name, room->getName()));
            const double amount = RaidRules::plunderAmount(room->getTotalGoldStored(), creature->getGoldCarried(),
                carryCapacity(*creature));
            if(amount <= 0.0)
                continue;

            const double taken = room->withdrawGold(amount);
            if(taken <= 0.0)
                continue;

            creature->addGoldStolen(taken);
            mGameMap.getLevelScript().recordEvent(name, "steals");
            OD_LOG_INF("Raid member " + name + " plunders " + Helper::toString(taken) + " gold from " + room->getName());
            if(firstInRoom)
                tellKeepers("The raid plunders your gold!");
        }
    }
}

//! \brief A leader flees once the fallen share of his group reached the escape share, and escapes at the gate.
void RaidManager::updateLeaders()
{
    const double share = escapeShare();
    for(RaidGroupData& group : mGroups)
    {
        // RA8 / FQ 10: a follower that reached the gate escapes through it, also when its leader escaped before it
        // (a leader who fell during the flight released his followers before, RA8b)
        const std::vector<std::string> followers = group.mFollowers;
        for(const std::string& follower : followers)
        {
            if(!isEscaping(follower) || !isStanding(follower))
                continue;

            Creature* member = mGameMap.getCreature(follower);
            if(isAtGate(*member))
                escapeMember(group, *member);
        }

        if(!group.mArrived || group.mLeaderSpawned.empty())
            continue;

        if(group.mLeaderState == RaidLeaderState::escaped)
            continue;

        if(!isStanding(group.mLeaderSpawned))
        {
            // RA8b: a fleeing leader killed or captured before the gate ends the flight of his followers
            if(group.mLeaderState == RaidLeaderState::fleeing)
                endFlight(group);

            continue;
        }

        Creature* leader = mGameMap.getCreature(group.mLeaderSpawned);
        if(group.mLeaderState == RaidLeaderState::fleeing)
        {
            if(isAtGate(*leader))
                escape(group, *leader);

            continue;
        }

        uint32_t others = 0;
        uint32_t fallen = 0;
        for(const std::string& member : group.mSpawned)
        {
            if(member == group.mLeaderSpawned)
                continue;

            ++others;
            if(!isStanding(member))
                ++fallen;
        }
        if(!RaidRules::leaderShouldFlee(others, fallen, share))
            continue;

        // The leader leaves his group and runs to the gate; the members still standing follow him there at his speed
        // (FQ 10 c), so the raid group breaks up
        group.mLeaderState = RaidLeaderState::fleeing;
        std::vector<std::string> fleeing(1, group.mLeaderSpawned);
        for(const std::string& member : group.mSpawned)
        {
            if((member == group.mLeaderSpawned) || !isStanding(member))
                continue;

            group.mFollowers.push_back(member);
            fleeing.push_back(member);
        }
        for(const std::string& name : fleeing)
        {
            Creature* creature = mGameMap.getCreature(name);
            mGameMap.getCombatGroups().setRaidMemberDetached(name, true);
            creature->setMoveSpeedModifier(LevelScriptRunner::getRunSpeedFactor());
            creature->stopWalking();
            creature->clearActionQueue();
        }
        OD_LOG_INF("Raid leader " + group.mLeaderSpawned + " flees to the gate, fallen "
            + Helper::toString(fallen) + " of " + Helper::toString(others) + ", followers "
            + Helper::toString(static_cast<uint32_t>(group.mFollowers.size())));
        tellKeepers(group.mLeaderSpawned + " flees to the Moreya gate! Catch him before he escapes.");
    }
}

//! \brief The leader fell (dead, imprisoned or converted) while he fled: the flight is over. His followers that did
//! not escape yet stop running, rejoin their raid group at their normal speed and fight again; the members that
//! already escaped stay escaped. The leader state goes back to none, so that the fallen leader neither runs to the gate
//! nor counts as fleeing.
void RaidManager::endFlight(RaidGroupData& group)
{
    std::vector<std::string> escapedFollowers;
    uint32_t released = 0;
    for(const std::string& follower : group.mFollowers)
    {
        if(std::find(group.mEscapedMembers.begin(), group.mEscapedMembers.end(), follower) !=
           group.mEscapedMembers.end())
        {
            escapedFollowers.push_back(follower);
            continue;
        }

        mGameMap.getCombatGroups().setRaidMemberDetached(follower, false);
        Creature* creature = mGameMap.getCreature(follower);
        if((creature == nullptr) || !isStanding(follower))
            continue;

        ++released;
        creature->clearMoveSpeedModifier();
        if(creature->getIsOnServerMap())
        {
            creature->stopWalking();
            creature->clearActionQueue();
        }
    }
    // A captured or converted leader walks at his normal speed again
    mGameMap.getCombatGroups().setRaidMemberDetached(group.mLeaderSpawned, false);
    Creature* leader = mGameMap.getCreature(group.mLeaderSpawned);
    if((leader != nullptr) && leader->isAlive())
        leader->clearMoveSpeedModifier();
    group.mFollowers = escapedFollowers;
    group.mLeaderState = RaidLeaderState::none;
    OD_LOG_INF("Raid leader " + group.mLeaderSpawned + " fell during his flight, " + Helper::toString(released)
        + " followers fight again");
}

//! \brief Gives a fleeing leader and his followers that did not escape yet their running speed again (the speed is
//! not saved, the flight is: Leader and Follower lines of the [Raid] section).
void RaidManager::restoreFlightSpeed()
{
    for(const RaidGroupData& group : mGroups)
    {
        if(group.mLeaderState != RaidLeaderState::fleeing)
            continue;

        std::vector<std::string> fleeing(1, group.mLeaderSpawned);
        for(const std::string& follower : group.mFollowers)
        {
            if(std::find(group.mEscapedMembers.begin(), group.mEscapedMembers.end(), follower) ==
               group.mEscapedMembers.end())
                fleeing.push_back(follower);
        }
        for(const std::string& name : fleeing)
        {
            Creature* creature = mGameMap.getCreature(name);
            if((creature != nullptr) && creature->isAlive())
                creature->setMoveSpeedModifier(LevelScriptRunner::getRunSpeedFactor());
        }
    }
}

//! \brief The follower leaves the map through the gate with its gold and items; it counts as defeated (isStanding no
//! longer finds it) and does not lose the level.
void RaidManager::escapeMember(RaidGroupData& group, Creature& member)
{
    const std::string name = member.getName();
    group.mEscapedMembers.push_back(name);
    mGameMap.getCombatGroups().setRaidMemberDetached(name, false);
    OD_LOG_INF("Raid member " + name + " followed its leader through the gate with "
        + Helper::toString(member.getGoldCarried()) + " gold");
    member.clearDestinations(EntityAnimation::idle_anim, true, true);
    member.removeFromGameMap();
    member.deleteYourself();
}

//! \brief Drops the names of loot bags that are no longer on the map.
void RaidManager::forgetMissingLoot()
{
    std::set<std::string>::iterator it = mLoot.begin();
    while(it != mLoot.end())
    {
        RenderedMovableEntity* entity = mGameMap.getRenderedMovableEntity(*it);
        if((entity == nullptr) || !entity->getIsOnMap() || (entity->getObjectType() != GameEntityType::itemBagEntity))
            it = mLoot.erase(it);
        else
            ++it;
    }
}

//! \brief Remembers the bag when a keeper's creature dropped it at its death on the server map of a raid level.
void RaidManager::registerFallenDrop(const Creature& fallen, const ItemBagEntity& bag)
{
    if(!mHasGate || !mGameMap.isServerGameMap() || !CombatGroupManager::isKeeperSeat(fallen.getSeat()))
        return;

    mLoot.insert(bag.getName());
}

//! \brief Takes a loot bag on the creature's tile, else walks to the nearest reachable loot bag it sees.
bool RaidManager::doLoot(Creature& creature)
{
    if(!mHasGate || mLoot.empty() || !creature.getIsOnServerMap() || (creature.getSeat() == nullptr))
        return false;

    const std::string& name = creature.getName();
    if((findGroupOfSpawned(name) == nullptr) || !isStanding(name) || isEscaping(name) || creature.isKo() ||
       creature.isActionInList(CreatureActionType::fight))
        return false;

    // Exactly like the creatures: an item goes into a free inventory slot
    bool freeSlot = false;
    for(const std::unique_ptr<ItemInstance>& item : creature.getInventory())
    {
        if(item.get() == nullptr)
            freeSlot = true;
    }
    if(!freeSlot)
        return false;

    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
        return false;

    ItemBagEntity* bagHere = nullptr;
    std::vector<Tile*> lootTiles;
    for(Tile* tile : creature.getVisibleTiles())
    {
        for(GameEntity* entity : tile->getEntitiesInTile())
        {
            if((entity->getObjectType() != GameEntityType::itemBagEntity) || (mLoot.count(entity->getName()) == 0))
                continue;

            ItemBagEntity* bag = static_cast<ItemBagEntity*>(entity);
            const ItemInstance* item = bag->getItem();
            if((item == nullptr) || item->mMerchantGoods || (item->mGhostItem != GhostItem::none) ||
               bag->getCarryLock(creature))
                continue;

            if((bag->getSeat() != nullptr) && creature.getSeat()->isAlliedSeat(bag->getSeat()))
                continue;

            if(tile == myTile)
            {
                bagHere = bag;
                break;
            }

            if(mGameMap.pathExists(&creature, myTile, tile))
                lootTiles.push_back(tile);
        }
        if(bagHere != nullptr)
            break;
    }

    if(bagHere != nullptr)
    {
        const std::string bagName = bagHere->getName();
        std::unique_ptr<ItemInstance> item = bagHere->takeItem();
        mLoot.erase(bagName);
        bagHere->removeFromGameMap();
        bagHere->deleteYourself();
        if(item.get() == nullptr)
            return false;

        OD_LOG_INF("Raid member " + name + " loots the item bag " + bagName);
        creature.acceptItem(std::move(item));
        return true;
    }

    if(lootTiles.empty())
        return false;

    return LevelScriptRunner::walkToNearestTile(creature, lootTiles);
}

//! \brief The central tile of the gate.
Tile* RaidManager::getGateTile() const
{
    if(!mHasGate)
        return nullptr;

    return mGameMap.getTile(mGateX, mGateY);
}

//! \brief RaidRules::carryCapacity with the size of the member's class and the config values.
double RaidManager::carryCapacity(const Creature& creature)
{
    ConfigManager& config = ConfigManager::getSingleton();
    const std::string className = (creature.getDefinition() != nullptr) ? creature.getDefinition()->getClassName()
        : std::string();
    const bool large = RaidRules::isLargeMember(className, config.getRaidConfigWords("RaidLargeMemberClasses"));
    return RaidRules::carryCapacity(large, config.getRoomConfigDouble("TreasuryGoldPerTile"),
        raidConfig("RaidCarryTilesSmall"), raidConfig("RaidCarryTilesLarge"));
}

//! \brief The leader leaves the map through the gate with the gold he carries; the attacked keeper loses the level.
void RaidManager::escape(RaidGroupData& group, Creature& leader)
{
    group.mLeaderState = RaidLeaderState::escaped;
    OD_LOG_INF("Raid leader " + group.mLeaderSpawned + " escaped through the gate with "
        + Helper::toString(leader.getGoldCarried()) + " gold");
    leader.clearDestinations(EntityAnimation::idle_anim, true, true);
    leader.removeFromGameMap();
    leader.deleteYourself();

    tellKeepers(group.mLeaderSpawned + " escaped through the Moreya gate. The level is lost.");
    if(mLost)
        return;

    mLost = true;
    for(Player* player : mGameMap.getPlayers())
    {
        if(!player->getIsHuman() || player->getHasLost() || (player->getSeat() == nullptr))
            continue;

        if((mTargetSeatId >= 0) && (player->getSeat()->getId() != mTargetSeatId))
            continue;

        player->notifyNoMoreDungeonTemple();
    }
}

//! \brief Alive (an unconscious member too, Q20.12), on the map or held in a keeper's hand, not imprisoned and not won
//! over by a keeper. An escaped member is no longer on the map and has fallen.
bool RaidManager::isStanding(const std::string& creatureName) const
{
    Creature* creature = mGameMap.getCreature(creatureName);
    if(creature == nullptr)
        return false;

    return creature->isAlive() && (creature->getIsOnMap() || creature->isInHand()) && !creature->isInPrison() &&
        (creature->getSeat() != nullptr) && !CombatGroupManager::isKeeperSeat(creature->getSeat());
}

//! \brief On a tile of the gate room or within RaidGateArrivalTiles of the gate tile.
bool RaidManager::isAtGate(const Creature& creature) const
{
    Tile* tile = creature.getPositionTile();
    Tile* gateTile = mGameMap.getTile(mGateX, mGateY);
    if((tile == nullptr) || (gateTile == nullptr))
        return false;

    RoomPortalWave* gate = getGateRoom();
    if((gate != nullptr) && (tile->getCoveringRoom() == gate))
        return true;

    return static_cast<double>(tileDistance(*tile, *gateTile)) <= raidConfig("RaidGateArrivalTiles");
}

//! \brief Sends the text as a major event to the attacked keeper, or to every human keeper without one.
void RaidManager::tellKeepers(const std::string& text) const
{
    for(Player* player : mGameMap.getPlayers())
    {
        if(!player->getIsHuman() || (player->getSeat() == nullptr))
            continue;

        if((mTargetSeatId >= 0) && (player->getSeat()->getId() != mTargetSeatId))
            continue;

        ServerNotification* serverNotification = new ServerNotification(
            ServerNotificationType::chatServer, player);
        serverNotification->mPacket << text << EventShortNoticeType::majorGameEvent;
        ODServer::getSingleton().queueServerNotification(serverNotification);
    }
}

//! \brief The saved spelling of a leader state.
const char* RaidManager::leaderStateName(RaidLeaderState state)
{
    switch(state)
    {
        case RaidLeaderState::fleeing:
            return "fleeing";
        case RaidLeaderState::escaped:
            return "escaped";
        case RaidLeaderState::none:
        default:
            return "none";
    }
}

//! \brief Reads none, fleeing or escaped.
bool RaidManager::parseLeaderState(const std::string& text, RaidLeaderState& state)
{
    if(text == "none")
        state = RaidLeaderState::none;
    else if(text == "fleeing")
        state = RaidLeaderState::fleeing;
    else if(text == "escaped")
        state = RaidLeaderState::escaped;
    else
        return false;

    return true;
}

//! \brief The line formats of the section, one per kind of line.
std::string RaidManager::getStreamFormat()
{
    return "Gate X Y RotationDegrees | Seats RaidSeatId TargetSeatId | Countdown Seconds|- | Interval Seconds|- | "
        "EscapeShare Share|- | Group RaidGroupId LeaderName|- | Member RaidGroupId ClassName Level Name|- Template|- | "
        "State Started GateOpen NextGroup SecondsToNext Lost | Arrived RaidGroupId LeaderName|- LeaderState NbMembers "
        "Member... | Plundered CreatureName RoomName | Follower RaidGroupId CreatureName | Escaped RaidGroupId "
        "CreatureName | Loot ItemBagName";
}

//! \brief Writes the level data and, in a saved game, the running state of the raid.
void RaidManager::exportToStream(std::ostream& os, bool isGameSave) const
{
    if(!mHasGate)
        return;

    // The numbers are written with all their digits, so that a saved game continues exactly
    const std::streamsize oldPrecision = os.precision(17);
    os << "\n[Raid]\n";
    os << "# " << getStreamFormat() << "\n";
    os << "Gate\t" << mGateX << "\t" << mGateY << "\t" << mGateRotation << "\n";
    os << "Seats\t" << mRaidSeatId << "\t" << mTargetSeatId << "\n";
    os << "Countdown\t" << optionalNumberText(mCountdownSeconds) << "\n";
    os << "Interval\t" << optionalNumberText(mIntervalSeconds) << "\n";
    os << "EscapeShare\t" << optionalNumberText(mEscapeShare) << "\n";
    for(const RaidGroupData& group : mGroups)
    {
        os << "Group\t" << group.mRaidGroupId << "\t" << textOrDash(group.mLeaderName) << "\n";
        for(const RaidMemberSpec& spec : group.mMembers)
        {
            os << "Member\t" << group.mRaidGroupId << "\t" << spec.mClassName << "\t" << spec.mLevel << "\t"
                << textOrDash(spec.mName) << "\t" << textOrDash(spec.mTemplate) << "\n";
        }
    }

    if(isGameSave)
    {
        os << "State\t" << (mStarted ? 1 : 0) << "\t" << (mSchedule.mGateOpen ? 1 : 0) << "\t" << mSchedule.mNextGroup
            << "\t" << mSchedule.mSecondsToNext << "\t" << (mLost ? 1 : 0) << "\n";
        for(const RaidGroupData& group : mGroups)
        {
            if(!group.mArrived)
                continue;

            os << "Arrived\t" << group.mRaidGroupId << "\t" << textOrDash(group.mLeaderSpawned) << "\t"
                << leaderStateName(group.mLeaderState) << "\t" << group.mSpawned.size();
            for(const std::string& member : group.mSpawned)
                os << "\t" << member;
            os << "\n";
        }
        for(const std::pair<std::string, std::string>& done : mPlundered)
            os << "Plundered\t" << done.first << "\t" << done.second << "\n";
        for(const RaidGroupData& group : mGroups)
        {
            for(const std::string& follower : group.mFollowers)
                os << "Follower\t" << group.mRaidGroupId << "\t" << follower << "\n";
            for(const std::string& escaped : group.mEscapedMembers)
                os << "Escaped\t" << group.mRaidGroupId << "\t" << escaped << "\n";
        }
        for(const std::string& bag : mLoot)
            os << "Loot\t" << bag << "\n";
    }

    os << "[/Raid]\n";
    os.precision(oldPrecision);
}

//! \brief Reads the lines written by exportToStream; an unknown or broken line refuses the section. The groups come in
//! the order of their Group lines; a fleeing leader and the followers that did not escape yet leave their combat group
//! again. A saved game without Follower, Escaped and Loot lines (written before them) loads as before.
bool RaidManager::importFromStream(std::istream& is)
{
    std::string token;
    while(is >> token)
    {
        if(token == "[/Raid]")
        {
            if(!mHasGate)
            {
                OD_LOG_ERR("[Raid] section without a Gate line");
                return false;
            }
            mSchedule.mGroupCount = static_cast<uint32_t>(mGroups.size());
            for(const RaidGroupData& group : mGroups)
            {
                if(group.mLeaderState == RaidLeaderState::fleeing)
                    mGameMap.getCombatGroups().setRaidMemberDetached(group.mLeaderSpawned, true);

                for(const std::string& follower : group.mFollowers)
                {
                    if(std::find(group.mEscapedMembers.begin(), group.mEscapedMembers.end(), follower) ==
                       group.mEscapedMembers.end())
                        mGameMap.getCombatGroups().setRaidMemberDetached(follower, true);
                }
            }
            return true;
        }

        std::string rest;
        std::getline(is, rest);
        std::stringstream line(rest);
        if(token == "Gate")
        {
            if(!(line >> mGateX >> mGateY >> mGateRotation))
            {
                OD_LOG_ERR("Invalid Gate line=" + rest);
                return false;
            }
            mHasGate = true;
            continue;
        }

        if(token == "Seats")
        {
            if(!(line >> mRaidSeatId >> mTargetSeatId))
            {
                OD_LOG_ERR("Invalid Seats line=" + rest);
                return false;
            }
            continue;
        }

        if((token == "Countdown") || (token == "Interval") || (token == "EscapeShare"))
        {
            std::string valueText;
            double value = -1.0;
            if(!(line >> valueText) || !parseOptionalNumber(valueText, value))
            {
                OD_LOG_ERR("Invalid " + token + " line=" + rest);
                return false;
            }
            if(token == "Countdown")
                mCountdownSeconds = value;
            else if(token == "Interval")
                mIntervalSeconds = value;
            else
                mEscapeShare = value;
            continue;
        }

        if(token == "Group")
        {
            RaidGroupData group;
            std::string leader;
            if(!(line >> group.mRaidGroupId >> leader) || (group.mRaidGroupId == 0))
            {
                OD_LOG_ERR("Invalid Group line=" + rest);
                return false;
            }
            group.mLeaderName = dashToEmpty(leader);
            mGroups.push_back(group);
            continue;
        }

        if(token == "Member")
        {
            uint32_t raidGroupId = 0;
            RaidMemberSpec spec;
            std::string name;
            std::string templateName;
            if(!(line >> raidGroupId >> spec.mClassName >> spec.mLevel >> name >> templateName))
            {
                OD_LOG_ERR("Invalid Member line=" + rest);
                return false;
            }
            spec.mName = dashToEmpty(name);
            spec.mTemplate = dashToEmpty(templateName);
            RaidGroupData* group = nullptr;
            for(RaidGroupData& candidate : mGroups)
            {
                if(candidate.mRaidGroupId == raidGroupId)
                    group = &candidate;
            }
            if(group == nullptr)
            {
                OD_LOG_ERR("Member line of a raid group without Group line=" + rest);
                return false;
            }
            group->mMembers.push_back(spec);
            continue;
        }

        if(token == "State")
        {
            int32_t started = 0;
            int32_t gateOpen = 0;
            int32_t lost = 0;
            if(!(line >> started >> gateOpen >> mSchedule.mNextGroup >> mSchedule.mSecondsToNext >> lost))
            {
                OD_LOG_ERR("Invalid State line=" + rest);
                return false;
            }
            mStarted = (started != 0);
            mSchedule.mGateOpen = (gateOpen != 0);
            mLost = (lost != 0);
            continue;
        }

        if(token == "Arrived")
        {
            uint32_t raidGroupId = 0;
            std::string leader;
            std::string stateText;
            uint32_t nbMembers = 0;
            RaidLeaderState state = RaidLeaderState::none;
            if(!(line >> raidGroupId >> leader >> stateText >> nbMembers) || !parseLeaderState(stateText, state))
            {
                OD_LOG_ERR("Invalid Arrived line=" + rest);
                return false;
            }
            RaidGroupData* group = nullptr;
            for(RaidGroupData& candidate : mGroups)
            {
                if(candidate.mRaidGroupId == raidGroupId)
                    group = &candidate;
            }
            if(group == nullptr)
            {
                OD_LOG_ERR("Arrived line of a raid group without Group line=" + rest);
                return false;
            }
            group->mArrived = true;
            group->mLeaderSpawned = dashToEmpty(leader);
            group->mLeaderState = state;
            group->mSpawned.clear();
            for(uint32_t i = 0; i < nbMembers; ++i)
            {
                std::string member;
                if(!(line >> member))
                {
                    OD_LOG_ERR("Arrived line with too few members=" + rest);
                    return false;
                }
                group->mSpawned.push_back(member);
            }
            continue;
        }

        if(token == "Plundered")
        {
            std::string name;
            std::string room;
            if(!(line >> name >> room))
            {
                OD_LOG_ERR("Invalid Plundered line=" + rest);
                return false;
            }
            mPlundered.insert(std::make_pair(name, room));
            continue;
        }

        if((token == "Follower") || (token == "Escaped"))
        {
            uint32_t raidGroupId = 0;
            std::string name;
            if(!(line >> raidGroupId >> name))
            {
                OD_LOG_ERR("Invalid " + token + " line=" + rest);
                return false;
            }
            RaidGroupData* group = nullptr;
            for(RaidGroupData& candidate : mGroups)
            {
                if(candidate.mRaidGroupId == raidGroupId)
                    group = &candidate;
            }
            if(group == nullptr)
            {
                OD_LOG_ERR(token + " line of a raid group without Group line=" + rest);
                return false;
            }
            if(token == "Follower")
                group->mFollowers.push_back(name);
            else
                group->mEscapedMembers.push_back(name);
            continue;
        }

        if(token == "Loot")
        {
            std::string bag;
            if(!(line >> bag))
            {
                OD_LOG_ERR("Invalid Loot line=" + rest);
                return false;
            }
            mLoot.insert(bag);
            continue;
        }

        OD_LOG_ERR("Unknown line in [Raid]: " + token + rest);
        return false;
    }

    OD_LOG_ERR("Missing [/Raid]");
    return false;
}
