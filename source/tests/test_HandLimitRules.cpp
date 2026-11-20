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
