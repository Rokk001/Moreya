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

#define BOOST_TEST_MODULE HelperPipeProtocol
#include "BoostTestTargetConfig.h"

#include "network/HelperPipeProtocol.h"

#include <string>
#include <vector>

//! \brief Builds a byte vector from a fixed array.
static std::vector<uint8_t> bytes(const uint8_t* data, std::size_t size)
{
    return std::vector<uint8_t>(data, data + size);
}

// Checks the exact header and body bytes of a peerData frame against the documented layout.
BOOST_AUTO_TEST_CASE(test_peer_data_frame_layout)
{
    const uint8_t payload[] = { 0xAA, 0xBB };
    std::vector<uint8_t> frame;
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::peerData,
        HelperPipe::encodePeerData(0x0102030405060708ull, payload, sizeof(payload)), frame));

    const uint8_t expected[] = {
        0x00, 0x00, 0x00, 0x0A,                         // body size 10, big-endian
        0x01,                                           // version
        0x64,                                           // peerData
        0x00, 0x00,                                     // reserved
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, // peer id
        0xAA, 0xBB                                      // message bytes
    };
    BOOST_CHECK(frame == bytes(expected, sizeof(expected)));
}

// Checks that every body kind decodes to the values it was encoded from.
BOOST_AUTO_TEST_CASE(test_body_round_trips)
{
    uint64_t id = 0;
    BOOST_CHECK(HelperPipe::decodeId(HelperPipe::encodeId(0xFEDCBA9876543210ull), id));
    BOOST_CHECK(id == 0xFEDCBA9876543210ull);

    HelperPipe::LobbyVisibility visibility = HelperPipe::LobbyVisibility::privateLobby;
    uint16_t maxMembers = 0;
    BOOST_CHECK(HelperPipe::decodeLobbyCreate(
        HelperPipe::encodeLobbyCreate(HelperPipe::LobbyVisibility::friendsOnly, 4), visibility, maxMembers));
    BOOST_CHECK(visibility == HelperPipe::LobbyVisibility::friendsOnly);
    BOOST_CHECK(maxMembers == 4);

    uint64_t lobbyId = 0;
    uint64_t hostUserId = 0;
    BOOST_CHECK(HelperPipe::decodeLobbyJoined(HelperPipe::encodeLobbyJoined(11, 22), lobbyId, hostUserId));
    BOOST_CHECK(lobbyId == 11);
    BOOST_CHECK(hostUserId == 22);

    HelperPipe::MessageType request = HelperPipe::MessageType::hello;
    std::string reason;
    BOOST_CHECK(HelperPipe::decodeLobbyFailed(
        HelperPipe::encodeLobbyFailed(HelperPipe::MessageType::lobbyJoin, "lobby full"), request, reason));
    BOOST_CHECK(request == HelperPipe::MessageType::lobbyJoin);
    BOOST_CHECK(reason == "lobby full");

    std::string text;
    BOOST_CHECK(HelperPipe::decodeText(HelperPipe::encodeText(std::string()), text));
    BOOST_CHECK(text.empty());

    const uint8_t payload[] = { 1, 2, 3 };
    uint64_t peerId = 0;
    std::vector<uint8_t> decodedPayload;
    BOOST_CHECK(HelperPipe::decodePeerData(HelperPipe::encodePeerData(77, payload, sizeof(payload)), peerId,
        decodedPayload));
    BOOST_CHECK(peerId == 77);
    BOOST_CHECK(decodedPayload == bytes(payload, sizeof(payload)));

    // A message without bytes is still a valid peerData body
    BOOST_CHECK(HelperPipe::decodePeerData(HelperPipe::encodePeerData(78, nullptr, 0), peerId, decodedPayload));
    BOOST_CHECK(peerId == 78);
    BOOST_CHECK(decodedPayload.empty());
}

// Checks that short, overlong or out of range bodies are rejected instead of read past their end.
BOOST_AUTO_TEST_CASE(test_malformed_bodies_rejected)
{
    uint64_t id = 0;
    std::vector<uint8_t> shortId = HelperPipe::encodeId(5);
    shortId.pop_back();
    BOOST_CHECK(!HelperPipe::decodeId(shortId, id));

    std::vector<uint8_t> longId = HelperPipe::encodeId(5);
    longId.push_back(0);
    BOOST_CHECK(!HelperPipe::decodeId(longId, id));

    HelperPipe::LobbyVisibility visibility = HelperPipe::LobbyVisibility::privateLobby;
    uint16_t maxMembers = 0;
    std::vector<uint8_t> badVisibility = HelperPipe::encodeLobbyCreate(HelperPipe::LobbyVisibility::publicLobby, 2);
    badVisibility[0] = 3;
    BOOST_CHECK(!HelperPipe::decodeLobbyCreate(badVisibility, visibility, maxMembers));

    // A string that announces more bytes than the body holds
    std::string text;
    std::vector<uint8_t> shortText = HelperPipe::encodeText("abc");
    shortText.pop_back();
    BOOST_CHECK(!HelperPipe::decodeText(shortText, text));

    uint64_t peerId = 0;
    std::vector<uint8_t> payload;
    const uint8_t sevenBytes[] = { 0, 0, 0, 0, 0, 0, 0 };
    BOOST_CHECK(!HelperPipe::decodePeerData(bytes(sevenBytes, sizeof(sevenBytes)), peerId, payload));
}

