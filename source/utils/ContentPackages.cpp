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

#include "utils/ContentPackages.h"

#include "game/CampaignPackages.h"
#include "utils/LogManager.h"

#include <boost/filesystem.hpp>

#include <algorithm>
#include <sstream>

const std::string ContentPackages::CONTENT_KEY = "Content";

namespace
{
//! The content packages the game needs, sorted by name; fixed for this branch, the same table as REQUIRED_PACKAGES in
//! scripts/content_packages.py
const char* const REQUIRED_PACKAGES[] =
{
    "core-config",
    "core-gui",
    "core-levels",
    "core-menu",
    "core-models",
    "core-portraits",
    "core-sounds",
    "creatures",
    "doors",
    "effects",
    "equipment",
    "gui-skin",
    "items",
    "lang-en",
    "room-arena",
    "room-casino",
    "room-crypt",
    "room-dormitory",
    "room-dungeon-temple",
    "room-hatchery",
    "room-library",
    "room-portal",
    "room-portal-wave",
    "room-prison",
    "room-stone-bridge",
    "room-torture",
    "room-training-hall",
    "room-treasury",
    "room-wooden-bridge",
    "room-workshop",
    "terrain",
    "traps",
};

//! True once the game refused to start because content packages are missing
bool startRefused = false;
} // namespace

//! \brief The fixed table as a vector, built once.
const std::vector<std::string>& ContentPackages::getRequiredPackages()
{
    static const std::vector<std::string> packages(REQUIRED_PACKAGES,
        REQUIRED_PACKAGES + sizeof(REQUIRED_PACKAGES) / sizeof(REQUIRED_PACKAGES[0]));
    return packages;
}

//! \brief The value of the first line "Content=<name>"; spaces and a carriage return around the name are removed.
std::string ContentPackages::parseDefinition(const std::string& definition)
{
    std::istringstream lines(definition);
    std::string line;
    const std::string prefix = CONTENT_KEY + "=";
    while(std::getline(lines, line))
    {
        if(line.compare(0, prefix.size(), prefix) != 0)
            continue;
        std::string name = line.substr(prefix.size());
        const std::string::size_type first = name.find_first_not_of(" \t\r");
        if(first == std::string::npos)
            return std::string();
        const std::string::size_type last = name.find_last_not_of(" \t\r");
        return name.substr(first, last - first + 1);
    }
    return std::string();
}

//! \brief Reads the Package.cfg of every package subfolder, sorted by folder name inside each searched folder.
std::map<std::string, std::string> ContentPackages::findPackages(const std::vector<std::string>& folders)
{
    std::map<std::string, std::string> packages;
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
            const std::string name = parseDefinition(text.str());
            if(name.empty() || (packages.count(name) != 0))
                continue;
            packages[name] = directory.generic_string();
        }
    }
    return packages;
}

//! \brief Finds the packages in the folders of the wing packages, keeps them and logs the missing ones.
void ContentPackages::discover(const std::string& gameDataPath)
{
    const std::map<std::string, std::string> packages = findPackages(CampaignPackages::getPackageFolders(gameDataPath));
    setPackages(gameDataPath, packages);
    for(const std::pair<const std::string, std::string>& package : packages)
        OD_LOG_INF("Content package " + package.first + ": " + package.second);
    const std::vector<std::string> missing = getMissingPackages();
    if(missing.empty())
        OD_LOG_INF("Content packages: every content package is there");
    else
        OD_LOG_ERR(getMissingContentMessage(missing));
}

//! \brief The required names without a kept package.
std::vector<std::string> ContentPackages::getMissingPackages()
{
    std::vector<std::string> missing;
    const Registry& registry = getRegistry();
    for(const std::string& name : getRequiredPackages())
    {
        if(registry.mPackages.count(name) == 0)
            missing.push_back(name);
    }
    return missing;
}

//! \brief One text for the message box and the log: what is missing and where the game looks for it.
std::string ContentPackages::getMissingContentMessage(const std::vector<std::string>& missing)
{
    std::string names;
    for(const std::string& name : missing)
        names += (names.empty() ? "" : ", ") + name;
    return "The content of Moreya is missing (content packages: " + names + "). The game data of this build holds "
        "the game code only; the content comes with the game on Steam. Point the environment variable "
        + CampaignPackages::CONTENT_VARIABLE + " at the folder of the content packages, or install the game with "
        "its content. The game quits now.";
}

//! \brief Keeps the flag for main().
void ContentPackages::setStartRefused(bool refused)
{
    startRefused = refused;
}

//! \brief The kept flag.
bool ContentPackages::isStartRefused()
{
    return startRefused;
}
