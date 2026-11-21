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

#define BOOST_TEST_MODULE NetTransport
#include "BoostTestTargetConfig.h"

#include "network/HelperPipeProtocol.h"
#include "network/ODPacket.h"
#include "network/TcpNetTransport.h"

#include <SFML/Network.hpp>

#include <cstring>
#include <string>
#include <vector>

//! Upper bound for every wait in this test; each wait returns as soon as the data is there.
static const int WAIT_LIMIT_MS = 2000;

//! \brief A listener on a free local port with one client connected to it and accepted on the server side.
struct LoopbackPair
{
    TcpNetListener mListenerImpl;
    TcpNetConnection mClientImpl;
    TcpNetConnection mServerImpl;
    NetListener& mListener;
    NetConnection& mClient;
    NetConnection& mServer;

    //! \brief Listens, connects and accepts through the interfaces; the test fails if any step does not succeed.
    LoopbackPair():
        mListener(mListenerImpl),
        mClient(mClientImpl),
        mServer(mServerImpl)
    {
        BOOST_REQUIRE(mListener.listen(NetListener::AnyPort) == NetStatus::Done);
        BOOST_REQUIRE(mListener.getLocalPort() != 0);
        BOOST_REQUIRE(mClient.connect("127.0.0.1", mListener.getLocalPort(), WAIT_LIMIT_MS) == NetStatus::Done);
        BOOST_REQUIRE(mListener.wait(WAIT_LIMIT_MS));
        BOOST_REQUIRE(mListener.isPendingConnection());
        BOOST_REQUIRE(mListener.accept(mServer) == NetStatus::Done);
        mListener.watch(mServer);
    }

    //! \brief Closes the listener (which forgets the watched connection) and both ends.
    ~LoopbackPair()
    {
        mListener.close();
        mClient.disconnect();
        mServer.disconnect();
    }
};

// Checks that a message goes from client to server and back unchanged through the transport interfaces.
BOOST_AUTO_TEST_CASE(test_tcp_loopback_exchange)
{
    LoopbackPair pair;
    BOOST_CHECK(pair.mClient.getKind() == NetTransportKind::tcp);
    BOOST_CHECK(pair.mListener.getKind() == NetTransportKind::tcp);

    ODPacket request;
    const int32_t requestNumber = -12345;
    const std::string requestText("hello host");
    request << requestNumber << requestText;
    BOOST_REQUIRE(pair.mClient.send(request) == NetStatus::Done);

    BOOST_REQUIRE(pair.mListener.wait(WAIT_LIMIT_MS));
    BOOST_CHECK(!pair.mListener.isPendingConnection());
    BOOST_REQUIRE(pair.mListener.isReady(pair.mServer));
    ODPacket received;
    BOOST_REQUIRE(pair.mServer.receive(received) == NetStatus::Done);
    int32_t number = 0;
    std::string text;
    received >> number >> text;
    BOOST_CHECK(received);
    BOOST_CHECK(number == requestNumber);
    BOOST_CHECK(text == requestText);

    ODPacket reply;
    const uint64_t replyNumber = 0x0123456789ABCDEFull;
    reply << replyNumber;
    BOOST_REQUIRE(pair.mServer.send(reply) == NetStatus::Done);
    BOOST_REQUIRE(pair.mClient.waitForData(WAIT_LIMIT_MS));
    ODPacket replyReceived;
    BOOST_REQUIRE(pair.mClient.receive(replyReceived) == NetStatus::Done);
    uint64_t number64 = 0;
    replyReceived >> number64;
    BOOST_CHECK(number64 == replyNumber);

    // After unwatch the listener no longer waits for the connection, which still receives on its own
    pair.mListener.unwatch(pair.mServer);
    BOOST_REQUIRE(pair.mClient.send(request) == NetStatus::Done);
    BOOST_REQUIRE(pair.mServer.receive(received) == NetStatus::Done);
}

