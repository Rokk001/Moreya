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

#ifndef TOILETLAYOUT_H
#define TOILETLAYOUT_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <set>
#include <utility>
#include <vector>

//! \brief Where the seats of a toilet room stand and how long one use lasts. Pure functions on tile coordinates, so
//! the rules can be tested without a game map (see source/tests/check_toilet_k25.py).
namespace ToiletLayout
{
//! \brief Seat angles (degrees) for a back to the side at +y, -y, -x and +x (same convention as the wall furniture of
//! the library): the seat mesh has its back at +y, the angle turns it counter-clockwise.
const double SEAT_ANGLE_WALL_TOP = 0.0;
const double SEAT_ANGLE_WALL_BOTTOM = 180.0;
const double SEAT_ANGLE_WALL_LEFT = 90.0;
const double SEAT_ANGLE_WALL_RIGHT = 270.0;

//! \brief A tile coordinate (x, y).
typedef std::pair<int, int> Coord;

//! \brief The seat angle for a back to the given side, as the offset (dx, dy) from the tile to that side's neighbour.
inline double angleForSide(int dx, int dy)
{
    if(dy > 0)
        return SEAT_ANGLE_WALL_TOP;
    if(dy < 0)
        return SEAT_ANGLE_WALL_BOTTOM;
    if(dx < 0)
        return SEAT_ANGLE_WALL_LEFT;
    return SEAT_ANGLE_WALL_RIGHT;
}

//! \brief Chooses the seats of a toilet room: the seats stand in rows along the edge of the room with their backs to
//! the outside, and the middle of the room stays free as a walking lane.
//! A tile gets a seat when exactly one of its four neighbours is not part of the room (an edge tile that is not a
//! corner and not in a passage one tile wide); its back is at that neighbour. A room without such a tile (one or two
//! tiles wide, 2 x 2) gets a seat on every second tile in (x, y) order, each turned to its first outside side, so that
//! every seat keeps a free tile beside it.
//! \param tiles The covered tiles of the room.
//! \param seats Filled with the seat tiles and their angles (degrees).
inline void chooseSeats(const std::vector<Coord>& tiles, std::map<Coord, double>& seats)
{
    seats.clear();
    const std::set<Coord> room(tiles.begin(), tiles.end());
    const int sides[4][2] = { {0, 1}, {0, -1}, {-1, 0}, {1, 0} };
    for(const Coord& tile : room)
    {
        int outside = 0;
        int backX = 0;
        int backY = 0;
        for(const int* side : sides)
        {
            if(room.count(Coord(tile.first + side[0], tile.second + side[1])) != 0)
                continue;
            ++outside;
            backX = side[0];
            backY = side[1];
        }
        if(outside == 1)
            seats[tile] = angleForSide(backX, backY);
    }
    if(!seats.empty())
        return;

    // Narrow or tiny rooms: every second tile, so the users can step beside the seats
    uint32_t index = 0;
    for(const Coord& tile : room)
    {
        if((index++ % 2) != 0)
            continue;
        double angle = SEAT_ANGLE_WALL_TOP;
        for(const int* side : sides)
        {
            if(room.count(Coord(tile.first + side[0], tile.second + side[1])) == 0)
            {
                angle = angleForSide(side[0], side[1]);
                break;
            }
        }
        seats[tile] = angle;
    }
}

//! \brief Number of turns of one use of a seat that lasts the given number of seconds (at least one turn).
inline int32_t useTurns(double seconds, double turnsPerSecond)
{
    return std::max(static_cast<int32_t>(1), static_cast<int32_t>(std::lround(seconds * turnsPerSecond)));
}

//! \brief Seconds of one use: minSeconds plus the share random01 (0 to 1, drawn anew for every use) of the range up
//! to maxSeconds.
inline double useSeconds(double minSeconds, double maxSeconds, double random01)
{
    const double share = std::min(1.0, std::max(0.0, random01));
    return minSeconds + (std::max(minSeconds, maxSeconds) - minSeconds) * share;
}
}

#endif // TOILETLAYOUT_H
