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

#include "creatureskill/CreatureSkillHealInstant.h"

#include "creatureeffect/CreatureEffectProtection.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "spells/Spell.h"
#include "utils/ConfigManager.h"

const std::string CreatureSkillHealInstantName = "HealInstant";

namespace
{
//! \brief Creates instant heal skills when a skill line names "HealInstant".
class CreatureSkillHealInstantFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty instant heal skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillHealInstant; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillHealInstantName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillHealInstantFactory);
}

//! \brief Returns "HealInstant".
const std::string& CreatureSkillHealInstant::getSkillName() const
{
    return CreatureSkillHealInstantName;
}

//! \brief Heals the own creature within the range with the lowest health share below SkillHealAllyBelow at once and
//! adds the protections of its rank properties.
bool CreatureSkillHealInstant::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive())
        return false;

    Creature* weakest = creature->findWeakestHurtAlly(mRange, ConfigManager::getSingleton().getSkillHealAllyBelow());
    if(weakest == nullptr)
        return false;

    creature->waiveSkillManaWhenLow(*weakest);
    weakest->heal(mValue / 100.0 * creature->getHealBase());
    if(hasProperty("CLEANSE") || hasProperty("CLEANSE_ALL"))
        weakest->cleanseDamageOverTime(hasProperty("CLEANSE_ALL"));
    if(hasProperty("LESS_DAMAGE_TAKEN"))
    {
        weakest->addCreatureEffect(new CreatureEffectProtection(getPropertyValue("LESS_DAMAGE_TAKEN", 1, 0.0),
            getPropertyValue("LESS_DAMAGE_TAKEN", 0, 1.0), 1.0, false, false));
    }
    if(hasProperty("SURVIVE_DEADLY") && creature->useOncePerFight(getTreeSkillId() + ":SURVIVE_DEADLY"))
    {
        weakest->addCreatureEffect(new CreatureEffectProtection(getPropertyValue("SURVIVE_DEADLY", 0, 0.0),
            1.0, 1.0, false, true));
    }

    for(Tile* tile : weakest->getCoveredTiles())
    {
        Spell::fireSpellEffect(*tile, "Heal", "HealCast");
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillHealInstant* CreatureSkillHealInstant::clone() const
{
    return new CreatureSkillHealInstant(*this);
}
