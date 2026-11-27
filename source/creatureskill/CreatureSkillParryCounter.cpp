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

#include "creatureskill/CreatureSkillParryCounter.h"

#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillParryCounterName = "ParryCounter";

namespace
{
//! \brief Creates parry skills when a skill line names "ParryCounter".
class CreatureSkillParryCounterFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty parry skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillParryCounter; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillParryCounterName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillParryCounterFactory);
}

//! \brief Returns "ParryCounter".
const std::string& CreatureSkillParryCounter::getSkillName() const
{
    return CreatureSkillParryCounterName;
}

//! \brief Returns a copy of the skill.
CreatureSkillParryCounter* CreatureSkillParryCounter::clone() const
{
    return new CreatureSkillParryCounter(*this);
}