// Checks that the bytes on the wire are those of sf::Packet: a 32 bit big-endian length and the packet bytes.
BOOST_AUTO_TEST_CASE(test_tcp_wire_format_unchanged)
{
    TcpNetListener listenerImpl;
    NetListener& listener = listenerImpl;
    BOOST_REQUIRE(listener.listen(NetListener::AnyPort) == NetStatus::Done);

    sf::TcpSocket rawClient;
    BOOST_REQUIRE(rawClient.connect(sf::IpAddress::LocalHost, listener.getLocalPort(), sf::milliseconds(WAIT_LIMIT_MS))
        == sf::Socket::Status::Done);
    BOOST_REQUIRE(listener.wait(WAIT_LIMIT_MS));
    TcpNetConnection serverImpl;
    NetConnection& server = serverImpl;
    BOOST_REQUIRE(listener.accept(server) == NetStatus::Done);

    ODPacket packet;
    const int32_t number = 7;
    const std::string text("wire");
    packet << number << text;
    BOOST_REQUIRE(server.send(packet) == NetStatus::Done);

    const std::size_t dataSize = packet.getRawDataSize();
    std::vector<uint8_t> expected;
    HelperPipe::appendUnsigned(expected, static_cast<uint64_t>(dataSize), 4);
    const uint8_t* data = static_cast<const uint8_t*>(packet.getRawData());
    expected.insert(expected.end(), data, data + dataSize);

    // Blocking raw reads until all expected bytes are there; the server sent them already
    std::vector<uint8_t> wire(expected.size(), 0);
    std::size_t total = 0;
    while(total < wire.size())
    {
        std::size_t received = 0;
        BOOST_REQUIRE(rawClient.receive(&wire[total], wire.size() - total, received) == sf::Socket::Status::Done);
        total += received;
    }
    BOOST_CHECK(wire == expected);

    rawClient.disconnect();
    server.disconnect();
    listener.close();
}

// Checks that a non blocking receive without a message reports NotReady and that blocking mode can be restored.
BOOST_AUTO_TEST_CASE(test_tcp_non_blocking_poll)
{
    LoopbackPair pair;
    BOOST_CHECK(pair.mClient.isBlocking());
    pair.mClient.setBlocking(false);
    BOOST_CHECK(!pair.mClient.isBlocking());
    ODPacket nothing;
    BOOST_CHECK(pair.mClient.receive(nothing) == NetStatus::NotReady);
    pair.mClient.setBlocking(true);
    BOOST_CHECK(pair.mClient.isBlocking());
}

// Checks that closing one end is reported as Disconnected on the other end.
BOOST_AUTO_TEST_CASE(test_tcp_disconnect_reported)
{
    LoopbackPair pair;
    pair.mServer.disconnect();
    ODPacket packet;
    BOOST_CHECK(pair.mClient.receive(packet) == NetStatus::Disconnected);
}

// Checks that ODPacket bytes carried in a peerData frame rebuild an identical packet (helper relay path).
BOOST_AUTO_TEST_CASE(test_packet_bytes_through_pipe_frame)
{
    ODPacket packet;
    const int32_t number = 99;
    const std::string text("relayed");
    packet << number << text;

    std::vector<uint8_t> stream;
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::peerData,
        HelperPipe::encodePeerData(5, packet.getRawData(), packet.getRawDataSize()), stream));

    HelperPipe::FrameDecoder decoder;
    decoder.feed(stream.data(), stream.size());
    HelperPipe::Frame frame;
    BOOST_REQUIRE(decoder.next(frame) == HelperPipe::DecodeResult::frame);
    uint64_t peerId = 0;
    std::vector<uint8_t> payload;
    BOOST_REQUIRE(HelperPipe::decodePeerData(frame.mBody, peerId, payload));
    BOOST_CHECK(peerId == 5);
    BOOST_REQUIRE(payload.size() == packet.getRawDataSize());
    BOOST_CHECK(std::memcmp(payload.data(), packet.getRawData(), payload.size()) == 0);

    ODPacket rebuilt;
    rebuilt.setRawData(payload.data(), payload.size());
    int32_t numberOut = 0;
    std::string textOut;
    rebuilt >> numberOut >> textOut;
    BOOST_CHECK(rebuilt);
    BOOST_CHECK(numberOut == number);
    BOOST_CHECK(textOut == text);
}
