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

#include "creatureskill/CreatureSkillShieldArea.h"

#include "creatureaction/CreatureAction.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"

#include <vector>

const std::string CreatureSkillShieldAreaName = "ShieldArea";

namespace
{
//! \brief Creates group shield skills when a skill line names "ShieldArea".
class CreatureSkillShieldAreaFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty group shield skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillShieldArea; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillShieldAreaName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillShieldAreaFactory);
}

//! \brief Returns "ShieldArea".
const std::string& CreatureSkillShieldArea::getSkillName() const
{
    return CreatureSkillShieldAreaName;
}

//! \brief Shields every own creature within the radius without a running shield of this skill while the creature
//! fights.
bool CreatureSkillShieldArea::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive() || !creature->isActionInList(CreatureActionType::fight))
        return false;

    bool shielded = false;
    const std::vector<Creature*> allies = creature->getOwnCreaturesWithin(getEffectRadius());
    for(Creature* ally : allies)
    {
        if(isTreeSkill() && ally->countActiveEffects("Shield", getTreeSkillId()) > 0)
            continue;
        creature->giveSkillShield(*ally, *this, mValue, getEffectDuration());
        shielded = true;
    }
    return shielded;
}

//! \brief Returns a copy of the skill.
CreatureSkillShieldArea* CreatureSkillShieldArea::clone() const
{
    return new CreatureSkillShieldArea(*this);
}
