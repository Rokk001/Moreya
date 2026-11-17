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

#include "rooms/RoomToilet.h"

#include "entities/BuildingObject.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/RoomObjectBounds.h"
#include "gamemap/RoomObjectNavigation.h"
#include "rooms/RoomManager.h"
#include "rooms/ToiletLayout.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"

#include <algorithm>
#include <cmath>

const std::string RoomToiletName = "Toilet";
const std::string RoomToiletNameDisplay = "Toilet room";
const RoomType RoomToilet::mRoomType = RoomType::toilet;
const TileVisual RoomToilet::mRoomVisual = TileVisual::toiletRoom;

namespace
{
//! \brief Distance (tiles) kept between the front of a seat and the staging point, beyond the walking radius.
const float STAGING_MARGIN = 0.05f;
//! \brief Distance (tiles) in front of the seat tried when the full one is blocked.
const float STAGING_SHORT = 0.3f;

//! \brief Builds, prices and loads toilet rooms; registered for RoomType::toilet.
class RoomToiletFactory : public RoomFactory
{
    RoomType getRoomType() const override
    { return RoomToilet::mRoomType; }

    TileVisual getVisualType() const override
    { return RoomToilet::mRoomVisual; }

    const std::string& getName() const override
    { return RoomToiletName; }

    const std::string& getNameReadable() const override
    { return RoomToiletNameDisplay; }

    int getCostPerTile() const override
    { return ConfigManager::getSingleton().getRoomConfigInt32("ToiletCostPerTile"); }

