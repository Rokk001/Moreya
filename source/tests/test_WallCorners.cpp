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
#define BOOST_TEST_MODULE WallCorners
#include <boost/test/included/unit_test.hpp>

#include "gamemap/WallCorners.h"

#include <cstdlib>
#include <vector>

namespace
{
const int32_t MAP_SIZE = 16;
const int32_t KEEPER = 1;
const int32_t OTHER_KEEPER = 2;

//! What a test tile is made of
enum class Ground
{
    earth,
    rock,
    gold
};

//! A small map. Every tile starts as solid earth that nobody owns.
class TestMap : public WallCornerMap
{
public:
    //! \brief Creates a map of MAP_SIZE * MAP_SIZE solid earth tiles
    TestMap() :
        mWall(MAP_SIZE * MAP_SIZE, true),
        mGround(MAP_SIZE * MAP_SIZE, Ground::earth),
        mSeat(MAP_SIZE * MAP_SIZE, -1)
    {}

    //! \brief Returns the info of the tile as the game fills it from its map (WallCorners::makeTileInfo)
    WallCornerTileInfo getTileInfo(int32_t x, int32_t y) const override
    {
        if(!isInside(x, y))
            return WallCornerTileInfo();

        size_t index = indexOf(x, y);
        return WallCorners::makeTileInfo(mWall[index], mGround[index] == Ground::earth, mSeat[index]);
    }

    //! \brief Tells whether (x, y) lies on the map
    static bool isInside(int32_t x, int32_t y)
    {
        return (x >= 0) && (y >= 0) && (x < MAP_SIZE) && (y < MAP_SIZE);
    }

    //! \brief Makes the tile a floor claimed by the seat (as a dug and claimed tile, without the corner rule)
    void setFloor(int32_t x, int32_t y, int32_t seatId)
    {
        mWall[indexOf(x, y)] = false;
        mSeat[indexOf(x, y)] = seatId;
    }

    //! \brief Makes the tile a wall reinforced by the seat (as in a loaded level, without the corner rule)
    void setReinforcedWall(int32_t x, int32_t y, int32_t seatId)
    {
        mWall[indexOf(x, y)] = true;
        mSeat[indexOf(x, y)] = seatId;
    }

    //! \brief Makes the tile a solid tile of the given ground that nobody owns
    void setGround(int32_t x, int32_t y, Ground ground)
    {
        mGround[indexOf(x, y)] = ground;
    }

    //! \brief Claims the tile for the seat as a worker finishes it, then reinforces the corners that the claim
    //! completes without letting them look for further corners (as GameMap::reinforceWallCornersAfterClaim)
    void claim(int32_t x, int32_t y, int32_t seatId)
    {
        mSeat[indexOf(x, y)] = seatId;
        std::vector<WallCorner> corners;
        WallCorners::findCornersAfterClaim(*this, x, y, seatId, corners);
        apply(corners);
    }

    //! \brief Loads the map: reinforces every corner it already shows (as GameMap::reinforceWallCornersOnLoad).
    //! Returns how many corners were reinforced.
    size_t load()
    {
        std::vector<WallCorner> corners;
        WallCorners::findCornersOnLoad(*this, MAP_SIZE, MAP_SIZE, corners);
        apply(corners);
        return corners.size();
    }

    //! \brief Tells whether the tile is a wall reinforced by the seat
    bool isReinforcedBy(int32_t x, int32_t y, int32_t seatId) const
    {
        return mWall[indexOf(x, y)] && (mSeat[indexOf(x, y)] == seatId);
    }

    //! \brief Tells whether the tile is a wall that nobody has reinforced
    bool isUnreinforcedWall(int32_t x, int32_t y) const
    {
        return mWall[indexOf(x, y)] && (mSeat[indexOf(x, y)] < 0);
    }

    //! \brief Tells whether the tile is a floor claimed by the seat
    bool isFloorOf(int32_t x, int32_t y, int32_t seatId) const
    {
        return isInside(x, y) && !mWall[indexOf(x, y)] && (mSeat[indexOf(x, y)] == seatId);
    }

private:
    //! \brief Returns the index of the tile (x, y) in the tile vectors
    static size_t indexOf(int32_t x, int32_t y)
    {
        return static_cast<size_t>(y) * static_cast<size_t>(MAP_SIZE) + static_cast<size_t>(x);
    }

    //! \brief Reinforces the listed corners for their keepers
    void apply(const std::vector<WallCorner>& corners)
    {
        for(const WallCorner& corner : corners)
            mSeat[indexOf(corner.mX, corner.mY)] = corner.mSeatId;
    }

