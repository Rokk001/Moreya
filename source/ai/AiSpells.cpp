/*!
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

#include "ai/AiSpells.h"

#include "ai/AiActions.h"
#include "ai/AiKnowledge.h"
#include "ai/AiMind.h"
#include "ai/AiSettings.h"
#include "ai/AiWar.h"
#include "ai/KeeperAI.h"

#include "creatureaction/CreatureAction.h"
#include "creatureaction/CreatureActionFight.h"
#include "creaturemood/CreatureMood.h"
#include "creatureskill/CreatureSkill.h"
#include "entities/Building.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "game/SkillManager.h"
#include "game/SkillType.h"
#include "gamemap/GameMap.h"
#include "ODApplication.h"
#include "rooms/Room.h"
#include "rooms/RoomDungeonTemple.h"
#include "rooms/RoomType.h"
#include "spells/SpellBlessing.h"
#include "spells/SpellBreakWall.h"
#include "spells/SpellCurse.h"
#include "spells/SpellInvisibility.h"
#include "spells/SpellPlague.h"
#include "spells/SpellRevealEnemy.h"
#include "spells/SpellSummonChampion.h"
#include "spells/SpellType.h"
#include "utils/ConfigManager.h"
#include "utils/Random.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <limits>
#include <sstream>
#include <string>

namespace
{
//! \brief One spell the casting loop can choose from.
struct SpellOption
{
    SpellType mType;
    double mPrice;
    //! \brief Damage per mana of the spell (0 for Heal).
    double mEfficiency;
};

//! \brief Returns the key of the price of a spell in the spell configuration (the six spells of the review included).
const char* priceKey(SpellType type)
{
    switch(type)
    {
        case SpellType::callToWar: return "CallToWarPrice";
        case SpellType::creatureHeal: return "CreatureHealPrice";
        case SpellType::creatureExplosion: return "CreatureExplosionPrice";
        case SpellType::creatureHaste: return "CreatureHastePrice";
        case SpellType::creatureDefense: return "CreatureDefensePrice";
        case SpellType::creatureSlow: return "CreatureSlowPrice";
        case SpellType::creatureStrength: return "CreatureStrengthPrice";
        case SpellType::creatureWeak: return "CreatureWeakPrice";
        case SpellType::eyeEvil: return "EyeEvilPrice";
        case SpellType::lightning: return "LightningPrice";
        case SpellType::tremor: return "TremorPrice";
        case SpellType::defector: return "DefectorPrice";
        case SpellType::hexenHen: return "HexenHenPrice";
        case SpellType::inferno: return "InfernoPrice";
        case SpellType::summonChampion: return "SummonChampionPrice";
        case SpellType::curse: return "CursePrice";
        case SpellType::blessing: return "BlessingPrice";
        case SpellType::invisibility: return "InvisibilityPrice";
        case SpellType::plague: return "PlaguePrice";
        case SpellType::breakWall: return "BreakWallPrice";
        case SpellType::revealEnemy: return "RevealEnemyPrice";
        default: return "";
    }
}

//! \brief Returns the mana price of a spell.
double spellPrice(SpellType type)
{
    return ConfigManager::getSingleton().getSpellConfigDouble(priceKey(type));
}

//! \brief Returns a value of the [KeeperAI] section of ai.cfg.
double aiKey(const std::string& key)
{
    return ConfigManager::getSingleton().getAiConfigDouble(key);
}

//! \brief Tells whether the AI can cast the spell now: researched, off cooldown and mana for the price plus a share
//! of the maximum mana.
//! \param reserveKey The key of the share of MaxManaPerSeat that stays free.
bool canCast(KeeperAI& ai, SpellType type, const std::string& reserveKey)
{
    Player& player = ai.getControlledPlayer();
    Seat* seat = player.getSeat();
    if(!SkillManager::isSpellAvailable(type, seat))
        return false;

    if(player.getSpellCooldownTurns(type) > 0)
        return false;

    double reserve = aiKey(reserveKey) * ConfigManager::getSingleton().getMaxManaPerSeat();
    return seat->getMana() >= (spellPrice(type) + reserve);
}

//! \brief Returns the HP share of a creature.
double hpShare(const Creature* creature)
{
    return creature->getHP() / std::max(1.0, creature->getMaxHp());
}

//! \brief Returns the strength of a creature: HP times raw damage per second.
double strength(const Creature* creature)
{
    return creature->getHP() * creature->getRawDamagePerSecond();
}

//! \brief Tells whether the creature stands on ground claimed for the seat.
bool onOwnGround(const Creature* creature, const Seat* seat)
{
    Tile* tile = creature->getPositionTile();
    return (tile != nullptr) && tile->isClaimedForSeat(seat);
}

//! \brief Returns the enemy fighters the AI sees now (the tile of the creature is in the vision of the AI's seat). A
//! creature hidden by the Invisibility spell is not seen.
std::vector<Creature*> visibleEnemies(KeeperAI& ai)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    std::vector<Creature*> enemies;
    for(Creature* creature : ai.getGameMap().getCreatures())
    {
        if(!creature->isAlive() || creature->getDefinition()->isWorker() || creature->isSpellInvisible())
            continue;

        Seat* creatureSeat = creature->getSeat();
        if((creatureSeat == nullptr) || (creatureSeat == seat) || seat->isAlliedSeat(creatureSeat))
            continue;

        Tile* tile = creature->getPositionTile();
        if(tile == nullptr)
            continue;

        const std::vector<Seat*>& seeing = tile->getSeatsWithVision();
        if(std::find(seeing.begin(), seeing.end(), seat) == seeing.end())
            continue;

        enemies.push_back(creature);
    }
    return enemies;
}

//! \brief Tells whether the creature takes part in a fight now (fighting, or fleeing from one).
bool inFight(const Creature* creature)
{
    return creature->isActionInList(CreatureActionType::fight) || creature->isActionInList(CreatureActionType::flee);
}

//! \brief Tells whether the first attack line of the creature's kind is a melee attack.
bool isMelee(const Creature* creature)
{
    const CreatureDefinition* definition = creature->getDefinition();
    for(const CreatureSkill* skill : definition->getCreatureSkills())
    {
        if(definition->isFirstAttackSkill(skill))
            return skill->getSkillName() == "Melee";
    }
    return false;
}

//! \brief Returns the own fighters that are alive and on the map.
std::vector<Creature*> ownFighters(KeeperAI& ai)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    std::vector<Creature*> fighters;
    for(Creature* creature : ai.getGameMap().getCreaturesBySeat(seat))
    {
        if(!creature->isAlive() || creature->isKo() || creature->getDefinition()->isWorker() ||
           (creature->getPositionTile() == nullptr))
        {
            continue;
        }
        fighters.push_back(creature);
    }
    return fighters;
}

//! \brief Tells whether one of the two creatures is among the enemies the other one sees, so they can fight each other.
bool engaged(const Creature* a, const Creature* b)
{
    const std::vector<GameEntity*>& seenByA = a->getVisibleEnemyObjects();
    if(std::find(seenByA.begin(), seenByA.end(), b) != seenByA.end())
        return true;

    const std::vector<GameEntity*>& seenByB = b->getVisibleEnemyObjects();
    return std::find(seenByB.begin(), seenByB.end(), a) != seenByB.end();
}

//! \brief Collects the creatures of the fight at a tile: starting with the fighting creature nearest to the tile, every
//! fighting own fighter and fighting enemy in sight that is linked to it by a chain of creatures seeing each other as
//! enemies. A parallel fight elsewhere on the map stays out of the group.
//! \param fightTile The tile of the Fight event of the fight, nullptr for none (empty group).
//! \param own Out: the own fighters of the fight.
//! \param enemies Out: the enemy fighters in sight of the fight.
void fightGroupAt(KeeperAI& ai, Tile* fightTile, std::vector<Creature*>& own, std::vector<Creature*>& enemies)
{
    own.clear();
    enemies.clear();
    if(fightTile == nullptr)
        return;

    std::vector<Creature*> ownLeft;
    for(Creature* creature : ownFighters(ai))
    {
        if(inFight(creature))
            ownLeft.push_back(creature);
    }
    std::vector<Creature*> enemyLeft;
    for(Creature* creature : visibleEnemies(ai))
    {
        if(inFight(creature))
            enemyLeft.push_back(creature);
    }

    // The seed: the fighting creature nearest to the tile of the Fight event
    Creature* seed = nullptr;
    bool seedOwn = false;
    int seedDistance = 0;
    for(int side = 0; side < 2; ++side)
    {
        for(Creature* creature : (side == 0) ? ownLeft : enemyLeft)
        {
            Tile* tile = creature->getPositionTile();
            int dx = tile->getX() - fightTile->getX();
            int dy = tile->getY() - fightTile->getY();
            int distance = dx * dx + dy * dy;
            if((seed == nullptr) || (distance < seedDistance))
            {
                seed = creature;
                seedOwn = (side == 0);
                seedDistance = distance;
            }
        }
    }
    if(seed == nullptr)
        return;

    std::vector<Creature*>& seedLeft = seedOwn ? ownLeft : enemyLeft;
    seedLeft.erase(std::find(seedLeft.begin(), seedLeft.end(), seed));
    (seedOwn ? own : enemies).push_back(seed);

    // Each side grows by the creatures of the other side that are engaged with one of its members
    size_t ownDone = 0;
    size_t enemyDone = 0;
    while((ownDone < own.size()) || (enemyDone < enemies.size()))
    {
        bool fromOwn = (ownDone < own.size());
        Creature* member = fromOwn ? own[ownDone++] : enemies[enemyDone++];
        std::vector<Creature*>& other = fromOwn ? enemyLeft : ownLeft;
        std::vector<Creature*>& joined = fromOwn ? enemies : own;
        std::vector<Creature*> kept;
        for(Creature* creature : other)
        {
            if(engaged(member, creature))
                joined.push_back(creature);
            else
                kept.push_back(creature);
        }
        other.swap(kept);
    }
}

//! \brief Collects the creatures of the fight of the session whose decisions run now (fightGroupAt at its tile).
//! \param own Out: the own fighters of the fight.
//! \param enemies Out: the enemy fighters in sight of the fight.
void fightGroup(KeeperAI& ai, std::vector<Creature*>& own, std::vector<Creature*>& enemies)
{
    const SPELL::State& state = ai.getSpellState();
    fightGroupAt(ai, ai.getGameMap().getTile(state.mFightX, state.mFightY), own, enemies);
}

//! \brief Returns the enemy fighters in sight that take part in the current fight (fightGroup).
std::vector<Creature*> fightEnemies(KeeperAI& ai)
{
    std::vector<Creature*> own;
    std::vector<Creature*> enemies;
    fightGroup(ai, own, enemies);
    return enemies;
}

//! \brief Returns the own fighters that take part in the current fight (fightGroup).
std::vector<Creature*> fightingOwn(KeeperAI& ai)
{
    std::vector<Creature*> own;
    std::vector<Creature*> enemies;
    fightGroup(ai, own, enemies);
    return own;
}

//! \brief Returns the building the creature attacks now, or nullptr when it attacks a creature or nothing. It is the
//! choice of CreatureActionFight::handleFight: a fight with a given target attacks only that creature; otherwise the
//! living creatures in sight come first, and only when none of them can be attacked or reached, the buildings in sight.
//! A worker never attacks a building.
GameEntity* attackedBuilding(Creature* creature)
{
    if(creature->getDefinition()->isWorker())
        return nullptr;

    // The fight action on top of the others is the one that runs
    const CreatureActionFight* fight = nullptr;
    for(const std::unique_ptr<CreatureAction>& action : creature->getActions())
    {
        if(action->getType() == CreatureActionType::fight)
            fight = static_cast<const CreatureActionFight*>(action.get());
    }
    if((fight == nullptr) || (fight->getEntityAttack() != nullptr))
        return nullptr;

    std::vector<GameEntity*> creatures;
    std::vector<GameEntity*> buildings;
    for(GameEntity* entity : creature->getVisibleEnemyObjects())
    {
        if(entity->getObjectType() != GameEntityType::creature)
            buildings.push_back(entity);
        else if(static_cast<Creature*>(entity)->isAlive())
            creatures.push_back(entity);
    }

    static const std::vector<Tile*> noFilter;
    GameEntity* target = nullptr;
    Tile* targetTile = nullptr;
    Tile* position = nullptr;
    CreatureSkillData* skill = nullptr;
    if(!creatures.empty() && creature->searchBestTargetInList(creatures, noFilter, target, targetTile, position, skill))
        return nullptr;

    target = nullptr;
    if(buildings.empty() || !creature->searchBestTargetInList(buildings, noFilter, target, targetTile, position, skill))
        return nullptr;

    return target;
}

//! \brief Returns the creature of the list with the lowest HP share.
Creature* weakest(const std::vector<Creature*>& list)
{
    Creature* best = nullptr;
    for(Creature* creature : list)
    {
        if((best == nullptr) || (hpShare(creature) < hpShare(best)))
            best = creature;
    }
    return best;
}

//! \brief Returns the creature of the list with the highest strength.
Creature* strongest(const std::vector<Creature*>& list)
{
    Creature* best = nullptr;
    for(Creature* creature : list)
    {
        if((best == nullptr) || (strength(creature) > strength(best)))
            best = creature;
    }
    return best;
}

//! \brief Returns a random creature of the list, or nullptr for an empty list.
Creature* anyOf(const std::vector<Creature*>& list)
{
    if(list.empty())
        return nullptr;

    return list[Random::Int(0, static_cast<int>(list.size()) - 1)];
}

//! \brief Picks the target of a spell: the lowest-HP creature with the focus fire of the level, otherwise a random one.
Creature* focusTarget(KeeperAI& ai, const std::vector<Creature*>& list)
{
    if(Random::Double(0.0, 1.0) < ai.getSettings().focusFire)
    {
        // The lowest absolute HP, as the target a player would finish first
        Creature* best = nullptr;
        for(Creature* creature : list)
        {
            if((best == nullptr) || (creature->getHP() < best->getHP()))
                best = creature;
        }
        return best;
    }
    return anyOf(list);
}

//! \brief Returns how many of the creatures stand within the radius of an area spell around the tile (the circle the
//! spell itself tests).
//! \param centerTile The tile the area spell would be cast on.
//! \param radius The radius of the spell in tiles.
int creaturesAround(const std::vector<Creature*>& list, const Tile* centerTile, double radius)
{
    int count = 0;
    for(Creature* creature : list)
    {
        Tile* tile = creature->getPositionTile();
        if(tile == nullptr)
            continue;

        int dx = tile->getX() - centerTile->getX();
        int dy = tile->getY() - centerTile->getY();
        if(static_cast<double>(dx * dx + dy * dy) <= (radius * radius))
            ++count;
    }
    return count;
}

//! \brief Returns the creatures of the list that stand on ground claimed for the AI's seat.
std::vector<Creature*> onOwnGroundOnly(KeeperAI& ai, const std::vector<Creature*>& list)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    std::vector<Creature*> result;
    for(Creature* creature : list)
    {
        if(onOwnGround(creature, seat))
            result.push_back(creature);
    }
    return result;
}

//! \brief Returns the enemies of the current fight that stand on ground claimed for the AI's seat.
std::vector<Creature*> enemiesOnOwnGround(KeeperAI& ai)
{
    return onOwnGroundOnly(ai, fightEnemies(ai));
}

//! \brief Casts a spell on the creature: the area spells Inferno and Tremor on its tile, every other spell on the
//! creature itself, which the hand looks up by name when it reaches it (not at the time of the decision).
//! \return The mind time at which the hand has finished the cast.
double castOnTileOf(KeeperAI& ai, SpellType type, Creature* creature)
{
    if((type == SpellType::inferno) || (type == SpellType::tremor))
        return ACTS::castSpell(ai, type, creature->getPositionTile());

    return ACTS::castSpell(ai, type, creature);
}

//! \brief Tells whether the tile is covered by the heart room of the seat.
bool isHeartTile(const Tile* tile, const Seat* seat)
{
    if(tile == nullptr)
        return false;

    Room* room = tile->getCoveringRoom();
    return (room != nullptr) && (room->getType() == RoomType::dungeonTemple) && (room->getSeat() == seat);
}

//! \brief Tells whether a running mood effect of the given name (a curse, a blessing) is on the creature.
bool hasMoodEffect(const Creature* creature, const std::string& name)
{
    for(const CreatureMoodEffect& effect : creature->getMoodEffects())
    {
        if((effect.mName == name) && (effect.mTurnsLeft > 0.0))
            return true;
    }
    return false;
}

//! \brief Tells whether the two creatures stand within the given number of tiles of each other (in both directions).
bool withinTiles(const Creature* a, const Creature* b, int tiles)
{
    Tile* tileA = a->getPositionTile();
    Tile* tileB = b->getPositionTile();
    if((tileA == nullptr) || (tileB == nullptr))
        return false;

    return (std::abs(tileA->getX() - tileB->getX()) <= tiles) && (std::abs(tileA->getY() - tileB->getY()) <= tiles);
}

//! \brief Returns a claimed, not full tile of the own land next to the own heart, or nullptr.
Tile* tileNextToHeart(KeeperAI& ai)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    for(Room* room : ai.getGameMap().getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        for(Tile* heartTile : room->getCoveredTiles())
        {
            for(Tile* neighbor : heartTile->getAllNeighbors())
            {
                if(!neighbor->isFullTile() && neighbor->isClaimedForSeat(seat) && (neighbor->getCoveringBuilding() == nullptr))
                    return neighbor;
            }
        }
    }
    return nullptr;
}

//! \brief The tile of a wasted area spell (the E19 mistake): a tile of the own land, next to the heart or under an own
//! fighter, on which the spell reaches no enemy the AI sees, so the mana is paid without effect.
//! \param type Inferno or Tremor.
//! \return The tile, or nullptr when every such tile has an enemy in reach (then nothing is cast).
Tile* wastedAreaTile(KeeperAI& ai, SpellType type)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    const char* radiusKey = (type == SpellType::inferno) ? "InfernoRadiusTiles" : "TremorRadiusTiles";
    double radius = ConfigManager::getSingleton().getSpellConfigDouble(radiusKey);
    std::vector<Tile*> candidates;
    Tile* heartSide = tileNextToHeart(ai);
    if(heartSide != nullptr)
        candidates.push_back(heartSide);
    for(Creature* creature : ownFighters(ai))
    {
        if(onOwnGround(creature, seat))
            candidates.push_back(creature->getPositionTile());
    }

    // Every enemy creature in sight counts, workers included, since the area spells hurt them too
    std::vector<Creature*> enemies;
    for(Creature* creature : ai.getGameMap().getCreatures())
    {
        Seat* creatureSeat = creature->getSeat();
        Tile* position = creature->getPositionTile();
        if(!creature->isAlive() || (creatureSeat == nullptr) || seat->isAlliedSeat(creatureSeat) || (position == nullptr) ||
           !seat->hasVisionOnTile(position))
        {
            continue;
        }
        enemies.push_back(creature);
    }
    for(Tile* tile : candidates)
    {
        if(!tile->isFullTile() && (creaturesAround(enemies, tile, radius) == 0))
            return tile;
    }
    return nullptr;
}

//! \brief The target of a wasted single-target spell (the E19 mistake): the valid target on which the spell helps least.
//! Heal goes to the own hurt creature on own claimed ground with the highest HP share; Lightning and Explosion go to the
//! enemy of the fight on own claimed ground with the highest HP share (most HP when equal), where the damage is wasted.
//! \param type The spell of the mistake.
//! \param enemies The enemies of the fight that stand on ground claimed for the AI.
//! \return The target, or nullptr when the spell has no valid target (then nothing is cast).
Creature* wastedCreatureTarget(KeeperAI& ai, SpellType type, const std::vector<Creature*>& enemies)
{
    Seat* seat = ai.getControlledPlayer().getSeat();
    std::vector<Creature*> valid;
    if(type == SpellType::creatureHeal)
    {
        for(Creature* creature : ownFighters(ai))
        {
            if(onOwnGround(creature, seat) && creature->isHurt())
                valid.push_back(creature);
        }
    }
    else
    {
        valid = enemies;
    }

    Creature* best = nullptr;
    for(Creature* creature : valid)
    {
        if((best == nullptr) || (hpShare(creature) > hpShare(best)) ||
           ((hpShare(creature) == hpShare(best)) && (creature->getHP() > best->getHP())))
        {
            best = creature;
        }
    }
    return best;
}

//! \brief Writes a number with full double precision for a draw line.
std::string numberToken(double value)
{
    std::ostringstream os;
    os.precision(17);
    os << value;
    return os.str();
}

//! \brief Encodes a creature name into one comma-free saved token.
std::string encodeName(const std::string& value)
{
    static const char digits[] = "0123456789abcdef";
    std::string result;
    for(unsigned char ch : value)
    {
        result += digits[ch >> 4];
        result += digits[ch & 15];
    }
    return result;
}

//! \brief Decodes one saved creature name, returning empty for an invalid token.
std::string decodeName(const std::string& value)
{
    if(value.size() % 2 != 0)
        return "";
    std::string result;
    for(std::size_t i = 0; i < value.size(); i += 2)
    {
        unsigned int ch = 0;
        std::istringstream input(value.substr(i, 2));
        if(!(input >> std::hex >> ch))
            return "";
        result += static_cast<char>(ch);
    }
    return result;
}

//! \brief Splits a comma separated draw value into its parts.
std::vector<std::string> splitValue(const std::string& value)
{
    std::vector<std::string> parts;
    std::string::size_type start = 0;
    while(true)
    {
        std::string::size_type comma = value.find(',', start);
        parts.push_back(value.substr(start, (comma == std::string::npos) ? std::string::npos : comma - start));
        if(comma == std::string::npos)
            return parts;
        start = comma + 1;
    }
}

//! \brief Reads the spell draws of a loaded game from the mind once: Eye cast state (E04), the
//! pending late Defense (E05) and the running fight sessions (E19, one line each). The mind imports its state at its
//! first turn, at mind time 0, so a saved time relative to the save is the mind time itself.
void restoreDraws(KeeperAI& ai)
{
    SPELL::State& state = ai.getSpellState();
    if(state.mRestored)
        return;

    state.mRestored = true;
    bool legacyLate = false;
    for(const AiMath::AiStateLine& line : ai.getMind().savedRows())
    {
        if((line.tag != "draw") || (line.tokens.size() != 3))
            continue;

        if((line.tokens[0] == "E04") && (line.tokens[1] == "eyeTurn"))
            state.mLastEyeTurn = std::atoll(line.tokens[2].c_str());
        else if((line.tokens[0] == "E04") && (line.tokens[1] == "eyePending"))
            state.mEyePending = (line.tokens[2] == "1");
        else if((line.tokens[0] == "E05") && (line.tokens[1] == "lateDefense"))
            legacyLate = (line.tokens[2] == "1");
        else if((line.tokens[0] == "E19") && (line.tokens[1] == "session"))
        {
            // start,lastFight,x,y,nextCast,haste,lateDefense,holderCount,encoded holder names
            std::vector<std::string> parts = splitValue(line.tokens[2]);
            if(parts.size() < 6)
                continue;

            SPELL::State::Session session;
            session.mStart = std::atof(parts[0].c_str());
            session.mLastFight = std::atof(parts[1].c_str());
            session.mFightX = std::atoi(parts[2].c_str());
            session.mFightY = std::atoi(parts[3].c_str());
            session.mNextCast = std::atof(parts[4].c_str());
            session.mHaste = (parts[5] == "1");
            session.mLateDefense = (parts.size() >= 7) && (parts[6] == "1");
            session.mLegacyHolders = parts.size() < 8;
            if(!session.mLegacyHolders)
            {
                char* end = nullptr;
                unsigned long count = std::strtoul(parts[7].c_str(), &end, 10);
                if(end == parts[7].c_str() || *end != '\0' || count != parts.size() - 8)
                    continue;
                for(std::size_t i = 8; i < parts.size(); ++i)
                {
                    const std::string name = decodeName(parts[i]);
                    if(!name.empty())
                        session.mDefenseHolders.push_back(name);
                }
            }
            state.mSessions.push_back(session);
        }
    }
    // A save that kept one late Defense flag for the whole AI: the fights that were running owe it
    if(legacyLate)
    {
        for(SPELL::State::Session& session : state.mSessions)
            session.mLateDefense = true;
    }
}

//! \brief Saves spell draws, the Eye cast state and each session's delayed Defense holders.
void saveDraws(KeeperAI& ai, std::vector<AiMath::AiStateLine>& lines)
{
    restoreDraws(ai);
    std::vector<AiMath::AiStateLine> kept;
    for(const AiMath::AiStateLine& line : lines)
    {
        bool own = (line.tag == "draw") && !line.tokens.empty() &&
                   ((line.tokens[0] == "E04") || (line.tokens[0] == "E05") || (line.tokens[0] == "E19"));
        if(!own)
            kept.push_back(line);
    }
    lines.swap(kept);

    const SPELL::State& state = ai.getSpellState();
    if(state.mLastEyeTurn >= 0)
    {
        AiMath::AiStateLine line;
        line.tag = "draw";
        line.tokens.push_back("E04");
        line.tokens.push_back("eyeTurn");
        line.tokens.push_back(std::to_string(state.mLastEyeTurn));
        lines.push_back(line);
    }
    if(state.mEyePending)
        lines.push_back({"draw", {"E04", "eyePending", "1"}});
    // The times relative to the save, one line per running session
    double now = ai.getMind().now();
    for(const SPELL::State::Session& session : state.mSessions)
    {
        AiMath::AiStateLine line;
        line.tag = "draw";
        line.tokens.push_back("E19");
        line.tokens.push_back("session");
        std::string value = numberToken(session.mStart - now) + "," + numberToken(session.mLastFight - now) + "," +
                              std::to_string(session.mFightX) + "," + std::to_string(session.mFightY) + "," +
                              numberToken(session.mNextCast - now) + "," + (session.mHaste ? "1" : "0") + "," +
                              (session.mLateDefense ? "1" : "0");
        if(!session.mLegacyHolders)
        {
            value += "," + std::to_string(session.mDefenseHolders.size());
            for(const std::string& name : session.mDefenseHolders)
                value += "," + encodeName(name);
        }
        line.tokens.push_back(value);
        lines.push_back(line);
    }
}

//! \brief Returns the seconds the fight marker of the game at the tile still lasts, or a negative number when the seat
//! shows none: the game raises one Fight event per fight place and refreshes its marker (FightOverSeconds) while the
//! fight goes on, so the marker shows that the fight lasts and its end is the end of the fight.
double fightMarkerRemain(KeeperAI& ai, int x, int y)
{
    const Player& player = ai.getControlledPlayer();
    uint32_t index = std::numeric_limits<uint32_t>::max();
    const PlayerEvent* event = player.getNextEvent(index);
    uint32_t first = index;
    while(event != nullptr)
    {
        Tile* tile = event->getTile();
        if((event->getType() == PlayerEventType::fight) && (tile != nullptr) && (tile->getX() == x) && (tile->getY() == y))
            return event->getTimeRemain();

        event = player.getNextEvent(index);
        if(index == first)
            break;
    }
    return -1.0;
}

//! \brief Makes the session the one whose decisions run now: the fight spells look at the creatures of its fight.
void selectSession(KeeperAI& ai, const SPELL::State::Session& session)
{
    SPELL::State& state = ai.getSpellState();
    state.mFightX = session.mFightX;
    state.mFightY = session.mFightY;
}

//! \brief Runs a session's casting loop and tries Haste once an ongoing fight exceeds HasteFightSeconds.
void stepSession(KeeperAI& ai, SPELL::State::Session& session, double now)
{
    selectSession(ai, session);
    if(!session.mHaste && ((now - session.mStart) > aiKey("HasteFightSeconds")) &&
       ((now - session.mLastFight) < aiKey("FightOverSeconds")))
    {
        session.mHaste = true;
        SPELL::castHaste(ai, fightingOwn(ai), false, now - session.mStart);
    }

    // On ground not claimed for the AI (an assault) only Inferno and Tremor reach the enemy
    Tile* tile = ai.getGameMap().getTile(session.mFightX, session.mFightY);
    bool enemyGround = (tile != nullptr) && !tile->isClaimedForSeat(ai.getControlledPlayer().getSeat());
    SPELL::chooseSpell(ai, enemyGround, now, session.mNextCast);
}

//! \brief The casting loops of the fight sessions: a cast as soon as the previous one of the same session allows it.
//! A session lasts while the game shows its fight marker; the marker lives FightOverSeconds after the last Fight event,
//! so the session ends the moment the fight is over (and, when no marker is seen, FightOverSeconds after its last
//! Fight reaction). The late Defense of the E05 mistake is cast when its own session ends. Run by the mind every
//! AiPollSeconds; it never raises an event, so the loop needs no hand time of its own.
//! \return Always false.
bool sessionStep(KeeperAI& ai)
{
    restoreDraws(ai);
    SPELL::State& state = ai.getSpellState();
    double now = ai.getMind().now();
    std::vector<SPELL::State::Session> running;
    std::vector<SPELL::State::Session> ended;
    for(const SPELL::State::Session& session : state.mSessions)
    {
        SPELL::State::Session current = session;
        double remain = fightMarkerRemain(ai, current.mFightX, current.mFightY);
        if(remain >= 0.0)
            current.mLastFight = std::max(current.mLastFight, now - (aiKey("FightOverSeconds") - remain));
        if((now - current.mLastFight) < aiKey("FightOverSeconds"))
            running.push_back(current);
        else
            ended.push_back(current);
    }
    state.mSessions.swap(running);
    // The late Defense of a fight drawn as a mistake follows when that fight is over
    for(SPELL::State::Session& session : ended)
    {
        std::vector<Creature*> holders;
        if(session.mLegacyHolders)
            holders = ownFighters(ai);
        else
            for(const std::string& name : session.mDefenseHolders)
            {
                Creature* creature = ai.getGameMap().getCreature(name);
                if(creature != nullptr && creature->isAlive() && creature->getSeat() == ai.getControlledPlayer().getSeat())
                    holders.push_back(creature);
            }
        SPELL::castDefense(ai, onOwnGroundOnly(ai, holders), true, session.mLateDefense);
    }
    for(SPELL::State::Session& session : state.mSessions)
        stepSession(ai, session, now);
    return false;
}

//! \brief Tells whether two lists of creatures share a creature.
bool shareCreature(const std::vector<Creature*>& a, const std::vector<Creature*>& b)
{
    for(Creature* creature : a)
    {
        if(std::find(b.begin(), b.end(), creature) != b.end())
            return true;
    }
    return false;
}

//! \brief The reaction to a Fight event after its alert delay: starts the session of a new fight, or extends the session
//! of the same fight (same tile or creatures of the same fight), and makes the decisions of the single-target and
//! support spells of this fight, retaining its holders for a delayed Defense cast.
void onFight(KeeperAI& ai, const AiEvent& event)
{
    restoreDraws(ai);
    SPELL::State& state = ai.getSpellState();
    Seat* seat = ai.getControlledPlayer().getSeat();
    double now = ai.getMind().now();

    // E20 reacts to the Fight event itself; the other fight spells need a still-active session.
    if((now - event.time) >= aiKey("FightOverSeconds"))
    {
        SPELL::castChampion(ai, tileNextToHeart(ai), isHeartTile(event.tile, seat));
        return;
    }

    // The creatures of this fight; sessions that hold one of them are the same fight and are merged into one
    std::vector<Creature*> own;
    std::vector<Creature*> enemies;
    fightGroupAt(ai, event.tile, own, enemies);
    own.insert(own.end(), enemies.begin(), enemies.end());
    int match = -1;
    std::vector<SPELL::State::Session> kept;
    for(const SPELL::State::Session& session : state.mSessions)
    {
        bool sameTile = (event.tile != nullptr) && (session.mFightX == event.tile->getX()) &&
                        (session.mFightY == event.tile->getY());
        bool same = sameTile || (event.tile == nullptr);
        if(!same)
        {
            std::vector<Creature*> sessionOwn;
            std::vector<Creature*> sessionEnemies;
            fightGroupAt(ai, ai.getGameMap().getTile(session.mFightX, session.mFightY), sessionOwn, sessionEnemies);
            same = shareCreature(own, sessionOwn) || shareCreature(own, sessionEnemies);
        }
        if(!same)
        {
            kept.push_back(session);
            continue;
        }
        if(match < 0)
        {
            match = static_cast<int>(kept.size());
            kept.push_back(session);
            continue;
        }
        SPELL::State::Session& merged = kept[static_cast<size_t>(match)];
        merged.mStart = std::min(merged.mStart, session.mStart);
        merged.mLastFight = std::max(merged.mLastFight, session.mLastFight);
        merged.mNextCast = std::max(merged.mNextCast, session.mNextCast);
        merged.mHaste = merged.mHaste || session.mHaste;
        merged.mLegacyHolders = (merged.mLateDefense && merged.mLegacyHolders) ||
                                (session.mLateDefense && session.mLegacyHolders);
        merged.mLateDefense = merged.mLateDefense || session.mLateDefense;
        for(const std::string& name : session.mDefenseHolders)
            if(std::find(merged.mDefenseHolders.begin(), merged.mDefenseHolders.end(), name) == merged.mDefenseHolders.end())
                merged.mDefenseHolders.push_back(name);
    }
    state.mSessions.swap(kept);

    bool first = (match < 0);
    if(first)
    {
        SPELL::State::Session session;
        session.mStart = event.fightStart;
        session.mLastFight = event.time;
        session.mFightX = -1;
        session.mFightY = -1;
        session.mNextCast = now;
        session.mHaste = false;
        session.mLateDefense = false;
        session.mLegacyHolders = false;
        match = static_cast<int>(state.mSessions.size());
        state.mSessions.push_back(session);
    }
    SPELL::State::Session& session = state.mSessions[static_cast<size_t>(match)];
    session.mStart = std::min(session.mStart, event.fightStart);
    // The fight ends FightOverSeconds after the time the game raised the Fight event, not after this delayed reaction
    session.mLastFight = std::max(session.mLastFight, event.time);
    if(event.tile != nullptr)
    {
        session.mFightX = event.tile->getX();
        session.mFightY = event.tile->getY();
    }
    selectSession(ai, session);

    // Defense on the group that holds the entrance, at the first Fight of the session
    if(first)
    {
        const std::vector<Creature*> holders = onOwnGroundOnly(ai, fightingOwn(ai));
        SPELL::castDefense(ai, holders, false, session.mLateDefense);
        if(session.mLateDefense)
            for(Creature* holder : holders)
                session.mDefenseHolders.push_back(holder->getName());
    }

    SPELL::castSlow(ai);
    SPELL::castWeak(ai);
    SPELL::castDefector(ai);
    SPELL::castHexenHen(ai);

    // A fight on a heart tile is an attack on the heart
    bool heart = isHeartTile(event.tile, seat);
    SPELL::castChampion(ai, tileNextToHeart(ai), heart);

    // The first cast of the session follows this same alert delay; Haste once the fight lasts long enough
    stepSession(ai, session, now);
}

//! \brief The champion of an assault. The Launch event carries the drop tile of the main group and the tactic index as
//! amount (raid 3 gets no champion).
void onLaunch(KeeperAI& ai, const AiEvent& event)
{
    if(static_cast<int>(event.amount) != 3)
        SPELL::castChampion(ai, event.tile, true);
    else
        ai.getMind().slip("E20");
}

//! \brief The champion when the heart is critical.
void onHeartCritical(KeeperAI& ai, const AiEvent& event)
{
    SPELL::castChampion(ai, tileNextToHeart(ai), true);
}
}

//! \brief Starts the spell state without a pending cast or fight session.
SPELL::State::State() :
    mLastEyeTurn(-1),
    mEyePending(false),
    mFightX(-1),
    mFightY(-1),
    mRestored(false)
{
}

//! \brief Binds the fight sessions, the champion reactions, the saved draw lines and the look of rows E21 to E25.
void SPELL::bindRows(KeeperAI& ai)
{
    Mind& mind = ai.getMind();
    KeeperAI* self = &ai;
    std::function<void(const AiEvent&)> fight = [self](const AiEvent& event) { onFight(*self, event); };
    std::function<void(const AiEvent&)> champion = [self](const AiEvent& event)
    {
        if(event.type == AiEventType::Launch)
            onLaunch(*self, event);
        else
            onHeartCritical(*self, event);
    };
    std::function<bool()> session = [self]() { return sessionStep(*self); };
    std::function<void(std::vector<AiMath::AiStateLine>&)> save = [self](std::vector<AiMath::AiStateLine>& lines) { saveDraws(*self, lines); };

    mind.onEvent("E19", std::vector<AiEventType>(1, AiEventType::Fight), fight);
    std::vector<AiEventType> championEvents;
    championEvents.push_back(AiEventType::Launch);
    championEvents.push_back(AiEventType::HeartCritical);
    mind.onEvent("E20", championEvents, champion);
    mind.onPoll("E19", AiEventType::Fight, session);
    // The six spells of the review: Curse, Blessing, Invisibility, Plague and Break Wall on their own look; Reveal
    // Enemy (E26) is cast by the attack plan
    mind.onLook("E21", aiKey("LookFactorScan"), std::bind(&SPELL::spellLook, std::ref(ai)));
    mind.onSave(save);
}

//! \brief Chooses and schedules the most effective eligible fight spell for this session.
bool SPELL::chooseSpell(KeeperAI& ai, bool enemyGround, double now, double& nextCast)
{
    // AI row E02
    // AI row E09
    // AI row E11
    // AI row E15
    // AI row E16
    // AI row E19
    // AI row J04
    // AI row K06
    if(now < nextCast)
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    ConfigManager& config = ConfigManager::getSingleton();

    // The spells the AI may use here: on ground not claimed for the caster only Inferno and Tremor reach the enemy
    std::vector<SpellOption> damage;
    std::vector<SpellType> candidates;
    if(!enemyGround)
    {
        candidates.push_back(SpellType::lightning);
        candidates.push_back(SpellType::creatureExplosion);
    }
    candidates.push_back(SpellType::inferno);
    candidates.push_back(SpellType::tremor);
    for(SpellType type : candidates)
    {
        const std::string reserveKey = (type == SpellType::lightning) ? "LightningManaReserve" : "SpellManaReserve";
        if(!canCast(ai, type, reserveKey))
            continue;

        double amount = 0.0;
        double targets = 1.0;
        switch(type)
        {
            case SpellType::lightning:
                amount = (config.getSpellConfigDouble("LightningDamageMin") + config.getSpellConfigDouble("LightningDamage")) / 2.0;
                amount *= SkillManager::getResearchValue(seat, SkillType::spellLightning, 1.0, ResearchEffect::Damage);
                targets = aiKey("SpellTargetsLightning");
                break;
            case SpellType::creatureExplosion:
                amount = config.getSpellConfigDouble("CreatureExplosionValue") * config.getSpellConfigDouble("CreatureExplosionDuration");
                amount *= SkillManager::getResearchValue(seat, SkillType::spellCreatureExplosion, 1.0, ResearchEffect::Damage);
                targets = aiKey("SpellTargetsExplosion");
                break;
            case SpellType::inferno:
                amount = (config.getSpellConfigDouble("InfernoDamagePerTurnMin") + config.getSpellConfigDouble("InfernoDamagePerTurn")) / 2.0
                         * config.getSpellConfigDouble("InfernoNbTurns");
                amount *= SkillManager::getResearchValue(seat, SkillType::spellInferno, 1.0, ResearchEffect::Damage);
                targets = aiKey("SpellTargetsInferno");
                break;
            default:
                amount = (config.getSpellConfigDouble("TremorDamageMin") + config.getSpellConfigDouble("TremorDamage")) / 2.0;
                amount *= SkillManager::getResearchValue(seat, SkillType::spellTremor, 1.0, ResearchEffect::Damage);
                targets = aiKey("SpellTargetsTremor");
                break;
        }
        SpellOption option;
        option.mType = type;
        option.mPrice = spellPrice(type);
        option.mEfficiency = amount * targets / std::max(1.0, option.mPrice);
        damage.push_back(option);
    }

    // The heal reaches only own creatures of the fight on claimed ground, so an assault on enemy land has none
    std::vector<Creature*> hurt;
    bool healOffered = !enemyGround && canCast(ai, SpellType::creatureHeal, "SpellManaReserve");
    if(healOffered)
    {
        for(Creature* creature : fightingOwn(ai))
        {
            // Never a creature above HealNeverAbove: the heal would be wasted
            if((hpShare(creature) < aiKey("HealBelow")) && (hpShare(creature) <= aiKey("HealNeverAbove")) &&
               onOwnGround(creature, seat))
                hurt.push_back(creature);
        }
    }

    // Only the enemies of the fight count; without an enemy in sight nothing is cast, also no heal
    std::vector<Creature*> allEnemies = fightEnemies(ai);
    std::vector<Creature*> enemies = enemyGround ? allEnemies : onOwnGroundOnly(ai, allEnemies);
    if((damage.empty() && !healOffered) || allEnemies.empty())
    {
        nextCast = now + aiKey("CastRecheckSeconds");
        return false;
    }

    // The choice: a mistake picks a random spell of those the AI can cast and wastes it, otherwise heal or the best
    // damage per mana
    bool slipped = ai.getMind().slip("E19");
    SpellType chosen = SpellType::nullSpellType;
    if(slipped)
    {
        std::vector<SpellType> all;
        for(const SpellOption& option : damage)
            all.push_back(option.mType);
        if(healOffered)
            all.push_back(SpellType::creatureHeal);
        chosen = all[Random::Int(0, static_cast<int>(all.size()) - 1)];
    }
    else
    {
        const SpellOption* best = nullptr;
        for(const SpellOption& option : damage)
        {
            // Tremor is chosen by its damage per mana like the others; it needs no minimum group of intruders
            // Lightning and Explosion need a target on claimed ground
            if((option.mType != SpellType::inferno) && (option.mType != SpellType::tremor) && enemies.empty())
                continue;

            if((best == nullptr) || (option.mEfficiency > best->mEfficiency))
                best = &option;
        }
        if(!hurt.empty() && ((best == nullptr) || (Random::Double(0.0, 1.0) < aiKey("HealCastChance"))))
            chosen = SpellType::creatureHeal;
        else if(best != nullptr)
            chosen = best->mType;
    }

    if(chosen == SpellType::nullSpellType)
    {
        nextCast = now + aiKey("CastRecheckSeconds");
        return false;
    }

    double handEnd = now;
    // The target: a wasted cast of the mistake goes to the valid target where the spell helps least (an area spell on
    // own ground without an enemy in reach, a heal on the least hurt creature, a single-target spell on the healthiest
    // enemy); without such a target nothing is cast
    if(slipped)
    {
        if((chosen == SpellType::inferno) || (chosen == SpellType::tremor))
        {
            Tile* tile = wastedAreaTile(ai, chosen);
            if(tile == nullptr)
            {
                nextCast = now + aiKey("CastRecheckSeconds");
                return false;
            }
            handEnd = ACTS::castSpell(ai, chosen, tile);
        }
        else
        {
            Creature* target = wastedCreatureTarget(ai, chosen, enemies);
            if(target == nullptr)
            {
                nextCast = now + aiKey("CastRecheckSeconds");
                return false;
            }
            handEnd = ACTS::castSpell(ai, chosen, target);
        }
    }
    else if(chosen == SpellType::creatureHeal)
    {
        Creature* target = weakest(hurt);
        if(target == nullptr)
        {
            nextCast = now + aiKey("CastRecheckSeconds");
            return false;
        }
        handEnd = ACTS::castSpell(ai, chosen, target);
    }
    else
    {
        std::vector<Creature*>& pool = (chosen == SpellType::inferno || chosen == SpellType::tremor) ? allEnemies : enemies;
        Creature* target = nullptr;
        if(chosen == SpellType::inferno)
        {
            // Focus on the lowest-HP intruder, or choose randomly, as for the other damage spells.
            target = focusTarget(ai, pool);
        }
        else if(chosen == SpellType::tremor)
        {
            // The normal focus decision; Tremor needs no minimum group of nearby intruders.
            target = focusTarget(ai, pool);
        }
        else
        {
            target = focusTarget(ai, pool);
        }
        if(target == nullptr)
        {
            nextCast = now + aiKey("CastRecheckSeconds");
            return false;
        }

        if(chosen == SpellType::creatureExplosion)
            handEnd = ACTS::castSpell(ai, chosen, target);
        else
            handEnd = castOnTileOf(ai, chosen, target);
    }

    // The next cast is no earlier than the later of the end of the hand action and MinRecastSeconds
    nextCast = std::max(handEnd, now + aiKey("MinRecastSeconds"));
    return true;
}

bool SPELL::castHaste(KeeperAI& ai, const std::vector<Creature*>& group, bool march, double fightSeconds)
{
    // AI row E03
    if(!march && (fightSeconds <= aiKey("HasteFightSeconds")))
        return false;

    if(!canCast(ai, SpellType::creatureHaste, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    // The target must stand on ground claimed for the caster; the mistake casts it on idle creatures at home
    std::vector<Creature*> targets;
    bool slipped = ai.getMind().slip("E03");
    const std::vector<Creature*> source = slipped ? ownFighters(ai) : group;
    for(Creature* creature : source)
    {
        if(!onOwnGround(creature, seat))
            continue;

        if(slipped && creature->isActionInList(CreatureActionType::fight))
            continue;

        targets.push_back(creature);
    }
    Creature* target = slipped ? anyOf(targets) : strongest(targets);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::creatureHaste, target);
    return true;
}

//! \brief Schedules one Eye cast when none is pending and its interval has elapsed.
bool SPELL::castEye(KeeperAI& ai, Tile* tile)
{
    // AI row E04
    if((tile == nullptr) || !canCast(ai, SpellType::eyeEvil, "SpellManaReserve"))
        return false;

    restoreDraws(ai);
    State& state = ai.getSpellState();
    if(state.mEyePending)
        return false;
    int64_t turn = ai.getGameMap().getTurnNumber();
    double minTurns = aiKey("EyeCastIntervalMinutes") * 60.0 * ODApplication::turnsPerSecond;
    if((state.mLastEyeTurn >= 0) && (static_cast<double>(turn - state.mLastEyeTurn) < minTurns))
        return false;

    // The mistake: the AI never casts it and attacks blind
    if(ai.getMind().slip("E04"))
        return false;

    state.mEyePending = true;
    ACTS::castSpell(ai, SpellType::eyeEvil, tile);
    return true;
}

//! \brief Finishes an Eye cast after the server confirms success or rejection.
void SPELL::finishEyeCast(KeeperAI& ai, bool succeeded)
{
    restoreDraws(ai);
    State& state = ai.getSpellState();
    state.mEyePending = false;
    if(succeeded)
        state.mLastEyeTurn = ai.getGameMap().getTurnNumber();
}

bool SPELL::castDefense(KeeperAI& ai, const std::vector<Creature*>& holders, bool fightOver, bool& lateDefense)
{
    // AI row E05
    restoreDraws(ai);
    Seat* seat = ai.getControlledPlayer().getSeat();
    if(fightOver)
    {
        // The late cast of the mistake: after the fight
        if(!lateDefense)
            return false;

        lateDefense = false;
    }
    else if(ai.getMind().slip("E05"))
    {
        lateDefense = true;
        return false;
    }

    if(!canCast(ai, SpellType::creatureDefense, "SpellManaReserve"))
        return false;

    std::vector<Creature*> targets;
    for(Creature* creature : holders)
    {
        if(onOwnGround(creature, seat))
            targets.push_back(creature);
    }
    Creature* target = strongest(targets);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::creatureDefense, target);
    return true;
}

bool SPELL::castStrength(KeeperAI& ai, const std::vector<Creature*>& group)
{
    // AI row E06
    if(!canCast(ai, SpellType::creatureStrength, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    // The mistake: Strength on a creature that is leaving
    bool slipped = ai.getMind().slip("E06");
    std::vector<Creature*> targets;
    for(Creature* creature : (slipped ? ownFighters(ai) : group))
    {
        if(!onOwnGround(creature, seat))
            continue;

        if(slipped != creature->isActionInList(CreatureActionType::flee))
            continue;

        targets.push_back(creature);
    }
    Creature* target = slipped ? anyOf(targets) : strongest(targets);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::creatureStrength, target);
    return true;
}

bool SPELL::castCallToWar(KeeperAI& ai, Tile* tile, int creaturesToGather, bool assault)
{
    // AI row E07
    // The banner needs its price only: the launch already counts one price per group and the defence rally needs
    // mana >= price
    Player& player = ai.getControlledPlayer();
    if((tile == nullptr) || !SkillManager::isSpellAvailable(SpellType::callToWar, player.getSeat()) ||
       (player.getSpellCooldownTurns(SpellType::callToWar) > 0) ||
       (player.getSeat()->getMana() < spellPrice(SpellType::callToWar)))
    {
        return false;
    }

    // The defence rally: only for more than CallToWarMinCreatures creatures; the complex mistake rallies them by hand
    // instead of the banner. The banners of an assault are always cast (drawLaunchGathering is the launch's draw)
    if(!assault)
    {
        if(creaturesToGather <= static_cast<int>(aiKey("CallToWarMinCreatures")))
            return false;

        if(ai.getMind().slip("E07"))
            return false;
    }

    ACTS::castSpell(ai, SpellType::callToWar, tile);
    return true;
}

bool SPELL::drawLaunchGathering(KeeperAI& ai)
{
    // The mistake of the launch: the groups are not carried to the tunnel end and walk from home to their banners
    return ai.getMind().slip("E07");
}

//! \brief Slows a visible melee enemy of the current fight, including fighting workers.
bool SPELL::castSlow(KeeperAI& ai)
{
    // AI row E08
    if(!canCast(ai, SpellType::creatureSlow, "SpellManaReserve"))
        return false;

    std::vector<Creature*> enemies = enemiesOnOwnGround(ai);
    Seat* seat = ai.getControlledPlayer().getSeat();
    const State& state = ai.getSpellState();
    Tile* fightTile = ai.getGameMap().getTile(state.mFightX, state.mFightY);
    std::vector<Creature*> anchors = fightingOwn(ai);
    for(Creature* creature : ai.getGameMap().getCreaturesBySeat(seat))
        if(fightTile != nullptr && creature->isAlive() && creature->getDefinition()->isWorker() && inFight(creature) &&
           creature->getPositionTile() == fightTile)
            anchors.push_back(creature);
    for(Creature* creature : ai.getGameMap().getCreatures())
    {
        if(!creature->isAlive() || !creature->getDefinition()->isWorker() || !inFight(creature) ||
           creature->getSeat() == nullptr || seat->isAlliedSeat(creature->getSeat()) || !onOwnGround(creature, seat))
            continue;
        Tile* tile = creature->getPositionTile();
        const std::vector<Seat*>& vision = tile->getSeatsWithVision();
        if(std::find(vision.begin(), vision.end(), seat) == vision.end())
            continue;
        bool sameFight = tile == fightTile;
        for(Creature* anchor : anchors)
            sameFight = sameFight || engaged(anchor, creature);
        if(sameFight)
            enemies.push_back(creature);
    }
    std::vector<Creature*> melee;
    for(Creature* creature : enemies)
    {
        if(isMelee(creature))
            melee.push_back(creature);
    }
    // The mistake: the weakest enemy instead of the strongest melee enemy
    Creature* target = ai.getMind().slip("E08") ? weakest(enemies) : strongest(melee);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::creatureSlow, target);
    return true;
}

//! \brief Selects an enemy for Weak according to its damage or remaining HP.
bool SPELL::castWeak(KeeperAI& ai)
{
    // AI row E10
    if(!canCast(ai, SpellType::creatureWeak, "SpellManaReserve"))
        return false;

    std::vector<Creature*> enemies = enemiesOnOwnGround(ai);
    Creature* target = nullptr;
    if(ai.getMind().slip("E10"))
    {
        // The mistake: a nearly dead enemy
        for(Creature* creature : enemies)
            if(target == nullptr || creature->getHP() < target->getHP())
                target = creature;
    }
    else
    {
        for(Creature* creature : enemies)
        {
            if((target == nullptr) || (creature->getRawDamagePerSecond() > target->getRawDamagePerSecond()))
                target = creature;
        }
    }
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::creatureWeak, target);
    return true;
}

//! \brief Selects an eligible enemy for the Defector spell and schedules the cast.
bool SPELL::castDefector(KeeperAI& ai)
{
    // AI row E17
    if(!canCast(ai, SpellType::defector, "SpellManaReserve"))
        return false;

    // The AI needs room for the new fighter
    Seat* seat = ai.getControlledPlayer().getSeat();
    if(seat->getNumCreaturesFighters() >= seat->getNumCreaturesFightersMax())
        return false;

    // The best rule takes the strongest enemy whose mood is low (Upset or worse; the creature window shows the mood of
    // any creature); the mistake takes a strong one at full health, which resists
    bool slipped = ai.getMind().slip("E17");
    std::vector<Creature*> candidates;
    for(Creature* creature : enemiesOnOwnGround(ai))
    {
        if(creature->isInPrison() || creature->getDefinition()->isChampion())
            continue;
        CreatureMoodLevel mood = creature->getMoodValue();
        bool lowMood = (mood != CreatureMoodLevel::Unknown) && (static_cast<int>(mood) >= static_cast<int>(CreatureMoodLevel::Upset));
        if(slipped ? (hpShare(creature) >= 1.0) : lowMood)
            candidates.push_back(creature);
    }
    Creature* target = strongest(candidates);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::defector, target);
    return true;
}

//! \brief Selects a legal enemy target for Hexen Hen and schedules the cast.
bool SPELL::castHexenHen(KeeperAI& ai)
{
    // AI row E18
    if(!canCast(ai, SpellType::hexenHen, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    // The building each enemy of the fight attacks is the target its fight action chooses now; a room of the AI's seat
    // (the heart is the dungeon temple room) makes it the attacker of a room or the heart
    bool slipped = ai.getMind().slip("E18");
    std::vector<Creature*> candidates;
    for(Creature* creature : enemiesOnOwnGround(ai))
    {
        if(creature->isHexenHen() || creature->isInPrison() || creature->getDefinition()->isChampion())
            continue;
        GameEntity* building = attackedBuilding(creature);
        bool attacksRoom = (building != nullptr) && (building->getObjectType() == GameEntityType::room) &&
                           (building->getSeat() == seat);
        // The mistake: a random enemy that attacks no building
        if(slipped ? (building == nullptr) : attacksRoom)
            candidates.push_back(creature);
    }
    Creature* target = anyOf(candidates);
    if(target == nullptr)
        return false;

    castOnTileOf(ai, SpellType::hexenHen, target);
    return true;
}

//! \brief Curses the visible enemy of the highest level that is not cursed yet.
bool SPELL::castCurse(KeeperAI& ai)
{
    // AI row E21
    if(!canCast(ai, SpellType::curse, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    std::vector<Creature*> candidates;
    for(Creature* creature : visibleEnemies(ai))
    {
        if(SpellCurse::isValidTarget(*creature, seat) && !hasMoodEffect(creature, SpellCurse::MOOD_EFFECT_NAME))
            candidates.push_back(creature);
    }
    if(candidates.empty())
        return false;

    Creature* target = nullptr;
    if(ai.getMind().slip("E21"))
        target = anyOf(candidates);
    else
    {
        for(Creature* creature : candidates)
        {
            if((target == nullptr) || (creature->getLevel() > target->getLevel()))
                target = creature;
        }
    }
    if(target == nullptr)
        return false;

    ACTS::castSpell(ai, SpellType::curse, target);
    return true;
}

//! \brief Blesses the own creature in the worst mood that is Upset or worse and not blessed yet.
bool SPELL::castBlessing(KeeperAI& ai)
{
    // AI row E22
    if(!canCast(ai, SpellType::blessing, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    const bool slipped = ai.getMind().slip("E22");
    std::vector<Creature*> candidates;
    for(Creature* creature : ai.getGameMap().getCreaturesBySeat(seat))
    {
        if(!SpellBlessing::isValidTarget(*creature, seat) || hasMoodEffect(creature, SpellBlessing::MOOD_EFFECT_NAME))
            continue;

        CreatureMoodLevel mood = creature->getMoodValue();
        bool upset = (mood != CreatureMoodLevel::Unknown) &&
                     (static_cast<int>(mood) >= static_cast<int>(CreatureMoodLevel::Upset));
        // The mistake: a creature that is not upset
        if(slipped != upset)
            candidates.push_back(creature);
    }
    if(candidates.empty())
        return false;

    Creature* target = nullptr;
    if(slipped)
        target = anyOf(candidates);
    else
    {
        for(Creature* creature : candidates)
        {
            if((target == nullptr) ||
               (static_cast<int>(creature->getMoodValue()) > static_cast<int>(target->getMoodValue())))
                target = creature;
        }
    }
    if(target == nullptr)
        return false;

    ACTS::castSpell(ai, SpellType::blessing, target);
    return true;
}

//! \brief Hides the weakest own creature that flees with low HP.
bool SPELL::castInvisibility(KeeperAI& ai)
{
    // AI row E23
    if(!canCast(ai, SpellType::invisibility, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    const bool slipped = ai.getMind().slip("E23");
    std::vector<Creature*> candidates;
    for(Creature* creature : ownFighters(ai))
    {
        if(!SpellInvisibility::isValidTarget(*creature, seat) || creature->isSpellInvisible())
            continue;

        bool fleesHurt = creature->isActionInList(CreatureActionType::flee) && (hpShare(creature) < aiKey("HealBelow"));
        // The mistake: a fighter that does not flee
        if(slipped ? !creature->isActionInList(CreatureActionType::flee) : fleesHurt)
            candidates.push_back(creature);
    }
    Creature* target = slipped ? anyOf(candidates) : weakest(candidates);
    if(target == nullptr)
        return false;

    ACTS::castSpell(ai, SpellType::invisibility, target);
    return true;
}

//! \brief Infects a visible enemy standing among other enemies and far from the own creatures.
bool SPELL::castPlague(KeeperAI& ai)
{
    // AI row E24
    if(!canCast(ai, SpellType::plague, "SpellManaReserve"))
        return false;

    Seat* seat = ai.getControlledPlayer().getSeat();
    const int enemyRadius = static_cast<int>(aiKey("PlagueEnemyRadius"));
    const int ownRadius = static_cast<int>(aiKey("PlagueOwnClearRadius"));
    const int minEnemies = static_cast<int>(aiKey("PlagueMinEnemies"));
    std::vector<Creature*> enemies = visibleEnemies(ai);
    std::vector<Creature*> valid;
    for(Creature* creature : enemies)
    {
        if(SpellPlague::isValidTarget(*creature, seat))
            valid.push_back(creature);
    }
    if(valid.empty())
        return false;

    Creature* target = nullptr;
    if(ai.getMind().slip("E24"))
        target = anyOf(valid);
    else
    {
        std::vector<Creature*> own = ai.getGameMap().getCreaturesBySeat(seat);
        for(Creature* creature : valid)
        {
            int others = 0;
            for(Creature* other : enemies)
            {
                if((other != creature) && withinTiles(creature, other, enemyRadius))
                    ++others;
            }
            if(others < minEnemies)
                continue;

            bool ownNear = false;
            for(Creature* mate : own)
                ownNear = ownNear || (mate->isAlive() && mate->getIsOnMap() && withinTiles(creature, mate, ownRadius));
            if(ownNear)
                continue;

            target = creature;
            break;
        }
    }
    if(target == nullptr)
        return false;

    ACTS::castSpell(ai, SpellType::plague, target);
    return true;
}

//! \brief Breaks the enemy wall that blocks the tunnel towards the attacked enemy and marks it for digging.
bool SPELL::castBreakWall(KeeperAI& ai)
{
    // AI row E25
    WAR::WarState& war = ai.getWarState();
    if((war.tunnel != WAR::WarState::tunnelDigging) || (war.tunnelTarget == nullptr))
        return false;

    if(!canCast(ai, SpellType::breakWall, "SpellManaReserve"))
        return false;

    GameMap& map = ai.getGameMap();
    Seat* seat = ai.getControlledPlayer().getSeat();
    Creature* worker = map.getWorkerForPathFinding(seat);
    Tile* heart = nullptr;
    for(Room* room : map.getRoomsByTypeAndSeat(RoomType::dungeonTemple, seat))
    {
        heart = static_cast<RoomDungeonTemple*>(room)->getHeartTile();
        if(heart != nullptr)
            break;
    }
    if((worker == nullptr) || (heart == nullptr))
        return false;

    // The blocking wall: a visible enemy claimed wall next to ground the workers reach from the heart, the one nearest
    // to the tunnel target
    Tile* wall = nullptr;
    int wallDistance = 0;
    for(int x = 0; x < map.getMapSizeX(); ++x)
    {
        for(int y = 0; y < map.getMapSizeY(); ++y)
        {
            Tile* tile = map.getTile(x, y);
            if((tile == nullptr) || !SpellBreakWall::isValidWall(*tile, seat))
                continue;

            const std::vector<Seat*>& seeing = tile->getSeatsWithVision();
            if(std::find(seeing.begin(), seeing.end(), seat) == seeing.end())
                continue;

            const int dx = x - war.tunnelTarget->getX();
            const int dy = y - war.tunnelTarget->getY();
            const int distance = dx * dx + dy * dy;
            if((wall != nullptr) && (distance >= wallDistance))
                continue;

            bool reached = false;
            for(Tile* neighbor : tile->getAllNeighbors())
                reached = reached || (!neighbor->isFullTile() && map.pathExists(worker, heart, neighbor));
            if(!reached)
                continue;

            wall = tile;
            wallDistance = distance;
        }
    }
    if(wall == nullptr)
        return false;

    // The mistake: the AI does not think of the spell and its workers stand before the wall
    if(ai.getMind().slip("E25"))
        return false;

    ACTS::castSpell(ai, SpellType::breakWall, wall);
    std::vector<Tile*> dig(1, wall);
    ACTS::markDig(ai, dig, true);
    return true;
}

//! \brief Reveals the claimed tiles of the attacked keeper when its heart was never seen.
bool SPELL::castRevealEnemy(KeeperAI& ai, Seat* enemy)
{
    // AI row E26
    if((enemy == nullptr) || !canCast(ai, SpellType::revealEnemy, "SpellManaReserve"))
        return false;

    GameMap& map = ai.getGameMap();
    Seat* seat = ai.getControlledPlayer().getSeat();
    Tile* enemyHeart = nullptr;
    for(Room* room : map.getRoomsByTypeAndSeat(RoomType::dungeonTemple, enemy))
    {
        enemyHeart = static_cast<RoomDungeonTemple*>(room)->getHeartTile();
        if(enemyHeart != nullptr)
            break;
    }
    AiKnowledge knowledge(map, seat);
    if((enemyHeart == nullptr) || knowledge.isKnown(enemyHeart))
        return false;

    // The mistake: the AI attacks blind
    if(ai.getMind().slip("E26"))
        return false;

    for(Tile* tile : SpellRevealEnemy::getClaimedTiles(&map, enemy))
    {
        const std::vector<Seat*>& seeing = tile->getSeatsWithVision();
        if(std::find(seeing.begin(), seeing.end(), seat) == seeing.end())
            continue;

        ACTS::castSpell(ai, SpellType::revealEnemy, tile);
        return true;
    }
    return false;
}

//! \brief Runs the decisions of rows E21 to E25 at each look.
void SPELL::spellLook(KeeperAI& ai)
{
    castCurse(ai);
    castBlessing(ai);
    castInvisibility(ai);
    castPlague(ai);
    castBreakWall(ai);
}

//! \brief Decides whether to summon a champion at the heart, on launch, or in a trivial fight.
bool SPELL::castChampion(KeeperAI& ai, Tile* tile, bool heartOrLaunch)
{
    // AI row E20
    const bool mistaken = ai.getMind().slip("E20");
    if((tile == nullptr) || !SkillManager::isSpellAvailable(SpellType::summonChampion, ai.getControlledPlayer().getSeat()))
        return false;

    Player& player = ai.getControlledPlayer();
    if((player.getSpellCooldownTurns(SpellType::summonChampion) > 0) ||
       SpellSummonChampion::hasChampion(&ai.getGameMap(), player.getSeat()))
    {
        return false;
    }

    // The mana for the price and the first seconds of the upkeep after the free period
    ConfigManager& config = ConfigManager::getSingleton();
    double needed = spellPrice(SpellType::summonChampion) +
                    config.getSpellConfigDouble("SummonChampionDrainPerSecond") * aiKey("ChampionExtraSeconds");
    if(player.getSeat()->getMana() < needed)
        return false;

    // The mistake: the champion is summoned at any fight, also a trivial one
    if(!heartOrLaunch && !mistaken)
        return false;

    ACTS::castSpell(ai, SpellType::summonChampion, tile);
    return true;
}
