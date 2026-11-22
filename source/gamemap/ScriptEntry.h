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

#ifndef SCRIPTENTRY_H
#define SCRIPTENTRY_H

#include <sstream>
#include <string>
#include <vector>

//! \brief One line of the [Scripts] section of a level: "EventName ScriptFile Trigger..." with the trigger as
//! a list of numbers. The loader and the writer of the level file share this format.
namespace ScriptEntry
{
    //! \brief Reads a [Scripts] line into the event name, the script file name and the trigger numbers. Returns
    //! false for a line that holds no entry: an empty line, a comment line (starting with #) or a line without
    //! a script file name.
    inline bool parse(const std::string& line, std::string& eventName, std::string& scriptName,
        std::vector<int>& trigger)
    {
        eventName.clear();
        scriptName.clear();
        trigger.clear();
        std::istringstream stream(line);
        if(!(stream >> eventName))
            return false;
        if(eventName[0] == '#')
            return false;
        if(!(stream >> scriptName))
            return false;
        int value = 0;
        while(stream >> value)
            trigger.push_back(value);
        return true;
    }

    //! \brief Builds the [Scripts] line of an entry, in the form parse reads.
    inline std::string format(const std::string& eventName, const std::string& scriptName,
        const std::vector<int>& trigger)
    {
        std::ostringstream stream;
        stream << eventName << " " << scriptName;
        for(size_t index = 0; index < trigger.size(); ++index)
            stream << " " << trigger[index];
        return stream.str();
    }
}

#endif // SCRIPTENTRY_H
