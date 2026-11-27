#!/usr/bin/env python3
"""Non-compiling check that the Moreya gate of every raid level stands built into the outer wall of the map.

Owner's decision of 2026-11-23: the gate the raiders come through stands at the edge of the dungeon, always built into
a wall, with nothing on its back side, and the keeper's creatures cannot claim the tiles around it. For every level
with a [Raid] section that ships in this repository the check holds, with values fixed here:

- the Gate line has the fixed tile and rotation, and the rotation turns the front of the gate (rotation 0: front
  towards -Y, RaidManager.h; the model node is rolled counter-clockwise about +Z) towards the fixed open side;
- the gate room is the hero portal room of the raid seat with exactly the gate tile and its two neighbours along the
  wall, all of them dug floor;
- every tile behind the gate row, five tiles wide, up to the map border is indestructible rock (so nothing stands or
  can be dug out behind the gate), and the two tiles beside the gate room are rock as well;
- the three tiles in front of the gate room are dug floor (the only opening); the two front corners are rock or
  floor, never an earth wall that could be dug or claimed;
- walking over floor, room and bridge tiles, the raid reaches the fixed route tile of the level from the gate (the
  keeper's dungeon heart, or on Brackenford, whose heart lies behind earth the keeper digs, the old gate tile where the
  former route began);
- the game code keeps rock walls undiggable and unclaimable and the hero portal room unclaimable;
- the passage behind the bars (material MoreyaGateDepth) is textured stone with a faint green glow, not flat black.

Nothing is derived from the files under test; the game is not started and nothing is compiled.
The wing levels, the gate material and its texture live in content packages (found through scripts/content_packages.py
and scripts/campaign_packages.py); without the content the check names them as not checked and checks the public test
level and the code.

Usage: python -I source/tests/check_moreya_gate_wall.py
Exit 0 and "moreya gate wall ok" when every item holds.
"""
import os
import re
import sys
import time
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

START = time.perf_counter()
FAILURES = []
WITH_CONTENT = content_packages.has_content(ROOT)
# Files that need the content and are not checked because it is not present
NOT_CHECKED = []

# Level file, gate tile, rotation in degrees, open side of the gate (front direction) and the route tile the raid
# must reach from the gate, fixed on fix/ingame-ui-findings for the owner's decision of 2026-11-23.
LEVELS = (
    ("levels/campaign/wing1/Brackenford.level", (53, 8), 270, (-1, 0), (38, 12)),
    ("levels/campaign/wing1/Coldwell.level", (52, 27), 270, (-1, 0), (10, 9)),
    ("levels/campaign/wing1/Ravensledge.level", (2, 33), 90, (1, 0), (48, 56)),
    ("levels/skirmish/TestRaid.level", (33, 38), 0, (0, -1), (7, 7)),
)

# Front of the gate model for each rotation: 0 faces -Y, the node is rolled counter-clockwise about +Z.
FRONT_OF_ROTATION = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}

DIRT, ROCK, WATER, LAVA = 1, 3, 4, 5
PORTAL_WAVE_ROOM = 10
DUNGEON_TEMPLE_ROOM = 1
GATE_ROOM_TILES = 3


def check(condition, message):
    """Records the message as a failure when the condition does not hold."""
    if not condition:
        FAILURES.append(message)


def read(relative):
    """Returns the text of a file of the repository with Unix line ends."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n")


def data_file(relative):
    """Returns the game data file (a level of the public tree or of its wing or content package, else any other data
    file of the public tree or of a content package); None when the content is not present (with the content present
    the path below the repository, so that a missing file still fails)."""
    if relative.endswith(".level"):
        found = campaign_packages.level_file(ROOT, relative)
    else:
        found = content_packages.data_file(ROOT, relative)
    if found is None and WITH_CONTENT:
        return os.path.join(ROOT, relative)
    if found is None:
        NOT_CHECKED.append(relative)
        return None
    return str(found)


def read_data(relative):
    """Returns the text of a game data file with Unix line ends, or None when the content is not present."""
    path = data_file(relative)
    if path is None:
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n")


def function(source, signature):
    """Returns the body of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise AssertionError("no end of " + signature)


