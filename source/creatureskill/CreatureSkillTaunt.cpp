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

#include "creatureskill/CreatureSkillTaunt.h"

#include "creatureaction/CreatureAction.h"
#include "creatureeffect/CreatureEffectTaunt.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "spells/Spell.h"

#include <vector>

const std::string CreatureSkillTauntName = "Taunt";

namespace
{
//! \brief Creates taunt skills when a skill line names "Taunt".
class CreatureSkillTauntFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty taunt skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillTaunt; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillTauntName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillTauntFactory);
}

//! \brief Returns "Taunt".
const std::string& CreatureSkillTaunt::getSkillName() const
{
    return CreatureSkillTauntName;
}

//! \brief Taunts the nearest enemy within the range that the creature does not taunt yet (AREA: every enemy within
//! the AREA radius); used only while the creature fights.
bool CreatureSkillTaunt::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive() || !creature->isActionInList(CreatureActionType::fight))
        return false;

    const bool area = hasProperty("AREA");
    const double reach = area ? getEffectRadius() : mRange;
    const std::vector<Creature*> enemies = creature->getEnemyCreaturesNear(creature->getPosition(), reach);
    const double damageFactor = getPropertyValue("LESS_DAMAGE_DEALT", 0, 1.0);
    bool taunted = false;
    for(Creature* enemy : enemies)
    {
        if(enemy->getTaunter() == creature)
            continue;

        CreatureEffectTaunt* effect = new CreatureEffectTaunt(mValue, creature->getName(), damageFactor);
        tagEffect(effect);
        enemy->addCreatureEffect(effect);
        taunted = true;
        if(!area)
            break;
    }

    if(!taunted)
        return false;

    for(Tile* tile : creature->getCoveredTiles())
    {
        Spell::fireSpellSound(*tile, "Heal");
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillTaunt* CreatureSkillTaunt::clone() const
{
    return new CreatureSkillTaunt(*this);
}
