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

#ifndef STARTGAMEREFUSAL_H
#define STARTGAMEREFUSAL_H

#include <cstdint>

//! \brief Why the server refuses to start the game a client asked for with seatConfigurationSet. The reason is
//! sent as an int32_t with ServerNotificationType::startGameRefused. The header has no other dependencies so
//! that the server, the client and small probes can share it.
namespace StartGameRefusal
{

//! \brief Reason code sent with startGameRefused. Values are fixed on the wire: append new reasons at the end
//! and move LAST_REASON with them.
enum class Reason : int32_t
{
    //! A seat that is not a rogue seat has no player, team or faction yet.
    seatsIncomplete = 0,
    //! The client that asked is not the player that configures the game.
    notHost = 1,
    //! The server is not in the seat configuration any more (or not yet).
    wrongState = 2
};

//! \brief Last value of Reason. Must be updated when a new reason is appended to the enum.
const Reason LAST_REASON = Reason::wrongState;

//! \brief Returns true if the value read from a packet is a Reason.
inline bool isReasonValue(int32_t value)
{
    return (value >= 0) && (value <= static_cast<int32_t>(LAST_REASON));
}

}

#endif // STARTGAMEREFUSAL_H
