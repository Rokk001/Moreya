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

#include "creatureaction/CreatureActionUseToilet.h"

#include "ODApplication.h"
#include "creatureaction/CreatureActionWalkToTile.h"

#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/DirtPileEntity.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/RoomObjectNavigation.h"
#include "rooms/Room.h"
#include "rooms/RoomToilet.h"
#include "rooms/RoomType.h"
#include "rooms/ToiletLayout.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "utils/MakeUnique.h"
#include "utils/Random.h"

namespace
{
//! \brief Squared distance (tiles) below which a creature counts as standing on the place of its seat.
const float SEAT_REACHED_SQUARED = 0.0025f;
}

CreatureActionUseToilet::CreatureActionUseToilet(Creature& creature, Tile* seatTile) :
    CreatureAction(creature),
    mSeatTile(seatTile),
    mPhase(Phase::approach),
    mTurnsLeft(0),
    mLastTurn(-1),
    mLeaveTried(false),
    mSeatLost(false),
    mStagingPoint(Ogre::Vector2::ZERO)
{
    if(mSeatTile == nullptr)
        return;

    // The seat is reserved at once so that no other creature takes it while this one walks there
    RoomToilet* room = getSeatRoom();
    if((room == nullptr) || !room->reserveTile(mSeatTile, &mCreature))
        mSeatLost = true;
}

CreatureActionUseToilet::~CreatureActionUseToilet()
{
    releaseSeat();
}

std::function<bool()> CreatureActionUseToilet::action() // allowed-lambda: signature required by CreatureAction
{
    return std::bind(&CreatureActionUseToilet::handleUseToilet, this);
}

void CreatureActionUseToilet::interrupt()
{
    releaseSeat();
    // A use that is already over (the creature steps off the seat) is not started again
    if(mPhase != Phase::leave)
        mPhase = Phase::approach;
}

bool CreatureActionUseToilet::isExemptRoomType(const Room* room)
{
    if(room == nullptr)
        return false;

    RoomType type = room->getType();
    return (type == RoomType::treasury) || (type == RoomType::dungeonTemple) || (type == RoomType::temple);
}

RoomToilet* CreatureActionUseToilet::getSeatRoom() const
{
    if(mSeatTile == nullptr)
        return nullptr;

    Room* room = mSeatTile->getCoveringRoom();
    if((room == nullptr) || (room->getType() != RoomType::toilet))
        return nullptr;

    return static_cast<RoomToilet*>(room);
}

void CreatureActionUseToilet::releaseSeat()
{
    RoomToilet* room = getSeatRoom();
    if(room != nullptr)
        room->releaseTile(mSeatTile, &mCreature);
}

void CreatureActionUseToilet::finish()
{
    releaseSeat();
    mCreature.setAnimationState(EntityAnimation::idle_anim, true);
    mCreature.popAction();
}

void CreatureActionUseToilet::startSquat(bool onSeat, const Ogre::Vector2& facing)
{
    mPhase = Phase::squat;
    ConfigManager& config = ConfigManager::getSingleton();
    if(onSeat)
    {
        // Every use lasts its own random time
        const double seconds = ToiletLayout::useSeconds(config.getDirtConfigDouble("ToiletUseSecondsMin"),
            config.getDirtConfigDouble("ToiletUseSecondsMax"), Random::Double(0.0, 1.0));
        mTurnsLeft = ToiletLayout::useTurns(seconds, ODApplication::turnsPerSecond);
    }
    else
        mTurnsLeft = static_cast<int32_t>(config.getDirtConfigDouble("ToiletUseTurns"));
    if(mCreature.isMoving())
        mCreature.clearDestinations(EntityAnimation::relieve_anim, true, false);
    mCreature.setAnimationState(EntityAnimation::relieve_anim, true, Ogre::Vector3(facing.x, facing.y, 0.0f), false);
    mCreature.fireCreatureSound(CreatureSound::Relieve);
}

bool CreatureActionUseToilet::walkOntoSeat(RoomToilet& room)
{
    Ogre::Vector2 place;
    Ogre::Vector2 facing;
    Tile* creatureTile = mCreature.getPositionTile();
    if((creatureTile == nullptr) || !room.getSeatPlace(mSeatTile, place, facing))
        return false;

    GameMap* gameMap = mCreature.getGameMap();
    for(const Ogre::Vector2& staging : room.getSeatStagingPoints(mCreature, mSeatTile))
    {
        std::vector<Ogre::Vector2> path;
        Tile* stagingTile = gameMap->getTile(Helper::round(staging.x), Helper::round(staging.y));
        if(stagingTile != creatureTile)
        {
            const std::list<Tile*> tiles = gameMap->path(&mCreature, stagingTile);
            if(tiles.empty())
                continue;
            Creature::tileToVector2(tiles, path, true, 0.0f);
        }
        path.push_back(staging);
        RoomObjectNavigation::refine(mCreature, path);
        if(path.empty() || !(path.back() == staging))
            continue;

        // The last leg goes straight from the point in front of the seat onto it; the seat is the only furniture it
        // touches (getSeatStagingPoints checked it)
        path.push_back(place);
        mStagingPoint = staging;
        mPhase = Phase::mount;
        mCreature.setWalkPath(EntityAnimation::walk_anim, EntityAnimation::idle_anim, true, true, path, false, true);
        mCreature.pushAction(Utils::make_unique<CreatureActionWalkToTile>(mCreature));
        return true;
    }
    return false;
}

