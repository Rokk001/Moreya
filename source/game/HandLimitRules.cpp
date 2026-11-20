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

#include "game/HandLimitRules.h"

namespace HandLimitRules
{
//! \brief A creature that is neither a worker nor a prisoner counts against the hand limit.
bool isFightingCreature(bool isCreature, bool isWorker, bool isPrisoner)
{
    return isCreature && !isWorker && !isPrisoner;
}

//! \brief Without the limit, or for an entity that is not a fighting creature, the pickup is always allowed;
//! otherwise the hand must have room for one more fighting creature and the cooldown must be over.
bool mayPickUp(bool limitActive, bool fightingCreature, uint32_t fightersInHand, uint32_t maxFighters,
    double cooldownLeft)
{
    if(!limitActive || !fightingCreature)
        return true;

    if(fightersInHand >= maxFighters)
        return false;

    return cooldownLeft <= 0.0;
}

//! \brief A dropped fighting creature in a campaign level starts the full cooldown; any other drop keeps it.
double cooldownAfterDrop(bool limitActive, bool fightingCreature, double cooldownLeft, double cooldownSeconds)
{
    if(!limitActive || !fightingCreature)
        return cooldownLeft;

    if(cooldownSeconds <= 0.0)
        return 0.0;

    return cooldownSeconds;
}

//! \brief Counts the cooldown down by the passed seconds and stops at 0.
double advanceCooldown(double cooldownLeft, double seconds)
{
    if(cooldownLeft <= seconds)
        return 0.0;

    return cooldownLeft - seconds;
}
}
