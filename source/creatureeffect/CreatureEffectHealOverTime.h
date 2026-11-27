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

#ifndef CREATUREEFFECTHEALOVERTIME_H
#define CREATUREEFFECTHEALOVERTIME_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <iosfwd>
#include <string>

//! \brief Heal over time of the role skills (HOT_AREA, HOT_SELF): the creature is healed the same amount every turn.
//! Unlike the plain Heal effect it knows its caster (each tick can give the caster mana back, MANA_REFUND) and
//! carries the rank properties MORE_ON_LOW (heals more below a health share), BURST_ON_LOW (one extra heal when the
//! creature drops below a health share) and EXTEND_ON_HIT (every hit the creature takes extends it).
class CreatureEffectHealOverTime : public CreatureEffectCombat
{
public:
    //! \brief Creates the heal over time.
    //! \param nbTurnsEffect Turns the effect lasts.
    //! \param healPerTurn Hit points healed every turn.
    //! \param casterName The creature that cast it (empty = none).
    CreatureEffectHealOverTime(double nbTurnsEffect, double healPerTurn, const std::string& casterName) :
        CreatureEffectCombat(nbTurnsEffect, "SpellCreatureHeal"),
        mHealPerTurn(healPerTurn),
        mCasterName(casterName),
        mLowShare(0.0),
        mLowFactor(1.0),
        mBurstShare(0.0),
        mBurstHeal(0.0),
        mExtendOnHit(0.0)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectHealOverTime() :
        CreatureEffectCombat(),
        mHealPerTurn(0.0),
        mLowShare(0.0),
        mLowFactor(1.0),
        mBurstShare(0.0),
        mBurstHeal(0.0),
        mExtendOnHit(0.0)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectHealOverTime()
    {}

    //! \brief The name under which the effect is registered and saved ("HealOverTime").
    virtual const std::string& getEffectName() const override;

    //! \brief Heals the factor times more while the health share of the creature is below the share (MORE_ON_LOW).
    inline void setMoreOnLow(double factor, double share)
    {
        mLowFactor = factor;
        mLowShare = share;
    }

    //! \brief Heals the hit points once when the health share of the creature drops below the share (BURST_ON_LOW).
    inline void setBurstOnLow(double heal, double share)
    {
        mBurstHeal = heal;
        mBurstShare = share;
    }

    //! \brief Every hit the creature takes extends the effect by the turns (EXTEND_ON_HIT).
    inline void setExtendOnHit(double turns)
    { mExtendOnHit = turns; }

    //! \brief Called when the creature takes a hit: extends the effect when it has EXTEND_ON_HIT.
    void notifyHit();

    //! \brief Writes the remaining turns and every part of the effect.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Heals the turn's share and lets the caster know of the tick (MANA_REFUND).
    virtual void applyEffect(Creature& creature) override;

private:
    //! \brief Hit points healed every turn.
    double mHealPerTurn;
    //! \brief The creature that cast the effect (empty = none).
    std::string mCasterName;
    //! \brief Health share below which the heal is multiplied by mLowFactor (0 = never).
    double mLowShare;
    //! \brief Factor on the heal below mLowShare.
    double mLowFactor;
    //! \brief Health share below which mBurstHeal is healed once (0 = never).
    double mBurstShare;
    //! \brief Hit points of the one extra heal (0 once it was used).
    double mBurstHeal;
    //! \brief Turns every hit adds (0 = none).
    double mExtendOnHit;
};

#endif // CREATUREEFFECTHEALOVERTIME_H
