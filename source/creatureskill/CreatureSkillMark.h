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

#ifndef CREATURESKILLMARK_H
#define CREATURESKILLMARK_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief MARK: the enemy creature in the range takes its damage times Value for Duration turns. FOCUS_TARGET: the
//! creatures of the caster's side prefer the marked creature as target. EXTRA_TARGETS marks more enemies near it.
class CreatureSkillMark : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillMark()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("Mark").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns the range on an enemy creature that can still take the effect, 0 otherwise.
    virtual double getRangeMax(const Creature* creature, GameEntity* entityAttack) const override;

    //! \brief Marks the attacked creature.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillMark* clone() const override;
};

#endif // CREATURESKILLMARK_H
