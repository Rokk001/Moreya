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

#include "creatureskill/CreatureSkillChainLightning.h"

#include "creatureskill/CreatureSkillManager.h"

const std::string CreatureSkillChainLightningName = "ChainLightning";

namespace
{
//! \brief Creates chain lightning skills when a skill line names "ChainLightning".
class CreatureSkillChainLightningFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty chain lightning skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillChainLightning; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillChainLightningName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillChainLightningFactory);
}

//! \brief Returns "ChainLightning".
const std::string& CreatureSkillChainLightning::getSkillName() const
{
    return CreatureSkillChainLightningName;
}

//! \brief Returns a copy of the skill.
CreatureSkillChainLightning* CreatureSkillChainLightning::clone() const
{
    return new CreatureSkillChainLightning(*this);
}
