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

#ifndef CREATURESKILLHOTAREA_H
#define CREATURESKILLHOTAREA_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief HOT_AREA: when an own creature within the radius is below SkillHealAreaBelow, every own creature within the
//! radius without a running heal of this skill is healed Value percent of the heal base of the caster, spread
//! evenly over Duration turns. LONGER, LARGER_RADIUS, CLEANSE, MORE_ON_LOW and BURST_ON_LOW tune it.
class CreatureSkillHotArea : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillHotArea()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("HotArea").
    virtual const std::string& getSkillName() const override;

    //! \brief Heals the own creatures around the creature over time.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillHotArea* clone() const override;
};

#endif // CREATURESKILLHOTAREA_H
