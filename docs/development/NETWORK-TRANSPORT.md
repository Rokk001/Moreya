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

## Backend 2: platform lobby and relay through a helper process

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

- The game starts the helper as a child process and owns its standard input and output.
  If the helper is missing or exits, the lobby option is disabled and direct TCP stays
  available.
- The pipe protocol is `source/network/HelperPipeProtocol.h`, header only and without
  dependencies, so the helper can be written from that file alone.
- The backend is compiled only with the CMake option `OD_NET_HELPER_RELAY` (default `OFF`,
  so the normal build is unchanged). Without it the factory falls back to TCP with an
  error log if the kind is requested anyway.

### Game side

- `HelperRelayProcess` (`source/network/HelperRelayProcess.h`): one per game. `start`
  launches the helper program (a path, not searched for) with its standard input and output
  connected to the game: two anonymous pipes on Windows (`CreateProcessW`, only these
  handles are inherited, standard error goes to `NUL`), a socket pair with `fork`/`execv`
  elsewhere (a failed `execv` is reported to `start`, writes never raise `SIGPIPE`). It
  sends `hello`; `waitForReady` or the observer reports `ready`. `stop` sends `shutdown`,
  closes the helper input, waits a bounded time for the exit and terminates the helper
  after that.
- A reader thread reads the helper output, splits it with `HelperPipe::FrameDecoder` and
  files each frame into state guarded by one mutex: per peer message queues, the queue of
  peers waiting to be accepted, the lobby state and a queue of lobby events. Neither the
  server thread nor the render loop ever reads the pipe. End of stream or a broken frame
  stream (the helper is terminated then) marks the helper as exited: every relayed peer
  reads as disconnected, lobby requests fail, the exit code is reported.
- Lobby API, no UI yet: `createLobby(visibility, maxMembers)`, `joinLobby(lobbyId)`,
  `leaveLobby()`, `inviteToLobby()`. Answers go to a `HelperLobbyObserver`
  (`onHelperReady`, `onLobbyCreated`, `onLobbyJoined`, `onLobbyInviteAccepted`,
  `onLobbyFailed`, `onHelperError`, `onHelperExited`), called by `dispatchLobbyEvents()`
  on the thread that calls it. The game calls it once per rendered frame.
- `HelperRelayConnection`: `connect("lobby:<id>", ...)` joins that lobby (it waits for
  `lobbyJoined` within the timeout, `Error` on `lobbyFailed`) and then talks to the host
  peer; any other host is connected by TCP. `send` puts `ODPacket::getRawData()` into a
  `peerData` frame, `receive` rebuilds the packet with `ODPacket::setRawData()`.
- `HelperRelayListener`: listens on the TCP port like the TCP backend, so the host's own
  client keeps connecting by TCP on localhost (and direct joins by address keep working).
  Peers announced by `peerConnected` after `createLobby` are accepted into
  `HelperRelayConnection`s. `wait` waits on the socket selector; the reader thread wakes it
  by writing one byte to a socket pair on the loopback interface, so relayed messages do
  not wait for the timeout. `close` leaves a lobby the game hosts.
- Status values as the TCP backend reports them: `Done`; `NotReady` for a non blocking
  `receive` without a message; `Disconnected` after `peerDisconnected`, `peerClose` or the
  helper exit, once the queued messages are read; `Error` for a failed connect.
- With the option built, `--net-helper <path>` starts the helper when the game starts.
  While it is set up, `NetTransport::getDefaultKind` returns `helperRelay`; this backend
  also carries every TCP connection, so local games and direct joins are unchanged.

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
  `peerConnected` peers in addition to TCP connections; the host's own client still connects to
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

### Tests without the platform

`source/tests/mocks/FakeNetHelper.cpp` is a test-only helper program: it answers the pipe
messages with fixed values (ready, lobby created with one joining peer, lobby joined, invite
accepted, failures, an echo of `peerData`, an exit on request). `source/tests/test_HelperRelay.cpp`
(`00-HelperRelay`, which builds the fake helper as `odp-fake-net-helper`) runs the handshake,
the lobby requests, the host listener with its own TCP client and a relayed peer, the client
connection and the detection of a helper exit against it. Every wait is bounded and returns as
soon as the awaited frame is there. `source/tests/check_helper_relay.py` compiles and runs the
same test without Boost.Test.

## Still open for the helper backend

- A platform developer account and an application id; the helper reads the id, the game
  does not need it.
- The helper program itself (its own repository and build) implementing the messages above.
- Lobby UI in the multiplayer menus: host through the lobby, invite, join from an invite,
  with the direct IP connection kept beside it. The UI implements `HelperLobbyObserver`,
  chooses the lobby visibility and size for `createLobby` and connects the client to
  `HelperRelayConnection::formatLobbyAddress(lobbyId)` after an accepted invite.
- Packaging: where the helper program lies next to the game and how the launcher passes
  `--net-helper`.
- The POSIX process code (socket pair, `fork`/`execv`) is not run by any test yet; the
  tests run on Windows.
