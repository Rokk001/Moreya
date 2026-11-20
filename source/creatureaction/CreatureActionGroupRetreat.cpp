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

#include "creatureaction/CreatureActionGroupRetreat.h"

#include "creatureaction/CreatureActionWalkToTile.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "game/CombatGroupManager.h"
#include "gamemap/GameMap.h"
#include "utils/LogManager.h"
#include "utils/MakeUnique.h"

#include <functional>
#include <list>
#include <vector>

//! \brief Binds the creature to the static handler.
std::function<bool()> CreatureActionGroupRetreat::action()
{
    return std::bind(&CreatureActionGroupRetreat::handleGroupRetreat, std::ref(mCreature));
}

//! \brief Walks to the gathering tile of the group's retreat; pops when the group no longer retreats.
bool CreatureActionGroupRetreat::handleGroupRetreat(Creature& creature)
{
    CombatGroupManager& groups = creature.getGameMap()->getCombatGroups();
    Tile* gathering = groups.getRetreatTile(creature);
    if(gathering == nullptr)
    {
        // The retreat is over (or the creature left its group): back to the group or to normal work
        creature.popAction();
        return true;
    }

    if(creature.isMoving())
        return false; // still walking; check again next turn

    if(groups.isAtGatheringTile(creature, *gathering))
        return false; // arrived: wait for the others

    Tile* myTile = creature.getPositionTile();
    if(myTile == nullptr)
    {
        OD_LOG_ERR("name=" + creature.getName());
        return false;
    }

    std::list<Tile*> result = creature.getGameMap()->path(&creature, gathering);
    if(result.empty())
        return false; // no way: wait and try again next turn

    std::vector<Ogre::Vector2> path;
    creature.tileToVector2(result, path, true, 0.0);
    if(path.empty())
        return false;

    creature.setWalkPath(EntityAnimation::walk_anim, EntityAnimation::idle_anim, true, true, path, true);
    creature.pushAction(Utils::make_unique<CreatureActionWalkToTile>(creature));
    return false;
}
