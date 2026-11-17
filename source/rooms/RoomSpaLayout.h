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

#ifndef ROOMSPALAYOUT_H
#define ROOMSPALAYOUT_H

#include <cstddef>
#include <cstdint>
#include <map>
#include <set>
#include <utility>
#include <vector>

//! \brief A set of tile positions (x, y) of a lava spa. The pure layout rules of the spa work on such sets so that
//! they do not need a map; the room maps its tiles to a set and back.
typedef std::set<std::pair<int32_t, int32_t> > SpaTileSet;

//! \brief A block of tiles in a pool: the smallest x and y and the size in tiles.
struct SpaBlock
{
    //! \brief Creates an empty block of 1 x 1 tiles at the origin.
    SpaBlock() :
        mX(0),
        mY(0),
        mWidth(1),
        mHeight(1)
    {}

    //! Smallest x of the block.
    int32_t mX;
    //! Smallest y of the block.
    int32_t mY;
    //! Number of tiles along x.
    int32_t mWidth;
    //! Number of tiles along y.
    int32_t mHeight;
};

//! \brief The layout rules of the lava spa: which tiles are pool, where a bather finds a place, where the pool
//! attendant's chair and the springboard stand and how large the room has to be. All of them are deterministic, so
//! the server and the checks get the same result.
namespace SpaLayout
{
    //! \brief The pool tiles of a spa: the covered tiles whose eight neighbours are covered tiles too. The other
    //! covered tiles are the rim.
    //! \param covered All the tiles the room covers.
    inline SpaTileSet poolTiles(const SpaTileSet& covered)
    {
        SpaTileSet pool;
        for(SpaTileSet::const_iterator it = covered.begin(); it != covered.end(); ++it)
        {
            bool allNeighbours = true;
            for(int32_t dx = -1; dx <= 1; ++dx)
            {
                for(int32_t dy = -1; dy <= 1; ++dy)
                {
                    if(covered.find(std::make_pair(it->first + dx, it->second + dy)) == covered.end())
                        allNeighbours = false;
                }
            }
            if(allNeighbours)
                pool.insert(*it);
        }
        return pool;
    }

    //! \brief True when the tiles contain a full block of side x side tiles.
    //! \param tiles The tiles to look in.
    //! \param side The side of the block in tiles.
    inline bool hasSquareBlock(const SpaTileSet& tiles, int32_t side)
    {
        for(SpaTileSet::const_iterator it = tiles.begin(); it != tiles.end(); ++it)
        {
            bool full = true;
            for(int32_t dx = 0; dx < side; ++dx)
            {
                for(int32_t dy = 0; dy < side; ++dy)
                {
                    if(tiles.find(std::make_pair(it->first + dx, it->second + dy)) == tiles.end())
                        full = false;
                }
            }
            if(full)
                return true;
        }
        return false;
    }

    //! \brief True when every tile of the block is a pool tile that is not taken.
    //! \param pool The pool tiles.
    //! \param taken The tiles of the blocks that bathers have or have reserved.
    //! \param block The block to test.
    inline bool isBlockFree(const SpaTileSet& pool, const SpaTileSet& taken, const SpaBlock& block)
    {
        for(int32_t dx = 0; dx < block.mWidth; ++dx)
        {
            for(int32_t dy = 0; dy < block.mHeight; ++dy)
            {
                const std::pair<int32_t, int32_t> tile(block.mX + dx, block.mY + dy);
                if((pool.find(tile) == pool.end()) || (taken.find(tile) != taken.end()))
                    return false;
            }
        }
        return true;
    }

    //! \brief Finds the bath place of a creature: the first free block of its bed size among the pool tiles, in the
    //! order of smaller y, then smaller x. A bed of 1 x 2 tiles tries both orientations, the unrotated one
    //! (width dim1, height dim2) first.
    //! \param pool The pool tiles.
    //! \param taken The tiles of the blocks that bathers have or have reserved.
    //! \param dim1 First bed dimension of the creature (BedDim).
    //! \param dim2 Second bed dimension of the creature (BedDim).
    //! \param block Set to the block that was found.
    //! \return False when no free block exists.
    inline bool findFreeBlock(const SpaTileSet& pool, const SpaTileSet& taken, int32_t dim1, int32_t dim2, SpaBlock& block)
    {
        // The tiles are walked in the order of smaller y, then smaller x
        std::set<std::pair<int32_t, int32_t> > anchors;
        for(SpaTileSet::const_iterator it = pool.begin(); it != pool.end(); ++it)
            anchors.insert(std::make_pair(it->second, it->first));

        for(SpaTileSet::const_iterator it = anchors.begin(); it != anchors.end(); ++it)
        {
            SpaBlock candidate;
            candidate.mX = it->second;
            candidate.mY = it->first;
            candidate.mWidth = dim1;
            candidate.mHeight = dim2;
            if(isBlockFree(pool, taken, candidate))
            {
                block = candidate;
                return true;
            }

            if(dim1 == dim2)
                continue;

            candidate.mWidth = dim2;
            candidate.mHeight = dim1;
            if(isBlockFree(pool, taken, candidate))
            {
                block = candidate;
                return true;
            }
        }
        return false;
    }

