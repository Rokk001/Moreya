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

// The game side of the helper relay against the test-only fake helper (mocks/FakeNetHelper.cpp), which speaks
// HelperPipeProtocol.h with fixed answers. No platform SDK is involved. The path of the fake helper program comes
// from the macro OD_FAKE_NET_HELPER (source/tests/CMakeLists.txt, check_helper_relay.py).

#define BOOST_TEST_MODULE HelperRelay
#include "BoostTestTargetConfig.h"

#include "network/HelperPipeProtocol.h"
#include "network/HelperRelayProcess.h"
#include "network/HelperRelayTransport.h"
#include "network/ODPacket.h"
#include "network/TcpNetTransport.h"
#include "utils/LogManager.h"

#include <chrono>
#include <cstring>
#include <string>
#include <vector>

//! Upper bound for every wait in this test; each wait returns as soon as the awaited event is there.
static const int WAIT_LIMIT_MS = 2000;

//! Fixed values of the fake helper (see mocks/FakeNetHelper.cpp).
static const uint64_t FAKE_LOCAL_USER_ID = 1001;
static const uint64_t FAKE_CREATED_LOBBY_ID = 5001;
static const uint64_t FAKE_JOINING_PEER_ID = 2002;
static const uint64_t FAKE_HOST_USER_ID = 3003;
static const uint64_t FAKE_INVITE_LOBBY_ID = 6001;
static const uint64_t FAKE_EXIT_LOBBY_ID = 9999;
static const int FAKE_EXIT_CODE = 7;

//! \brief Path of the fake helper program, given by the build as the macro OD_FAKE_NET_HELPER.
static std::string fakeHelperPath()
{
#ifdef OD_FAKE_NET_HELPER
    return std::string(OD_FAKE_NET_HELPER);
#else
    return std::string();
#endif
}

//! \brief Milliseconds left until the deadline, at least 1 while it is in the future, 0 after it.
static int remainingMs(const std::chrono::steady_clock::time_point& deadline)
{
    std::chrono::steady_clock::duration left = deadline - std::chrono::steady_clock::now();
    long long milliseconds = std::chrono::duration_cast<std::chrono::milliseconds>(left).count();
    if(milliseconds <= 0)
        return (left.count() > 0) ? 1 : 0;
    return static_cast<int>(milliseconds);
}

//! \brief Writes every lobby event as one line, so a test can compare the sequence it got.
class RecordingObserver : public HelperLobbyObserver
{
public:
    //! \brief Records "ready <id>".
    void onHelperReady(uint64_t localUserId) override
    { mEvents.push_back("ready " + std::to_string(localUserId)); }

    //! \brief Records "created <id>".
    void onLobbyCreated(uint64_t lobbyId) override
    { mEvents.push_back("created " + std::to_string(lobbyId)); }

    //! \brief Records "joined <lobby> <host>".
    void onLobbyJoined(uint64_t lobbyId, uint64_t hostUserId) override
    { mEvents.push_back("joined " + std::to_string(lobbyId) + " " + std::to_string(hostUserId)); }

    //! \brief Records "invite <id>".
    void onLobbyInviteAccepted(uint64_t lobbyId) override
    { mEvents.push_back("invite " + std::to_string(lobbyId)); }

    //! \brief Records "failed <request type> <reason>".
    void onLobbyFailed(HelperPipe::MessageType request, const std::string& reason) override
    { mEvents.push_back("failed " + std::to_string(static_cast<int>(request)) + " " + reason); }

    //! \brief Records "error <text>".
    void onHelperError(const std::string& text) override
    { mEvents.push_back("error " + text); }

    //! \brief Records "exited <code>".
    void onHelperExited(int exitCode) override
    { mEvents.push_back("exited " + std::to_string(exitCode)); }

    std::vector<std::string> mEvents;
};

