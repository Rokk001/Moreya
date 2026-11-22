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

#ifndef OFFICIALLEVELCHECKSUMS_H
#define OFFICIALLEVELCHECKSUMS_H

#include "gamemap/OfficialLevels.h"

#include <cstddef>

//! \brief The checksums of the shipped levels. The definitions are generated at every build from the levels/ folder
//! (cmake/GenerateOfficialLevelChecksums.cmake) into the build directory; they are not part of the repository.
namespace OfficialLevelChecksums
{
    //! \brief One entry per shipped level, followed by an entry with null pointers.
    extern const OfficialLevels::ChecksumEntry ENTRIES[];

    //! \brief The number of shipped levels in ENTRIES (without the closing entry).
    extern const std::size_t ENTRY_COUNT;
}

#endif // OFFICIALLEVELCHECKSUMS_H
