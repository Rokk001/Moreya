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

// Compiled only with OD_NET_HELPER_RELAY (see HelperRelayTransport.h and docs/development/NETWORK-TRANSPORT.md).
#ifdef OD_NET_HELPER_RELAY

#include "network/HelperRelayTransport.h"
#include "network/ODPacket.h"

#include "utils/LogManager.h"

#include <climits>
#include <cstdint>
#include <vector>

namespace
{
    //! \brief Limit for connecting the local wake socket pair of the listener.
    const int WAKE_CONNECT_TIMEOUT_MS = 2000;

    //! \brief Bytes drained from the wake socket per receive.
    const std::size_t WAKE_DRAIN_SIZE = 64;

    //! \brief Most decimal digits of a 64 bit lobby id.
    const std::size_t MAX_LOBBY_ID_DIGITS = 20;
}

const char* const HelperRelayConnection::LOBBY_ADDRESS_PREFIX = "lobby:";

//! \brief "lobby:" followed by the decimal id.
std::string HelperRelayConnection::formatLobbyAddress(uint64_t lobbyId)
{
    return std::string(LOBBY_ADDRESS_PREFIX) + std::to_string(lobbyId);
}

//! \brief Accepts "lobby:" followed by 1 to 20 decimal digits that fit in 64 bits and are not 0.
bool HelperRelayConnection::parseLobbyAddress(const std::string& host, uint64_t& lobbyId)
{
    const std::string prefix(LOBBY_ADDRESS_PREFIX);
    if((host.size() <= prefix.size()) || (host.compare(0, prefix.size(), prefix) != 0))
        return false;
    if(host.size() - prefix.size() > MAX_LOBBY_ID_DIGITS)
        return false;

    uint64_t value = 0;
    for(std::string::const_iterator it = host.begin() + static_cast<std::ptrdiff_t>(prefix.size()); it != host.end(); ++it)
    {
        if((*it < '0') || (*it > '9'))
            return false;
        uint64_t digit = static_cast<uint64_t>(*it - '0');
        if(value > (UINT64_MAX - digit) / 10)
            return false;
        value = value * 10 + digit;
    }
    if(value == 0)
        return false;
    lobbyId = value;
    return true;
}

//! \brief Creates a blocking connection without a peer.
HelperRelayConnection::HelperRelayConnection(HelperRelayProcess* process):
    mProcess(process),
    mPeerId(0),
    mBlocking(true)
{
}

//! \brief Sends peerClose for an attached relayed peer; the TCP connection closes with its object.
HelperRelayConnection::~HelperRelayConnection()
{
    if(mPeerId != 0)
        disconnect();
}

//! \brief Reports NetTransportKind::helperRelay.
NetTransportKind HelperRelayConnection::getKind() const
{
    return NetTransportKind::helperRelay;
}

//! \brief Joins a lobby address through the helper, or connects anything else by TCP.
NetStatus HelperRelayConnection::connect(const std::string& host, int port, uint32_t timeoutMs)
{
    uint64_t lobbyId = 0;
    if(!parseLobbyAddress(host, lobbyId))
    {
        if(mPeerId != 0)
            disconnect();
        return useTcp().connect(host, port, timeoutMs);
    }

    mTcp.reset();
    if((mProcess == nullptr) || !mProcess->isReady())
    {
        OD_LOG_ERR("No relay helper is ready to join lobby " + std::to_string(lobbyId));
        return NetStatus::Error;
    }
    if(mPeerId != 0)
        disconnect();

    int timeout = (timeoutMs > static_cast<uint32_t>(INT_MAX)) ? INT_MAX : static_cast<int>(timeoutMs);
    uint64_t hostUserId = 0;
    if(!mProcess->joinLobbyAndWait(lobbyId, timeout, hostUserId))
    {
        OD_LOG_ERR("Could not join lobby " + std::to_string(lobbyId) + " through the relay helper");
        return NetStatus::Error;
    }
    mProcess->openPeer(hostUserId);
    mPeerId = hostUserId;
    return NetStatus::Done;
}

