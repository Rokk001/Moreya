/*
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

#include "creatureaction/CreatureActionSearchInfirmary.h"

#include "entities/Creature.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "rooms/Room.h"
#include "rooms/RoomInfirmary.h"
#include "rooms/RoomType.h"
#include "utils/LogManager.h"

#include <list>
#include <vector>

//! \brief Gets the function that runs this action.
std::function<bool()> CreatureActionSearchInfirmary::action() // allowed-lambda: signature required by CreatureAction
{
    return std::bind(&CreatureActionSearchInfirmary::handleSearchInfirmary, std::ref(mCreature));
}

//! \brief Finds the cot of the nearest own infirmary that admits the sick creature now and that it can reach.
Tile* CreatureActionSearchInfirmary::findInfirmaryTile(Creature& creature)
{
    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
        return nullptr;

    GameMap* gameMap = creature.getGameMap();
    std::vector<Tile*> cotTiles;
    std::vector<Room*> infirmaries = gameMap->getRoomsByTypeAndSeat(RoomType::infirmary, creature.getSeat());
    for(Room* room : infirmaries)
    {
        if(room->numCoveredTiles() <= 0)
            continue;

        RoomInfirmary* infirmary = static_cast<RoomInfirmary*>(room);
        if(!infirmary->canAdmitSick(creature))
            continue;

        Tile* cotTile = infirmary->getSickCotTile(creature);
        if(cotTile == nullptr)
            continue;

        if((cotTile != myTile) && !gameMap->pathExists(&creature, myTile, cotTile))
            continue;

        cotTiles.push_back(cotTile);
    }

    if(cotTiles.empty())
        return nullptr;

    if(cotTiles.size() == 1)
        return cotTiles.front();

    // The nearest one along the walk
    Tile* chosenTile = nullptr;
    std::list<Tile*> path = gameMap->findBestPath(&creature, myTile, cotTiles, chosenTile);
    return (chosenTile != nullptr) ? chosenTile : cotTiles.front();
}

//! \brief Admits the creature in the infirmary it stands in, or walks it to the cot of the nearest one.
bool CreatureActionSearchInfirmary::handleSearchInfirmary(Creature& creature)
{
    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
    {
        OD_LOG_ERR("creature=" + creature.getName());
        creature.popAction();
        return true;
    }

    // Cured in the meantime (carried in, dropped on a cot) or the infection is over
    if(!creature.isPlagueSick())
    {
        creature.popAction();
        return true;
    }

    // Arrived: an own infirmary that takes the creature admits it whatever its HP. The admission replaces the actions
    // of the creature with the rest on its cot
    Room* room = myTile->getCoveringRoom();
    if((room != nullptr) && (room->getType() == RoomType::infirmary) && (room->getSeat() == creature.getSeat()))
    {
        if(static_cast<RoomInfirmary*>(room)->admitSick(creature))
            return false;
    }

    Tile* cotTile = findInfirmaryTile(creature);
    if((cotTile == nullptr) || !creature.setDestination(cotTile))
    {
        creature.popAction();
        return true;
    }

    return true;
}