Tile* CreatureActionUseToilet::findTileOutsideExemptRoom() const
{
    Tile* myTile = mCreature.getPositionTile();
    if(myTile == nullptr)
        return nullptr;

    // The tiles within sight are sorted by distance, so the first one that fits is the nearest
    for(Tile* tile : mCreature.getTilesWithinSightRadius())
    {
        if(tile->isFullTile() || !mCreature.canGoThroughTile(tile))
            continue;

        if(isExemptRoomType(tile->getCoveringRoom()))
            continue;

        if(!mCreature.getGameMap()->pathExists(&mCreature, myTile, tile))
            continue;

        return tile;
    }

    return nullptr;
}

bool CreatureActionUseToilet::handleUseToilet()
{
    Tile* myTile = mCreature.getPositionTile();
    if(myTile == nullptr)
    {
        OD_LOG_ERR("creature=" + mCreature.getName());
        mCreature.popAction();
        return true;
    }

    // A gap in the turns means something else (a fight) ran in between: the use starts again
    int64_t turn = mCreature.getGameMap()->getTurnNumber();
    if((mPhase == Phase::squat) && ((mLastTurn < 0) || (turn - mLastTurn > 1)))
        mPhase = Phase::approach;
    mLastTurn = turn;

    if(mSeatTile != nullptr)
        return handleSeat(myTile);

    return handleFloor(myTile);
}

bool CreatureActionUseToilet::handleSeat(Tile* /*myTile*/)
{
    // After the use the creature has stepped off the seat: the action is over
    if(mPhase == Phase::leave)
    {
        finish();
        return true;
    }

    // The seat was taken, or the room is gone or was sold
    RoomToilet* room = getSeatRoom();
    if(mSeatLost || (room == nullptr) || !room->reserveTile(mSeatTile, &mCreature))
    {
        finish();
        return true;
    }

    Ogre::Vector2 place;
    Ogre::Vector2 facing;
    if(!room->getSeatPlace(mSeatTile, place, facing))
    {
        finish();
        return true;
    }

    if((mPhase == Phase::approach) || (mPhase == Phase::mount))
    {
        const Ogre::Vector2 position(mCreature.getPosition().x, mCreature.getPosition().y);
        if(mCreature.isMoving() || (position.squaredDistance(place) > SEAT_REACHED_SQUARED))
        {
            // Arrived somewhere else (the walk was cut short) or not started yet: walk to the seat (again). A seat
            // that cannot be reached without walking through furniture is given up.
            if(!walkOntoSeat(*room))
            {
                finish();
                return true;
            }

            return true;
        }

        startSquat(true, facing);
    }

    --mTurnsLeft;
    if(mTurnsLeft > 0)
        return false;

    // Done: the urge is gone and the seat dirties the floor of the room
    mCreature.setUrge(0.0);
    Room::addUseDirt(mCreature, mSeatTile, "ToiletDirtPerUse");
    releaseSeat();

    // The creature gets up and steps off the seat to the point it came from, never through the seat
    mPhase = Phase::leave;
    if(mStagingPoint == Ogre::Vector2::ZERO)
    {
        const std::vector<Ogre::Vector2> points = room->getSeatStagingPoints(mCreature, mSeatTile);
        if(!points.empty())
            mStagingPoint = points.front();
    }
    if(mStagingPoint == Ogre::Vector2::ZERO)
    {
        finish();
        return true;
    }

    const std::vector<Ogre::Vector2> route(1, mStagingPoint);
    mCreature.setWalkPath(EntityAnimation::walk_anim, EntityAnimation::idle_anim, true, true, route, false, true);
    mCreature.pushAction(Utils::make_unique<CreatureActionWalkToTile>(mCreature));
    return true;
}

bool CreatureActionUseToilet::handleFloor(Tile* myTile)
{
    if(mPhase == Phase::approach)
    {
        // In a treasury, the dungeon heart room or a temple the creature steps out of the room first
        if(isExemptRoomType(myTile->getCoveringRoom()) && !mLeaveTried)
        {
            mLeaveTried = true;
            Tile* outsideTile = findTileOutsideExemptRoom();
            if((outsideTile != nullptr) && mCreature.setDestination(outsideTile))
                return true;
        }

        startSquat(false, Ogre::Vector2::ZERO);
    }

    --mTurnsLeft;
    if(mTurnsLeft > 0)
        return false;

    // Done: a pile of the creature's kind stays on the floor until a worker cleans it
    DirtPileEntity::createOnTile(mCreature.getGameMap(), myTile, DirtPileKind::pile,
        mCreature.getDefinition()->getClassName());
    mCreature.setUrge(0.0);

    // A human keeper is told that a creature found no toilet
    Seat* seat = mCreature.getSeat();
    Player* player = (seat == nullptr) ? nullptr : seat->getPlayer();
    if((player != nullptr) && player->getIsHuman())
        player->notifyDirtEvent(Player::DirtEventKind::relieved, "", &mCreature);

    finish();
    return true;
}