//! \brief Relayed: the packet bytes as one peerData frame; Disconnected once the peer or the helper is gone.
NetStatus HelperRelayConnection::send(ODPacket& packet)
{
    if(mTcp)
        return mTcp->send(packet);
    if((mPeerId == 0) || (mProcess == nullptr))
        return NetStatus::Disconnected;
    if(!mProcess->sendPeerData(mPeerId, packet.getRawData(), packet.getRawDataSize()))
        return NetStatus::Disconnected;
    return NetStatus::Done;
}

//! \brief Relayed: the oldest queued message of the peer; NotReady without one when non blocking.
NetStatus HelperRelayConnection::receive(ODPacket& packet)
{
    if(mTcp)
        return mTcp->receive(packet);
    if((mPeerId == 0) || (mProcess == nullptr))
        return NetStatus::Disconnected;

    if(mBlocking)
        mProcess->waitForPeer(mPeerId, 0);

    std::vector<uint8_t> payload;
    switch(mProcess->takePeerData(mPeerId, payload))
    {
        case HelperPeerRead::data:
            packet.setRawData(payload.data(), payload.size());
            return NetStatus::Done;
        case HelperPeerRead::empty:
            return NetStatus::NotReady;
        case HelperPeerRead::disconnected:
        default:
            break;
    }
    return NetStatus::Disconnected;
}

//! \brief Relayed: waits on the process for a message or the disconnect of the peer.
bool HelperRelayConnection::waitForData(int milliseconds)
{
    if(mTcp)
        return mTcp->waitForData(milliseconds);
    if((mPeerId == 0) || (mProcess == nullptr))
        return false;
    return mProcess->waitForPeer(mPeerId, milliseconds);
}

//! \brief Stores the mode and passes it to the TCP socket.
void HelperRelayConnection::setBlocking(bool blocking)
{
    mBlocking = blocking;
    if(mTcp)
        mTcp->setBlocking(blocking);
}

//! \brief Whether receive() waits.
bool HelperRelayConnection::isBlocking() const
{
    if(mTcp)
        return mTcp->isBlocking();
    return mBlocking;
}

//! \brief Closes the TCP socket or sends peerClose and forgets the relayed peer.
void HelperRelayConnection::disconnect()
{
    if(mTcp)
        mTcp->disconnect();
    if((mPeerId != 0) && (mProcess != nullptr))
    {
        mProcess->closePeer(mPeerId);
        mProcess->releasePeer(mPeerId);
    }
    mPeerId = 0;
}

//! \brief Attaches a relayed peer accepted by the listener; a TCP connection is dropped.
void HelperRelayConnection::attachPeer(uint64_t peerId)
{
    mTcp.reset();
    mPeerId = peerId;
}

//! \brief Creates the TCP connection with the current blocking mode if there is none; an attached peer is closed first.
TcpNetConnection& HelperRelayConnection::useTcp()
{
    if(mPeerId != 0)
        disconnect();
    if(!mTcp)
    {
        mTcp.reset(new TcpNetConnection);
        mTcp->setBlocking(mBlocking);
    }
    return *mTcp;
}

//! \brief Creates a listener that does not listen yet.
HelperRelayListener::HelperRelayListener(HelperRelayProcess* process):
    mProcess(process),
    mListening(false),
    mTcpPending(false),
    mWakeConnected(false)
{
}

//! \brief Closes the listener; the process does not call it any more after this.
HelperRelayListener::~HelperRelayListener()
{
    close();
}

//! \brief Reports NetTransportKind::helperRelay.
NetTransportKind HelperRelayListener::getKind() const
{
    return NetTransportKind::helperRelay;
}

