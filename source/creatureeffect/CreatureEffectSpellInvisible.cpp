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

#include "creatureeffect/CreatureEffectSpellInvisible.h"

#include "creatureeffect/CreatureEffectManager.h"
#include "entities/Creature.h"

const std::string CreatureEffectSpellInvisible::EFFECT_NAME = "SpellInvisible";

namespace
{
//! \brief Creates the effect of the Invisibility spell when a saved game names "SpellInvisible"
class CreatureEffectSpellInvisibleFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty effect that the loader fills
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectSpellInvisible; }

    //! \brief The name of the effect in a saved game
    const std::string& getCreatureEffectName() const override
    {
        return CreatureEffectSpellInvisible::EFFECT_NAME;
    }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectSpellInvisibleFactory);
}

//! \brief Returns the registered name of the effect.
const std::string& CreatureEffectSpellInvisible::getEffectName() const
{
    return EFFECT_NAME;
}

//! \brief Nothing changes from turn to turn: the invisible state is deduced from the running effect.
void CreatureEffectSpellInvisible::applyEffect(Creature& creature)
{
}
