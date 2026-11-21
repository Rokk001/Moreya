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

#ifndef HELPERPIPEPROTOCOL_H
#define HELPERPIPEPROTOCOL_H

/*! \file HelperPipeProtocol.h
 * \brief Message framing between the game and the relay helper process (header only, no dependencies).
 *
 * The game starts the helper as a child process and talks to it over a pair of pipes (the helper's
 * standard input and output, or two named pipes). The helper is a separate program with its own licence;
 * it is the only part that talks to the platform lobby and relay service. This file is the whole contract
 * between the two: the helper can be written in any language from this description alone.
 *
 * Byte stream in each direction: a sequence of frames.
 *
 *     offset size  field
 *     0      4     bodySize   unsigned, big-endian, at most MAX_BODY_SIZE
 *     4      1     version    PROTOCOL_VERSION
 *     5      1     type       MessageType
 *     6      2     reserved   0
 *     8      n     body       bodySize bytes, layout depends on type
 *
 * Body fields use the same encoding: unsigned integers big-endian; ids are 64 bit; a string is a 32 bit
 * byte count followed by UTF-8 bytes. A receiver ignores frames of an unknown type (newer peer) but
 * treats a wrong version, a non zero reserved field or an oversized body as a broken stream and closes it.
 *
 * Message types and bodies (G = game, H = helper):
 *
 *     hello              G->H  (empty)                    first frame of the game
 *     ready              H->G  u64 localUserId            helper is logged in to the platform
 *     shutdown           G->H  (empty)                    helper leaves the lobby and exits
 *     lobbyCreate        G->H  u8 visibility, u16 maxMembers
 *     lobbyCreated       H->G  u64 lobbyId                the game is host of this lobby
 *     lobbyJoin          G->H  u64 lobbyId
 *     lobbyJoined        H->G  u64 lobbyId, u64 hostUserId
 *     lobbyLeave         G->H  (empty)
 *     lobbyInvite        G->H  (empty)                    open the platform invite dialog for the lobby
 *     lobbyInviteAccepted H->G u64 lobbyId                the player accepted an invite outside the game
 *     lobbyFailed        H->G  u8 requestType, string reason
 *     peerConnected      H->G  u64 peerId                 a member opened a relay session to the host
 *     peerDisconnected   H->G  u64 peerId
 *     peerClose          G->H  u64 peerId                 close the relay session to this peer
 *     peerData           both  u64 peerId, payload        one ODPacket, see below
 *     error              H->G  string text                fatal helper error, the helper exits
 *
 * peerData carries exactly one game message: the ODPacket bytes (ODPacket::getRawData()) without the
 * 32 bit length prefix the TCP backend puts in front of it. The payload size is bodySize - 8. On the
 * client, peerId is the host. The helper delivers peerData reliably and in order per peer and splits and
 * joins it if the platform limits the message size.
 */

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace HelperPipe
{
    //! \brief Version written in every frame header.
    const uint8_t PROTOCOL_VERSION = 1;

    //! \brief Size of the frame header in bytes.
    const std::size_t HEADER_SIZE = 8;

    //! \brief Largest body accepted; a larger announced size means a broken stream.
    const uint32_t MAX_BODY_SIZE = 16u * 1024u * 1024u;

    //! \brief Frame types. The numbers are part of the protocol and never change meaning.
    enum class MessageType : uint8_t
    {
        hello = 1,
        shutdown = 2,
        lobbyCreate = 10,
        lobbyJoin = 11,
        lobbyLeave = 12,
        lobbyInvite = 13,
        peerClose = 20,
        ready = 64,
        lobbyCreated = 70,
        lobbyJoined = 71,
        lobbyInviteAccepted = 72,
        lobbyFailed = 73,
        peerConnected = 80,
        peerDisconnected = 81,
        error = 90,
        peerData = 100
    };

    //! \brief Who may join a lobby created with lobbyCreate.
    enum class LobbyVisibility : uint8_t
    {
        privateLobby = 0,
        friendsOnly = 1,
        publicLobby = 2
    };

    //! \brief One decoded frame.
    struct Frame
    {
        MessageType mType;
        std::vector<uint8_t> mBody;
    };

    //! \brief Appends an unsigned big-endian integer of the given byte count.
    inline void appendUnsigned(std::vector<uint8_t>& out, uint64_t value, std::size_t bytes)
    {
        for(std::size_t i = bytes; i > 0; --i)
            out.push_back(static_cast<uint8_t>((value >> (8 * (i - 1))) & 0xFF));
    }

    //! \brief Appends a string as 32 bit byte count and UTF-8 bytes.
    inline void appendString(std::vector<uint8_t>& out, const std::string& text)
    {
        appendUnsigned(out, static_cast<uint64_t>(text.size()), 4);
        out.insert(out.end(), text.begin(), text.end());
    }

    //! \brief Reads body fields in order and remembers whether any read ran past the end.
    class BodyReader
    {
    public:
        //! \brief Reads from the given body, which must outlive the reader.
        explicit BodyReader(const std::vector<uint8_t>& body):
            mBody(body),
            mPosition(0),
            mFailed(false)
        {}

        //! \brief Reads an unsigned big-endian integer of the given byte count; 0 and failed if too short.
        uint64_t readUnsigned(std::size_t bytes)
        {
            if(mFailed || (mBody.size() - mPosition < bytes))
            {
                mFailed = true;
                return 0;
            }
            uint64_t value = 0;
            for(std::size_t i = 0; i < bytes; ++i)
                value = (value << 8) | mBody[mPosition + i];
            mPosition += bytes;
            return value;
        }

        //! \brief Reads a string; empty and failed if the body is too short.
        std::string readString()
        {
            uint64_t size = readUnsigned(4);
            if(mFailed || (mBody.size() - mPosition < size))
            {
                mFailed = true;
                return std::string();
            }
            std::string text(mBody.begin() + static_cast<std::ptrdiff_t>(mPosition),
                mBody.begin() + static_cast<std::ptrdiff_t>(mPosition + size));
            mPosition += static_cast<std::size_t>(size);
            return text;
        }

        //! \brief Copies all bytes not read yet.
        std::vector<uint8_t> readRest()
        {
            std::vector<uint8_t> rest(mBody.begin() + static_cast<std::ptrdiff_t>(mPosition), mBody.end());
            mPosition = mBody.size();
            return rest;
        }

        //! \brief True if every read so far succeeded and the whole body was read.
        bool isComplete() const
        { return !mFailed && (mPosition == mBody.size()); }

    private:
        const std::vector<uint8_t>& mBody;
        std::size_t mPosition;
        bool mFailed;
    };

    //! \brief Appends one frame with header and body to out; false (out unchanged) if the body is too large.
    inline bool encodeFrame(MessageType type, const std::vector<uint8_t>& body, std::vector<uint8_t>& out)
    {
        if(body.size() > MAX_BODY_SIZE)
            return false;
        appendUnsigned(out, static_cast<uint64_t>(body.size()), 4);
        out.push_back(PROTOCOL_VERSION);
        out.push_back(static_cast<uint8_t>(type));
        appendUnsigned(out, 0, 2);
        out.insert(out.end(), body.begin(), body.end());
        return true;
    }

    //! \brief Body of the frames that carry only one 64 bit id (lobbyJoin, lobbyCreated, peerConnected, ...).
    inline std::vector<uint8_t> encodeId(uint64_t id)
    {
        std::vector<uint8_t> body;
        appendUnsigned(body, id, 8);
        return body;
    }

    //! \brief Reads a body made of exactly one 64 bit id.
    inline bool decodeId(const std::vector<uint8_t>& body, uint64_t& id)
    {
        BodyReader reader(body);
        id = reader.readUnsigned(8);
        return reader.isComplete();
    }

    //! \brief Body of lobbyCreate.
    inline std::vector<uint8_t> encodeLobbyCreate(LobbyVisibility visibility, uint16_t maxMembers)
    {
        std::vector<uint8_t> body;
        appendUnsigned(body, static_cast<uint64_t>(visibility), 1);
        appendUnsigned(body, maxMembers, 2);
        return body;
    }

    //! \brief Reads the body of lobbyCreate.
    inline bool decodeLobbyCreate(const std::vector<uint8_t>& body, LobbyVisibility& visibility, uint16_t& maxMembers)
    {
        BodyReader reader(body);
        uint64_t visibilityValue = reader.readUnsigned(1);
        maxMembers = static_cast<uint16_t>(reader.readUnsigned(2));
        if(!reader.isComplete() || (visibilityValue > static_cast<uint64_t>(LobbyVisibility::publicLobby)))
            return false;
        visibility = static_cast<LobbyVisibility>(visibilityValue);
        return true;
    }

    //! \brief Body of lobbyJoined.
    inline std::vector<uint8_t> encodeLobbyJoined(uint64_t lobbyId, uint64_t hostUserId)
    {
        std::vector<uint8_t> body;
        appendUnsigned(body, lobbyId, 8);
        appendUnsigned(body, hostUserId, 8);
        return body;
    }

    //! \brief Reads the body of lobbyJoined.
    inline bool decodeLobbyJoined(const std::vector<uint8_t>& body, uint64_t& lobbyId, uint64_t& hostUserId)
    {
        BodyReader reader(body);
        lobbyId = reader.readUnsigned(8);
        hostUserId = reader.readUnsigned(8);
        return reader.isComplete();
    }

    //! \brief Body of lobbyFailed.
    inline std::vector<uint8_t> encodeLobbyFailed(MessageType request, const std::string& reason)
    {
        std::vector<uint8_t> body;
        appendUnsigned(body, static_cast<uint64_t>(request), 1);
        appendString(body, reason);
        return body;
    }

    //! \brief Reads the body of lobbyFailed.
    inline bool decodeLobbyFailed(const std::vector<uint8_t>& body, MessageType& request, std::string& reason)
    {
        BodyReader reader(body);
        request = static_cast<MessageType>(reader.readUnsigned(1));
        reason = reader.readString();
        return reader.isComplete();
    }

    //! \brief Body of error.
    inline std::vector<uint8_t> encodeText(const std::string& text)
    {
        std::vector<uint8_t> body;
        appendString(body, text);
        return body;
    }

    //! \brief Reads the body of error.
    inline bool decodeText(const std::vector<uint8_t>& body, std::string& text)
    {
        BodyReader reader(body);
        text = reader.readString();
        return reader.isComplete();
    }

    //! \brief Body of peerData: the peer id followed by the message bytes.
    inline std::vector<uint8_t> encodePeerData(uint64_t peerId, const void* data, std::size_t size)
    {
        std::vector<uint8_t> body;
        body.reserve(8 + size);
        appendUnsigned(body, peerId, 8);
        const uint8_t* bytes = static_cast<const uint8_t*>(data);
        if(size > 0)
            body.insert(body.end(), bytes, bytes + size);
        return body;
    }

    //! \brief Reads the body of peerData; the payload may be empty.
    inline bool decodePeerData(const std::vector<uint8_t>& body, uint64_t& peerId, std::vector<uint8_t>& payload)
    {
        if(body.size() < 8)
            return false;
        BodyReader reader(body);
        peerId = reader.readUnsigned(8);
        payload = reader.readRest();
        return true;
    }

    //! \brief Result of FrameDecoder::next().
    enum class DecodeResult
    {
        //! A frame was taken from the buffer.
        frame,
        //! The buffer holds no complete frame yet.
        needMoreData,
        //! The stream is broken; the decoder stays in this state.
        error
    };

    //! \brief Splits the byte stream read from the pipe into frames, whatever the chunk sizes of the reads.
    class FrameDecoder
    {
    public:
        //! \brief Creates an empty decoder.
        FrameDecoder():
            mFailed(false)
        {}

        //! \brief Adds bytes read from the pipe.
        void feed(const uint8_t* data, std::size_t size)
        {
            if(size > 0)
                mBuffer.insert(mBuffer.end(), data, data + size);
        }

        //! \brief Takes the next complete frame out of the buffer, if there is one.
        DecodeResult next(Frame& frame)
        {
            if(mFailed)
                return DecodeResult::error;
            if(mBuffer.size() < HEADER_SIZE)
                return DecodeResult::needMoreData;

            uint32_t bodySize = (static_cast<uint32_t>(mBuffer[0]) << 24) | (static_cast<uint32_t>(mBuffer[1]) << 16)
                | (static_cast<uint32_t>(mBuffer[2]) << 8) | static_cast<uint32_t>(mBuffer[3]);
            if((bodySize > MAX_BODY_SIZE) || (mBuffer[4] != PROTOCOL_VERSION) || (mBuffer[6] != 0) || (mBuffer[7] != 0))
            {
                mFailed = true;
                return DecodeResult::error;
            }
            if(mBuffer.size() - HEADER_SIZE < bodySize)
                return DecodeResult::needMoreData;

            frame.mType = static_cast<MessageType>(mBuffer[5]);
            std::vector<uint8_t>::iterator bodyBegin = mBuffer.begin() + static_cast<std::ptrdiff_t>(HEADER_SIZE);
            std::vector<uint8_t>::iterator bodyEnd = bodyBegin + static_cast<std::ptrdiff_t>(bodySize);
            frame.mBody.assign(bodyBegin, bodyEnd);
            mBuffer.erase(mBuffer.begin(), bodyEnd);
            return DecodeResult::frame;
        }

        //! \brief Number of bytes received but not yet returned as a frame.
        std::size_t getBufferedSize() const
        { return mBuffer.size(); }

    private:
        std::vector<uint8_t> mBuffer;
        bool mFailed;
    };
}

#endif // HELPERPIPEPROTOCOL_H
