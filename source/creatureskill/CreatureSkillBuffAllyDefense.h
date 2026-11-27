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

#ifndef CREATURESKILLBUFFALLYDEFENSE_H
#define CREATURESKILLBUFFALLYDEFENSE_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief BUFF_ALLY_Defense: while the creature fights it gives the fighting ally within the range that has the
//! lowest health share and no running buff of this skill Value more physical defence for Duration turns.
//! MAGIC: also as much magical and element defence. ALLIES_NEAR: also every own creature within the first
//! number in tiles of that ally.
class CreatureSkillBuffAllyDefense : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillBuffAllyDefense()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("BuffAllyDefense").
    virtual const std::string& getSkillName() const override;

    //! \brief Buffs one fighting ally.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillBuffAllyDefense* clone() const override;
};

#endif // CREATURESKILLBUFFALLYDEFENSE_H
