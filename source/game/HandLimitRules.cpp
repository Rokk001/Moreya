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

#include <algorithm>
#include <cmath>
#include <sstream>

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

//! \brief A full hand is named first, then a running cooldown; without the limit nothing is refused.
Refusal refusal(bool limitActive, bool fightingCreature, uint32_t fightersInHand, uint32_t maxFighters,
    double cooldownLeft)
{
    if(!limitActive || !fightingCreature)
        return Refusal::none;

    if(fightersInHand >= maxFighters)
        return Refusal::handFull;

    if(cooldownLeft > 0.0)
        return Refusal::cooldown;

    return Refusal::none;
}

//! \brief Rounds the running cooldown up to whole seconds.
uint32_t displaySeconds(double cooldownLeft)
{
    if(!(cooldownLeft > 0.0))
        return 0;

    return static_cast<uint32_t>(std::max(1.0, std::ceil(cooldownLeft)));
}

//! \brief The message of a refused pickup with the whole seconds left of a running cooldown.
std::string refusalMessage(Refusal reason, double cooldownLeft)
{
    if(reason == Refusal::handFull)
        return "Your hand cannot hold another fighting creature.";

    if(reason == Refusal::cooldown)
    {
        std::stringstream message;
        message << "You can pick up the next fighting creature in " << displaySeconds(cooldownLeft) << " s.";
        return message.str();
    }

    return std::string();
}

//! \brief The number shown under the prohibition picture with the whole seconds left of a running cooldown (HL2, K5):
//! only the digits, no words; empty when the cooldown is over.
std::string cooldownText(double cooldownLeft)
{
    const uint32_t seconds = displaySeconds(cooldownLeft);
    if(seconds == 0)
        return std::string();

    std::stringstream text;
    text << seconds;
    return text.str();
}

//! \brief The whole seconds the prohibition picture shows over a creature: 0 (nothing is drawn) unless the pointer is
//! over a fighting creature the keeper could otherwise pick up and the cooldown runs.
uint32_t cooldownIconSeconds(bool overPickableFighter, double cooldownLeft)
{
    if(!overPickableFighter)
        return 0;

    return displaySeconds(cooldownLeft);
}

//! \brief Puts the prohibition picture centred on the given point of the creature and the number directly under the
//! picture; both are moved back inside the screen where they would leave it.
void cooldownIconPlace(float centreX, float centreY, float iconSize, float numberWidth, float numberHeight,
    float screenWidth, float screenHeight, float& iconLeft, float& iconTop, float& numberLeft, float& numberTop)
{
    iconLeft = std::max(0.0f, std::min(centreX - iconSize * 0.5f, screenWidth - iconSize));
    iconTop = std::max(0.0f, std::min(centreY - iconSize * 0.5f, screenHeight - iconSize - numberHeight));
    numberLeft = std::max(0.0f, std::min(iconLeft + (iconSize - numberWidth) * 0.5f, screenWidth - numberWidth));
    numberTop = iconTop + iconSize;
}
}
