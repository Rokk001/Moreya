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

#ifndef ITEMVALUELINES_H
#define ITEMVALUELINES_H

#include <cmath>
#include <iomanip>
#include <locale>
#include <sstream>
#include <string>
#include <vector>

//! \brief The base values of a held weapon or shield that an item tooltip lists (see ItemInstance::describeTooltip).
struct ItemWeaponValues
{
    //! \brief All values 0: a tooltip of these values has no value line.
    ItemWeaponValues() :
        mPhysicalDamageMin(0.0), mPhysicalDamage(0.0),
        mMagicalDamageMin(0.0), mMagicalDamage(0.0),
        mElementDamageMin(0.0), mElementDamage(0.0),
        mPhysicalDefense(0.0), mMagicalDefense(0.0), mElementDefense(0.0),
        mAttackRating(0.0), mDefenseRating(0.0)
    {}

    double mPhysicalDamageMin;
    double mPhysicalDamage;
    double mMagicalDamageMin;
    double mMagicalDamage;
    double mElementDamageMin;
    double mElementDamage;
    double mPhysicalDefense;
    double mMagicalDefense;
    double mElementDefense;
    double mAttackRating;
    double mDefenseRating;
};

//! \brief The value lines of an item tooltip (plan INGAME-QS-11 K6): every damage and defence component is a line of
//! its own that says in words what it is, damage as "min-max", and a line whose value is 0 is left out. Without
//! dependencies, so that it can be tested without the game.
namespace ItemValueLines
{
//! \brief A value of an item as the equipment file gives it: a whole number without decimals, any other number with
//! its decimals (six significant digits, so a base value below one keeps its precision, decision 922: "0.14").
inline std::string formatNumber(double value)
{
    std::ostringstream stream;
    stream.imbue(std::locale::classic());
    if(value == std::floor(value) && std::fabs(value) < 1e15)
        stream << std::fixed << std::setprecision(0) << value;
    else
        stream << value;
    return stream.str();
}

//! \brief A damage range as "min-max", a single number when both ends are equal.
inline std::string formatDamage(double minimum, double maximum)
{
    if(minimum == maximum)
        return formatNumber(maximum);
    return formatNumber(minimum) + "-" + formatNumber(maximum);
}

//! \brief Adds the line "label: value" unless the value is 0.
inline void addLine(std::vector<std::string>& lines, const char* label, double value)
{
    if(value != 0.0)
        lines.push_back(std::string(label) + ": " + formatNumber(value));
}

//! \brief Adds the damage line "label: min-max" unless both ends of the range are 0.
inline void addDamageLine(std::vector<std::string>& lines, const char* label, double minimum, double maximum)
{
    if(minimum != 0.0 || maximum != 0.0)
        lines.push_back(std::string(label) + ": " + formatDamage(minimum, maximum));
}

//! \brief The named value lines of a held weapon or shield, in the order damage, defence, ratings. A weapon without
//! any damage or defence gives no damage or defence line.
inline std::vector<std::string> describeWeapon(const ItemWeaponValues& values)
{
    std::vector<std::string> lines;
    addDamageLine(lines, "Physical damage", values.mPhysicalDamageMin, values.mPhysicalDamage);
    addDamageLine(lines, "Magical damage", values.mMagicalDamageMin, values.mMagicalDamage);
    addDamageLine(lines, "Elemental damage", values.mElementDamageMin, values.mElementDamage);
    addLine(lines, "Physical defence", values.mPhysicalDefense);
    addLine(lines, "Magical defence", values.mMagicalDefense);
    addLine(lines, "Elemental defence", values.mElementDefense);
    addLine(lines, "Attack rating", values.mAttackRating);
    addLine(lines, "Defence rating", values.mDefenseRating);
    return lines;
}
}

#endif // ITEMVALUELINES_H
