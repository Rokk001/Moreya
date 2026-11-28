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

#include "creatureskill/CreatureSkillPoison.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillPoisonName = "Poison";

namespace
{
//! \brief Creates poison skills when a skill line names "Poison".
class CreatureSkillPoisonFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty poison skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillPoison; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillPoisonName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillPoisonFactory);
}

//! \brief Returns "Poison".
const std::string& CreatureSkillPoison::getSkillName() const
{
    return CreatureSkillPoisonName;
}

//! \brief Returns "poison".
const std::string& CreatureSkillPoison::getDamageKind() const
{
    return CreatureEffectDamageOverTime::KIND_POISON;
}

//! \brief Returns a copy of the skill.
CreatureSkillPoison* CreatureSkillPoison::clone() const
{
    return new CreatureSkillPoison(*this);
}
