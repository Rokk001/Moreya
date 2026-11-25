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

#ifndef CONTENTPACKAGES_H
#define CONTENTPACKAGES_H

#include <sys/types.h>
#include <sys/stat.h>

#include <cstddef>
#include <fstream>
#include <map>
#include <string>
#include <vector>

//! \brief The content packages of the game. The game data of the public repository holds the code side only; the
//! content of the game (models, textures, interface art, portraits, sounds, levels and data tables) comes from content
//! packages. A content package is a folder with a Package.cfg that names it in a line "Content=<package name>"; inside
//! the package every file lies at the same relative path as in the game data (models/, materials/, gui/, sounds/,
//! levels/, config/, particles/). The packages are searched in the same folders as the wing and room packages (see
//! CampaignPackages::getPackageFolders): the subfolders of levels/campaign/ of the game data and of the folder named by
//! MOREYA_CONTENT_DIR. Every package of getRequiredPackages() must be there; without them the game tells the player
//! that the content is missing and quits.
//!
//! A file of the game data is looked up first in the game data and then at the same relative path in every found
//! content package (resolveFile). The lookup part of this header has no other dependencies and no source file, so
//! that every part of the game and the small probes of the checks can use it; finding the packages on disk
//! (discover) lives in ContentPackages.cpp.
namespace ContentPackages
{
    //! Key of the definition line that names a content package
    extern const std::string CONTENT_KEY;
    //! Exit code of the game when it quits because content packages are missing
    const int MISSING_CONTENT_EXIT_CODE = 7;

    //! \brief The content packages the game needs, sorted by name.
    const std::vector<std::string>& getRequiredPackages();

    //! \brief The content package named in a definition text (the value of the first line "Content=<name>"), or an
    //! empty text when the text names none.
    std::string parseDefinition(const std::string& definition);

    //! \brief Reads every subfolder with a Package.cfg of the folders that names a content package, folder by folder
    //! and in name order inside a folder. The first package of a name wins. Missing folders are skipped.
    std::map<std::string, std::string> findPackages(const std::vector<std::string>& folders);

    //! \brief Searches the content packages of the game data and MOREYA_CONTENT_DIR, keeps them for the lookup of
    //! files and logs the missing ones.
    void discover(const std::string& gameDataPath);

    //! \brief The required content packages that were not found by discover() or setPackages(), sorted by name.
    std::vector<std::string> getMissingPackages();

    //! \brief The message shown to the player when content packages are missing.
    std::string getMissingContentMessage(const std::vector<std::string>& missing);

    //! \brief Remembers that the game refused to start because content packages are missing.
    void setStartRefused(bool refused);

    //! \brief True when the game refused to start because content packages are missing.
    bool isStartRefused();

    //! \brief State of the lookup: the game data folder and the folders of the found packages by name.
    struct Registry
    {
        std::string mGameDataPath;
        std::map<std::string, std::string> mPackages;
    };

    //! \brief The one registry of the program.
    inline Registry& getRegistry()
    {
        static Registry registry;
        return registry;
    }

    //! \brief Replaces the game data folder and the found packages (the result of discover()), for tools and tests.
    inline void setPackages(const std::string& gameDataPath, const std::map<std::string, std::string>& packages)
    {
        Registry& registry = getRegistry();
        registry.mGameDataPath = gameDataPath;
        registry.mPackages = packages;
    }

    //! \brief The folders of every found content package, in name order.
    inline std::vector<std::string> getPackageDirectories()
    {
        std::vector<std::string> directories;
        const Registry& registry = getRegistry();
        for(std::map<std::string, std::string>::const_iterator it = registry.mPackages.begin();
            it != registry.mPackages.end(); ++it)
        {
            directories.push_back(it->second);
        }
        return directories;
    }

    //! \brief The path with every backslash replaced by a slash, so that paths of both spellings compare equal.
    inline std::string toForwardSlashes(const std::string& path)
    {
        std::string result = path;
        for(std::string::iterator it = result.begin(); it != result.end(); ++it)
        {
            if(*it == '\\')
                *it = '/';
        }
        return result;
    }

