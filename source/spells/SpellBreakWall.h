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

#ifndef SPELLBREAKWALL_H
#define SPELLBREAKWALL_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

class GameMap;
class InputCommand;
class InputManager;
class Seat;
class Tile;

//! \brief The Break Wall spell: turns one full wall tile claimed by a non-allied keeper that the caster sees back into
//! earth (unclaimed and diggable again), as Tremor does in its radius. Gold, gem, rock, lava and water are no target.
//! The research lowers the price (Price).
class SpellBreakWall : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the wall under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the wall and unclaims it.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief True if the tile is a full earth wall claimed by a seat not allied to the caster (both sides). The server
    //! also checks that the caster sees it.
    static bool isValidWall(Tile& tile, const Seat* caster);

    //! \brief The price the seat pays now, after its research.
    static int32_t getPrice(const Seat* seat);

    //! \brief Break Wall is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief Break Wall is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLBREAKWALL_H
