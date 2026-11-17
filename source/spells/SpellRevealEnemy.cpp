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

#include "spells/SpellRevealEnemy.h"

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

#include <algorithm>
#include <cmath>

const std::string SpellRevealEnemyName = "revealEnemy";
const std::string SpellRevealEnemyNameDisplay = "Reveal Enemy";
const std::string SpellRevealEnemyCooldownKey = "RevealEnemyCooldown";
const SpellType SpellRevealEnemy::mSpellType = SpellType::revealEnemy;

namespace
{
//! \brief Registers the Reveal Enemy spell
class SpellRevealEnemyFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellRevealEnemy::mSpellType; }

    const std::string& getName() const override
    { return SpellRevealEnemyName; }

    const std::string& getCooldownKey() const override
    { return SpellRevealEnemyCooldownKey; }

    const std::string& getNameReadable() const override
    { return SpellRevealEnemyNameDisplay; }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellRevealEnemy::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellRevealEnemy::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellRevealEnemy::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellRevealEnemy::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellRevealEnemyFactory);
}

//! \brief A tile claimed by a keeper that is not allied to the caster.
bool SpellRevealEnemy::isValidTile(Tile& tile, const Seat* caster)
{
    if(!tile.isClaimed())
        return false;

    const Seat* owner = tile.getSeat();
    return (owner != nullptr) && !owner->isAlliedSeat(caster);
}

//! \brief Every claimed tile of the seat, in map order.
std::vector<Tile*> SpellRevealEnemy::getClaimedTiles(GameMap* gameMap, const Seat* owner)
{
    std::vector<Tile*> tiles;
    for(int xx = 0; xx < gameMap->getMapSizeX(); ++xx)
    {
        for(int yy = 0; yy < gameMap->getMapSizeY(); ++yy)
        {
            Tile* tile = gameMap->getTile(xx, yy);
            if((tile != nullptr) && tile->isClaimed() && (tile->getSeat() == owner))
                tiles.push_back(tile);
        }
    }
    return tiles;
}

//! \brief Shows the price, checks the tile under the hand and sends the cast.
void SpellRevealEnemy::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("RevealEnemyPrice");
    int32_t playerMana = static_cast<int32_t>(player->getSeat()->getMana());
    Tile* tile = gameMap->getTile(inputManager.mXPos, inputManager.mYPos);
    if(tile == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Point at a tile inside the map.");
        return;
    }

    if(inputManager.mCommandState != InputCommandState::validated)
    {
        std::vector<Tile*> tiles;
        tiles.push_back(tile);
        inputCommand.selectTiles(tiles);
    }

    if(!tile->getLocalPlayerHasVision() || !isValidTile(*tile, player->getSeat()))
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Select a tile claimed by an enemy keeper that you can see.");
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, "Not enough mana. " +
            formatCastSpell(SpellType::revealEnemy, price));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::revealEnemy, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::revealEnemy);
    gameMap->tileToPacket(clientNotification->mPacket, tile);
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief Casts the spell: every tile the keeper of the clicked tile has claimed is shown to the caster for
//! RevealEnemyTurns, lengthened by the research.
bool SpellRevealEnemy::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
{
    Tile* tile = gameMap->tileFromPacket(packet);
    if(tile == nullptr)
        return false;

    // That can happen if the tile changed since the client sent the cast
    if(!isValidTile(*tile, player->getSeat()) || !isTileSeenBy(*tile, player->getSeat()))
    {
        OD_LOG_WRN("Tile=" + Tile::displayAsString(tile) + " is no valid target of Reveal Enemy");
        return false;
    }

    int32_t price = ConfigManager::getSingleton().getSpellConfigInt32("RevealEnemyPrice");
    if(!player->getSeat()->takeMana(price))
        return false;

    const double turns = SkillManager::getResearchValue(player->getSeat(), SkillType::spellRevealEnemy,
        ConfigManager::getSingleton().getSpellConfigDouble("RevealEnemyTurns"), ResearchEffect::Duration);
    const uint32_t revealTurns = static_cast<uint32_t>(std::max(1L, std::lround(turns)));
    std::vector<Tile*> tiles = getClaimedTiles(gameMap, tile->getSeat());
    player->getSeat()->revealTiles(tiles, revealTurns);
    fireSpellEffect(*tile, "", "EyeEvilCast", gameMap, player->getSeat());

    return true;
}

Spell* SpellRevealEnemy::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellRevealEnemy cannot be read from stream");
    return nullptr;
}

Spell* SpellRevealEnemy::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellRevealEnemy cannot be read from packet");
    return nullptr;
}
