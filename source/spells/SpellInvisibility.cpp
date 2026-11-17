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

#include "spells/SpellInvisibility.h"

#include "creatureeffect/CreatureEffectSpellInvisible.h"
#include "entities/Creature.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "game/SkillManager.h"
#include "game/SkillType.h"
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

const std::string SpellInvisibilityName = "invisibility";
const std::string SpellInvisibilityNameDisplay = "Invisibility";
const std::string SpellInvisibilityCooldownKey = "InvisibilityCooldown";
const SpellType SpellInvisibility::mSpellType = SpellType::invisibility;

namespace
{
//! \brief Registers the Invisibility spell
class SpellInvisibilityFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellInvisibility::mSpellType; }

    const std::string& getName() const override
    { return SpellInvisibilityName; }

    const std::string& getCooldownKey() const override
    { return SpellInvisibilityCooldownKey; }

    const std::string& getNameReadable() const override
    { return SpellInvisibilityNameDisplay; }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellInvisibility::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellInvisibility::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellInvisibility::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellInvisibility::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellInvisibilityFactory);
}

//! \brief Shows the price, checks the own creature under the hand as far as the client knows it and sends the cast.
void SpellInvisibility::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("InvisibilityPrice");
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

    Creature* closestCreature = tileSelected->getClosestCreature(SelectionEntityWanted::creatureAliveOwned);
    if(closestCreature == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Select one of your living creatures.");
        return;
    }

    if(closestCreature->isKo())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "The creature is knocked out.");
        return;
    }

    if(closestCreature->isInContainment())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "The creature is a prisoner.");
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Not enough mana. " +
            formatCastSpell(SpellType::invisibility, price));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::invisibility, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::invisibility);
    clientNotification->mPacket << closestCreature->getName();
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief A living own creature anywhere on the map that is not knocked out and not held in a prison or torture chamber.
bool SpellInvisibility::isValidTarget(const Creature& creature, const Seat* caster)
{
    if(!creature.isAlive() || (creature.getSeat() != caster))
        return false;

    return !creature.isKo() && !creature.isInContainment();
}

//! \brief Casts the spell: the creature is invisible for InvisibilityTurns, lengthened by the research.
bool SpellInvisibility::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
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
        OD_LOG_WRN("Creature=" + creatureName + " is no valid target of the invisibility");
        return false;
    }

    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("InvisibilityPrice");
    if(!player->getSeat()->takeMana(price))
        return false;

    double turns = SkillManager::getResearchValue(player->getSeat(), SkillType::spellInvisibility,
        ConfigManager::getSingleton().getSpellConfigDouble("InvisibilityTurns"), ResearchEffect::Duration);
    creature->addCreatureEffect(new CreatureEffectSpellInvisible(turns));
    // The sound is heard where the creature stands; the spell has no cast look of its own (the body turns half
    // transparent for its keeper and his allies)
    Tile* pos = creature->getPositionTile();
    if(pos != nullptr)
        fireSpellEffect(*pos, "", "Dark", gameMap, player->getSeat());

    return true;
}

Spell* SpellInvisibility::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellInvisibility cannot be read from stream");
    return nullptr;
}

Spell* SpellInvisibility::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellInvisibility cannot be read from packet");
    return nullptr;
}
