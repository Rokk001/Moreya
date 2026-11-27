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

#include "creatureeffect/CreatureEffectProtection.h"

#include "creatureeffect/CreatureEffectManager.h"

#include <istream>
#include <ostream>

static const std::string CreatureEffectProtectionName = "Protection";

namespace
{
//! \brief Creates protection effects when a saved game is loaded.
class CreatureEffectProtectionFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty protection.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectProtection; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectProtectionName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectProtectionFactory);
}

//! \brief Returns "Protection".
const std::string& CreatureEffectProtection::getEffectName() const
{
    return CreatureEffectProtectionName;
}

//! \brief Uses up the rescue from a deadly blow; true when it was still there.
bool CreatureEffectProtection::consumeSurviveDeadly()
{
    if(!mSurviveDeadly)
        return false;
    mSurviveDeadly = false;
    return true;
}

//! \brief Writes the remaining turns and the parts of the protection.
void CreatureEffectProtection::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << mDamageTakenFactor;
    os << "\t" << mAttackCooldownFactor;
    os << "\t" << (mControlImmune ? 1 : 0);
    os << "\t" << (mSurviveDeadly ? 1 : 0);
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectProtection::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    int controlImmune = 0;
    int surviveDeadly = 0;
    if(!(is >> mDamageTakenFactor >> mAttackCooldownFactor >> controlImmune >> surviveDeadly))
        return false;
    mControlImmune = (controlImmune != 0);
    mSurviveDeadly = (surviveDeadly != 0);
    return true;
}
