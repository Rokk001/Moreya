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

#include "creatureskill/CreatureSkillHold.h"

#include "creatureeffect/CreatureEffectHold.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"

#include <vector>

const std::string CreatureSkillHoldName = "Hold";

namespace
{
//! \brief Creates hold skills when a skill line names "Hold".
class CreatureSkillHoldFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty hold skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillHold; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillHoldName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillHoldFactory);
}

//! \brief Returns "Hold".
const std::string& CreatureSkillHold::getSkillName() const
{
    return CreatureSkillHoldName;
}

//! \brief The range on an enemy creature that is not held by this skill and not immune to control.
double CreatureSkillHold::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    if(entityAttack->getObjectType() == GameEntityType::creature &&
       static_cast<const Creature*>(entityAttack)->isControlImmune())
    {
        return 0.0;
    }
    return getRangeOnCreature(creature, entityAttack, "Hold");
}

//! \brief Holds the attacked creature (and the enemies of EXTRA_TARGETS near it) in place for Value turns times
//! LONGER.
bool CreatureSkillHold::tryUseFight(GameMap& gameMap, Creature* creature, float range,
    GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
        return false;

    const double turns = mValue * getPropertyValue("LONGER", 0, 1.0);
    const std::vector<Creature*> targets = getTargets(*creature, *static_cast<Creature*>(attackedObject));
    for(Creature* target : targets)
    {
        if(target->isControlImmune())
            continue;
        CreatureEffectHold* effect = new CreatureEffectHold(turns);
        tagEffect(effect);
        target->addCreatureEffect(effect);
    }
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillHold* CreatureSkillHold::clone() const
{
    return new CreatureSkillHold(*this);
}
