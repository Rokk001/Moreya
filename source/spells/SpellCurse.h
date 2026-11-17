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

#ifndef SPELLCURSE_H
#define SPELLCURSE_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

class Creature;
class GameMap;
class InputCommand;
class InputManager;
class Seat;

//! \brief The Curse spell: lowers the mood of one living enemy creature the caster sees, anywhere on the map (not in the
//! caster's prison, a creature type with a mood): CurseMoodJump at once and CurseMoodFall spread over CurseTurns as the
//! timed mood effect "Curse". Several curses on one creature stack like every mood effect. The research scales both
//! mood amounts (MoodLoss).
class SpellCurse : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the enemy creature under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the target and curses it.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief Server side: true if the creature is a valid target of a curse cast by the seat.
    static bool isValidTarget(const Creature& creature, const Seat* caster);

    //! \brief The name of the mood effect of the curse ("Curse"), as the Dungeonbook shows it.
    static const std::string MOOD_EFFECT_NAME;

    //! \brief The curse is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief The curse is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLCURSE_H