// Checks that frames are reassembled when the pipe delivers them byte by byte or several in one read.
BOOST_AUTO_TEST_CASE(test_decoder_reassembles_stream)
{
    std::vector<uint8_t> stream;
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::hello, std::vector<uint8_t>(), stream));
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::lobbyCreated, HelperPipe::encodeId(42), stream));
    const uint8_t payload[] = { 9, 8, 7, 6 };
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::peerData,
        HelperPipe::encodePeerData(3, payload, sizeof(payload)), stream));

    // Byte by byte: a frame only comes out once its last byte arrived
    HelperPipe::FrameDecoder slow;
    std::vector<HelperPipe::Frame> frames;
    for(std::size_t i = 0; i < stream.size(); ++i)
    {
        slow.feed(&stream[i], 1);
        HelperPipe::Frame frame;
        HelperPipe::DecodeResult result = slow.next(frame);
        BOOST_REQUIRE(result != HelperPipe::DecodeResult::error);
        if(result == HelperPipe::DecodeResult::frame)
            frames.push_back(frame);
    }
    BOOST_REQUIRE(frames.size() == 3);
    BOOST_CHECK(slow.getBufferedSize() == 0);
    BOOST_CHECK(frames[0].mType == HelperPipe::MessageType::hello);
    BOOST_CHECK(frames[0].mBody.empty());
    BOOST_CHECK(frames[1].mType == HelperPipe::MessageType::lobbyCreated);
    uint64_t lobbyId = 0;
    BOOST_CHECK(HelperPipe::decodeId(frames[1].mBody, lobbyId));
    BOOST_CHECK(lobbyId == 42);
    BOOST_CHECK(frames[2].mType == HelperPipe::MessageType::peerData);
    uint64_t peerId = 0;
    std::vector<uint8_t> decodedPayload;
    BOOST_CHECK(HelperPipe::decodePeerData(frames[2].mBody, peerId, decodedPayload));
    BOOST_CHECK(peerId == 3);
    BOOST_CHECK(decodedPayload == bytes(payload, sizeof(payload)));

    // All in one read: three frames, then the decoder asks for more
    HelperPipe::FrameDecoder fast;
    fast.feed(stream.data(), stream.size());
    HelperPipe::Frame frame;
    BOOST_CHECK(fast.next(frame) == HelperPipe::DecodeResult::frame);
    BOOST_CHECK(fast.next(frame) == HelperPipe::DecodeResult::frame);
    BOOST_CHECK(fast.next(frame) == HelperPipe::DecodeResult::frame);
    BOOST_CHECK(fast.next(frame) == HelperPipe::DecodeResult::needMoreData);
}

// Checks that a broken header puts the decoder in a lasting error state.
BOOST_AUTO_TEST_CASE(test_decoder_rejects_broken_headers)
{
    HelperPipe::Frame frame;

    // Wrong version
    const uint8_t wrongVersion[] = { 0x00, 0x00, 0x00, 0x00, 0x02, 0x01, 0x00, 0x00 };
    HelperPipe::FrameDecoder versionDecoder;
    versionDecoder.feed(wrongVersion, sizeof(wrongVersion));
    BOOST_CHECK(versionDecoder.next(frame) == HelperPipe::DecodeResult::error);

    // Reserved field not zero
    const uint8_t reservedSet[] = { 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x01 };
    HelperPipe::FrameDecoder reservedDecoder;
    reservedDecoder.feed(reservedSet, sizeof(reservedSet));
    BOOST_CHECK(reservedDecoder.next(frame) == HelperPipe::DecodeResult::error);

    // Body larger than 16 MiB (0x01000001 bytes); rejected from the header alone
    const uint8_t oversized[] = { 0x01, 0x00, 0x00, 0x01, 0x01, 0x64, 0x00, 0x00 };
    HelperPipe::FrameDecoder sizeDecoder;
    sizeDecoder.feed(oversized, sizeof(oversized));
    BOOST_CHECK(sizeDecoder.next(frame) == HelperPipe::DecodeResult::error);

    // The error state lasts even when a valid frame follows
    std::vector<uint8_t> valid;
    BOOST_REQUIRE(HelperPipe::encodeFrame(HelperPipe::MessageType::hello, std::vector<uint8_t>(), valid));
    sizeDecoder.feed(valid.data(), valid.size());
    BOOST_CHECK(sizeDecoder.next(frame) == HelperPipe::DecodeResult::error);

    // The encoder refuses a body over the limit and leaves the output unchanged
    std::vector<uint8_t> output;
    std::vector<uint8_t> tooLarge(static_cast<std::size_t>(HelperPipe::MAX_BODY_SIZE) + 1, 0);
    BOOST_CHECK(!HelperPipe::encodeFrame(HelperPipe::MessageType::peerData, tooLarge, output));
    BOOST_CHECK(output.empty());
}
