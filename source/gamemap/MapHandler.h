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


#ifndef MAPHANDLER_H
#define MAPHANDLER_H

#include <string>
#include <vector>
#include "game/Campaign.h"
#include "gamemap/OfficialLevels.h"

class GameMap;

enum class GameEntityType;

//! \brief A small structure storing level info for the player
struct LevelInfo
{
    //! \brief Creates empty level info that is not a sandbox level.
    LevelInfo() :
        mIsSandbox(false)
    {}

    //! \brief The level visible name
    std::string mLevelName;

    //! \brief The level description, player's slot, size, ...
    std::string mLevelDescription;

    //! \brief True for a sandbox level (no goals, hero toolbox and invasions)
    bool mIsSandbox;

    //! \brief The name of a sandbox realm (empty for a sandbox level that is not one) and the level file of the realm after it
    std::string mSandboxRealm;
    std::string mSandboxNext;

    //! \brief Optional campaign snapshot, absent in levels and legacy saves.
    CampaignSave mCampaignSave;
};

namespace MapHandler
{
    //! \brief Reads the campaign definition and user progress for load eligibility without opening its menu.
    bool loadCampaignProgress();
    //! \brief Loads a level or saved game file into the game map, including the optional [Triggers] section.
    //! \param fileName The level file to read.
    //! \param gameMap The game map to fill.
    //! \return False if the file or one of its sections is invalid.
    //! \brief Loads supported level formats and reports every rejected section.
    //! \param strictOfficialCheck True (multiplayer, and the default): a changed shipped level is always rejected.
    //! False: a developer build loads a changed shipped level (single player and editor).
    bool readGameMapFromFile(const std::string& fileName, GameMap& gameMap, bool strictOfficialCheck = true);

    //! \brief Tells whether a file version header (e.g. "OpenDungeons_Version:0.7.4.20") can be loaded.
    //! Any build number of a supported release (0.7.1, 0.7.2, 0.7.4) is accepted, as is the running version.
    bool isSupportedVersionHeader(const std::string& header);

    //! \brief Returns the exact reason why the last readGameMapFromFile call failed (empty if it did not fail).
    const std::string& getLastLoadError();

    //! \brief Writes the game map to a level file, including the [Triggers] section if the level has a script.
    //! \param fileName The level file to write.
    //! \param gameMap The game map to save.
    //! \return False if the file could not be written.
    //! \brief Saves map entities, including loose harvested herb bundles.
    bool writeGameMapToFile(const std::string& fileName, GameMap& gameMap);

    bool readGameEntity(GameMap& gameMap, const std::string& item, GameEntityType type, std::stringstream& levelFile);

    //! \brief Reads the optional [Dirt] section (lines x y dirt) and the optional [DirtPiles] section (lines kind
    //! creatureClass x y dirtLeft ageTurns) of a level or saved game. When a section is missing the stream is left where
    //! it was, so levels and saves from before the dirt exist still load (no dirt, no piles).
    //! \param gameMap The game map whose tiles get the dirt and which gets the piles.
    //! \param levelFile The level stream, positioned behind the gift boxes.
    //! \return False if a section is started but invalid.
    bool readDirtSections(GameMap& gameMap, std::stringstream& levelFile);

    bool loadEquipments(const std::string& fileName, GameMap& gameMap);

    bool loadCreatureDefinition(const std::string& fileName, GameMap& gameMap);

    //! \brief Reads the main user map info. Returns true if the level could be read and levelInfo is set to
    //! corresponding info. Returns false otherwise.
    //! \brief Reads supported level headers regardless of the executable build suffix.
    bool getMapInfo(const std::string& fileName, LevelInfo& levelInfo);

    //! \brief Counts the number of all seats in the levelfile, needed to initialize the structure
    //! everVisitedflagpool plus map Size X and map Size Y

    void getXandYandSeatsNumber(std::stringstream& ss,int& xx, int& yy, int& numberOfSeats);
    //! \brief Level extension constant, used in different GUI modes.
    static const std::string LEVEL_EXTENSION = OfficialLevels::LEVEL_FILE_EXTENSION;
    //! \brief Extension of the maps made in the editor (the shipped levels keep LEVEL_EXTENSION).
    static const std::string USER_MAP_EXTENSION = OfficialLevels::USER_MAP_EXTENSION;

    //! \brief Tells whether an extension (with its dot) is the one of a level: LEVEL_EXTENSION or USER_MAP_EXTENSION.
    bool isLevelFileExtension(const std::string& extension);

    //! \brief Adds the levels of a folder to the list: both extensions, LEVEL_EXTENSION and USER_MAP_EXTENSION.
    //! \return False if the folder does not exist.
    bool fillLevelFilesList(const std::string& path, std::vector<std::string>& listFiles);

    //! \brief Tells whether a file lies inside one of the shipped level folders of the game data.
    bool isOfficialLevelPath(const std::string& fileName);

    //! \brief Tells whether the hidden option EditOfficialLevels of the user config file is on.
    bool isEditOfficialLevelsEnabled();

    //! \brief Compares a shipped level with the checksum compiled into the game.
    //! \param multiplayer True for a multiplayer game, where a changed shipped level is always rejected.
    //! \param message Set to the reason shown to the player when the level is rejected.
    //! \return False if the level must not be loaded.
    bool checkOfficialLevel(const std::string& fileName, bool multiplayer, std::string& message);

    //! \brief Tells whether the editor may open a file: a shipped level only with the hidden option, and only when
    //! it passes checkOfficialLevel.
    //! \param message Set to the reason shown to the player when the file is refused.
    bool checkEditorMayOpen(const std::string& fileName, std::string& message);

    //! \brief Decides where an editor save of target is written (see OfficialLevels::resolveEditorSaveTarget), with
    //! the folders of the game.
    OfficialLevels::EditorSaveTarget resolveEditorSaveTarget(const std::string& target, bool saveAs,
        bool editOfficialLevels);
};

#endif // MAPHANDLER_H
