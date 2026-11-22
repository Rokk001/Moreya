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

#ifndef MAPSIZEINPUT_H
#define MAPSIZEINPUT_H

#include <cstddef>
#include <cstdint>
#include <string>

//! \brief Reads the width and height typed into the New dialogs of the level editor.
namespace MapSizeInput
{
    //! \brief The largest width or height, in tiles, the New dialogs accept.
    const int32_t MAX_SIZE = 400;

    //! \brief Reads a map width or height from the text of an edit box. Returns true and sets size when the text
    //! (leading and trailing blanks ignored) is a plain decimal number from 1 to MAX_SIZE. Empty text, signs,
    //! letters, decimals, zero, too large values and overflow are refused and leave size unchanged.
    inline bool parse(const std::string& text, int32_t& size)
    {
        const std::string blanks = " \t\r\n";
        size_t first = text.find_first_not_of(blanks);
        if(first == std::string::npos)
            return false;
        size_t last = text.find_last_not_of(blanks);

        int32_t value = 0;
        for(size_t i = first; i <= last; ++i)
        {
            if((text[i] < '0') || (text[i] > '9'))
                return false;
            value = value * 10 + (text[i] - '0');
            // Stop before the value can overflow: anything above the limit is refused anyway
            if(value > MAX_SIZE)
                return false;
        }
        if(value < 1)
            return false;

        size = value;
        return true;
    }
}

#endif // MAPSIZEINPUT_H
