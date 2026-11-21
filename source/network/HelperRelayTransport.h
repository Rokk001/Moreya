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

#ifndef HELPERRELAYTRANSPORT_H
#define HELPERRELAYTRANSPORT_H

/*! \file HelperRelayTransport.h
 * \brief The second transport backend: lobby and relay through a helper process.
 *
 * Compiled only with OD_NET_HELPER_RELAY (CMake option of the same name, off by default). It shows where the
 * backend plugs into NetTransport.h, as NetTransportKind::helperRelay. The design:
 *
 * - HelperRelayProcess (one per game, HelperRelayProcess.h) starts the helper executable, owns both pipes and a
 *   HelperPipe::FrameDecoder, sends hello, waits for ready and files incoming frames into peer queues that the
 *   listener (host) and the connections (client) read. Lobby frames go to the multiplayer menus through a
 *   HelperLobbyObserver.
 * - HelperRelayListener (host): listens on the TCP port as the TCP backend does, so the host's own client keeps
 *   connecting by TCP on localhost, and additionally accepts the peers that the helper announces with
 *   peerConnected into fresh HelperRelayConnections. wait() covers both: the reader thread wakes the socket
 *   selector through a local socket pair.
 * - HelperRelayConnection: either one relayed peer id or, for a host name or address, a plain TCP connection.
 *   send() wraps ODPacket::getRawData() in a peerData frame; receive() returns the next queued peerData payload
 *   through ODPacket::setRawData(). Lobbies are addressed as "lobby:<id>" (formatLobbyAddress()).
 *
 * Status values follow the TCP backend: Done, NotReady for a non blocking receive without a message,
 * Disconnected once the peer or the helper is gone (queued messages are read first), Error for a failed connect.
 *
 * Nothing of the platform SDK is used here: the game only speaks the pipe protocol of HelperPipeProtocol.h.
 */

#ifdef OD_NET_HELPER_RELAY

#include "network/HelperPipeProtocol.h"
#include "network/HelperRelayProcess.h"
#include "network/NetTransport.h"
#include "network/TcpNetTransport.h"

#include <SFML/Network.hpp>

#include <memory>
#include <mutex>
#include <set>
#include <string>

/*! \brief Connection to one peer relayed by the helper process, or a plain TCP connection.
 * connect() with a lobby address joins the lobby and talks to its host through the helper; any other host is
 * connected by TCP, so the host's own client (localhost) and direct joins by address work unchanged.
 * HelperRelayListener::accept() fills it with a relayed peer or an accepted TCP socket.
 */
class HelperRelayConnection : public NetConnection
{
public:
    //! \brief Prefix of a lobby address passed to connect() as the host.
    static const char* const LOBBY_ADDRESS_PREFIX;

    //! \brief The host string that connect() takes for a lobby: "lobby:<decimal id>".
    static std::string formatLobbyAddress(uint64_t lobbyId);

    //! \brief Reads a lobby address; false for anything else (a host name or address) or a lobby id of 0.
    static bool parseLobbyAddress(const std::string& host, uint64_t& lobbyId);

    //! \brief Creates a connection that has no peer yet; relayed operations go through process (may be nullptr).
    explicit HelperRelayConnection(HelperRelayProcess* process);

    //! \brief Closes a relayed peer that is still attached; a TCP socket closes with its object.
    ~HelperRelayConnection() override;

    //! \brief Reports NetTransportKind::helperRelay.
    NetTransportKind getKind() const override;

    /*! \brief A lobby address joins that lobby through the helper (the port is ignored) and waits up to timeoutMs
     * (0: no limit) for lobbyJoined; anything else connects by TCP. Error if the join fails or the helper does
     * not run.
     */
    NetStatus connect(const std::string& host, int port, uint32_t timeoutMs) override;

    //! \brief Relayed: sends a peerData frame with the packet bytes. TCP: sends the packet as one sf::Packet.
    NetStatus send(ODPacket& packet) override;

    //! \brief Relayed: returns the next peerData payload of this peer; waits for it when blocking.
    NetStatus receive(ODPacket& packet) override;

    //! \brief Relayed: waits for a peerData frame or the disconnect of this peer (0: no limit). TCP: as the TCP backend.
    bool waitForData(int milliseconds) override;

    //! \brief Stores the blocking mode for receive() and passes it to the TCP socket.
    void setBlocking(bool blocking) override;

    //! \brief Whether receive() waits.
    bool isBlocking() const override;

