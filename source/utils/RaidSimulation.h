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

#ifndef RAIDSIMULATION_H
#define RAIDSIMULATION_H

#include <cstdint>
#include <iosfwd>
#include <string>

class GameMap;

//! \brief Debug tool for the raid balance (command line: --raid-sim <level file> --seconds <N> --seed <S>
//! [--raid-sim-out <file>] [--raid-sim-keeper-ai]). It plays a level with a [Raid] section headless: no window, no
//! renderer, no network socket and no client. The server loads the level with the real config, gives every seat its
//! player (the human seat a player who gives no orders, or a computer keeper with --raid-sim-keeper-ai) and runs the
//! real game turns one after the other as fast as it can, each one game turn long. The random generator is set to the
//! seed, so a run can be repeated. After every turn one line of the raid and keeper state is written to the output
//! file (see writeHeader for the columns); the run ends when the raid is defeated, a raid leader escaped, the attacked
//! keeper lost his dungeon heart or the game time is over, and the last line names that result. The process exit code
//! tells whether the run worked (see Code), not who won.
class RaidSimulation
{
public:
    enum Code
    {
        codeDone = 0,
        codeUsage = 1,
        codeLoadError = 2,
        codeRunError = 3
    };

    //! \brief Runs one simulation and returns its exit code (see Code). Needs the resource manager (data paths) and
    //! the log manager; creates the config manager and the server itself.
    //! \param levelFile The level file to play (it needs a [Raid] section).
    //! \param seconds The longest game time of the run in seconds (more than 0).
    //! \param seed The seed of the random generator (0 takes 1, so that every run is repeatable).
    //! \param outFile The file the turn lines are written to.
    //! \param keeperAi True when a computer keeper plays the human seat instead of a player who gives no orders.
    static int run(const std::string& levelFile, int32_t seconds, uint32_t seed, const std::string& outFile,
        bool keeperAi);

    //! \brief Sets the reference keeper force of the next run (--raid-sim-force, --raid-sim-force-level): when the gate
    //! opens, one creature of each class stands at the attacked keeper's dungeon heart at the given level.
    //! \param classes Comma-separated creature classes (empty: no reference force).
    //! \param level Level of the creatures (at least 1).
    static void setKeeperForce(const std::string& classes, int32_t level);

    //! \brief Lets the hand limit of campaign levels apply in the next run (--raid-sim-hand-limit), see
    //! Player::setHandLimitForced.
    static void setHandLimit(bool handLimit);

    //! \brief Lets a model keeper drop his fighters into the fight with the hand in the next run
    //! (--raid-sim-hand-player): once per turn, as the hand rules allow, a fighter that stands away from the raid is
    //! picked up and dropped next to the raid member nearest the keeper's heart.
    static void setHandPlayer(bool handPlayer);

    //! \brief Sets the campaign difficulty of the next run (--raid-sim-difficulty): the computer keepers of the level
    //! without own level get it as their computer level, as in the campaign, and the raid uses the countdown of that
    //! difficulty (none on Easy and Medium). Empty: the level's computer levels (else normal) and the Normal countdown.
    static void setDifficulty(const std::string& difficulty);

    //! \brief Lets the keeper of the human seat also pursue the goals of the level in the next run
    //! (--raid-sim-goal-player, see RaidSimGoalPlayer); it needs --raid-sim-keeper-ai.
    static void setGoalPlayer(bool goalPlayer);

    //! \brief True once run was called (main returns its exit code then).
    static bool isActive();

    //! \brief The exit code of the last run.
    static int getExitCode();

private:
    //! \brief Writes the column names of the turn lines.
    static void writeHeader(std::ostream& os);

    //! \brief Writes the state of the raid and of the attacked keeper after a turn as one line.
    //! \param attackedSeatId The seat the raid attacks.
    static void writeTurn(std::ostream& os, GameMap& gameMap, int32_t attackedSeatId);
};

#endif // RAIDSIMULATION_H
