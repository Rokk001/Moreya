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

#include "creatureskill/CreatureSkillAuraAllyDefense.h"

#include "creatureaction/CreatureAction.h"
#include "creatureeffect/CreatureEffectDefense.h"
#include "creatureeffect/CreatureEffectProtection.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "spells/Spell.h"
#include "utils/ConfigManager.h"

#include <vector>

const std::string CreatureSkillAuraAllyDefenseName = "AuraAllyDefense";

namespace
{
//! \brief Creates defence aura skills when a skill line names "AuraAllyDefense".
class CreatureSkillAuraAllyDefenseFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty defence aura skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillAuraAllyDefense; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillAuraAllyDefenseName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillAuraAllyDefenseFactory);
}

//! \brief Returns "AuraAllyDefense".
const std::string& CreatureSkillAuraAllyDefense::getSkillName() const
{
    return CreatureSkillAuraAllyDefenseName;
}

//! \brief Raises the defence of the own creatures within the radius while the creature fights and enough allies are
//! near (AuraAllyMinAllies, the creature itself counted).
bool CreatureSkillAuraAllyDefense::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive() || !creature->isActionInList(CreatureActionType::fight))
        return false;

    const std::vector<Creature*> allies = creature->getOwnCreaturesWithin(getEffectRadius());
    if(allies.size() < static_cast<size_t>(ConfigManager::getSingleton().getAuraAllyMinAllies()))
        return false;

    double value = mValue;
    double duration = mDuration + creature->getSkillPropertyValue("AURA_LINGER", 0, 0.0);
    creature->applyAuraDouble(value, duration, false);
    const double other = hasProperty("MAGIC") ? value : 0.0;
    const bool controlImmune = hasProperty("CONTROL_IMMUNE");
    for(Creature* ally : allies)
    {
        CreatureEffectDefense* effect = new CreatureEffectDefense(duration, value, other, other,
            "SpellCreatureDefense");
        tagEffect(effect);
        ally->addCreatureEffect(effect);
        if(controlImmune)
            ally->addCreatureEffect(new CreatureEffectProtection(duration, 1.0, 1.0, true, false));
    }

    for(Tile* tile : creature->getCoveredTiles())
    {
        Spell::fireSpellSound(*tile, "Heal");
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillAuraAllyDefense* CreatureSkillAuraAllyDefense::clone() const
{
    return new CreatureSkillAuraAllyDefense(*this);
}
