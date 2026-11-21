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

// The checks the server applies to client messages (ServerGuards.h) and the failure state of ODPacket::markInvalid.
#define BOOST_TEST_MODULE ServerGuards
#include "BoostTestTargetConfig.h"

#include "network/ODPacket.h"
#include "network/ServerGuards.h"

#include <cstdint>
#include <string>
#include <vector>

namespace
{
//! A first human player id for the tests (the server passes Seat::PLAYER_ID_HUMAN_MIN)
const int32_t HUMAN_MIN = 5;
}

//! Checks which commands are handshake, lobby (player needed) and game (seat needed) commands.
BOOST_AUTO_TEST_CASE(test_commandRequirement)
{
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::hello) == ServerGuards::CommandRequirement::handshake);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::levelOK) == ServerGuards::CommandRequirement::handshake);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::setNick) == ServerGuards::CommandRequirement::handshake);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::readyForSeatConfiguration) == ServerGuards::CommandRequirement::player);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::seatConfigurationSet) == ServerGuards::CommandRequirement::player);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::seatConfigurationRefresh) == ServerGuards::CommandRequirement::player);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::chat) == ServerGuards::CommandRequirement::player);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::askExecuteConsoleCommand) == ServerGuards::CommandRequirement::seat);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::notifyTileRevealed) == ServerGuards::CommandRequirement::seat);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::askSetPlayerSettings) == ServerGuards::CommandRequirement::seat);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::ackNewTurn) == ServerGuards::CommandRequirement::seat);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::editorAskChangeTile) == ServerGuards::CommandRequirement::seat);
    BOOST_CHECK(ServerGuards::commandRequirement(ClientNotificationType::askOpenRaidGate) == ServerGuards::CommandRequirement::seat);
}

//! Checks that only ready sockets with a player (and a seat for game commands) pass, and handshake commands always.
BOOST_AUTO_TEST_CASE(test_isCommandAllowed)
{
    const ServerGuards::CommandRequirement handshake = ServerGuards::CommandRequirement::handshake;
    const ServerGuards::CommandRequirement player = ServerGuards::CommandRequirement::player;
    const ServerGuards::CommandRequirement seat = ServerGuards::CommandRequirement::seat;

    BOOST_CHECK(ServerGuards::isCommandAllowed(handshake, "connected", false, false));
    BOOST_CHECK(ServerGuards::isCommandAllowed(handshake, "nick", false, false));

    BOOST_CHECK(!ServerGuards::isCommandAllowed(player, "connected", false, false));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(player, "loadLevel", false, false));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(player, "nick", false, false));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(player, "ready", false, false));
    BOOST_CHECK(ServerGuards::isCommandAllowed(player, "ready", true, false));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(player, "rejected", true, false));

    BOOST_CHECK(!ServerGuards::isCommandAllowed(seat, "ready", true, false));
    BOOST_CHECK(ServerGuards::isCommandAllowed(seat, "ready", true, true));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(seat, "rejected", false, false));
    BOOST_CHECK(!ServerGuards::isCommandAllowed(seat, "nick", true, true));
}

//! Checks the range of the enum values read from packets.
BOOST_AUTO_TEST_CASE(test_enumValues)
{
    BOOST_CHECK(ServerGuards::isClientNotificationTypeValue(0));
    BOOST_CHECK(ServerGuards::isClientNotificationTypeValue(static_cast<int32_t>(ClientNotificationType::askOpenRaidGate)));
    BOOST_CHECK(!ServerGuards::isClientNotificationTypeValue(static_cast<int32_t>(ClientNotificationType::askOpenRaidGate) + 1));
    BOOST_CHECK(!ServerGuards::isClientNotificationTypeValue(-1));

    BOOST_CHECK(ServerGuards::isServerModeValue(static_cast<int32_t>(ServerMode::ModeNone)));
    BOOST_CHECK(ServerGuards::isServerModeValue(static_cast<int32_t>(ServerMode::ModeEditor)));
    BOOST_CHECK(!ServerGuards::isServerModeValue(static_cast<int32_t>(ServerMode::ModeEditor) + 1));
    BOOST_CHECK(!ServerGuards::isServerModeValue(-1));
}

//! Checks the bounds of a revealed tile and of the seat index of the ever-visited flags.
BOOST_AUTO_TEST_CASE(test_tileAndSeatBounds)
{
    BOOST_CHECK(ServerGuards::isTileOnMap(0, 0, 10, 20));
    BOOST_CHECK(ServerGuards::isTileOnMap(9, 19, 10, 20));
    BOOST_CHECK(!ServerGuards::isTileOnMap(10, 0, 10, 20));
    BOOST_CHECK(!ServerGuards::isTileOnMap(0, 20, 10, 20));
    BOOST_CHECK(!ServerGuards::isTileOnMap(-1, 0, 10, 20));
    BOOST_CHECK(!ServerGuards::isTileOnMap(0, -1, 10, 20));

    BOOST_CHECK(ServerGuards::isSeatIndexValid(0, 3));
    BOOST_CHECK(ServerGuards::isSeatIndexValid(2, 3));
    BOOST_CHECK(!ServerGuards::isSeatIndexValid(3, 3));
    BOOST_CHECK(!ServerGuards::isSeatIndexValid(-1, 3));
}

