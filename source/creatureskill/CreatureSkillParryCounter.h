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

#ifndef CREATURESKILLPARRYCOUNTER_H
#define CREATURESKILLPARRYCOUNTER_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief PARRY_COUNTER: the creature parries a melee blow that would land with the chance Value (percent); the
//! blow then does no damage. COUNTER: a parried blow is answered with a melee blow of the first number times the
//! own blow. STUN: the counter blow stuns the attacker for the first number of turns. The skill is never cast; the
//! melee blow asks the creature for the parry (Creature::rollSkillParry).
class CreatureSkillParryCounter : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillParryCounter()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("ParryCounter").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillParryCounter* clone() const override;
};

#endif // CREATURESKILLPARRYCOUNTER_H