    //! \brief The path of the game data file relative to the game data folder, or an empty text when the path does not
    //! lie in the game data folder (or no game data folder is known).
    inline std::string getRelativePath(const std::string& path)
    {
        const std::string root = toForwardSlashes(getRegistry().mGameDataPath);
        const std::string file = toForwardSlashes(path);
        if(root.empty() || (file.size() <= root.size()) || (file.compare(0, root.size(), root) != 0))
            return std::string();
        std::string relative = file.substr(root.size());
        while(!relative.empty() && ((relative[0] == '/') || (relative[0] == '\\')))
            relative.erase(0, 1);
        return relative;
    }

    //! \brief True when the file can be opened for reading.
    inline bool isReadableFile(const std::string& path)
    {
        std::ifstream file(path.c_str(), std::ios::binary);
        return file.is_open();
    }

    //! \brief The file of the game data: the path itself when the file is there, else the file at the same relative
    //! path in the first content package that has it, else the path unchanged (so that the caller reports it missing).
    inline std::string resolveFile(const std::string& path)
    {
        if(isReadableFile(path))
            return path;
        const std::string relative = getRelativePath(path);
        if(relative.empty())
            return path;
        const Registry& registry = getRegistry();
        for(std::map<std::string, std::string>::const_iterator it = registry.mPackages.begin();
            it != registry.mPackages.end(); ++it)
        {
            const std::string candidate = it->second + "/" + relative;
            if(isReadableFile(candidate))
                return candidate;
        }
        return path;
    }

    //! \brief The folder of the game data and the folders at the same relative path in every found content package,
    //! in that order; a folder outside the game data is returned alone. The folders are not checked for existence.
    inline std::vector<std::string> getDataFolders(const std::string& folder)
    {
        std::vector<std::string> folders;
        folders.push_back(folder);
        std::string relative = getRelativePath(folder);
        if(relative.empty())
            return folders;
        const Registry& registry = getRegistry();
        for(std::map<std::string, std::string>::const_iterator it = registry.mPackages.begin();
            it != registry.mPackages.end(); ++it)
        {
            folders.push_back(it->second + "/" + relative);
        }
        return folders;
    }

    //! \brief True when the path names an existing folder; slashes at its end are ignored.
    inline bool isDirectory(const std::string& path)
    {
        std::string folder = path;
        while((folder.size() > 1) && ((folder[folder.size() - 1] == '/') || (folder[folder.size() - 1] == '\\')))
            folder.erase(folder.size() - 1);
        struct stat info;
        return (stat(folder.c_str(), &info) == 0) && ((info.st_mode & S_IFMT) == S_IFDIR);
    }

    //! \brief The folder of the game data: the folder itself when it is there, else the folder at the same relative path
    //! in the first content package that has it, else the folder unchanged.
    inline std::string resolveFolder(const std::string& folder)
    {
        const std::vector<std::string> folders = getDataFolders(folder);
        for(std::vector<std::string>::const_iterator it = folders.begin(); it != folders.end(); ++it)
        {
            if(isDirectory(*it))
                return *it;
        }
        return folder;
    }

    //! Prefix of a marker line of a mixed data table and of a block line of its own rows file
    const std::string OWN_ROWS_MARKER = "#@own ";

    //! \brief The path of the own rows file of a mixed data table: ".own" before the extension of the table
    //! (config/global.cfg gives config/global.own.cfg).
    //!
    //! A mixed data table is an upstream table with rows the project wrote itself. Its public file keeps the upstream
    //! rows and has a marker line "#@own <n>" where a run of own rows was; the own rows lie in the own rows file of a
    //! content package, one block per marker: a line "#@own <n>" and the rows up to the next such line. Lines before
    //! the first block are its header. Helper::readFile puts every block in place of its marker (mergeOwnRows), so
    //! the game reads the whole table; scripts/config_own_rows.py does the same for the checks.
    inline std::string getOwnRowsPath(const std::string& path)
    {
        const std::string::size_type slash = path.find_last_of("/\\");
        const std::string::size_type dot = path.rfind('.');
        if((dot == std::string::npos) || ((slash != std::string::npos) && (dot < slash)))
            return path + ".own";
        return path.substr(0, dot) + ".own" + path.substr(dot);
    }

