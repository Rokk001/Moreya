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

#include "creatureskill/CreatureSkillMark.h"

#include "creatureeffect/CreatureEffectMark.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"
#include "game/Seat.h"

#include <vector>

const std::string CreatureSkillMarkName = "Mark";

namespace
{
//! \brief Creates mark skills when a skill line names "Mark".
class CreatureSkillMarkFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty mark skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillMark; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillMarkName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillMarkFactory);
}

//! \brief Returns "Mark".
const std::string& CreatureSkillMark::getSkillName() const
{
    return CreatureSkillMarkName;
}

//! \brief The range on an enemy creature that carries no mark of this skill.
double CreatureSkillMark::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    return getRangeOnCreature(creature, entityAttack, "Mark");
}

//! \brief Marks the attacked creature (and the enemies of EXTRA_TARGETS near it).
bool CreatureSkillMark::tryUseFight(GameMap& gameMap, Creature* creature, float range,
    GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
        return false;

    const int32_t focusSeat = (hasProperty("FOCUS_TARGET") && creature->getSeat() != nullptr) ?
        creature->getSeat()->getId() : -1;
    const std::vector<Creature*> targets = getTargets(*creature, *static_cast<Creature*>(attackedObject));
    for(Creature* target : targets)
    {
        CreatureEffectMark* effect = new CreatureEffectMark(getEffectDuration(), mValue, focusSeat);
        tagEffect(effect);
        target->addCreatureEffect(effect);
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillMark* CreatureSkillMark::clone() const
{
    return new CreatureSkillMark(*this);
}
