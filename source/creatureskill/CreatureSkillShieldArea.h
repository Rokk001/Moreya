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

#ifndef CREATURESKILLSHIELDAREA_H
#define CREATURESKILLSHIELDAREA_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief SHIELD_AREA: while the creature fights, every own creature within the radius that has no running shield of
//! this skill gets a shield of Value percent of the heal base of the caster for Duration turns. DEFENSE,
//! HEAL_ON_BREAK and REFLECT as for SHIELD_ALLY; LARGER_RADIUS multiplies the radius.
class CreatureSkillShieldArea : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillShieldArea()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("ShieldArea").
    virtual const std::string& getSkillName() const override;

    //! \brief Shields the own creatures around the creature while it fights.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillShieldArea* clone() const override;
};

#endif // CREATURESKILLSHIELDAREA_H
