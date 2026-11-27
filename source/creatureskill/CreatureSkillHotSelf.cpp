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

#include "creatureskill/CreatureSkillHotSelf.h"

#include "creatureaction/CreatureAction.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "utils/ConfigManager.h"

const std::string CreatureSkillHotSelfName = "HotSelf";

namespace
{
//! \brief Creates self heal over time skills when a skill line names "HotSelf".
class CreatureSkillHotSelfFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty self heal over time skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillHotSelf; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillHotSelfName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillHotSelfFactory);
}

//! \brief Returns "HotSelf".
const std::string& CreatureSkillHotSelf::getSkillName() const
{
    return CreatureSkillHotSelfName;
}

//! \brief Heals the creature over time while it fights below SkillHealSelfBelow and no heal of this skill runs.
bool CreatureSkillHotSelf::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive() || !creature->isActionInList(CreatureActionType::fight))
        return false;

    if(creature->getMaxHp() <= 0.0 ||
       creature->getHP() / creature->getMaxHp() >= ConfigManager::getSingleton().getSkillHealSelfBelow())
    {
        return false;
    }

    if(isTreeSkill() && creature->countActiveEffects("HealOverTime", getTreeSkillId()) > 0)
        return false;

    creature->giveSkillHealOverTime(*creature, *this, mValue, getEffectDuration());
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillHotSelf* CreatureSkillHotSelf::clone() const
{
    return new CreatureSkillHotSelf(*this);
}
