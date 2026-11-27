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

#include "creatureskill/CreatureSkillFlurry.h"

#include "creatureeffect/CreatureEffectDamageOverTime.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"

#include <algorithm>
#include <istream>
#include <ostream>
#include <vector>

const std::string CreatureSkillFlurryName = "Flurry";

namespace
{
//! \brief Creates flurry skills when a skill line names "Flurry".
class CreatureSkillFlurryFactory : public CreatureSkillFactory
{
    //! \brief Creates an empty flurry skill.
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillFlurry; }

    //! \brief The skill name used in skill lines.
    const std::string& getCreatureSkillName() const override
    { return CreatureSkillFlurryName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillFlurryFactory);
}

//! \brief Returns "Flurry".
const std::string& CreatureSkillFlurry::getSkillName() const
{
    return CreatureSkillFlurryName;
}

//! \brief The range on an enemy creature, 0 for any other target.
double CreatureSkillFlurry::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    if(entityAttack->getObjectType() != GameEntityType::creature)
        return 0.0;
    return mRange;
}

//! \brief Tells whether the creature has the level the skill needs (0 is reached with rank 1).
bool CreatureSkillFlurry::canBeUsedBy(const Creature* creature) const
{
    return creature->getLevel() >= mCreatureLevelMin;
}

//! \brief Strikes every enemy within the radius (the attacked one included) with the blows of the rank, moves them by
//! PUSH or PULL and leaves the bleeding of BLEED_ON_HIT; DOUBLE_CAST strikes twice. The hits shorten the cooldown by
//! COOLDOWN_PER_HIT of the caster.
bool CreatureSkillFlurry::tryUseFight(GameMap& gameMap, Creature* creature, float range,
    GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
        return false;

    Creature* attacked = static_cast<Creature*>(attackedObject);
    const double radius = mRadius * getPropertyValue("LARGER_RADIUS", 0, 1.0);
    std::vector<Creature*> targets = creature->getEnemyCreaturesNear(creature->getPosition(), radius);
    if(std::find(targets.begin(), targets.end(), attacked) == targets.end())
        targets.insert(targets.begin(), attacked);

    const uint32_t passes = hasProperty("DOUBLE_CAST") ? 2 : 1;
    const uint32_t blows = static_cast<uint32_t>(std::max(0.0, mBlows));
    const bool canCrit = hasProperty("CAN_CRIT");
    uint32_t hits = 0;
    for(uint32_t pass = 0; pass < passes; ++pass)
    {
        for(Creature* target : targets)
        {
            if(!target->isAlive() || target->rollAreaDodge())
                continue;

            for(uint32_t blow = 0; blow < blows && target->isAlive(); ++blow)
                creature->skillMeleeBlow(*target, mFactor, canCrit, ko);
            ++hits;

            if(hasProperty("PUSH"))
                creature->pushSkillTarget(*target, getPropertyValue("PUSH", 0, 0.0), false);
            else if(hasProperty("PULL"))
                creature->pushSkillTarget(*target, getPropertyValue("PULL", 0, 0.0), true);

            if(hasProperty("BLEED_ON_HIT") && target->isAlive())
            {
                // The bleeding is scaled like the damage of the other skill tree spells
                const double turns = std::max(1.0, getPropertyValue("BLEED_ON_HIT", 1, 1.0));
                const double total = getPropertyValue("BLEED_ON_HIT", 0, 0.0) * creature->getTreeSpellDamageFactor();
                CreatureEffectDamageOverTime* bleed = new CreatureEffectDamageOverTime(turns,
                    CreatureEffectDamageOverTime::KIND_BLEED, total / turns,
                    creature->getName(), creature->getSkillPropertyValue("HEAL_REDUCTION", 0, 1.0), 0.0, "");
                tagEffect(bleed);
                target->addCreatureEffect(bleed);
            }
        }
    }
    creature->addSkillCooldownCut(static_cast<double>(hits) * creature->getSkillPropertyValue("COOLDOWN_PER_HIT", 0, 0.0));
    if(notifyPlayerIfHit)
        attacked->notifyFightPlayer(attackedTile);
    return true;
}

//! \brief Returns a copy of the skill.
CreatureSkillFlurry* CreatureSkillFlurry::clone() const
{
    return new CreatureSkillFlurry(*this);
}

//! \brief Appends the names of the columns of the skill line to the format string.
void CreatureSkillFlurry::getFormatString(std::string& format) const
{
    CreatureSkill::getFormatString(format);
    if(!format.empty())
        format += "\t";

    format += "LevelMin\tRange\tRadius\tBlows\tFactor";
}

//! \brief Writes the columns of the skill line.
void CreatureSkillFlurry::exportToStream(std::ostream& os) const
{
    CreatureSkill::exportToStream(os);
    os << "\t" << mCreatureLevelMin;
    os << "\t" << mRange;
    os << "\t" << mRadius;
    os << "\t" << mBlows;
    os << "\t" << mFactor;
}

//! \brief Reads the columns of the skill line; returns false when one is missing or malformed.
bool CreatureSkillFlurry::importFromStream(std::istream& is)
{
    if(!CreatureSkill::importFromStream(is))
        return false;

    if(!(is >> mCreatureLevelMin))
        return false;
    if(!(is >> mRange))
        return false;
    if(!(is >> mRadius))
        return false;
    if(!(is >> mBlows))
        return false;
    if(!(is >> mFactor))
        return false;

    return true;
}

//! \brief Tells whether the other skill is the same class with the same values.
bool CreatureSkillFlurry::isEqual(const CreatureSkill& creatureSkill) const
{
    if(!CreatureSkill::isEqual(creatureSkill))
        return false;

    const CreatureSkillFlurry* skill = dynamic_cast<const CreatureSkillFlurry*>(&creatureSkill);
    if(skill == nullptr)
        return false;

    return (mCreatureLevelMin == skill->mCreatureLevelMin) && (mRange == skill->mRange) &&
        (mRadius == skill->mRadius) && (mBlows == skill->mBlows) && (mFactor == skill->mFactor);
}
