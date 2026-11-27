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

#include "creatureeffect/CreatureEffectMark.h"

#include "creatureeffect/CreatureEffectManager.h"

#include <istream>
#include <ostream>

static const std::string CreatureEffectMarkName = "Mark";

namespace
{
//! \brief Creates mark effects when a saved game is loaded.
class CreatureEffectMarkFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty mark.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectMark; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectMarkName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectMarkFactory);
}

//! \brief Returns "Mark".
const std::string& CreatureEffectMark::getEffectName() const
{
    return CreatureEffectMarkName;
}

//! \brief Writes the remaining turns, the factor and the focus seat.
void CreatureEffectMark::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << mDamageTakenFactor;
    os << "\t" << mFocusSeatId;
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectMark::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    if(!(is >> mDamageTakenFactor >> mFocusSeatId))
        return false;
    return true;
}
