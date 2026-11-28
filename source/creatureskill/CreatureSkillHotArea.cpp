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

#include "creatureskill/CreatureSkillHotArea.h"

#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "utils/ConfigManager.h"

#include <vector>

const std::string CreatureSkillHotAreaName = "HotArea";

namespace
{
//! \brief Creates area heal over time skills when a skill line names "HotArea".
class CreatureSkillHotAreaFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty area heal over time skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillHotArea; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillHotAreaName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillHotAreaFactory);
}

//! \brief Returns "HotArea".
const std::string& CreatureSkillHotArea::getSkillName() const
{
    return CreatureSkillHotAreaName;
}

//! \brief Heals every own creature within the radius over time when one of them is below SkillHealAreaBelow; a
//! creature with a running heal of this skill is left out.
bool CreatureSkillHotArea::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive())
        return false;

    const double below = ConfigManager::getSingleton().getSkillHealAreaBelow();
    const std::vector<Creature*> allies = creature->getOwnCreaturesWithin(getEffectRadius());
    std::vector<Creature*> targets;
    bool anyHurt = false;
    for(Creature* ally : allies)
    {
        if(isTreeSkill() && ally->countActiveEffects("HealOverTime", getTreeSkillId()) > 0)
            continue;
        targets.push_back(ally);
        if(ally->getMaxHp() > 0.0 && ally->getHP() / ally->getMaxHp() < below)
            anyHurt = true;
    }
    if(!anyHurt)
        return false;

    for(Creature* ally : targets)
        creature->giveSkillHealOverTime(*ally, *this, mValue, getEffectDuration());
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillHotArea* CreatureSkillHotArea::clone() const
{
    return new CreatureSkillHotArea(*this);
}
