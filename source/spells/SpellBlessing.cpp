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

#include "spells/SpellBlessing.h"

#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
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

const std::string SpellBlessingName = "blessing";
const std::string SpellBlessingNameDisplay = "Blessing";
const std::string SpellBlessingCooldownKey = "BlessingCooldown";
const SpellType SpellBlessing::mSpellType = SpellType::blessing;
const std::string SpellBlessing::MOOD_EFFECT_NAME = "Blessing";

namespace
{
//! \brief Registers the Blessing spell
class SpellBlessingFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellBlessing::mSpellType; }

    const std::string& getName() const override
    { return SpellBlessingName; }

    const std::string& getCooldownKey() const override
    { return SpellBlessingCooldownKey; }

    const std::string& getNameReadable() const override
    { return SpellBlessingNameDisplay; }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellBlessing::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellBlessing::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellBlessing::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellBlessing::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellBlessingFactory);
}

//! \brief Shows the price, checks the own creature under the hand as far as the client knows it and sends the cast.
void SpellBlessing::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("BlessingPrice");
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

    if(closestCreature->getDefinition()->getCreatureMoods().empty())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "This creature has no mood to bless.");
        return;
    }

    if(closestCreature->isInContainment())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "The creature is a prisoner.");
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Not enough mana. " + formatCastSpell(SpellType::blessing, price));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::blessing, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::blessing);
    clientNotification->mPacket << closestCreature->getName();
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief A living own creature with a mood, anywhere on the map, that is not held in a prison or torture chamber.
bool SpellBlessing::isValidTarget(const Creature& creature, const Seat* caster)
{
    if(!creature.isAlive() || (creature.getSeat() != caster))
        return false;

    if(creature.getDefinition()->getCreatureMoods().empty())
        return false;

    return !creature.isInContainment();
}

//! \brief Casts the spell: the jump at once and the timed mood effect "Blessing"; the amounts follow the research.
bool SpellBlessing::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
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
        OD_LOG_WRN("Creature=" + creatureName + " is no valid target of the blessing");
        return false;
    }

    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("BlessingPrice");
    if(!player->getSeat()->takeMana(price))
        return false;

    // The stored mood never rises above the maximum (Creature::changeStoredMood)
    const ConfigManager& config = ConfigManager::getSingleton();
    const double factor = SkillManager::getResearchValue(player->getSeat(), SkillType::spellBlessing, 1.0,
        ResearchEffect::MoodGain);
    creature->applyMoodEvent(config.getSpellConfigDouble("BlessingMoodJump") * factor, false);
    creature->addMoodEffect(MOOD_EFFECT_NAME, config.getSpellConfigDouble("BlessingMoodRise") * factor,
        config.getSpellConfigDouble("BlessingTurns"));
    creature->requestRefresh();
    Tile* pos = creature->getPositionTile();
    if(pos != nullptr)
        fireSpellEffect(*pos, "Strength", "Boost", gameMap, player->getSeat());

    return true;
}

Spell* SpellBlessing::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellBlessing cannot be read from stream");
    return nullptr;
}

Spell* SpellBlessing::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellBlessing cannot be read from packet");
    return nullptr;
}
