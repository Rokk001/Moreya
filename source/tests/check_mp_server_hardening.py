#!/usr/bin/env python3
"""Non-compiling check of the guards the multiplayer server applies to client messages.

The C++ sources are checked for the statements that implement the guards: the central command check before the
switch of ODServer::processClientNotifications, the console command rule, the host check and the id checks of the
seat configuration, the bounds of notifyTileRevealed, the nickname and chat limits, the turn barrier without
playerless sockets, the editor checks of the draggable tile container and the range checks of the enum reads. The
fixed values (20 letters, 512 bytes, the command groups, the last enum values) were counted once for this branch.
Nothing is compiled and the game is not started; the integration build compiles the code and runs the Boost test
00-ServerGuards, which tests the guard functions themselves.

Usage: python -I source/tests/check_mp_server_hardening.py
Exit 0 and "mp server hardening ok" when every item holds.
"""
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = time.perf_counter()
FAILURES = []


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def check(condition, message):
    """Records a failed item."""
    if not condition:
        FAILURES.append(message)


def block(source, start, end):
    """Returns the text from start up to (not including) end, both searched from start."""
    first = source.index(start)
    return source[first:source.index(end, first + len(start))]


def case(source, name):
    """Returns the text of one case of the client command switch, up to the next case label."""
    start = source.index("case ClientNotificationType::" + name + ":")
    following = re.compile(r"\n\s*case ClientNotificationType::\w+:").search(source, start + 1)
    return source[start:following.start()] if following else source[start:]


GUARDS = read("source/network/ServerGuards.h")
SERVER = read("source/network/ODServer.cpp")
SERVER_H = read("source/network/ODServer.h")
NOTIFICATION = read("source/network/ClientNotification.cpp")
NOTIFICATION_H = read("source/network/ClientNotification.h")
SERVER_MODE = read("source/network/ServerMode.cpp")
SERVER_MODE_H = read("source/network/ServerMode.h")
PACKET_H = read("source/network/ODPacket.h")
PACKET = read("source/network/ODPacket.cpp")
TESTS_CMAKE = read("source/tests/CMakeLists.txt")
BOOST_TEST = read("source/tests/test_ServerGuards.cpp")

# ------------------------------------------------------------------------------------------------ fixed values
check("MAX_NICK_LETTERS = 20;" in GUARDS, "the nickname limit is 20 letters")
check("MAX_CHAT_BYTES = 512;" in GUARDS, "the chat limit is 512 bytes")
check('STATE_READY = "ready";' in GUARDS, "the ready state is the one setNick sets")
check('clientSocket->setState("ready");' in SERVER, "setNick still sets the ready state")

# The last enum values: a value appended to an enum must also move these
enum_body = re.search(r"enum class ClientNotificationType\s*\{(.*?)\};", NOTIFICATION_H, re.S).group(1)
enum_names = [re.sub(r"//.*", "", line).strip().rstrip(",") for line in enum_body.split("\n")]
enum_names = [name for name in enum_names if name]
check(enum_names[-1] == "askOpenRaidGate", "last ClientNotificationType is " + enum_names[-1])
check("LAST_CLIENT_NOTIFICATION_TYPE = ClientNotificationType::askOpenRaidGate;" in GUARDS,
      "LAST_CLIENT_NOTIFICATION_TYPE is the last ClientNotificationType")
mode_body = re.search(r"enum class ServerMode\s*\{(.*?)\};", SERVER_MODE_H, re.S).group(1)
mode_names = [name.strip() for name in mode_body.split(",") if name.strip()]
check(mode_names[-1] == "ModeEditor", "last ServerMode is " + mode_names[-1])
check("LAST_SERVER_MODE = ServerMode::ModeEditor;" in GUARDS, "LAST_SERVER_MODE is the last ServerMode")

# The command groups, counted once: 3 handshake commands, 4 commands that need a player, the rest need a seat
requirement = block(GUARDS, "inline CommandRequirement commandRequirement", "inline bool isCommandAllowed")
handshake = re.findall(r"case ClientNotificationType::(\w+):",
                       block(requirement, "switch(type)", "return CommandRequirement::handshake;"))
