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

#ifndef CREATUREEFFECTSHIELD_H
#define CREATUREEFFECTSHIELD_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <iosfwd>
#include <string>

//! \brief Absorb shield of a healer: it takes the damage of the creature until its hit points are used up or its time
//! runs out. Optional: a share of the damage it takes is thrown back at the attacker (REFLECT) and the creature is
//! healed when the shield breaks (HEAL_ON_BREAK).
class CreatureEffectShield : public CreatureEffectCombat
{
public:
    //! \brief Creates the shield.
    //! \param nbTurnsEffect Turns the shield lasts.
    //! \param absorb Hit points of damage the shield takes.
    //! \param reflectShare Share of the absorbed damage thrown back at the attacker (0 = none).
    //! \param healOnBreak Hit points healed when the shield breaks (0 = none).
    CreatureEffectShield(double nbTurnsEffect, double absorb, double reflectShare, double healOnBreak) :
        CreatureEffectCombat(nbTurnsEffect, "SpellCreatureDefense"),
        mAbsorb(absorb),
        mReflectShare(reflectShare),
        mHealOnBreak(healOnBreak)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectShield() :
        CreatureEffectCombat(),
        mAbsorb(0.0),
        mReflectShare(0.0),
        mHealOnBreak(0.0)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectShield()
    {}

    //! \brief The name under which the effect is registered and saved ("Shield").
    virtual const std::string& getEffectName() const override;

    //! \brief Takes as much of the damage as the shield still holds. A shield that is used up ends and heals the
    //! creature by its heal on break.
    //! \param creature The creature that carries the shield.
    //! \param damage The damage that reaches the creature.
    //! \param absorbed Receives the damage the shield took.
    //! \return The damage that goes through the shield.
    double absorbDamage(Creature& creature, double damage, double& absorbed);

    //! \brief The share of the absorbed damage thrown back at the attacker.
    inline double getReflectShare() const
    { return mReflectShare; }

    //! \brief Writes the remaining turns and hit points, the reflect share and the heal on break.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Nothing to do each turn: the shield acts when the creature takes damage.
    virtual void applyEffect(Creature& creature) override
    {}

private:
    //! \brief Hit points of damage the shield still takes.
    double mAbsorb;
    //! \brief Share of the absorbed damage thrown back at the attacker.
    double mReflectShare;
    //! \brief Hit points healed when the shield breaks.
    double mHealOnBreak;
};

#endif // CREATUREEFFECTSHIELD_H
