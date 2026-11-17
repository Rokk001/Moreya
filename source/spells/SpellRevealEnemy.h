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

#ifndef SPELLREVEALENEMY_H
#define SPELLREVEALENEMY_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

#include <vector>

class GameMap;
class InputCommand;
class InputManager;
class Seat;
class Tile;

//! \brief The Reveal Enemy spell: the caster clicks a visible tile claimed by an enemy keeper; every tile claimed by that
//! keeper is shown to the caster for RevealEnemyTurns (the research lengthens it, Duration). The running reveal is
//! saved with its tiles and turns left (Seat::revealTiles and the [RevealedTiles] block of the seat).
class SpellRevealEnemy : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the tile under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the tile and reveals the claimed tiles of its keeper.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief True if the tile is claimed by a keeper that is not allied to the caster (both sides). The server also
    //! checks that the caster sees it.
    static bool isValidTile(Tile& tile, const Seat* caster);

    //! \brief Every tile of the map claimed by the given seat (rooms and claimed walls included).
    static std::vector<Tile*> getClaimedTiles(GameMap* gameMap, const Seat* owner);

    //! \brief Reveal Enemy is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief Reveal Enemy is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLREVEALENEMY_H
