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

#ifndef CREATUREEFFECTTAUNT_H
#define CREATUREEFFECTTAUNT_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <iosfwd>
#include <string>

//! \brief Taunt of a tank: while it runs the creature attacks the tank that taunted it (when it can reach it) and
//! deals its damage times the damage factor (1 unless the taunt has the LESS_DAMAGE_DEALT property).
class CreatureEffectTaunt : public CreatureEffectCombat
{
public:
    //! \brief Creates the taunt of the named tank.
    //! \param nbTurnsEffect Turns the taunt lasts.
    //! \param taunterName The name of the tank.
    //! \param damageDealtFactor Factor on the damage of the taunted creature.
    CreatureEffectTaunt(double nbTurnsEffect, const std::string& taunterName, double damageDealtFactor) :
        CreatureEffectCombat(nbTurnsEffect, ""),
        mTaunterName(taunterName),
        mDamageDealtFactor(damageDealtFactor)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectTaunt() :
        CreatureEffectCombat(),
        mDamageDealtFactor(1.0)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectTaunt()
    {}

    //! \brief The name under which the effect is registered and saved ("Taunt").
    virtual const std::string& getEffectName() const override;

    //! \brief The name of the tank the creature must attack.
    virtual const std::string& getTaunterName() const override
    { return mTaunterName; }

    //! \brief The factor on the damage of the taunted creature.
    virtual double getDamageDealtFactor() const override
    { return mDamageDealtFactor; }

    //! \brief Writes the remaining turns, the tank and the damage factor.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Nothing to do each turn: the taunt is read by the target choice of the creature.
    virtual void applyEffect(Creature& creature) override
    {}

private:
    //! \brief The tank that taunted the creature.
    std::string mTaunterName;
    //! \brief Factor on the damage the taunted creature deals.
    double mDamageDealtFactor;
};

#endif // CREATUREEFFECTTAUNT_H
