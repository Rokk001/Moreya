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

#include "ODSocketServer.h"
#include "network/ODPacket.h"
#include "game/Player.h"

#include "utils/Helper.h"
#include "utils/LogManager.h"

#include <SFML/System.hpp>

//! \brief Creates the server with a listener of the default transport; it listens once createServer is called.
ODSocketServer::ODSocketServer():
    mThread(nullptr),
    mListener(NetTransport::createListener(NetTransport::getDefaultKind())),
    mIsConnected(false)
{
}

ODSocketServer::~ODSocketServer()
{
    if(mIsConnected || mThread != nullptr)
        stopServer();
}

//! \brief Starts listening on the given port and launches the server thread.
bool ODSocketServer::createServer(int listeningPort)
{
    mIsConnected = false;

    // As we use selector, there is no need to set the socket as not-blocking
    // The listener adds itself to its selector once it listens (TcpNetListener::listen).
    NetStatus status = mListener->listen(listeningPort);
    if (status != NetStatus::Done)
    {
        OD_LOG_ERR("Could not listen to server port status="
            + Helper::toString(static_cast<int>(status)) + " port=" + Helper::toString(listeningPort));
        return false;
    }

    mIsConnected = true;
    OD_LOG_INF("Server connected and listening");
    mThread = new std::thread(&ODSocketServer::serverThread, this);

    return true;
}

//! \brief Returns the actual TCP port, including one assigned by the OS.
unsigned short ODSocketServer::getListeningPort() const
{
    return mListener->getLocalPort();
}

bool ODSocketServer::isConnected()
{
    return mIsConnected;
}

//! \brief Waits on the transport listener for new peers and messages and dispatches them (see the header).
void ODSocketServer::doTask(int timeoutMs)
{
    mClockMainTask.restart();
    while((timeoutMs == 0) ||
          (timeoutMs > mClockMainTask.getElapsedTime().asMilliseconds()))
    {
        bool isSockReady;
        if(timeoutMs != 0)
        {
            // We adapt the timeout so that the function returns after timeoutMs
            // even if events occurred
            int timeoutMsAdjusted = std::max(1, timeoutMs - mClockMainTask.getElapsedTime().asMilliseconds());
            isSockReady = mListener->wait(timeoutMsAdjusted);
        }
        else
        {
            // 0 waits until something is ready, like sf::Time::Zero on the selector
            isSockReady = mListener->wait(0);
        }

        // Check if a client tries to connect or to communicate
        if(!isSockReady)
            continue;

        if(mListener->isPendingConnection())
        {
            // New connection
            ODSocketClient* newClient = notifyNewConnection(*mListener);
            if (newClient != nullptr)
            {
                // New connection
                OD_LOG_INF("New client connected.");
                // The server wants to keep the client
                newClient->setSource(ODSocketClient::ODSource::network);
                mListener->watch(newClient->getConnection());
                mSockClients.push_back(newClient);
            }
        }
        else
        {

            for(std::vector<ODSocketClient*>::iterator it = mSockClients.begin(); it != mSockClients.end();)
            {
                ODSocketClient* client = *it;
                if((mListener->isReady(client->getConnection())) &&
                    (!notifyClientMessage(client)))
                {
                    OD_LOG_INF("The server wants to remove the client");
                    // The server wants to remove the client
                    it = mSockClients.erase(it);
                    mListener->unwatch(client->getConnection());
                    client->disconnect();
                    delete client;
                }
                else
                {
                    ++it;
                }
            }
        }
    }
}

void ODSocketServer::requestStop()
{
    mIsConnected = false;
}

//! \brief Stops the server: joins the server thread, closes the sockets and drops all clients.
void ODSocketServer::stopServer()
{
    requestStop();
    if(mThread != nullptr)
    {
        // Wait for the thread to finish before deleting it
        if(mThread->joinable())
            mThread->join();
        delete mThread;
    }
    mThread = nullptr;
    // Clears the selector and closes the listening socket (TcpNetListener::close)
    mListener->close();
    for (std::vector<ODSocketClient*>::iterator it = mSockClients.begin(); it != mSockClients.end(); ++it)
    {
        ODSocketClient* client = *it;
        client->disconnect();
        delete client;
    }

    mSockClients.clear();
}
