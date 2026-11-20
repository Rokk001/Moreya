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

#include "utils/RaidSimulation.h"

#include "creatureaction/CreatureAction.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/Tile.h"
#include "game/CombatGroupManager.h"
#include "game/Player.h"
#include "game/RaidManager.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/LevelScript.h"
#include "network/ODServer.h"
#include "rooms/Room.h"
#include "rooms/RoomType.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "utils/Random.h"
#include "utils/ResourceManager.h"
#include "ODApplication.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <vector>

namespace
{
//! \brief True once run was called.
bool sActive = false;
//! \brief The exit code of the last run.
int sExitCode = RaidSimulation::codeDone;

//! \brief Sums and counts of the creatures of one side after a turn.
struct SideState
{
    //! \brief Creates an empty side.
    SideState() :
        mAlive(0),
        mHp(0.0),
        mMaxHp(0.0),
        mFighting(0),
        mFleeing(0),
        mInPlace(0),
        mWithPlace(0),
        mPlaceDistance(0.0),
        mGold(0.0)
    {}
    //! \brief Standing creatures (alive, on the map, not knocked out).
    uint32_t mAlive;
    //! \brief Hit points and maximum hit points of the standing creatures.
    double mHp;
    double mMaxHp;
    //! \brief Standing creatures that have a fight in their action list.
    uint32_t mFighting;
    //! \brief Standing creatures that have a flight in their action list.
    uint32_t mFleeing;
    //! \brief Group members standing at their formation place, and group members that have one.
    uint32_t mInPlace;
    uint32_t mWithPlace;
    //! \brief Sum of the distances in tiles of the group members that have a formation place to that place.
    double mPlaceDistance;
    //! \brief Gold the standing creatures carry.
    double mGold;
};

//! \brief True while the creature stands: alive, on the map and not knocked out.
bool isStanding(const Creature& creature)
{
    return creature.isAlive() && creature.getIsOnMap() && !creature.isKo() && (creature.getPositionTile() != nullptr);
}

//! \brief Adds a standing creature to the sums of its side.
void addToSide(SideState& side, Creature& creature, const CombatGroupManager& groups)
{
    ++side.mAlive;
    side.mHp += creature.getHP();
    side.mMaxHp += creature.getMaxHp();
    side.mGold += creature.getGoldCarried();
    if(creature.isActionInList(CreatureActionType::fight))
        ++side.mFighting;
    if(creature.isActionInList(CreatureActionType::flee))
        ++side.mFleeing;

    Tile* place = groups.getFormationTile(creature);
    if(place == nullptr)
        return;

    ++side.mWithPlace;
    if(groups.isAtFormationPlace(creature, *place))
        ++side.mInPlace;

    Tile* tile = creature.getPositionTile();
    side.mPlaceDistance += static_cast<double>(std::max(std::abs(tile->getX() - place->getX()),
        std::abs(tile->getY() - place->getY())));
}

//! \brief The mean distance in tiles (largest of the x and y distance) of the creatures to their centre.
double spread(const std::vector<Creature*>& creatures)
{
    if(creatures.empty())
        return 0.0;

    double centreX = 0.0;
    double centreY = 0.0;
    for(Creature* creature : creatures)
    {
        centreX += static_cast<double>(creature->getPositionTile()->getX());
        centreY += static_cast<double>(creature->getPositionTile()->getY());
    }
    centreX /= static_cast<double>(creatures.size());
    centreY /= static_cast<double>(creatures.size());
    double sum = 0.0;
    for(Creature* creature : creatures)
    {
        sum += std::max(std::abs(static_cast<double>(creature->getPositionTile()->getX()) - centreX),
            std::abs(static_cast<double>(creature->getPositionTile()->getY()) - centreY));
    }
    return sum / static_cast<double>(creatures.size());
}

//! \brief The gold stored in the treasuries and the dungeon heart of the seat.
double storedGold(GameMap& gameMap, Seat* seat)
{
    double gold = 0.0;
    const RoomType types[] = { RoomType::treasury, RoomType::dungeonTemple };
    for(RoomType type : types)
    {
        for(Room* room : gameMap.getRoomsByTypeAndSeat(type, seat))
            gold += room->getTotalGoldStored();
    }
    return gold;
}

//! \brief Gold each raid member carried after the last turn, to see what it took this turn.
std::map<std::string, double> sCarried;
//! \brief Gold the raid took so far from treasuries and from dungeon hearts.
double sPlunderedTreasury = 0.0;
double sPlunderedHeart = 0.0;

//! \brief Adds what a raid member took this turn to the plunder of the room type it stands in.
void notePlunder(Creature& creature)
{
    const double carried = creature.getGoldCarried();
    std::map<std::string, double>::iterator it = sCarried.find(creature.getName());
    const double before = (it == sCarried.end()) ? 0.0 : it->second;
    sCarried[creature.getName()] = carried;
    if(carried <= before)
        return;

    Room* room = creature.getPositionTile()->getCoveringRoom();
    if(room == nullptr)
        return;
    if(room->getType() == RoomType::treasury)
        sPlunderedTreasury += carried - before;
    else if(room->getType() == RoomType::dungeonTemple)
        sPlunderedHeart += carried - before;
}

//! \brief The gold stored in the treasuries of the seat (without the dungeon heart).
double treasuryGold(GameMap& gameMap, Seat* seat)
{
    double gold = 0.0;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(RoomType::treasury, seat))
        gold += room->getTotalGoldStored();
    return gold;
}