//! \brief Listens on the TCP port, connects the local wake pair, adds both to the selector and registers as event sink.
NetStatus HelperRelayListener::listen(int port)
{
    if(mListening)
        close();

    // As we use selector, there is no need to set the socket as not-blocking
    sf::Socket::Status status = mTcpListener.listen(static_cast<unsigned short>(port));
    if(status != sf::Socket::Status::Done)
        return toNetStatus(status);

    // The reader thread of the process ends a selector wait by writing to this pair. Its remote port is checked so
    // that no other local program can take the place of the sender.
    sf::TcpListener wakeListener;
    bool wakeReady = (wakeListener.listen(static_cast<unsigned short>(NetListener::AnyPort), sf::IpAddress::LocalHost)
            == sf::Socket::Status::Done)
        && (mWakeSender.connect(sf::IpAddress::LocalHost, wakeListener.getLocalPort(),
            sf::milliseconds(WAKE_CONNECT_TIMEOUT_MS)) == sf::Socket::Status::Done)
        && (wakeListener.accept(mWakeReceiver) == sf::Socket::Status::Done)
        && (mWakeReceiver.getRemotePort() == mWakeSender.getLocalPort());
    wakeListener.close();
    if(!wakeReady)
    {
        OD_LOG_ERR("Could not open the local wake sockets of the relay listener");
        mWakeSender.disconnect();
        mWakeReceiver.disconnect();
        mTcpListener.close();
        return NetStatus::Error;
    }
    mWakeSender.setBlocking(false);
    mWakeReceiver.setBlocking(false);

    mSelector.add(mTcpListener);
    mSelector.add(mWakeReceiver);
    {
        std::lock_guard<std::mutex> lock(mWakeMutex);
        mWakeConnected = true;
    }
    mListening = true;
    if(mProcess != nullptr)
        mProcess->addEventSink(this);
    return NetStatus::Done;
}

//! \brief The bound TCP port.
unsigned short HelperRelayListener::getLocalPort() const
{
    return mTcpListener.getLocalPort();
}

//! \brief A TCP client found ready by wait() goes first, then the oldest relayed peer; NotReady if neither waits.
NetStatus HelperRelayListener::accept(NetConnection& connection)
{
    if(mTcpPending)
    {
        mTcpPending = false;
        HelperRelayConnection* relay = relayOf(connection);
        if(relay != nullptr)
            return toNetStatus(mTcpListener.accept(relay->useTcp().getSocket()));
        if(connection.getKind() == NetTransportKind::tcp)
            return toNetStatus(mTcpListener.accept(static_cast<TcpNetConnection&>(connection).getSocket()));
        return NetStatus::Error;
    }

    uint64_t peerId = 0;
    if((mProcess == nullptr) || !mProcess->hasPendingPeer())
        return NetStatus::NotReady;
    HelperRelayConnection* relay = relayOf(connection);
    if(relay == nullptr)
    {
        // A relayed peer needs a HelperRelayConnection; it stays queued for the next accept
        OD_LOG_ERR("A relayed peer cannot be accepted into a connection of another transport");
        return NetStatus::Error;
    }
    if(!mProcess->takePendingPeer(peerId))
        return NetStatus::NotReady;
    relay->attachPeer(peerId);
    return NetStatus::Done;
}

//! \brief Adds the TCP socket to the selector or the relayed peer to the watched set.
void HelperRelayListener::watch(NetConnection& connection)
{
    sf::TcpSocket* socket = tcpSocketOf(connection);
    if(socket != nullptr)
    {
        mSelector.add(*socket);
        return;
    }
    HelperRelayConnection* relay = relayOf(connection);
    if((relay != nullptr) && (relay->getPeerId() != 0))
        mWatchedPeers.insert(relay->getPeerId());
}

//! \brief Removes the TCP socket from the selector or the relayed peer from the watched set.
void HelperRelayListener::unwatch(NetConnection& connection)
{
    sf::TcpSocket* socket = tcpSocketOf(connection);
    if(socket != nullptr)
    {
        mSelector.remove(*socket);
        return;
    }
    HelperRelayConnection* relay = relayOf(connection);
    if(relay != nullptr)
        mWatchedPeers.erase(relay->getPeerId());
}

//! \brief Wakes itself when relay events are queued already, then waits on the selector; 0 waits until something comes.
bool HelperRelayListener::wait(int timeoutMs)
{
    if(!mListening)
        return false;

    // Queued relay events must not wait for the timeout; the selector still reports the TCP sockets of this round
    if(isRelayReady())
        wake();

    bool ready = mSelector.wait(sf::milliseconds(timeoutMs));
    mTcpPending = ready && mSelector.isReady(mTcpListener);
    if(ready && mSelector.isReady(mWakeReceiver))
        drainWake();
    return ready;
}

