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

#ifndef NETTRANSPORT_H
#define NETTRANSPORT_H

/*! \file NetTransport.h
 * \brief Transport layer between the game protocol (ODPacket messages) and the medium that carries them.
 *
 * ODSocketServer and ODSocketClient no longer talk to sockets directly. They exchange ODPacket messages
 * through a NetConnection (one per peer) and, on the server, a NetListener that accepts new peers and
 * waits until a peer has data. The contract every backend keeps:
 *
 * - One ODPacket sent is one ODPacket received, with the same bytes (message boundaries are preserved).
 * - Messages from one peer arrive complete, in order and without loss (reliable, ordered delivery).
 * - The game protocol above the transport does not change between backends; replays (.odr) are
 *   written by ODSocketClient from the received ODPacket and do not depend on the backend.
 *
 * Backends:
 * - NetTransportKind::tcp: direct connection by host name or IP address over SFML TCP sockets
 *   (TcpNetTransport.h). It is the default and the only one built without OD_NET_HELPER_RELAY. Its bytes on the wire are those
 *   of sf::Packet over sf::TcpSocket: a 32 bit big-endian length followed by the packet data.
 * - NetTransportKind::helperRelay: lobby and relay through a separate helper process that the game
 *   starts and talks to over a pipe (HelperPipeProtocol.h, HelperRelayProcess.h, HelperRelayTransport.h). Built
 *   only with the CMake option OD_NET_HELPER_RELAY (off by default) and used once a helper process is set up
 *   with --net-helper; see docs/development/NETWORK-TRANSPORT.md.
 */

#include <cstdint>
#include <memory>
#include <string>

class ODPacket;

//! \brief Result of a transport operation. The values equal the SFML socket status codes, so the numbers
//! written to the log stay the same as before the transport layer existed.
enum class NetStatus
{
    //! The operation completed.
    Done = 0,
    //! A non blocking operation found no complete message yet.
    NotReady = 1,
    //! Only a part of the data was sent (non blocking send).
    Partial = 2,
    //! The other side closed the connection.
    Disconnected = 3,
    //! Any other failure.
    Error = 4
};

//! \brief The media that can carry the game protocol.
enum class NetTransportKind
{
    //! Direct TCP connection by host name or IP address. Default.
    tcp,
    //! Lobby and relay through an external helper process over a pipe; also carries direct TCP. Only with OD_NET_HELPER_RELAY.
    helperRelay
};

/*! \brief One connection to one peer: the server side of a joined player, or the client side to the host.
 * ODSocketClient owns exactly one connection.
 */
class NetConnection
{
public:
    //! \brief Closes nothing by itself; owners call disconnect() first where needed.
    virtual ~NetConnection()
    {}

    //! \brief The backend this connection belongs to. A listener only accepts and watches its own kind.
    virtual NetTransportKind getKind() const = 0;

    /*! \brief Connects to a host (client side). For TCP, host is a name or an IPv4 address and port the
     * TCP port. timeoutMs limits the attempt. Returns NetStatus::Done on success.
     */
    virtual NetStatus connect(const std::string& host, int port, uint32_t timeoutMs) = 0;

    //! \brief Sends one complete message. Blocks until it is handed to the medium when the connection is blocking.
    virtual NetStatus send(ODPacket& packet) = 0;

    /*! \brief Receives one complete message into packet. A blocking connection waits for it; a non blocking
     * one returns NetStatus::NotReady when no complete message is there yet and keeps a part already
     * received for a later call.
     */
    virtual NetStatus receive(ODPacket& packet) = 0;

    /*! \brief Waits up to milliseconds for data from the peer and tells whether there is some.
     * Only meaningful on the client side; on the server side the listener waits for all peers.
     * A value of 0 waits until data comes (same as the selector it replaces).
     */
    virtual bool waitForData(int milliseconds) = 0;

    //! \brief Switches between blocking and non blocking receive.
    virtual void setBlocking(bool blocking) = 0;

    //! \brief Whether receive waits for a message.
    virtual bool isBlocking() const = 0;

    //! \brief Closes the connection. Safe to call on a connection that is not open.
    virtual void disconnect() = 0;
};

/*! \brief Server side: accepts peers and waits until a new peer or a message is there.
 * It replaces the TCP listener and the socket selector of ODSocketServer; for TCP, watching a connection
 * means adding its socket to the selector.
 */
class NetListener
{
public:
    //! \brief Port value that lets the medium choose a free port (TCP: the operating system).
    static const int AnyPort = 0;

    //! \brief Releases the backend resources.
    virtual ~NetListener()
    {}

    //! \brief The backend this listener belongs to.
    virtual NetTransportKind getKind() const = 0;

    //! \brief Starts accepting peers on the given port (AnyPort for a free one).
    virtual NetStatus listen(int port) = 0;

    //! \brief The port peers connect to, including one chosen by the medium. 0 when not listening.
    virtual unsigned short getLocalPort() const = 0;

    /*! \brief Accepts the pending peer into connection, which must be a fresh connection of the same kind
     * (ODSocketClient creates it from NetTransport::getDefaultKind(), like the listener).
     */
    virtual NetStatus accept(NetConnection& connection) = 0;

    //! \brief Includes the connection in wait() and isReady().
    virtual void watch(NetConnection& connection) = 0;

    //! \brief Removes the connection from wait() and isReady() before it is closed and deleted.
    virtual void unwatch(NetConnection& connection) = 0;

    /*! \brief Waits up to timeoutMs for a new peer or a message from a watched connection.
     * A value of 0 waits until something comes. Returns true if something is ready.
     */
    virtual bool wait(int timeoutMs) = 0;

    //! \brief After wait() returned true: whether a new peer waits to be accepted.
    virtual bool isPendingConnection() const = 0;

    //! \brief After wait() returned true: whether the watched connection has data.
    virtual bool isReady(NetConnection& connection) const = 0;

    //! \brief Stops listening and forgets all watched connections. The connections themselves stay open.
    virtual void close() = 0;
};

//! \brief Creates the transport objects of a backend.
namespace NetTransport
{
    //! \brief The backend used by the game: NetTransportKind::tcp, or helperRelay once a helper process is set up (OD_NET_HELPER_RELAY builds only).
    NetTransportKind getDefaultKind();

    //! \brief Creates an unconnected connection of the given kind. An unbuilt kind falls back to TCP with an error log.
    std::unique_ptr<NetConnection> createConnection(NetTransportKind kind);

    //! \brief Creates a listener of the given kind. An unbuilt kind falls back to TCP with an error log.
    std::unique_ptr<NetListener> createListener(NetTransportKind kind);
}

#endif // NETTRANSPORT_H