//! \brief The phase-1 main goals of the attacked keeper: the ids of the level script's main objectives of his seat
//! (Action mainobjectiveid) except the raid goal (id ending in "-raid"), read from the level file.
std::vector<std::string> sPhase1Goals;

//! \brief Reads the phase-1 main goals of the seat from the trigger lines of the level file.
void readPhase1Goals(const std::string& levelFile, int32_t seatId)
{
    sPhase1Goals.clear();
    std::ifstream level(levelFile.c_str());
    std::string line;
    const std::string raidSuffix = "-raid";
    while(std::getline(level, line))
    {
        std::istringstream fields(line);
        std::string word;
        std::string type;
        int32_t goalSeat = -1;
        std::string id;
        if(!(fields >> word >> type >> goalSeat >> id) || (word != "Action") || (type != "mainobjectiveid"))
            continue;
        if((goalSeat != seatId) && (goalSeat != -1))
            continue;
        if((id.size() >= raidSuffix.size())
            && (id.compare(id.size() - raidSuffix.size(), raidSuffix.size(), raidSuffix) == 0))
            continue;
        if(std::find(sPhase1Goals.begin(), sPhase1Goals.end(), id) == sPhase1Goals.end())
            sPhase1Goals.push_back(id);
    }
}

//! \brief The number of phase-1 main goals of the seat that are reached now.
uint32_t phase1Reached(const GameMap& gameMap, int32_t seatId)
{
    uint32_t reached = 0;
    for(const std::string& id : sPhase1Goals)
    {
        if(gameMap.getLevelScript().getObjectiveState(seatId, id) == LevelScriptObjectiveState::reached)
            ++reached;
    }
    return reached;
}

//! \brief Counts the ground tiles claimed by the seat and the tiles covered by its rooms.
void countTiles(GameMap& gameMap, Seat* seat, uint32_t& claimed, uint32_t& roomTiles)
{
    claimed = 0;
    roomTiles = 0;
    if(seat == nullptr)
        return;
    for(int32_t x = 0; x < gameMap.getMapSizeX(); ++x)
    {
        for(int32_t y = 0; y < gameMap.getMapSizeY(); ++y)
        {
            Tile* tile = gameMap.getTile(x, y);
            if((tile != nullptr) && tile->isClaimedForSeat(seat))
                ++claimed;
        }
    }
    for(Room* room : gameMap.getRooms())
    {
        if(room->getSeat() == seat)
            roomTiles += static_cast<uint32_t>(room->getCoveredTiles().size());
    }
}

//! \brief The hit points of the dungeon heart tiles of the seat.
double heartHp(GameMap& gameMap, Seat* seat)
{
    double hp = 0.0;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        for(Tile* tile : room->getCoveredTiles())
            hp += room->getHP(tile);
    }
    return hp;
}

