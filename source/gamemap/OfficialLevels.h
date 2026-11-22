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

#ifndef OFFICIALLEVELS_H
#define OFFICIALLEVELS_H

#include <cstddef>
#include <string>

//! \brief Rules that protect the shipped levels (the .level files below levels/skirmish, levels/multiplayer and
//! levels/campaign of the game data). Everything here works on explicit paths and tables, without the game
//! singletons, so that it can be tested on its own. MapHandler applies the rules to the running game.
namespace OfficialLevels
{
    //! \brief Extension of the shipped levels.
    static const char* const LEVEL_FILE_EXTENSION = ".level";

    //! \brief Extension of the maps the players make in the editor.
    static const char* const USER_MAP_EXTENSION = ".mmap";

    //! \brief One shipped level of the build: its key (path below levels/ with '/', e.g. "skirmish/Foo.level")
    //! and the SHA-256 of its content as 64 lower case hex digits.
    struct ChecksumEntry
    {
        const char* mKey;
        const char* mSha256;
    };

    //! \brief Result of comparing a level file with the checksums of the build.
    enum class Verdict
    {
        NotOfficial, //!< The file is not inside a shipped level folder
        Unchanged,   //!< A shipped level whose content matches the build
        Modified,    //!< A shipped level whose content differs from the build
        NotShipped,  //!< A file inside a shipped level folder that the build does not know
        Unreadable   //!< A shipped level that could not be read
    };

    //! \brief Where an editor save is written to.
    struct EditorSaveTarget
    {
        EditorSaveTarget() :
            mRedirected(false)
        {}

        //! \brief The file that is written.
        std::string mPath;

        //! \brief True when the save was turned into an own copy in the user level folder.
        bool mRedirected;
    };

    //! \brief Returns the SHA-256 of data as 64 lower case hex digits.
    std::string computeSha256(const std::string& data);

    //! \brief Returns the checksum of a level file content: the SHA-256 of the content without carriage returns, so
    //! that the line endings of a checkout do not matter.
    std::string computeLevelChecksum(const std::string& content);

    //! \brief Tells whether filePath lies inside levelsRoot/skirmish, levelsRoot/multiplayer or levelsRoot/campaign
    //! (at any depth, also through links). The folders are compared as file system objects, not as text.
    //! \param key Set to the path below levelsRoot with '/' separators, e.g. "campaign/wing1/Mossgate.level".
    //! \return False if the file is outside these folders.
    bool getOfficialKey(const std::string& filePath, const std::string& levelsRoot, std::string& key);

    //! \brief Returns the checksum stored for key in the table, or nullptr. On Windows the key is compared without
    //! regard to case, as the file system does.
    const char* findChecksum(const std::string& key, const ChecksumEntry* entries, std::size_t count);

    //! \brief Compares a level file with the checksum table of the build.
    Verdict verifyLevelFile(const std::string& filePath, const std::string& levelsRoot, const ChecksumEntry* entries,
        std::size_t count);

    //! \brief Tells whether this build was made with the developer option.
    bool isDeveloperModeBuild();

    //! \brief Tells whether a level with the given verdict may be loaded. A changed shipped level is always rejected,
    //! except in a developer build outside of multiplayer.
    bool mayLoad(Verdict verdict, bool multiplayer);

    //! \brief Tells whether the editor may open a file: a shipped level only with the hidden option.
    bool mayEditorOpen(bool officialLevel, bool editOfficialLevels);

    //! \brief Gives a map name of the editor the extension of the player maps: ".level" becomes ".mmap", any other
    //! name gets ".mmap" appended. An empty name, "." and ".." stay as they are.
    std::string toUserMapName(const std::string& fileName);

    //! \brief Gives the name of a saved game the extension the Load menu lists: a trailing ".mmap" (a game played
    //! on an own map) becomes ".level", every other name stays as it is. The SK-/MP- prefix is not touched.
    std::string toSavedGameName(const std::string& fileName);

    //! \brief Decides where an editor save goes. A shipped level is written in place only with the hidden option;
    //! without it the save becomes an own copy (stem + ".mmap", "-2", "-3"... if taken) in the user skirmish folder
    //! (user multiplayer folder for a multiplayer level). A save under a new name (saveAs) outside the shipped folders
    //! gets the extension of the player maps; a save in place keeps its file name.
    EditorSaveTarget resolveEditorSaveTarget(const std::string& target, bool saveAs, const std::string& levelsRoot,
        bool editOfficialLevels, const std::string& userSkirmishFolder, const std::string& userMultiplayerFolder);
}

#endif // OFFICIALLEVELS_H
