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

#ifndef CREATURESKILLAURAALLYDEFENSE_H
#define CREATURESKILLAURAALLYDEFENSE_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief AURA_ALLY_Defense: while the creature fights and enough allies (AuraAllyMinAllies) stand within the radius,
//! every own creature within the radius gets Value more physical defence for Duration turns. MAGIC: also as much
//! magical and element defence. CONTROL_IMMUNE: the allies cannot be stunned, knocked down or held meanwhile.
//! LARGER_RADIUS multiplies the radius; AURA_LINGER and AURA_DOUBLE of the caster act as on every aura.
class CreatureSkillAuraAllyDefense : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillAuraAllyDefense()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("AuraAllyDefense").
    virtual const std::string& getSkillName() const override;

    //! \brief Gives the defence aura while the creature fights.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillAuraAllyDefense* clone() const override;
};

#endif // CREATURESKILLAURAALLYDEFENSE_H