    //! \brief The bath place of a creature the keeper dropped into the spa: the free block of its bed size that holds
    //! the tile it was dropped on; else the free block whose middle is nearest to that tile (a drop on the rim), in the
    //! order of findFreeBlock when two are as near.
    //! \param pool The pool tiles.
    //! \param taken The tiles of the blocks that bathers have or have reserved.
    //! \param dim1 First bed dimension of the creature (BedDim).
    //! \param dim2 Second bed dimension of the creature (BedDim).
    //! \param drop The tile the creature was dropped on.
    //! \param block Set to the block that was found.
    //! \return False when no free block of the bed size exists.
    inline bool findDropBlock(const SpaTileSet& pool, const SpaTileSet& taken, int32_t dim1, int32_t dim2,
        const std::pair<int32_t, int32_t>& drop, SpaBlock& block)
    {
        std::set<std::pair<int32_t, int32_t> > anchors;
        for(SpaTileSet::const_iterator it = pool.begin(); it != pool.end(); ++it)
            anchors.insert(std::make_pair(it->second, it->first));

        bool found = false;
        double bestDistance = 0.0;
        for(std::set<std::pair<int32_t, int32_t> >::const_iterator it = anchors.begin(); it != anchors.end(); ++it)
        {
            for(int32_t orientation = 0; orientation < 2; ++orientation)
            {
                if((orientation == 1) && (dim1 == dim2))
                    continue;

                SpaBlock candidate;
                candidate.mX = it->second;
                candidate.mY = it->first;
                candidate.mWidth = (orientation == 0) ? dim1 : dim2;
                candidate.mHeight = (orientation == 0) ? dim2 : dim1;
                if(!isBlockFree(pool, taken, candidate))
                    continue;

                // A block that holds the tile of the drop is nearer than every other one
                const bool holdsDrop = (drop.first >= candidate.mX) && (drop.first < candidate.mX + candidate.mWidth) &&
                    (drop.second >= candidate.mY) && (drop.second < candidate.mY + candidate.mHeight);
                const double middleX = static_cast<double>(candidate.mX) + static_cast<double>(candidate.mWidth - 1) * 0.5;
                const double middleY = static_cast<double>(candidate.mY) + static_cast<double>(candidate.mHeight - 1) * 0.5;
                const double distance = holdsDrop ? -1.0 :
                    (middleX - drop.first) * (middleX - drop.first) + (middleY - drop.second) * (middleY - drop.second);
                if(!found || (distance < bestDistance))
                {
                    found = true;
                    bestDistance = distance;
                    block = candidate;
                }
            }
        }
        return found;
    }

    //! \brief The tile of the pool attendant's chair: directly above (y - 1) the pool tile with the smallest y, then
    //! the smallest x.
    //! \param pool The pool tiles.
    //! \param tile Set to the position of the chair tile.
    //! \return False when the pool has no tile.
    inline bool chairTile(const SpaTileSet& pool, std::pair<int32_t, int32_t>& tile)
    {
        if(pool.empty())
            return false;

        std::pair<int32_t, int32_t> best = *pool.begin();
        for(SpaTileSet::const_iterator it = pool.begin(); it != pool.end(); ++it)
        {
            if((it->second < best.second) || ((it->second == best.second) && (it->first < best.first)))
                best = *it;
        }
        tile = std::make_pair(best.first, best.second - 1);
        return true;
    }

    //! \brief The tile of the springboard: directly below (y + 1) the pool tile with the largest y, then the largest x.
    //! \param pool The pool tiles.
    //! \param tile Set to the position of the springboard tile.
    //! \return False when the pool has no tile.
    inline bool springboardTile(const SpaTileSet& pool, std::pair<int32_t, int32_t>& tile)
    {
        if(pool.empty())
            return false;

        std::pair<int32_t, int32_t> best = *pool.begin();
        for(SpaTileSet::const_iterator it = pool.begin(); it != pool.end(); ++it)
        {
            if((it->second > best.second) || ((it->second == best.second) && (it->first > best.first)))
                best = *it;
        }
        tile = std::make_pair(best.first, best.second + 1);
        return true;
    }

    //! \brief Cost of stepping onto a pool tile on a walk of the pool attendant. A step on the rim costs 1, so he goes
    //! around the pool on the rim and wades only out of the mud after a jump (decision 837: nobody walks over the pool).
    const int32_t POOL_STEP_COST = 100;

