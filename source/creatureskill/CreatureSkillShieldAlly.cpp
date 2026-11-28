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

#include "creatureskill/CreatureSkillShieldAlly.h"

#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"

const std::string CreatureSkillShieldAllyName = "ShieldAlly";

namespace
{
//! \brief Creates ally shield skills when a skill line names "ShieldAlly".
class CreatureSkillShieldAllyFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty ally shield skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillShieldAlly; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillShieldAllyName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillShieldAllyFactory);
}

//! \brief Returns "ShieldAlly".
const std::string& CreatureSkillShieldAlly::getSkillName() const
{
    return CreatureSkillShieldAllyName;
}

//! \brief Shields the fighting ally within the range with the lowest health share that has no running shield of
//! this skill.
bool CreatureSkillShieldAlly::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive())
        return false;

    Creature* chosen = creature->findWeakestFightingAlly(mRange, getTreeSkillId(), "Shield", false);
    if(chosen == nullptr)
        return false;

    creature->giveSkillShield(*chosen, *this, mValue, getEffectDuration());
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillShieldAlly* CreatureSkillShieldAlly::clone() const
{
    return new CreatureSkillShieldAlly(*this);
}
