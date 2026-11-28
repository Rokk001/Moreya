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

#ifndef CAMPAIGNPACKAGES_H
#define CAMPAIGNPACKAGES_H

#include "game/Campaign.h"

#include <string>
#include <vector>

//! \brief Finds the wing packages of the campaign on disk. A wing package is a folder with a Package.cfg (the
//! campaign entries of the wing) and the level files of the wing. The game searches the subfolders of
//! levels/campaign/ of the game data (wing 1 comes with the game; a release build adds the content packages there)
//! and the subfolders of the folder named by the environment variable MOREYA_CONTENT_DIR. The code reads the
//! packages only; no campaign text or level is part of the code.
namespace CampaignPackages
{
    //! Name of the definition file of a wing package
    extern const std::string DEFINITION_FILE;
    //! Environment variable naming an additional folder of wing packages
    extern const std::string CONTENT_VARIABLE;
    //! \brief Text shown on the campaign map for a wing whose package is missing, in the chosen language
    std::string getMissingWingText();

    //! \brief The folders whose subfolders are searched for packages: levels/campaign/ of the game data, then the
    //! folder of MOREYA_CONTENT_DIR when the variable is set and not empty.
    std::vector<std::string> getPackageFolders(const std::string& gameDataPath);

    //! \brief Reads every subfolder with a Package.cfg of the folders, folder by folder and in name order inside a
    //! folder. Missing folders are skipped.
    std::vector<CampaignPackage> findPackages(const std::vector<std::string>& folders);

    //! \brief Reads the packages of the game data and MOREYA_CONTENT_DIR into the campaign and logs the missing
    //! wings. Returns false if no campaign level was found.
    bool loadCampaign(Campaign& campaign, const std::string& gameDataPath);

    //! \brief The level file of a campaign level: the file in its package folder, or the file below the "levels"
    //! directory of the game data for a definition that was not read from a package.
    std::string getLevelFile(const CampaignLevel& level, const std::string& gameDataPath);
}

#endif // CAMPAIGNPACKAGES_H
