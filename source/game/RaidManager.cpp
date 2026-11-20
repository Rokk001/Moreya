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

#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
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

//! \brief Forgets the level data, the running state and the transient state.
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

//! \brief Runs the raid for one turn: gate, countdown, arrivals, plundering and the leaders.
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
        setUpGate();

    if(!mLost)
        advanceSchedule(1.0 / ODApplication::turnsPerSecond);

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

//! \brief Looks for a fleeing leader with that name.
bool RaidManager::isEscaping(const std::string& creatureName) const
{
    for(const RaidGroupData& group : mGroups)
    {
        if((group.mLeaderState == RaidLeaderState::fleeing) && (group.mLeaderSpawned == creatureName))
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

//! \brief A fleeing leader runs to the gate; the leader of a group turns aside to a treasury on the way that he did
//! not plunder yet, else walks to the dungeon heart of the attacked keeper as the killplayer order does.
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
        // The flight ends at the gate (update); until then the leader runs there and does nothing else
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
            OD_LOG_WRN("Raid leader " + name + " finds no way to the gate");

        return true;
    }

    // The members keep their place in the formation of their raid group; its leader leads them
    if(mGameMap.getCombatGroups().shouldKeepFormation(creature))
        return false;

    if(mTargetSeatId < 0)
        return false;

    // A treasury holding gold that lies on the way and that the leader did not plunder yet
    const double detour = raidConfig("RaidPlunderDetourTiles");
    std::vector<Tile*> plunderTiles;
    for(Room* room : plunderableRooms())
    {
        if(mPlundered.count(std::make_pair(name, room->getName())) > 0)
            continue;

        for(Tile* tile : room->getCoveredTiles())
        {
            if(static_cast<double>(tileDistance(*myTile, *tile)) <= detour)
                plunderTiles.push_back(tile);
        }
    }
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

//! \brief Each standing member in a plunderable room takes RaidPlunderGoldPerMember from it once; the gold leaves the
//! keeper at once and the member carries it (a killed member drops it, as every creature drops the gold it carries).
void RaidManager::plunder()
{
    if(mGroups.empty())
        return;

    std::vector<Room*> rooms = plunderableRooms();
    if(rooms.empty())
        return;

    const double perMember = raidConfig("RaidPlunderGoldPerMember");
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

            const std::pair<std::string, std::string> key(name, room->getName());
            if(mPlundered.count(key) > 0)
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

            mPlundered.insert(key);
            const double taken = room->withdrawGold(RaidRules::plunderAmount(room->getTotalGoldStored(), perMember));
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
        if(!group.mArrived || group.mLeaderSpawned.empty())
            continue;

        if(group.mLeaderState == RaidLeaderState::escaped)
            continue;

        if(!isStanding(group.mLeaderSpawned))
            continue;

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

        // The leader leaves his group and runs to the gate; the members go on fighting under the next leader
        group.mLeaderState = RaidLeaderState::fleeing;
        mGameMap.getCombatGroups().setRaidMemberDetached(group.mLeaderSpawned, true);
        leader->setMoveSpeedModifier(LevelScriptRunner::getRunSpeedFactor());
        leader->stopWalking();
        leader->clearActionQueue();
        OD_LOG_INF("Raid leader " + group.mLeaderSpawned + " flees to the gate, fallen "
            + Helper::toString(fallen) + " of " + Helper::toString(others));
        tellKeepers(group.mLeaderSpawned + " flees to the Moreya gate! Catch him before he escapes.");
    }
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

//! \brief Alive, on the map, not imprisoned and not won over by a keeper.
bool RaidManager::isStanding(const std::string& creatureName) const
{
    Creature* creature = mGameMap.getCreature(creatureName);
    if(creature == nullptr)
        return false;

    return creature->isAlive() && creature->getIsOnMap() && !creature->isInPrison() &&
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
        "Member... | Plundered CreatureName RoomName";
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
    }

    os << "[/Raid]\n";
    os.precision(oldPrecision);
}

//! \brief Reads the lines written by exportToStream; an unknown or broken line refuses the section. The groups come in
//! the order of their Group lines; a fleeing leader leaves his combat group again.
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

        OD_LOG_ERR("Unknown line in [Raid]: " + token + rest);
        return false;
    }

    OD_LOG_ERR("Missing [/Raid]");
    return false;
}
