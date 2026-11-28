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

#include "entities/ItemValueLines.h"

#define BOOST_TEST_MODULE ItemValueLines
#include "BoostTestTargetConfig.h"

#include <map>
#include <string>
#include <vector>

namespace
{
//! \brief The English labels of the value lines, as the language file lang-en gives them for the language keys of the
//! lines; the test fixes them here so that it does not depend on the content.
std::string englishLabel(const std::string& key)
{
    static std::map<std::string, std::string> labels;
    if(labels.empty())
    {
        labels["ui.item.value.physicaldamage"] = "Physical damage";
        labels["ui.item.value.magicaldamage"] = "Magical damage";
        labels["ui.item.value.elementaldamage"] = "Elemental damage";
        labels["ui.item.value.physicaldefence"] = "Physical defence";
        labels["ui.item.value.magicaldefence"] = "Magical defence";
        labels["ui.item.value.elementaldefence"] = "Elemental defence";
        labels["ui.item.value.attackrating"] = "Attack rating";
        labels["ui.item.value.defencerating"] = "Defence rating";
    }
    return labels[key];
}
}

//! Checks that a weapon without damage, defence or ratings (the kobold pick) gets no value line at all
BOOST_AUTO_TEST_CASE(test_weapon_without_values_has_no_line)
{
    const ItemWeaponValues pick;
    BOOST_CHECK(ItemValueLines::describeWeapon(pick, englishLabel).empty());
}

//! Checks that every damage and defence component is a line of its own with its name, damage as min-max, and that
//! the components that are 0 are left out
BOOST_AUTO_TEST_CASE(test_every_line_names_its_value)
{
    ItemWeaponValues sword;
    sword.mPhysicalDamageMin = 2.0;
    sword.mPhysicalDamage = 4.5;
    sword.mElementDamageMin = 1.0;
    sword.mElementDamage = 1.0;
    sword.mMagicalDefense = 3.0;
    sword.mAttackRating = 5.0;
    const std::vector<std::string> lines = ItemValueLines::describeWeapon(sword, englishLabel);
    BOOST_REQUIRE_EQUAL(lines.size(), 4u);
    BOOST_CHECK_EQUAL(lines[0], "Physical damage: 2-4.5");
    BOOST_CHECK_EQUAL(lines[1], "Elemental damage: 1");
    BOOST_CHECK_EQUAL(lines[2], "Magical defence: 3");
    BOOST_CHECK_EQUAL(lines[3], "Attack rating: 5");
    for(const std::string& line : lines)
        BOOST_CHECK(line.find(": 0") == std::string::npos);
}

//! Checks that a base value below one keeps its decimals (decision 922: sub-unit precision)
BOOST_AUTO_TEST_CASE(test_sub_unit_values_keep_their_decimals)
{
    ItemWeaponValues sword;
    sword.mPhysicalDamageMin = 0.14;
    sword.mPhysicalDamage = 0.2;
    const std::vector<std::string> lines = ItemValueLines::describeWeapon(sword, englishLabel);
    BOOST_REQUIRE_EQUAL(lines.size(), 1u);
    BOOST_CHECK_EQUAL(lines[0], "Physical damage: 0.14-0.2");
}

//! Checks that a damage range starting at 0 is still shown, since its maximum is not 0
BOOST_AUTO_TEST_CASE(test_damage_from_zero_is_shown)
{
    ItemWeaponValues club;
    club.mPhysicalDamage = 3.0;
    club.mDefenseRating = 1.5;
    const std::vector<std::string> lines = ItemValueLines::describeWeapon(club, englishLabel);
    BOOST_REQUIRE_EQUAL(lines.size(), 2u);
    BOOST_CHECK_EQUAL(lines[0], "Physical damage: 0-3");
    BOOST_CHECK_EQUAL(lines[1], "Defence rating: 1.5");
}