//! \brief Creature classes of the reference keeper force (--raid-sim-force), in the order they are placed.
std::vector<std::string> sForceClasses;
//! \brief Level of the creatures of the reference keeper force.
int32_t sForceLevel = 1;
//! \brief True when the hand limit of campaign levels applies in the run (--raid-sim-hand-limit).
bool sHandLimit = false;
//! \brief Fighting creatures the attacked keeper dropped from his hand so far.
uint32_t sHandDrops = 0;
//! \brief Fighting creatures in the attacked keeper's hand after the last turn.
uint32_t sHandFighters = 0;
//! \brief True when --raid-sim-hand-player lets a model keeper use his hand in the fight.
bool sHandPlayer = false;

//! \brief The ground tiles around the centre of the seat's dungeon heart that the creature can walk on, nearest
//! first (steps from tile to neighbour tile), at most count of them.
std::vector<Tile*> tilesAroundHeart(GameMap& gameMap, Seat* seat, const Creature& creature, size_t count)
{
    std::vector<Tile*> tiles;
    Tile* centre = nullptr;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        centre = room->getCentralTile();
        break;
    }
    if(centre == nullptr)
        return tiles;

    std::vector<Tile*> frontier(1, centre);
    std::vector<Tile*> seen(1, centre);
    while(!frontier.empty() && (tiles.size() < count))
    {
        std::vector<Tile*> next;
        for(Tile* tile : frontier)
        {
            if(creature.canGoThroughTile(tile) && (tiles.size() < count))
                tiles.push_back(tile);

            for(Tile* neighbor : tile->getAllNeighbors())
            {
                if((neighbor == nullptr) || (std::find(seen.begin(), seen.end(), neighbor) != seen.end()))
                    continue;

                seen.push_back(neighbor);
                // The search spreads over walkable tiles only (the heart itself counts as the start)
                if(creature.canGoThroughTile(neighbor))
                    next.push_back(neighbor);
            }
        }
        frontier.swap(next);
    }
    return tiles;
}

//! \brief Places the reference keeper force of --raid-sim-force at the dungeon heart of the attacked keeper: one
//! creature of each class in the given order, at the given level and full health, each on its own walkable tile
//! nearest the heart (when there are fewer tiles than creatures, the tiles are used again).
void placeKeeperForce(GameMap& gameMap, int32_t attackedSeatId)
{
    Seat* seat = gameMap.getSeatById(attackedSeatId);
    if((seat == nullptr) || sForceClasses.empty())
        return;

    std::vector<Tile*> tiles;
    uint32_t placed = 0;
    for(const std::string& className : sForceClasses)
    {
        const CreatureDefinition* definition = gameMap.getClassDescription(className);
        if(definition == nullptr)
        {
            OD_LOG_ERR("Reference keeper force of unknown creature class=" + className);
            continue;
        }

        Ogre::Vector3 position(0.0f, 0.0f, 0.0f);
        Creature* creature = new Creature(&gameMap, definition, seat, position);
        if(tiles.empty())
            tiles = tilesAroundHeart(gameMap, seat, *creature, sForceClasses.size());
        if(tiles.empty())
        {
            OD_LOG_ERR("No walkable tile at the dungeon heart of seat " + Helper::toString(attackedSeatId));
            delete creature;
            return;
        }

        Tile* tile = tiles[placed % tiles.size()];
        creature->setPosition(Ogre::Vector3(static_cast<Ogre::Real>(tile->getX()),
            static_cast<Ogre::Real>(tile->getY()), 0.0f));
        creature->setLevel(sForceLevel);
        creature->setHP(creature->getMaxHp());
        creature->addToGameMap();
        creature->createMesh();
        creature->setPosition(creature->getPosition());
        ++placed;
    }
    OD_LOG_INF("Reference keeper force placed at the heart of seat " + Helper::toString(attackedSeatId) + ": "
        + Helper::toString(placed) + " creatures of level " + Helper::toString(sForceLevel));
}

//! \brief Counts the fighting creatures (not workers) in the player's hand and the drops of one since the last turn.
void noteHand(Player* keeper)
{
    if(keeper == nullptr)
        return;

    const uint32_t fighters = keeper->numFightingCreaturesInHand();
    // The hand player counts his own drops (he may pick up and drop in the same turn)
    if((fighters < sHandFighters) && !sHandPlayer)
        sHandDrops += sHandFighters - fighters;
    sHandFighters = fighters;
}

