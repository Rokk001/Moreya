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

#include "creatureskill/CreatureSkillSlow.h"

#include "creatureeffect/CreatureEffectHold.h"
#include "creatureeffect/CreatureEffectSpeedChange.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "spells/Spell.h"
#include "utils/LogManager.h"

#include <istream>
#include <vector>

const std::string CreatureSkillSlowName = "Slow";

namespace
{
class CreatureSkillSlowFactory : public CreatureSkillFactory
{
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillSlow; }

    const std::string& getCreatureSkillName() const override
    { return CreatureSkillSlowName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillSlowFactory);
}

const std::string& CreatureSkillSlow::getSkillName() const
{
    return CreatureSkillSlowName;
}

//! \brief Returns the range of the skill; 0 for targets that are not creatures (a skill of the skill tree: also for a
//! target that already suffers from it).
double CreatureSkillSlow::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    // Slow can be cast on creatures only
    if(entityAttack->getObjectType() != GameEntityType::creature)
        return 0.0;

    // A skill of the skill tree is not cast on a target that already suffers from it
    if(isTreeSkill() && static_cast<Creature*>(entityAttack)->hasActiveEffectSource(getTreeSkillId()))
        return 0.0;

    return mMaxRange;
}

bool CreatureSkillSlow::canBeUsedBy(const Creature* creature) const
{
    if(creature->getLevel() < mCreatureLevelMin)
        return false;

    return true;
}

//! \brief Puts the effect on the attacked creature; a skill of the skill tree tags it with its id. Rank properties:
//! AREA slows every enemy within its radius of the target, LONGER multiplies the turns, HOLD also holds the target in
//! place for its first number of turns.
bool CreatureSkillSlow::tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
    {
        OD_LOG_ERR("creature=" + creature->getName() + ", attackedObject=" + attackedObject->getName() + ", attackedTile=" + Tile::displayAsString(attackedTile));
        return false;
    }

    Creature* attackedCreature = static_cast<Creature*>(attackedObject);
    std::vector<Creature*> targets;
    targets.push_back(attackedCreature);
    if(hasProperty("AREA"))
    {
        const std::vector<Creature*> nearby = creature->getEnemyCreaturesNear(attackedCreature->getPosition(),
            getPropertyValue("AREA", 0, 0.0) * getPropertyValue("LARGER_RADIUS", 0, 1.0));
        for(Creature* enemy : nearby)
        {
            if(enemy != attackedCreature)
                targets.push_back(enemy);
        }
    }

    const double duration = mEffectDuration * getPropertyValue("LONGER", 0, 1.0);
    for(Creature* target : targets)
    {
        CreatureEffectSpeedChange* effect = new CreatureEffectSpeedChange(duration, mEffectValue, "SpellCreatureSlow");
        tagEffect(effect);
        target->addCreatureEffect(effect);
    }

    if(hasProperty("HOLD") && !attackedCreature->isControlImmune())
    {
        CreatureEffectHold* hold = new CreatureEffectHold(getPropertyValue("HOLD", 0, 0.0));
        tagEffect(hold);
        attackedCreature->addCreatureEffect(hold);
    }

    return true;
}

CreatureSkillSlow* CreatureSkillSlow::clone() const
{
    return new CreatureSkillSlow(*this);
}

void CreatureSkillSlow::getFormatString(std::string& format) const
{
    CreatureSkill::getFormatString(format);
    if(!format.empty())
        format += "\t";

    format += "RangeMax\tLevelMin\tEffectDuration\tEffectValue";

}

void CreatureSkillSlow::exportToStream(std::ostream& os) const
{
    CreatureSkill::exportToStream(os);
    os << "\t" << mMaxRange;
    os << "\t" << mCreatureLevelMin;
    os << "\t" << mEffectDuration;
    os << "\t" << mEffectValue;
}

bool CreatureSkillSlow::importFromStream(std::istream& is)
{
    if(!CreatureSkill::importFromStream(is))
        return false;

    if(!(is >> mMaxRange))
        return false;
    if(!(is >> mCreatureLevelMin))
        return false;
    if(!(is >> mEffectDuration))
        return false;
    if(!(is >> mEffectValue))
        return false;

    return true;
}

bool CreatureSkillSlow::isEqual(const CreatureSkill& creatureSkill) const
{
    if(!CreatureSkill::isEqual(creatureSkill))
        return false;

    const CreatureSkillSlow* skill = dynamic_cast<const CreatureSkillSlow*>(&creatureSkill);
    if(skill == nullptr)
        return false;

    if(mMaxRange != skill->mMaxRange)
        return false;
    if(mCreatureLevelMin != skill->mCreatureLevelMin)
        return false;
    if(mEffectDuration != skill->mEffectDuration)
        return false;
    if(mEffectValue != skill->mEffectValue)
        return false;

    return true;
}
