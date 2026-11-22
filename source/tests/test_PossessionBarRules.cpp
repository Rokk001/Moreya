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

#define BOOST_TEST_MODULE PossessionBarRules
#include "BoostTestTargetConfig.h"

#include "modes/PossessionBarRules.h"

#include <cmath>
#include <string>

//! Checks the key under each slot: 1 to 9 and 0 for the first ten, S+1 to S+0 (Shift) for the next ten, none after.
BOOST_AUTO_TEST_CASE(test_KeyLabels)
{
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(0), std::string("1"));
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(8), std::string("9"));
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(9), std::string("0"));
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(10), std::string("S+1"));
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(19), std::string("S+0"));
    BOOST_CHECK_EQUAL(PossessionBarRules::keyLabel(20), std::string());
}

//! Checks the icon of a slot: the painted icon of a skill tree skill by its id, the explosion spell icon for the
//! Explosion line of a creature definition and the general skill icon for every other line.
BOOST_AUTO_TEST_CASE(test_IconImages)
{
    BOOST_CHECK_EQUAL(PossessionBarRules::iconImage("BLK_A3", "Strike"), std::string("CreatureSkillIcons/BLK_A3"));
    BOOST_CHECK_EQUAL(PossessionBarRules::iconImage("T4_Orc", "AuraAlly"), std::string("CreatureSkillIcons/T4_Orc"));
    BOOST_CHECK_EQUAL(PossessionBarRules::iconImage("", "Explosion"),
        std::string("OpenDungeonsIcons/CreatureExplosionButton"));
    BOOST_CHECK_EQUAL(PossessionBarRules::iconImage("", "Teleport"), std::string("OpenDungeonsIcons/SkillIcon"));
}

//! Checks the share of the recovery a slot shows: none when ready, the remaining share while it recovers, never
//! more than all.
BOOST_AUTO_TEST_CASE(test_RecoveryShare)
{
    PossessionBarRules::Slot slot;
    BOOST_CHECK_EQUAL(PossessionBarRules::recoveryShare(slot), 0.0f);
    slot.mRemaining = 3.0;
    slot.mDuration = 4.0;
    BOOST_CHECK_EQUAL(PossessionBarRules::recoveryShare(slot), 0.75f);
    slot.mRemaining = 6.0;
    BOOST_CHECK_EQUAL(PossessionBarRules::recoveryShare(slot), 1.0f);
    slot.mDuration = 0.0;
    BOOST_CHECK_EQUAL(PossessionBarRules::recoveryShare(slot), 0.0f);
}

//! Checks the place of the bar: at 1920x1200 and scale 1 six slots of 78 pixels sit centred at the bottom; at 640x480
//! the full twenty slots and the exit plate still fit into the width with slots of at least 24 pixels.
BOOST_AUTO_TEST_CASE(test_Layout)
{
    const PossessionBarRules::Layout big = PossessionBarRules::computeLayout(6, 1920.0f, 1200.0f, 1.0f);
    BOOST_CHECK(std::abs(big.mSlotSize - 78.0f) < 0.01f);
    const float bigTotal = big.mSlotsWidth + big.mGap + big.mPlateWidth;
    BOOST_CHECK(big.mLeft > 0.0f && (big.mLeft + bigTotal) < 1920.0f);
    BOOST_CHECK(std::abs((big.mLeft * 2.0f + bigTotal) - 1920.0f) < 0.01f);
    BOOST_CHECK((big.mTop + big.mHeight) < 1200.0f && big.mTop > 1000.0f);
    BOOST_CHECK(PossessionBarRules::slotLeft(big, 1) > PossessionBarRules::slotLeft(big, 0) + big.mSlotSize);

    const PossessionBarRules::Layout small = PossessionBarRules::computeLayout(20, 640.0f, 480.0f, 1.0f);
    const float smallTotal = small.mSlotsWidth + small.mGap + small.mPlateWidth;
    BOOST_CHECK(small.mSlotSize >= 24.0f);
    BOOST_CHECK(smallTotal <= 640.0f);
    BOOST_CHECK(small.mLeft >= 0.0f);
    BOOST_CHECK((small.mTop + small.mHeight) <= 480.0f);
}