check(handshake == ["hello", "levelOK", "setNick"], "handshake commands " + repr(handshake))
player = re.findall(r"case ClientNotificationType::(\w+):",
                    block(requirement, "return CommandRequirement::handshake;", "return CommandRequirement::player;"))
check(player == ["readyForSeatConfiguration", "seatConfigurationSet", "seatConfigurationRefresh", "chat"],
      "commands that need a player " + repr(player))
check("default:\n                return CommandRequirement::seat;" in requirement, "every other command needs a seat")

# ------------------------------------------------------------------------------------------------ enum reads
for label, source, name in [("ClientNotification.cpp", NOTIFICATION, "isClientNotificationTypeValue"),
                            ("ServerMode.cpp", SERVER_MODE, "isServerModeValue")]:
    reader = source[source.index("ODPacket& operator>>"):]
    check("int32_t tmp = 0;" in reader and "if(!(is >> tmp))" in reader, label + ": the raw value read is checked")
    check("ServerGuards::" + name + "(tmp)" in reader and "is.markInvalid();" in reader,
          label + ": a value outside of the enum marks the packet as failed")
check("void markInvalid();" in PACKET_H and "void ODPacket::markInvalid()" in PACKET, "ODPacket::markInvalid exists")

# ------------------------------------------------------------------------------------------------ central guard
process = SERVER[SERVER.index("bool ODServer::processClientNotifications"):]
switch_at = process.index("switch(clientCommand)")
before_switch = process[:switch_at]
check("if(!(packetReceived >> clientCommand))" in before_switch, "an unreadable command is ignored")
check("ServerGuards::isCommandAllowed(ServerGuards::commandRequirement(clientCommand)" in before_switch,
      "the central guard runs before the switch")
check("OD_ASSERT_TRUE(packetReceived >> clientCommand)" not in process, "the command read is no longer an assert")

# ------------------------------------------------------------------------------------------------ turn barrier
turn = block(SERVER, "void ODServer::startNewTurn", "void ODServer::serverThread")
barrier = block(turn, "for (ODSocketClient* client : mSockClients)", "gameMap->setTurnNumber(++turn);")
check("if(!isPlayingClient(client))\n            continue;" in barrier, "playerless sockets do not hold the barrier")
notify = block(turn, "for (ODSocketClient* sock : mSockClients)", "Player* player = sock->getPlayer();")
check("if(!isPlayingClient(sock))\n            continue;" in notify, "playerless sockets get no turn notifications")

# ------------------------------------------------------------------------------------------------ console commands
console = case(SERVER, "askExecuteConsoleCommand")
check("ServerGuards::isConsoleCommandAllowed(multiPlayer, player == mPlayerConfig, serverHasLocalClient)" in console,
      "console commands use the host rule")
check("(mServerMode == ServerMode::ModeGameMultiPlayer)" in console
      and "(ODClient::getSingletonPtr() != nullptr)" in console, "the rule knows the mode and the local client")
check(console.index("isConsoleCommandAllowed") < console.index("handleConsoleCommand"),
      "the rule is checked before the command runs")
check("OD_ASSERT_TRUE" not in console, "failed reads stop the console command")

# ------------------------------------------------------------------------------------------------ seat configuration
check("bool isSeatConfigurationSender(ODSocketClient* clientSocket);" in SERVER_H, "the host check is declared")
sender = block(SERVER, "bool ODServer::isSeatConfigurationSender", "void ODServer::printConsoleMsg")
check("mServerState != ServerState::StateConfiguration" in sender and "player != mPlayerConfig" in sender,
      "the host check needs the configuration state and the configuring player")
refresh = case(SERVER, "seatConfigurationRefresh")
check("if(!isSeatConfigurationSender(clientSocket))" in refresh, "seatConfigurationRefresh checks the host")
check("ServerGuards::isConfigPlayerIdAllowed(playerId, Seat::PLAYER_ID_HUMAN_MIN, humanIds)" in refresh,
      "player ids are checked")
