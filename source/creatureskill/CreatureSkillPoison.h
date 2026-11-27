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

#ifndef CREATURESKILLPOISON_H
#define CREATURESKILLPOISON_H

#include "creatureskill/CreatureSkillDamageOverTime.h"

#include <string>

//! \brief POISON: damage over time of the kind "poison" (see CreatureSkillDamageOverTime for the columns and the
//! rank properties).
class CreatureSkillPoison : public CreatureSkillDamageOverTime
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillPoison()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("Poison").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillPoison* clone() const override;

protected:
    //! \brief The kind of damage ("poison").
    virtual const std::string& getDamageKind() const override;
};

#endif // CREATURESKILLPOISON_H
