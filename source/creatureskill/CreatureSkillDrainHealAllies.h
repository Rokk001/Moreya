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

#ifndef CREATURESKILLDRAINHEALALLIES_H
#define CREATURESKILLDRAINHEALALLIES_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief DRAIN_HEAL_ALLIES: takes Value percent of the full health of the enemy creature in the range and heals the
//! own creatures within the radius of the caster that are hurt (the caster included) with it, split evenly;
//! when none is hurt the caster keeps it. MANA_DRAIN: the target also loses the first number times the drained
//! hit points as mana and the caster gains it.
class CreatureSkillDrainHealAllies : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillDrainHealAllies()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("DrainHealAllies").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns the range on an enemy creature that can still take the effect, 0 otherwise.
    virtual double getRangeMax(const Creature* creature, GameEntity* entityAttack) const override;

    //! \brief Drains the attacked creature and heals the allies.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillDrainHealAllies* clone() const override;
};

#endif // CREATURESKILLDRAINHEALALLIES_H
