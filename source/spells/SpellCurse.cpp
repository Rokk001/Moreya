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

#include "spells/SpellCurse.h"

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
#include "utils/Translation.h"

const std::string SpellCurseName = "curse";
const std::string SpellCurseNameKey = "spell.curse.name";
const std::string SpellCurseCooldownKey = "CurseCooldown";
const SpellType SpellCurse::mSpellType = SpellType::curse;
const std::string SpellCurse::MOOD_EFFECT_NAME = "Curse";

namespace
{
//! \brief Registers the Curse spell
class SpellCurseFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellCurse::mSpellType; }

    const std::string& getName() const override
    { return SpellCurseName; }

    const std::string& getCooldownKey() const override
    { return SpellCurseCooldownKey; }

    //! \brief The name shown to the player, in the chosen language.
    std::string getNameReadable() const override
    { return Translation::tr(SpellCurseNameKey); }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellCurse::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellCurse::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellCurse::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellCurse::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellCurseFactory);
}

//! \brief Shows the price, checks the enemy creature under the hand as far as the client knows it and sends the cast.
void SpellCurse::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("CursePrice");
    int32_t playerMana = static_cast<int32_t>(player->getSeat()->getMana());
    Tile* tileSelected = gameMap->getTile(inputManager.mXPos, inputManager.mYPos);
    if(tileSelected == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.point_at_tile"));
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
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.select_visible_enemy"));
        return;
    }

    if(closestCreature->getDefinition()->getCreatureMoods().empty())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.no_mood_to_curse"));
        return;
    }

    if(closestCreature->getSeatPrison() == player->getSeat())
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.creature_is_your_prisoner"));
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.not_enough_mana", {{"text", formatCastSpell(SpellType::curse, price)}}));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::curse, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::curse);
    clientNotification->mPacket << closestCreature->getName();
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief A living enemy creature with a mood that the caster sees, not in the caster's prison and not hidden by the
//! Invisibility spell.
bool SpellCurse::isValidTarget(const Creature& creature, const Seat* caster)
{
    if(!creature.isAlive() || (creature.getSeat() == nullptr) || creature.getSeat()->isAlliedSeat(caster))
        return false;

    if(creature.getDefinition()->getCreatureMoods().empty())
        return false;

    if(creature.getSeatPrison() == caster)
        return false;

    if(creature.isSpellInvisible())
        return false;

    Tile* pos = creature.getPositionTile();
    return (pos != nullptr) && isTileSeenBy(*pos, caster);
}

//! \brief Casts the spell: the jump at once and the timed mood effect "Curse"; the amounts follow the curse research.
bool SpellCurse::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
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
        OD_LOG_WRN("Creature=" + creatureName + " is no valid target of the curse");
        return false;
    }

    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("CursePrice");
    if(!player->getSeat()->takeMana(price))
        return false;

    const ConfigManager& config = ConfigManager::getSingleton();
    const double factor = SkillManager::getResearchValue(player->getSeat(), SkillType::spellCurse, 1.0,
        ResearchEffect::MoodLoss);
    creature->applyMoodEvent(config.getSpellConfigDouble("CurseMoodJump") * factor, false);
    creature->addMoodEffect(MOOD_EFFECT_NAME, config.getSpellConfigDouble("CurseMoodFall") * factor,
        config.getSpellConfigDouble("CurseTurns"));
    creature->requestRefresh();
    fireSpellEffect(*creature->getPositionTile(), "Weak", "Curse", gameMap, player->getSeat());

    return true;
}

Spell* SpellCurse::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellCurse cannot be read from stream");
    return nullptr;
}

Spell* SpellCurse::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellCurse cannot be read from packet");
    return nullptr;
}
