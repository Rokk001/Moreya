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

#ifndef SERVERGUARDS_H
#define SERVERGUARDS_H

#include "network/ClientNotification.h"
#include "network/ServerMode.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

//! \brief Checks the server applies to what a client sends before a command is handled. The functions only
//! work on plain values so that they can be tested without a running game.
namespace ServerGuards
{
    //! \brief State of a socket that finished the handshake (set by setNick).
    static const std::string STATE_READY = "ready";

    //! \brief Longest nickname in letters (code points), the same limit as the multiplayer menus.
    static const std::size_t MAX_NICK_LETTERS = 20;

    //! \brief Longest chat message in bytes; longer messages are cut.
    static const std::size_t MAX_CHAT_BYTES = 512;

    //! \brief Longest region name of the level script in bytes an editor client may set.
    static const std::size_t MAX_REGION_NAME_BYTES = 64;

    //! \brief Most region markers a level script may hold; an editor client cannot add more.
    static const std::size_t MAX_REGIONS = 256;

    //! \brief Most creatures and most tiles one client may follow in its info windows at the same time.
    static const std::size_t MAX_INFO_SUBSCRIPTIONS = 64;

    //! \brief Most target teams of a wave portal configuration read from a packet.
    static const uint32_t MAX_PORTAL_TARGET_TEAMS = 64;

    //! \brief Most waves of a wave portal configuration read from a packet.
    static const uint32_t MAX_PORTAL_WAVES = 1024;

    //! \brief Most creature entries of one wave of a wave portal configuration read from a packet.
    static const uint32_t MAX_PORTAL_WAVE_CREATURES = 256;

    //! \brief Longest name (creature, entity, creature class, trap order) in bytes the server accepts from a client.
    static const std::size_t MAX_NAME_BYTES = 256;

    //! \brief Returns true if a count read from a packet does not exceed the given maximum.
    inline bool isCountAllowed(uint32_t count, uint32_t maximum)
    {
        return count <= maximum;
    }

    //! \brief Returns true if a region name sent by an editor client may be used: not empty and not too long.
    inline bool isRegionNameAllowed(const std::string& name)
    {
        return !name.empty() && (name.size() <= MAX_REGION_NAME_BYTES);
    }

    //! \brief Returns true if a name sent by a client is not longer than MAX_NAME_BYTES.
    inline bool isNameAllowed(const std::string& name)
    {
        return name.size() <= MAX_NAME_BYTES;
    }

    //! \brief Returns true if one more entry may be added to a list that already holds size entries.
    inline bool canAddEntry(std::size_t size, std::size_t maximum)
    {
        return size < maximum;
    }

    //! \brief Last value of ClientNotificationType. Must be updated when a new message is appended to the enum.
    static const ClientNotificationType LAST_CLIENT_NOTIFICATION_TYPE = ClientNotificationType::askOpenRaidGate;

    //! \brief Last value of ServerMode. Must be updated when a new mode is appended to the enum.
    static const ServerMode LAST_SERVER_MODE = ServerMode::ModeEditor;

    //! \brief What a client command needs from the socket that sent it.
    enum class CommandRequirement
    {
        //! The handshake commands check the socket state themselves.
        handshake,
        //! The socket finished the handshake and has a player (seat configuration and chat).
        player,
        //! The socket finished the handshake and its player has a seat (every command of a running game or editor).
        seat
    };

    //! \brief Returns what the socket must have before the given command is handled.
    inline CommandRequirement commandRequirement(ClientNotificationType type)
    {
        switch(type)
        {
            case ClientNotificationType::hello:
            case ClientNotificationType::levelOK:
            case ClientNotificationType::setNick:
                return CommandRequirement::handshake;
            case ClientNotificationType::readyForSeatConfiguration:
            case ClientNotificationType::seatConfigurationSet:
            case ClientNotificationType::seatConfigurationRefresh:
            case ClientNotificationType::chat:
                return CommandRequirement::player;
            default:
                return CommandRequirement::seat;
        }
    }

    //! \brief Returns true if a socket in the given state, with or without a player and a seat, may send a command
    //! with the given requirement.
    inline bool isCommandAllowed(CommandRequirement requirement, const std::string& state, bool hasPlayer, bool hasSeat)
    {
        if(requirement == CommandRequirement::handshake)
            return true;
        if(state != STATE_READY)
            return false;
        if(!hasPlayer)
            return false;
        if(requirement == CommandRequirement::seat)
            return hasSeat;
        return true;
    }

    //! \brief Returns true if the value read from a packet is a ClientNotificationType.
    inline bool isClientNotificationTypeValue(int32_t value)
    {
        return (value >= 0) && (value <= static_cast<int32_t>(LAST_CLIENT_NOTIFICATION_TYPE));
    }