check("ServerGuards::isConfigTeamIdAllowed(teamId, seat->getAvailableTeamIds())" in refresh, "team ids are checked")
check("usedHumanIds" in refresh, "a human player takes only one seat")
check("OD_ASSERT_TRUE" not in refresh, "failed reads stop the seat configuration")
check(refresh.index("if(!packetReceived)") < refresh.index("entry.mSeat->setConfigPlayerId"),
      "nothing is applied before the whole message was read")
set_case = case(SERVER, "seatConfigurationSet")
check("if(!isSeatConfigurationSender(clientSocket))" in set_case, "seatConfigurationSet checks the host")
check("(client->getPlayer() == nullptr) || (client->getPlayer()->getSeat() == nullptr)" in set_case,
      "sockets still in the handshake are rejected without a crash")

# ------------------------------------------------------------------------------------------------ handlers
revealed = case(SERVER, "notifyTileRevealed")
check("ServerGuards::isTileOnMap(xx, yy, gameMap->getMapSizeX(), gameMap->getMapSizeY())" in revealed
      and "ServerGuards::isSeatIndexValid(seatId" in revealed, "notifyTileRevealed checks the bounds")
check(revealed.index("isTileOnMap") < revealed.index("everVisitedFlagPool[xx][yy][seatId] = true"),
      "the bounds are checked before the write")
chat = case(SERVER, "chat")
check("ServerGuards::truncateUtf8Bytes(chatMsg, ServerGuards::MAX_CHAT_BYTES)" in chat, "chat messages are cut")
for name in ["setNick", "changeNick"]:
    check("ServerGuards::truncateUtf8Letters(" in case(SERVER, name) and "ServerGuards::MAX_NICK_LETTERS" in case(SERVER, name),
          name + " cuts the nickname")
for name in ["chat", "changeNick", "askSetPlayerSettings", "notifyTileRevealed", "ackNewTurn", "editorAskChangeTile",
             "editorAskCreateDraggableTileContainer", "editorAskRevealTiles", "editorAskRevealRooms",
             "editorAskRevealTraps"]:
    check("OD_ASSERT_TRUE(packetReceived" not in case(SERVER, name), name + " stops when a read fails")
ready = case(SERVER, "readyForSeatConfiguration")
check("clientsWithPlayer" in ready, "the player list leaves out sockets without a player")

# ------------------------------------------------------------------------------------------------ editor
for name in ["createAllEntities", "editorAskCopyRoom", "editorAskCopyTrap", "editorAskRevealTiles",
             "editorAskRevealRooms", "editorAskRevealTraps"]:
    handler = case(SERVER, name)
    check("if(mDraggableTileContainer == nullptr)" in handler, name + " checks the draggable tile container")
    # The first mention of the container in the handler is the check itself
    check(handler.index("mDraggableTileContainer") == handler.index("if(mDraggableTileContainer == nullptr)") + len("if("),
          name + " checks the container before using it")
check("if(selectedTile == nullptr)" in case(SERVER, "editorAskChangeTile"), "editorAskChangeTile checks the tile")
check("mServerMode != ServerMode::ModeEditor" in case(SERVER, "editorAskDeleteDraggableTileContainer"),
      "editorAskDeleteDraggableTileContainer checks the editor mode")

# ------------------------------------------------------------------------------------------------ Boost test
check(re.search(r"add_boost_test\(00-ServerGuards\s+SOURCES\s+test_ServerGuards\.cpp\s+\$\{SRC\}/network/ServerGuards\.h"
                r"\s+\$\{SRC\}/network/ODPacket\.cpp", TESTS_CMAKE) is not None, "the Boost test 00-ServerGuards is built")
test_cases = re.findall(r"BOOST_AUTO_TEST_CASE\((\w+)\)", BOOST_TEST)
check(test_cases == ["test_commandRequirement", "test_isCommandAllowed", "test_enumValues", "test_tileAndSeatBounds",
                     "test_consoleCommand", "test_seatConfigurationIds", "test_textLimits", "test_markInvalid"],
      "Boost test cases " + repr(test_cases))

print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % (time.perf_counter() - START))
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("mp server hardening ok")