def load_level(text):
    """Returns the map size, the listed tiles {(x, y): (type, fullness)}, the rooms and the [Raid] Gate and Seats."""
    body = text[text.index("[Tiles]"):text.index("[/Tiles]")].split("\n")
    sizes = [int(line.split("#")[0]) for line in body if line.split("#")[0].strip().isdigit()]
    tiles = {}
    for line in body:
        fields = line.split("#")[0].split()
        if len(fields) >= 4 and fields[0].isdigit() and fields[1].isdigit():
            tiles[int(fields[0]), int(fields[1])] = (int(fields[2]), float(fields[3]))
    rooms = []
    for block in re.findall(r"\[Room\]\n(.*?)\n\[/Room\]", text[text.index("[Rooms]"):text.index("[/Rooms]")], re.S):
        lines = [line.split() for line in block.split("\n") if line.strip() and not line.startswith("[")]
        count = int(lines[0][3])
        rooms.append((int(lines[0][0]), lines[0][1], int(lines[0][2]),
                      [(int(fields[0]), int(fields[1])) for fields in lines[1:count + 1]],
                      lines[count + 1] if len(lines) > count + 1 else []))
    raid = text[text.index("[Raid]"):text.index("[/Raid]")]
    gate = re.search(r"^Gate\t(\d+)\t(\d+)\t(\S+)$", raid, re.M)
    seats = re.search(r"^Seats\t(\d+)\t(\d+)$", raid, re.M)
    return sizes[0], sizes[1], tiles, rooms, gate, seats


def check_level(path, gate_tile, rotation, front, route_tile):
    """Checks the gate niche, its rock surroundings and the raid route of one level."""
    name = os.path.basename(path)
    text = read_data(path)
    if text is None:
        return
    size_x, size_y, tiles, rooms, gate, seats = load_level(text)
    check(gate is not None and seats is not None, name + ": the [Raid] section needs a Gate and a Seats line")
    if gate is None or seats is None:
        return
    check((int(gate.group(1)), int(gate.group(2))) == gate_tile and float(gate.group(3)) == rotation,
          name + ": the gate must stand at %d,%d with rotation %d" % (gate_tile + (rotation,)))
    check(FRONT_OF_ROTATION.get(rotation) == front, name + ": rotation %d must turn the gate front towards %s"
          % (rotation, front))

    def tile(position):
        """Type and fullness of a tile; unlisted tiles are full earth (GameMap::createNewMap)."""
        return tiles.get(position, (DIRT, 100.0))

    def is_rock(position):
        """True for indestructible full rock; beyond the map there is nothing to stand or dig either."""
        x, y = position
        if x < 0 or y < 0 or x >= size_x or y >= size_y:
            return True
        return tile(position) == (ROCK, 100.0)

    def is_floor(position):
        """True for dug earth floor."""
        return tile(position) == (DIRT, 0.0)

    gx, gy = gate_tile
    fx, fy = front
    ax, ay = (1, 0) if fx == 0 else (0, 1)

    def along(k, d=0):
        """The tile k steps along the wall from the gate tile and d steps forward (negative: behind the gate)."""
        return (gx + k * ax + d * fx, gy + k * ay + d * fy)

    gate_rooms = [room for room in rooms if room[0] == PORTAL_WAVE_ROOM]
    check(len(gate_rooms) == 1, name + ": exactly one hero portal room (the gate) is expected")
    if len(gate_rooms) == 1:
        _, _, owner, room_tiles, data = gate_rooms[0]
        check(owner == int(seats.group(1)), name + ": the gate room must belong to the raid seat")
        check(sorted(room_tiles) == sorted(along(k) for k in (-1, 0, 1)),
              name + ": the gate room must be the gate tile and its two neighbours along the wall, found %s" % room_tiles)
        check(len(room_tiles) == GATE_ROOM_TILES and data[:1] == [str(GATE_ROOM_TILES)],
              name + ": the gate room has %d tiles and keeps that count as its claimed value" % GATE_ROOM_TILES)
        for position in room_tiles:
            check(is_floor(position), name + ": gate room tile %d,%d must be dug floor" % position)

    # Behind the gate row up to the border, five tiles wide: rock only
    depth = 1
    while True:
        row = [along(k, -depth) for k in range(-2, 3)]
        inside = [p for p in row if 0 <= p[0] < size_x and 0 <= p[1] < size_y]
        if not inside:
            break
        for position in row:
            check(is_rock(position), name + ": tile %d,%d behind the gate must be rock" % position)
        depth += 1
    check(depth >= 2, name + ": the gate must have rock or the map border behind it")
    for k in (-2, 2):
        check(is_rock(along(k)), name + ": tile %d,%d beside the gate must be rock" % along(k))
    for k in (-1, 0, 1):
        check(is_floor(along(k, 1)), name + ": tile %d,%d in front of the gate must be open floor" % along(k, 1))
    for k in (-2, 2):
        check(is_rock(along(k, 1)) or is_floor(along(k, 1)),
              name + ": front corner %d,%d must be rock or floor, not a wall that can be dug or claimed" % along(k, 1))

    # The raid walks from the gate over floor, room and bridge tiles to the route tile
    room_cover = {position: kind for kind, _, _, room_tiles, _ in rooms for position in room_tiles}

    def walkable(position):
        """Floor that is not water or lava, or a tile under a room (bridges included)."""
        if position in room_cover:
            return True
        kind, fullness = tile(position)
        return fullness == 0.0 and kind not in (WATER, LAVA)

    seen = {gate_tile}
    queue = deque([gate_tile])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            position = (x + dx, y + dy)
            if 0 <= position[0] < size_x and 0 <= position[1] < size_y and position not in seen and walkable(position):
                seen.add(position)
                queue.append(position)
    check(route_tile in seen, name + ": the raid must reach %d,%d from the gate" % route_tile)


