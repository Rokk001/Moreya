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

#include "creatureeffect/CreatureEffectHold.h"

#include "creatureeffect/CreatureEffectManager.h"

static const std::string CreatureEffectHoldName = "Hold";

namespace
{
//! \brief Creates hold effects when a saved game is loaded.
class CreatureEffectHoldFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty hold.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectHold; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectHoldName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectHoldFactory);
}

//! \brief Returns "Hold".
const std::string& CreatureEffectHold::getEffectName() const
{
    return CreatureEffectHoldName;
}