//! \brief Tiles (largest of the x and y distance) a keeper fighter must stand away from every raid member before the
//! hand player carries it into the fight.
const int32_t HAND_PLAYER_MIN_DISTANCE = 6;

//! \brief The largest of the x and y distance between two creatures in tiles.
int32_t creatureDistance(const Creature& first, const Creature& second)
{
    Tile* a = first.getPositionTile();
    Tile* b = second.getPositionTile();
    if((a == nullptr) || (b == nullptr))
        return 0;

    return std::max(std::abs(a->getX() - b->getX()), std::abs(a->getY() - b->getY()));
}

//! \brief A model of a keeper who drops his fighters straight into the fight with the hand (the play the campaign hand
//! limit restrains): once per turn, when the hand rules allow it, he picks up the keeper fighter farthest from the raid
//! that does not fight and stands more than HAND_PLAYER_MIN_DISTANCE tiles from every raid member, and drops it next
//! to the raid member nearest his dungeon heart. Each drop of a fighting creature is counted.
void handPlayer(GameMap& gameMap, Player* keeper)
{
    if(!sHandPlayer || (keeper == nullptr) || (keeper->getSeat() == nullptr))
        return;

    Seat* seat = keeper->getSeat();
    std::vector<Creature*> raiders;
    for(const RaidGroupData& group : gameMap.getRaid().getGroups())
    {
        for(const std::string& name : group.mSpawned)
        {
            Creature* creature = gameMap.getCreature(name);
            if((creature != nullptr) && isStanding(*creature) && (creature->getPositionTile() != nullptr))
                raiders.push_back(creature);
        }
    }
    if(raiders.empty())
        return;

    // The raid member nearest the heart is where the fight is carried to
    Tile* heart = nullptr;
    for(Room* room : gameMap.getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        heart = room->getCentralTile();
        break;
    }
    Creature* target = raiders.front();
    if(heart != nullptr)
    {
        int32_t best = -1;
        for(Creature* raider : raiders)
        {
            Tile* tile = raider->getPositionTile();
            const int32_t distance = std::max(std::abs(tile->getX() - heart->getX()), std::abs(tile->getY() - heart->getY()));
            if((best < 0) || (distance < best))
            {
                best = distance;
                target = raider;
            }
        }
    }

    // A creature still held from an earlier turn is dropped first
    if(keeper->numObjectsInHand() == 0)
    {
        Creature* chosen = nullptr;
        int32_t chosenDistance = HAND_PLAYER_MIN_DISTANCE;
        for(Creature* creature : gameMap.getCreaturesBySeat(seat))
        {
            if(creature->getDefinition()->isWorker() || !isStanding(*creature) ||
               creature->isActionInList(CreatureActionType::fight) || !keeper->isHandLimitPickupAllowed(creature) ||
               !creature->tryPickup(seat))
                continue;

            int32_t nearest = -1;
            for(Creature* raider : raiders)
            {
                const int32_t distance = creatureDistance(*creature, *raider);
                if((nearest < 0) || (distance < nearest))
                    nearest = distance;
            }
            if(nearest > chosenDistance)
            {
                chosenDistance = nearest;
                chosen = creature;
            }
        }
        if(chosen == nullptr)
            return;

        keeper->pickUpEntity(chosen);
        if(keeper->numObjectsInHand() == 0)
            return;
    }

    Tile* targetTile = target->getPositionTile();
    std::vector<Tile*> dropTiles(1, targetTile);
    for(Tile* neighbor : targetTile->getAllNeighbors())
        dropTiles.push_back(neighbor);
    for(Tile* tile : dropTiles)
    {
        if((tile == nullptr) || !keeper->isDropHandPossible(tile))
            continue;

        keeper->dropHand(tile);
        ++sHandDrops;
        return;
    }
}
}

//! \brief Splits the comma-separated classes; an empty text means no reference keeper force.
void RaidSimulation::setKeeperForce(const std::string& classes, int32_t level)
{
    sForceClasses.clear();
    std::stringstream ss(classes);
    std::string className;
    while(std::getline(ss, className, ','))
    {
        if(!className.empty())
            sForceClasses.push_back(className);
    }
    sForceLevel = std::max(1, level);
}

//! \brief Remembers whether the hand limit applies in the next run.
void RaidSimulation::setHandLimit(bool handLimit)
{
    sHandLimit = handLimit;
}

