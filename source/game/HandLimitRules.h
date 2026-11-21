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

#ifndef HANDLIMITRULES_H
#define HANDLIMITRULES_H

#include <cstdint>
#include <string>

//! \brief The decisions of the hand limit of a campaign level: a keeper holds at most HandLimitFighters fighting
//! creatures in the hand at once, Zivs (workers) are not limited, and after a fighting creature is dropped a cooldown
//! of HandLimitCooldownSeconds runs before the next fighting creature can be picked up. Outside of a campaign level
//! (skirmish, multiplayer) nothing is limited. The engine side (Player) collects the facts of the game and applies the
//! results. This file only depends on the standard library so that its rules can be checked on their own.
namespace HandLimitRules
{
//! \brief True when a held or picked up entity counts against the hand limit: a creature that is not a worker (Ziv)
//! and not a prisoner of a keeper.
//! \param isCreature True when the entity is a creature (items, gold and other objects are never limited).
//! \param isWorker True when the creature is a worker (Ziv).
//! \param isPrisoner True when the creature is held in a prison of a keeper.
bool isFightingCreature(bool isCreature, bool isWorker, bool isPrisoner);

//! \brief True when the keeper may pick up the entity now.
//! \param limitActive True while a campaign level is played (false: nothing is limited).
//! \param fightingCreature True when the entity counts against the hand limit (see isFightingCreature).
//! \param fightersInHand Number of fighting creatures the keeper holds already.
//! \param maxFighters Fighting creatures the keeper can hold at once (HandLimitFighters).
//! \param cooldownLeft Seconds left of the cooldown after the last drop of a fighting creature.
bool mayPickUp(bool limitActive, bool fightingCreature, uint32_t fightersInHand, uint32_t maxFighters,
    double cooldownLeft);

//! \brief The cooldown left after the keeper dropped an entity from the hand: a dropped fighting creature in a
//! campaign level starts the cooldown again with its full length; any other drop keeps the cooldown that runs.
//! \param limitActive True while a campaign level is played.
//! \param fightingCreature True when the dropped entity counts against the hand limit.
//! \param cooldownLeft Seconds left of the running cooldown.
//! \param cooldownSeconds Length of the cooldown (HandLimitCooldownSeconds).
double cooldownAfterDrop(bool limitActive, bool fightingCreature, double cooldownLeft, double cooldownSeconds);

//! \brief The cooldown left after the given game seconds have passed (never below 0).
//! \param cooldownLeft Seconds left of the running cooldown.
//! \param seconds Game seconds that passed.
double advanceCooldown(double cooldownLeft, double seconds);

//! \brief Why a pickup is refused (HL2).
enum class Refusal
{
    //! The pickup is allowed.
    none,
    //! The hand holds HandLimitFighters fighting creatures already.
    handFull,
    //! The cooldown after the last drop of a fighting creature runs.
    cooldown
};

//! \brief The reason why the keeper may not pick up the entity now (none when mayPickUp allows it); a full hand
//! comes before a running cooldown. Same parameters as mayPickUp.
Refusal refusal(bool limitActive, bool fightingCreature, uint32_t fightersInHand, uint32_t maxFighters,
    double cooldownLeft);

//! \brief Whole seconds shown for a running cooldown: rounded up, at least 1 while it runs, 0 when it is over.
uint32_t displaySeconds(double cooldownLeft);

//! \brief The short message a human keeper gets when a pickup is refused (HL2); empty for Refusal::none.
std::string refusalMessage(Refusal reason, double cooldownLeft);

//! \brief The number shown under the prohibition picture while the cooldown runs (HL2, K5): the whole seconds as
//! digits only, empty when it is over.
std::string cooldownText(double cooldownLeft);

//! \brief The whole seconds the prohibition picture shows over a creature (K5): 0, so nothing is drawn, unless the
//! pointer is over a fighting creature the keeper could otherwise pick up and the cooldown runs.
//! \param overPickableFighter True when the pointer is over such a creature.
//! \param cooldownLeft Seconds left of the cooldown.
uint32_t cooldownIconSeconds(bool overPickableFighter, double cooldownLeft);

//! \brief Place of the prohibition picture and its number, in screen pixels: the picture centred on the given point
//! of the hovered creature, the number directly under it, both moved back inside the screen so that they stay visible
//! on every screen size and UI scale.
//! \param centreX Horizontal screen position of the creature point in pixels.
//! \param centreY Vertical screen position of the creature point in pixels.
//! \param iconSize Side of the square picture in pixels (already scaled with the UI).
//! \param numberWidth Width of the number in pixels.
//! \param numberHeight Height of the number in pixels.
//! \param screenWidth Width of the screen in pixels.
//! \param screenHeight Height of the screen in pixels.
//! \param iconLeft Receives the left edge of the picture.
//! \param iconTop Receives the top edge of the picture.
//! \param numberLeft Receives the left edge of the number.
//! \param numberTop Receives the top edge of the number.
void cooldownIconPlace(float centreX, float centreY, float iconSize, float numberWidth, float numberHeight,
    float screenWidth, float screenHeight, float& iconLeft, float& iconTop, float& numberLeft, float& numberTop);
}

#endif // HANDLIMITRULES_H
