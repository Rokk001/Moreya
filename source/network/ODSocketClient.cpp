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

#include "ODSocketClient.h"
#include "network/ODPacket.h"
#include "network/ServerNotification.h"

#include "utils/Helper.h"
#include "utils/LogManager.h"

#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/filesystem.hpp>

#include <optional>
#include <vector>

//! \brief Connects to the server through the transport and opens the replay file; returns false if resolving or connecting fails.
bool ODSocketClient::connect(const std::string& host, const int port, uint32_t timeout, const std::string& outputReplayFilename)
{
    mSource = ODSource::none;

    // The transport resolves the host and connects (for TCP see TcpNetConnection::connect, which also
    // reports a host that cannot be resolved as a connection error). The status numbers are those of SFML.
    NetStatus status = mConnection->connect(host, port, timeout);
    if (status != NetStatus::Done)
    {
        OD_LOG_ERR("Could not connect to distant server status="
            + Helper::toString(static_cast<int>(status)));
        mConnection->disconnect();
        return false;
    }
    OD_LOG_INF("Connected to server successfully");

    mOutputReplayFilename = outputReplayFilename;

    mReplayOutputStream.open(mOutputReplayFilename, std::ios::out | std::ios::binary);
    mGameClock.restart();
    mSource = ODSource::network;
    return true;
}

bool ODSocketClient::replay(const std::string& filename)
{
    OD_LOG_INF("Reading replay from file " + filename);
    mReplayInputStream.open(filename, std::ios::in | std::ios::binary);
    mGameClock.restart();
    mSource = ODSource::file;
    return true;
}

//! \brief Closes the connection or replay and clears negotiated and subscribed client state.
void ODSocketClient::disconnect(bool keepReplay)
{
    mInfirmaryWindowOpen = false;
    mDungeonbookRosterOpen = false;
    mSupportsLiveNickname = false;
    mSupportsCreatureMood = false;
    mSupportsCreatureActivity = false;
    mSupportsCreaturePanel = false;
    mSupportsCreatureProgress = false;
    mSupportsCosmeticEvents = false;
    mSupportsDungeonbookRoster = false;
    mPendingTimestamp = -1;
    ODSource src = mSource;
    mSource = ODSource::none;
    switch(src)
    {
        case ODSource::none:
        {
            // Nothing to do
            return;
        }
        case ODSource::network:
        {
            // Remove any remaining client sockets from the socket selector,
            // if there is any left. The transport does both (TcpNetConnection::disconnect).
            mConnection->disconnect();
            break;
        }
        case ODSource::file:
        {
            mReplayInputStream.close();
            return;
        }
        default:
            assert(false);
            break;
    }

    mReplayOutputStream.close();
    // Delete the replay newly created if asked to.
    if (!keepReplay)
        boost::filesystem::remove(mOutputReplayFilename);
    mOutputReplayFilename.clear();
}

//! \brief Tells whether a message can be read: waits up to miliseconds on the transport, or checks the replay clock.
bool ODSocketClient::isDataAvailable(int miliseconds)
{
    switch(mSource)
    {
        case ODSource::none:
        {
            return false;
        }
        case ODSource::network:
        {
            // There is only 1 socket in the selector so it should be ready if
            // wait returns true but it doesn't hurt to return isReady...
            // The transport waits on its own selector (TcpNetConnection::waitForData).
            return mConnection->waitForData(miliseconds);
        }
        case ODSource::file:
        {
            if(mReplayInputStream.eof())
                return false;

            if(mPendingTimestamp == -1)
                mPendingTimestamp = mPendingPacket.readPacket(mReplayInputStream);

            if(mPendingTimestamp < 0)
                return false;

            if(mPendingTimestamp < mGameClock.getElapsedTime().asMilliseconds())
                return true;

            return false;
        }
        default:
            assert(false);
            break;
    }

    return false;
}

//! \brief Sends the packet to the server and reports the result as an ODComStatus.
ODSocketClient::ODComStatus ODSocketClient::send(ODPacket& s)
{
    if(mSource != ODSource::network)
        return ODComStatus::OK;

    NetStatus status = mConnection->send(s);
    if (status == NetStatus::Done)
        return ODComStatus::OK;

    OD_LOG_ERR("Could not send data from client status="
        + Helper::toString(static_cast<int>(status)));
    return ODComStatus::Error;
}

//! \brief Receives a packet from the server (or the replay file) and reports the result as an ODComStatus.
ODSocketClient::ODComStatus ODSocketClient::recv(ODPacket& s)
{
    switch(mSource)
    {
        case ODSource::none:
        {
            // We should not try to send anything until connected
            OD_LOG_ERR("Unexpected null server mode");
            return ODComStatus::Error;
        }
        case ODSource::network:
        {
            NetStatus status = mConnection->receive(s);
            if (status == NetStatus::Done)
            {
                s.writePacket(mGameClock.getElapsedTime().asMilliseconds(),
                    mReplayOutputStream);
                return ODComStatus::OK;
            }

            if((!mConnection->isBlocking()) &&
                    (status == NetStatus::NotReady))
            {
                return ODComStatus::NotReady;
            }

            if(status == NetStatus::Disconnected)
            {
                OD_LOG_WRN("Socket disconnected");
                return ODComStatus::Error;
            }
            OD_LOG_ERR("Could not receive data from client status=" + Helper::toString(static_cast<int>(status)));
            return ODComStatus::Error;
        }
        case ODSource::file:
        {
            OD_ASSERT_TRUE(mPendingPacket != 0);
            s = mPendingPacket;
            mPendingTimestamp = -1;
            return ODComStatus::OK;
        }
        default:
            break;
    }
    return ODComStatus::Error;
}

bool ODSocketClient::isConnected()
{
    return mSource != ODSource::none;
}

void ODSocketClient::processClientSocketMessages(int miliseconds)
{
    // If we receive message for a new turn, after processing every message,
    // we will refresh what is needed
    // We loop until no more data is available
    while(isConnected() && processOneClientSocketMessage(miliseconds));
}

//! \brief Receives and processes one server message. A timeout of 0 or less polls the socket without waiting.
bool ODSocketClient::processOneClientSocketMessage(int miliseconds)
{
    ODPacket packetReceived;
    ODComStatus comStatus;
    if((miliseconds <= 0) && (mSource == ODSource::network))
    {
        // Poll without any wait. A selector wait of zero would block until data comes, and even a very short
        // wait lasts at least one tick of the system timer. The socket is non blocking for this receive only;
        // SFML keeps a packet that has arrived only in part until the rest comes with a later call.
        mConnection->setBlocking(false);
        comStatus = recv(packetReceived);
        mConnection->setBlocking(true);
        if(comStatus == ODComStatus::NotReady)
            return false;
    }
    else
    {
        if(!isDataAvailable(miliseconds))
            return false;

        // Check if data available
        comStatus = recv(packetReceived);
    }
    if(comStatus != ODComStatus::OK)
    {
        playerDisconnected();
        return false;
    }

    ServerNotificationType serverCommand;
    OD_ASSERT_TRUE(packetReceived >> serverCommand);

    return processMessage(serverCommand, packetReceived);
}
