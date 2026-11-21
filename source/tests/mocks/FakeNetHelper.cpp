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

/*! \file FakeNetHelper.cpp
 * \brief Test-only stand-in for the relay helper program (no platform, no network).
 *
 * It reads HelperPipeProtocol.h frames from its standard input and answers on its standard output with fixed
 * values, so test_HelperRelay.cpp can run the whole game side of the relay. The answers:
 *
 *     hello                         ready(localUserId), 1001 or the value of --local-user <id>
 *     lobbyCreate, maxMembers > 0   lobbyCreated(5001), then peerConnected(2002)
 *     lobbyCreate, maxMembers 0     lobbyFailed(lobbyCreate, "no members")
 *     lobbyJoin(9999)               error("fake helper stops"), then exit with code 7
 *     lobbyJoin(0)                  lobbyFailed(lobbyJoin, "unknown lobby")
 *     lobbyJoin(id)                 lobbyJoined(id, 3003)
 *     lobbyInvite                   lobbyInviteAccepted(6001)
 *     lobbyLeave                    peerDisconnected for every connected peer
 *     peerData(peer, bytes)         the same peerData back (echo)
 *     peerClose(peer)               the peer is no longer connected
 *     shutdown or end of input      exit with code 0
 */

#include "network/HelperPipeProtocol.h"

#include <cstdlib>
#include <cstring>
#include <set>
#include <string>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <stdio.h>
#else
#include <cerrno>
#include <unistd.h>
#endif

namespace
{
    const uint64_t DEFAULT_LOCAL_USER_ID = 1001;
    const uint64_t CREATED_LOBBY_ID = 5001;
    const uint64_t JOINING_PEER_ID = 2002;
    const uint64_t HOST_USER_ID = 3003;
    const uint64_t INVITE_LOBBY_ID = 6001;
    const uint64_t EXIT_LOBBY_ID = 9999;
    const int EXIT_CODE_ON_REQUEST = 7;
    const int EXIT_CODE_BROKEN_STREAM = 2;

    //! \brief Reads what is there from standard input; 0 at the end of the input.
    std::size_t readInput(uint8_t* buffer, std::size_t size)
    {
#ifdef _WIN32
        int received = _read(0, buffer, static_cast<unsigned int>(size));
        return (received > 0) ? static_cast<std::size_t>(received) : 0;
#else
        ssize_t received = 0;
        do
        {
            received = read(STDIN_FILENO, buffer, size);
        } while((received < 0) && (errno == EINTR));
        return (received > 0) ? static_cast<std::size_t>(received) : 0;
#endif
    }

    //! \brief Writes all bytes to standard output without buffering.
    bool writeOutput(const std::vector<uint8_t>& bytes)
    {
        std::size_t offset = 0;
        while(offset < bytes.size())
        {
#ifdef _WIN32
            int written = _write(1, bytes.data() + offset, static_cast<unsigned int>(bytes.size() - offset));
#else
            ssize_t written = write(STDOUT_FILENO, bytes.data() + offset, bytes.size() - offset);
            if((written < 0) && (errno == EINTR))
                continue;
#endif
            if(written <= 0)
                return false;
            offset += static_cast<std::size_t>(written);
        }
        return true;
    }

    //! \brief Encodes and writes one frame.
    bool sendFrame(HelperPipe::MessageType type, const std::vector<uint8_t>& body)
    {
        std::vector<uint8_t> frame;
        if(!HelperPipe::encodeFrame(type, body, frame))
            return false;
        return writeOutput(frame);
    }

    //! \brief State of the fake helper between frames.
    struct FakeState
    {
        uint64_t mLocalUserId;
        std::set<uint64_t> mConnectedPeers;
    };