//! \brief Dispatches lobby events until the observer holds count of them or WAIT_LIMIT_MS passed.
static bool dispatchUntil(HelperRelayProcess& process, RecordingObserver& observer, std::size_t count)
{
    std::chrono::steady_clock::time_point deadline = std::chrono::steady_clock::now()
        + std::chrono::milliseconds(WAIT_LIMIT_MS);
    while(observer.mEvents.size() < count)
    {
        int remaining = remainingMs(deadline);
        if(remaining == 0)
            return false;
        if(process.waitForLobbyEvent(remaining))
            process.dispatchLobbyEvents();
    }
    return true;
}

//! \brief Waits on the listener until a new peer waits to be accepted or WAIT_LIMIT_MS passed.
static bool waitForPendingConnection(NetListener& listener)
{
    std::chrono::steady_clock::time_point deadline = std::chrono::steady_clock::now()
        + std::chrono::milliseconds(WAIT_LIMIT_MS);
    while(!listener.isPendingConnection())
    {
        int remaining = remainingMs(deadline);
        if(remaining == 0)
            return false;
        listener.wait(remaining);
    }
    return true;
}

//! \brief Waits on the listener until the watched connection is ready or WAIT_LIMIT_MS passed.
static bool waitForReadyConnection(NetListener& listener, NetConnection& connection)
{
    std::chrono::steady_clock::time_point deadline = std::chrono::steady_clock::now()
        + std::chrono::milliseconds(WAIT_LIMIT_MS);
    while(true)
    {
        int remaining = remainingMs(deadline);
        if(remaining == 0)
            return false;
        if(listener.wait(remaining) && listener.isReady(connection))
            return true;
    }
}

//! \brief A packet with a number and a text, for the exchange checks.
static void fillPacket(ODPacket& packet, int32_t number, const std::string& text)
{
    packet << number << text;
}

//! \brief Whether the packet holds exactly the number and the text of fillPacket().
static bool packetHolds(ODPacket& packet, int32_t number, const std::string& text)
{
    int32_t numberOut = 0;
    std::string textOut;
    packet >> numberOut >> textOut;
    return packet && (numberOut == number) && (textOut == text);
}

//! \brief A log manager and a started fake helper that answered ready; stops it at the end of the test.
struct RunningHelper
{
    LogManager mLogManager;
    HelperRelayProcess mProcess;
    RecordingObserver mObserver;

    //! \brief Starts the fake helper with the given arguments and waits for ready; the test fails otherwise.
    explicit RunningHelper(const std::vector<std::string>& arguments)
    {
        mProcess.setLobbyObserver(&mObserver);
        BOOST_REQUIRE(!fakeHelperPath().empty());
        BOOST_REQUIRE(mProcess.start(fakeHelperPath(), arguments));
        BOOST_REQUIRE(mProcess.waitForReady(WAIT_LIMIT_MS));
    }

    //! \brief Stops the helper (bounded) before the log manager goes.
    ~RunningHelper()
    {
        mProcess.stop(WAIT_LIMIT_MS);
        mProcess.setLobbyObserver(nullptr);
    }
};

// Checks the hello/ready handshake with an argument passed to the helper, and a clean shutdown with exit code 0.
BOOST_AUTO_TEST_CASE(test_handshake_and_shutdown)
{
    std::vector<std::string> arguments;
    arguments.push_back("--local-user");
    arguments.push_back("4242");
    RunningHelper helper(arguments);
    BOOST_CHECK(helper.mProcess.isRunning());
    BOOST_CHECK(helper.mProcess.isReady());
    BOOST_CHECK_EQUAL(helper.mProcess.getLocalUserId(), 4242u);
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 1));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[0], std::string("ready 4242"));

    helper.mProcess.stop(WAIT_LIMIT_MS);
    BOOST_CHECK(helper.mProcess.hasExited());
    BOOST_CHECK(!helper.mProcess.isRunning());
    BOOST_CHECK_EQUAL(helper.mProcess.getExitCode(), 0);
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 2));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[1], std::string("exited 0"));
}

