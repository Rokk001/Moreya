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

#ifndef CREATURESKILLHOLD_H
#define CREATURESKILLHOLD_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief HOLD: the enemy creature in the range cannot walk for Value turns (it still attacks what it reaches).
//! LONGER multiplies the turns, EXTRA_TARGETS holds more enemies near it. A creature that is immune to control
//! (CONTROL_IMMUNE) is not held.
class CreatureSkillHold : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillHold()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("Hold").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns the range on an enemy creature that can still take the effect, 0 otherwise.
    virtual double getRangeMax(const Creature* creature, GameEntity* entityAttack) const override;

    //! \brief Holds the attacked creature in place.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillHold* clone() const override;
};

#endif // CREATURESKILLHOLD_H