    //! \brief Returns true if the value read from a packet is a ServerMode.
    inline bool isServerModeValue(int32_t value)
    {
        return (value >= 0) && (value <= static_cast<int32_t>(LAST_SERVER_MODE));
    }

    //! \brief Returns true if the tile x, y lies on a map of the given size.
    inline bool isTileOnMap(int32_t x, int32_t y, int32_t mapSizeX, int32_t mapSizeY)
    {
        return (x >= 0) && (y >= 0) && (x < mapSizeX) && (y < mapSizeY);
    }

    //! \brief Cuts the rectangle between the corners x1, y1 and x2, y2 (any order) to the part on a map of the given
    //! size, so that a rectangle sent by a client never makes the server walk over more than the map. Afterwards
    //! x1 <= x2 and y1 <= y2. Returns false, leaving the corners as they were, if no tile of the rectangle is on
    //! the map.
    inline bool clipRectangleToMap(int32_t& x1, int32_t& y1, int32_t& x2, int32_t& y2, int32_t mapSizeX, int32_t mapSizeY)
    {
        const int32_t minX = (x1 < x2) ? x1 : x2;
        const int32_t maxX = (x1 < x2) ? x2 : x1;
        const int32_t minY = (y1 < y2) ? y1 : y2;
        const int32_t maxY = (y1 < y2) ? y2 : y1;
        if((mapSizeX <= 0) || (mapSizeY <= 0) || (maxX < 0) || (maxY < 0) || (minX >= mapSizeX) || (minY >= mapSizeY))
            return false;
        x1 = (minX < 0) ? 0 : minX;
        y1 = (minY < 0) ? 0 : minY;
        x2 = (maxX >= mapSizeX) ? mapSizeX - 1 : maxX;
        y2 = (maxY >= mapSizeY) ? mapSizeY - 1 : maxY;
        return true;
    }

    //! \brief Returns true if the seat id is an index of a per-seat array with the given number of entries.
    inline bool isSeatIndexValid(int32_t seatId, std::size_t nbEntries)
    {
        return (seatId >= 0) && (static_cast<std::size_t>(seatId) < nbEntries);
    }

    //! \brief Returns true if a console command may be run for the sender. Outside of multiplayer games, every
    //! client is the local player. In a multiplayer game, only the game host may run console commands, and only
    //! when the server runs in the same process as the host client (not on a dedicated server).
    inline bool isConsoleCommandAllowed(bool multiPlayer, bool senderIsConfigPlayer, bool serverHasLocalClient)
    {
        if(!multiPlayer)
            return true;
        return senderIsConfigPlayer && serverHasLocalClient;
    }

    //! \brief Returns true if a seat may be configured with the given player id: -1 (not set), the inactive and AI
    //! ids (below humanMin) or the id of a connected human player.
    inline bool isConfigPlayerIdAllowed(int32_t playerId, int32_t humanMin, const std::vector<int32_t>& humanIds)
    {
        if(playerId == -1)
            return true;
        if(playerId < 0)
            return false;
        if(playerId < humanMin)
            return true;
        for(int32_t humanId : humanIds)
        {
            if(humanId == playerId)
                return true;
        }
        return false;
    }

    //! \brief Returns true if a seat may be configured with the given team id: -1 (not set) or one of the teams
    //! the level allows for that seat.
    inline bool isConfigTeamIdAllowed(int32_t teamId, const std::vector<int>& availableTeamIds)
    {
        if(teamId == -1)
            return true;
        for(int availableTeamId : availableTeamIds)
        {
            if(availableTeamId == teamId)
                return true;
        }
        return false;
    }

    //! \brief Returns true if the byte starts a UTF-8 sequence (it is not a continuation byte 10xxxxxx).
    inline bool isUtf8LeadByte(unsigned char byte)
    {
        return (byte & 0xC0) != 0x80;
    }

    //! \brief Returns the text cut after at most maxLetters code points of UTF-8.
    inline std::string truncateUtf8Letters(const std::string& text, std::size_t maxLetters)
    {
        std::size_t letters = 0;
        for(std::size_t index = 0; index < text.size(); ++index)
        {
            if(!isUtf8LeadByte(static_cast<unsigned char>(text[index])))
                continue;
            if(letters == maxLetters)
                return text.substr(0, index);
            ++letters;
        }
        return text;
    }

    //! \brief Returns the text cut to at most maxBytes bytes without splitting a UTF-8 sequence.
    inline std::string truncateUtf8Bytes(const std::string& text, std::size_t maxBytes)
    {
        if(text.size() <= maxBytes)
            return text;
        std::size_t end = maxBytes;
        while((end > 0) && !isUtf8LeadByte(static_cast<unsigned char>(text[end])))
            --end;
        return text.substr(0, end);
    }
}

#endif // SERVERGUARDS_H
