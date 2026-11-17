#include "rooms/RoomInfirmary.h"

#include "entities/InfirmaryShamanEntity.h"
#include "entities/Creature.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "gamemap/RoomObjectNavigation.h"
#include "rooms/InfirmaryShamanWalk.h"

#include <cstdlib>
#include <iomanip>
#include <istream>
#include <limits>
#include <ostream>
#include <set>

//! \brief Creates one harmless figure at the saved position or at the free standing point of the room's instrument
//! table tile, never inside the table (INGAME-QS-10 K23).
void RoomInfirmary::updateShaman()
{
    if(!getIsOnServerMap())
        return;
    if(mShaman != nullptr)
    {
        mShaman->setRoomName(getName());
        mShaman->setRoomOwner(getSeat());
        return;
    }
    Tile* tile = getShamanSpawnTile();
    if(tile == nullptr)
        return;
    mShaman = new InfirmaryShamanEntity(getGameMap(), getName());
    mShaman->setRoomOwner(getSeat());
    mShaman->addToGameMap();
    mShaman->createMesh();
    Ogre::Vector2 position(static_cast<Ogre::Real>(tile->getX()), static_cast<Ogre::Real>(tile->getY()));
    if(mHasLoadedShamanPosition)
        position = mLoadedShamanPosition;
    else
        InfirmaryShamanWalk::standingPoint(RoomObjectNavigation::collect(*getGameMap(), InfirmaryShamanWalk::WALKING_RADIUS),
            InfirmaryShamanWalk::Cell(tile->getX(), tile->getY()), position);
    mShaman->setPosition(Ogre::Vector3(position.x, position.y, 0.0));
    mShaman->setAnimationState("Idle", true);
    mHasLoadedShamanPosition = false;
}

//! \brief Removes the figure without affecting a creature or its treatment.
void RoomInfirmary::removeShaman()
{
    if(mShaman == nullptr)
        return;
    mShaman->removeFromGameMap();
    mShaman->deleteYourself();
    mShaman = nullptr;
}

//! \brief Plays the freely licensed rattle sound at the active pose.
void RoomInfirmary::playShamanRattle(Tile& tile)
{
    fireRoomSound(tile, "Infirmary/Rattle");
}

//! \brief Retains the figure position using enough digits for a lossless coordinate round-trip.
void RoomInfirmary::exportShamanToStream(std::ostream& stream) const
{
    if(mShaman == nullptr)
        return;
    const std::streamsize precision = stream.precision();
    stream << std::setprecision(std::numeric_limits<Ogre::Real>::max_digits10)
        << "InfirmaryShaman\t" << mShaman->getPosition().x << '\t' << mShaman->getPosition().y << '\n';
    stream.precision(precision);
}

//! \brief Accepts older room records without a figure and leaves following cot tags unread.
bool RoomInfirmary::importShamanFromStream(std::istream& stream)
{
    const std::istream::pos_type position = stream.tellg();
    std::string tag;
    if(!(stream >> tag) || tag != "InfirmaryShaman")
    {
        stream.clear();
        stream.seekg(position);
        return true;
    }
    if(!(stream >> mLoadedShamanPosition.x >> mLoadedShamanPosition.y))
        return false;
    mHasLoadedShamanPosition = true;
    return true;
}

//! \brief Offers each cot once by the free floor tile beside it, plus the instrument table; the shaman stands beside a
//! cot and never on it (INGAME-QS-10 K23).
std::vector<Tile*> RoomInfirmary::getShamanWalkTargets() const
{
    std::set<InfirmaryShamanWalk::Cell> floor;
    std::set<InfirmaryShamanWalk::Cell> cots;
    std::set<InfirmaryShamanWalk::Cell> accessories;
    for(Tile* tile : mCoveredTiles)
        floor.insert(InfirmaryShamanWalk::Cell(tile->getX(), tile->getY()));
    for(Tile* tile : getCotTiles())
        cots.insert(InfirmaryShamanWalk::Cell(tile->getX(), tile->getY()));
    for(Tile* tile : mAccessoryTiles)
        accessories.insert(InfirmaryShamanWalk::Cell(tile->getX(), tile->getY()));
    std::vector<Tile*> targets;
    for(const std::pair<const size_t, CotInfo>& entry : mCots)
    {
        std::vector<InfirmaryShamanWalk::Cell> cot;
        for(Tile* tile : entry.second.tiles)
            cot.push_back(InfirmaryShamanWalk::Cell(tile->getX(), tile->getY()));
        InfirmaryShamanWalk::Cell beside;
        if(!InfirmaryShamanWalk::besideCot(cot, floor, cots, accessories, beside))
            continue;
        Tile* target = getGameMap()->getTile(beside.first, beside.second);
        if(target != nullptr)
            targets.push_back(target);
    }
    if(mInstrumentTable != nullptr)
        targets.push_back(mInstrumentTable);
    return targets;
}

//! \brief A pose is played on a tile that touches, also diagonally, a tile of a cot with an admitted patient.
bool RoomInfirmary::isBesidePatient(const Tile& tile) const
{
    for(const std::pair<const size_t, PatientInfo>& entry : mPatients)
    {
        if(entry.second.creature == nullptr)
            continue;
        std::map<size_t, CotInfo>::const_iterator cot = mCots.find(entry.first);
        if(cot == mCots.end())
            continue;
        for(Tile* cotTile : cot->second.tiles)
            if(std::abs(cotTile->getX() - tile.getX()) <= 1 && std::abs(cotTile->getY() - tile.getY()) <= 1)
                return true;
    }
    return false;
}
