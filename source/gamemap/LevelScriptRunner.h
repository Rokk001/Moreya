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

#ifndef LEVELSCRIPTRUNNER_H
#define LEVELSCRIPTRUNNER_H

#include <cstdint>
#include <vector>

class Creature;
class GameMap;
class Tile;

namespace LevelScriptRunner
{
    //! \brief Checks the triggers of the game map level script and runs the actions of
    //! the ones whose conditions are met. Server side only, called once per turn.
    //! \brief Retries original victories after all objective observers have updated.
    void doTurn(GameMap& gameMap);

    //! \brief Carries out the standing order that a script action gave to the creature (go to
    //! the dungeon of a player, walk to a point, hunt creatures, wait, steal gold). Server side only,
    //! called when the creature has nothing to do. Returns true if the order takes the turn of the
    //! creature, false if the creature may do what it does without an order.
    bool doCreatureOrder(Creature& creature);

    //! \brief Leaves a carried portal stone on the creature's current tile before pickup; server side only.
    void dropCarriedStone(Creature& creature);

    //! \brief The factor by which a running creature moves faster than a walking one (action speed run). The raid
    //! leader who flees to the gate runs with it.
    double getRunSpeedFactor();

    //! \brief Server side. The creature walks to the nearest of the tiles it can reach.
    //! \return False when none of them can be reached.
    bool walkToNearestTile(Creature& creature, const std::vector<Tile*>& tiles);

    //! \brief Server side. The rule of the killplayer order: the creature walks to the dungeon heart of the seat and
    //! stays near it to fight what comes. The raid attacks the heart this way.
    //! \return True when this takes the turn of the creature (it walks there or stays near the heart), false when the
    //! seat has no heart or no way leads there.
    bool walkToDungeonHeart(Creature& creature, int32_t seatId);
}

#endif // LEVELSCRIPTRUNNER_H
