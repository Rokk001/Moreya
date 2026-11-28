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

#include "spells/SpellBreakWall.h"

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

#include <cmath>

const std::string SpellBreakWallName = "breakWall";
const std::string SpellBreakWallNameKey = "spell.breakwall.name";
const std::string SpellBreakWallCooldownKey = "BreakWallCooldown";
const SpellType SpellBreakWall::mSpellType = SpellType::breakWall;

namespace
{
//! \brief Registers the Break Wall spell
class SpellBreakWallFactory : public SpellFactory
{
    SpellType getSpellType() const override
    { return SpellBreakWall::mSpellType; }

    const std::string& getName() const override
    { return SpellBreakWallName; }

    const std::string& getCooldownKey() const override
    { return SpellBreakWallCooldownKey; }

    //! \brief The name shown to the player, in the chosen language.
    std::string getNameReadable() const override
    { return Translation::tr(SpellBreakWallNameKey); }

    virtual void checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand) const override
    { SpellBreakWall::checkSpellCast(gameMap, inputManager, inputCommand); }

    virtual bool castSpell(GameMap* gameMap, Player* player, ODPacket& packet) const override
    { return SpellBreakWall::castSpell(gameMap, player, packet); }

    Spell* getSpellFromStream(GameMap* gameMap, std::istream &is) const override
    { return SpellBreakWall::getSpellFromStream(gameMap, is); }

    Spell* getSpellFromPacket(GameMap* gameMap, ODPacket &is) const override
    { return SpellBreakWall::getSpellFromPacket(gameMap, is); }
};

// Register the factory
static SpellRegister reg(new SpellBreakWallFactory);
}

//! \brief BreakWallPrice after the Break Wall research of the seat, rounded to whole mana.
int32_t SpellBreakWall::getPrice(const Seat* seat)
{
    return static_cast<int32_t>(std::lround(SkillManager::getResearchValue(seat, SkillType::spellBreakWall,
        ConfigManager::getSingleton().getSpellConfigDouble("BreakWallPrice"), ResearchEffect::Price)));
}

//! \brief A full earth wall (no gold, gem, rock, lava or water) claimed by a seat that is not allied to the caster. The
//! client knows the wall by its look (a claimed wall), the server by its type, fullness and claim.
bool SpellBreakWall::isValidWall(Tile& tile, const Seat* caster)
{
    if(!tile.getIsOnServerMap())
    {
        if(tile.getTileVisual() != TileVisual::claimedFull)
            return false;
    }
    else if((tile.getType() != TileType::dirt) || !tile.isFullTile() || !tile.isClaimed())
        return false;

    const Seat* owner = tile.getSeat();
    return (owner != nullptr) && !owner->isAlliedSeat(caster);
}

//! \brief Shows the researched price, checks the wall under the hand and sends the cast.
void SpellBreakWall::checkSpellCast(GameMap* gameMap, const InputManager& inputManager, InputCommand& inputCommand)
{
    Player* player = gameMap->getLocalPlayer();
    int32_t price = getPrice(player->getSeat());
    int32_t playerMana = static_cast<int32_t>(player->getSeat()->getMana());
    Tile* tile = gameMap->getTile(inputManager.mXPos, inputManager.mYPos);
    if(tile == nullptr)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.point_at_tile"));
        return;
    }

    if(inputManager.mCommandState != InputCommandState::validated)
    {
        std::vector<Tile*> tiles;
        tiles.push_back(tile);
        inputCommand.selectTiles(tiles);
    }

    if(!tile->getLocalPlayerHasVision() || !isValidWall(*tile, player->getSeat()))
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.select_enemy_wall"));
        return;
    }

    if(playerMana < price)
    {
        inputCommand.displayText(Ogre::ColourValue::Red, Translation::tr("spell.hint.not_enough_mana", {{"text", formatCastSpell(SpellType::breakWall, price)}}));
        return;
    }

    inputCommand.displayText(Ogre::ColourValue::White, formatCastSpell(SpellType::breakWall, price));

    if(inputManager.mCommandState != InputCommandState::validated)
        return;

    inputCommand.unselectAllTiles();

    ClientNotification *clientNotification = SpellManager::createSpellClientNotification(SpellType::breakWall);
    gameMap->tileToPacket(clientNotification->mPacket, tile);
    ODClient::getSingleton().queueClientNotification(clientNotification);
}

//! \brief Casts the spell: the wall turns back into earth that can be dug, like the walls in the radius of Tremor.
bool SpellBreakWall::castSpell(GameMap* gameMap, Player* player, ODPacket& packet)
{
    Tile* tile = gameMap->tileFromPacket(packet);
    if(tile == nullptr)
        return false;

    // That can happen if the wall changed since the client sent the cast
    if(!isValidWall(*tile, player->getSeat()) || !isTileSeenBy(*tile, player->getSeat()))
    {
        OD_LOG_WRN("Tile=" + Tile::displayAsString(tile) + " is no valid target of Break Wall");
        return false;
    }

    if(!player->getSeat()->takeMana(getPrice(player->getSeat())))
        return false;

    // We notify the previous owner that the tile is lost, like when it is claimed by an enemy
    tile->getSeat()->notifyTileClaimedByEnemy(tile);
    tile->unclaimTile();
    fireSpellEffect(*tile, "Tremor", "TremorImpact", gameMap, player->getSeat());

    return true;
}

Spell* SpellBreakWall::getSpellFromStream(GameMap* gameMap, std::istream &is)
{
    OD_LOG_ERR("SpellBreakWall cannot be read from stream");
    return nullptr;
}

Spell* SpellBreakWall::getSpellFromPacket(GameMap* gameMap, ODPacket &is)
{
    OD_LOG_ERR("SpellBreakWall cannot be read from packet");
    return nullptr;
}
