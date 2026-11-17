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

#ifndef SPELLBLESSING_H
#define SPELLBLESSING_H

#include "spells/Spell.h"
#include "spells/SpellType.h"

class Creature;
class GameMap;
class InputCommand;
class InputManager;
class Seat;

//! \brief The Blessing spell: raises the mood of one living own creature anywhere on the map (not in a prison, a
//! creature type with a mood): BlessingMoodJump at once and BlessingMoodRise spread over BlessingTurns as the timed
//! mood effect "Blessing". The mood never rises above the maximum. The research scales both mood amounts (MoodGain).
class SpellBlessing : public Spell
{
public:
    //! \brief Client side: shows the price and sends the cast for the own creature under the hand.
    static void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand);
    //! \brief Server side: checks the target and blesses it.
    static bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet);

    //! \brief Server side: true if the creature is a valid target of a blessing cast by the seat.
    static bool isValidTarget(const Creature& creature, const Seat* caster);

    //! \brief The name of the mood effect of the blessing ("Blessing"), as the Dungeonbook shows it.
    static const std::string MOOD_EFFECT_NAME;

    //! \brief The blessing is no lasting entity: it cannot be read from a stream.
    static Spell* getSpellFromStream(GameMap* gameMap, std::istream &is);
    //! \brief The blessing is no lasting entity: it cannot be read from a packet.
    static Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is);

    static const SpellType mSpellType;
};

#endif // SPELLBLESSING_H