    //! \brief Relayed: sends peerClose for this peer and forgets the peer. TCP: closes the socket.
    void disconnect() override;

    //! \brief Listener side: makes this connection the relayed peer peerId.
    void attachPeer(uint64_t peerId);

    //! \brief Listener side: the TCP connection to accept a socket into; created on first use.
    TcpNetConnection& useTcp();

    //! \brief The TCP connection, nullptr for a relayed or unused connection.
    TcpNetConnection* getTcp() const
    { return mTcp.get(); }

    //! \brief Platform user id of the relayed peer; 0 while none is attached.
    uint64_t getPeerId() const
    { return mPeerId; }

private:
    HelperRelayProcess* mProcess;
    //! \brief Platform user id of the peer; 0 while not connected.
    uint64_t mPeerId;
    bool mBlocking;
    //! \brief Set for a TCP connection (connect to an address, or a socket accepted by the listener).
    std::unique_ptr<TcpNetConnection> mTcp;
};

/*! \brief Host side of the helper relay: a lobby in addition to the TCP port.
 * The lobby itself is created by the menus through HelperRelayProcess::createLobby(); peers announced with
 * peerConnected are accepted like new TCP clients. close() leaves a lobby the game hosts.
 */
class HelperRelayListener : public NetListener, private HelperRelayEventSink
{
public:
    //! \brief Creates a listener that does not listen yet; relayed peers come from process (may be nullptr).
    explicit HelperRelayListener(HelperRelayProcess* process);

    //! \brief Closes the listener (see close()).
    ~HelperRelayListener() override;

    //! \brief Reports NetTransportKind::helperRelay.
    NetTransportKind getKind() const override;

    //! \brief Listens on the TCP port (for the host's own client), opens the local wake socket pair and registers with the process.
    NetStatus listen(int port) override;

    //! \brief The TCP port, including one chosen by the operating system; a lobby has no port.
    unsigned short getLocalPort() const override;

    //! \brief Accepts a pending TCP client, else hands the oldest peerConnected peer to the connection.
    NetStatus accept(NetConnection& connection) override;

    //! \brief Includes the relayed peer or the TCP socket in wait().
    void watch(NetConnection& connection) override;

    //! \brief Removes the relayed peer or the TCP socket from wait().
    void unwatch(NetConnection& connection) override;

    //! \brief Waits on the selector of TCP sockets and the wake socket, so a frame read from the pipe ends the wait.
    bool wait(int timeoutMs) override;

    //! \brief Whether a TCP client waits or a peerConnected is queued.
    bool isPendingConnection() const override;

    //! \brief Whether peerData (or the disconnect) of the peer is queued, or the TCP socket is readable.
    bool isReady(NetConnection& connection) const override;

    //! \brief Leaves the lobby the game hosts, closes the TCP listener and the wake sockets and forgets the watched peers.
    void close() override;

private:
    //! \brief Reader thread of the process: new frames are there, so wake wait().
    void onRelayEvent() override;

    //! \brief Writes one byte to the wake socket, which makes the selector return.
    void wake();

    //! \brief Reads the wake bytes that are there.
    void drainWake();

    //! \brief Whether a relayed peer waits to be accepted or a watched relayed peer is ready.
    bool isRelayReady() const;

    //! \brief The TCP socket of a TCP connection or of a HelperRelayConnection that carries TCP; nullptr otherwise.
    static sf::TcpSocket* tcpSocketOf(NetConnection& connection);

    //! \brief The connection as HelperRelayConnection; nullptr for a connection of another backend.
    static HelperRelayConnection* relayOf(NetConnection& connection);

    HelperRelayProcess* mProcess;
    bool mListening;
    sf::TcpListener mTcpListener;
    sf::SocketSelector mSelector;
    //! \brief Set by wait() when the TCP listener was ready; cleared by accept().
    bool mTcpPending;
    //! \brief Relayed peers included in wait() and isReady().
    std::set<uint64_t> mWatchedPeers;
    //! \brief Guards mWakeSender and mWakeConnected; the reader thread and wait() both write the sender.
    std::mutex mWakeMutex;
    bool mWakeConnected;
    sf::TcpSocket mWakeSender;
    //! \brief Read end of the wake pair; part of the selector.
    sf::TcpSocket mWakeReceiver;
};

#endif // OD_NET_HELPER_RELAY

#endif // HELPERRELAYTRANSPORT_H
