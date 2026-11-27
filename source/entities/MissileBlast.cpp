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

#include "entities/MissileBlast.h"

#include "entities/Creature.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "network/ODPacket.h"
#include "utils/LogManager.h"

#include <iostream>
#include <vector>

//! \brief The smallest squared horizontal distance to the target that still gives a usable direction
static const float MIN_TARGET_SQUARED_LENGTH = 0.0001f;

MissileBlast::MissileBlast(GameMap* gameMap, Seat* seat, const std::string& senderName, const std::string& meshName,
        const std::string& particleScript, const Ogre::Vector3& direction, double speed, double physicalDamage, double magicalDamage,
        double elementDamage, GameEntity* entityTarget, bool damageAllies, bool koEnemyCreature, bool notifyPlayerIfHit,
        double blastRadius, bool homing) :
    MissileOneHit(gameMap, seat, senderName, meshName, particleScript, direction, speed, physicalDamage, magicalDamage,
        elementDamage, entityTarget, damageAllies, koEnemyCreature, notifyPlayerIfHit),
    mBlastRadius(blastRadius),
    mHoming(homing)
{
}

MissileBlast::MissileBlast(GameMap* gameMap) :
    MissileOneHit(gameMap),
    mBlastRadius(0.0),
    mHoming(false)
{
}

bool MissileBlast::wallHitNextDirection(const Ogre::Vector3& actDirection, Tile* tile, Ogre::Vector3& nextDirection)
{
    // The missile explodes against walls
    if(mBlastRadius > 0.0)
        explode(tile);

    return false;
}

bool MissileBlast::hitCreature(Tile* tile, GameEntity* entity)
{
    if(mBlastRadius <= 0.0)
        return MissileOneHit::hitCreature(tile, entity);

    explode(tile);
    return false;
}

void MissileBlast::hitTargetEntity(Tile* tile, GameEntity* entityTarget)
{
    if(mBlastRadius <= 0.0)
    {
        MissileOneHit::hitTargetEntity(tile, entityTarget);
        return;
    }

    // Creatures are hurt by the explosion. Other targets (buildings, doors) are hit directly
    if(entityTarget->getObjectType() != GameEntityType::creature)
        MissileOneHit::hitTargetEntity(tile, entityTarget);

    explode(tile);
}

void MissileBlast::updateDirection()
{
    if(!mHoming)
        return;

    GameEntity* target = getEntityTarget();
    if(target == nullptr)
        return;

    Ogre::Vector3 direction = target->getPosition() - getPosition();
    direction.z = 0.0f;
    if(direction.squaredLength() < MIN_TARGET_SQUARED_LENGTH)
        return;

    direction.normalise();
    setDirection(direction);
}

void MissileBlast::explode(Tile* tile)
{
    if(tile == nullptr)
        return;

    const double radiusSquared = mBlastRadius * mBlastRadius;
    uint32_t hits = 0;
    // We copy the list as dying creatures might be removed from the map
    std::vector<Creature*> creatures = getGameMap()->getCreatures();
    for(Creature* creature : creatures)
    {
        if(!creature->isAlive())
            continue;

        if((getSeat() != nullptr) && creature->getSeat()->isAlliedSeat(getSeat()))
            continue;

        Tile* creatureTile = creature->getPositionTile();
        if(creatureTile == nullptr)
            continue;

        double dx = static_cast<double>(creatureTile->getX() - tile->getX());
        double dy = static_cast<double>(creatureTile->getY() - tile->getY());
        if(((dx * dx) + (dy * dy)) > radiusSquared)
            continue;

        hurt(creatureTile, creature);
        ++hits;
        if(mNotifyPlayerIfHit)
            creature->notifyFightPlayer(creatureTile);
    }

    // COOLDOWN_PER_HIT of the shooter: every enemy hit takes turns off the cooldown of the skill that launched it
    if(hits == 0 || mCooldownSkillId.empty())
        return;

    Creature* shooter = getGameMap()->getCreature(mShooterName);
    if(shooter == nullptr)
        return;

    shooter->cutTreeSkillCooldown(mCooldownSkillId,
        static_cast<double>(hits) * shooter->getSkillPropertyValue("COOLDOWN_PER_HIT", 0, 0.0));
}

//! \brief Reads a blast missile from a saved line; a line that cannot be read gives no object.
MissileBlast* MissileBlast::getMissileBlastFromStream(GameMap* gameMap, std::istream& is)
{
    MissileBlast* obj = new MissileBlast(gameMap);
    if(!obj->importFromStream(is))
    {
        OD_LOG_ERR("Invalid blast missile record");
        delete obj;
        return nullptr;
    }
    return obj;
}

MissileBlast* MissileBlast::getMissileBlastFromPacket(GameMap* gameMap, ODPacket& is)
{
    MissileBlast* obj = new MissileBlast(gameMap);
    obj->importFromPacket(is);
    return obj;
}

void MissileBlast::exportToStream(std::ostream& os) const
{
    MissileOneHit::exportToStream(os);
    os << "\t" << mBlastRadius;
    os << "\t" << mHoming;
    if(!mCooldownSkillId.empty())
        os << "\tCooldownSkill\t" << mCooldownSkillId;
}

//! \brief Reads the missile; the skill whose cooldown the hits shorten is optional (saves from before it have none).
bool MissileBlast::importFromStream(std::istream& is)
{
    if(!MissileOneHit::importFromStream(is))
        return false;
    if(!(is >> mBlastRadius))
        return false;
    if(!(is >> mHoming))
        return false;

    const std::streampos skillPosition = is.tellg();
    std::string marker;
    if((is >> marker) && (marker == "CooldownSkill"))
    {
        if(!(is >> mCooldownSkillId))
            return false;
    }
    else
    {
        is.clear();
        is.seekg(skillPosition);
    }

    return true;
}