    /*! \brief Answers one frame as described in the file comment. Returns false when the helper ends, with the
     * exit code in exitCode.
     */
    bool handleFrame(const HelperPipe::Frame& frame, FakeState& state, int& exitCode)
    {
        switch(frame.mType)
        {
            case HelperPipe::MessageType::hello:
                return sendFrame(HelperPipe::MessageType::ready, HelperPipe::encodeId(state.mLocalUserId));
            case HelperPipe::MessageType::shutdown:
                exitCode = 0;
                return false;
            case HelperPipe::MessageType::lobbyCreate:
            {
                HelperPipe::LobbyVisibility visibility = HelperPipe::LobbyVisibility::privateLobby;
                uint16_t maxMembers = 0;
                if(!HelperPipe::decodeLobbyCreate(frame.mBody, visibility, maxMembers) || (maxMembers == 0))
                {
                    return sendFrame(HelperPipe::MessageType::lobbyFailed,
                        HelperPipe::encodeLobbyFailed(HelperPipe::MessageType::lobbyCreate, "no members"));
                }
                state.mConnectedPeers.insert(JOINING_PEER_ID);
                return sendFrame(HelperPipe::MessageType::lobbyCreated, HelperPipe::encodeId(CREATED_LOBBY_ID))
                    && sendFrame(HelperPipe::MessageType::peerConnected, HelperPipe::encodeId(JOINING_PEER_ID));
            }
            case HelperPipe::MessageType::lobbyJoin:
            {
                uint64_t lobbyId = 0;
                if(!HelperPipe::decodeId(frame.mBody, lobbyId) || (lobbyId == 0))
                {
                    return sendFrame(HelperPipe::MessageType::lobbyFailed,
                        HelperPipe::encodeLobbyFailed(HelperPipe::MessageType::lobbyJoin, "unknown lobby"));
                }
                if(lobbyId == EXIT_LOBBY_ID)
                {
                    sendFrame(HelperPipe::MessageType::error, HelperPipe::encodeText("fake helper stops"));
                    exitCode = EXIT_CODE_ON_REQUEST;
                    return false;
                }
                state.mConnectedPeers.insert(HOST_USER_ID);
                return sendFrame(HelperPipe::MessageType::lobbyJoined, HelperPipe::encodeLobbyJoined(lobbyId, HOST_USER_ID));
            }
            case HelperPipe::MessageType::lobbyInvite:
                return sendFrame(HelperPipe::MessageType::lobbyInviteAccepted, HelperPipe::encodeId(INVITE_LOBBY_ID));
            case HelperPipe::MessageType::lobbyLeave:
            {
                for(std::set<uint64_t>::const_iterator it = state.mConnectedPeers.begin(); it != state.mConnectedPeers.end(); ++it)
                {
                    if(!sendFrame(HelperPipe::MessageType::peerDisconnected, HelperPipe::encodeId(*it)))
                        return false;
                }
                state.mConnectedPeers.clear();
                return true;
            }
            case HelperPipe::MessageType::peerClose:
            {
                uint64_t peerId = 0;
                if(HelperPipe::decodeId(frame.mBody, peerId))
                    state.mConnectedPeers.erase(peerId);
                return true;
            }
            case HelperPipe::MessageType::peerData:
                return sendFrame(HelperPipe::MessageType::peerData, frame.mBody);
            default:
                // Unknown frames are ignored, as the protocol says
                return true;
        }
    }
}

//! \brief Reads frames until shutdown, the end of the input or a frame that ends the fake helper.
int main(int argc, char** argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    FakeState state;
    state.mLocalUserId = DEFAULT_LOCAL_USER_ID;
    for(int i = 1; i + 1 < argc; ++i)
    {
        if(std::strcmp(argv[i], "--local-user") == 0)
            state.mLocalUserId = std::strtoull(argv[i + 1], nullptr, 10);
    }

    HelperPipe::FrameDecoder decoder;
    std::vector<uint8_t> buffer(4096);
    while(true)
    {
        std::size_t count = readInput(buffer.data(), buffer.size());
        if(count == 0)
            return 0;
        decoder.feed(buffer.data(), count);

        HelperPipe::Frame frame;
        HelperPipe::DecodeResult result = decoder.next(frame);
        while(result == HelperPipe::DecodeResult::frame)
        {
            int exitCode = 0;
            if(!handleFrame(frame, state, exitCode))
                return exitCode;
            result = decoder.next(frame);
        }
        if(result == HelperPipe::DecodeResult::error)
            return EXIT_CODE_BROKEN_STREAM;
    }
}
