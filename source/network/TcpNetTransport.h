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

#ifndef TCPNETTRANSPORT_H
#define TCPNETTRANSPORT_H

#include "network/NetTransport.h"

#include <SFML/Network.hpp>

/*! \brief Direct TCP connection over SFML sockets, the default backend.
 * Each message is one sf::Packet sent with sf::TcpSocket, so the bytes on the wire are a 32 bit
 * big-endian length followed by the packet data, exactly as before the transport layer existed.
 */
class TcpNetConnection : public NetConnection
{
public:
    //! \brief Creates an unconnected, blocking socket.
    TcpNetConnection();

    //! \brief Reports NetTransportKind::tcp.
    NetTransportKind getKind() const override;

    //! \brief Resolves the host (first IPv4 address) and connects within timeoutMs.
    NetStatus connect(const std::string& host, int port, uint32_t timeoutMs) override;

    //! \brief Sends the packet as one sf::Packet.
    NetStatus send(ODPacket& packet) override;

    //! \brief Receives one sf::Packet into the packet.
    NetStatus receive(ODPacket& packet) override;

    //! \brief Waits on the own selector, filled by connect(), for data from the server.
    bool waitForData(int milliseconds) override;

    //! \brief Switches the socket between blocking and non blocking mode.
    void setBlocking(bool blocking) override;

    //! \brief Whether the socket is blocking.
    bool isBlocking() const override;

    //! \brief Removes the socket from the own selector and closes it.
    void disconnect() override;

    //! \brief The socket, for the TCP listener that accepts into it and watches it.
    sf::TcpSocket& getSocket()
    { return mSocket; }

private:
    sf::TcpSocket mSocket;
    //! \brief Holds the socket after connect() so waitForData() can wait on it (client side only).
    sf::SocketSelector mSelector;
};

/*! \brief TCP listener and socket selector of the server. The selector holds the listener and every
 * watched connection, so one wait covers new peers and messages, as before the transport layer existed.
 */
class TcpNetListener : public NetListener
{
public:
    //! \brief Creates a listener that does not listen yet.
    TcpNetListener();

    //! \brief Reports NetTransportKind::tcp.
    NetTransportKind getKind() const override;

    //! \brief Listens on the TCP port and adds the listener to the selector.
    NetStatus listen(int port) override;

    //! \brief The bound TCP port, including one the operating system chose.
    unsigned short getLocalPort() const override;

    //! \brief Accepts the pending peer into the socket of a TcpNetConnection.
    NetStatus accept(NetConnection& connection) override;

    //! \brief Adds the socket of a TcpNetConnection to the selector.
    void watch(NetConnection& connection) override;

    //! \brief Removes the socket of a TcpNetConnection from the selector.
    void unwatch(NetConnection& connection) override;

    //! \brief Waits on the selector; 0 waits until something is ready.
    bool wait(int timeoutMs) override;

    //! \brief Whether the listener socket is ready, i.e. a peer waits to be accepted.
    bool isPendingConnection() const override;

    //! \brief Whether the socket of the TcpNetConnection is ready.
    bool isReady(NetConnection& connection) const override;

    //! \brief Clears the selector and closes the listener socket.
    void close() override;

private:
    //! \brief The socket of a connection, which must be a TcpNetConnection.
    static sf::TcpSocket& socketOf(NetConnection& connection);

    sf::TcpListener mListener;
    sf::SocketSelector mSelector;
};

//! \brief Converts an SFML socket status to the transport status with the same number.
NetStatus toNetStatus(sf::Socket::Status status);

#endif // TCPNETTRANSPORT_H
