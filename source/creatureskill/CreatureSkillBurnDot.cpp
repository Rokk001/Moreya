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

#include "creatureskill/CreatureSkillBurnDot.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillBurnDotName = "BurnDot";

namespace
{
//! \brief Creates burn skills when a skill line names "BurnDot".
class CreatureSkillBurnDotFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty burn skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillBurnDot; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillBurnDotName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillBurnDotFactory);
}

//! \brief Returns "BurnDot".
const std::string& CreatureSkillBurnDot::getSkillName() const
{
    return CreatureSkillBurnDotName;
}

//! \brief Returns "burn".
const std::string& CreatureSkillBurnDot::getDamageKind() const
{
    return CreatureEffectDamageOverTime::KIND_BURN;
}

//! \brief Returns a copy of the skill.
CreatureSkillBurnDot* CreatureSkillBurnDot::clone() const
{
    return new CreatureSkillBurnDot(*this);
}