// Checks that a helper program that does not exist is reported by start() and leaves no running process.
BOOST_AUTO_TEST_CASE(test_missing_helper)
{
    LogManager logManager;
    HelperRelayProcess process;
    std::string missing = fakeHelperPath() + ".missing";
    BOOST_CHECK(!process.start(missing, std::vector<std::string>()));
    BOOST_CHECK(!process.isRunning());
    BOOST_CHECK(!process.isReady());
    BOOST_CHECK(!process.createLobby(HelperPipe::LobbyVisibility::friendsOnly, 4));
}

// Checks the lobby API: create, invite, join and the failure answers, each delivered once through the observer.
BOOST_AUTO_TEST_CASE(test_lobby_requests)
{
    RunningHelper helper((std::vector<std::string>()));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 1));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[0], "ready " + std::to_string(FAKE_LOCAL_USER_ID));

    BOOST_REQUIRE(helper.mProcess.createLobby(HelperPipe::LobbyVisibility::friendsOnly, 4));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 2));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[1], "created " + std::to_string(FAKE_CREATED_LOBBY_ID));
    BOOST_CHECK_EQUAL(helper.mProcess.getLobbyId(), FAKE_CREATED_LOBBY_ID);
    BOOST_CHECK(helper.mProcess.isLobbyHost());
    BOOST_CHECK_EQUAL(helper.mProcess.getHostUserId(), FAKE_LOCAL_USER_ID);

    BOOST_REQUIRE(helper.mProcess.inviteToLobby());
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 3));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[2], "invite " + std::to_string(FAKE_INVITE_LOBBY_ID));

    BOOST_REQUIRE(helper.mProcess.joinLobby(42));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 4));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[3], "joined 42 " + std::to_string(FAKE_HOST_USER_ID));
    BOOST_CHECK(!helper.mProcess.isLobbyHost());
    BOOST_CHECK_EQUAL(helper.mProcess.getHostUserId(), FAKE_HOST_USER_ID);

    BOOST_REQUIRE(helper.mProcess.joinLobby(0));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 5));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[4],
        "failed " + std::to_string(static_cast<int>(HelperPipe::MessageType::lobbyJoin)) + " unknown lobby");

    BOOST_REQUIRE(helper.mProcess.createLobby(HelperPipe::LobbyVisibility::privateLobby, 0));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 6));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[5],
        "failed " + std::to_string(static_cast<int>(HelperPipe::MessageType::lobbyCreate)) + " no members");

    BOOST_REQUIRE(helper.mProcess.leaveLobby());
    BOOST_CHECK_EQUAL(helper.mProcess.getLobbyId(), 0u);
    BOOST_CHECK_EQUAL(helper.mProcess.dispatchLobbyEvents(), 0u);
}

