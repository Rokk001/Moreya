/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
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

#include "giftboxes/GiftBoxBonus.h"

#include "ODApplication.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/Tile.h"
#include "entities/TreasuryObject.h"
#include "game/Seat.h"
#include "game/SkillType.h"
#include "gamemap/GameMap.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "utils/Random.h"
#include "utils/Translation.h"

#include <cmath>
#include <iostream>

// The amounts, levels and durations of the gift boxes are read from global.cfg (GiftBox...) and spells.cfg (SummonWorkerUpgraded...)

//! \brief Creates a bonus box of the given type and amount with the mystery box mesh
GiftBoxBonus::GiftBoxBonus(GameMap* gameMap, const std::string& baseName, GiftBoxType type, uint32_t amount) :
    GiftBoxEntity(gameMap, baseName, "MysteryBox", type),
    mAmount(amount)
{
    mPrevAnimationState = "Loop";
    mPrevAnimationStateLoop = true;
}

//! \brief Creates an empty bonus box of the given type, filled afterwards when it is loaded from a stream
GiftBoxBonus::GiftBoxBonus(GameMap* gameMap, GiftBoxType type) :
    GiftBoxEntity(gameMap, type),
    mAmount(0)
{
}

//! \brief Returns the name of the bonus of the given type, in the chosen language
std::string GiftBoxBonus::getDisplayName(GiftBoxType type)
{
    switch(type)
    {
        case GiftBoxType::mana:
            return Translation::tr("gift.mana.name");
        case GiftBoxType::gold:
            return Translation::tr("gift.gold.name");
        case GiftBoxType::revealMap:
            return Translation::tr("gift.revealmap.name");
        case GiftBoxType::levelUp:
            return Translation::tr("gift.levelup.name");
        case GiftBoxType::healAll:
            return Translation::tr("gift.healall.name");
        case GiftBoxType::makeSafe:
            return Translation::tr("gift.makesafe.name");
        case GiftBoxType::weakenWalls:
            return Translation::tr("gift.weakenwalls.name");
        case GiftBoxType::stunWorkers:
            return Translation::tr("gift.stunworkers.name");
        case GiftBoxType::receiveWorkers:
            return Translation::tr("gift.receiveworkers.name");
        case GiftBoxType::makeHappy:
            return Translation::tr("gift.makehappy.name");
        case GiftBoxType::makeUnhappy:
            return Translation::tr("gift.makeunhappy.name");
        case GiftBoxType::killCreatures:
            return Translation::tr("gift.killcreatures.name");
        default:
            return Translation::tr("gift.default.name");
    }
}

//! \brief The key giftbox.<type id>.name with the display name as the text for a language without it.
std::string GiftBoxBonus::getDisplayNameReference(GiftBoxType type)
{
    static const char* const TYPE_IDS[] = {"skill", "mana", "gold", "revealmap", "levelup", "healall", "makesafe",
        "weakenwalls", "stunworkers", "receiveworkers", "makehappy", "makeunhappy", "killcreatures", "item"};
    const uint32_t index = static_cast<uint32_t>(type);
    const std::string id = (index < sizeof(TYPE_IDS) / sizeof(TYPE_IDS[0])) ? TYPE_IDS[index] : "special";
    return Translation::makeNameReference("giftbox." + id + ".name", getDisplayName(type));
}

//! \brief Returns a short text saying what the bonus of the given type does, in the chosen language
std::string GiftBoxBonus::getDescription(GiftBoxType type)
{
    switch(type)
    {
        case GiftBoxType::mana:
            return Translation::tr("gift.mana.description");
        case GiftBoxType::gold:
            return Translation::tr("gift.gold.description");
        case GiftBoxType::revealMap:
            return Translation::tr("gift.revealmap.description");
        case GiftBoxType::levelUp:
            return Translation::tr("gift.levelup.description");
        case GiftBoxType::healAll:
            return Translation::tr("gift.healall.description");
        case GiftBoxType::makeSafe:
            return Translation::tr("gift.makesafe.description");
        case GiftBoxType::weakenWalls:
            return Translation::tr("gift.weakenwalls.description");
        case GiftBoxType::stunWorkers:
            return Translation::tr("gift.stunworkers.description");
        case GiftBoxType::receiveWorkers:
            return Translation::tr("gift.receiveworkers.description");
        case GiftBoxType::makeHappy:
            return Translation::tr("gift.makehappy.description");
        case GiftBoxType::makeUnhappy:
            return Translation::tr("gift.makeunhappy.description");
        case GiftBoxType::killCreatures:
            return Translation::tr("gift.killcreatures.description");
        default:
            return "";
    }
}

