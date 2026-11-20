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

#include "creatureaction/CreatureActionGroupFollow.h"

#include "creatureaction/CreatureActionWalkToTile.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "game/CombatGroupManager.h"
#include "game/RaidManager.h"
#include "gamemap/GameMap.h"
#include "utils/LogManager.h"
#include "utils/MakeUnique.h"

#include <functional>
#include <list>
#include <vector>

//! \brief Binds the creature to the static handler.
std::function<bool()> CreatureActionGroupFollow::action()
{
    return std::bind(&CreatureActionGroupFollow::handleGroupFollow, std::ref(mCreature));
}

//! \brief Keeps the place of the formation computed by the group manager at its last update. A raid member first
//! loots an item a fallen keeper creature dropped that it sees (RA12), then returns to its place.
bool CreatureActionGroupFollow::handleGroupFollow(Creature& creature)
{
    CombatGroupManager& groups = creature.getGameMap()->getCombatGroups();
    if(!groups.shouldKeepFormation(creature))
    {
        creature.popAction();
        return true;
    }

    if(creature.isMoving())
        return false; // still walking to the place; check again next turn

    if(creature.getGameMap()->getRaid().doLoot(creature))
        return false; // took an item or walks to one; the place is kept again afterwards

    Tile* place = groups.getFormationTile(creature);
    if(place == nullptr)
        return false; // the leader of a keeper's group holds his position

    if(groups.isAtFormationPlace(creature, *place))
        return false; // hold the place; the action stays in the queue

    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
    {
        OD_LOG_ERR("name=" + creature.getName());
        return false;
    }

    std::list<Tile*> result = creature.getGameMap()->path(&creature, place);
    if(result.empty())
        return false; // no way to the place: hold and try again next turn

    std::vector<Ogre::Vector2> path;
    creature.tileToVector2(result, path, true, 0.0);
    if(path.empty())
        return false;

    creature.setWalkPath(EntityAnimation::walk_anim, EntityAnimation::idle_anim, true, true, path, true);
    creature.pushAction(Utils::make_unique<CreatureActionWalkToTile>(creature));
    return false;
}
