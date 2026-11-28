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

// Header-only Boost.Test, see test_DungeonHeartTier.cpp.
// OVERRIDE_BOOST_TEST_INCLUDED_WARNING
#define BOOST_TEST_MODULE HandLimitRules
#include <boost/test/included/unit_test.hpp>

#include "game/HandLimitRules.h"

#include <cstdint>

namespace
{
//! Fighting creatures a keeper of a campaign level can hold at once (HandLimitFighters of global.cfg)
const uint32_t MAX_FIGHTERS = 1;
//! A cooldown length for the checks; the shipped value is set by the simulation
const double COOLDOWN = 10.0;
}

//! Checks which held entities count against the limit: fighters only, not Zivs, prisoners or objects.
BOOST_AUTO_TEST_CASE(test_fightingCreature)
{
    BOOST_CHECK(HandLimitRules::isFightingCreature(true, false, false));
    BOOST_CHECK(!HandLimitRules::isFightingCreature(true, true, false));
    BOOST_CHECK(!HandLimitRules::isFightingCreature(true, false, true));
    BOOST_CHECK(!HandLimitRules::isFightingCreature(false, false, false));
}

//! Checks that a second fighting creature is refused in a campaign level while one is held.
BOOST_AUTO_TEST_CASE(test_secondFighterRefused)
{
    BOOST_CHECK(HandLimitRules::mayPickUp(true, true, 0, MAX_FIGHTERS, 0.0));
    BOOST_CHECK(!HandLimitRules::mayPickUp(true, true, 1, MAX_FIGHTERS, 0.0));
    BOOST_CHECK(!HandLimitRules::mayPickUp(true, true, 2, MAX_FIGHTERS, 0.0));
}

//! Checks that Zivs and other entities that are no fighting creature are never limited, not even with a full hand
//! and a running cooldown.
BOOST_AUTO_TEST_CASE(test_zivsNotLimited)
{
    BOOST_CHECK(HandLimitRules::mayPickUp(true, false, 1, MAX_FIGHTERS, COOLDOWN));
    BOOST_CHECK(HandLimitRules::mayPickUp(true, false, 0, MAX_FIGHTERS, 0.0));
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownAfterDrop(true, false, 0.0, COOLDOWN), 0.0);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownAfterDrop(true, false, 4.0, COOLDOWN), 4.0);
}

//! Checks the cooldown after a drop: it starts with its full length, refuses the next fighting creature while it runs,
//! counts down by the passed game seconds and allows the pickup again once it is over.
BOOST_AUTO_TEST_CASE(test_cooldownAfterDrop)
{
    double cooldown = HandLimitRules::cooldownAfterDrop(true, true, 0.0, COOLDOWN);
    BOOST_CHECK_EQUAL(cooldown, COOLDOWN);
    BOOST_CHECK(!HandLimitRules::mayPickUp(true, true, 0, MAX_FIGHTERS, cooldown));

    cooldown = HandLimitRules::advanceCooldown(cooldown, 4.0);
    BOOST_CHECK_EQUAL(cooldown, 6.0);
    BOOST_CHECK(!HandLimitRules::mayPickUp(true, true, 0, MAX_FIGHTERS, cooldown));

    // A second drop while the cooldown runs starts it again with its full length
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownAfterDrop(true, true, cooldown, COOLDOWN), COOLDOWN);

    cooldown = HandLimitRules::advanceCooldown(cooldown, 7.0);
    BOOST_CHECK_EQUAL(cooldown, 0.0);
    BOOST_CHECK(HandLimitRules::mayPickUp(true, true, 0, MAX_FIGHTERS, cooldown));

    // A cooldown length of 0 means no cooldown
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownAfterDrop(true, true, 0.0, 0.0), 0.0);
}

//! Checks that skirmish and multiplayer (no campaign level) stay unchanged: every pickup is allowed and a drop starts
//! no cooldown.
BOOST_AUTO_TEST_CASE(test_skirmishAndMultiplayerUnchanged)
{
    BOOST_CHECK(HandLimitRules::mayPickUp(false, true, 1, MAX_FIGHTERS, 0.0));
    BOOST_CHECK(HandLimitRules::mayPickUp(false, true, 5, MAX_FIGHTERS, COOLDOWN));
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownAfterDrop(false, true, 0.0, COOLDOWN), 0.0);
}

//! Checks that a cooldown restored from a saved game goes on with the seconds it had left.
BOOST_AUTO_TEST_CASE(test_savedCooldownGoesOn)
{
    const double saved = 3.25;
    BOOST_CHECK(!HandLimitRules::mayPickUp(true, true, 0, MAX_FIGHTERS, saved));
    BOOST_CHECK_EQUAL(HandLimitRules::advanceCooldown(saved, 3.0), 0.25);
    BOOST_CHECK_EQUAL(HandLimitRules::advanceCooldown(saved, 3.25), 0.0);
}

