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

#ifndef RAIDSIMGOALPLAYER_H
#define RAIDSIMGOALPLAYER_H

#include <cstdint>
#include <string>
#include <vector>

class GameMap;
class Player;

//! \brief Debug tool of the raid simulation (--raid-sim-goal-player): the test player that measures how long building
//! up the dungeon of a story level takes. The keeper of the human seat is a computer keeper (economy, rooms, research,
//! defence); this player adds what the computer keeper does not do: it pursues the goals of the level. It reads the
//! main and optional goals of the seat from the level file (every mainobjectiveid and optionalobjectiveid except the
//! raid goal, whose id ends in -raid) and the conditions of the triggers that set them reached, resolving flag, trigger
//! and objective conditions to the triggers behind them. On the goals not reached yet it acts with the real game rules
//! only, as a player would: it marks the tiles to dig on the way to a goal region (and the tiles of a region to claim
//! or mine), builds the rooms a goal asks for, and drops its fighters with the hand (within the hand limit of the
//! campaign) next to the enemies, doors and hearts a goal asks to defeat, and a worker into a region to visit. It
//! spawns nothing, gives no gold, reveals nothing and changes no rule.
namespace RaidSimGoalPlayer
{
//! \brief Reads the goals of the seat and the triggers, regions and spawn points of the level file.
//! \param levelFile The level file of the run.
//! \param seatId The seat whose goals are pursued (the human seat).
void load(const std::string& levelFile, int32_t seatId);

//! \brief The ids of the goals of the seat: main and optional, without the raid goal.
const std::vector<std::string>& getGoals();

//! \brief The creatures the player carried with the hand so far (fighters and workers).
uint32_t getCarried();

//! \brief The number of goals of getGoals that are reached now.
uint32_t countReached(const GameMap& gameMap, int32_t seatId);

//! \brief Called after every turn: every few game seconds the player looks at the goals that are not reached and acts
//! on them (see the namespace).
//! \param gameMap The map of the run.
//! \param keeper The player of the seat.
void act(GameMap& gameMap, Player* keeper);

//! \brief One line per goal that is not reached: its id and what the player works on for it, for the run's end line.
std::string describeOpenGoals(GameMap& gameMap, int32_t seatId);

//! \brief The state of the keeper of the seat for the run's end line: gold, room tiles per room type and creatures per
//! class.
std::string describeKeeper(GameMap& gameMap, int32_t seatId);
}

#endif // RAIDSIMGOALPLAYER_H
