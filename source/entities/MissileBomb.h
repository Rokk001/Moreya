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

#ifndef MISSILEBOMB_H
#define MISSILEBOMB_H

#include "entities/MissileObject.h"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>
#include <iosfwd>

namespace Ogre
{
class ParticleSystem;
}

class EntityParticleEffect;
class GameMap;
class Tile;
class ODPacket;

//! \brief The bomb a creature type with the key ThrownBomb throws when it uses its Explosion skill. Look only: it has
//! no damage, no hit roll and no effect on anything it passes. The explosion itself hits at the throw, in the same
//! turn as without the bomb.
//! On the clients the throw plays in three steps within the turn of the throw: the fuse of the bomb in the thrower's
//! hand sparks (wind-up), the bomb leaves the hand and flies with its sparks to the target (flight), it lands: the
//! explosions of every creature its blast hit show now and a new bomb lies in the hand.
class MissileBomb: public MissileObject
{
public:
    //! \brief Particle script of the explosion effect that is shown on the creatures hit when the bomb lands
    static const std::string IMPACT_PARTICLE_SCRIPT;
    //! \brief Bone of the thrower the bomb is held at (the hand bone the bomb part of the model is bound to)
    static const std::string HAND_BONE;
    //! \brief Speed in tiles per turn for a target on the thrower's own tile or right next to it
    static const double MIN_FLIGHT_SPEED;
    //! \brief Turns after which a bomb that did not land on the server (target gone, path blocked) is removed
    static const uint32_t MAX_FLIGHT_TURNS;
    //! \brief Client: part of a turn the fuse sparks in the hand before the bomb leaves it
    static const double WIND_UP_TURNS;
    //! \brief Client: part of a turn the bomb flies from the hand to the target. With WIND_UP_TURNS below one turn:
    //! the bomb lands before the server removes it at the next turn
    static const double CLIENT_FLIGHT_TURNS;
    //! \brief Client: height of the arc of the flight above the straight line, plus ARC_HEIGHT_PER_TILE per tile
    static const double ARC_HEIGHT;
    //! \brief Client: extra height of the arc per tile of distance
    static const double ARC_HEIGHT_PER_TILE;

    //! \brief Steps of the throw on a client
    enum class ThrowPhase
    {
        windUp,
        flight,
        landed
    };

    //! \brief Creates the bomb on the server side, thrown by throwerName at the creature target standing on
    //! targetTile. targetNames are the creatures the blast hit (the target first), hiddenMaterial names the material
    //! of the bomb part of the thrower's model.
    MissileBomb(GameMap* gameMap, Seat* seat, const std::string& throwerName, const std::string& meshName,
        const std::string& particleScript, const std::string& hiddenMaterial, const Ogre::Vector3& direction,
        double speed, GameEntity* target, Tile* targetTile, const std::vector<std::string>& targetNames);
    //! \brief Creates an empty bomb that is filled by importFromStream or importFromPacket
    MissileBomb(GameMap* gameMap);

    //! \brief Takes the bomb out of the list of flying bombs of the client
    virtual ~MissileBomb();

    //! \brief Returns the type used to identify this missile in saved games and packets.
    virtual MissileObjectType getMissileType() const override
    { return MissileObjectType::skillBomb; }

    //! \brief The bomb stops at a wall without any effect.
    virtual bool wallHitNextDirection(const Ogre::Vector3& actDirection, Tile* tile, Ogre::Vector3& nextDirection) override
    { return false; }

    //! \brief The bomb flies over every creature on its way without touching it.
    virtual bool hitCreature(Tile* tile, GameEntity* entity) override
    { return true; }

    //! \brief The bomb reached its target: nothing happens, the explosion was already applied at the throw.
    virtual void hitTargetEntity(Tile* tile, GameEntity* entityTarget) override
    {}

    //! \brief The bomb lands on the tile of its target, also when the target is gone.
    virtual bool stopsOnTile(Tile* tile) override;

    //! \brief Server: moves the bomb like every missile. Client: plays wind-up, flight and landing (look only).
    virtual void update(Ogre::Real timeSinceLastFrame) override;

    //! \brief Speed in tiles per turn that makes a bomb cover the given distance in the turn of the throw.
    static double flightSpeed(double distance);

