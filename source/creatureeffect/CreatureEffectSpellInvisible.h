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

#ifndef CREATUREEFFECTSPELLINVISIBLE_H
#define CREATUREEFFECTSPELLINVISIBLE_H

#include "creatureeffect/CreatureEffect.h"

#include <string>

//! \brief Marks a creature made invisible by the Invisibility spell. While the effect lasts, its enemies do not see
//! the creature and their creatures, aiming traps and spells cannot target it (see Creature::isSpellInvisible). The
//! effect ends when its time runs out or when the creature starts an attack on an enemy
//! (Creature::endSpellInvisibility). It is saved with its time left like every creature effect.
class CreatureEffectSpellInvisible : public CreatureEffect
{
public:
    //! \brief Creates the effect for the given number of turns.
    CreatureEffectSpellInvisible(double nbTurnsEffect) :
        CreatureEffect(nbTurnsEffect, "")
    {}

    //! \brief Creates an empty effect that is filled by importFromStream.
    CreatureEffectSpellInvisible() :
        CreatureEffect()
    {}

    //! \brief Destroys the effect.
    virtual ~CreatureEffectSpellInvisible()
    {}

    //! \brief Returns the name under which the effect is registered and saved ("SpellInvisible").
    virtual const std::string& getEffectName() const override;

    //! \brief The registered name of the effect, for the lookups of Creature.
    static const std::string EFFECT_NAME;

protected:
    //! \brief Called every turn while the effect lasts; the invisible state is deduced from the effect itself.
    virtual void applyEffect(Creature& creature) override;
};

#endif // CREATUREEFFECTSPELLINVISIBLE_H