//! \brief A TCP client found by wait() or a pending relayed peer.
bool HelperRelayListener::isPendingConnection() const
{
    if(mTcpPending)
        return true;
    return (mProcess != nullptr) && mProcess->hasPendingPeer();
}

//! \brief The TCP socket is readable, or the relayed peer has a message or is gone.
bool HelperRelayListener::isReady(NetConnection& connection) const
{
    sf::TcpSocket* socket = tcpSocketOf(connection);
    if(socket != nullptr)
        return mSelector.isReady(*socket);
    HelperRelayConnection* relay = relayOf(connection);
    if((relay == nullptr) || (relay->getPeerId() == 0) || (mProcess == nullptr))
        return false;
    return mProcess->isPeerReady(relay->getPeerId());
}

//! \brief Unregisters from the process, leaves a hosted lobby and closes every socket of the listener.
void HelperRelayListener::close()
{
    if(mProcess != nullptr)
    {
        mProcess->removeEventSink(this);
        if(mListening && mProcess->isLobbyHost())
            mProcess->leaveLobby();
    }
    {
        std::lock_guard<std::mutex> lock(mWakeMutex);
        mWakeConnected = false;
        mWakeSender.disconnect();
    }
    mWakeReceiver.disconnect();
    mSelector.clear();
    mTcpListener.close();
    mWatchedPeers.clear();
    mTcpPending = false;
    mListening = false;
}

//! \brief Runs on the reader thread of the process: wakes the selector.
void HelperRelayListener::onRelayEvent()
{
    wake();
}

//! \brief One byte on the non blocking wake sender; a full buffer means the receiver is readable already.
void HelperRelayListener::wake()
{
    std::lock_guard<std::mutex> lock(mWakeMutex);
    if(!mWakeConnected)
        return;
    // The overload with the sent count: the other one warns on every call to a non blocking socket
    const char byte = 1;
    std::size_t sent = 0;
    sf::Socket::Status status = mWakeSender.send(&byte, 1, sent);
    if((status == sf::Socket::Status::Disconnected) || (status == sf::Socket::Status::Error))
    {
        OD_LOG_ERR("The wake socket of the relay listener failed");
        mWakeConnected = false;
    }
}

//! \brief Reads the wake bytes until none is left; their value carries no meaning.
void HelperRelayListener::drainWake()
{
    char buffer[WAKE_DRAIN_SIZE];
    std::size_t received = 0;
    while((mWakeReceiver.receive(buffer, sizeof(buffer), received) == sf::Socket::Status::Done) && (received > 0))
        received = 0;
}

//! \brief A pending relayed peer or a watched relayed peer that is ready; a peer whose connection was closed does not count.
bool HelperRelayListener::isRelayReady() const
{
    if(mProcess == nullptr)
        return false;
    if(mProcess->hasPendingPeer())
        return true;
    for(std::set<uint64_t>::const_iterator it = mWatchedPeers.begin(); it != mWatchedPeers.end(); ++it)
    {
        if(mProcess->isKnownPeerReady(*it))
            return true;
    }
    return false;
}

//! \brief The socket of a TcpNetConnection, or of the TCP connection a HelperRelayConnection carries.
sf::TcpSocket* HelperRelayListener::tcpSocketOf(NetConnection& connection)
{
    if(connection.getKind() == NetTransportKind::tcp)
        return &static_cast<TcpNetConnection&>(connection).getSocket();
    HelperRelayConnection* relay = relayOf(connection);
    if((relay != nullptr) && (relay->getTcp() != nullptr))
        return &relay->getTcp()->getSocket();
    return nullptr;
}

//! \brief The connection as HelperRelayConnection if it is one.
HelperRelayConnection* HelperRelayListener::relayOf(NetConnection& connection)
{
    if(connection.getKind() != NetTransportKind::helperRelay)
        return nullptr;
    return &static_cast<HelperRelayConnection&>(connection);
}

#endif // OD_NET_HELPER_RELAY