    //! \brief The step of the client throw after the given game seconds since the bomb appeared on the client.
    static ThrowPhase phaseAt(double seconds, double turnSeconds);

    //! \brief Part of the client flight done after the given game seconds since the bomb appeared (0 to 1).
    static double flightFraction(double seconds, double turnSeconds);

    //! \brief Height of the flight arc above the straight line at the given part of the flight over the distance.
    static double arcHeight(double fraction, double distance);

    //! \brief Client side: called when the entity gets a new particle effect. If a bomb that has not landed yet hit
    //! the entity with its blast and the effect is the explosion, the bomb keeps the effect name and returns true:
    //! the caller does not show it now, the bomb shows it when it lands. Returns false otherwise.
    static bool holdImpactParticle(const GameEntity& entity, const EntityParticleEffect& effect);

    //! \brief Name of the creature that threw the bomb
    const std::string& getThrowerName() const
    { return mThrowerName; }

    //! \brief Names of the creatures the blast hit, the target first
    const std::vector<std::string>& getTargetNames() const
    { return mTargetNames; }

    //! \brief Material of the bomb part of the thrower's model, hidden while the bomb flies (empty for none)
    const std::string& getHiddenMaterial() const
    { return mHiddenMaterial; }

    //! \brief Creates a bomb from the saved game stream
    static MissileBomb* getMissileBombFromStream(GameMap* gameMap, std::istream& is);
    //! \brief Creates a bomb from the network packet
    static MissileBomb* getMissileBombFromPacket(GameMap* gameMap, ODPacket& is);

protected:
    //! \brief Counts the turns of the flight and stops the bomb when MAX_FLIGHT_TURNS are over.
    virtual void updateDirection() override;

    //! \brief Client side: starts the wind-up, the fuse of the bomb in the thrower's hand sparks.
    virtual void createMeshLocal(NodeType nt = NodeType::MTILES_NODE) override;
    //! \brief Client side: ends the throw at once if it did not land yet (the bomb left the view or was removed).
    virtual void destroyMeshLocal(NodeType nt = NodeType::MTILES_NODE) override;

    //! \brief Writes the bomb (names, target tile, turns left and its particle scripts) to the stream.
    void exportToStream(std::ostream& os) const override;
    //! \brief Reads the bomb from the stream. Returns false if the stream is malformed.
    bool importFromStream(std::istream& is) override;
    //! \brief Sends the thrower, the hidden material, the target tile and the creatures hit with the missile.
    void exportToPacket(ODPacket& os, const Seat* seat) const override;
    //! \brief Reads what exportToPacket sent.
    void importFromPacket(ODPacket& is) override;

private:
    //! \brief Adds the particle effect that the bomb carries in flight
    void addFlightParticle(const std::string& particleScript);

    //! \brief Client: removes the sparks of the fuse in the hand
    void removeHandSparks();

    //! \brief Client: the bomb leaves the hand. The hand bomb is hidden and the bomb starts its flight at the hand
    void release();

    //! \brief Client: the bomb lands. The held explosions show, the bomb mesh is hidden and the hand bomb is shown
    void land();

    std::string mThrowerName;
    //! \brief The creatures the blast hit, the target first
    std::vector<std::string> mTargetNames;
    std::string mHiddenMaterial;
    //! \brief Tile the bomb lands on (the tile of the target at the throw)
    int32_t mTargetX;
    int32_t mTargetY;
    //! \brief Turns of flight left before the bomb is removed anyway
    uint32_t mTurnsLeft;

    //! \brief Client: step of the throw and game seconds since the bomb appeared
    ThrowPhase mThrowPhase;
    double mThrowSeconds;
    //! \brief Client: the sparks of the fuse in the hand during the wind-up, nullptr when there are none
    Ogre::ParticleSystem* mHandSparks;
    //! \brief Client: start and end of the flight
    Ogre::Vector3 mReleasePosition;
    Ogre::Vector3 mLandingPosition;
    //! \brief Client: explosion particle effects (entity name, effect name) held until the bomb lands
    std::vector<std::pair<std::string, std::string>> mHeldEffects;
    //! \brief Client side: the bombs whose mesh exists, so that the explosions of their blast can be held
    static std::vector<MissileBomb*> sFlyingBombs;
};

#endif // MISSILEBOMB_H
