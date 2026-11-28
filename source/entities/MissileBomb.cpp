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

#include "entities/MissileBomb.h"

#include "entities/Creature.h"
#include "entities/GameEntity.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "network/ODPacket.h"
#include "render/RenderManager.h"
#include "utils/LogManager.h"

#include <algorithm>
#include <iostream>

// The Explosion skill puts this particle script on every creature its blast hits
const std::string MissileBomb::IMPACT_PARTICLE_SCRIPT = "SpellCreatureExplosion";
const double MissileBomb::MIN_FLIGHT_SPEED = 0.5;
const uint32_t MissileBomb::MAX_FLIGHT_TURNS = 2;

std::vector<MissileBomb*> MissileBomb::sFlyingBombs;

MissileBomb::MissileBomb(GameMap* gameMap, Seat* seat, const std::string& throwerName, const std::string& meshName,
        const std::string& particleScript, const std::string& hiddenMaterial, const Ogre::Vector3& direction,
        double speed, GameEntity* target, Tile* targetTile) :
    MissileObject(gameMap, seat, throwerName, meshName, direction, speed, target, false, false),
    mThrowerName(throwerName),
    mTargetName(target == nullptr ? std::string() : target->getName()),
    mHiddenMaterial(hiddenMaterial),
    mTargetX(targetTile == nullptr ? -1 : targetTile->getX()),
    mTargetY(targetTile == nullptr ? -1 : targetTile->getY()),
    mTurnsLeft(MAX_FLIGHT_TURNS)
{
    addFlightParticle(particleScript);
}

MissileBomb::MissileBomb(GameMap* gameMap) :
    MissileObject(gameMap),
    mTargetX(-1),
    mTargetY(-1),
    mTurnsLeft(MAX_FLIGHT_TURNS)
{
}

MissileBomb::~MissileBomb()
{
    std::vector<MissileBomb*>::iterator it = std::find(sFlyingBombs.begin(), sFlyingBombs.end(), this);
    if(it != sFlyingBombs.end())
        sFlyingBombs.erase(it);
}

void MissileBomb::addFlightParticle(const std::string& particleScript)
{
    if(particleScript.empty())
        return;

    EntityParticleEffect* effect = new EntityParticleEffect(nextParticleSystemsName(), particleScript, -1);
    mEntityParticleEffects.push_back(effect);
}

bool MissileBomb::stopsOnTile(Tile* tile)
{
    return (tile->getX() == mTargetX) && (tile->getY() == mTargetY);
}

//! \brief The distance itself, so that the whole flight takes the turn of the throw, and at least MIN_FLIGHT_SPEED.
double MissileBomb::flightSpeed(double distance)
{
    return std::max(distance, MIN_FLIGHT_SPEED);
}

void MissileBomb::updateDirection()
{
    if(mTurnsLeft == 0)
    {
        stopMissile();
        return;
    }
    --mTurnsLeft;
}

bool MissileBomb::holdImpactParticle(const GameEntity& entity, const EntityParticleEffect& effect)
{
    if(effect.mScript != IMPACT_PARTICLE_SCRIPT)
        return false;

    for(MissileBomb* bomb : sFlyingBombs)
    {
        if(bomb->mTargetName.empty() || (bomb->mTargetName != entity.getName()))
            continue;

        bomb->mHeldEffects.push_back(effect.mName);
        return true;
    }
    return false;
}

void MissileBomb::createMeshLocal(NodeType nt)
{
    MissileObject::createMeshLocal(nt);

    if(getIsOnServerMap())
        return;

    sFlyingBombs.push_back(this);
    if(mHiddenMaterial.empty())
        return;

    Creature* thrower = getGameMap()->getCreature(mThrowerName);
    if(thrower != nullptr)
        RenderManager::getSingleton().rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, false);
}

void MissileBomb::destroyMeshLocal(NodeType nt)
{
    if(!getIsOnServerMap())
    {
        std::vector<MissileBomb*>::iterator it = std::find(sFlyingBombs.begin(), sFlyingBombs.end(), this);
        if(it != sFlyingBombs.end())
            sFlyingBombs.erase(it);

        if(!mHiddenMaterial.empty())
        {
            Creature* thrower = getGameMap()->getCreature(mThrowerName);
            if(thrower != nullptr)
                RenderManager::getSingleton().rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, true);
        }

        // The bomb landed (or left the view): the explosion of its target shows now
        Creature* target = getGameMap()->getCreature(mTargetName);
        if(target != nullptr)
        {
            for(const std::string& effectName : mHeldEffects)
                target->showHeldParticleEffect(effectName);
        }
        mHeldEffects.clear();
    }

    MissileObject::destroyMeshLocal(nt);
}

//! \brief Reads a bomb from a saved line; a line that cannot be read gives no object.
MissileBomb* MissileBomb::getMissileBombFromStream(GameMap* gameMap, std::istream& is)
{
    MissileBomb* obj = new MissileBomb(gameMap);
    if(!obj->importFromStream(is))
    {
        OD_LOG_ERR("Invalid bomb missile record");
        delete obj;
        return nullptr;
    }
    return obj;
}

MissileBomb* MissileBomb::getMissileBombFromPacket(GameMap* gameMap, ODPacket& is)
{
    MissileBomb* obj = new MissileBomb(gameMap);
    obj->importFromPacket(is);
    return obj;
}

void MissileBomb::exportToStream(std::ostream& os) const
{
    MissileObject::exportToStream(os);
    // The marker keeps the names apart from the optional ShotOrigin field of MissileObject (it starts with S)
    os << "Bomb\t";
    os << (mThrowerName.empty() ? "none" : mThrowerName) << "\t";
    os << (mTargetName.empty() ? "none" : mTargetName) << "\t";
    os << (mHiddenMaterial.empty() ? "none" : mHiddenMaterial) << "\t";
    os << mTargetX << "\t" << mTargetY << "\t" << mTurnsLeft << "\t";
    os << mEntityParticleEffects.size();
    for(EntityParticleEffect* effect : mEntityParticleEffects)
        os << "\t" << effect->mScript;
}

bool MissileBomb::importFromStream(std::istream& is)
{
    if(!MissileObject::importFromStream(is))
        return false;
    std::string marker;
    if(!(is >> marker) || (marker != "Bomb"))
        return false;
    if(!(is >> mThrowerName >> mTargetName >> mHiddenMaterial))
        return false;
    if(mThrowerName == "none")
        mThrowerName.clear();
    if(mTargetName == "none")
        mTargetName.clear();
    if(mHiddenMaterial == "none")
        mHiddenMaterial.clear();
    if(!(is >> mTargetX >> mTargetY >> mTurnsLeft))
        return false;

    uint32_t nbEffects;
    if(!(is >> nbEffects))
        return false;
    while(nbEffects > 0)
    {
        --nbEffects;
        std::string effectScript;
        if(!(is >> effectScript))
            return false;
        addFlightParticle(effectScript);
    }
    return true;
}

void MissileBomb::exportToPacket(ODPacket& os, const Seat* seat) const
{
    MissileObject::exportToPacket(os, seat);
    os << mThrowerName;
    os << mTargetName;
    os << mHiddenMaterial;
}

void MissileBomb::importFromPacket(ODPacket& is)
{
    MissileObject::importFromPacket(is);
    OD_ASSERT_TRUE(is >> mThrowerName);
    OD_ASSERT_TRUE(is >> mTargetName);
    OD_ASSERT_TRUE(is >> mHiddenMaterial);
}
