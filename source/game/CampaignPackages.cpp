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

#include "game/CampaignPackages.h"

#include "utils/Helper.h"
#include "utils/LogManager.h"

#include <boost/filesystem.hpp>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

const std::string CampaignPackages::DEFINITION_FILE = "Package.cfg";
const std::string CampaignPackages::CONTENT_VARIABLE = "MOREYA_CONTENT_DIR";
const std::string CampaignPackages::MISSING_WING_TEXT = "Coming in Early Access";

namespace
{
//! Folder of the packages below the game data
const std::string GAME_PACKAGE_FOLDER = "levels/campaign/";
} // namespace

//! \brief levels/campaign/ of the game data, then the folder of MOREYA_CONTENT_DIR when it is set.
std::vector<std::string> CampaignPackages::getPackageFolders(const std::string& gameDataPath)
{
    std::vector<std::string> folders;
    folders.push_back(gameDataPath + GAME_PACKAGE_FOLDER);
    const char* content = std::getenv(CONTENT_VARIABLE.c_str());
    if((content != nullptr) && (content[0] != '\0'))
        folders.push_back(content);
    return folders;
}

//! \brief Reads the Package.cfg of every package subfolder, sorted by folder name inside each searched folder.
std::vector<CampaignPackage> CampaignPackages::findPackages(const std::vector<std::string>& folders)
{
    std::vector<CampaignPackage> packages;
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
            if(boost::filesystem::is_regular_file(it->path() / DEFINITION_FILE, error))
                directories.push_back(it->path());
        }
        std::sort(directories.begin(), directories.end());

        for(const boost::filesystem::path& directory : directories)
        {
            std::ifstream file((directory / DEFINITION_FILE).string().c_str(), std::ios::binary);
            if(!file.is_open())
                continue;

            std::ostringstream text;
            text << file.rdbuf();
            CampaignPackage package;
            package.mDirectory = directory.generic_string();
            package.mDefinition = text.str();
            packages.push_back(package);
        }
    }
    return packages;
}

//! \brief Reads all packages into the campaign; the wings without a package are logged as missing.
bool CampaignPackages::loadCampaign(Campaign& campaign, const std::string& gameDataPath)
{
    std::vector<CampaignPackage> packages = findPackages(getPackageFolders(gameDataPath));
    bool loaded = campaign.importPackages(packages);
    std::string missing;
    for(uint32_t wing = 1; wing <= Campaign::NUM_WINGS; ++wing)
    {
        if(!campaign.isWingAvailable(wing))
            missing += " " + Helper::toString(wing);
    }
    OD_LOG_INF("Campaign packages found: " + Helper::toString(static_cast<uint32_t>(packages.size()))
        + ", campaign levels: " + Helper::toString(static_cast<uint32_t>(campaign.getNumLevels()))
        + (missing.empty() ? std::string(", every wing is there") : ", wings without package:" + missing));
    return loaded;
}

//! \brief The package file of the level, or the file below levels/ of the game data.
std::string CampaignPackages::getLevelFile(const CampaignLevel& level, const std::string& gameDataPath)
{
    if(!level.mPath.empty())
        return level.mPath;
    return gameDataPath + "levels/" + level.mFile;
}
