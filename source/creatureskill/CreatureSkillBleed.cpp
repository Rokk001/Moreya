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

#include "creatureskill/CreatureSkillBleed.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillBleedName = "Bleed";

namespace
{
//! \brief Creates bleeding skills when a skill line names "Bleed".
class CreatureSkillBleedFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty bleeding skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillBleed; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillBleedName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillBleedFactory);
}

//! \brief Returns "Bleed".
const std::string& CreatureSkillBleed::getSkillName() const
{
    return CreatureSkillBleedName;
}

//! \brief Returns "bleeding".
const std::string& CreatureSkillBleed::getDamageKind() const
{
    return CreatureEffectDamageOverTime::KIND_BLEED;
}

//! \brief Returns a copy of the skill.
CreatureSkillBleed* CreatureSkillBleed::clone() const
{
    return new CreatureSkillBleed(*this);
}
