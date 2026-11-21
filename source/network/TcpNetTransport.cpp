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

#include "network/TcpNetTransport.h"
#include "network/ODPacket.h"

#include <cassert>
#include <optional>
#include <vector>

//! \brief Maps every SFML status to the transport status with the same number.
NetStatus toNetStatus(sf::Socket::Status status)
{
    switch(status)
    {
        case sf::Socket::Status::Done:
            return NetStatus::Done;
        case sf::Socket::Status::NotReady:
            return NetStatus::NotReady;
        case sf::Socket::Status::Partial:
            return NetStatus::Partial;
        case sf::Socket::Status::Disconnected:
            return NetStatus::Disconnected;
        case sf::Socket::Status::Error:
            return NetStatus::Error;
        default:
            break;
    }
    return NetStatus::Error;
}

//! \brief Creates an unconnected, blocking socket.
TcpNetConnection::TcpNetConnection()
{
}

//! \brief Reports NetTransportKind::tcp.
NetTransportKind TcpNetConnection::getKind() const
{
    return NetTransportKind::tcp;
}

//! \brief Resolves the host and connects; a host that cannot be resolved is reported as NetStatus::Error.
NetStatus TcpNetConnection::connect(const std::string& host, int port, uint32_t timeoutMs)
{
    // As we use selector, there is no need to set the socket as not-blocking
    // SFML 3 connects to an address, not to a host name, so the host is resolved first (IPv4 only, as before).
    // A host that cannot be resolved is reported as a connection error.
    sf::Socket::Status status = sf::Socket::Status::Error;
    // SFML 3: Dns::resolve without timeout, first IPv4 address only (same as SFML 2 IpAddress(host)).
    std::optional<std::vector<sf::IpAddress> > addresses = sf::Dns::resolve(host, std::vector<sf::IpAddress>(), std::nullopt);
    if(addresses.has_value())
    {
        for(std::vector<sf::IpAddress>::const_iterator it = addresses->begin(); it != addresses->end(); ++it)
        {
            if(!it->isV4())
                continue;

            status = mSocket.connect(*it, static_cast<unsigned short>(port), sf::milliseconds(static_cast<int32_t>(timeoutMs)));
            break;
        }
    }
    if(status != sf::Socket::Status::Done)
        return toNetStatus(status);

    mSelector.add(mSocket);
    return NetStatus::Done;
}

//! \brief Sends the packet as one sf::Packet (length prefix and data, unchanged wire format).
NetStatus TcpNetConnection::send(ODPacket& packet)
{
    return toNetStatus(mSocket.send(packet.mPacket));
}

//! \brief Receives one sf::Packet; a partly received packet is kept by SFML until the rest comes.
NetStatus TcpNetConnection::receive(ODPacket& packet)
{
    return toNetStatus(mSocket.receive(packet.mPacket));
}

//! \brief Waits on the own selector for data from the server.
bool TcpNetConnection::waitForData(int milliseconds)
{
    // There is only 1 socket in the selector so it should be ready if
    // wait returns true but it doesn't hurt to return isReady...
    if(!mSelector.wait(sf::milliseconds(milliseconds)))
        return false;
    return mSelector.isReady(mSocket);
}

//! \brief Switches the socket between blocking and non blocking mode.
void TcpNetConnection::setBlocking(bool blocking)
{
    mSocket.setBlocking(blocking);
}

//! \brief Whether the socket is blocking.
bool TcpNetConnection::isBlocking() const
{
    return mSocket.isBlocking();
}

//! \brief Removes the socket from the own selector and closes it.
void TcpNetConnection::disconnect()
{
    // Remove any remaining client sockets from the socket selector,
    // if there is any left.
    mSelector.clear();
    mSocket.disconnect();
}

//! \brief Creates a listener that does not listen yet.
TcpNetListener::TcpNetListener()
{
}

//! \brief Reports NetTransportKind::tcp.
NetTransportKind TcpNetListener::getKind() const
{
    return NetTransportKind::tcp;
}

//! \brief Listens on the TCP port and, on success, adds the listener to the selector.
NetStatus TcpNetListener::listen(int port)
{
    // As we use selector, there is no need to set the socket as not-blocking
    sf::Socket::Status status = mListener.listen(static_cast<unsigned short>(port));
    if(status != sf::Socket::Status::Done)
        return toNetStatus(status);

    mSelector.add(mListener);
    return NetStatus::Done;
}

//! \brief Returns the actual TCP port, including one assigned by the OS.
unsigned short TcpNetListener::getLocalPort() const
{
    return mListener.getLocalPort();
}

//! \brief Accepts the pending peer into the socket of the given TcpNetConnection.
NetStatus TcpNetListener::accept(NetConnection& connection)
{
    return toNetStatus(mListener.accept(socketOf(connection)));
}

//! \brief Adds the socket of the connection to the selector.
void TcpNetListener::watch(NetConnection& connection)
{
    mSelector.add(socketOf(connection));
}

//! \brief Removes the socket of the connection from the selector.
void TcpNetListener::unwatch(NetConnection& connection)
{
    mSelector.remove(socketOf(connection));
}

//! \brief Waits on the selector; 0 waits until something is ready, like sf::Time::Zero.
bool TcpNetListener::wait(int timeoutMs)
{
    return mSelector.wait(sf::milliseconds(timeoutMs));
}

//! \brief Whether a peer waits to be accepted.
bool TcpNetListener::isPendingConnection() const
{
    return mSelector.isReady(mListener);
}

//! \brief Whether the socket of the connection has data.
bool TcpNetListener::isReady(NetConnection& connection) const
{
    return mSelector.isReady(socketOf(connection));
}

//! \brief Clears the selector and closes the listener socket; accepted sockets stay open.
void TcpNetListener::close()
{
    mSelector.clear();
    mListener.close();
}

//! \brief The socket of a connection; mixing backends is a programming error.
sf::TcpSocket& TcpNetListener::socketOf(NetConnection& connection)
{
    assert(connection.getKind() == NetTransportKind::tcp);
    return static_cast<TcpNetConnection&>(connection).getSocket();
}
