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

#ifndef CREATURESKILLTAUNT_H
#define CREATURESKILLTAUNT_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief TAUNT: while the tank fights, the nearest enemy creature within the range that is not taunted by it yet has
//! to attack it for Value turns. AREA: every enemy within the AREA radius of the tank. LESS_DAMAGE_DEALT: the taunted
//! enemies deal their damage times the first number.
class CreatureSkillTaunt : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillTaunt()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("Taunt").
    virtual const std::string& getSkillName() const override;

    //! \brief Taunts the enemies while the creature fights.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillTaunt* clone() const override;
};

#endif // CREATURESKILLTAUNT_H