//! \brief Returns the amount a box of the given type carries by default
uint32_t GiftBoxBonus::getDefaultAmount(GiftBoxType type)
{
    switch(type)
    {
        case GiftBoxType::mana:
            return ConfigManager::getSingleton().getGiftBoxMana();
        case GiftBoxType::gold:
            return ConfigManager::getSingleton().getGiftBoxGold();
        case GiftBoxType::levelUp:
            return ConfigManager::getSingleton().getGiftBoxLevels();
        case GiftBoxType::receiveWorkers:
            return ConfigManager::getSingleton().getGiftBoxWorkers();
        case GiftBoxType::revealMap:
        case GiftBoxType::healAll:
        case GiftBoxType::makeSafe:
        case GiftBoxType::weakenWalls:
        case GiftBoxType::stunWorkers:
        case GiftBoxType::makeHappy:
        case GiftBoxType::makeUnhappy:
        case GiftBoxType::killCreatures:
            return 0;
        default:
            OD_LOG_ERR("Unexpected GiftBoxType=" + Helper::toString(static_cast<uint32_t>(type)));
            return 0;
    }
}

//! \brief Writes the box and its amount to the stream
void GiftBoxBonus::exportToStream(std::ostream& os) const
{
    GiftBoxEntity::exportToStream(os);
    os << mAmount << "\t";
}

//! \brief Reads the box and its amount from the stream. Returns false if the data is incomplete
bool GiftBoxBonus::importFromStream(std::istream& is)
{
    if(!GiftBoxEntity::importFromStream(is))
        return false;
    if(!(is >> mAmount))
        return false;

    return true;
}

//! \brief Server side. Gives the bonus of this box to the seat that delivered it
void GiftBoxBonus::applyEffect()
{
    Seat* seat = getSeat();
    if(seat == nullptr)
    {
        OD_LOG_ERR("null Seat for giftbox=" + getName() + " pos=" + Helper::toString(getPosition()));
        return;
    }

    applyBonus(getGameMap(), seat, getGiftBoxType(), mAmount, getPositionTile());
}