    //! \brief Extra cost of a step over the rim on the walk of a bather: higher than any walk through a room, so its way
    //! crosses the rim as seldom as possible (once in, once out; decision 902(3)).
    const int32_t RIM_CROSSING_COST = 100000;

    //! \brief The tiles the pool attendant walks over from one covered tile to another: steps between the four
    //! neighbours, around the pool on the rim where the rim connects them, through the fewest pool tiles otherwise.
    //! \param covered All the tiles the room covers.
    //! \param pool The pool tiles of the room.
    //! \param from The tile he starts on (not part of the result).
    //! \param to The tile he walks to (the last tile of the result).
    //! \param path Set to the tiles in walking order.
    //! \param crossingCost Extra cost of every step over the rim, from the rim into the pool or out of it. The walk of a
    //! bather uses RIM_CROSSING_COST, so it steps into the pool once and does not climb out and in again to save mud;
    //! the walk of the attendant uses 0.
    //! \return False when the room does not connect the two tiles.
    inline bool rimWalk(const SpaTileSet& covered, const SpaTileSet& pool, const std::pair<int32_t, int32_t>& from,
        const std::pair<int32_t, int32_t>& to, std::vector<std::pair<int32_t, int32_t> >& path, int32_t crossingCost = 0)
    {
        path.clear();
        if((covered.find(from) == covered.end()) || (covered.find(to) == covered.end()))
            return false;
        if(from == to)
            return true;

        // Dijkstra over the room tiles; the room is small, a plain search for the cheapest open tile is enough
        static const int32_t DX[] = { 0, 1, 0, -1 };
        static const int32_t DY[] = { -1, 0, 1, 0 };
        std::map<std::pair<int32_t, int32_t>, int32_t> cost;
        std::map<std::pair<int32_t, int32_t>, std::pair<int32_t, int32_t> > previous;
        SpaTileSet done;
        cost[from] = 0;
        while(true)
        {
            bool found = false;
            std::pair<int32_t, int32_t> current;
            int32_t best = 0;
            for(std::map<std::pair<int32_t, int32_t>, int32_t>::const_iterator it = cost.begin(); it != cost.end(); ++it)
            {
                if((done.find(it->first) != done.end()) || (found && (it->second >= best)))
                    continue;
                found = true;
                best = it->second;
                current = it->first;
            }
            if(!found)
                return false;
            if(current == to)
                break;
            done.insert(current);
            for(int32_t i = 0; i < 4; ++i)
            {
                const std::pair<int32_t, int32_t> next(current.first + DX[i], current.second + DY[i]);
                if((covered.find(next) == covered.end()) || (done.find(next) != done.end()))
                    continue;
                const bool nextInPool = (pool.find(next) != pool.end());
                const bool currentInPool = (pool.find(current) != pool.end());
                const int32_t step = (nextInPool ? POOL_STEP_COST : 1) + ((nextInPool != currentInPool) ? crossingCost : 0);
                std::map<std::pair<int32_t, int32_t>, int32_t>::iterator known = cost.find(next);
                if((known != cost.end()) && (known->second <= best + step))
                    continue;
                cost[next] = best + step;
                previous[next] = current;
            }
        }

        for(std::pair<int32_t, int32_t> tile = to; tile != from; tile = previous[tile])
            path.insert(path.begin(), tile);
        return true;
    }
    //! \brief The round of the pool attendant: from the rim tile on the left of his chair (x - 1) on the rim around the
    //! pool to the rim tile on the right of it (x + 1). He never steps on the mud and never through his chair, so in a
    //! room whose rim is one ring around the pool the round passes every rim tile (Mario 2026-11-17, answer to Q8).
    //! \param covered All the tiles the room covers.
    //! \param pool The pool tiles of the room.
    //! \param chair The tile of the chair.
    //! \param path Set to the tiles in walking order, the first one beside the chair on the left, the last one beside
    //! it on the right.
    //! \return False when the rim does not lead around the pool from one side of the chair to the other.
    inline bool attendantRound(const SpaTileSet& covered, const SpaTileSet& pool, const std::pair<int32_t, int32_t>& chair,
        std::vector<std::pair<int32_t, int32_t> >& path)
    {
        path.clear();
        SpaTileSet rim;
        for(SpaTileSet::const_iterator it = covered.begin(); it != covered.end(); ++it)
        {
            if((pool.find(*it) == pool.end()) && (*it != chair))
                rim.insert(*it);
        }

        const std::pair<int32_t, int32_t> left(chair.first - 1, chair.second);
        const std::pair<int32_t, int32_t> right(chair.first + 1, chair.second);
        std::vector<std::pair<int32_t, int32_t> > walk;
        if(!rimWalk(rim, SpaTileSet(), left, right, walk) || walk.empty())
            return false;

        path.push_back(left);
        path.insert(path.end(), walk.begin(), walk.end());
        return true;
    }