    //! \brief The number of a marker line "#@own <n>" (spaces at its end allowed), or -1 when the line is none.
    inline int getOwnRowsMarker(const std::string& line)
    {
        if(line.compare(0, OWN_ROWS_MARKER.size(), OWN_ROWS_MARKER) != 0)
            return -1;
        std::string::size_type index = OWN_ROWS_MARKER.size();
        int number = 0;
        bool hasDigit = false;
        while((index < line.size()) && (line[index] >= '0') && (line[index] <= '9'))
        {
            number = number * 10 + (line[index] - '0');
            hasDigit = true;
            ++index;
        }
        while((index < line.size()) && ((line[index] == ' ') || (line[index] == '\t') || (line[index] == '\r')))
            ++index;
        if(!hasDigit || (index != line.size()))
            return -1;
        return number;
    }

    //! \brief Reads the blocks of the own rows file of the table (found like every game data file, resolveFile) into
    //! blocks, by marker number. Line ends lose their carriage return. Returns false when there is no own rows file.
    inline bool readOwnRows(const std::string& tablePath, std::map<int, std::vector<std::string> >& blocks)
    {
        std::ifstream file(resolveFile(getOwnRowsPath(tablePath)).c_str(), std::ifstream::in);
        if(!file.good())
            return false;
        std::vector<std::string>* current = NULL;
        std::string line;
        while(std::getline(file, line))
        {
            if(!line.empty() && (line[line.size() - 1] == '\r'))
                line.erase(line.size() - 1);
            const int number = getOwnRowsMarker(line);
            if(number >= 0)
            {
                current = &blocks[number];
                current->clear();
                continue;
            }
            if(current != NULL)
                current->push_back(line);
        }
        return true;
    }

    //! \brief Puts the block of the own rows file in place of every marker line of the table lines. Returns the
    //! numbers of the markers without a block in missing and of the blocks without a marker in unused; both stay
    //! empty when the table has no markers. Without an own rows file (no content) the lines stay as they are, with
    //! the markers as comments, and hasOwnRows is false.
    inline void mergeOwnRows(const std::string& tablePath, std::vector<std::string>& lines, bool& hasOwnRows,
        std::vector<int>& missing, std::vector<int>& unused)
    {
        hasOwnRows = false;
        bool hasMarker = false;
        for(std::vector<std::string>::const_iterator it = lines.begin(); it != lines.end(); ++it)
        {
            if(getOwnRowsMarker(*it) >= 0)
            {
                hasMarker = true;
                break;
            }
        }
        if(!hasMarker)
            return;
        std::map<int, std::vector<std::string> > blocks;
        if(!readOwnRows(tablePath, blocks))
            return;
        hasOwnRows = true;
        std::map<int, bool> used;
        std::vector<std::string> merged;
        for(std::vector<std::string>::const_iterator it = lines.begin(); it != lines.end(); ++it)
        {
            const int number = getOwnRowsMarker(*it);
            if(number < 0)
            {
                merged.push_back(*it);
                continue;
            }
            std::map<int, std::vector<std::string> >::const_iterator block = blocks.find(number);
            if(block == blocks.end())
            {
                missing.push_back(number);
                continue;
            }
            used[number] = true;
            merged.insert(merged.end(), block->second.begin(), block->second.end());
        }
        for(std::map<int, std::vector<std::string> >::const_iterator it = blocks.begin(); it != blocks.end(); ++it)
        {
            if(used.find(it->first) == used.end())
                unused.push_back(it->first);
        }
        lines.swap(merged);
    }
}

#endif // CONTENTPACKAGES_H
