/*
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

#ifndef SPELLINVISIBILITY_H
#define SPELLINVISIBILITY_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

class Creature;
class GameMap;
class InputCommand;
class InputManager;
class Seat;

//! \brief The Invisibility spell: makes one living own creature anywhere on the map (not knocked out, not in a prison)
//! invisible to its enemies until it attacks or uses a skill against an enemy, at most InvisibilityTurns (the research
//! lengthens it, Duration). Enemy creatures, enemy aiming traps and enemy keepers' spells cannot target it, tile traps
//! still hit it; its keeper and his allies see it half transparent (CreatureEffectSpellInvisible).
class SpellInvisibility : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the own creature under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the target and hides it.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief Server side: true if the creature is a valid target of an invisibility cast by the seat.
    static bool isValidTarget(const Creature& creature, const Seat* caster);

    //! \brief The invisibility is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief The invisibility is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLINVISIBILITY_H