//! Checks that console commands in multiplayer need the host with a client in the server process.
BOOST_AUTO_TEST_CASE(test_consoleCommand)
{
    BOOST_CHECK(ServerGuards::isConsoleCommandAllowed(false, false, false));
    BOOST_CHECK(ServerGuards::isConsoleCommandAllowed(false, true, true));
    BOOST_CHECK(ServerGuards::isConsoleCommandAllowed(true, true, true));
    BOOST_CHECK(!ServerGuards::isConsoleCommandAllowed(true, false, true));
    BOOST_CHECK(!ServerGuards::isConsoleCommandAllowed(true, true, false));
    BOOST_CHECK(!ServerGuards::isConsoleCommandAllowed(true, false, false));
}

//! Checks the player and team ids a seat configuration may set.
BOOST_AUTO_TEST_CASE(test_seatConfigurationIds)
{
    std::vector<int32_t> humanIds;
    humanIds.push_back(HUMAN_MIN);
    humanIds.push_back(HUMAN_MIN + 2);

    BOOST_CHECK(ServerGuards::isConfigPlayerIdAllowed(-1, HUMAN_MIN, humanIds));
    BOOST_CHECK(ServerGuards::isConfigPlayerIdAllowed(0, HUMAN_MIN, humanIds));
    BOOST_CHECK(ServerGuards::isConfigPlayerIdAllowed(HUMAN_MIN - 1, HUMAN_MIN, humanIds));
    BOOST_CHECK(ServerGuards::isConfigPlayerIdAllowed(HUMAN_MIN, HUMAN_MIN, humanIds));
    BOOST_CHECK(!ServerGuards::isConfigPlayerIdAllowed(HUMAN_MIN + 1, HUMAN_MIN, humanIds));
    BOOST_CHECK(ServerGuards::isConfigPlayerIdAllowed(HUMAN_MIN + 2, HUMAN_MIN, humanIds));
    BOOST_CHECK(!ServerGuards::isConfigPlayerIdAllowed(-2, HUMAN_MIN, humanIds));

    std::vector<int> teams;
    teams.push_back(1);
    teams.push_back(3);
    BOOST_CHECK(ServerGuards::isConfigTeamIdAllowed(-1, teams));
    BOOST_CHECK(ServerGuards::isConfigTeamIdAllowed(1, teams));
    BOOST_CHECK(ServerGuards::isConfigTeamIdAllowed(3, teams));
    BOOST_CHECK(!ServerGuards::isConfigTeamIdAllowed(2, teams));
    BOOST_CHECK(!ServerGuards::isConfigTeamIdAllowed(0, teams));
}

//! Checks that nicknames are cut to 20 letters and chat to 512 bytes without splitting UTF-8 sequences.
BOOST_AUTO_TEST_CASE(test_textLimits)
{
    BOOST_CHECK_EQUAL(ServerGuards::MAX_NICK_LETTERS, 20u);
    BOOST_CHECK_EQUAL(ServerGuards::MAX_CHAT_BYTES, 512u);

    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Letters("Keeper", 20), "Keeper");
    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Letters(std::string(25, 'a'), 20), std::string(20, 'a'));
    // 21 letters of two bytes each (U+00E4) keep 20 letters, 40 bytes
    std::string umlauts;
    for(int i = 0; i < 21; ++i)
        umlauts += "\xC3\xA4";
    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Letters(umlauts, 20).size(), 40u);

    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Bytes("hello", 512), "hello");
    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Bytes(std::string(600, 'x'), 512).size(), 512u);
    // A two-byte letter across the limit is dropped whole
    std::string chat = std::string(511, 'x') + "\xC3\xA4";
    BOOST_CHECK_EQUAL(ServerGuards::truncateUtf8Bytes(chat, 512), std::string(511, 'x'));
}

//! Checks that markInvalid leaves the packet failed even when data was left, like a read past its end.
BOOST_AUTO_TEST_CASE(test_markInvalid)
{
    ODPacket packet;
    packet << static_cast<int32_t>(7) << static_cast<int32_t>(8);
    int32_t value = 0;
    BOOST_REQUIRE(packet >> value);
    BOOST_CHECK_EQUAL(value, 7);
    packet.markInvalid();
    BOOST_CHECK(!packet);
    BOOST_CHECK(!(packet >> value));
}
