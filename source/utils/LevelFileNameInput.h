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

#ifndef LEVELFILENAMEINPUT_H
#define LEVELFILENAMEINPUT_H

#include <cstddef>
#include <string>

//! \brief Checks the level file names typed into the New and Save dialogs of the level editor.
namespace LevelFileNameInput
{
    //! \brief Returns true when the last part of name (after the last '/' or '\') is a file name: not empty, not
    //! only blanks, not "." and not "..". A name that names no file would make its folder the target of a save.
    inline bool namesFile(const std::string& name)
    {
        const std::size_t separator = name.find_last_of("/\\");
        const std::string last = (separator == std::string::npos) ? name : name.substr(separator + 1);
        const std::string blanks = " \t\r\n";
        const std::size_t first = last.find_first_not_of(blanks);
        if(first == std::string::npos)
            return false;
        const std::string trimmed = last.substr(first, last.find_last_not_of(blanks) - first + 1);
        return (trimmed != ".") && (trimmed != "..");
    }

    //! \brief Returns true when name names a file (see namesFile) and holds no folder: no '/', no '\' and no ':'
    //! (a drive). Such a name stays in the folder it is put in.
    inline bool isPlainFileName(const std::string& name)
    {
        if(name.find_first_of("/\\:") != std::string::npos)
            return false;
        return namesFile(name);
    }
}

#endif // LEVELFILENAMEINPUT_H
