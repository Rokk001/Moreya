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

#include "creatureaction/CreatureActionClaimWallTile.h"

#include "creatureaction/CreatureActionClaimGroundTile.h"

#include "entities/Creature.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "gamemap/Pathfinding.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"

//! \brief Counts the worker on the tile when the tile has room for one more claiming worker.
CreatureActionClaimWallTile::CreatureActionClaimWallTile(Creature& creature, Tile& tileClaim) :
    CreatureAction(creature),
    mTileClaim(tileClaim),
    mClaimCounted(false)
{
    mClaimCounted = mTileClaim.addWorkerClaiming(mCreature);
}

//! \brief Takes the worker off the count of the tile, only when it was counted (else it would take another worker's
//! place off the count).
CreatureActionClaimWallTile::~CreatureActionClaimWallTile()
{
    if(mClaimCounted)
        mTileClaim.removeWorkerClaiming(mCreature);
}

std::function<bool()> CreatureActionClaimWallTile::action()
{
    return std::bind(&CreatureActionClaimWallTile::handleClaimWallTile,
        std::ref(mCreature), std::ref(mTileClaim));
}

//! \brief Performs the existing claim step and reports its one-upkeep interval without delaying work.
bool CreatureActionClaimWallTile::handleClaimWallTile(Creature& creature, Tile& tileClaim)
{
    Tile* myTile = creature.getPositionTile();
    if (myTile == nullptr)
    {
        OD_LOG_ERR("creature=" + creature.getName() + ", pos=" + Helper::toString(creature.getPosition()));
        creature.popAction();
        return false;
    }

    // We check if the tile is still claimable
    if(!tileClaim.isWallClaimable(creature.getSeat()))
    {
        creature.popAction();
        return true;
    }

    // We check if we are on a claimed tile next to the tile to claim
    Tile* tileDest = nullptr;
    float distBest = -1;
    for(Tile* tile : tileClaim.getAllNeighbors())
    {
        // We look for the closest allowed tile
        if(tile->isFullTile())
            continue;
        if(!creature.getGameMap()->pathExists(&creature, myTile, tile))
            continue;
        float dist = Pathfinding::squaredDistanceTile(*myTile, *tile);
        if((distBest != -1) && (distBest <= dist))
            continue;

        distBest = dist,
        tileDest = tile;
    }

    // The wall was reachable when the worker chose it (CreatureActionSearchWallTileToClaim); a way that closed since
    // (a bridge lost, a door locked, a room or a wall built) ends the claim, and the worker looks for other work
    if(tileDest == nullptr)
    {
        OD_LOG_WRN("creature=" + creature.getName() + " can no longer reach the wall, myTile=" + Tile::displayAsString(myTile) + ", tileClaim=" + Tile::displayAsString(&tileClaim));
        creature.popAction();
        return true;
    }

    if(tileDest != myTile)
    {
        if(!creature.setDestination(tileDest))
        {
            OD_LOG_WRN("creature=" + creature.getName() + " finds no way to the wall, myTile=" + Tile::displayAsString(myTile) + ", tileClaim=" + Tile::displayAsString(&tileClaim) + ", tileDest=" + Tile::displayAsString(tileDest));
            creature.popAction();
            return false;
        }
        return true;
    }

    // Claim the wall tile
    const Ogre::Vector3& pos = creature.getPosition();
    Ogre::Vector3 walkDirection(tileClaim.getX() - pos.x, tileClaim.getY() - pos.y, 0);
    walkDirection.normalise();
    creature.setAnimationState(EntityAnimation::claim_anim, true, walkDirection);
    tileClaim.claimForSeat(creature.getSeat(), creature.getClaimRate());
    creature.receiveExp(CreatureActionClaimGroundTile::getClaimExperience(creature));
    creature.recordWorkerStepRecovery();

    return false;
}
