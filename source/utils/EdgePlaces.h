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

#ifndef EDGEPLACES_H
#define EDGEPLACES_H

#include <algorithm>
#include <utility>
#include <vector>

//! \brief Places beyond the map edge that can be marked for digging like undiscovered tiles.
//! A place has no Tile; it is a pair of coordinates outside the map, at most EDGE_PLACE_REACH
//! places away from it, so the number of marks stays bounded.
namespace EdgePlaces
{
//! How far beyond the map edge, in places, marks can reach.
static const int EDGE_PLACE_REACH = 12;

//! \brief True if the coordinates are outside a map of the given size.
inline bool isBeyondEdge(int x, int y, int sizeX, int sizeY)
{
    return x < 0 || y < 0 || x >= sizeX || y >= sizeY;
}

//! \brief True if the coordinates are outside the map and within EDGE_PLACE_REACH of it.
inline bool isMarkable(int x, int y, int sizeX, int sizeY)
{
    return isBeyondEdge(x, y, sizeX, sizeY) &&
        x >= -EDGE_PLACE_REACH && y >= -EDGE_PLACE_REACH &&
        x < sizeX + EDGE_PLACE_REACH && y < sizeY + EDGE_PLACE_REACH;
}

//! \brief Moves coordinates that are farther out than EDGE_PLACE_REACH to the outermost markable ring, so a drag
//! can go on beyond the reach without losing its selection. Coordinates inside the reach stay as they are.
inline void clampToReach(int& x, int& y, int sizeX, int sizeY)
{
    x = std::max(-EDGE_PLACE_REACH, std::min(sizeX + EDGE_PLACE_REACH - 1, x));
    y = std::max(-EDGE_PLACE_REACH, std::min(sizeY + EDGE_PLACE_REACH - 1, y));
}

//! \brief All markable places inside the rectangle spanned by the two corners (in any order), row by row.
inline std::vector<std::pair<int, int> > inRectangle(int x1, int y1, int x2, int y2, int sizeX, int sizeY)
{
    std::vector<std::pair<int, int> > places;
    if(x1 > x2)
        std::swap(x1, x2);
    if(y1 > y2)
        std::swap(y1, y2);
    x1 = std::max(x1, -EDGE_PLACE_REACH);
    y1 = std::max(y1, -EDGE_PLACE_REACH);
    x2 = std::min(x2, sizeX + EDGE_PLACE_REACH - 1);
    y2 = std::min(y2, sizeY + EDGE_PLACE_REACH - 1);
    for(int x = x1; x <= x2; ++x)
    {
        for(int y = y1; y <= y2; ++y)
        {
            if(isBeyondEdge(x, y, sizeX, sizeY))
                places.push_back(std::pair<int, int>(x, y));
        }
    }
    return places;
}
}

#endif // EDGEPLACES_H
