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
#include "entities/CreatureDefinition.h"
#include "entities/GameEntity.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "network/ODPacket.h"
#include "render/RenderManager.h"
#include "utils/LogManager.h"
#include "ODApplication.h"

#include <algorithm>
#include <iostream>

// The Explosion skill puts this particle script on every creature its blast hits
const std::string MissileBomb::IMPACT_PARTICLE_SCRIPT = "SpellCreatureExplosion";
const std::string MissileBomb::HAND_BONE = "Weapon_R";
const double MissileBomb::MIN_FLIGHT_SPEED = 0.5;
const uint32_t MissileBomb::MAX_FLIGHT_TURNS = 2;
const double MissileBomb::WIND_UP_TURNS = 0.35;
const double MissileBomb::CLIENT_FLIGHT_TURNS = 0.45;
const double MissileBomb::ARC_HEIGHT = 0.3;
const double MissileBomb::ARC_HEIGHT_PER_TILE = 0.06;

//! \brief Height of the bomb when no hand bone or target position is known (the height of the other missiles)
static const Ogre::Real FALLBACK_HEIGHT = 0.3f;

std::vector<MissileBomb*> MissileBomb::sFlyingBombs;

MissileBomb::MissileBomb(GameMap* gameMap, Seat* seat, const std::string& throwerName, const std::string& meshName,
        const std::string& particleScript, const std::string& hiddenMaterial, const Ogre::Vector3& direction,
        double speed, GameEntity* target, Tile* targetTile, const std::vector<std::string>& targetNames) :
    MissileObject(gameMap, seat, throwerName, meshName, direction, speed, target, false, false),
    mThrowerName(throwerName),
    mTargetNames(targetNames),
    mHiddenMaterial(hiddenMaterial),
    mTargetX(targetTile == nullptr ? -1 : targetTile->getX()),
    mTargetY(targetTile == nullptr ? -1 : targetTile->getY()),
    mTurnsLeft(MAX_FLIGHT_TURNS),
    mThrowPhase(ThrowPhase::windUp),
    mThrowSeconds(0.0),
    mHandSparks(nullptr),
    mReleasePosition(Ogre::Vector3::ZERO),
    mLandingPosition(Ogre::Vector3::ZERO)
{
    addFlightParticle(particleScript);
}

MissileBomb::MissileBomb(GameMap* gameMap) :
    MissileObject(gameMap),
    mTargetX(-1),
    mTargetY(-1),
    mTurnsLeft(MAX_FLIGHT_TURNS),
    mThrowPhase(ThrowPhase::windUp),
    mThrowSeconds(0.0),
    mHandSparks(nullptr),
    mReleasePosition(Ogre::Vector3::ZERO),
    mLandingPosition(Ogre::Vector3::ZERO)
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

//! \brief Wind-up for WIND_UP_TURNS, then the flight for CLIENT_FLIGHT_TURNS, then landed.
MissileBomb::ThrowPhase MissileBomb::phaseAt(double seconds, double turnSeconds)
{
    if(seconds < WIND_UP_TURNS * turnSeconds)
        return ThrowPhase::windUp;
    if(seconds < (WIND_UP_TURNS + CLIENT_FLIGHT_TURNS) * turnSeconds)
        return ThrowPhase::flight;
    return ThrowPhase::landed;
}

double MissileBomb::flightFraction(double seconds, double turnSeconds)
{
    const double fraction = (seconds - (WIND_UP_TURNS * turnSeconds)) / (CLIENT_FLIGHT_TURNS * turnSeconds);
    return std::max(0.0, std::min(1.0, fraction));
}

