/*! \file   ODApplication.cpp
 *  \author Ogre team, andrewbuck, oln, StefanP.MUC
 *  \date   07 April 2011
 *  \brief  Class ODApplication containing everything to start the game
 *
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

#ifndef ODAPPLICATION_H
#define ODAPPLICATION_H

#include <string>
namespace boost
{
namespace program_options
{
class variables_map;
}
}

namespace Ogre {
class Root;
}

class LogManager;

//! \brief Base class which manages the startup of OpenDungeons.
class ODApplication
{
public:
    ODApplication()
    {}
    ~ODApplication()
    {}

    //! \brief Initializes the Application along with the ResourceManager
    void startGame(boost::program_options::variables_map& options);

    static double turnsPerSecond;
    static const std::string VERSION;
    static const std::string VERSIONSTRING;
    static const std::string POINTER_INFO_STRING;
    //! \brief Text box at the hand that shows the hand cooldown of a campaign level (HL2).
    static const std::string HAND_COOLDOWN_STRING;
    //! \brief Welcome line with the version shown by the debug text box; printable characters only.
    static std::string MOTD;

private:
    ODApplication(const ODApplication&) = delete;
    ODApplication& operator=(const ODApplication&) = delete;

    //! \brief Normal launch mode. Creates everything to be client and server
    void startClient();
    //! \brief Server mode. Creates only the needed to launch a level. Note that this is to be used without gui
    void startServer();
};

#endif // ODAPPLICATION_H
