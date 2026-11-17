#ifndef MERCHANTWALLTABLE_H
#define MERCHANTWALLTABLE_H

#include <functional>
#include <utility>
#include <vector>

//! \brief What a tile in or around a merchant room is when the wall-side sales table is placed.
enum class MerchantCell
{
    outside,   //!< no tile of the room and no wall: a corridor, another room (an opening of the room)
    wall,      //!< a full tile beside the room (wall, rock, gold) or the map edge
    floor,     //!< a free floor tile of the room
    furniture  //!< a tile of the room with a sales table, a shelf or another object
};

//! \brief The tile chosen for the wall-side sales table and the angle that turns its back to the wall.
struct MerchantWallTableChoice
{
    //! \brief Starts without a chosen tile.
    MerchantWallTableChoice() : mX(0), mY(0), mAngle(0.0f) {}
    int mX;
    int mY;
    float mAngle;
};

//! \brief Places the second sales table of a merchant room on a free wall-side tile (owner answer to Q2 of INGAME-QS-10:
//! a merchant room shows at least two sales tables from 3x3 upward; one table stands on every 3x3 centre).
namespace MerchantWallTable
{
//! \brief Least number of sales tables a merchant room with at least one 3x3 centre shows.
static const unsigned int MIN_SALES_TABLES = 2;

//! \brief Returns whether a free floor tile of the room touches a wall with one of its four sides.
inline bool isWallSide(const std::function<MerchantCell(int, int)>& cellAt, int x, int y)
{
    return cellAt(x, y + 1) == MerchantCell::wall || cellAt(x, y - 1) == MerchantCell::wall ||
        cellAt(x - 1, y) == MerchantCell::wall || cellAt(x + 1, y) == MerchantCell::wall;
}

//! \brief Returns the angle that turns a table's back to its wall, by the convention of the wall shelves
//! (top 0, left 90, bottom 180, right 270 degrees).
inline float angleTowardWall(const std::function<MerchantCell(int, int)>& cellAt, int x, int y)
{
    if(cellAt(x, y + 1) == MerchantCell::wall)
        return 0.0f;
    if(cellAt(x - 1, y) == MerchantCell::wall)
        return 90.0f;
    if(cellAt(x, y - 1) == MerchantCell::wall)
        return 180.0f;
    if(cellAt(x + 1, y) == MerchantCell::wall)
        return 270.0f;
    return 0.0f;
}

//! \brief Counts the groups of free floor tiles that touch each other side by side, leaving out one tile.
inline unsigned int floorGroups(const std::vector<std::pair<int, int>>& roomTiles,
    const std::function<MerchantCell(int, int)>& cellAt, int skipX, int skipY)
{
    std::vector<std::pair<int, int>> floors;
    for(const std::pair<int, int>& tile : roomTiles)
        if(cellAt(tile.first, tile.second) == MerchantCell::floor && (tile.first != skipX || tile.second != skipY))
            floors.push_back(tile);
    std::vector<bool> seen(floors.size(), false);
    unsigned int groups = 0;
    for(size_t start = 0; start < floors.size(); ++start)
    {
        if(seen[start])
            continue;
        ++groups;
        std::vector<size_t> pending(1, start);
        seen[start] = true;
        while(!pending.empty())
        {
            const std::pair<int, int> current = floors[pending.back()];
            pending.pop_back();
            for(size_t other = 0; other < floors.size(); ++other)
            {
                if(seen[other])
                    continue;
                const int dx = floors[other].first - current.first;
                const int dy = floors[other].second - current.second;
                if((dx == 0 && (dy == 1 || dy == -1)) || (dy == 0 && (dx == 1 || dx == -1)))
                {
                    seen[other] = true;
                    pending.push_back(other);
                }
            }
        }
    }
    return groups;
}

//! \brief Chooses the free wall-side floor tile for the second sales table. A tile is preferred, in this order, when a
//! free floor tile stands beside it (the merchant and the buyers stand there), when the table does not cut the free
//! floor in two, when it lies away from the room's openings, and when it touches more walls (a corner). Equal tiles
//! keep the order of roomTiles. Returns false when no free wall-side tile exists.
inline bool choose(const std::vector<std::pair<int, int>>& roomTiles, const std::function<MerchantCell(int, int)>& cellAt,
    MerchantWallTableChoice& choice)
{
    static const int AROUND[][2] = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}, {1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
    static const int SIDES[][2] = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}};
    const unsigned int groupsBefore = floorGroups(roomTiles, cellAt, false, 0, 0);
    bool found = false;
    int bestScore[4] = {0, 0, 0, 0};
    for(const std::pair<int, int>& tile : roomTiles)
    {
        const int x = tile.first;
        const int y = tile.second;
        if(cellAt(x, y) != MerchantCell::floor || !isWallSide(cellAt, x, y))
            continue;
        int stand = 0;
        for(const int (&step)[2] : AROUND)
            if(cellAt(x + step[0], y + step[1]) == MerchantCell::floor)
                stand = 1;
        int openings = 0;
        int walls = 0;
        for(const int (&step)[2] : SIDES)
        {
            const MerchantCell side = cellAt(x + step[0], y + step[1]);
            if(side == MerchantCell::outside)
                ++openings;
            else if(side == MerchantCell::wall)
                ++walls;
        }
        const int joined = floorGroups(roomTiles, cellAt, true, x, y) <= groupsBefore ? 1 : 0;
        const int score[4] = {stand, joined, -openings, walls};
        bool better = !found;
        for(int i = 0; i < 4 && !better; ++i)
        {
            if(score[i] != bestScore[i])
            {
                better = score[i] > bestScore[i];
                break;
            }
        }
        if(!better)
            continue;
        found = true;
        for(int i = 0; i < 4; ++i)
            bestScore[i] = score[i];
        choice.mX = x;
        choice.mY = y;
        choice.mAngle = angleTowardWall(cellAt, x, y);
    }
    return found;
}
}

#endif // MERCHANTWALLTABLE_H
