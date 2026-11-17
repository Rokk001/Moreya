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

#ifndef ROOMTOILET_H
#define ROOMTOILET_H

#include "rooms/Room.h"
#include "rooms/RoomType.h"

#include <OgreVector2.h>

#include <cstdint>
#include <map>
#include <vector>

class Creature;
class Tile;
enum class TileVisual;

//! \brief A room with toilet seats in rows along its edge and a free walking lane in the middle (ToiletLayout). A
//! creature that has to relieve itself reserves a free seat, steps onto it, uses it for a random time and leaves the
//! room a little dirtier. The seats are solid furniture: only the user of a seat steps onto it. The creatures do not
//! work in this room: they are sent here by their urge (see CreatureActionSearchToilet and CreatureActionUseToilet).
class RoomToilet: public Room
{
public:
    //! \brief Creates an empty toilet room on the given map.
    RoomToilet(GameMap* gameMap);

    //! \brief Returns the type of this room (RoomType::toilet).
    RoomType getType() const override
    { return mRoomType; }

    //! \brief True when at least one seat of the room is free for the creature.
    bool hasOpenCreatureSpot(Creature* c) override;

    //! \brief Places the seats the layout of the room asks for (ToiletLayout::chooseSeats) and removes every other seat,
    //! also the seats whose angle changed because the room grew or shrank. Reservations of tiles that no longer carry
    //! a seat are dropped.
    void updateActiveSpots(GameMap* gameMap = nullptr) override;

    //! \brief True when the tile carries a seat of this room that is not reserved by another creature (a reservation
    //! also ends after ToiletUseTurns times ToiletReserveFactor turns without being renewed).
    //! \param tile The tile of the seat.
    //! \param user The creature that wants the seat; its own reservation does not count.
    bool isTileFree(const Tile* tile, const Creature* user) const;

    //! \brief Reserves (or renews the reservation of) the seat on the tile for the creature.
    //! \return False if the tile is not a seat of this room or another creature holds it.
    bool reserveTile(const Tile* tile, const Creature* user);

    //! \brief Drops the reservation of the tile when the given creature holds it.
    void releaseTile(const Tile* tile, const Creature* user);

    //! \brief True when the creature may use the seats of this room: the room belongs to its seat, or its
    //! seat has no toilet room at all (then any toilet room will do).
    bool canBeUsedBy(const Creature& creature) const;

    //! \brief True when the tile carries a seat of this room.
    bool hasSeatOn(const Tile* tile) const;

    //! \brief The place where the user of the seat on the tile sits (world x, y; the seat top is
    //! RoomObjectPath::toiletSeatTop higher) and the direction it faces (away from the wall).
    //! \return False when the tile carries no seat of this room.
    bool getSeatPlace(const Tile* tile, Ogre::Vector2& place, Ogre::Vector2& facing) const;

    //! \brief The points in front of the seat on the tile from where the creature steps straight onto the seat
    //! without touching other furniture, the farther (full clearance) ones first. Empty when there is none.
    std::vector<Ogre::Vector2> getSeatStagingPoints(Creature& creature, const Tile* tile) const;

    //! \brief Finds the toilet seat nearest by path that the creature may use, that is free and that the creature can
    //! step onto from a point in front of it without touching other furniture.
    //! \return The tile of the seat, nullptr if there is none or none can be reached.
    static Tile* findFreeToiletTile(Creature& creature);

    //! \brief Tells whether the creature has a toilet room it may use at all (free seats or not).
    static bool hasToiletRoomFor(const Creature& creature);

    //! \brief Finds the tile where a creature waits when every seat is busy: a reachable tile within
    //! ToiletWaitRadius tiles of a toilet room, outside the room when possible.
    //! \param waiting Set to true when the creature already stands within that distance.
    //! \return The tile to walk to, nullptr if there is none or the creature already waits.
    static Tile* findWaitTile(Creature& creature, bool& waiting);

    static const RoomType mRoomType;
    static const TileVisual mRoomVisual;

private:
    //! \brief The reservation of a seat.
    struct Reservation
    {
        Reservation() :
            mUser(nullptr),
            mExpireTurn(0)
        {}

        //! The creature that holds the seat; only compared, never dereferenced.
        const Creature* mUser;
        //! First turn on which the reservation no longer counts.
        int64_t mExpireTurn;
    };

    //! \brief Returns the turn on which a reservation made now ends.
    int64_t getReservationEndTurn() const;

    //! \brief The reservations by tile.
    std::map<const Tile*, Reservation> mReserved;
};

#endif // ROOMTOILET_H
