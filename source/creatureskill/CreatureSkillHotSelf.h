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

#ifndef CREATURESKILLHOTSELF_H
#define CREATURESKILLHOTSELF_H

#include "creatureskill/CreatureSkillRole.h"

#include <string>

//! \brief HOT_SELF: while the creature fights and its health share is below SkillHealSelfBelow it heals itself Value
//! percent of its heal base, spread evenly over Duration turns. LONGER, CLEANSE and EXTEND_ON_HIT tune it.
class CreatureSkillHotSelf : public CreatureSkillRole
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillHotSelf()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("HotSelf").
    virtual const std::string& getSkillName() const override;

    //! \brief Heals the creature itself over time.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillHotSelf* clone() const override;
};

#endif // CREATURESKILLHOTSELF_H