    //! \brief What a bather does on the next leg of its walk in the spa (decision 902(3)).
    enum class BathLeg
    {
        //! Walking on the rim.
        rim = 0,
        //! Wading through the mud.
        wade = 1,
        //! Stepping over the rim from a rim tile into the pool (one tile).
        stepIn = 2,
        //! Climbing over the rim from a pool tile out onto the rim (one tile).
        stepOut = 3
    };

    //! \brief Splits the walk of a bather into legs so that it never walks or wades through the rim: a leg stays on the
    //! rim or in the mud, and every crossing of the rim is a leg of its own of one tile (step in or climb out).
    //! \param pool The pool tiles.
    //! \param here The tile the bather stands on.
    //! \param steps The tiles of its walk (see rimWalk; here is not part of it).
    //! \param kind Set to what the bather does on the leg.
    //! \return The number of tiles of steps the leg walks over (0 when steps is empty).
    inline std::size_t nextBathLeg(const SpaTileSet& pool, const std::pair<int32_t, int32_t>& here,
        const std::vector<std::pair<int32_t, int32_t> >& steps, BathLeg& kind)
    {
        const bool inPool = (pool.find(here) != pool.end());
        kind = inPool ? BathLeg::wade : BathLeg::rim;
        if(steps.empty())
            return 0;

        const bool firstInPool = (pool.find(steps.front()) != pool.end());
        if(firstInPool != inPool)
        {
            kind = firstInPool ? BathLeg::stepIn : BathLeg::stepOut;
            return 1;
        }

        std::size_t count = 0;
        while((count < steps.size()) && ((pool.find(steps[count]) != pool.end()) == inPool))
            ++count;
        return count;
    }

    //! \brief Height in tiles of the top of the stone rim of the pool (SpaPoolRim reaches from 0 to 0.3).
    const double RIM_TOP = 0.3;

    //! \brief Height in tiles the feet of a walker are lifted where it crosses the rim: the top of the rim and 0.02 to
    //! spare (decision 902(3)).
    const double RIM_STEP_HEIGHT = RIM_TOP + 0.02;

    //! \brief Half the width of a tile: the rim edge lies this far from the middle of the pool tile it stands on.
    const double HALF_TILE = 0.5;

    //! \brief How high a walker has to be lifted at a point so that it steps over the rim and does not walk through it.
    //! The rim stands on the edge between a pool tile and a rim tile; the lift is a parabola over the crossing that is
    //! 0 in the middles of both tiles and RIM_STEP_HEIGHT on the edge.
    //! \param offsetX The x of the point minus the x of the middle of its tile (-0.5 to 0.5).
    //! \param offsetY The y of the point minus the y of the middle of its tile (-0.5 to 0.5).
    //! \param poolHere True when the tile of the point is a pool tile.
    //! \param poolSide True for each neighbour that is a pool tile, in the order -y, +x, +y, -x.
    //! \param edgeDistance Set to the distance from the point to the nearest rim edge of its tile (HALF_TILE when the
    //! tile has no rim edge).
    //! \return The lift in tiles (0 away from the rim).
    inline double rimStepLift(double offsetX, double offsetY, bool poolHere, const bool poolSide[4], double& edgeDistance)
    {
        static const double SIDE_X[] = { 0.0, 1.0, 0.0, -1.0 };
        static const double SIDE_Y[] = { -1.0, 0.0, 1.0, 0.0 };
        edgeDistance = HALF_TILE;
        for(int32_t side = 0; side < 4; ++side)
        {
            if(poolSide[side] == poolHere)
                continue;
            const double distance = HALF_TILE - (offsetX * SIDE_X[side] + offsetY * SIDE_Y[side]);
            if(distance < edgeDistance)
                edgeDistance = distance;
        }
        if(edgeDistance < 0.0)
            edgeDistance = 0.0;
        if(edgeDistance >= HALF_TILE)
            return 0.0;

        const double ratio = edgeDistance / HALF_TILE;
        return RIM_STEP_HEIGHT * (1.0 - ratio * ratio);
    }

    //! \brief How far a walker is on its step over the rim, from 0 in the middle of the tile it leaves to 1 in the
    //! middle of the tile it reaches, worked out from where it stands (the rim edge is at 0.5).
    //! \param edgeDistance The distance of the walker from the rim edge (see rimStepLift).
    //! \param onTargetSide True when the walker stands on the tile it steps onto.
    inline double rimStepProgress(double edgeDistance, bool onTargetSide)
    {
        const double clamped = (edgeDistance < HALF_TILE) ? edgeDistance : HALF_TILE;
        return onTargetSide ? (HALF_TILE + clamped) : (HALF_TILE - clamped);
    }
}

#endif // ROOMSPALAYOUT_H
