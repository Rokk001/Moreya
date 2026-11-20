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

#ifndef CREATUREACTIONGROUPFOLLOW_H
#define CREATUREACTIONGROUPFOLLOW_H

#include "creatureaction/CreatureAction.h"

class Creature;

//! \brief A member of a combat group keeps its place in the formation behind its leader (the leader of a keeper's
//! group holds his position so that the group gathers around him). Fights are pushed on top of this action by the
//! creature's behaviours as usual. The action pops when the creature no longer keeps the formation (the group broke
//! up, retreats, or the creature became the leader of a raid group).
class CreatureActionGroupFollow : public CreatureAction
{
public:
    //! \brief Creates the action for the creature.
    CreatureActionGroupFollow(Creature& creature) :
        CreatureAction(creature)
    {}

    //! \brief Nothing to release.
    virtual ~CreatureActionGroupFollow()
    {}

    //! \brief Returns CreatureActionType::groupFollow.
    CreatureActionType getType() const override
    { return CreatureActionType::groupFollow; }

    //! \brief Binds the creature to handleGroupFollow.
    std::function<bool()> action() override;

    //! \brief Walks to the place of the formation when the creature is too far from it, else holds the position.
    //! \return true when the action popped and the creature can decide again at once.
    static bool handleGroupFollow(Creature& creature);
};

#endif // CREATUREACTIONGROUPFOLLOW_H