    void checkBuildRoom(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    {
        checkBuildRoomDefault(gameMap, RoomToilet::mRoomType, inputManager, inputCommand);
    }

    bool buildRoom(GameMap* gameMap, Player* player, ODPacket& packet) const override
    {
        std::vector<Tile*> tiles;
        if(!getRoomTilesDefault(tiles, gameMap, player, packet))
            return false;

        int32_t pricePerTarget = RoomManager::costPerTile(RoomToilet::mRoomType);
        int32_t price = static_cast<int32_t>(tiles.size()) * pricePerTarget;
        if(!gameMap->withdrawFromTreasuries(price, player->getSeat()))
            return false;

        RoomToilet* room = new RoomToilet(gameMap);
        return buildRoomDefault(gameMap, room, player->getSeat(), tiles);
    }

    void checkBuildRoomEditor(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    {
        checkBuildRoomDefaultEditor(gameMap, RoomToilet::mRoomType, inputManager, inputCommand);
    }

    bool buildRoomEditor(GameMap* gameMap, ODPacket& packet) const override
    {
        RoomToilet* room = new RoomToilet(gameMap);
        return buildRoomDefaultEditor(gameMap, room, packet);
    }

    //! \brief Creates an empty room of this type, for a room that has to be split in two.
    Room* createRoom(GameMap* gameMap) const override
    { return new RoomToilet(gameMap); }

    Room* getRoomFromStream(GameMap* gameMap, std::istream& is) const override
    {
        RoomToilet* room = new RoomToilet(gameMap);
        if(!Room::importRoomFromStream(*room, is))
        {
            OD_LOG_ERR("Error while building a room from the stream");
        }
        return room;
    }

    bool buildRoomOnTiles(GameMap* gameMap, Player* player, const std::vector<Tile*>& tiles, bool noFee =false) const override
    {
        int32_t pricePerTarget = RoomManager::costPerTile(RoomToilet::mRoomType);
        int32_t price = static_cast<int32_t>(tiles.size()) * pricePerTarget;
        if(!noFee)
            if(!gameMap->withdrawFromTreasuries(price, player->getSeat()))
                return false;
        RoomToilet* room = new RoomToilet(gameMap);
        return buildRoomDefault(gameMap, room, player->getSeat(), tiles);
    }
};

// Register the factory
static RoomRegister reg(new RoomToiletFactory);

//! \brief Collects the toilet rooms the creature may use: the ones of its seat, or all of them when its seat has none.
//! \param creature The creature that looks for a toilet.
//! \param rooms Filled with the rooms.
void collectToiletRooms(const Creature& creature, std::vector<RoomToilet*>& rooms)
{
    rooms.clear();
    std::vector<Room*> allRooms = creature.getGameMap()->getRoomsByType(RoomType::toilet);
    for(Room* room : allRooms)
    {
        if(room->getSeat() == creature.getSeat())
            rooms.push_back(static_cast<RoomToilet*>(room));
    }

    if(!rooms.empty())
        return;

    for(Room* room : allRooms)
        rooms.push_back(static_cast<RoomToilet*>(room));
}
}

RoomToilet::RoomToilet(GameMap* gameMap) :
    Room(gameMap)
{
    setMeshName("Room");
}

int64_t RoomToilet::getReservationEndTurn() const
{
    ConfigManager& config = ConfigManager::getSingleton();
    double turns = config.getDirtConfigDouble("ToiletUseTurns") * config.getDirtConfigDouble("ToiletReserveFactor");
    return getGameMap()->getTurnNumber() + static_cast<int64_t>(turns);
}

bool RoomToilet::isTileFree(const Tile* tile, const Creature* user) const
{
    if((tile->getCoveringRoom() != this) || !hasSeatOn(tile))
        return false;

    std::map<const Tile*, Reservation>::const_iterator it = mReserved.find(tile);
    if(it == mReserved.end())
        return true;

    if(it->second.mUser == user)
        return true;

    return getGameMap()->getTurnNumber() >= it->second.mExpireTurn;
}

bool RoomToilet::reserveTile(const Tile* tile, const Creature* user)
{
    if(!isTileFree(tile, user))
        return false;

    Reservation& reservation = mReserved[tile];
    reservation.mUser = user;
    reservation.mExpireTurn = getReservationEndTurn();
    return true;
}

void RoomToilet::releaseTile(const Tile* tile, const Creature* user)
{
    std::map<const Tile*, Reservation>::iterator it = mReserved.find(tile);
    if(it == mReserved.end())
        return;

    if(it->second.mUser == user)
        mReserved.erase(it);
}

bool RoomToilet::hasOpenCreatureSpot(Creature* c)
{
    for(const std::pair<Tile* const, BuildingObject*>& entry : mBuildingObjects)
    {
        if(isTileFree(entry.first, c))
            return true;
    }

    return false;
}

bool RoomToilet::canBeUsedBy(const Creature& creature) const
{
    if(getSeat() == creature.getSeat())
        return true;

    return getGameMap()->numRoomsByTypeAndSeat(RoomType::toilet, creature.getSeat()) == 0;
}

bool RoomToilet::hasSeatOn(const Tile* tile) const
{
    for(const std::pair<Tile* const, BuildingObject*>& entry : mBuildingObjects)
    {
        if(entry.first == tile)
            return true;
    }
    return false;
}

bool RoomToilet::getSeatPlace(const Tile* tile, Ogre::Vector2& place, Ogre::Vector2& facing) const
{
    for(const std::pair<Tile* const, BuildingObject*>& entry : mBuildingObjects)
    {
        if(entry.first != tile)
            continue;

        const float angle = static_cast<float>(entry.second->getRotationAngle()) * RoomObjectPath::degreesToRadians;
        const float cosine = std::cos(angle);
        const float sine = std::sin(angle);
        // The seat mesh has its back at +y: the user sits at (0, toiletSeatPlaceY) and faces -y, turned by the angle
        const Ogre::Vector2 centre(entry.second->getPosition().x, entry.second->getPosition().y);
        place = centre + Ogre::Vector2(-sine * RoomObjectPath::toiletSeatPlaceY, cosine * RoomObjectPath::toiletSeatPlaceY);
        facing = Ogre::Vector2(sine, -cosine);
        return true;
    }
    return false;
}

std::vector<Ogre::Vector2> RoomToilet::getSeatStagingPoints(Creature& creature, const Tile* tile) const
{
    std::vector<Ogre::Vector2> points;
    Ogre::Vector2 place;
    Ogre::Vector2 facing;
    if(!getSeatPlace(tile, place, facing))
        return points;

    const BuildingObject* seat = nullptr;
    for(const std::pair<Tile* const, BuildingObject*>& entry : mBuildingObjects)
    {
        if(entry.first == tile)
            seat = entry.second;
    }
    // The seat itself is the piece the user steps onto; every other piece of furniture stays an obstacle
    const std::vector<RoomObjectPath::Obstacle> obstacles = RoomObjectNavigation::bodyObstacles(creature, seat);
    // The front of the seat lies at mesh y minY, that is toiletSeatPlaceY - minY in front of the place
    float front = RoomObjectPath::toiletSeatPlaceY;
    for(const RoomObjectPath::MeshBounds& bounds : RoomObjectPath::meshBounds)
    {
        if(RoomObjectPath::TOILET_SEAT_MESH == bounds.name)
            front -= bounds.minY;
    }
    const Ogre::Vector2 side(-facing.y, facing.x);
    const Ogre::Vector2 directions[] = { facing, (facing + side * 0.5f).normalisedCopy(), (facing - side * 0.5f).normalisedCopy() };
    const float distances[] = { front + RoomObjectNavigation::clearance(creature) + STAGING_MARGIN, front + STAGING_SHORT };
    for(float distance : distances)
    {
        for(const Ogre::Vector2& direction : directions)
        {
            const Ogre::Vector2 staging = place + direction * distance;
            Tile* stagingTile = getGameMap()->getTile(Helper::round(staging.x), Helper::round(staging.y));
            if((stagingTile == nullptr) || stagingTile->isFullTile() || !creature.canGoThroughTile(stagingTile))
                continue;

            if(!RoomObjectPath::clearPoint(obstacles, staging) || !RoomObjectPath::clearSegment(obstacles, staging, place))
                continue;

            points.push_back(staging);
        }
    }
    return points;
}

void RoomToilet::updateActiveSpots(GameMap* gameMap)
{
    Room::updateActiveSpots(gameMap);

    // The seats are created by the server and sent to the clients like every other building object
    if(!getIsOnServerMap())
        return;

    if(gameMap == nullptr)
        gameMap = getGameMap();

    // The seats the layout of the room asks for: rows along the edge, a free lane in the middle
    std::vector<ToiletLayout::Coord> coords;
    for(Tile* tile : mCoveredTiles)
        coords.push_back(ToiletLayout::Coord(tile->getX(), tile->getY()));
    std::map<ToiletLayout::Coord, double> wanted;
    ToiletLayout::chooseSeats(coords, wanted);

    // Seats that are not wanted any more (lost tile, lane tile, other angle) go away together with their reservation
    std::vector<Tile*> seatsToRemove;
    for(const std::pair<Tile* const, BuildingObject*>& entry : mBuildingObjects)
    {
        std::map<ToiletLayout::Coord, double>::const_iterator it =
            wanted.find(ToiletLayout::Coord(entry.first->getX(), entry.first->getY()));
        if((it == wanted.end()) || (std::abs(it->second - entry.second->getRotationAngle()) > 0.5))
            seatsToRemove.push_back(entry.first);
    }
    for(Tile* tile : seatsToRemove)
        removeBuildingObject(tile);

    for(std::map<const Tile*, Reservation>::iterator it = mReserved.begin(); it != mReserved.end();)
    {
        if((it->first->getCoveringRoom() != this) || !hasSeatOn(it->first))
            it = mReserved.erase(it);
        else
            ++it;
    }

    // Every wanted seat that is missing is placed
    for(Tile* tile : mCoveredTiles)
    {
        std::map<ToiletLayout::Coord, double>::const_iterator it = wanted.find(ToiletLayout::Coord(tile->getX(), tile->getY()));
        if((it == wanted.end()) || (mBuildingObjects.find(tile) != mBuildingObjects.end()))
            continue;

        BuildingObject* seat = new BuildingObject(gameMap, *this, RoomObjectPath::TOILET_SEAT_MESH, *tile, it->second, false);
        addBuildingObject(tile, seat, gameMap);
        seat->createMesh();
    }
}

Tile* RoomToilet::findFreeToiletTile(Creature& creature)
{
    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
        return nullptr;

    std::vector<RoomToilet*> rooms;
    collectToiletRooms(creature, rooms);

    std::vector<Tile*> freeTiles;
    for(RoomToilet* room : rooms)
    {
        for(const std::pair<Tile* const, BuildingObject*>& entry : room->mBuildingObjects)
        {
            Tile* tile = entry.first;
            if(!room->isTileFree(tile, &creature))
                continue;

            // A seat the creature cannot step onto without touching other furniture is no seat for it
            if(room->getSeatStagingPoints(creature, tile).empty())
                continue;

            if(!creature.getGameMap()->pathExists(&creature, myTile, tile))
                continue;

            freeTiles.push_back(tile);
        }
    }

    if(freeTiles.empty())
        return nullptr;

    Tile* chosenTile = nullptr;
    creature.getGameMap()->findBestPath(&creature, myTile, freeTiles, chosenTile);
    return chosenTile;
}

bool RoomToilet::hasToiletRoomFor(const Creature& creature)
{
    std::vector<RoomToilet*> rooms;
    collectToiletRooms(creature, rooms);
    for(RoomToilet* room : rooms)
    {
        if(!room->mBuildingObjects.empty())
            return true;
    }

    return false;
}

Tile* RoomToilet::findWaitTile(Creature& creature, bool& waiting)
{
    waiting = false;
    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
        return nullptr;

    const int radius = static_cast<int>(ConfigManager::getSingleton().getDirtConfigDouble("ToiletWaitRadius"));
    GameMap* gameMap = creature.getGameMap();
    std::vector<RoomToilet*> rooms;
    collectToiletRooms(creature, rooms);

    std::vector<Tile*> waitTiles;
    for(RoomToilet* room : rooms)
    {
        for(Tile* seatTile : room->mCoveredTiles)
        {
            for(int dx = -radius; dx <= radius; ++dx)
            {
                for(int dy = -radius; dy <= radius; ++dy)
                {
                    Tile* tile = gameMap->getTile(seatTile->getX() + dx, seatTile->getY() + dy);
                    if((tile == nullptr) || tile->isFullTile() || !creature.canGoThroughTile(tile))
                        continue;

                    // The creature already waits close to a toilet room
                    if(tile == myTile)
                    {
                        waiting = true;
                        return nullptr;
                    }

                    // Outside the room, so that the seats stay free for the creatures that use them
                    if(tile->getCoveringRoom() == room)
                        continue;

                    if(std::find(waitTiles.begin(), waitTiles.end(), tile) != waitTiles.end())
                        continue;

                    if(!gameMap->pathExists(&creature, myTile, tile))
                        continue;

                    waitTiles.push_back(tile);
                }
            }
        }
    }

    if(waitTiles.empty())
        return nullptr;

    Tile* chosenTile = nullptr;
    gameMap->findBestPath(&creature, myTile, waitTiles, chosenTile);
    return chosenTile;
}
