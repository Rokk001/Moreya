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

#ifndef CREATUREEFFECTDAMAGEOVERTIME_H
#define CREATUREEFFECTDAMAGEOVERTIME_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <iosfwd>
#include <string>

//! \brief Damage over time of the role skills (bleeding, poison, curse, burn): the creature takes the same damage
//! every turn, counted for the attacker that put it on. Optional: the creature heals less while it runs
//! (HEAL_REDUCTION) and the effect jumps to an ally of the creature near it when the creature dies
//! (SPREAD_ON_DEATH). The skill item Bleed and the Burn of the spells and traps stay their own effects: they carry
//! a fixed duration or no attacker in their saved form.
class CreatureEffectDamageOverTime : public CreatureEffectCombat
{
public:
    //! \brief Kind of damage over time "bleed"
    static const std::string KIND_BLEED;
    //! \brief Kind of damage over time "poison"
    static const std::string KIND_POISON;
    //! \brief Kind of damage over time "curse"
    static const std::string KIND_CURSE;
    //! \brief Kind of damage over time "burn"
    static const std::string KIND_BURN;

    //! \brief Creates the damage over time.
    //! \param nbTurnsEffect Turns the effect lasts.
    //! \param kind One of the KIND_ texts.
    //! \param damagePerTurn Damage taken every turn.
    //! \param attackerName The creature the damage is counted for (empty = none).
    //! \param healFactor Factor on every heal the creature receives while it runs (1 = unchanged).
    //! \param spreadRadius Radius in tiles of the jump on death (0 = no jump).
    //! \param particleEffectScript The particle script shown while it runs (may be empty).
    CreatureEffectDamageOverTime(double nbTurnsEffect, const std::string& kind, double damagePerTurn,
            const std::string& attackerName, double healFactor, double spreadRadius,
            const std::string& particleEffectScript) :
        CreatureEffectCombat(nbTurnsEffect, particleEffectScript),
        mKind(kind),
        mDamagePerTurn(damagePerTurn),
        mAttackerName(attackerName),
        mHealFactor(healFactor),
        mSpreadRadius(spreadRadius)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectDamageOverTime() :
        CreatureEffectCombat(),
        mDamagePerTurn(0.0),
        mHealFactor(1.0),
        mSpreadRadius(0.0)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectDamageOverTime()
    {}

    //! \brief The name under which the effect is registered and saved ("DamageOverTime").
    virtual const std::string& getEffectName() const override;

    //! \brief The factor on every heal the creature receives.
    virtual double getHealReceivedFactor() const override
    { return mHealFactor; }

    //! \brief The kind of the damage (KIND_BLEED, KIND_POISON, KIND_CURSE or KIND_BURN).
    inline const std::string& getKind() const
    { return mKind; }

    //! \brief The creature the damage is counted for.
    inline const std::string& getAttackerName() const
    { return mAttackerName; }

    //! \brief The radius of the jump on death (0 = no jump).
    inline double getSpreadRadius() const
    { return mSpreadRadius; }

    //! \brief Returns a new effect with the same kind, damage, attacker and heal factor for the remaining turns
    //! (used when the effect jumps or spreads to another creature).
    //! \param spreadRadius The jump radius of the copy (0 so that a jumped effect does not jump again).
    CreatureEffectDamageOverTime* copyForSpread(double spreadRadius) const;

    //! \brief Writes the remaining turns and every part of the effect.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Deals the damage of the turn; a kill by the effect is told to the attacker.
    virtual void applyEffect(Creature& creature) override;

private:
    //! \brief The kind of the damage.
    std::string mKind;
    //! \brief Damage taken every turn.
    double mDamagePerTurn;
    //! \brief The creature the damage is counted for (empty = none).
    std::string mAttackerName;
    //! \brief Factor on every heal the creature receives.
    double mHealFactor;
    //! \brief Radius in tiles of the jump on death (0 = no jump).
    double mSpreadRadius;
};

#endif // CREATUREEFFECTDAMAGEOVERTIME_H