//! \brief Remembers whether the model keeper of handPlayer uses his hand in the next run.
void RaidSimulation::setHandPlayer(bool handPlayer)
{
    sHandPlayer = handPlayer;
}

//! \brief Loads the level on a server without socket, runs the turns and writes one line per turn; the result line
//! names how the raid ended.
int RaidSimulation::run(const std::string& levelFile, int32_t seconds, uint32_t seed, const std::string& outFile,
    bool keeperAi)
{
    sActive = true;
    sExitCode = codeDone;
    if(seconds <= 0)
    {
        std::cout << "RAIDSIM usage error: --seconds must be greater than 0" << std::endl;
        sExitCode = codeUsage;
        return sExitCode;
    }

    std::ofstream out(outFile.c_str());
    if(!out.good())
    {
        std::cout << "RAIDSIM usage error: cannot write " << outFile << std::endl;
        sExitCode = codeUsage;
        return sExitCode;
    }

    ResourceManager& resMgr = ResourceManager::getSingleton();
    Random::initialize();
    const uint32_t usedSeed = (seed == 0) ? 1 : seed;
    Random::setSeed(usedSeed);
    ConfigManager configManager(resMgr.getConfigPath(), "", resMgr.getSoundPath());

    std::chrono::steady_clock::time_point wallStart = std::chrono::steady_clock::now();
    Player::setHandLimitForced(sHandLimit);
    ODServer server;
    const int32_t attackedSeatId = server.startHeadlessGame(levelFile, keeperAi);
    if(attackedSeatId < 0)
    {
        std::cout << "RAIDSIM load error: the level could not be started: " << levelFile << std::endl;
        sExitCode = codeLoadError;
        return sExitCode;
    }

    GameMap& gameMap = *server.getGameMap();
    if(!gameMap.getRaid().hasRaid())
    {
        std::cout << "RAIDSIM load error: the level has no raid: " << levelFile << std::endl;
        sExitCode = codeLoadError;
        return sExitCode;
    }

    readPhase1Goals(levelFile, attackedSeatId);

    // The seed again right before the first turn, so that loading does not change what the turns draw
    Random::setSeed(usedSeed);
    out << "# level=" << levelFile << " seed=" << usedSeed << " keeperAi=" << (keeperAi ? 1 : 0)
        << " turnsPerSecond=" << ODApplication::turnsPerSecond << " phase1Goals=" << sPhase1Goals.size()
        << " force=" << sForceClasses.size() << " forceLevel=" << sForceLevel << " handLimit=" << (sHandLimit ? 1 : 0)
        << " handPlayer=" << (sHandPlayer ? 1 : 0)
        << "\n";
    writeHeader(out);

    const double turnSeconds = 1.0 / ODApplication::turnsPerSecond;
    const int64_t maxTurns = static_cast<int64_t>(std::ceil(seconds * ODApplication::turnsPerSecond));
    std::string result = "timeout";
    Player* keeper = nullptr;
    for(Player* player : gameMap.getPlayers())
    {
        if((player->getSeat() != nullptr) && (player->getSeat()->getId() == attackedSeatId))
            keeper = player;
    }

    const RaidManager& raid = gameMap.getRaid();
    bool forcePlaced = false;
    sHandDrops = 0;
    sHandFighters = 0;
    for(int64_t turn = 0; turn < maxTurns; ++turn)
    {
        server.runHeadlessTurn(turnSeconds);
        // The reference keeper force stands at the heart when the gate opens
        if(!forcePlaced && !raid.isGateClosed())
        {
            placeKeeperForce(gameMap, attackedSeatId);
            forcePlaced = true;
        }
        handPlayer(gameMap, keeper);
        noteHand(keeper);
        writeTurn(out, gameMap, attackedSeatId);
        if(LogManager::getSingleton().getCriticalCount() > 0)
        {
            result = "error";
            break;
        }
        if(raid.isStateMet("escaped", 0))
        {
            result = "escaped";
            break;
        }
        if((keeper != nullptr) && keeper->getHasLost())
        {
            result = "heartlost";
            break;
        }
        if(raid.isStateMet("defeated", 0))
        {
            result = "defeated";
            break;
        }
    }

    const double wallSeconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    out << "# result=" << result << " turn=" << gameMap.getTurnNumber() << " seconds="
        << (static_cast<double>(gameMap.getTurnNumber()) / ODApplication::turnsPerSecond)
        << " wallSeconds=" << wallSeconds << "\n";
    out.close();
    std::cout << "RAIDSIM result=" << result << " turn=" << gameMap.getTurnNumber() << " wallSeconds=" << wallSeconds
        << std::endl;
    if(result == "error")
        sExitCode = codeRunError;

    server.stopServer();
    return sExitCode;
}

