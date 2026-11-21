# Network transport

The game protocol (ODPacket messages, see `source/network/ODPacket.h`) is carried by a
transport backend. The server and the client never touch sockets directly; they talk to
the interfaces in `source/network/NetTransport.h`.

## Interfaces

- `NetConnection`: one connection to one peer. `ODSocketClient` owns one. Operations:
  `connect`, `send`, `receive`, `waitForData`, `setBlocking` / `isBlocking`, `disconnect`.
- `NetListener`: the server side. It accepts new peers into a fresh `NetConnection`
  (`accept`), keeps a set of watched connections (`watch` / `unwatch`) and waits until a
  new peer or a message is there (`wait`, `isPendingConnection`, `isReady`).
  `ODSocketServer` owns one; its server thread loop (`doTask`) only uses this interface.
- `NetStatus`: result of every operation. The numbers equal the SFML socket status codes,
  so log lines keep their values.
- `NetTransport::createConnection` / `createListener` build the objects of a backend;
  `NetTransport::getDefaultKind` names the backend in use.

Every backend keeps this contract:

1. One ODPacket sent is one ODPacket received with the same bytes.
2. Messages of one peer arrive complete, in order and without loss.
3. A non blocking `receive` returns `NotReady` when no complete message is there and keeps
   a partly received message for the next call (the frame loop polls this way).
4. The protocol above the transport is the same for every backend. Replay files (`.odr`)
   are written by `ODSocketClient` from the received ODPacket, so they do not depend on the
   backend.

## Backend 1: direct TCP (default)

`source/network/TcpNetTransport.h`. It wraps `sf::TcpSocket`, `sf::TcpListener` and
`sf::SocketSelector` exactly as the code did before the interface existed. On the wire each
message is a 32 bit big-endian length followed by the ODPacket bytes (the `sf::Packet`
format). The host runs the server in the same process and its own client connects to
localhost. Joining by host name or IP address keeps working unchanged.

## Backend 2: platform lobby and relay through a helper process (planned)

Multiplayer through a platform lobby works without an own server: one player hosts, the
platform connects the others to the host. The platform SDK is not linked into the game.
A separate helper program talks to the platform alone, and the game talks to the helper.

```
 game process                                  helper process (separate program, own licence)
 +--------------------------------+            +------------------------------------+
 | ODServer / ODClient            |            |                                    |
 |   ODSocketServer/ODSocketClient|            |  platform SDK: login, lobby,       |
 |     HelperRelayListener /      |  pipes     |  invites, relayed peer sessions    |
 |     HelperRelayConnection  <---+----------->|                                    |
 |       HelperPipe frames        |            |                                    |
 +--------------------------------+            +------------------------------------+
```

- The game starts the helper as a child process and owns its standard input and output
  (or two named pipes). If the helper is missing or exits, the lobby option is disabled
  and direct TCP stays available.
- The pipe protocol is `source/network/HelperPipeProtocol.h`, header only and without
  dependencies, so the helper can be written from that file alone.
- The stub `source/network/HelperRelayTransport.h` shows where the backend plugs in. It is
  compiled only with `OD_NET_HELPER_RELAY`, which no build defines, and the factory falls
  back to TCP with an error log if the kind is requested anyway.

### Pipe framing

Each direction is a sequence of frames:

| offset | size | field    | value                                    |
|--------|------|----------|------------------------------------------|
| 0      | 4    | bodySize | unsigned, big-endian, at most 16 MiB     |
| 4      | 1    | version  | 1                                        |
| 5      | 1    | type     | message type                             |
| 6      | 2    | reserved | 0                                        |
| 8      | n    | body     | `bodySize` bytes                         |

Body fields: unsigned integers big-endian, ids 64 bit, strings as a 32 bit byte count
followed by UTF-8. Frames of an unknown type are ignored; a wrong version, a non zero
reserved field or an oversized body close the pipe.

### Messages

| type | name                | direction     | body                              |
|------|---------------------|---------------|-----------------------------------|
| 1    | hello               | game → helper | empty                             |
| 2    | shutdown            | game → helper | empty                             |
| 10   | lobbyCreate         | game → helper | u8 visibility, u16 maxMembers     |
| 11   | lobbyJoin           | game → helper | u64 lobbyId                       |
| 12   | lobbyLeave          | game → helper | empty                             |
| 13   | lobbyInvite         | game → helper | empty (opens the invite dialog)   |
| 20   | peerClose           | game → helper | u64 peerId                        |
| 64   | ready               | helper → game | u64 localUserId                   |
| 70   | lobbyCreated        | helper → game | u64 lobbyId                       |
| 71   | lobbyJoined         | helper → game | u64 lobbyId, u64 hostUserId       |
| 72   | lobbyInviteAccepted | helper → game | u64 lobbyId                       |
| 73   | lobbyFailed         | helper → game | u8 request type, string reason    |
| 80   | peerConnected       | helper → game | u64 peerId                        |
| 81   | peerDisconnected    | helper → game | u64 peerId                        |
| 90   | error               | helper → game | string text                       |
| 100  | peerData            | both          | u64 peerId, message bytes         |

`peerData` carries exactly one ODPacket: `ODPacket::getRawData()` without the TCP length
prefix; the receiver rebuilds it with `ODPacket::setRawData()`. The helper delivers it
reliably and in order per peer and splits and joins it if the platform limits the message
size.

### Flow

- Host: menu → `lobbyCreate` → `lobbyCreated`; the server listener now accepts
  `peerConnected` peers instead of TCP connections; the host's own client still connects to
  the local server by TCP on localhost.
- Join: invite accepted in the platform overlay → `lobbyInviteAccepted` → `lobbyJoin` →
  `lobbyJoined` → the client connection exchanges `peerData` with `hostUserId`.

### Licence separation

The game is GPLv3+. The platform SDK is not free software and cannot be linked into it.
Therefore:

- No SDK header, library, sample or identifier is stored in this repository or included by
  any game source.
- The helper is a separate executable, built and distributed on its own terms, and talks to
  the game only through the documented pipe protocol.
- The game works without the helper; the TCP backend has no platform dependency.

## Still open for the helper backend

- A platform developer account and an application id; the helper reads the id, the game
  does not need it.
- The helper program itself (its own repository and build) implementing the messages above.
- `HelperRelayProcess` in the game: start the helper, read the pipe without blocking the
  server thread, dispatch frames to listener and connections.
- Choosing the backend per session: `ODSocketServer::createServer` and
  `ODSocketClient::connect` create their listener / connection from a kind passed in by the
  menus instead of `NetTransport::getDefaultKind`.
- Lobby UI in the multiplayer menus: host through the lobby, invite, join from an invite,
  with the direct IP connection kept beside it.
