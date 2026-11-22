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

#ifndef PORTALWAVERULES_H
#define PORTALWAVERULES_H

#include <cstdint>
#include <string>

//! \brief What the level file can hold for the waves of a wave portal.
namespace PortalWaveRules
{
    //! \brief Team 0 is what a seat playing on its own gets; the level loader refuses it as a target team.
    inline bool isTargetTeamAllowed(int32_t team)
    {
        return team != 0;
    }

    //! \brief The level file stores a creature class name as one word: an empty name or one with white space
    //! cannot be read back.
    inline bool isStorableClassName(const std::string& name)
    {
        return !name.empty() && (name.find_first_of(" \t\r\n\v\f") == std::string::npos);
    }
}

#endif // PORTALWAVERULES_H
