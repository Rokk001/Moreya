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

#include "creatureeffect/CreatureEffectTaunt.h"

#include "creatureeffect/CreatureEffectManager.h"

#include <istream>
#include <ostream>

static const std::string CreatureEffectTauntName = "Taunt";

namespace
{
//! \brief Creates taunt effects when a saved game is loaded.
class CreatureEffectTauntFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty taunt.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectTaunt; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectTauntName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectTauntFactory);
}

//! \brief Returns "Taunt".
const std::string& CreatureEffectTaunt::getEffectName() const
{
    return CreatureEffectTauntName;
}

//! \brief Writes the remaining turns, the tank and the damage factor.
void CreatureEffectTaunt::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << (mTaunterName.empty() ? "none" : mTaunterName);
    os << "\t" << mDamageDealtFactor;
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectTaunt::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    if(!(is >> mTaunterName >> mDamageDealtFactor))
        return false;
    if(mTaunterName == "none")
        mTaunterName.clear();
    return true;
}
