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

#ifndef CREATUREACTIONGROUPRETREAT_H
#define CREATUREACTIONGROUPRETREAT_H

#include "creatureaction/CreatureAction.h"

class Creature;

//! \brief While its combat group retreats, a member walks to the gathering tile chosen by the leader (behind the next
//! own door, else at the nearest own room away from the enemy) and waits there. A retreating member starts no new
//! fight. The action pops when the retreat is over.
class CreatureActionGroupRetreat : public CreatureAction
{
public:
    //! \brief Creates the action for the creature.
    CreatureActionGroupRetreat(Creature& creature) :
        CreatureAction(creature)
    {}

    //! \brief Nothing to release.
    virtual ~CreatureActionGroupRetreat()
    {}

    //! \brief Returns CreatureActionType::groupRetreat.
    CreatureActionType getType() const override
    { return CreatureActionType::groupRetreat; }

    //! \brief Binds the creature to handleGroupRetreat.
    std::function<bool()> action() override;

    //! \brief Walks to the gathering tile of the retreat and waits there.
    //! \return true when the action popped and the creature can decide again at once.
    static bool handleGroupRetreat(Creature& creature);
};

#endif // CREATUREACTIONGROUPRETREAT_H
