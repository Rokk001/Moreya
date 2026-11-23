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

#ifndef ROOMPACKAGES_H
#define ROOMPACKAGES_H

#include "rooms/RoomType.h"

#include <map>
#include <string>
#include <vector>

//! \brief Finds the room packages on disk. Some rooms take their assets (meshes, materials, textures, particles,
//! sounds) from a room package instead of the public game data. A room package is a folder with a Package.cfg that
//! names its room in a line "Room=<room name>"; inside the package the assets lie at the same relative paths as in
//! the game data (models/, materials/scripts/, materials/textures/, particles/, sounds/). The packages are searched
//! in the same folders as the wing packages of the campaign (see CampaignPackages::getPackageFolders): the
//! subfolders of levels/campaign/ of the game data and of the folder named by MOREYA_CONTENT_DIR. The code of every
//! room stays in the game; a packaged room whose package is missing is unavailable: it cannot be built, its build
//! button is hidden, and a level that contains it loads without it (its tiles stay claimed ground of its seat).
namespace RoomPackages
{
    //! Key of the definition line that names the room of a room package
    extern const std::string ROOM_KEY;

    //! \brief The rooms that take their assets from a room package, in room type order.
    const std::vector<RoomType>& getPackagedRooms();

    //! \brief True when the assets of the room come from a room package.
    bool isPackagedRoom(RoomType type);

    //! \brief The room name a Package.cfg uses for a packaged room ("Tavern", "GhostRoom", ...); empty for a room
    //! that is not packaged.
    const std::string& getPackageRoomName(RoomType type);

    //! \brief The packaged room named in a definition text (the first line "Room=<name>" with the name of a packaged
    //! room), or nullRoomType when the text names none.
    RoomType parseDefinition(const std::string& definition);

    //! \brief Reads every subfolder with a Package.cfg of the folders that names a packaged room, folder by folder and
    //! in name order inside a folder. The first package of a room wins. Missing folders are skipped.
    std::map<RoomType, std::string> findPackages(const std::vector<std::string>& folders);

    //! \brief Searches the room packages of the game data and MOREYA_CONTENT_DIR, keeps them for
    //! isRoomAvailable() and logs the rooms without package.
    void discover(const std::string& gameDataPath);

    //! \brief Replaces the kept packages (the result of discover()), for tools and tests.
    void setPackages(const std::map<RoomType, std::string>& packages);

    //! \brief True for every room that needs no package and for a packaged room whose package was found and, while
    //! the client is connected to a server that sent its room packages (setServerPackages), the server has too.
    bool isRoomAvailable(RoomType type);

    //! \brief The room names of the found packages (the kept packages, not limited by setServerPackages), sorted.
    //! The client sends them with hello and the server with loadLevel.
    std::vector<std::string> getAvailablePackageNames();

    //! \brief Limits the packaged rooms isRoomAvailable() offers to those the server named: a client may have more
    //! room packages than its server, and the server's packages govern. Kept until clearServerPackages().
    void setServerPackages(const std::vector<std::string>& names);

    //! \brief Removes the limit of setServerPackages(), so that only the found packages count again.
    void clearServerPackages();

    //! \brief The folder of the package of the room; empty when the room is not packaged or its package is missing.
    std::string getPackageDirectory(RoomType type);

    //! \brief The folders of every found room package, in room type order.
    std::vector<std::string> getPackageDirectories();
}

#endif // ROOMPACKAGES_H
