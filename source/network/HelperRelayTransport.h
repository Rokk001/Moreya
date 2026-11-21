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
 * \brief Stub of the second transport backend: lobby and relay through a helper process.
 *
 * Not built and not selectable: the whole file is compiled only with OD_NET_HELPER_RELAY, which no build
 * defines yet. It shows where the backend plugs into NetTransport.h. The planned design:
 *
 * - HelperRelayProcess (one per game) starts the helper executable next to the game binary, owns both
 *   pipes and a HelperPipe::FrameDecoder, sends hello, waits for ready and dispatches incoming frames to
 *   the listener (host) or connection (client). Lobby frames go to the multiplayer menus.
 * - HelperRelayListener (host): listen() sends lobbyCreate; peerConnected queues a pending peer that
 *   accept() hands to a fresh HelperRelayConnection; wait() reads the pipe until a frame is there.
 * - HelperRelayConnection: one peer id; send() wraps ODPacket::getRawData() in a peerData frame;
 *   receive() returns the next queued peerData payload through ODPacket::setRawData().
 *
 * Nothing of the platform SDK is used here: the game only speaks the pipe protocol of HelperPipeProtocol.h.
 */

#ifdef OD_NET_HELPER_RELAY

#include "network/HelperPipeProtocol.h"
#include "network/NetTransport.h"

//! \brief Connection to one peer relayed by the helper process. Stub: every operation fails.
class HelperRelayConnection : public NetConnection
{
public:
    //! \brief Creates a connection that has no peer yet.
    HelperRelayConnection():
        mPeerId(0),
        mBlocking(true)
    {}

    //! \brief Reports NetTransportKind::helperRelay.
    NetTransportKind getKind() const override
    { return NetTransportKind::helperRelay; }

    //! \brief Will join the lobby named by host (a lobby id) through the helper. Stub: fails.
    NetStatus connect(const std::string& host, int port, uint32_t timeoutMs) override
    { return NetStatus::Error; }

    //! \brief Will send a peerData frame with the packet bytes. Stub: fails.
    NetStatus send(ODPacket& packet) override
    { return NetStatus::Error; }

    //! \brief Will return the next peerData payload of this peer. Stub: fails.
    NetStatus receive(ODPacket& packet) override
    { return NetStatus::Error; }

    //! \brief Will wait for a peerData frame of this peer. Stub: nothing comes.
    bool waitForData(int milliseconds) override
    { return false; }

    //! \brief Stores the blocking mode for receive().
    void setBlocking(bool blocking) override
    { mBlocking = blocking; }

    //! \brief Whether receive() waits.
    bool isBlocking() const override
    { return mBlocking; }

    //! \brief Will send peerClose for this peer. Stub: forgets the peer.
    void disconnect() override
    { mPeerId = 0; }

private:
    //! \brief Platform user id of the peer; 0 while not connected.
    uint64_t mPeerId;
    bool mBlocking;
};

//! \brief Host side of the helper relay: a lobby instead of a TCP port. Stub: listening fails.
class HelperRelayListener : public NetListener
{
public:
    //! \brief Reports NetTransportKind::helperRelay.
    NetTransportKind getKind() const override
    { return NetTransportKind::helperRelay; }

    //! \brief Will create the lobby (the port is ignored). Stub: fails.
    NetStatus listen(int port) override
    { return NetStatus::Error; }

    //! \brief A lobby has no port.
    unsigned short getLocalPort() const override
    { return 0; }

    //! \brief Will hand the oldest peerConnected peer to the connection. Stub: fails.
    NetStatus accept(NetConnection& connection) override
    { return NetStatus::Error; }

    //! \brief Will include the peer in wait(). Stub: nothing to do.
    void watch(NetConnection& connection) override
    {}

    //! \brief Will remove the peer from wait(). Stub: nothing to do.
    void unwatch(NetConnection& connection) override
    {}

    //! \brief Will read the pipe until a frame comes. Stub: nothing comes.
    bool wait(int timeoutMs) override
    { return false; }

    //! \brief Whether a peerConnected is queued. Stub: never.
    bool isPendingConnection() const override
    { return false; }

    //! \brief Whether peerData of the peer is queued. Stub: never.
    bool isReady(NetConnection& connection) const override
    { return false; }

    //! \brief Will leave the lobby. Stub: nothing to do.
    void close() override
    {}
};

#endif // OD_NET_HELPER_RELAY

#endif // HELPERRELAYTRANSPORT_H