bool RaidSimulation::isActive()
{
    return sActive;
}

int RaidSimulation::getExitCode()
{
    return sExitCode;
}

//! \brief Columns: turn, game seconds, gate open, raid groups arrived, then per side (raid, keeper fighters) standing
//! count, hit points, maximum hit points, fighting count, members at their formation place and members with one,
//! carried gold; then raid leaders fleeing and escaped, keeper groups, standing keeper group members, retreating keeper
//! and raid groups, the smallest distance in tiles between a standing raid member and a standing keeper fighter (-1 without
//! both), the gold stored by the keeper, the hit points of his dungeon heart, 1 once he lost, the fleeing creatures of
//! the raid and of the keeper, the highest id a combat group got so far (how many groups were formed), the summed
//! distance of the raid and keeper group members to their formation places and the spread of the standing raid (mean
//! distance of its members to their centre), the gold stored in the keeper's treasuries alone and the gold the raid
//! took so far from treasuries and from dungeon hearts (what a member's carried gold grew by while it stood there), the
//! phase-1 main goals of the keeper reached now and their number (see readPhase1Goals), the ground tiles he claimed, the
//! tiles of his rooms and the gold he mined so far; the fighting creatures in his hand, the fighting creatures he
//! dropped from his hand so far and the seconds left of his hand cooldown.
void RaidSimulation::writeHeader(std::ostream& os)
{
    os << "turn\tseconds\tgateOpen\tarrived"
        << "\traidAlive\traidHp\traidMaxHp\traidFighting\traidInPlace\traidWithPlace\traidGold"
        << "\tkeeperAlive\tkeeperHp\tkeeperMaxHp\tkeeperFighting\tkeeperInPlace\tkeeperWithPlace\tkeeperCarried"
        << "\tleadersFleeing\tleadersEscaped\tkeeperGroups\tkeeperGroupMembers\tkeeperRetreating\traidRetreating"
        << "\tminDistance\tkeeperGold\theartHp\tkeeperLost\traidFleeing\tkeeperFleeing\tmaxGroupId"
        << "\traidPlaceDistance\tkeeperPlaceDistance\traidSpread\ttreasuryGold\tplunderedTreasury\tplunderedHeart"
        << "\tphase1Reached\tphase1Total\tclaimedTiles\troomTiles\tgoldMined\thandFighters\thandDrops\thandCooldown\n";
}