    std::vector<bool> mWall;
    std::vector<Ground> mGround;
    std::vector<int32_t> mSeat;
};

//! \brief Digs and claims a rectangle of floor for the seat, lower left tile (x0, y0)
void addFloor(TestMap& map, int32_t x0, int32_t y0, int32_t width, int32_t height, int32_t seatId)
{
    for(int32_t x = x0; x < x0 + width; ++x)
    {
        for(int32_t y = y0; y < y0 + height; ++y)
            map.setFloor(x, y, seatId);
    }
}

//! \brief Tells whether the tile (x, y) has a direct neighbour that is a floor of the seat
bool touchesFloorOf(const TestMap& map, int32_t x, int32_t y, int32_t seatId)
{
    return map.isFloorOf(x + 1, y, seatId) || map.isFloorOf(x - 1, y, seatId) ||
        map.isFloorOf(x, y + 1, seatId) || map.isFloorOf(x, y - 1, seatId);
}

//! \brief Tells whether the tile (x, y) has a diagonal neighbour that is a floor of the seat
bool touchesFloorOfAtCorner(const TestMap& map, int32_t x, int32_t y, int32_t seatId)
{
    return map.isFloorOf(x + 1, y + 1, seatId) || map.isFloorOf(x + 1, y - 1, seatId) ||
        map.isFloorOf(x - 1, y + 1, seatId) || map.isFloorOf(x - 1, y - 1, seatId);
}

//! \brief Claims, the way workers do, every wall that touches a floor of the seat directly, row by row
void reinforceWallsAlongFloor(TestMap& map, int32_t seatId)
{
    for(int32_t y = 0; y < MAP_SIZE; ++y)
    {
        for(int32_t x = 0; x < MAP_SIZE; ++x)
        {
            if(map.isUnreinforcedWall(x, y) && touchesFloorOf(map, x, y, seatId))
                map.claim(x, y, seatId);
        }
    }
}

//! \brief A 3 x 3 room of the keeper with its lower left tile at (5, 5); its four corner tiles are (4, 4), (8, 4),
//! (4, 8) and (8, 8). Only the walls are reinforced that the test names.
void addRoom(TestMap& map)
{
    addFloor(map, 5, 5, 3, 3, KEEPER);
}
} // namespace

//! \brief The corner becomes the keeper's reinforced wall as soon as the second of its two walls is reinforced, not
//! with the first.
BOOST_AUTO_TEST_CASE(test_CornerReinforcedWithSecondWall)
{
    TestMap map;
    addRoom(map);
    map.claim(4, 5, KEEPER);
    BOOST_CHECK(map.isUnreinforcedWall(4, 4));
    map.claim(5, 4, KEEPER);
    BOOST_CHECK(map.isReinforcedBy(4, 4, KEEPER));
}

//! \brief The corner becomes the keeper's when its diagonal floor is claimed after both walls were reinforced.
BOOST_AUTO_TEST_CASE(test_CornerReinforcedWithDiagonalFloor)
{
    TestMap map;
    map.setReinforcedWall(9, 10, KEEPER);
    map.setReinforcedWall(10, 9, KEEPER);
    map.setFloor(10, 10, -1);
    BOOST_CHECK(map.isUnreinforcedWall(9, 9));
    map.claim(10, 10, KEEPER);
    BOOST_CHECK(map.isReinforcedBy(9, 9, KEEPER));
}

