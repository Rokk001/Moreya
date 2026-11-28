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

#ifndef CREATUREEFFECTMARK_H
#define CREATUREEFFECTMARK_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <cstdint>
#include <iosfwd>
#include <string>

//! \brief Mark of a supporter (and the SHATTER property of a freeze): the creature takes its damage times the factor
//! while the effect runs. With a focus seat the creatures of that seat and its allies prefer it as their target.
class CreatureEffectMark : public CreatureEffectCombat
{
public:
    //! \brief Creates the mark.
    //! \param nbTurnsEffect Turns the mark lasts.
    //! \param damageTakenFactor Factor on the damage the marked creature takes.
    //! \param focusSeatId Seat whose creatures prefer the marked creature as target, -1 for none.
    CreatureEffectMark(double nbTurnsEffect, double damageTakenFactor, int32_t focusSeatId) :
        CreatureEffectCombat(nbTurnsEffect, ""),
        mDamageTakenFactor(damageTakenFactor),
        mFocusSeatId(focusSeatId)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectMark() :
        CreatureEffectCombat(),
        mDamageTakenFactor(1.0),
        mFocusSeatId(-1)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectMark()
    {}

    //! \brief The name under which the effect is registered and saved ("Mark").
    virtual const std::string& getEffectName() const override;

    //! \brief The factor on the damage the marked creature takes.
    virtual double getDamageTakenFactor() const override
    { return mDamageTakenFactor; }

    //! \brief The seat whose creatures prefer the marked creature, -1 for none.
    virtual int32_t getFocusSeatId() const override
    { return mFocusSeatId; }

    //! \brief Writes the remaining turns, the factor and the focus seat.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Nothing to do each turn: the factor is read when the creature takes damage.
    virtual void applyEffect(Creature& creature) override
    {}

private:
    //! \brief Factor on the damage the marked creature takes.
    double mDamageTakenFactor;
    //! \brief Seat whose creatures prefer the marked creature, -1 for none.
    int32_t mFocusSeatId;
};

#endif // CREATUREEFFECTMARK_H
