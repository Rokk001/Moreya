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

#include "creatureskill/CreatureSkillCurseDot.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillCurseDotName = "CurseDot";

namespace
{
//! \brief Creates curse skills when a skill line names "CurseDot".
class CreatureSkillCurseDotFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty curse skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillCurseDot; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillCurseDotName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillCurseDotFactory);
}

//! \brief Returns "CurseDot".
const std::string& CreatureSkillCurseDot::getSkillName() const
{
    return CreatureSkillCurseDotName;
}

//! \brief Returns "curse".
const std::string& CreatureSkillCurseDot::getDamageKind() const
{
    return CreatureEffectDamageOverTime::KIND_CURSE;
}

//! \brief Returns "SpellCreatureWeak".
const std::string& CreatureSkillCurseDot::getParticleScript() const
{
    static const std::string PARTICLE = "SpellCreatureWeak";
    return PARTICLE;
}

//! \brief Returns a copy of the skill.
CreatureSkillCurseDot* CreatureSkillCurseDot::clone() const
{
    return new CreatureSkillCurseDot(*this);
}
