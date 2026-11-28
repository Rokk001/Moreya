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

#ifndef CREATURESKILLDAMAGEOVERTIME_H
#define CREATURESKILLDAMAGEOVERTIME_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief Common base of the damage over time kinds BLEED, POISON, CURSE_DOT and BURN_DOT: the enemy creature in the
//! range takes Value damage in total, spread evenly over Duration turns. Value is scaled like the damage of the
//! other skill tree spells (SkillDamageFactor of the type and Creature::getTreeSpellDamageFactor) and by the target
//! bonuses of the caster (Creature::getSkillTargetDamageFactor). STACK lets up to that many effects of the skill run
//! on one target; LONGER multiplies the turns; HEAL_REDUCTION (of the skill, else of a passive of the caster) makes
//! the target heal its first number times; SPREAD_ON_DEATH lets the effect jump to an ally of the target within the
//! first number in tiles when the target dies; SLOW also slows the target (factor, turns).
class CreatureSkillDamageOverTime : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillDamageOverTime()
    {}

    //! \brief Returns the range on an enemy creature that carries fewer effects of this skill than STACK allows.
    virtual double getRangeMax(const Creature* creature, GameEntity* entityAttack) const override;

    //! \brief Puts the damage over time on the attacked creature.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override;

protected:
    //! \brief The kind of damage (one of the CreatureEffectDamageOverTime::KIND_ texts).
    virtual const std::string& getDamageKind() const = 0;

    //! \brief The particle script shown on the target (may be empty).
    virtual const std::string& getParticleScript() const;
};

#endif // CREATURESKILLDAMAGEOVERTIME_H