//! \brief All four corners of a room are reinforced once workers have reinforced the walls along the room, and every
//! wall of the room then belongs to the keeper.
BOOST_AUTO_TEST_CASE(test_AllRoomCornersAfterClaims)
{
    TestMap map;
    addRoom(map);
    reinforceWallsAlongFloor(map, KEEPER);
    BOOST_CHECK(map.isReinforcedBy(4, 4, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(8, 4, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(4, 8, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(8, 8, KEEPER));
    for(int32_t x = 4; x <= 8; ++x)
    {
        BOOST_CHECK(map.isReinforcedBy(x, 4, KEEPER));
        BOOST_CHECK(map.isReinforcedBy(x, 8, KEEPER));
    }
    // Nothing beyond the ring of walls: the corners do not make the tiles next to them corners
    for(int32_t x = 3; x <= 9; ++x)
    {
        BOOST_CHECK(map.isUnreinforcedWall(x, 3));
        BOOST_CHECK(map.isUnreinforcedWall(x, 9));
        BOOST_CHECK(map.isUnreinforcedWall(3, x));
        BOOST_CHECK(map.isUnreinforcedWall(9, x));
    }
}

//! \brief A loaded map whose corners already have two reinforced walls of the keeper and his floor between them gets
//! exactly those four corners reinforced; loading the result again (a saved game) changes nothing.
BOOST_AUTO_TEST_CASE(test_CornersOnLoad)
{
    TestMap map;
    addRoom(map);
    for(int32_t i = 5; i <= 7; ++i)
    {
        map.setReinforcedWall(i, 4, KEEPER);
        map.setReinforcedWall(i, 8, KEEPER);
        map.setReinforcedWall(4, i, KEEPER);
        map.setReinforcedWall(8, i, KEEPER);
    }
    BOOST_CHECK_EQUAL(map.load(), 4u);
    BOOST_CHECK(map.isReinforcedBy(4, 4, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(8, 4, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(4, 8, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(8, 8, KEEPER));
    BOOST_CHECK_EQUAL(map.load(), 0u);
    BOOST_CHECK(map.isReinforcedBy(4, 4, KEEPER));
}

//! \brief Rock and gold corners stay as they are, both when the second wall is reinforced and on load.
BOOST_AUTO_TEST_CASE(test_RockAndGoldCornersStay)
{
    TestMap map;
    addRoom(map);
    map.setGround(4, 4, Ground::rock);
    map.setGround(8, 4, Ground::gold);
    reinforceWallsAlongFloor(map, KEEPER);
    BOOST_CHECK(map.isUnreinforcedWall(4, 4));
    BOOST_CHECK(map.isUnreinforcedWall(8, 4));
    BOOST_CHECK(map.isReinforcedBy(4, 8, KEEPER));
    BOOST_CHECK(map.isReinforcedBy(8, 8, KEEPER));
    BOOST_CHECK_EQUAL(map.load(), 0u);
    BOOST_CHECK(map.isUnreinforcedWall(4, 4));
    BOOST_CHECK(map.isUnreinforcedWall(8, 4));
}

//! \brief Walls or floor of another keeper never make a corner, and a corner another keeper has reinforced is not
//! taken.
BOOST_AUTO_TEST_CASE(test_OtherKeeperBlocksCorner)
{
    TestMap map;
    // Corner (4, 4): one wall each
    map.setFloor(5, 5, KEEPER);
    map.setReinforcedWall(4, 5, KEEPER);
    map.claim(5, 4, OTHER_KEEPER);
    BOOST_CHECK(map.isUnreinforcedWall(4, 4));
    // Corner (10, 4): both walls of the keeper, floor of the other keeper
    map.setFloor(11, 5, OTHER_KEEPER);
    map.setReinforcedWall(10, 5, KEEPER);
    map.claim(11, 4, KEEPER);
    BOOST_CHECK(map.isUnreinforcedWall(10, 4));
    // Corner (4, 10): already reinforced by the other keeper
    map.setFloor(5, 11, KEEPER);
    map.setReinforcedWall(4, 10, OTHER_KEEPER);
    map.setReinforcedWall(4, 11, KEEPER);
    map.claim(5, 10, KEEPER);
    BOOST_CHECK(map.isReinforcedBy(4, 10, OTHER_KEEPER));
    BOOST_CHECK_EQUAL(map.load(), 0u);
    BOOST_CHECK(map.isUnreinforcedWall(4, 4));
    BOOST_CHECK(map.isUnreinforcedWall(10, 4));
}

//! \brief Along a diagonal (staircase) tunnel no tile is reinforced that has no floor of the keeper at one of its
//! corners, every reinforced corner lies between two of his reinforced walls, and loading the result again (a saved
//! game) adds nothing: the rule does not spread into the earth.
BOOST_AUTO_TEST_CASE(test_StaircaseTunnelDoesNotSpread)
{
    TestMap map;
    // Floor (2, 2), (3, 2), (3, 3), (4, 3), (4, 4), ... up to (12, 12)
    for(int32_t i = 2; i <= 12; ++i)
    {
        map.setFloor(i, i, KEEPER);
        if(i < 12)
            map.setFloor(i + 1, i, KEEPER);
    }
    reinforceWallsAlongFloor(map, KEEPER);

    size_t cornerCount = 0;
    for(int32_t y = 0; y < MAP_SIZE; ++y)
    {
        for(int32_t x = 0; x < MAP_SIZE; ++x)
        {
            if(!map.isReinforcedBy(x, y, KEEPER) || touchesFloorOf(map, x, y, KEEPER))
                continue;

            // A tile reinforced by the rule: the keeper's floor at one of its corners
            ++cornerCount;
            BOOST_CHECK(touchesFloorOfAtCorner(map, x, y, KEEPER));
        }
    }
    // The tunnel has outer corners on both sides; the rule reinforced some of them
    BOOST_CHECK(cornerCount > 0);

    for(int32_t y = 0; y < MAP_SIZE; ++y)
    {
        for(int32_t x = 0; x < MAP_SIZE; ++x)
        {
            if(!touchesFloorOf(map, x, y, KEEPER) && !touchesFloorOfAtCorner(map, x, y, KEEPER) &&
               !map.isFloorOf(x, y, KEEPER))
            {
                BOOST_CHECK(map.isUnreinforcedWall(x, y));
            }
        }
    }

    BOOST_CHECK_EQUAL(map.load(), 0u);
}
