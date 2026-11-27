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

#ifndef CREATUREEFFECTPROTECTION_H
#define CREATUREEFFECTPROTECTION_H

#include "creatureeffect/CreatureEffectCombat.h"

#include <iosfwd>
#include <string>

//! \brief Short protection given by a skill property: less damage taken (LESS_DAMAGE_TAKEN), faster attacks (HASTE),
//! immunity against stun, knock down and hold (CONTROL_IMMUNE) and the rescue from one deadly blow (SURVIVE_DEADLY).
//! Each part is neutral unless it is set.
class CreatureEffectProtection : public CreatureEffectCombat
{
public:
    //! \brief Creates the protection.
    //! \param nbTurnsEffect Turns the protection lasts.
    //! \param damageTakenFactor Factor on the damage taken (1 = unchanged).
    //! \param attackCooldownFactor Factor on the attack cooldowns (1 = unchanged).
    //! \param controlImmune True when the creature cannot be stunned, knocked down or held.
    //! \param surviveDeadly True when the protection saves the creature from one deadly blow.
    CreatureEffectProtection(double nbTurnsEffect, double damageTakenFactor, double attackCooldownFactor,
            bool controlImmune, bool surviveDeadly) :
        CreatureEffectCombat(nbTurnsEffect, ""),
        mDamageTakenFactor(damageTakenFactor),
        mAttackCooldownFactor(attackCooldownFactor),
        mControlImmune(controlImmune),
        mSurviveDeadly(surviveDeadly)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectProtection() :
        CreatureEffectCombat(),
        mDamageTakenFactor(1.0),
        mAttackCooldownFactor(1.0),
        mControlImmune(false),
        mSurviveDeadly(false)
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectProtection()
    {}

    //! \brief The name under which the effect is registered and saved ("Protection").
    virtual const std::string& getEffectName() const override;

    //! \brief The factor on the damage the creature takes.
    virtual double getDamageTakenFactor() const override
    { return mDamageTakenFactor; }

    //! \brief The factor on the attack cooldowns of the creature.
    virtual double getAttackCooldownFactor() const override
    { return mAttackCooldownFactor; }

    //! \brief True when the creature cannot be stunned, knocked down or held.
    virtual bool isControlImmune() const override
    { return mControlImmune; }

    //! \brief Uses up the rescue from a deadly blow.
    virtual bool consumeSurviveDeadly() override;

    //! \brief Writes the remaining turns and the parts of the protection.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads what exportToStream wrote.
    virtual bool importFromStream(std::istream& is) override;

protected:
    //! \brief Nothing to do each turn: the parts are read where they act.
    virtual void applyEffect(Creature& creature) override
    {}

private:
    //! \brief Factor on the damage the creature takes.
    double mDamageTakenFactor;
    //! \brief Factor on the attack cooldowns of the creature.
    double mAttackCooldownFactor;
    //! \brief True when the creature cannot be stunned, knocked down or held.
    bool mControlImmune;
    //! \brief True while the rescue from a deadly blow is not used up.
    bool mSurviveDeadly;
};

#endif // CREATUREEFFECTPROTECTION_H
