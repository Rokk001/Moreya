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

#include "creatureskill/CreatureSkillDrainHealAllies.h"

#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"
#include "entities/ItemEffects.h"
#include "entities/Tile.h"
#include "spells/Spell.h"

#include <vector>

const std::string CreatureSkillDrainHealAlliesName = "DrainHealAllies";

namespace
{
//! \brief Creates ally life drain skills when a skill line names "DrainHealAllies".
class CreatureSkillDrainHealAlliesFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty ally life drain skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillDrainHealAllies; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillDrainHealAlliesName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillDrainHealAlliesFactory);
}

//! \brief Returns "DrainHealAllies".
const std::string& CreatureSkillDrainHealAllies::getSkillName() const
{
    return CreatureSkillDrainHealAlliesName;
}

//! \brief The range on an enemy creature; 0 for any other target.
double CreatureSkillDrainHealAllies::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    if(entityAttack->getObjectType() != GameEntityType::creature)
        return 0.0;
    return mRange;
}

//! \brief Drains Value percent of the full health of the target and spreads it evenly over the hurt own creatures
//! within the radius (the caster included); the caster keeps it when none is hurt.
bool CreatureSkillDrainHealAllies::tryUseFight(GameMap& gameMap, Creature* creature, float range,
    GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
        return false;

    Creature* target = static_cast<Creature*>(attackedObject);
    const double drained = target->getMaxHp() * mValue / 100.0 * ItemEffects::targetDamageFactor(*creature, *target)
        * creature->getSkillTargetDamageFactor(*target, this);
    const double damageDone = target->takeDamage(creature, drained, 0.0, 0.0, 0.0, attackedTile, ko);
    creature->drainSkillMana(*target, damageDone, *this);
    if(damageDone > 0.0)
    {
        std::vector<Creature*> hurt;
        const std::vector<Creature*> allies = creature->getOwnCreaturesWithin(getEffectRadius());
        for(Creature* ally : allies)
        {
            if(ally->isHurt())
                hurt.push_back(ally);
        }
        if(hurt.empty())
            hurt.push_back(creature);
        const double share = damageDone / static_cast<double>(hurt.size());
        for(Creature* ally : hurt)
        {
            ally->heal(share);
            for(Tile* tile : ally->getCoveredTiles())
            {
                Spell::fireSpellEffect(*tile, "Heal", "HealCast");
            }
        }
    }
    if(notifyPlayerIfHit)
        target->notifyFightPlayer(attackedTile);
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillDrainHealAllies* CreatureSkillDrainHealAllies::clone() const
{
    return new CreatureSkillDrainHealAllies(*this);
}
