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

#include "game/RaidRules.h"

#include <algorithm>
#include <cmath>

namespace RaidRules
{
//! \brief Resets the schedule: no group came, the gate is closed and the first group waits countdownSeconds.
void start(Schedule& schedule, uint32_t groupCount, double countdownSeconds)
{
    schedule.mNextGroup = 0;
    schedule.mGroupCount = groupCount;
    schedule.mGateOpen = false;
    if(groupCount == 0)
        schedule.mSecondsToNext = -1.0;
    else
        schedule.mSecondsToNext = std::max(0.0, countdownSeconds);
}

//! \brief Counts the countdown down; at its end the gate opens and the next group comes, then the interval starts for
//! the group after it.
bool advance(Schedule& schedule, double seconds, double intervalSeconds)
{
    if((schedule.mNextGroup >= schedule.mGroupCount) || (schedule.mSecondsToNext < 0.0))
        return false;

    schedule.mSecondsToNext -= seconds;
    if(schedule.mSecondsToNext > 0.0)
        return false;

    schedule.mGateOpen = true;
    ++schedule.mNextGroup;
    if(schedule.mNextGroup < schedule.mGroupCount)
        schedule.mSecondsToNext = std::max(0.0, intervalSeconds);
    else
        schedule.mSecondsToNext = -1.0;

    return true;
}

//! \brief Ends the countdown of the first group at once while the gate is still closed.
bool openEarly(Schedule& schedule)
{
    if(schedule.mGateOpen || (schedule.mNextGroup != 0) || (schedule.mGroupCount == 0))
        return false;

    schedule.mSecondsToNext = 0.0;
    return true;
}

//! \brief Sets the countdown of the waiting group, at least 0 seconds.
void setSecondsToNext(Schedule& schedule, double seconds)
{
    if(schedule.mNextGroup >= schedule.mGroupCount)
        return;

    schedule.mSecondsToNext = std::max(0.0, seconds);
}

//! \brief Rounds the seconds of the waiting group up; -1 without a waiting group.
int32_t displaySeconds(const Schedule& schedule)
{
    if((schedule.mNextGroup >= schedule.mGroupCount) || (schedule.mSecondsToNext < 0.0))
        return -1;

    return static_cast<int32_t>(std::ceil(schedule.mSecondsToNext));
}

//! \brief True when the index of the next group is past the last group.
bool allArrived(const Schedule& schedule)
{
    return schedule.mNextGroup >= schedule.mGroupCount;
}

//! \brief fallen / others, 0 without other members.
double fallenShare(uint32_t others, uint32_t fallen)
{
    if(others == 0)
        return 0.0;

    return static_cast<double>(std::min(fallen, others)) / static_cast<double>(others);
}

//! \brief A leader alone never flees; otherwise he flees once the fallen share reached the share of the config.
bool leaderShouldFlee(uint32_t others, uint32_t fallen, double escapeShare)
{
    if(others == 0)
        return false;

    return fallenShare(others, fallen) >= escapeShare;
}

//! \brief Every group came, someone came, nobody stands and no leader got away.
bool isRaidDefeated(bool allGroupsArrived, uint32_t spawned, uint32_t standing, bool leaderEscaped)
{
    return allGroupsArrived && (spawned > 0) && (standing == 0) && !leaderEscaped;
}

//! \brief min(perMember, stored), not below 0.
double plunderAmount(double stored, double perMember)
{
    return std::max(0.0, std::min(stored, perMember));
}
}