//! Checks the reason and the short message of a refused pickup (HL2): a full hand first, then the running cooldown with
//! its whole seconds rounded up; an allowed pickup, a Ziv and skirmish give no message.
BOOST_AUTO_TEST_CASE(test_refusalMessage)
{
    BOOST_CHECK(HandLimitRules::refusal(true, true, 1, MAX_FIGHTERS, 0.0) == HandLimitRules::Refusal::handFull);
    BOOST_CHECK(HandLimitRules::refusal(true, true, 1, MAX_FIGHTERS, COOLDOWN) == HandLimitRules::Refusal::handFull);
    BOOST_CHECK(HandLimitRules::refusal(true, true, 0, MAX_FIGHTERS, 2.1) == HandLimitRules::Refusal::cooldown);
    BOOST_CHECK(HandLimitRules::refusal(true, true, 0, MAX_FIGHTERS, 0.0) == HandLimitRules::Refusal::none);
    BOOST_CHECK(HandLimitRules::refusal(true, false, 1, MAX_FIGHTERS, COOLDOWN) == HandLimitRules::Refusal::none);
    BOOST_CHECK(HandLimitRules::refusal(false, true, 1, MAX_FIGHTERS, COOLDOWN) == HandLimitRules::Refusal::none);

    BOOST_CHECK_EQUAL(HandLimitRules::refusalMessage(HandLimitRules::Refusal::handFull, 0.0),
        "@msg.hand.full");
    BOOST_CHECK_EQUAL(HandLimitRules::refusalMessage(HandLimitRules::Refusal::cooldown, 2.1),
        "@msg.hand.cooldown|seconds=3");
    BOOST_CHECK_EQUAL(HandLimitRules::refusalMessage(HandLimitRules::Refusal::none, 2.1), "");
}

//! Checks the number under the prohibition picture (HL2, K5): the whole seconds left as digits only, at least 1 while the
//! cooldown runs, nothing once it is over, and no word in it.
BOOST_AUTO_TEST_CASE(test_cooldownText)
{
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownText(COOLDOWN), "10");
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownText(23.0), "23");
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownText(22.4), "23");
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownText(0.01), "1");
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownText(0.0), "");
    BOOST_CHECK_EQUAL(HandLimitRules::displaySeconds(9.0), 9u);
    BOOST_CHECK_EQUAL(HandLimitRules::displaySeconds(-1.0), 0u);
}

//! Checks that the prohibition picture shows its whole seconds only over a pickable fighting creature while the
//! cooldown runs, counts down with the cooldown, and nothing is drawn when the pointer is not over such a creature or
//! the cooldown is over (K5).
BOOST_AUTO_TEST_CASE(test_cooldownIconSeconds)
{
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(true, 23.0), 23u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(true, 22.0), 22u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(true, 21.2), 22u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(true, 0.01), 1u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(true, 0.0), 0u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(false, 23.0), 0u);
    BOOST_CHECK_EQUAL(HandLimitRules::cooldownIconSeconds(false, 0.0), 0u);
}

//! Checks that the prohibition picture and its number stay inside the screen from 640x480 to 7680x4320 at UI scale 80 %
//! to 120 %, with the hovered creature anywhere, also in the corners (Global Constraint 6), and that away from the
//! edges the picture is centred on the creature point with the number centred under it.
BOOST_AUTO_TEST_CASE(test_cooldownIconInsideScreen)
{
    const float screens[][2] = {{640.0f, 480.0f}, {1920.0f, 1080.0f}, {7680.0f, 4320.0f}};
    const float scales[] = {0.8f, 1.0f, 1.2f};
    for(const float* screen : screens)
    {
        for(float scale : scales)
        {
            // The size of a 640x480 screen scales the hand feedback down, an 8K screen up
            const float feedback = scale * screen[1] / 1080.0f;
            const float iconSize = 48.0f * feedback;
            const float numberHeight = 24.0f * feedback;
            const float numberWidth = 3.0f * numberHeight * 0.6f;
            const float points[][2] = {{0.0f, 0.0f}, {screen[0] / 2.0f, screen[1] / 2.0f},
                {screen[0] - 1.0f, screen[1] - 1.0f}, {screen[0] - 1.0f, 0.0f}, {0.0f, screen[1] - 1.0f}};
            for(const float* point : points)
            {
                float iconLeft = -1.0f;
                float iconTop = -1.0f;
                float numberLeft = -1.0f;
                float numberTop = -1.0f;
                HandLimitRules::cooldownIconPlace(point[0], point[1], iconSize, numberWidth, numberHeight, screen[0],
                    screen[1], iconLeft, iconTop, numberLeft, numberTop);
                BOOST_CHECK(iconLeft >= 0.0f && iconLeft + iconSize <= screen[0]);
                BOOST_CHECK(iconTop >= 0.0f && iconTop + iconSize <= screen[1]);
                BOOST_CHECK(numberLeft >= 0.0f && numberLeft + numberWidth <= screen[0]);
                BOOST_CHECK(numberTop >= 0.0f && numberTop + numberHeight <= screen[1]);
            }
        }
    }

    // Away from the edges the picture is centred on the point and the number centred under it
    float iconLeft = 0.0f;
    float iconTop = 0.0f;
    float numberLeft = 0.0f;
    float numberTop = 0.0f;
    HandLimitRules::cooldownIconPlace(500.0f, 400.0f, 48.0f, 30.0f, 24.0f, 1920.0f, 1080.0f, iconLeft, iconTop,
        numberLeft, numberTop);
    BOOST_CHECK_EQUAL(iconLeft, 476.0f);
    BOOST_CHECK_EQUAL(iconTop, 376.0f);
    BOOST_CHECK_EQUAL(numberLeft, 485.0f);
    BOOST_CHECK_EQUAL(numberTop, 424.0f);
}
