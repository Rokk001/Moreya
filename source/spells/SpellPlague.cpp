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

#include "spells/SpellPlague.h"

#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "modes/InputCommand.h"
#include "modes/InputManager.h"
#include "network/ClientNotification.h"
#include "network/ODClient.h"
#include "spells/SpellManager.h"
#include "spells/SpellType.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"

const std::string SpellPlagueName = "plague";
const std::string SpellPlagueNameDisplay = "Plague";
const std::string SpellPlagueCooldownKey = "PlagueCooldown";
const SpellType SpellPlague::mSpellType = SpellType::plague;

namespace
{
//! \brief Registers the Plague spell
class SpellPlagueFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellPlague::mSpellType; }

    const std::string& getName() const override
    { return SpellPlagueName; }

    const std::string& getCooldownKey() const override
    { return SpellPlagueCooldownKey; }

    const std::string& getNameReadable() const override
    { return SpellPlagueNameDisplay; }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellPlague::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellPlague::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellPlague::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellPlague::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellPlagueFactory);
}

//! \brief Shows the price, checks the enemy creature under the hand as far as the client knows it and sends the cast.
void SpellPlague::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("PlaguePrice");
    int32_t playerMana = static_cast<int32_t>(player->getSeat()->getMana());
    Tile* tileSelected = gameMap->getTile(inputManager.mXPos, inputManager.mYPos);
    if(tileSelected == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Point at a tile inside the map.");
        return;
    }

    if(inputManager.mCommandState != InputCommandState::validated)
    {
        inputCommand.selectSquaredTiles(inputManager.mXPos, inputManager.mYPos, inputManager.mXPos,
            inputManager.mYPos);
    }

    // The client only knows the creatures the keeper sees
    Creature* closestCreature = tileSelected->getClosestCreature(SelectionEntityWanted::creatureAliveEnemy);
    if(closestCreature == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Select a living enemy creature you can see.");
        return;
    }

    if(closestCreature->getDefinition()->isWorker() || closestCreature->getDefinition()->isChampion())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Workers and champions never get sick.");
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Not enough mana. " + formatCastSpell(SpellType::plague, price));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::plague, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::plague);
    clientNotification->mPacket << closestCreature->getName();
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief A living enemy creature the caster sees that can get sick (no worker, no champion), is not sick yet and is not
//! hidden by the Invisibility spell.
bool SpellPlague::isValidTarget(const Creature& creature, const Seat* caster)
{
    if(!creature.isAlive() || (creature.getSeat() == nullptr) || creature.getSeat()->isAlliedSeat(caster))
        return false;

    if(!creature.canCatchPlague() || creature.isPlagueSick())
        return false;

    if(creature.isSpellInvisible())
        return false;

    Tile* pos = creature.getPositionTile();
    return (pos != nullptr) && isTileSeenBy(*pos, caster);
}

//! \brief Casts the spell: the creature is sick until an infirmary cot cures it or it dies.
bool SpellPlague::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
{
    std::string creatureName;
    OD_ASSERT_TRUE(packet >> creatureName);

    Creature* creature = gameMap->getCreature(creatureName);
    if(creature == nullptr)
    {
        OD_LOG_ERR("creatureName=" + creatureName);
        return false;
    }

    // That can happen if the creature changed since the client sent the cast
    if(!isValidTarget(*creature, player->getSeat()))
    {
        OD_LOG_WRN("Creature=" + creatureName + " is no valid target of the plague");
        return false;
    }

    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("PlaguePrice");
    if(!player->getSeat()->takeMana(price))
        return false;

    creature->catchPlague(player->getSeat()->getId());
    // The sound of the cast; the sick creature shows its green look from its next turn on
    fireSpellEffect(*creature->getPositionTile(), "", "Curse", gameMap, player->getSeat());

    return true;
}

Spell* SpellPlague::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellPlague cannot be read from stream");
    return nullptr;
}

Spell* SpellPlague::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellPlague cannot be read from packet");
    return nullptr;
}
