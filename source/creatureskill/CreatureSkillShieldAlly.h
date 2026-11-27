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

#ifndef CREATURESKILLSHIELDALLY_H
#define CREATURESKILLSHIELDALLY_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief SHIELD_ALLY: gives the fighting ally within the range that has the lowest health share and no running shield
//! a shield that takes Value percent of the heal base of the caster as damage for Duration turns. DEFENSE: the
//! ally also gets the first number as defence while the shield lasts. HEAL_ON_BREAK: a broken shield heals the
//! first number percent of the heal base. REFLECT: the first number is the share of the absorbed damage thrown
//! back at the attacker.
class CreatureSkillShieldAlly : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillShieldAlly()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("ShieldAlly").
    virtual const std::string& getSkillName() const override;

    //! \brief Shields one fighting ally.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillShieldAlly* clone() const override;
};

#endif // CREATURESKILLSHIELDALLY_H
