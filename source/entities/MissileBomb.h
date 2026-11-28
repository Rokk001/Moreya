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
#include <vector>
#include <iosfwd>

class EntityParticleEffect;
class GameMap;
class Tile;
class ODPacket;

//! \brief The bomb a creature type with the key ThrownBomb throws when it uses its Explosion skill. Look only: it has
//! no damage, no hit roll and no effect on anything it passes. The explosion itself hits at the throw, in the same
//! turn as without the bomb. On the clients the bomb part of the thrower's model is hidden while the bomb flies, and
//! the explosion particle of the target is shown when the bomb lands.
class MissileBomb: public MissileObject
{
public:
    //! \brief Particle script of the explosion effect that is shown on the target when the bomb lands
    static const std::string IMPACT_PARTICLE_SCRIPT;
    //! \brief Speed in tiles per turn for a target on the thrower's own tile or right next to it
    static const double MIN_FLIGHT_SPEED;
    //! \brief Turns after which a bomb that did not land (target gone, path blocked) is removed
    static const uint32_t MAX_FLIGHT_TURNS;

    //! \brief Creates the bomb on the server side, thrown by throwerName at the creature target standing on
    //! targetTile. hiddenMaterial names the material of the bomb part of the thrower's model.
    MissileBomb(GameMap* gameMap, Seat* seat, const std::string& throwerName, const std::string& meshName,
        const std::string& particleScript, const std::string& hiddenMaterial, const Ogre::Vector3& direction,
        double speed, GameEntity* target, Tile* targetTile);
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

    //! \brief Speed in tiles per turn that makes a bomb cover the given distance in the turn of the throw.
    static double flightSpeed(double distance);

    //! \brief Client side: called when the entity gets a new particle effect. If a flying bomb is aimed at the entity
    //! and the effect is the explosion, the bomb keeps the effect name and returns true: the caller does not show it
    //! now, the bomb shows it when it lands. Returns false otherwise.
    static bool holdImpactParticle(const GameEntity& entity, const EntityParticleEffect& effect);

    //! \brief Name of the creature that threw the bomb
    const std::string& getThrowerName() const
    { return mThrowerName; }

    //! \brief Name of the creature the bomb is aimed at
    const std::string& getTargetName() const
    { return mTargetName; }

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

    //! \brief Client side: hides the bomb part of the thrower's model while the bomb flies.
    virtual void createMeshLocal(NodeType nt = NodeType::MTILES_NODE) override;
    //! \brief Client side: shows the bomb part of the thrower's model again and the held explosion of the target.
    virtual void destroyMeshLocal(NodeType nt = NodeType::MTILES_NODE) override;

    //! \brief Writes the bomb (names, target tile, turns left and its particle scripts) to the stream.
    void exportToStream(std::ostream& os) const override;
    //! \brief Reads the bomb from the stream. Returns false if the stream is malformed.
    bool importFromStream(std::istream& is) override;
    //! \brief Sends the names of thrower, target and hidden material with the missile.
    void exportToPacket(ODPacket& os, const Seat* seat) const override;
    //! \brief Reads what exportToPacket sent.
    void importFromPacket(ODPacket& is) override;

private:
    //! \brief Adds the particle effect that the bomb carries in flight
    void addFlightParticle(const std::string& particleScript);

    std::string mThrowerName;
    std::string mTargetName;
    std::string mHiddenMaterial;
    //! \brief Tile the bomb lands on (the tile of the target at the throw)
    int32_t mTargetX;
    int32_t mTargetY;
    //! \brief Turns of flight left before the bomb is removed anyway
    uint32_t mTurnsLeft;
    //! \brief Client side: names of the explosion particle effects of the target held until the bomb lands
    std::vector<std::string> mHeldEffects;
    //! \brief Client side: the bombs whose mesh exists, so that the explosion of their target can be held
    static std::vector<MissileBomb*> sFlyingBombs;
};

#endif // MISSILEBOMB_H
