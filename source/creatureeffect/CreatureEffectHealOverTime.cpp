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

#include "creatureeffect/CreatureEffectHealOverTime.h"

#include "creatureeffect/CreatureEffectManager.h"
#include "entities/Creature.h"
#include "gamemap/GameMap.h"

#include <istream>
#include <ostream>

static const std::string CreatureEffectHealOverTimeName = "HealOverTime";

namespace
{
//! \brief Creates heal over time effects when a saved game is loaded.
class CreatureEffectHealOverTimeFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty heal over time.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectHealOverTime; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectHealOverTimeName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectHealOverTimeFactory);
}

//! \brief Returns "HealOverTime".
const std::string& CreatureEffectHealOverTime::getEffectName() const
{
    return CreatureEffectHealOverTimeName;
}

//! \brief Extends the running effect by the turns of EXTEND_ON_HIT.
void CreatureEffectHealOverTime::notifyHit()
{
    if(mExtendOnHit > 0.0 && mNbTurnsEffect > 0.0)
        mNbTurnsEffect += mExtendOnHit;
}

//! \brief Heals the share of the turn (more below the low share, once the burst below the burst share) and tells
//! the caster of the tick.
void CreatureEffectHealOverTime::applyEffect(Creature& creature)
{
    if(!creature.isAlive() || creature.getMaxHp() <= 0.0)
        return;

    const double share = creature.getHP() / creature.getMaxHp();
    if(mBurstHeal > 0.0 && share < mBurstShare)
    {
        creature.heal(mBurstHeal);
        mBurstHeal = 0.0;
    }

    if(!creature.isHurt())
        return;

    double amount = mHealPerTurn * getTurnFraction();
    if(share < mLowShare)
        amount *= mLowFactor;
    creature.heal(amount);

    if(mCasterName.empty() || creature.getGameMap() == nullptr)
        return;
    Creature* caster = creature.getGameMap()->getCreature(mCasterName);
    if(caster != nullptr)
        caster->onSkillHealTick();
}

//! \brief Writes the remaining turns and every part of the effect.
void CreatureEffectHealOverTime::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << mHealPerTurn;
    os << "\t" << (mCasterName.empty() ? "none" : mCasterName);
    os << "\t" << mLowShare;
    os << "\t" << mLowFactor;
    os << "\t" << mBurstShare;
    os << "\t" << mBurstHeal;
    os << "\t" << mExtendOnHit;
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectHealOverTime::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    if(!(is >> mHealPerTurn >> mCasterName >> mLowShare >> mLowFactor >> mBurstShare >> mBurstHeal >> mExtendOnHit))
        return false;
    if(mCasterName == "none")
        mCasterName.clear();
    return true;
}