// Checks the host side: the own client connects by TCP on localhost, a lobby peer is accepted from peerConnected,
// messages go both ways, a non blocking receive polls, and leaving the lobby reads as Disconnected.
BOOST_AUTO_TEST_CASE(test_host_listener_tcp_and_relay)
{
    RunningHelper helper((std::vector<std::string>()));
    HelperRelayListener listenerImpl(&helper.mProcess);
    NetListener& listener = listenerImpl;
    BOOST_CHECK(listener.getKind() == NetTransportKind::helperRelay);
    BOOST_REQUIRE(listener.listen(NetListener::AnyPort) == NetStatus::Done);
    BOOST_REQUIRE(listener.getLocalPort() != 0);

    // The host's own client: a relay connection to localhost is a plain TCP connection
    HelperRelayConnection ownClientImpl(&helper.mProcess);
    NetConnection& ownClient = ownClientImpl;
    BOOST_REQUIRE(ownClient.connect("127.0.0.1", listener.getLocalPort(), WAIT_LIMIT_MS) == NetStatus::Done);
    BOOST_CHECK(ownClientImpl.getTcp() != nullptr);
    BOOST_REQUIRE(waitForPendingConnection(listener));
    HelperRelayConnection ownServerSideImpl(&helper.mProcess);
    NetConnection& ownServerSide = ownServerSideImpl;
    BOOST_REQUIRE(listener.accept(ownServerSide) == NetStatus::Done);
    BOOST_CHECK(ownServerSideImpl.getTcp() != nullptr);
    BOOST_CHECK_EQUAL(ownServerSideImpl.getPeerId(), 0u);
    listener.watch(ownServerSide);

    ODPacket local;
    fillPacket(local, 11, "own client");
    BOOST_REQUIRE(ownClient.send(local) == NetStatus::Done);
    BOOST_REQUIRE(waitForReadyConnection(listener, ownServerSide));
    ODPacket localReceived;
    BOOST_REQUIRE(ownServerSide.receive(localReceived) == NetStatus::Done);
    BOOST_CHECK(packetHolds(localReceived, 11, "own client"));

    // A lobby peer: lobbyCreated is followed by peerConnected of the fake helper
    BOOST_REQUIRE(helper.mProcess.createLobby(HelperPipe::LobbyVisibility::friendsOnly, 4));
    BOOST_REQUIRE(waitForPendingConnection(listener));
    HelperRelayConnection peerImpl(&helper.mProcess);
    NetConnection& peer = peerImpl;
    BOOST_REQUIRE(listener.accept(peer) == NetStatus::Done);
    BOOST_CHECK_EQUAL(peerImpl.getPeerId(), FAKE_JOINING_PEER_ID);
    BOOST_CHECK(peerImpl.getTcp() == nullptr);
    BOOST_CHECK(!listener.isPendingConnection());
    listener.watch(peer);

    peer.setBlocking(false);
    ODPacket nothing;
    BOOST_CHECK(peer.receive(nothing) == NetStatus::NotReady);

    // The fake helper echoes peerData, so the message comes back from the peer unchanged
    ODPacket relayed;
    fillPacket(relayed, -77, "through the helper");
    BOOST_REQUIRE(peer.send(relayed) == NetStatus::Done);
    BOOST_REQUIRE(waitForReadyConnection(listener, peer));
    ODPacket relayedReceived;
    BOOST_REQUIRE(peer.receive(relayedReceived) == NetStatus::Done);
    BOOST_CHECK(packetHolds(relayedReceived, -77, "through the helper"));
    BOOST_CHECK(relayedReceived.getRawDataSize() == relayed.getRawDataSize());
    BOOST_CHECK(std::memcmp(relayedReceived.getRawData(), relayed.getRawData(), relayed.getRawDataSize()) == 0);

    // Leaving the lobby makes the fake helper report peerDisconnected
    BOOST_REQUIRE(helper.mProcess.leaveLobby());
    BOOST_REQUIRE(waitForReadyConnection(listener, peer));
    BOOST_CHECK(peer.receive(nothing) == NetStatus::Disconnected);
    BOOST_CHECK(peer.send(relayed) == NetStatus::Disconnected);

    listener.unwatch(peer);
    peer.disconnect();
    listener.unwatch(ownServerSide);
    ownServerSide.disconnect();
    ownClient.disconnect();
    listener.close();
}

