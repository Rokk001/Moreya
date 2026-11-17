#ifndef INFIRMARYSHAMANWALK_H
#define INFIRMARYSHAMANWALK_H

#include "gamemap/RoomObjectPath.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <queue>
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
//! \brief Spacing in tiles of the fine search grid that plan falls back to when the quarter-tile route search finds no
//! way. Wall furniture beside a cot can leave a passage narrower than a quarter tile (but wide enough for the shaman)
//! as the only way out of a standing point; the fine grid has a line inside every such passage.
static const float FINE_GRID_SPACING = 0.05f;
//! \brief Distance in tiles within which the fine search links the start and the goal to its grid points.
static const float FINE_GRID_LINK_REACH = 0.1f;

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

//! \brief Tells whether the shaman can walk the straight leg: it keeps the walking radius from all furniture and stays
//! on the room floor.
//! \param floor Every floor tile of the room.
//! \param furniture The room furniture, already widened by WALKING_RADIUS.
//! \param from Start of the leg.
//! \param to End of the leg.
//! \param allowExit True when the start may lie inside furniture that the leg leaves (a figure of an old save).
inline bool walkableLeg(const std::set<Cell>& floor, const std::vector<RoomObjectPath::Obstacle>& furniture,
    const Ogre::Vector2& from, const Ogre::Vector2& to, bool allowExit)
{
    return RoomObjectPath::clearSegment(furniture, from, to, allowExit) && insideRoom(floor, from, to);
}

//! \brief Searches a route on a grid of FINE_GRID_SPACING over the room, for the case that the quarter-tile route
//! search misses a narrow passage. The found grid route is shortened by dropping every waypoint that a straight
//! walkable leg can skip.
//! \param start The shaman's position.
//! \param goal The standing point he walks to.
//! \param floor Every floor tile of the room.
//! \param furniture The room furniture, already widened by WALKING_RADIUS.
//! \param path Receives the waypoints after the start; the last one is the goal.
//! \return False when there is no route on the fine grid either.
inline bool fineRoute(const Ogre::Vector2& start, const Ogre::Vector2& goal, const std::set<Cell>& floor,
    const std::vector<RoomObjectPath::Obstacle>& furniture, std::vector<Ogre::Vector2>& path)
{
    path.clear();
    int minX = floor.begin()->first, minY = floor.begin()->second;
    int maxX = minX, maxY = minY;
    for(std::set<Cell>::const_iterator it = floor.begin(); it != floor.end(); ++it)
    {
        minX = std::min(minX, it->first);
        minY = std::min(minY, it->second);
        maxX = std::max(maxX, it->first);
        maxY = std::max(maxY, it->second);
    }
    const int perTile = static_cast<int>(std::floor(1.0f / FINE_GRID_SPACING + 0.5f));
    const int width = (maxX - minX + 1) * perTile + 1;
    const int height = (maxY - minY + 1) * perTile + 1;
    const int count = width * height;
    const Ogre::Vector2 origin(static_cast<float>(minX) - 0.5f, static_cast<float>(minY) - 0.5f);
    const std::function<Ogre::Vector2(int)> position = [origin, width](int index)
    {
        return origin + Ogre::Vector2(static_cast<float>(index % width) * FINE_GRID_SPACING,
            static_cast<float>(index / width) * FINE_GRID_SPACING);
    };
    // 0 = not tested yet, 1 = the shaman can stand there, 2 = he cannot
    std::vector<signed char> usable(count, 0);
    const std::function<bool(int)> isUsable = [&](int index)
    {
        if(usable[index] == 0)
        {
            const Ogre::Vector2 point = position(index);
            usable[index] = RoomObjectPath::clearPoint(furniture, point) && insideRoom(floor, point, point) ? 1 : 2;
        }
        return usable[index] == 1;
    };
    // The goal is the extra node with the index count
    std::vector<float> cost(count + 1, std::numeric_limits<float>::infinity());
    std::vector<int> parent(count + 1, -1);
    typedef std::pair<float, int> Entry;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry> > open;
    // Only a figure that stands inside furniture (an old save) may leave it on its first leg
    const bool startInside = !RoomObjectPath::clearPoint(furniture, start);
    const int reachCells = static_cast<int>(std::ceil(FINE_GRID_LINK_REACH / FINE_GRID_SPACING));
    const int startX = static_cast<int>(std::floor((start.x - origin.x) / FINE_GRID_SPACING + 0.5f));
    const int startY = static_cast<int>(std::floor((start.y - origin.y) / FINE_GRID_SPACING + 0.5f));
    for(int y = std::max(0, startY - reachCells); y <= std::min(height - 1, startY + reachCells); ++y)
    {
        for(int x = std::max(0, startX - reachCells); x <= std::min(width - 1, startX + reachCells); ++x)
        {
            const int index = y * width + x;
            const Ogre::Vector2 point = position(index);
            const float distance = start.distance(point);
            if(distance > FINE_GRID_LINK_REACH || !isUsable(index) || !walkableLeg(floor, furniture, start, point, startInside))
                continue;
            cost[index] = distance;
            open.push(Entry(distance, index));
        }
    }
    while(!open.empty())
    {
        const Entry entry = open.top();
        open.pop();
        const int index = entry.second;
        if(entry.first > cost[index])
            continue;
        if(index == count)
            break;
        const Ogre::Vector2 point = position(index);
        if(point.distance(goal) <= FINE_GRID_LINK_REACH && cost[index] + point.distance(goal) < cost[count] &&
            walkableLeg(floor, furniture, point, goal, false))
        {
            cost[count] = cost[index] + point.distance(goal);
            parent[count] = index;
            open.push(Entry(cost[count], count));
        }
        const int x = index % width;
        const int y = index / width;
        for(int dy = -1; dy <= 1; ++dy)
        {
            for(int dx = -1; dx <= 1; ++dx)
            {
                if((dx == 0 && dy == 0) || x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= height)
                    continue;
                const int next = (y + dy) * width + x + dx;
                const float step = (dx != 0 && dy != 0 ? 1.41421356f : 1.0f) * FINE_GRID_SPACING;
                if(cost[index] + step >= cost[next] || !isUsable(next) ||
                    !walkableLeg(floor, furniture, point, position(next), false))
                    continue;
                cost[next] = cost[index] + step;
                parent[next] = index;
                open.push(Entry(cost[next], next));
            }
        }
    }
    if(parent[count] < 0)
        return false;
    std::vector<Ogre::Vector2> points;
    points.push_back(goal);
    for(int index = parent[count]; index >= 0; index = parent[index])
        points.push_back(position(index));
    points.push_back(start);
    std::reverse(points.begin(), points.end());
    size_t current = 0;
    while(current + 1 < points.size())
    {
        size_t next = points.size() - 1;
        while(next > current + 1 && !walkableLeg(floor, furniture, points[current], points[next], current == 0 && startInside))
            --next;
        path.push_back(points[next]);
        current = next;
    }
    return true;
}

//! \brief Plans the shaman's walk from his position to a free standing point of the target tile: the route goes around
//! every piece of furniture (cots, cabinets, tables, basins, shelves) and never leaves the floor of the room. When the
//! quarter-tile route search finds no way, the fine grid search (fineRoute) is tried, which also finds passages
//! narrower than a quarter tile.
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
        terrain, path, true) && !fineRoute(start, goal, floor, furniture, path))
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
