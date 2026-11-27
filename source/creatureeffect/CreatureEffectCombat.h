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

#ifndef CREATUREEFFECTCOMBAT_H
#define CREATUREEFFECTCOMBAT_H

#include "creatureeffect/CreatureEffect.h"

#include <cstdint>
#include <string>

//! \brief Base of the effects of the role skills that change how a creature fights: the creature asks every running
//! effect of this kind for its factors and states (Creature::getSkillDamageTakenFactor and the other getters). The
//! effect keeps its own state, so nothing has to be undone when it ends. Every getter returns the neutral value
//! unless the effect overrides it.
class CreatureEffectCombat : public CreatureEffect
{
public:
    //! \brief Destroys the effect.
    virtual ~CreatureEffectCombat()
    {}

    //! \brief Factor on the damage the creature takes (1 = unchanged).
    virtual double getDamageTakenFactor() const
    { return 1.0; }

    //! \brief Factor on the damage the creature deals (1 = unchanged).
    virtual double getDamageDealtFactor() const
    { return 1.0; }

    //! \brief Factor on every heal the creature receives (1 = unchanged).
    virtual double getHealReceivedFactor() const
    { return 1.0; }

    //! \brief Factor on the cooldown of the attacks of the creature (below 1 = attacks faster).
    virtual double getAttackCooldownFactor() const
    { return 1.0; }

    //! \brief True while the creature is held in place (it can still attack what it reaches).
    virtual bool isRooted() const
    { return false; }

    //! \brief True while the creature cannot be stunned, knocked down or held.
    virtual bool isControlImmune() const
    { return false; }

    //! \brief The name of the creature the creature must attack (taunt), empty if none.
    virtual const std::string& getTaunterName() const
    {
        static const std::string NONE;
        return NONE;
    }

    //! \brief The seat id of the creatures that prefer the creature as target (mark), -1 if none.
    virtual int32_t getFocusSeatId() const
    { return -1; }

    //! \brief Uses up the protection against one deadly blow; true when the effect had one.
    virtual bool consumeSurviveDeadly()
    { return false; }

protected:
    //! \brief Creates the effect for the given turns and particle script.
    CreatureEffectCombat(double nbTurnsEffect, const std::string& particleEffectScript) :
        CreatureEffect(nbTurnsEffect, particleEffectScript)
    {}

    //! \brief Creates an empty effect to be filled from a stream.
    CreatureEffectCombat() :
        CreatureEffect()
    {}
};

#endif // CREATUREEFFECTCOMBAT_H
