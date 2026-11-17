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

#ifndef SPELLPLAGUE_H
#define SPELLPLAGUE_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

class Creature;
class GameMap;
class InputCommand;
class InputManager;
class Seat;

//! \brief The Plague spell: makes one living enemy creature the caster sees, anywhere on the map, sick. A sick creature
//! loses PlagueDamagePerTurn HP every turn (the research multiplies it, Damage) until an infirmary cot cures it or it
//! dies, and infects the creatures around it (Creature::upkeepPlague). Workers and the champion never get sick.
class SpellPlague : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the enemy creature under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the target and makes it sick.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief Server side: true if the creature is a valid target of a plague cast by the seat.
    static bool isValidTarget(const Creature& creature, const Seat* caster);

    //! \brief The plague is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief The plague is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLPLAGUE_H
