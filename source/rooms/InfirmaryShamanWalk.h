#ifndef INFIRMARYSHAMANWALK_H
#define INFIRMARYSHAMANWALK_H

#include "gamemap/RoomObjectPath.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <set>
#include <utility>
#include <vector>

//! \brief Where the infirmary shaman stands and how he walks there without passing through a cot or other furniture
//! (INGAME-QS-10 K23). He stands beside a cot, never on it, and his route keeps his walking radius away from every
//! piece of room furniture and stays on the floor of his room.
namespace InfirmaryShamanWalk
{
//! \brief A tile position (x, y).
typedef std::pair<int, int> Cell;

//! \brief Radius in tiles that the shaman keeps free around his feet from every piece of room furniture.
static const float WALKING_RADIUS = 0.15f;
//! \brief Distance in tiles between two tested points when a walked segment is checked to stay on the room floor.
static const float SEGMENT_SAMPLE_STEP = 0.05f;
//! \brief Number of candidate standing points per tile side, spaced STANDING_POINT_SPACING apart around the centre.
static const int STANDING_GRID_SIZE = 9;
//! \brief Spacing in tiles of the candidate standing points inside the target tile.
static const float STANDING_POINT_SPACING = 0.1f;

//! \brief Finds the tile the shaman stands on to attend a cot: a floor tile of the room that touches the cot by a side
//! and holds no cot. A tile without wall furniture is preferred; the first one in the order of the cot tiles and the
//! directions left, right, down, up is taken.
//! \param cot The tiles of the cot.
//! \param floor Every floor tile of the room.
//! \param cots Every tile of the room that holds a cot.
//! \param accessories The tiles of the room that hold wall furniture.
//! \param result Receives the tile.
//! \return False when no floor tile touches the cot.
inline bool besideCot(const std::vector<Cell>& cot, const std::set<Cell>& floor, const std::set<Cell>& cots,
    const std::set<Cell>& accessories, Cell& result)
{
    static const int dx[] = {-1, 1, 0, 0};
    static const int dy[] = {0, 0, -1, 1};
    bool found = false;
    for(int pass = 0; pass < 2 && !found; ++pass)
    {
        for(std::vector<Cell>::const_iterator it = cot.begin(); it != cot.end() && !found; ++it)
        {
            for(int i = 0; i < 4 && !found; ++i)
            {
                const Cell next(it->first + dx[i], it->second + dy[i]);
                if(floor.count(next) == 0 || cots.count(next) != 0)
                    continue;
                if(pass == 0 && accessories.count(next) != 0)
                    continue;
                result = next;
                found = true;
            }
        }
    }
    return found;
}

//! \brief Tells whether a walked segment stays on the floor of the room the whole way, also where it crosses a tile
//! corner.
//! \param floor Every floor tile of the room.
//! \param from Start of the segment.
//! \param to End of the segment.
inline bool insideRoom(const std::set<Cell>& floor, const Ogre::Vector2& from, const Ogre::Vector2& to)
{
    const int steps = std::max(1, static_cast<int>(std::ceil(from.distance(to) / SEGMENT_SAMPLE_STEP)));
    for(int i = 0; i <= steps; ++i)
    {
        const Ogre::Vector2 point = from + (to - from) * (static_cast<float>(i) / static_cast<float>(steps));
        const Cell cell(static_cast<int>(std::floor(point.x + 0.5f)), static_cast<int>(std::floor(point.y + 0.5f)));
        if(floor.count(cell) == 0)
            return false;
    }
    return true;
}

//! \brief Finds the point of the target tile nearest to its centre where the shaman touches no furniture.
//! \param furniture The room furniture, already widened by WALKING_RADIUS.
//! \param target The tile.
//! \param result Receives the point.
//! \return False when the furniture covers the whole tile (a cot tile, for example).
inline bool standingPoint(const std::vector<RoomObjectPath::Obstacle>& furniture, const Cell& target,
    Ogre::Vector2& result)
{
    const Ogre::Vector2 centre(static_cast<float>(target.first), static_cast<float>(target.second));
    const float first = -0.5f * static_cast<float>(STANDING_GRID_SIZE - 1) * STANDING_POINT_SPACING;
    float best = std::numeric_limits<float>::infinity();
    for(int y = 0; y < STANDING_GRID_SIZE; ++y)
    {
        for(int x = 0; x < STANDING_GRID_SIZE; ++x)
        {
            const Ogre::Vector2 point = centre + Ogre::Vector2(first + x * STANDING_POINT_SPACING,
                first + y * STANDING_POINT_SPACING);
            if(point.squaredDistance(centre) >= best || !RoomObjectPath::clearPoint(furniture, point))
                continue;
            best = point.squaredDistance(centre);
            result = point;
        }
    }
    return best < std::numeric_limits<float>::infinity();
}

//! \brief Plans the shaman's walk from his position to a free standing point of the target tile: the route goes around
//! every piece of furniture (cots, cabinets, tables, basins, shelves) and never leaves the floor of the room.
//! \param start The shaman's position.
//! \param target The tile he walks to.
//! \param floor Every floor tile of the room.
//! \param furniture The room furniture, already widened by WALKING_RADIUS.
//! \param path Receives the waypoints after the start; the last one is the standing point.
//! \return False when there is no standing point or no route.
inline bool plan(const Ogre::Vector2& start, const Cell& target, const std::set<Cell>& floor,
    const std::vector<RoomObjectPath::Obstacle>& furniture, std::vector<Ogre::Vector2>& path)
{
    path.clear();
    if(floor.empty() || floor.count(target) == 0)
        return false;
    Ogre::Vector2 goal;
    if(!standingPoint(furniture, target, goal))
        return false;
    int minX = target.first, minY = target.second, maxX = target.first, maxY = target.second;
    for(std::set<Cell>::const_iterator it = floor.begin(); it != floor.end(); ++it)
    {
        minX = std::min(minX, it->first);
        minY = std::min(minY, it->second);
        maxX = std::max(maxX, it->first);
        maxY = std::max(maxY, it->second);
    }
    const RoomObjectPath::TerrainSegment terrain =
        std::bind(&insideRoom, std::cref(floor), std::placeholders::_1, std::placeholders::_2);
    if(!RoomObjectPath::route(start, goal, furniture, std::max(0, minX - 1), std::max(0, minY - 1), maxX + 1, maxY + 1,
        terrain, path, true))
    {
        path.clear();
        return false;
    }
    if(path.empty() || path.back() != goal)
        path.push_back(goal);
    return true;
}
}

#endif // INFIRMARYSHAMANWALK_H
