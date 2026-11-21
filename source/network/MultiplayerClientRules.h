/*
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

#ifndef MULTIPLAYERCLIENTRULES_H
#define MULTIPLAYERCLIENTRULES_H

#include <cstdint>
#include <string>
#include <vector>

//! \brief Decisions of the multiplayer client that do not depend on the game objects, so that a
//! small probe can check them without building the game.
namespace MultiplayerClientRules
{

//! \brief Highest valid network port.
const uint32_t MAX_PORT = 65535;

//! \brief Seconds the lobby waits for the server to start the game after the host pressed Start,
//! before it tells the host that the server did not start it.
const float LAUNCH_ANSWER_SECONDS = 5.0f;

//! \brief Message shown in the main menu after the connection to the server was lost.
const char* const LOST_SERVER_MESSAGE = "The connection to the server was lost.";

//! \brief Message shown in the lobby when not every seat has a player, a team and a faction.
const char* const SEATS_NOT_FILLED_MESSAGE = "Every seat needs a player, a team and a faction before the game can start.";

//! \brief Message shown in the lobby when the server did not start the game after Start was pressed.
const char* const LAUNCH_NOT_ANSWERED_MESSAGE = "The server did not start the game. Check that every seat is filled.";

//! \brief Message shown in the join menu for a port that is not a number from 1 to 65535.
const char* const INVALID_PORT_MESSAGE = "Please enter a port from 1 to 65535.";

//! \brief Tells whether the client takes part in a multiplayer game: it talks to a server over the
//! network, and that server is either remote (no local server runs) or the local multiplayer host.
//! A single player game, a loaded game, the editor and a replay are not multiplayer.
inline bool isMultiplayerSession(bool clientOnNetwork, bool localServerRunning, bool localServerMultiplayer)
{
    if(!clientOnNetwork)
        return false;
    return !localServerRunning || localServerMultiplayer;
}

//! \brief Tells whether the frame skips reading the server while the local game is paused. Only a
//! single player game stops there: in multiplayer the other players go on, so the client keeps
//! reading and acknowledging turns while its pause menu is open.
inline bool pauseStopsNetwork(bool gameStarted, bool paused, bool exitRequested, bool multiplayer)
{
    return gameStarted && paused && !exitRequested && !multiplayer;
}

//! \brief Where the confirmed defeat debriefing leads.
enum class DebriefingExit
{
    campaignMenu,
    skirmishSubMenu,
    multiplayerSubMenu
};

//! \brief Chooses the menu that the confirmed defeat debriefing opens: the campaign menu in a
//! campaign, the multiplayer sub-menu after a multiplayer game, otherwise the skirmish sub-menu.
inline DebriefingExit debriefingExit(bool campaignActive, bool multiplayer)
{
    if(campaignActive)
        return DebriefingExit::campaignMenu;
    if(multiplayer)
        return DebriefingExit::multiplayerSubMenu;
    return DebriefingExit::skirmishSubMenu;
}

//! \brief What the lobby shows for one seat: whether its player, team and faction are chosen.
struct LobbySeatChoice
{
    bool mPlayerChosen;
    bool mTeamChosen;
    bool mFactionChosen;
};

//! \brief Tells whether every seat has a player, a team and a faction, which the server requires
//! before it starts the game. An empty list is not filled.
inline bool areSeatsFilled(const std::vector<LobbySeatChoice>& seats)
{
    if(seats.empty())
        return false;
    for(std::vector<LobbySeatChoice>::const_iterator it = seats.begin(); it != seats.end(); ++it)
    {
        if(!it->mPlayerChosen || !it->mTeamChosen || !it->mFactionChosen)
            return false;
    }
    return true;
}

//! \brief Tells whether the lobby has waited long enough for the start of the game to report that
//! the server did not start it. Once reported, it is not reported again.
inline bool isLaunchUnanswered(float waitedSeconds, bool alreadyReported)
{
    return !alreadyReported && waitedSeconds >= LAUNCH_ANSWER_SECONDS;
}

//! \brief Reads the port typed in the join menu. Leading and trailing spaces are ignored; an empty
//! field gives the default port. Returns false for anything that is not a number from 1 to 65535
//! (and for an empty field whose default is not in that range).
inline bool parsePort(const std::string& text, uint32_t defaultPort, uint32_t& port)
{
    std::string::size_type first = text.find_first_not_of(" \t");
    if(first == std::string::npos)
    {
        if(defaultPort == 0 || defaultPort > MAX_PORT)
            return false;
        port = defaultPort;
        return true;
    }
    std::string::size_type last = text.find_last_not_of(" \t");
    uint32_t value = 0;
    for(std::string::size_type i = first; i <= last; ++i)
    {
        char c = text[i];
        if(c < '0' || c > '9')
            return false;
        value = value * 10 + static_cast<uint32_t>(c - '0');
        if(value > MAX_PORT)
            return false;
    }
    if(value == 0)
        return false;
    port = value;
    return true;
}

}

#endif // MULTIPLAYERCLIENTRULES_H
