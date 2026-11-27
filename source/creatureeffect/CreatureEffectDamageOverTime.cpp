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

#include "creatureeffect/CreatureEffectDamageOverTime.h"

#include "creatureeffect/CreatureEffectManager.h"
#include "entities/Creature.h"
#include "gamemap/GameMap.h"

#include <istream>
#include <ostream>

static const std::string CreatureEffectDamageOverTimeName = "DamageOverTime";

const std::string CreatureEffectDamageOverTime::KIND_BLEED = "bleed";
const std::string CreatureEffectDamageOverTime::KIND_POISON = "poison";
const std::string CreatureEffectDamageOverTime::KIND_CURSE = "curse";
const std::string CreatureEffectDamageOverTime::KIND_BURN = "burn";

namespace
{
//! \brief Creates damage over time effects when a saved game is loaded.
class CreatureEffectDamageOverTimeFactory : public CreatureEffectFactory
{
    //! \brief Creates an empty damage over time.
    CreatureEffect* createCreatureEffect() const override
    { return new CreatureEffectDamageOverTime; }

    //! \brief The name of the effect in a saved game.
    const std::string& getCreatureEffectName() const override
    { return CreatureEffectDamageOverTimeName; }
};

// Register the factory
static CreatureEffectRegister reg(new CreatureEffectDamageOverTimeFactory);
}

//! \brief Returns "DamageOverTime".
const std::string& CreatureEffectDamageOverTime::getEffectName() const
{
    return CreatureEffectDamageOverTimeName;
}

//! \brief Copies kind, damage, attacker, heal factor, source and remaining turns for another creature.
CreatureEffectDamageOverTime* CreatureEffectDamageOverTime::copyForSpread(double spreadRadius) const
{
    CreatureEffectDamageOverTime* copy = new CreatureEffectDamageOverTime(mNbTurnsEffect, mKind, mDamagePerTurn,
        mAttackerName, mHealFactor, spreadRadius, getParticleEffectScript());
    copy->setSourceId(getSourceId());
    return copy;
}

//! \brief Deals the damage of the turn (only the active fraction in the last turn); tells the attacker of a kill.
void CreatureEffectDamageOverTime::applyEffect(Creature& creature)
{
    if(!creature.isAlive() || creature.getPositionTile() == nullptr)
        return;

    Creature* attacker = mAttackerName.empty() ? nullptr : creature.getGameMap()->getCreature(mAttackerName);
    creature.takeDamage(attacker, mDamagePerTurn * getTurnFraction(), 0.0, 0.0, 0.0, creature.getPositionTile(),
        false);
    if(!creature.isAlive() && attacker != nullptr)
        attacker->onSkillDamageOverTimeKill();
}

//! \brief Writes the remaining turns and every part of the effect.
void CreatureEffectDamageOverTime::exportToStream(std::ostream& os) const
{
    CreatureEffect::exportToStream(os);
    os << "\t" << (mKind.empty() ? "none" : mKind);
    os << "\t" << mDamagePerTurn;
    os << "\t" << (mAttackerName.empty() ? "none" : mAttackerName);
    os << "\t" << mHealFactor;
    os << "\t" << mSpreadRadius;
}

//! \brief Reads what exportToStream wrote.
bool CreatureEffectDamageOverTime::importFromStream(std::istream& is)
{
    if(!CreatureEffect::importFromStream(is))
        return false;
    if(!(is >> mKind >> mDamagePerTurn >> mAttackerName >> mHealFactor >> mSpreadRadius))
        return false;
    if(mKind == "none")
        mKind.clear();
    if(mAttackerName == "none")
        mAttackerName.clear();
    return true;
}
