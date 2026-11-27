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

#include "creatureskill/CreatureSkillDamageOverTime.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureeffect/CreatureEffectSpeedChange.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntityType.h"

#include <algorithm>

//! \brief No particle script unless the kind names one.
const std::string& CreatureSkillDamageOverTime::getParticleScript() const
{
    static const std::string NONE;
    return NONE;
}

//! \brief The range on an enemy creature that carries fewer effects of this skill than STACK allows.
double CreatureSkillDamageOverTime::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    return getRangeOnCreature(creature, entityAttack, "DamageOverTime");
}

//! \brief Puts the damage over time on the target: the scaled total spread over the turns, with the heal reduction,
//! the jump on death and the slow of the rank properties.
bool CreatureSkillDamageOverTime::tryUseFight(GameMap& gameMap, Creature* creature, float range,
    GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
        return false;

    Creature* target = static_cast<Creature*>(attackedObject);
    const double turns = std::max(1.0, getEffectDuration());
    double damageFactor = creature->getDefinition()->getSkillDamageFactor();
    if(isTreeSkill())
        damageFactor *= creature->getTreeSpellDamageFactor();
    damageFactor *= creature->getSkillTargetDamageFactor(*target, this);
    const double perTurn = mValue * damageFactor / turns;
    // The heal reduction of the skill, else the one a passive of the caster gives its damage over time
    const double healFactor = getPropertyValue("HEAL_REDUCTION", 0,
        creature->getSkillPropertyValue("HEAL_REDUCTION", 0, 1.0));
    const double spread = getPropertyValue("SPREAD_ON_DEATH", 0, 0.0);
    CreatureEffectDamageOverTime* effect = new CreatureEffectDamageOverTime(turns, getDamageKind(), perTurn,
        creature->getName(), healFactor, spread, getParticleScript());
    tagEffect(effect);
    target->addCreatureEffect(effect);

    if(hasProperty("SLOW"))
    {
        CreatureEffectSpeedChange* slow = new CreatureEffectSpeedChange(getPropertyValue("SLOW", 1, turns),
            getPropertyValue("SLOW", 0, 1.0), "SpellCreatureSlow");
        tagEffect(slow);
        target->addCreatureEffect(slow);
    }

    if(notifyPlayerIfHit)
        target->notifyFightPlayer(attackedTile);
    return true;
}