//! \brief Server side. Applies the bonus of the given type and amount to the seat. Gold the
//! treasuries cannot hold is left on the given tile, workers appear on it
void GiftBoxBonus::applyBonus(GameMap* gameMap, Seat* seat, GiftBoxType type, uint32_t amount, Tile* positionTile)
{
    switch(type)
    {
        case GiftBoxType::mana:
        {
            gameMap->addManaToSeat(static_cast<int>(amount), seat->getId());
            break;
        }
        case GiftBoxType::gold:
        {
            // What the treasuries cannot hold is left on the ground where the box was
            double notStored = gameMap->addGoldToSeat(static_cast<int>(amount), seat->getId());
            Tile* tile = positionTile;
            if((notStored > 0) && (tile != nullptr))
            {
                TreasuryObject* obj = new TreasuryObject(gameMap, notStored);
                obj->addToGameMap();
                Ogre::Vector3 spawnPosition(static_cast<Ogre::Real>(tile->getX()),
                                            static_cast<Ogre::Real>(tile->getY()), 0.0f);
                obj->createMesh();
                obj->setPosition(spawnPosition);
            }
            break;
        }
        case GiftBoxType::revealMap:
        {
            seat->revealMapPermanently();
            break;
        }
        case GiftBoxType::levelUp:
        {
            std::vector<Creature*> creatures = gameMap->getCreaturesBySeat(seat);
            for(Creature* creature : creatures)
            {
                if(!creature->isAlive())
                    continue;

                creature->setLevel(creature->getLevel() + amount);
            }
            break;
        }
        case GiftBoxType::healAll:
        {
            std::vector<Creature*> creatures = gameMap->getCreaturesBySeat(seat);
            for(Creature* creature : creatures)
            {
                if(!creature->isAlive())
                    continue;

                creature->heal(creature->getMaxHp());
            }
            break;
        }
        case GiftBoxType::makeSafe:
        {
            // Every wall next to claimed ground of the seat that is not claimed yet becomes a reinforced wall
            for(int x = 0; x < gameMap->getMapSizeX(); ++x)
            {
                for(int y = 0; y < gameMap->getMapSizeY(); ++y)
                {
                    Tile* tile = gameMap->getTile(x, y);
                    if((tile == nullptr) || tile->isClaimed() || !tile->isWallClaimable(seat))
                        continue;

                    tile->claimTile(seat);
                }
            }
            break;
        }
        case GiftBoxType::weakenWalls:
        {
            // Reinforced enemy walls turn back to earth. Rooms, traps, doors and bridges are not affected
            for(int x = 0; x < gameMap->getMapSizeX(); ++x)
            {
                for(int y = 0; y < gameMap->getMapSizeY(); ++y)
                {
                    Tile* tile = gameMap->getTile(x, y);
                    if((tile == nullptr) || !tile->isFullTile() || !tile->isClaimed())
                        continue;

                    if(tile->getSeat()->isAlliedSeat(seat))
                        continue;

                    if((tile->getCoveringBuilding() != nullptr) || tile->getHasBridge())
                        continue;

                    tile->getSeat()->notifyTileClaimedByEnemy(tile);
                    tile->unclaimTile();
                }
            }
            break;
        }
        case GiftBoxType::stunWorkers:
        {
            int32_t nbTurns = static_cast<int32_t>(std::ceil(ConfigManager::getSingleton().getGiftBoxStunSeconds() * ODApplication::turnsPerSecond));
            std::vector<Creature*> creatures = gameMap->getCreatures();
            for(Creature* creature : creatures)
            {
                if(!creature->isAlive() || !creature->getDefinition()->isWorker())
                    continue;

                if(creature->getSeat()->isAlliedSeat(seat))
                    continue;

                creature->stun(nbTurns);
            }
            break;
        }
        case GiftBoxType::receiveWorkers:
        {
            const CreatureDefinition* workerClass = seat->getWorkerClassToSpawn();
            Tile* tile = positionTile;
            if((workerClass == nullptr) || (tile == nullptr))
            {
                OD_LOG_ERR("No worker class or tile for special type=" + Helper::toString(static_cast<uint32_t>(type)));
                break;
            }

            bool upgraded = (seat->getSkillLevel(SkillType::spellSummonWorker) >= ConfigManager::getSingleton().getSpellConfigUInt32("SummonWorkerUpgradedResearchLevel"));
            for(uint32_t i = 0; i < amount; ++i)
            {
                Creature* newCreature = new Creature(gameMap, workerClass, seat);
                newCreature->addToGameMap();
                if(upgraded)
                    newCreature->setLevel(ConfigManager::getSingleton().getSpellConfigUInt32("SummonWorkerUpgradedLevel"));

                Ogre::Vector3 spawnPosition(static_cast<Ogre::Real>(tile->getX()),
                                            static_cast<Ogre::Real>(tile->getY()), 0.0f);
                newCreature->addParticleEffect("SummonWorker", 3);
                newCreature->createMesh();
                newCreature->setPosition(spawnPosition);
                seat->notifyCreatureArrival(workerClass->getClassName());
            }
            break;
        }
        case GiftBoxType::makeHappy:
        {
            std::vector<Creature*> creatures = gameMap->getCreaturesBySeat(seat);
            for(Creature* creature : creatures)
            {
                if(creature->isAlive())
                    creature->removeAnnoyance();
            }
            break;
        }
        case GiftBoxType::makeUnhappy:
        {
            std::vector<Creature*> creatures = gameMap->getCreatures();
            for(Creature* creature : creatures)
            {
                if(!creature->isAlive() || creature->getSeat()->isRogueSeat())
                    continue;

                if(creature->getSeat()->isAlliedSeat(seat))
                    continue;

                creature->makeUnhappy();
            }
            break;
        }
        case GiftBoxType::killCreatures:
        {
            // One visible enemy creature is chosen at random
            std::vector<Creature*> victims;
            std::vector<Creature*> creatures = gameMap->getCreatures();
            for(Creature* creature : creatures)
            {
                // Owner answer 110: a creature held in a keeper's hand is not on the map and is no target
                if(!creature->isAlive() || !creature->getIsOnMap() || creature->getSeat()->isAlliedSeat(seat))
                    continue;

                Tile* pos = creature->getPositionTile();
                if((pos == nullptr) || !seat->hasVisionOnTile(pos))
                    continue;

                victims.push_back(creature);
            }
            if(victims.empty())
                break;

            Creature* victim = victims[Random::Int(0, static_cast<int>(victims.size()) - 1)];
            victim->takeDamage(nullptr, victim->getHP() + 1.0, 0.0, 0.0, 0.0, victim->getPositionTile(), false);
            break;
        }
        default:
            OD_LOG_ERR("Unexpected GiftBoxType=" + Helper::toString(static_cast<uint32_t>(type)));
            break;
    }
}
