#!/usr/bin/env python3
"""Non-compiling check of the guards the multiplayer server applies to client messages.

The C++ sources are checked for the statements that implement the guards: the central command check before the
switch of ODServer::processClientNotifications, the console command rule, the host check and the id checks of the
seat configuration, the bounds of notifyTileRevealed, the nickname and chat limits, the turn barrier without
playerless sockets, the editor checks of the draggable tile container, the range checks of the enum reads (network
and game enums), the packet reads that stop a command when they fail, and the bounds of counts, names, lists and
rectangles sent by clients, the startGameRefused answer (reasons wrongState, notHost, seatsIncomplete) to a start
the server does not carry out, and the room package list of hello (at most 64 names of at most 64 bytes): a client
that lacks a room package of the server is refused with clientRejected and the missing names. The fixed values (20
letters, 512 bytes, the command groups, the last enum values, the 3 refusal reasons 0 to 2, the 7 asserted setNick
reads, the count and name limits) were counted once for this branch.
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

# ------------------------------------------------------------------------------------------------ refused start
REFUSAL = read("source/network/StartGameRefusal.h")
SERVER_NOTIFICATION_H = read("source/network/ServerNotification.h")
reason_body = re.search(r"enum class Reason : int32_t\s*\{(.*?)\};", REFUSAL, re.S).group(1)
reasons = re.findall(r"^\s*(\w+) = (\d+),?\s*$", reason_body, re.M)
check(reasons == [("seatsIncomplete", "0"), ("notHost", "1"), ("wrongState", "2")], "refusal reasons " + repr(reasons))
check("LAST_REASON = Reason::wrongState;" in REFUSAL, "LAST_REASON is the last refusal reason")
notification_body = re.search(r"enum class ServerNotificationType\s*\{(.*?)\};", SERVER_NOTIFICATION_H, re.S).group(1)
notification_names = [re.sub(r"//.*", "", line).strip().rstrip(",") for line in notification_body.split("\n")]
notification_names = [name for name in notification_names if name]
check(notification_names[-2:] == ["setHandCooldown", "startGameRefused"],
      "startGameRefused is appended last: " + repr(notification_names[-2:]))
check('WIRE_SCHEMA_SUFFIX = " / wire-6";' in PACKET_H, "the wire suffix is wire-6 since the room package lists")
check("void sendStartGameRefused(ODSocketClient* clientSocket, StartGameRefusal::Reason reason);" in SERVER_H,
      "the refusal sender is declared")
refusal_sender = block(SERVER, "void ODServer::sendStartGameRefused", "void ODServer::printConsoleMsg")
check("packetSend << ServerNotificationType::startGameRefused << static_cast<int32_t>(reason);" in refusal_sender
      and "clientSocket->send(packetSend);" in refusal_sender, "the refusal goes to the socket that asked")
refused = [set_case.index(text) for text in [
    "sendStartGameRefused(clientSocket, StartGameRefusal::Reason::wrongState);",
    "if(!isSeatConfigurationSender(clientSocket))",
    "sendStartGameRefused(clientSocket, StartGameRefusal::Reason::notHost);",
    "sendStartGameRefused(clientSocket, StartGameRefusal::Reason::seatsIncomplete);",
    "mServerState = ServerState::StateGame;"] if text in set_case]
check(len(refused) == 5 and refused == sorted(refused),
      "seatConfigurationSet answers wrong state, not the host and incomplete seats before it starts the game")
check(set_case.count("sendStartGameRefused(") == 3 and set_case.count("break;") >= 3,
      "every refusal of seatConfigurationSet is answered once")

# ------------------------------------------------------------------------------------------------ room packages
PACKAGE_CHECK = read("source/network/ContentPackageCheck.h")
check("MAX_PACKAGES = 64;" in PACKAGE_CHECK and "MAX_NAME_BYTES = 64;" in PACKAGE_CHECK,
      "the room package lists hold at most 64 names of at most 64 bytes")
reader = block(PACKAGE_CHECK, "bool readList(", "template<typename Packet>")
check("!isCountAllowed(count)" in reader and "!isNameAllowed(name)" in reader, "readList bounds the count and names")
hello = case(SERVER, "hello")
order = [hello.index(text) if text in hello else -1 for text in [
    "NetworkProtocol::WIRE_SCHEMA_SUFFIX",
    "if(!ContentPackageCheck::readList(packetReceived, clientPackages))",
    "ContentPackageCheck::findMissing(serverPackages,",
    "packetRefused << ServerNotificationType::clientRejected;",
    "ContentPackageCheck::writeList(packetRefused, missingPackages);",
    "clientSocket->send(packetRefused);",
    "packet << ServerNotificationType::loadLevel;",
    "ContentPackageCheck::writeList(packet, serverPackages);"]]
check(-1 not in order and order == sorted(order),
      "hello checks the version, then the room packages, refuses a client that lacks one and sends the server's")
check("RoomPackages::getAvailablePackageNames()" in hello, "the server compares with its found room packages")
check(set_case.count("ContentPackageCheck::writeList(packetSend, std::vector<std::string>());") == 1,
      "clientRejected of the seat configuration names no missing package")

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

# ------------------------------------------------------------------------------------------------ every packet read
# The only asserted reads left are the 7 optional one-byte capability reads of setNick, which cannot fail once
# endOfPacket said that a byte is left
asserted = re.findall(r"OD_ASSERT_TRUE\(packetReceived >> (\w+)\);", process)
check(asserted == ["liveNickname", "creatureMood", "creatureActivity", "creaturePanel", "creatureProgress",
                   "cosmeticEvents", "dungeonbookRoster"], "asserted packet reads left " + repr(asserted))
check(all(name in case(SERVER, "setNick") for name in asserted), "the asserted reads left are those of setNick")

# ------------------------------------------------------------------------------------------------ game enum reads
check("static ODPacket& readEnum(ODPacket& packet, TEnum& value, TEnum last)" in PACKET_H
      and "packet.markInvalid();" in PACKET_H, "ODPacket::readEnum marks out-of-range values as a failed read")
ENUM_READERS = [
    ("source/entities/GameEntityType.cpp", "GameEntityType& type", "readEnum<int32_t>(is, type, GameEntityType::poolAttendantEntity)"),
    ("source/entities/Tile.cpp", "TileType& type", "readEnum<uint32_t>(is, type, TileType::countTileType)"),
    ("source/rooms/RoomType.cpp", "RoomType& rt", "readEnum<uint32_t>(is, rt, RoomType::nbRooms)"),
    ("source/spells/SpellType.cpp", "SpellType& tt", "readEnum<uint32_t>(is, tt, SpellType::nbSpells)"),
    ("source/traps/TrapType.cpp", "TrapType& tt", "readEnum<uint32_t>(is, tt, TrapType::nbTraps)"),
    ("source/game/SkillType.cpp", "SkillType& type", "readEnum<int32_t>(is, type, SkillType::countSkill)"),
    ("source/entities/NodeType.cpp", "NodeType& rt", "readEnum<uint32_t>(is, rt, NodeType::MTILES_NODE)"),
]
for path, parameter, call in ENUM_READERS:
    text = read(path)
    reader = block(text, "ODPacket& operator>>(ODPacket& is, " + parameter + ")", "}")
    check("ODPacket::" + call in reader, path + " reads with " + call)
# The last values named above are the last of their enums
entity_body = re.search(r"enum class GameEntityType\s*\{(.*?)\};", read("source/entities/GameEntityType.h"), re.S).group(1)
entity_names = [re.sub(r"//.*", "", line).strip().rstrip(",") for line in entity_body.split("\n")]
entity_names = [name for name in entity_names if name]
check(entity_names[-1] == "poolAttendantEntity", "last GameEntityType is " + entity_names[-1])
node_body = re.search(r"enum class NodeType\s*\{(.*?)\};", read("source/entities/NodeType.h"), re.S).group(1)
check([n.strip() for n in node_body.split(",") if n.strip()][-1] == "MTILES_NODE", "last NodeType is MTILES_NODE")

# ------------------------------------------------------------------------------------------------ counts, names, lists
LIMITS = {"MAX_REGION_NAME_BYTES": "64", "MAX_REGIONS": "256", "MAX_INFO_SUBSCRIPTIONS": "64",
          "MAX_PORTAL_TARGET_TEAMS": "64", "MAX_PORTAL_WAVES": "1024", "MAX_PORTAL_WAVE_CREATURES": "256",
          "MAX_NAME_BYTES": "256"}
for name, value in LIMITS.items():
    check(re.search(r"\b" + name + r" = " + value + r";", GUARDS) is not None, name + " is " + value)
PORTAL = read("source/rooms/RoomPortalWave.cpp")
portal_reader = block(PORTAL, "ODPacket& operator>>(ODPacket& is, RoomPortalWaveConfig& config)", "\n}\n")
for limit in ["MAX_PORTAL_TARGET_TEAMS", "MAX_PORTAL_WAVES", "MAX_PORTAL_WAVE_CREATURES"]:
    check("ServerGuards::isCountAllowed(" in portal_reader and "ServerGuards::" + limit in portal_reader,
          "the wave portal reader bounds " + limit)
check("RoomPortalWaveStrategy::fixedTeamIds" in portal_reader, "the wave portal strategy is range-checked")
region = case(SERVER, "editorRegionEdit")
check("ServerGuards::isRegionNameAllowed(regionName)" in region and "ServerGuards::MAX_REGIONS" in region
      and region.count("ServerGuards::isTileOnMap(") == 2, "editor regions are bounded")
creature_infos = case(SERVER, "askCreatureInfos")
check("ServerGuards::isNameAllowed(name)" in creature_infos
      and "ServerGuards::MAX_INFO_SUBSCRIPTIONS" in creature_infos, "creature info subscriptions are bounded")
tile_infos = case(SERVER, "askTileInfos")
check("ServerGuards::isTileOnMap(xx, yy" in tile_infos and "ServerGuards::MAX_INFO_SUBSCRIPTIONS" in tile_infos,
      "tile info subscriptions are bounded")
for name in ["askMarkTiles", "editorAskChangeTiles"]:
    handler = case(SERVER, name)
    check("ServerGuards::clipRectangleToMap(x1, y1, x2, y2" in handler
          and handler.index("clipRectangleToMap") < handler.index("rectangularRegion"),
          name + " walks only the part of the rectangle on the map")
for name in ["editorAskChangeTile", "editorAskChangeTiles"]:
    # the type, fullness and seat rules of both cases live in isEditorTileChangeValid (check_editor_save.py D7)
    check("isEditorTileChangeValid(gameMap, tileType, tileFullness, seatId)" in case(SERVER, name)
          and "TileType::countTileType" in SERVER[SERVER.index("bool isEditorTileChangeValid("):SERVER.index("bool ODServer::processClientNotifications(")],
          name + " ignores the TileType count value")

# ------------------------------------------------------------------------------------------------ Boost test
check(re.search(r"add_boost_test\(00-ServerGuards\s+SOURCES\s+test_ServerGuards\.cpp\s+\$\{SRC\}/network/ServerGuards\.h"
                r"\s+\$\{SRC\}/network/ODPacket\.cpp", TESTS_CMAKE) is not None, "the Boost test 00-ServerGuards is built")
test_cases = re.findall(r"BOOST_AUTO_TEST_CASE\((\w+)\)", BOOST_TEST)
check(test_cases == ["test_commandRequirement", "test_isCommandAllowed", "test_enumValues", "test_tileAndSeatBounds",
                     "test_consoleCommand", "test_seatConfigurationIds", "test_textLimits", "test_markInvalid",
                     "test_readEnum", "test_clientLimits", "test_clipRectangleToMap", "test_startGameRefusal"],
      "Boost test cases " + repr(test_cases))

print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % (time.perf_counter() - START))
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("mp server hardening ok")