//! \brief Counts both sides from the creatures of the map, the raid groups and the combat groups.
void RaidSimulation::writeTurn(std::ostream& os, GameMap& gameMap, int32_t attackedSeatId)
{
    const RaidManager& raid = gameMap.getRaid();
    const CombatGroupManager& groups = gameMap.getCombatGroups();
    Seat* keeperSeat = gameMap.getSeatById(attackedSeatId);

    SideState raidSide;
    SideState keeperSide;
    uint32_t arrived = 0;
    uint32_t fleeing = 0;
    uint32_t escaped = 0;
    std::vector<Creature*> raidStanding;
    for(const RaidGroupData& group : raid.getGroups())
    {
        if(group.mArrived)
            ++arrived;
        if(group.mLeaderState == RaidLeaderState::fleeing)
            ++fleeing;
        else if(group.mLeaderState == RaidLeaderState::escaped)
            ++escaped;

        for(const std::string& name : group.mSpawned)
        {
            Creature* creature = gameMap.getCreature(name);
            if((creature == nullptr) || !isStanding(*creature))
                continue;

            addToSide(raidSide, *creature, groups);
            raidStanding.push_back(creature);
            notePlunder(*creature);
        }
    }

    std::vector<Creature*> keeperStanding;
    for(Creature* creature : gameMap.getCreaturesBySeat(keeperSeat))
    {
        if(creature->getDefinition()->isWorker() || !isStanding(*creature))
            continue;

        addToSide(keeperSide, *creature, groups);
        keeperStanding.push_back(creature);
    }

    int32_t minDistance = -1;
    for(Creature* raider : raidStanding)
    {
        Tile* raiderTile = raider->getPositionTile();
        for(Creature* defender : keeperStanding)
        {
            Tile* defenderTile = defender->getPositionTile();
            const int32_t distance = std::max(std::abs(raiderTile->getX() - defenderTile->getX()),
                std::abs(raiderTile->getY() - defenderTile->getY()));
            if((minDistance < 0) || (distance < minDistance))
                minDistance = distance;
        }
    }

    uint32_t keeperGroups = 0;
    uint32_t keeperMembers = 0;
    uint32_t keeperRetreating = 0;
    uint32_t raidRetreating = 0;
    uint32_t maxGroupId = 0;
    for(const CombatGroup& group : groups.getGroups())
    {
        maxGroupId = std::max(maxGroupId, group.mId);
        if(group.mIsRaid)
        {
            if(group.mRetreating)
                ++raidRetreating;
            continue;
        }
        if(group.mSeatId != attackedSeatId)
            continue;

        ++keeperGroups;
        for(const std::string& member : group.mMembers)
        {
            Creature* creature = gameMap.getCreature(member);
            if((creature != nullptr) && isStanding(*creature))
                ++keeperMembers;
        }
        if(group.mRetreating)
            ++keeperRetreating;
    }

    bool keeperLost = false;
    if((keeperSeat != nullptr) && (keeperSeat->getPlayer() != nullptr))
        keeperLost = keeperSeat->getPlayer()->getHasLost();

    const int64_t turn = gameMap.getTurnNumber();
    os << turn << "\t" << (static_cast<double>(turn) / ODApplication::turnsPerSecond)
        << "\t" << (raid.isGateClosed() ? 0 : 1) << "\t" << arrived
        << "\t" << raidSide.mAlive << "\t" << raidSide.mHp << "\t" << raidSide.mMaxHp << "\t" << raidSide.mFighting
        << "\t" << raidSide.mInPlace << "\t" << raidSide.mWithPlace << "\t" << raidSide.mGold
        << "\t" << keeperSide.mAlive << "\t" << keeperSide.mHp << "\t" << keeperSide.mMaxHp
        << "\t" << keeperSide.mFighting << "\t" << keeperSide.mInPlace << "\t" << keeperSide.mWithPlace
        << "\t" << keeperSide.mGold
        << "\t" << fleeing << "\t" << escaped << "\t" << keeperGroups << "\t" << keeperMembers
        << "\t" << keeperRetreating << "\t" << raidRetreating << "\t" << minDistance
        << "\t" << ((keeperSeat == nullptr) ? 0.0 : storedGold(gameMap, keeperSeat))
        << "\t" << ((keeperSeat == nullptr) ? 0.0 : heartHp(gameMap, keeperSeat))
        << "\t" << (keeperLost ? 1 : 0) << "\t" << raidSide.mFleeing << "\t" << keeperSide.mFleeing
        << "\t" << maxGroupId << "\t" << raidSide.mPlaceDistance << "\t" << keeperSide.mPlaceDistance
        << "\t" << spread(raidStanding) << "\t" << ((keeperSeat == nullptr) ? 0.0 : treasuryGold(gameMap, keeperSeat))
        << "\t" << sPlunderedTreasury << "\t" << sPlunderedHeart;

    uint32_t claimed = 0;
    uint32_t roomTiles = 0;
    countTiles(gameMap, keeperSeat, claimed, roomTiles);
    os << "\t" << phase1Reached(gameMap, attackedSeatId) << "\t" << sPhase1Goals.size() << "\t" << claimed
        << "\t" << roomTiles << "\t" << ((keeperSeat == nullptr) ? 0 : keeperSeat->getGoldMined());

    Player* keeper = (keeperSeat == nullptr) ? nullptr : keeperSeat->getPlayer();
    os << "\t" << sHandFighters << "\t" << sHandDrops << "\t"
        << ((keeper == nullptr) ? 0.0 : keeper->getHandCooldownSeconds()) << "\n";
}