def check_code():
    """Rock is neither dug nor claimed, and the hero portal room cannot be claimed."""
    tile = read("source/entities/Tile.cpp")
    diggable = function(tile, "bool Tile::isDiggable(const Seat* seat) const")
    full_rock = diggable.index("case TileVisual::rockFull:")
    check(diggable.index("return false;", full_rock) < diggable.index("case TileVisual::goldFull:"),
          "Tile::isDiggable must keep full rock undiggable")
    wall = function(tile, "bool Tile::isWallClaimable(Seat* seat)")
    check(re.search(r"mType == TileType::rock[^;]*\)\s*return false;", wall) is not None,
          "Tile::isWallClaimable must keep rock unclaimable")
    portal = read("source/rooms/RoomPortalWave.cpp")
    check(re.search(r"\{\s*//[^\n]*\n\s*return false;\s*\}",
                    function(portal, "bool RoomPortalWave::isClaimable(Seat* seat) const")) is not None,
          "RoomPortalWave::isClaimable must keep the gate room unclaimable")


def check_material():
    """The passage behind the bars is the fortress stone with a faint green glow, not flat black."""
    text = read_data("materials/scripts/MoreyaGate.material")
    if text is None:
        return
    block = text[text.index("material MoreyaGateDepth"):]
    block = block[:block.index("\n}\n") + 2]
    check("texture MenuFortressStone.png" in block, "MoreyaGateDepth must show the fortress stone texture")
    stone = data_file("materials/textures/menu/MenuFortressStone.png")
    check(stone is None or os.path.isfile(stone), "the fortress stone texture must exist")
    check(re.search(r"\bdiffuse 0\.22 0\.26 0\.25 1\b", block) is not None and
          re.search(r"\bambient 0\.30 0\.34 0\.33 1\b", block) is not None,
          "MoreyaGateDepth must light its stone dimly (ambient 0.30 0.34 0.33, diffuse 0.22 0.26 0.25)")
    check(re.search(r"\bemissive 0\.10 0\.55 0\.24\b", block) is not None,
          "MoreyaGateDepth must glow faintly green (emissive 0.10 0.55 0.24)")


def main():
    """Runs every item of the check and prints the result."""
    for entry in LEVELS:
        check_level(*entry)
    check_code()
    check_material()
    seconds = time.perf_counter() - START
    content_packages.unchecked("check_moreya_gate_wall", NOT_CHECKED)
    print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % seconds)
    for failure in FAILURES:
        print("FAIL " + failure)
    if FAILURES:
        print("moreya gate wall: %d failures" % len(FAILURES))
        return 1
    print("moreya gate wall ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
