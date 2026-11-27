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

#ifndef CREATURESKILLCURSEDOT_H
#define CREATURESKILLCURSEDOT_H

#include "creatureskill/CreatureSkillDamageOverTime.h"

#include <string>

//! \brief CURSE_DOT: damage over time of the kind "curse" (see CreatureSkillDamageOverTime for the columns and the
//! rank properties).
class CreatureSkillCurseDot : public CreatureSkillDamageOverTime
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillCurseDot()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("CurseDot").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillCurseDot* clone() const override;

protected:
    //! \brief The kind of damage ("curse").
    virtual const std::string& getDamageKind() const override;

    //! \brief The particle script shown on the target ("SpellCreatureWeak").
    virtual const std::string& getParticleScript() const override;
};

#endif // CREATURESKILLCURSEDOT_H
