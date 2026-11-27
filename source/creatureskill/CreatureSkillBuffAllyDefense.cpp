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

#include "creatureskill/CreatureSkillBuffAllyDefense.h"

#include "creatureeffect/CreatureEffectDefense.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "spells/Spell.h"

#include <vector>

const std::string CreatureSkillBuffAllyDefenseName = "BuffAllyDefense";

namespace
{
//! \brief Creates ally defence buff skills when a skill line names "BuffAllyDefense".
class CreatureSkillBuffAllyDefenseFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty ally defence buff skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillBuffAllyDefense; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillBuffAllyDefenseName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillBuffAllyDefenseFactory);
}

//! \brief Returns "BuffAllyDefense".
const std::string& CreatureSkillBuffAllyDefense::getSkillName() const
{
    return CreatureSkillBuffAllyDefenseName;
}

//! \brief Raises the defence of the fighting ally within the range with the lowest health share that has no running
//! buff of this skill (ALLIES_NEAR: also of the own creatures near that ally).
bool CreatureSkillBuffAllyDefense::tryUseSupport(GameMap& gameMap, Creature* creature) const
{
    if(!creature->isAlive())
        return false;

    Creature* chosen = creature->findWeakestFightingAlly(mRange, getTreeSkillId(), "Defense", false);
    if(chosen == nullptr)
        return false;

    std::vector<Creature*> targets;
    targets.push_back(chosen);
    if(hasProperty("ALLIES_NEAR"))
    {
        const std::vector<Creature*> nearby = chosen->getOwnCreaturesWithin(getPropertyValue("ALLIES_NEAR", 0, 0.0));
        for(Creature* mate : nearby)
        {
            if(mate != chosen)
                targets.push_back(mate);
        }
    }

    const double other = hasProperty("MAGIC") ? mValue : 0.0;
    for(Creature* target : targets)
    {
        CreatureEffectDefense* effect = new CreatureEffectDefense(getEffectDuration(), mValue, other, other,
            "SpellCreatureDefense");
        tagEffect(effect);
        target->addCreatureEffect(effect);
        for(Tile* tile : target->getCoveredTiles())
        {
            Spell::fireSpellEffect(*tile, "Defense", "DefenseCast");
        }
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillBuffAllyDefense* CreatureSkillBuffAllyDefense::clone() const
{
    return new CreatureSkillBuffAllyDefense(*this);
}
