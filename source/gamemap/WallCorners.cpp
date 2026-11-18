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

#include "gamemap/WallCorners.h"

namespace
{
//! Number of pairs of direct neighbours that touch each other at a corner
const int32_t NB_CORNER_PAIRS = 4;

//! The direct neighbours in the order north, east, south, west (north is y + 1). Pair i is the neighbour i and
//! the neighbour (i + 1) % 4; the diagonal tile between them is at the sum of both offsets.
const int32_t NEIGHBOUR_DX[NB_CORNER_PAIRS] = { 0, 1, 0, -1 };
const int32_t NEIGHBOUR_DY[NB_CORNER_PAIRS] = { 1, 0, -1, 0 };

//! The diagonal neighbours, in the same order as the pairs
const int32_t DIAGONAL_DX[NB_CORNER_PAIRS] = { 1, 1, -1, -1 };
const int32_t DIAGONAL_DY[NB_CORNER_PAIRS] = { 1, -1, -1, 1 };

//! \brief Tells whether the info is a wall reinforced by the keeper seatId
bool isReinforcedWallOf(const WallCornerTileInfo& info, int32_t seatId)
{
    return info.mIsWall && (info.mClaimSeatId == seatId);
}

//! \brief Tells whether the info is a floor claimed by the keeper seatId
bool isClaimedFloorOf(const WallCornerTileInfo& info, int32_t seatId)
{
    return !info.mIsWall && (info.mClaimSeatId == seatId);
}

//! \brief Tells whether the pair of direct neighbours with the given index of the tile (x, y) makes it a corner of
//! the keeper seatId: both neighbours are his reinforced walls and the diagonal tile between them is his floor
bool isPairCornerOfSeat(const WallCornerMap& map, int32_t x, int32_t y, int32_t pair, int32_t seatId)
{
    int32_t next = (pair + 1) % NB_CORNER_PAIRS;
    if(!isReinforcedWallOf(map.getTileInfo(x + NEIGHBOUR_DX[pair], y + NEIGHBOUR_DY[pair]), seatId))
        return false;

    if(!isReinforcedWallOf(map.getTileInfo(x + NEIGHBOUR_DX[next], y + NEIGHBOUR_DY[next]), seatId))
        return false;

    int32_t diagonalX = x + NEIGHBOUR_DX[pair] + NEIGHBOUR_DX[next];
    int32_t diagonalY = y + NEIGHBOUR_DY[pair] + NEIGHBOUR_DY[next];
    return isClaimedFloorOf(map.getTileInfo(diagonalX, diagonalY), seatId);
}

//! \brief Adds the tile (x, y) to the corners when it is a corner of the keeper seatId and not listed yet
void addCornerOfSeat(const WallCornerMap& map, int32_t x, int32_t y, int32_t seatId,
    std::vector<WallCorner>& corners)
{
    if(!WallCorners::isCornerOfSeat(map, x, y, seatId))
        return;

    for(const WallCorner& corner : corners)
    {
        if((corner.mX == x) && (corner.mY == y))
            return;
    }

    WallCorner corner;
    corner.mX = x;
    corner.mY = y;
    corner.mSeatId = seatId;
    corners.push_back(corner);
}
} // namespace

namespace WallCorners
{
//! brief Fills the info of a tile; only an earth wall that nobody owns can become a corner
WallCornerTileInfo makeTileInfo(bool isWall, bool isEarth, int32_t claimSeatId)
{
    WallCornerTileInfo info;
    info.mIsWall = isWall;
    info.mClaimSeatId = (claimSeatId >= 0) ? claimSeatId : -1;
    info.mCanBecomeCorner = isWall && isEarth && (info.mClaimSeatId < 0);
    return info;
}

//! brief Returns the keeper for whom the tile is a corner, checking the pairs in a fixed order
int32_t getCornerSeatId(const WallCornerMap& map, int32_t x, int32_t y)
{
    if(!map.getTileInfo(x, y).mCanBecomeCorner)
        return -1;

    for(int32_t pair = 0; pair < NB_CORNER_PAIRS; ++pair)
    {
        // The owner of the first wall of the pair is the only keeper this pair can stand for
        int32_t seatId = map.getTileInfo(x + NEIGHBOUR_DX[pair], y + NEIGHBOUR_DY[pair]).mClaimSeatId;
        if(seatId < 0)
            continue;

        if(isPairCornerOfSeat(map, x, y, pair, seatId))
            return seatId;
    }

    return -1;
}

//! brief Tells whether one of the four pairs makes the tile a corner of the keeper
bool isCornerOfSeat(const WallCornerMap& map, int32_t x, int32_t y, int32_t seatId)
{
    if(seatId < 0)
        return false;

    if(!map.getTileInfo(x, y).mCanBecomeCorner)
        return false;

    for(int32_t pair = 0; pair < NB_CORNER_PAIRS; ++pair)
    {
        if(isPairCornerOfSeat(map, x, y, pair, seatId))
            return true;
    }

    return false;
}

//! brief Lists the corners next to a newly claimed wall or at the corners of a newly claimed floor
void findCornersAfterClaim(const WallCornerMap& map, int32_t x, int32_t y, int32_t seatId,
    std::vector<WallCorner>& corners)
{
    WallCornerTileInfo claimed = map.getTileInfo(x, y);
    if(claimed.mClaimSeatId != seatId)
        return;

    // A new reinforced wall can be one of the two walls of the corners next to it; a new floor can be the
    // diagonal tile of the corners at its corners
    const int32_t* dx = claimed.mIsWall ? NEIGHBOUR_DX : DIAGONAL_DX;
    const int32_t* dy = claimed.mIsWall ? NEIGHBOUR_DY : DIAGONAL_DY;
    for(int32_t i = 0; i < NB_CORNER_PAIRS; ++i)
        addCornerOfSeat(map, x + dx[i], y + dy[i], seatId, corners);
}

//! brief Lists every corner of the loaded map, row by row
void findCornersOnLoad(const WallCornerMap& map, int32_t mapSizeX, int32_t mapSizeY,
    std::vector<WallCorner>& corners)
{
    for(int32_t y = 0; y < mapSizeY; ++y)
    {
        for(int32_t x = 0; x < mapSizeX; ++x)
        {
            int32_t seatId = getCornerSeatId(map, x, y);
            if(seatId < 0)
                continue;

            WallCorner corner;
            corner.mX = x;
            corner.mY = y;
            corner.mSeatId = seatId;
            corners.push_back(corner);
        }
    }
}
} // namespace WallCorners
