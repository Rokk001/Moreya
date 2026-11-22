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

#ifndef CONTENTPACKAGECHECK_H
#define CONTENTPACKAGECHECK_H

#include <algorithm>
#include <cstdint>
#include <iterator>
#include <string>
#include <vector>

//! \brief The room package comparison of the multiplayer handshake. The client sends the names of its room packages
//! (the room names of RoomPackages, sorted) with hello; the server refuses a client that lacks a room package the
//! server has, with clientRejected and the names of the missing packages, and sends its own room packages with
//! loadLevel so that the client offers only the rooms the server can build. The header has no other dependencies so
//! that the server, the client and small probes can share it.
namespace ContentPackageCheck
{

//! \brief Most package names a list on the wire may hold.
const uint32_t MAX_PACKAGES = 64;

//! \brief Most bytes of one package name on the wire.
const uint32_t MAX_NAME_BYTES = 64;

//! \brief Text in front of the missing package names in the message the refused client shows.
const char* const MISSING_PACKAGES_PREFIX = "Missing content package(s): ";

//! \brief True when a count read from a packet is a valid number of package names.
inline bool isCountAllowed(uint32_t count)
{
    return count <= MAX_PACKAGES;
}

//! \brief True when a name read from a packet is a valid package name: not empty and at most MAX_NAME_BYTES bytes.
inline bool isNameAllowed(const std::string& name)
{
    return !name.empty() && (name.size() <= MAX_NAME_BYTES);
}

//! \brief Sorts the names and removes the duplicates, so that both sides compare the same sorted lists.
inline std::vector<std::string> normalize(const std::vector<std::string>& names)
{
    std::vector<std::string> sorted(names);
    std::sort(sorted.begin(), sorted.end());
    sorted.erase(std::unique(sorted.begin(), sorted.end()), sorted.end());
    return sorted;
}

//! \brief The packages of the server that the client lacks, sorted. Packages the client has beyond the server's
//! do not count: the server's packages govern.
inline std::vector<std::string> findMissing(const std::vector<std::string>& serverPackages,
    const std::vector<std::string>& clientPackages)
{
    const std::vector<std::string> server = normalize(serverPackages);
    const std::vector<std::string> client = normalize(clientPackages);
    std::vector<std::string> missing;
    std::set_difference(server.begin(), server.end(), client.begin(), client.end(), std::back_inserter(missing));
    return missing;
}

//! \brief Reads a package list written by writeList: a uint32_t count and the names. Returns false, with an empty
//! list, when a read fails, the count is above MAX_PACKAGES or a name is empty or longer than MAX_NAME_BYTES.
template<typename Packet>
bool readList(Packet& packet, std::vector<std::string>& names)
{
    names.clear();
    uint32_t count = 0;
    if(!(packet >> count) || !isCountAllowed(count))
        return false;
    for(uint32_t i = 0; i < count; ++i)
    {
        std::string name;
        if(!(packet >> name) || !isNameAllowed(name))
        {
            names.clear();
            return false;
        }
        names.push_back(name);
    }
    return true;
}

//! \brief Writes a package list as a uint32_t count and the names, in the order given.
template<typename Packet>
void writeList(Packet& packet, const std::vector<std::string>& names)
{
    const uint32_t count = static_cast<uint32_t>(names.size());
    packet << count;
    for(std::vector<std::string>::const_iterator it = names.begin(); it != names.end(); ++it)
    {
        const std::string name = *it;
        packet << name;
    }
}

//! \brief The message the refused client shows: MISSING_PACKAGES_PREFIX and the names, separated by ", ".
inline std::string missingMessage(const std::vector<std::string>& missing)
{
    std::string message(MISSING_PACKAGES_PREFIX);
    for(std::vector<std::string>::const_iterator it = missing.begin(); it != missing.end(); ++it)
    {
        if(it != missing.begin())
            message += ", ";
        message += *it;
    }
    return message;
}

}

#endif // CONTENTPACKAGECHECK_H