//! \brief A parabola that is 0 at the hand and at the target and highest in the middle of the flight.
double MissileBomb::arcHeight(double fraction, double distance)
{
    return 4.0 * fraction * (1.0 - fraction) * (ARC_HEIGHT + (ARC_HEIGHT_PER_TILE * distance));
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

void MissileBomb::update(Ogre::Real timeSinceLastFrame)
{
    // The server moves the bomb along its path like every missile; the clients show the throw on their own
    if(getIsOnServerMap())
    {
        MissileObject::update(timeSinceLastFrame);
        return;
    }

    if(mThrowPhase == ThrowPhase::landed)
        return;

    mThrowSeconds += static_cast<double>(timeSinceLastFrame) * getGameMap()->getGameSpeedFactor();
    const double turnSeconds = 1.0 / ODApplication::turnsPerSecond;
    const ThrowPhase phase = phaseAt(mThrowSeconds, turnSeconds);
    if((mThrowPhase == ThrowPhase::windUp) && (phase != ThrowPhase::windUp))
        release();
    if(phase == ThrowPhase::landed)
    {
        land();
        return;
    }
    if(mThrowPhase != ThrowPhase::flight)
        return;

    const double fraction = flightFraction(mThrowSeconds, turnSeconds);
    const double distance = static_cast<double>(mReleasePosition.distance(mLandingPosition));
    Ogre::Vector3 position = mReleasePosition + ((mLandingPosition - mReleasePosition) * static_cast<Ogre::Real>(fraction));
    position.z += static_cast<Ogre::Real>(arcHeight(fraction, distance));
    setPosition(position);
}

bool MissileBomb::holdImpactParticle(const GameEntity& entity, const EntityParticleEffect& effect)
{
    if(effect.mScript != IMPACT_PARTICLE_SCRIPT)
        return false;

    for(MissileBomb* bomb : sFlyingBombs)
    {
        if(bomb->mThrowPhase == ThrowPhase::landed)
            continue;
        if(std::find(bomb->mTargetNames.begin(), bomb->mTargetNames.end(), entity.getName()) == bomb->mTargetNames.end())
            continue;

        bomb->mHeldEffects.push_back(std::make_pair(entity.getName(), effect.mName));
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
    mThrowPhase = ThrowPhase::windUp;
    mThrowSeconds = 0.0;
    // The bomb is still in the hand: the missile is not seen before the release
    RenderManager::getSingleton().rrSetEntityNodeVisible(*this, false);

    Creature* thrower = getGameMap()->getCreature(mThrowerName);
    if((thrower == nullptr) || mEntityParticleEffects.empty())
        return;

    // The fuse of the bomb in the hand sparks during the wind-up
    mHandSparks = RenderManager::getSingleton().rrAttachCreatureBoneParticle(*thrower, HAND_BONE,
        nextParticleSystemsName(), mEntityParticleEffects.front()->mScript);
}

void MissileBomb::removeHandSparks()
{
    if(mHandSparks == nullptr)
        return;

    RenderManager::getSingleton().rrDestroyBoneParticle(mHandSparks);
    mHandSparks = nullptr;
}

void MissileBomb::release()
{
    removeHandSparks();
    mThrowPhase = ThrowPhase::flight;

    Creature* thrower = getGameMap()->getCreature(mThrowerName);
    mReleasePosition = getPosition();
    if(thrower != nullptr)
    {
        mReleasePosition = thrower->getPosition();
        mReleasePosition.z = FALLBACK_HEIGHT;
        RenderManager::getSingleton().rrGetCreatureBonePosition(*thrower, HAND_BONE, *this, mReleasePosition);
        if(!mHiddenMaterial.empty())
            RenderManager::getSingleton().rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, false);
    }

    // The bomb lands where the target stands now, else on the tile of the target at the throw
    Creature* target = mTargetNames.empty() ? nullptr : getGameMap()->getCreature(mTargetNames.front());
    if(target != nullptr)
        mLandingPosition = target->getPosition();
    else
        mLandingPosition = Ogre::Vector3(static_cast<Ogre::Real>(mTargetX), static_cast<Ogre::Real>(mTargetY), 0.0f);
    mLandingPosition.z = FALLBACK_HEIGHT;

    setPosition(mReleasePosition);
    RenderManager::getSingleton().rrSetEntityNodeVisible(*this, true);
}

void MissileBomb::land()
{
    removeHandSparks();
    mThrowPhase = ThrowPhase::landed;

    // The bomb is gone, the explosions of every creature its blast hit show now
    RenderManager::getSingleton().rrSetEntityNodeVisible(*this, false);
    for(const std::pair<std::string, std::string>& held : mHeldEffects)
    {
        Creature* creature = getGameMap()->getCreature(held.first);
        if(creature != nullptr)
            creature->showHeldParticleEffect(held.second);
    }
    mHeldEffects.clear();

    // A new bomb lies in the hand
    Creature* thrower = getGameMap()->getCreature(mThrowerName);
    if((thrower != nullptr) && !mHiddenMaterial.empty())
        RenderManager::getSingleton().rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, true);
}

void MissileBomb::destroyMeshLocal(NodeType nt)
{
    if(!getIsOnServerMap())
    {
        // The bomb left the view or was removed before it landed: the throw ends at once
        if(mThrowPhase != ThrowPhase::landed)
            land();

        std::vector<MissileBomb*>::iterator it = std::find(sFlyingBombs.begin(), sFlyingBombs.end(), this);
        if(it != sFlyingBombs.end())
            sFlyingBombs.erase(it);
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
    os << (mHiddenMaterial.empty() ? "none" : mHiddenMaterial) << "\t";
    os << mTargetX << "\t" << mTargetY << "\t" << mTurnsLeft << "\t";
    os << mTargetNames.size();
    for(const std::string& name : mTargetNames)
        os << "\t" << name;
    os << "\t" << mEntityParticleEffects.size();
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
    if(!(is >> mThrowerName >> mHiddenMaterial))
        return false;
    if(mThrowerName == "none")
        mThrowerName.clear();
    if(mHiddenMaterial == "none")
        mHiddenMaterial.clear();
    if(!(is >> mTargetX >> mTargetY >> mTurnsLeft))
        return false;

    uint32_t nbTargets;
    if(!(is >> nbTargets))
        return false;
    mTargetNames.clear();
    while(nbTargets > 0)
    {
        --nbTargets;
        std::string name;
        if(!(is >> name))
            return false;
        mTargetNames.push_back(name);
    }

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
    os << mHiddenMaterial;
    os << mTargetX << mTargetY;
    uint32_t nbTargets = static_cast<uint32_t>(mTargetNames.size());
    os << nbTargets;
    for(const std::string& name : mTargetNames)
        os << name;
}

void MissileBomb::importFromPacket(ODPacket& is)
{
    MissileObject::importFromPacket(is);
    OD_ASSERT_TRUE(is >> mThrowerName);
    OD_ASSERT_TRUE(is >> mHiddenMaterial);
    OD_ASSERT_TRUE(is >> mTargetX >> mTargetY);
    uint32_t nbTargets = 0;
    OD_ASSERT_TRUE(is >> nbTargets);
    mTargetNames.clear();
    while(nbTargets > 0)
    {
        --nbTargets;
        std::string name;
        OD_ASSERT_TRUE(is >> name);
        mTargetNames.push_back(name);
    }
}
