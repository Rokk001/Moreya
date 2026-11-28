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

#include "creatureeffect/CreatureEffectShield.h"

#include "creatureeffect/CreatureEffectManager.h"
#include "entities/Creature.h"

#include <algorithm>
#include <istream>
#include <ostream>

static const std::string CreatureEffectShieldName = "Shield";

namespace
{
//! \brief Creates shield effects when a saved game is loaded.
class CreatureEffectShieldFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty shield.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectShield; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectShieldName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectShieldFactory);
}

//! \brief Returns "Shield".
const std::string& CreatureEffectShield::getEffectName() const
{
    return CreatureEffectShieldName;
}

//! \brief Takes the damage up to the hit points left; a used up shield ends and heals by its heal on break.
double CreatureEffectShield::absorbDamage(Creature& creature, double damage, double& absorbed)
{
    absorbed = 0.0;
    if(mNbTurnsEffect <= 0.0 || mAbsorb <= 0.0 || damage <= 0.0)
        return damage;

    absorbed = std::min(mAbsorb, damage);
    mAbsorb -= absorbed;
    if(mAbsorb <= 0.0)
    {
        // The shield is broken: it ends after this turn
        mNbTurnsEffect = 0.0;
        if(mHealOnBreak > 0.0 && creature.isAlive())
            creature.heal(mHealOnBreak);
    }
    return damage - absorbed;
}

//! \brief Writes the remaining turns and hit points, the reflect share and the heal on break.
void CreatureEffectShield::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << mAbsorb;
    os << "\t" << mReflectShare;
    os << "\t" << mHealOnBreak;
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectShield::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    if(!(is >> mAbsorb >> mReflectShare >> mHealOnBreak))
        return false;
    return true;
}
