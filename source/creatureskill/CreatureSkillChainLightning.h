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

#ifndef CREATURESKILLCHAINLIGHTNING_H
#define CREATURESKILLCHAINLIGHTNING_H

#include "creatureskill/CreatureSkillGuidedBolt.h"

#include <string>

//! \brief CHAIN_LIGHTNING: a guided bolt with the line and values of GUIDEDBOLT. JUMP_TARGETS: the lightning also
//! hits that many more enemies nearest the target (within the second number in tiles, else within the range of the
//! skill); each of them gets a bolt of its own (see CreatureSkillMissileLaunch::tryUseFight).
class CreatureSkillChainLightning : public CreatureSkillGuidedBolt
{
public:
    //! \brief Destroys the skill.
    virtual ~CreatureSkillChainLightning()
    {}

    //! \brief Returns the name under which the skill is registered ("ChainLightning").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns a copy of the skill with the same parameters.
    virtual CreatureSkillChainLightning* clone() const override;
};

#endif // CREATURESKILLCHAINLIGHTNING_H
