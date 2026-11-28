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

#include "creatureskill/CreatureSkillRole.h"

#include "entities/Creature.h"
#include "entities/GameEntityType.h"

#include <istream>
#include <ostream>

//! \brief Tells whether the creature has the level the skill needs (0 is reached with rank 1).
bool CreatureSkillRole::canBeUsedBy(const Creature* creature) const
{
    return creature->getLevel() >= mCreatureLevelMin;
}

//! \brief The duration column times the factor of LONGER (1 without it).
double CreatureSkillRole::getEffectDuration() const
{
    return mDuration * getPropertyValue("LONGER", 0, 1.0);
}

//! \brief The radius column, or the radius written with AREA, times the factor of LARGER_RADIUS (1 without it).
double CreatureSkillRole::getEffectRadius() const
{
    const double radius = getPropertyValue("AREA", 0, mRadius);
    return radius * getPropertyValue("LARGER_RADIUS", 0, 1.0);
}

//! \brief The range on an enemy creature that does not carry the most effects of this skill the STACK allows.
double CreatureSkillRole::getRangeOnCreature(const Creature* creature, GameEntity* entityAttack,
    const std::string& effectName) const
{
    if(entityAttack->getObjectType() != GameEntityType::creature)
        return 0.0;

    if(isTreeSkill())
    {
        const Creature* target = static_cast<const Creature*>(entityAttack);
        const double stack = getPropertyValue("STACK", 0, 1.0);
        if(static_cast<double>(target->countActiveEffects(effectName, getTreeSkillId())) >= stack)
            return 0.0;
    }

    return mRange;
}

//! \brief The target plus the enemies of the AREA or EXTRA_TARGETS property, nearest first.
std::vector<Creature*> CreatureSkillRole::getTargets(Creature& caster, Creature& target) const
{
    std::vector<Creature*> targets;
    targets.push_back(&target);
    double radius = 0.0;
    uint32_t extra = 0;
    if(hasProperty("AREA"))
    {
        radius = getEffectRadius();
        extra = UINT32_MAX;
    }
    else if(hasProperty("EXTRA_TARGETS"))
    {
        extra = static_cast<uint32_t>(getPropertyValue("EXTRA_TARGETS", 0, 0.0));
        radius = getPropertyValue("EXTRA_TARGETS", 1, mRange);
    }
    if(extra == 0 || radius <= 0.0)
        return targets;

    const std::vector<Creature*> nearby = caster.getEnemyCreaturesNear(target.getPosition(), radius);
    for(Creature* enemy : nearby)
    {
        if(enemy == &target)
            continue;
        if(targets.size() - 1 >= extra)
            break;
        targets.push_back(enemy);
    }
    return targets;
}

//! \brief Appends the names of the columns of the skill line to the format string.
void CreatureSkillRole::getFormatString(std::string& format) const
{
    CreatureSkill::getFormatString(format);
    if(!format.empty())
        format += "\t";

    format += "LevelMin\tRange\tRadius\tEffectDuration\tValue";
}

//! \brief Writes the columns of the skill line.
void CreatureSkillRole::exportToStream(std::ostream& os) const
{
    CreatureSkill::exportToStream(os);
    os << "\t" << mCreatureLevelMin;
    os << "\t" << mRange;
    os << "\t" << mRadius;
    os << "\t" << mDuration;
    os << "\t" << mValue;
}

//! \brief Reads the columns of the skill line; returns false when one is missing or malformed.
bool CreatureSkillRole::importFromStream(std::istream& is)
{
    if(!CreatureSkill::importFromStream(is))
        return false;

    if(!(is >> mCreatureLevelMin))
        return false;
    if(!(is >> mRange))
        return false;
    if(!(is >> mRadius))
        return false;
    if(!(is >> mDuration))
        return false;
    if(!(is >> mValue))
        return false;

    return true;
}

//! \brief Tells whether the other skill is the same class with the same values.
bool CreatureSkillRole::isEqual(const CreatureSkill& creatureSkill) const
{
    if(!CreatureSkill::isEqual(creatureSkill))
        return false;

    const CreatureSkillRole* skill = dynamic_cast<const CreatureSkillRole*>(&creatureSkill);
    if(skill == nullptr)
        return false;

    return (mCreatureLevelMin == skill->mCreatureLevelMin) && (mRange == skill->mRange) &&
        (mRadius == skill->mRadius) && (mDuration == skill->mDuration) && (mValue == skill->mValue);
}
