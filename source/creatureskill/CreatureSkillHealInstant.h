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

#ifndef CREATURESKILLHEALINSTANT_H
#define CREATURESKILLHEALINSTANT_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief HEAL_INSTANT: heals the own creature within the range with the lowest health share below SkillHealAllyBelow
//! by Value percent of the heal base at once. LESS_DAMAGE_TAKEN: the healed creature takes its damage times the
//! first number for the second number of turns. SURVIVE_DEADLY: once per fight of the caster the healed creature
//! is saved from one deadly blow during the first number of turns. CLEANSE and CLEANSE_ALL remove damage over
//! time from the healed creature.
class CreatureSkillHealInstant : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillHealInstant()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("HealInstant").
    virtual const std::string& getSkillName() const override;

    //! \brief Heals the weakest own creature within the range at once.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillHealInstant* clone() const override;
};

#endif // CREATURESKILLHEALINSTANT_H
