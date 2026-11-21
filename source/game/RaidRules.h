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

#ifndef RAIDRULES_H
#define RAIDRULES_H

#include <cstdint>
#include <string>
#include <vector>

//! \brief The decisions of the raid: the countdown until the next raid group comes through the Moreya gate, the early
//! opening of the gate, the flight of a raid leader, the defeat of the whole raid, the gold a raid member can carry and
//! the gold it takes from a treasury. The engine side (RaidManager) collects the facts of the game and applies the results. This file
//! only depends on the standard library so that its rules can be checked on their own.
namespace RaidRules
{
//! \brief The arrival schedule of the raid groups of a level.
struct Schedule
{
    //! \brief Creates a schedule without raid groups and with a closed gate.
    Schedule() :
        mNextGroup(0),
        mGroupCount(0),
        mSecondsToNext(-1.0),
        mGateOpen(false),
        mOpenByKeeper(false)
    {}

    //! \brief Index of the raid group that comes next (equal to mGroupCount when every group has come).
    uint32_t mNextGroup;
    //! \brief Number of raid groups of the level.
    uint32_t mGroupCount;
    //! \brief Seconds until the next raid group comes, negative when none is waiting.
    double mSecondsToNext;
    //! \brief True while the gate is open (opened by the countdown or by the player). Without a countdown it closes
    //! again after a raid group came through it while further groups wait.
    bool mGateOpen;
    //! \brief True when no countdown runs (campaign difficulty Easy and Medium): every raid group waits behind the
    //! closed gate until the attacked keeper opens it.
    bool mOpenByKeeper;
};

//! \brief Starts the schedule at the level start: the first raid group comes after countdownSeconds, or, when
//! openByKeeper is set, only when the keeper opens the gate (no countdown).
//! \param groupCount Number of raid groups of the level (0: nothing ever comes).
//! \param countdownSeconds Seconds from the level start until the gate opens (at least 0); unused with openByKeeper.
//! \param openByKeeper True when no countdown runs and every raid group waits until the keeper opens the gate.
void start(Schedule& schedule, uint32_t groupCount, double countdownSeconds, bool openByKeeper);

//! \brief Lets the given seconds pass. When the countdown ends, the gate opens and the next raid group comes; while
//! raid groups are left, the countdown then runs for intervalSeconds until the following one. Without a countdown
//! (mOpenByKeeper) a group comes only once the keeper opened the gate, and no countdown runs for the following one.
//! At most one group comes per call.
//! \return True when a raid group comes now (it is the group with the index mNextGroup - 1).
bool advance(Schedule& schedule, double seconds, double intervalSeconds);

//! \brief The player opens the gate: with a countdown before it ends and only for the first raid group; without a
//! countdown (mOpenByKeeper) for every raid group that waits behind the closed gate. The group comes at once (at the
//! next call of advance). Refused when the gate is open or no raid group waits.
//! \return True when the gate is opened.
bool openEarly(Schedule& schedule);

//! \brief True when no countdown runs, the gate is open after a raid group came through it and a further raid group
//! is left: the gate closes again (closeAgain) once the group that came has left the gate, and the next group waits
//! until the keeper opens the gate again.
bool shouldCloseAgain(const Schedule& schedule);

//! \brief Closes the gate again behind a raid group (see shouldCloseAgain).
void closeAgain(Schedule& schedule);

//! \brief True when no countdown runs and a raid group waits behind the closed gate until the keeper opens it.
bool waitsForKeeper(const Schedule& schedule);

//! \brief Sets the seconds until the next raid group (script action raidcountdown). Ignored when no group waits.
void setSecondsToNext(Schedule& schedule, double seconds);

//! \brief The whole seconds the countdown shows (rounded up), -1 when no raid group waits.
int32_t displaySeconds(const Schedule& schedule);

//! \brief True when every raid group of the schedule has come.
bool allArrived(const Schedule& schedule);

//! \brief The share of the members of a raid group, the leader not counted, that have fallen.
//! \param others Members of the group without the leader.
//! \param fallen How many of them have fallen (dead, imprisoned or won over by a keeper).
//! \return 0 to 1; 0 when the group has no other member.
double fallenShare(uint32_t others, uint32_t fallen);

//! \brief True when the leader flees to the gate: his group has other members and their fallen share reached
//! escapeShare.
bool leaderShouldFlee(uint32_t others, uint32_t fallen, double escapeShare);

//! \brief True when the whole raid is defeated: every raid group has come, at least one member came, no member is
//! left standing and no leader escaped.
//! \param allGroupsArrived True when every raid group has come.
//! \param spawned Members that came through the gate.
//! \param standing Members that still stand (alive on the map, not imprisoned, not won over, not escaped).
//! \param leaderEscaped True when a leader escaped through the gate.
bool isRaidDefeated(bool allGroupsArrived, uint32_t spawned, uint32_t standing, bool leaderEscaped);

//! \brief True when the creature class is one of the large raid member classes (they carry more gold).
//! \param className The class of the raid member.
//! \param largeClasses The classes of the large raid members (config RaidLargeMemberClasses).
bool isLargeMember(const std::string& className, const std::vector<std::string>& largeClasses);

//! \brief The gold a raid member can carry: the gold of smallTiles treasury tiles for a small member, of largeTiles
//! treasury tiles for a large one; never less than 0.
//! \param large True for a large raid member.
//! \param goldPerTile The gold one treasury tile stores (config TreasuryGoldPerTile).
//! \param smallTiles Treasury tiles a small member carries (config RaidCarryTilesSmall).
//! \param largeTiles Treasury tiles a large member carries (config RaidCarryTilesLarge).
double carryCapacity(bool large, double goldPerTile, double smallTiles, double largeTiles);

//! \brief The gold one raid member takes from a treasury it stands in: what it can still carry, at most what the
//! treasury holds, never less than 0. Looted items do not count against the gold.
//! \param stored The gold the treasury holds.
//! \param carried The gold the member already carries.
//! \param capacity The gold the member can carry (carryCapacity).
double plunderAmount(double stored, double carried, double capacity);
}

#endif // RAIDRULES_H
