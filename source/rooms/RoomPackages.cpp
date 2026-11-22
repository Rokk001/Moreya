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

#include "rooms/RoomPackages.h"

#include "game/CampaignPackages.h"
#include "utils/LogManager.h"

#include <boost/filesystem.hpp>

#include <algorithm>
#include <fstream>
#include <mutex>
#include <sstream>
#include <utility>

const std::string RoomPackages::ROOM_KEY = "Room";

namespace
{
//! \brief A packaged room and the name its Package.cfg uses.
struct PackagedRoom
{
    RoomType mType;
    const char* mName;
};

//! The rooms whose assets come from a room package, in room type order
const PackagedRoom PACKAGED_ROOMS[] =
{
    { RoomType::guardRoom, "GuardRoom" },
    { RoomType::temple, "Temple" },
    { RoomType::toilet, "Toilet" },
    { RoomType::merchant, "Merchant" },
    { RoomType::herbGarden, "HerbGarden" },
    { RoomType::alchemyLab, "AlchemyLab" },
    { RoomType::tavern, "Tavern" },
    { RoomType::infirmary, "Infirmary" },
    { RoomType::ghostRoom, "GhostRoom" },
    { RoomType::spa, "Spa" }
};

//! \brief The kept room packages (room type to package folder) and the lock that guards them.
struct Registry
{
    std::mutex mMutex;
    std::map<RoomType, std::string> mPackages;
};

//! \brief The registry of the found packages, created on first use.
Registry& getRegistry()
{
    static Registry registry;
    return registry;
}

//! \brief Removes the spaces and tabs at both ends of a text.
std::string trim(const std::string& text)
{
    const std::string::size_type first = text.find_first_not_of(" \t\r");
    if(first == std::string::npos)
        return std::string();
    const std::string::size_type last = text.find_last_not_of(" \t\r");
    return text.substr(first, last - first + 1);
}

//! \brief The room types of PACKAGED_ROOMS in table order.
std::vector<RoomType> listPackagedRooms()
{
    std::vector<RoomType> rooms;
    for(const PackagedRoom& room : PACKAGED_ROOMS)
        rooms.push_back(room.mType);
    return rooms;
}

//! \brief The names of PACKAGED_ROOMS by room type.
std::map<RoomType, std::string> mapPackagedRoomNames()
{
    std::map<RoomType, std::string> names;
    for(const PackagedRoom& room : PACKAGED_ROOMS)
        names[room.mType] = room.mName;
    return names;
}
} // namespace

//! \brief The packaged rooms of PACKAGED_ROOMS as a list.
const std::vector<RoomType>& RoomPackages::getPackagedRooms()
{
    static const std::vector<RoomType> rooms = listPackagedRooms();
    return rooms;
}

//! \brief Looks the room up in PACKAGED_ROOMS.
bool RoomPackages::isPackagedRoom(RoomType type)
{
    return !getPackageRoomName(type).empty();
}

//! \brief The name of the room in PACKAGED_ROOMS, or an empty text.
const std::string& RoomPackages::getPackageRoomName(RoomType type)
{
    static const std::string none;
    static const std::map<RoomType, std::string> names = mapPackagedRoomNames();
    std::map<RoomType, std::string>::const_iterator it = names.find(type);
    return (it == names.end()) ? none : it->second;
}

//! \brief Reads the definition line by line; '#' starts a comment line.
RoomType RoomPackages::parseDefinition(const std::string& definition)
{
    std::istringstream lines(definition);
    std::string line;
    while(std::getline(lines, line))
    {
        line = trim(line);
        if(line.empty() || (line[0] == '#'))
            continue;
        const std::string::size_type separator = line.find('=');
        if((separator == std::string::npos) || (trim(line.substr(0, separator)) != ROOM_KEY))
            continue;
        const std::string name = trim(line.substr(separator + 1));
        for(const PackagedRoom& room : PACKAGED_ROOMS)
        {
            if(name == room.mName)
                return room.mType;
        }
    }
    return RoomType::nullRoomType;
}

//! \brief Reads the Package.cfg of every package subfolder, sorted by folder name inside each searched folder.
std::map<RoomType, std::string> RoomPackages::findPackages(const std::vector<std::string>& folders)
{
    std::map<RoomType, std::string> packages;
    for(const std::string& folder : folders)
    {
        boost::system::error_code error;
        boost::filesystem::path root(folder);
        if(!boost::filesystem::is_directory(root, error))
            continue;

        std::vector<boost::filesystem::path> directories;
        for(boost::filesystem::directory_iterator it(root, error); !error && (it != boost::filesystem::directory_iterator());
            it.increment(error))
        {
            if(boost::filesystem::is_regular_file(it->path() / CampaignPackages::DEFINITION_FILE, error))
                directories.push_back(it->path());
        }
        std::sort(directories.begin(), directories.end());

        for(const boost::filesystem::path& directory : directories)
        {
            std::ifstream file((directory / CampaignPackages::DEFINITION_FILE).string().c_str(), std::ios::binary);
            if(!file.is_open())
                continue;

            std::ostringstream text;
            text << file.rdbuf();
            const RoomType type = parseDefinition(text.str());
            if((type == RoomType::nullRoomType) || (packages.count(type) != 0))
                continue;
            packages[type] = directory.generic_string();
        }
    }
    return packages;
}

//! \brief Finds the packages in the folders of the wing packages and logs the rooms without package.
void RoomPackages::discover(const std::string& gameDataPath)
{
    const std::map<RoomType, std::string> packages = findPackages(CampaignPackages::getPackageFolders(gameDataPath));
    setPackages(packages);
    std::string missing;
    for(const PackagedRoom& room : PACKAGED_ROOMS)
    {
        if(packages.count(room.mType) == 0)
            missing += std::string(" ") + room.mName;
    }
    for(const std::pair<const RoomType, std::string>& package : packages)
        OD_LOG_INF("Room package of " + getPackageRoomName(package.first) + ": " + package.second);
    if(missing.empty())
        OD_LOG_INF("Room packages: every packaged room is available");
    else
        OD_LOG_INF("Room packages: rooms without package (not available):" + missing);
}

//! \brief Replaces the kept packages under the lock.
void RoomPackages::setPackages(const std::map<RoomType, std::string>& packages)
{
    Registry& registry = getRegistry();
    std::lock_guard<std::mutex> lock(registry.mMutex);
    registry.mPackages = packages;
}

//! \brief A room that is not packaged is always available; a packaged room needs its package.
bool RoomPackages::isRoomAvailable(RoomType type)
{
    if(!isPackagedRoom(type))
        return true;
    Registry& registry = getRegistry();
    std::lock_guard<std::mutex> lock(registry.mMutex);
    return registry.mPackages.count(type) != 0;
}

//! \brief The kept folder of the room's package, or an empty text.
std::string RoomPackages::getPackageDirectory(RoomType type)
{
    Registry& registry = getRegistry();
    std::lock_guard<std::mutex> lock(registry.mMutex);
    std::map<RoomType, std::string>::const_iterator it = registry.mPackages.find(type);
    return (it == registry.mPackages.end()) ? std::string() : it->second;
}

//! \brief The kept folders in room type order (the order of the map).
std::vector<std::string> RoomPackages::getPackageDirectories()
{
    Registry& registry = getRegistry();
    std::lock_guard<std::mutex> lock(registry.mMutex);
    std::vector<std::string> directories;
    for(const std::pair<const RoomType, std::string>& package : registry.mPackages)
        directories.push_back(package.second);
    return directories;
}
