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

#ifndef WALLCORNERS_H
#define WALLCORNERS_H

#include <cstdint>
#include <vector>

//! \brief What the wall corner rule needs to know about one tile. The server fills it from the map.
struct WallCornerTileInfo
{
    //! \brief Creates the info of an open tile that nobody has claimed (also used for tiles outside of the map)
    WallCornerTileInfo() :
        mIsWall(false),
        mCanBecomeCorner(false),
        mClaimSeatId(-1)
    {}

    //! The tile is solid (fullness > 0)
    bool mIsWall;
    //! The tile is an earth wall that no keeper has reinforced, so the rule may reinforce it
    bool mCanBecomeCorner;
    //! Seat id of the keeper who owns the tile completely (a reinforced wall or a claimed floor), else -1
    int32_t mClaimSeatId;
};

//! \brief A tile that the wall corner rule reinforces, and the keeper it then belongs to.
struct WallCorner
{
    int32_t mX;
    int32_t mY;
    int32_t mSeatId;
};

//! \brief Gives the rule access to the tiles of a map. The game reads its map, the unit test a small grid.
class WallCornerMap
{
public:
    //! \brief Destroys the map access
    virtual ~WallCornerMap()
    {}

    //! \brief Returns the info of the tile (x, y); a tile outside of the map gives the default info
    virtual WallCornerTileInfo getTileInfo(int32_t x, int32_t y) const = 0;
};

//! \brief The wall corner rule: an earth wall that no keeper has reinforced becomes a reinforced wall of a keeper
//! when two of its direct neighbours that touch each other (north+east, east+south, south+west, west+north) are walls
//! reinforced by that keeper and the diagonal tile between those two walls is floor claimed by that keeper.
//! A corner reinforced by the rule is never used to look for further corners in the same step, so the rule only
//! ever reaches tiles that touch a claimed floor of the keeper at a corner and never spreads into solid earth.
namespace WallCorners
{
    //! brief Returns the info of a tile: isWall for a solid tile, isEarth for an earth (dirt) tile, claimSeatId for
    //! the keeper who owns the tile completely or -1. Only an earth wall that nobody owns can become a corner; rock,
    //! gold, lava and water never do.
    WallCornerTileInfo makeTileInfo(bool isWall, bool isEarth, int32_t claimSeatId);

    //! \brief Returns the seat id of the first keeper (pairs checked in the order north+east, east+south,
    //! south+west, west+north) for whom the tile (x, y) is a corner, else -1
    int32_t getCornerSeatId(const WallCornerMap& map, int32_t x, int32_t y);

    //! \brief Tells whether the tile (x, y) is a corner of the keeper with the given seat id
    bool isCornerOfSeat(const WallCornerMap& map, int32_t x, int32_t y, int32_t seatId);

    //! \brief Lists the corners of the keeper seatId that the claim of the tile (x, y) by him completes: for a wall,
    //! its four direct neighbours; for a floor, its four diagonal neighbours. The list is computed before any of
    //! them is reinforced, so one claim never reaches further than these tiles.
    void findCornersAfterClaim(const WallCornerMap& map, int32_t x, int32_t y, int32_t seatId,
        std::vector<WallCorner>& corners);

    //! \brief Lists every corner of the map of size mapSizeX * mapSizeY as the map is when it is loaded. The list is
    //! computed from the loaded state only, so a corner it lists never makes another tile a corner.
    void findCornersOnLoad(const WallCornerMap& map, int32_t mapSizeX, int32_t mapSizeY,
        std::vector<WallCorner>& corners);
}

#endif // WALLCORNERS_H