// Checks the client side: a lobby address joins through the helper and talks to the host both ways, a lobbyFailed
// answer or a missing process fails the join, and only "lobby:<id>" counts as a lobby address.
BOOST_AUTO_TEST_CASE(test_client_connection_joins_lobby)
{
    uint64_t parsed = 0;
    BOOST_CHECK(HelperRelayConnection::parseLobbyAddress(HelperRelayConnection::formatLobbyAddress(42), parsed));
    BOOST_CHECK_EQUAL(parsed, 42u);
    BOOST_CHECK(HelperRelayConnection::parseLobbyAddress("lobby:18446744073709551615", parsed));
    BOOST_CHECK(parsed == 18446744073709551615ull);
    BOOST_CHECK(!HelperRelayConnection::parseLobbyAddress("lobby:18446744073709551616", parsed));
    BOOST_CHECK(!HelperRelayConnection::parseLobbyAddress("lobby:0", parsed));
    BOOST_CHECK(!HelperRelayConnection::parseLobbyAddress("lobby:", parsed));
    BOOST_CHECK(!HelperRelayConnection::parseLobbyAddress("lobby:12a", parsed));
    BOOST_CHECK(!HelperRelayConnection::parseLobbyAddress("localhost", parsed));

    RunningHelper helper((std::vector<std::string>()));
    HelperRelayConnection clientImpl(&helper.mProcess);
    NetConnection& client = clientImpl;
    BOOST_CHECK(client.getKind() == NetTransportKind::helperRelay);
    BOOST_REQUIRE(client.connect(HelperRelayConnection::formatLobbyAddress(42), 0, WAIT_LIMIT_MS) == NetStatus::Done);
    BOOST_CHECK_EQUAL(clientImpl.getPeerId(), FAKE_HOST_USER_ID);

    ODPacket request;
    fillPacket(request, 5, "to the host");
    BOOST_REQUIRE(client.send(request) == NetStatus::Done);
    BOOST_REQUIRE(client.waitForData(WAIT_LIMIT_MS));
    ODPacket reply;
    BOOST_REQUIRE(client.receive(reply) == NetStatus::Done);
    BOOST_CHECK(packetHolds(reply, 5, "to the host"));

    client.disconnect();
    BOOST_CHECK_EQUAL(clientImpl.getPeerId(), 0u);

    // A second connection joins another lobby; the answer to the earlier join does not count for it
    HelperRelayConnection secondImpl(&helper.mProcess);
    NetConnection& second = secondImpl;
    BOOST_CHECK(second.connect("lobby:1", 0, WAIT_LIMIT_MS) == NetStatus::Done);
    BOOST_CHECK_EQUAL(helper.mProcess.getLobbyId(), 1u);
    second.disconnect();

    // lobbyFailed for the join ends the wait at once
    uint64_t hostUserId = 0;
    BOOST_CHECK(!helper.mProcess.joinLobbyAndWait(0, WAIT_LIMIT_MS, hostUserId));

    // Without a process a lobby address cannot be joined
    HelperRelayConnection orphanImpl(nullptr);
    NetConnection& orphan = orphanImpl;
    BOOST_CHECK(orphan.connect(HelperRelayConnection::formatLobbyAddress(42), 0, WAIT_LIMIT_MS) == NetStatus::Error);
}

// Checks that an exit of the helper is detected: error and exit code reach the observer, relayed peers read as
// Disconnected and lobby requests fail.
BOOST_AUTO_TEST_CASE(test_helper_exit_detected)
{
    RunningHelper helper((std::vector<std::string>()));
    HelperRelayConnection clientImpl(&helper.mProcess);
    NetConnection& client = clientImpl;
    BOOST_REQUIRE(client.connect(HelperRelayConnection::formatLobbyAddress(42), 0, WAIT_LIMIT_MS) == NetStatus::Done);
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 2));

    // Joining this lobby makes the fake helper report an error and exit
    BOOST_REQUIRE(helper.mProcess.joinLobby(FAKE_EXIT_LOBBY_ID));
    BOOST_REQUIRE(dispatchUntil(helper.mProcess, helper.mObserver, 4));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[2], std::string("error fake helper stops"));
    BOOST_CHECK_EQUAL(helper.mObserver.mEvents[3], "exited " + std::to_string(FAKE_EXIT_CODE));
    BOOST_CHECK(helper.mProcess.hasExited());
    BOOST_CHECK(!helper.mProcess.isRunning());
    BOOST_CHECK_EQUAL(helper.mProcess.getExitCode(), FAKE_EXIT_CODE);

    BOOST_CHECK(client.waitForData(WAIT_LIMIT_MS));
    ODPacket packet;
    BOOST_CHECK(client.receive(packet) == NetStatus::Disconnected);
    fillPacket(packet, 1, "after exit");
    BOOST_CHECK(client.send(packet) == NetStatus::Disconnected);
    BOOST_CHECK(!helper.mProcess.createLobby(HelperPipe::LobbyVisibility::friendsOnly, 4));
    client.disconnect();
}
