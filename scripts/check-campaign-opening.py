#!/usr/bin/env python3
"""Opening check for campaign levels: the first minute must not be decided by the layout.

For every level the state at the START of the game is checked (no trigger has fired yet):

1. Enemy walk path. The sources of the enemy team are the creatures of other teams and of
   the neutral seat 0, the script spawns of other teams and of seat 0 that happen at the
   level start (a trigger whose only conditions are "time 0", or that has none), their
   wave portals, their portals and their dungeon temples. For every source the walk path
   to the dungeon temple of the human seat is measured (4-neighbourhood, like the game):
   only over tiles that can be walked right now (open dirt, claimed or built tiles, rooms,
   bridges, doors; doors count as walkable). Every such connection is a FAIL, whatever its
   length: a source must always have to dig to reach the temple. Water and lava are walked
   like the game does: a source passes water if one of its creature classes has a
   WaterMoveSpeed above 0 in config/creatures.cfg, and lava if one has a LavaMoveSpeed
   above 0. The classes of a creature are its class (DefaultWorker: the WorkerClass of its
   seat's faction in config/factions.cfg), of a spawn the classes it spawns, of a temple the
   WorkerClass of the owner's faction, of a portal that and the faction's SpawnPool, of a
   wave portal those plus the classes of its waves and of its raid members; a class or faction that the configs do
   not know passes both. Solid rock never counts as passable. A tile that is rock at the
   start and opened later by a trigger therefore separates, as it should. Spawns of
   triggers that fire later in the game are game events and are covered by rule 3. The shortest path that may also cross solid dirt,
   gold and gem tiles is only reported (shortest_dig_path) and has no threshold. Levels
   outside the campaign (skirmish, realms) are exempt from this part.
   Exception: the Moreya gate of a story level in gate mode is no enemy source at the start,
   because nothing comes through it before its countdown ends. Gate mode means: the level
   has a [Raid] section, the wave portal room of its raid seat contains the Gate tile of
   that section, the room has no waves of its own, and the raid comes only after a
   countdown (Countdown above 0 seconds, or "-" with RaidCountdownSeconds of
   config/global.cfg above 0). Every other wave portal, portal, temple and creature
   counts as before; the gate is named in the output (gate_mode=x,y).

2. Open areas between the rooms of the human seat. Within OPEN_RADIUS tiles of the temple
   and within the bounding box of all rooms of the human seat, a square of at least
   OPEN_SQUARE x OPEN_SQUARE walkable (not dug) tiles that belong to no room, i.e. an open
   area larger than 4x4, is a large empty hall: FAIL (the largest one is reported with
   its corner). Furthermore, rooms
   placed for the human seat must be separated from each other by rock: two such rooms
   that touch each other, or a block of WIDE_PASSAGE x WIDE_PASSAGE open non-room tiles
   next to one of them (passage wider than MAX_PASSAGE_WIDTH), is a FAIL.

3. Safe zone around heart and nearest portal (SAFE_RADIUS, default 20 tiles, option
   --safe-radius N). The seat of the human player must be able to build up before it has
   to fight. The zone is every tile that is at most SAFE_RADIUS tiles away, over walkable
   and diggable tiles (dirt, gold, gem, rooms, doors; rock, water and lava block), from the
   dungeon heart, from the nearest portal or from the dig path between the two. Portals of
   that seat count, and so do unclaimed portals (owner seat 0) because the player claims
   them on the way.
   Inside the zone there must be no creature of an enemy seat (other team; neutral seat 0
   does not count), no trap or door of an enemy seat, no room of an enemy seat, no wave
   portal of an enemy seat and no script spawn action of an enemy seat whose spawn position
   lies in the zone (triggered or not). A level without such a portal is only
   checked around the heart. Applies to every level with a human (or, failing that,
   a choice) seat, campaign or not.

Tiles that the level file does not list are treated like the game does: full dirt
(fullness 100), diggable but not walkable until dug. This applies to every rule above.

Output is one line per level (PASS or FAIL, file, numbers). Levels listed in
scripts/check-campaign-opening.allowlist report FAIL but do not change the exit code
("known, to be fixed"); the exit code is 0 only if every level passes or is allowlisted.
This script contains no level data.

Usage:
  check-campaign-opening.py [--no-allowlist] [--safe-radius N] [--full] [--all] [<file> ...]
  check-campaign-opening.py --self-test

Without files all levels of levels/campaign/Campaign.cfg are checked; --all checks every
level file below levels/ (campaign, skirmish, multiplayer). --full lists every violation
(by default at most MAX_EXAMPLES examples per kind). A summary block ends the output.
"""

import os
import shutil
import sys
import tempfile
from collections import deque

# --- Constants ---------------------------------------------------------------------------
OPEN_RADIUS = 12
OPEN_SQUARE = 5
MAX_PASSAGE_WIDTH = 3
WIDE_PASSAGE = MAX_PASSAGE_WIDTH + 1
# A room of the human seat counts as "next to" a wide passage within this many tiles.
PASSAGE_ROOM_DISTANCE = 2
# Safe zone around heart and nearest portal of the human seat (walk/dig path in tiles).
SAFE_RADIUS = 20
MAX_EXAMPLES = 5

TILE_DIRT = 1
TILE_GOLD = 2
TILE_ROCK = 3
TILE_WATER = 4
TILE_LAVA = 5
TILE_GEM = 6
DIGGABLE_TYPES = (TILE_DIRT, TILE_GOLD, TILE_GEM)

ROOM_TEMPLE = 1
ROOM_PORTAL = 4
ROOM_PORTAL_WAVE = 10

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Level(object):
    """A parsed level: tiles, seats, rooms, creatures, traps and triggers."""

    def __init__(self, path):
        """Create an empty level for the given file path."""
        self.path = path
        self.width = 0
        self.height = 0
        self.types = {}
        self.fullness = {}
        self.seats = {}          # seatId -> dict of fields
        self.rooms = []          # (roomType, seatId, [(x, y)])
        self.doors = []          # (x, y)
        self.creatures = []      # (seatId, x, y)
        self.room_lines = []     # (name, line number), parallel to rooms
        self.creature_info = []  # (name, line number), parallel to creatures
        self.traps = []          # (name, seatId, x, y, line number)
        self.spawns = []         # (trigger name, seatId, x, y, line number)
        self.creature_classes = []  # class name of each creature, parallel to creatures
        self.spawn_classes = []  # [class names] of each spawn, parallel to spawns
        self.spawn_triggers = []  # index into trigger_conds of each spawn, parallel to spawns
        self.trigger_conds = []  # [(condition type, [arguments])] of each trigger block
        self.room_wave_classes = []  # [class names] of the waves of each room, parallel to rooms
        self.room_waves = []     # number of [Wave] blocks of each room, parallel to rooms
        self.raid = None         # the [Raid] section: {"gate": (x, y), "seat": id, "countdown": text}


def to_int(text):
    """Convert text to an integer, or return None if it is not a number."""
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_level(path):
    """Parse a level file into a Level object."""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = [l.rstrip("\r") for l in handle.read().split("\n")]
    level = Level(path)
    section = ""
    seat = None
    trigger_name = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        stripped = line.strip()
        if stripped == "":
            continue
        if stripped.startswith("["):
            if section == "Rooms" and stripped == "[Wave]" and level.room_waves:
                # a wave of the wave portal room read last
                level.room_waves[-1] += 1
            elif section == "Rooms" and stripped == "[Creatures]":
                # the creature list of a wave, not the [Creatures] section of the level
                section = "WaveCreatures"
            elif section == "WaveCreatures" and stripped == "[/Creatures]":
                section = "Rooms"
            elif section == "Triggers" and stripped == "[Trigger]":
                level.trigger_conds.append([])
            elif stripped == "[Raid]":
                level.raid = {}
                section = "Raid"
            elif stripped == "[/Raid]":
                section = ""
            elif stripped == "[Seat]":
                seat = {}
                section = "Seat"
            elif stripped == "[/Seat]":
                if seat is not None and "seatId" in seat:
                    level.seats[seat["seatId"]] = seat
                seat = None
                section = "Seats"
            elif stripped in ("[/Tiles]", "[/Rooms]", "[/Traps]", "[/Creatures]",
                              "[/Triggers]"):
                section = ""
            elif stripped in ("[Tiles]", "[Rooms]", "[Traps]", "[Creatures]", "[Triggers]"):
                section = stripped[1:-1]
                trigger_name = ""
            continue
        if stripped.startswith("#") and section != "Tiles":
            continue
        if section == "Seat":
            fields = line.split("\t")
            if len(fields) == 2:
                if fields[0] == "seatId" or fields[0] == "teamId":
                    value = to_int(fields[1])
                    if value is not None:
                        seat[fields[0]] = value
                elif fields[0] in ("player", "faction"):
                    seat[fields[0]] = fields[1].strip()
                elif fields[0] in ("startingX", "startingY"):
                    value = to_int(fields[1])
                    if value is not None:
                        seat[fields[0]] = value
        elif section == "Tiles":
            body = line.split("#", 1)[0].strip()
            if body == "":
                continue
            fields = body.split()
            if len(fields) == 1 and level.width == 0:
                level.width = int(fields[0])
            elif len(fields) == 1 and level.height == 0:
                level.height = int(fields[0])
            elif len(fields) >= 4:
                x = int(fields[0])
                y = int(fields[1])
                level.types[(x, y)] = int(fields[2])
                level.fullness[(x, y)] = float(fields[3])
        elif section in ("Rooms", "Traps"):
            fields = line.split("\t")
            if len(fields) == 4 and to_int(fields[0]) is not None:
                count = to_int(fields[3])
                tiles = []
                entry_line = index
                for _ in range(count):
                    if index >= len(lines):
                        break
                    tile = lines[index].split("\t")
                    index += 1
                    if len(tile) >= 2:
                        tiles.append((int(tile[0]), int(tile[1])))
                if section == "Rooms":
                    level.rooms.append((to_int(fields[0]), to_int(fields[2]), tiles))
                    level.room_lines.append((fields[1], entry_line))
                    level.room_waves.append(0)
                    level.room_wave_classes.append([])
                else:
                    for pos in tiles:
                        level.traps.append((fields[1], to_int(fields[2]), pos[0], pos[1],
                                            entry_line))
                    if "Door" in fields[1]:
                        level.doors.extend(tiles)
        elif section == "Creatures":
            fields = line.split("\t")
            if len(fields) >= 6 and to_int(fields[0]) is not None:
                x = to_int(fields[3])
                y = to_int(fields[4])
                if x is not None and y is not None:
                    level.creatures.append((to_int(fields[0]), x, y))
                    level.creature_info.append((fields[1], index))
                    level.creature_classes.append(fields[6].strip() if len(fields) > 6 else "")
        elif section == "WaveCreatures":
            fields = stripped.split()
            if fields and level.room_wave_classes:
                level.room_wave_classes[-1].append(fields[0])
        elif section == "Triggers":
            fields = line.split("	")
            if fields[0] == "Name" and len(fields) >= 2:
                trigger_name = fields[1].strip()
            elif fields[0] == "Cond" and len(fields) >= 2 and level.trigger_conds:
                level.trigger_conds[-1].append((fields[1].strip(),
                                                [f.strip() for f in fields[2:]]))
            elif fields[0] == "Action" and len(fields) >= 6 and fields[1] == "spawn":
                seat_value = to_int(fields[2])
                x = to_int(fields[3])
                y = to_int(fields[4])
                if seat_value is not None and x is not None and y is not None:
                    level.spawns.append((trigger_name, seat_value, x, y, index))
                    # Class:count or Class:count@Name entries after the count field
                    level.spawn_classes.append([f.strip().split(":", 1)[0]
                                                for f in fields[6:] if f.strip()])
                    level.spawn_triggers.append(len(level.trigger_conds) - 1)
        elif section == "Raid":
            fields = stripped.split()
            if fields[0] == "Gate" and len(fields) >= 3:
                x = to_int(fields[1])
                y = to_int(fields[2])
                if x is not None and y is not None:
                    level.raid["gate"] = (x, y)
            elif fields[0] == "Seats" and len(fields) >= 2:
                level.raid["seat"] = to_int(fields[1])
            elif fields[0] == "Countdown" and len(fields) >= 2:
                level.raid["countdown"] = fields[1]
            elif fields[0] == "Member" and len(fields) >= 3:
                level.raid.setdefault("classes", []).append(fields[2])
    if level.width <= 0 or level.height <= 0:
        return None
    # A tile that is not listed is full, diggable dirt in the game (new maps start as dirt
    # with fullness 100), not solid rock.
    for x in range(level.width):
        for y in range(level.height):
            if (x, y) not in level.types:
                level.types[(x, y)] = TILE_DIRT
                level.fullness[(x, y)] = 100.0
    return level


def human_seat(level):
    """Return the id of the first human seat, or None if there is none."""
    for seat_id in sorted(level.seats):
        if level.seats[seat_id].get("player") == "Human":
            return seat_id
    return None


def build_grids(level):
    """Returns (walkable, digpassable, room_tiles) as sets of (x, y)."""
    walkable = set()
    passable = set()
    for pos, tile_type in level.types.items():
        if tile_type in DIGGABLE_TYPES:
            passable.add(pos)
            if level.fullness.get(pos, 100.0) <= 0:
                walkable.add(pos)
    room_tiles = set()
    for room_type, _, tiles in level.rooms:
        for pos in tiles:
            walkable.add(pos)
            passable.add(pos)
            room_tiles.add(pos)
    for pos in level.doors:
        walkable.add(pos)
        passable.add(pos)
    return walkable, passable, room_tiles


def bfs(sources, allowed, width, height):
    """Breadth-first search from the sources over allowed tiles; return {tile: distance}."""
    dist = {}
    queue = deque()
    for pos in sources:
        if pos in allowed and pos not in dist:
            dist[pos] = 0
            queue.append(pos)
    while queue:
        x, y = queue.popleft()
        d = dist[(x, y)]
        for dx, dy in NEIGHBOURS:
            nxt = (x + dx, y + dy)
            if 0 <= nxt[0] < width and 0 <= nxt[1] < height and nxt in allowed \
                    and nxt not in dist:
                dist[nxt] = d + 1
                queue.append(nxt)
    return dist


def nearest(dist, tiles):
    """Return the smallest distance among the tiles that were reached, or None."""
    best = None
    for pos in tiles:
        if pos in dist and (best is None or dist[pos] < best):
            best = dist[pos]
    return best


def heart_tiles(level, seat_id):
    """Return the tiles of the seat's temple, or its starting position if it has no temple."""
    tiles = []
    for room_type, owner, room in level.rooms:
        if room_type == ROOM_TEMPLE and owner == seat_id:
            tiles.extend(room)
    if not tiles:
        seat = level.seats[seat_id]
        if "startingX" in seat and "startingY" in seat:
            tiles.append((seat["startingX"], seat["startingY"]))
    return tiles


def default_raid_countdown(root):
    """Return RaidCountdownSeconds of config/global.cfg below root, or None if it is not set."""
    path = os.path.join(root, "config", "global.cfg")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            fields = line.split("#", 1)[0].split()
            if len(fields) >= 2 and fields[0] == "RaidCountdownSeconds":
                try:
                    return float(fields[1])
                except ValueError:
                    return None
    return None


def load_movement(root):
    """Return {"classes": {class: (walks water, walks lava)}, "factions": {faction:
    (WorkerClass, [SpawnPool classes])}} from config/creatures.cfg and config/factions.cfg
    below root. A file that is missing gives an empty table."""
    classes = {}
    path = os.path.join(root, "config", "creatures.cfg")
    if os.path.isfile(path):
        current = None
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                fields = line.split("#", 1)[0].split()
                if len(fields) < 2:
                    continue
                if fields[0] == "Name":
                    current = fields[1]
                    classes.setdefault(current, [False, False])
                elif current is not None and fields[0] in ("WaterMoveSpeed", "LavaMoveSpeed"):
                    try:
                        speed = float(fields[1])
                    except ValueError:
                        continue
                    classes[current][0 if fields[0] == "WaterMoveSpeed" else 1] = speed > 0
    factions = {}
    path = os.path.join(root, "config", "factions.cfg")
    if os.path.isfile(path):
        name = None
        worker = None
        pool = []
        in_pool = False
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                fields = line.split("#", 1)[0].split()
                if not fields:
                    continue
                if fields[0] == "[Faction]":
                    name, worker, pool, in_pool = None, None, [], False
                elif fields[0] == "[/Faction]":
                    if name is not None:
                        factions[name] = (worker, pool)
                elif fields[0] == "[SpawnPool]":
                    in_pool = True
                elif fields[0] == "[/SpawnPool]":
                    in_pool = False
                elif in_pool:
                    pool.append(fields[0])
                elif fields[0] == "Name" and len(fields) >= 2:
                    name = fields[1]
                elif fields[0] == "WorkerClass" and len(fields) >= 2:
                    worker = fields[1]
    return {"classes": dict((k, tuple(v)) for k, v in classes.items()), "factions": factions}


def class_moves(movement, class_name, faction):
    """Return (walks water, walks lava) of a creature class. DefaultWorker is the WorkerClass
    of the faction (of any faction if the faction is unknown); an unknown class walks both."""
    if class_name == "DefaultWorker":
        factions = movement["factions"]
        if faction in factions:
            workers = [factions[faction][0]]
        else:
            workers = [worker for worker, _ in factions.values()]
        if not workers or None in workers:
            return (True, True)
        return classes_moves(movement, workers, faction)
    return movement["classes"].get(class_name, (True, True))


def classes_moves(movement, class_names, faction):
    """Return (walks water, walks lava) of a group: it passes a tile if one of its classes
    can. An empty group (classes not known) walks both."""
    if not class_names:
        return (True, True)
    water = False
    lava = False
    for name in class_names:
        moves = class_moves(movement, name, faction)
        water = water or moves[0]
        lava = lava or moves[1]
    return (water, lava)


def faction_classes(movement, faction, with_pool=True):
    """Return the classes that a room of the faction brings into the game: its WorkerClass
    (a temple), with with_pool also its SpawnPool (a portal or wave portal); for an unknown
    faction every class of the config."""
    factions = movement["factions"]
    if faction in factions:
        worker, pool = factions[faction]
        return ([worker] if worker else []) + (list(pool) if with_pool else [])
    return sorted(movement["classes"])


def is_start_trigger(level, number):
    """A trigger fires at the level start if it has no condition or only "time 0" ones."""
    if number < 0 or number >= len(level.trigger_conds):
        return False
    for kind, args in level.trigger_conds[number]:
        if kind != "time" or not args or to_int(args[0]) is None or to_int(args[0]) > 0:
            return False
    return True


def gate_mode_room(level, raid_default):
    """Return the index of the room that is the Moreya gate in gate mode, or None.

    Gate mode: the [Raid] section names the gate tile and the raid seat, the wave portal
    room of that seat contains the tile, the room has no waves of its own and the raid
    comes only after a countdown (Countdown above 0, or "-" with raid_default above 0)."""
    raid = level.raid
    if raid is None or "gate" not in raid or raid.get("seat") is None:
        return None
    countdown = raid.get("countdown")
    if countdown == "-":
        seconds = raid_default
    else:
        try:
            seconds = float(countdown) if countdown is not None else None
        except ValueError:
            seconds = None
    if seconds is None or seconds <= 0:
        return None
    for number, (room_type, owner, tiles) in enumerate(level.rooms):
        if room_type == ROOM_PORTAL_WAVE and owner == raid["seat"] and raid["gate"] in tiles \
                and level.room_waves[number] == 0:
            return number
    return None


def is_start_enemy(level, seat_id, owner):
    """Enemy at the start = the neutral seat 0 or a seat of another team."""
    if owner == 0:
        return True
    if owner not in level.seats or owner == seat_id:
        return False
    return level.seats[owner].get("teamId") != level.seats[seat_id].get("teamId")


def enemy_sources(level, seat_id, raid_default=None, movement=None):
    """Return (name, tile, (walks water, walks lava)) for every place where enemies of the
    seat start: other teams' temples, portals and wave portals, the creatures and level start
    spawns of other teams and of seat 0. The Moreya gate in gate mode is no source at the
    start. movement is the table of load_movement (None: read from the repository)."""
    if movement is None:
        movement = load_movement(repo_root())
    team = level.seats[seat_id].get("teamId")
    gate = gate_mode_room(level, raid_default)
    sources = []
    for other_id, seat in level.seats.items():
        if other_id == seat_id or seat.get("teamId") == team:
            continue
        faction = seat.get("faction")
        for room_type, owner, tiles in level.rooms:
            if owner == other_id and room_type in (ROOM_TEMPLE, ROOM_PORTAL) and tiles:
                names = faction_classes(movement, faction, room_type == ROOM_PORTAL)
                sources.append(("seat %d room type %d" % (other_id, room_type), tiles[0],
                                classes_moves(movement, names, faction)))
    for number, (room_type, owner, tiles) in enumerate(level.rooms):
        if number == gate:
            continue
        if room_type == ROOM_PORTAL_WAVE and tiles:
            owner_team = level.seats.get(owner, {}).get("teamId")
            if owner_team != team:
                faction = level.seats.get(owner, {}).get("faction")
                names = faction_classes(movement, faction) + level.room_wave_classes[number]
                if level.raid is not None and level.raid.get("seat") == owner:
                    names = names + level.raid.get("classes", [])
                sources.append(("wave portal of seat %d" % owner, tiles[0],
                                classes_moves(movement, names, faction)))
    for number, (owner, x, y) in enumerate(level.creatures):
        if is_start_enemy(level, seat_id, owner):
            name = level.creature_classes[number]
            faction = level.seats.get(owner, {}).get("faction")
            sources.append(("creature of seat %d at %d,%d (%s)" % (owner, x, y, name), (x, y),
                            class_moves(movement, name, faction)))
    for number, (trigger, owner, x, y, _) in enumerate(level.spawns):
        if is_start_enemy(level, seat_id, owner) \
                and is_start_trigger(level, level.spawn_triggers[number]):
            names = level.spawn_classes[number]
            faction = level.seats.get(owner, {}).get("faction")
            sources.append(("start spawn %s of seat %d at %d,%d (%s)" % (
                trigger, owner, x, y, " ".join(names)), (x, y),
                classes_moves(movement, names, faction)))
    return sources


def check_enemy_distance(level, seat_id, raid_default=None, movement=None):
    """Check how close enemies are to the seat's heart; return (reasons, shortest distance).
    raid_default is RaidCountdownSeconds for a level whose raid countdown is "-"; movement
    is the table of load_movement (None: read from the repository). Each source walks the
    water and lava tiles its classes can walk."""
    walkable, passable, _ = build_grids(level)
    water = set(pos for pos, kind in level.types.items() if kind == TILE_WATER)
    lava = set(pos for pos, kind in level.types.items() if kind == TILE_LAVA)
    hearts = heart_tiles(level, seat_id)
    walks = {}
    dig = bfs(hearts, passable, level.width, level.height)
    reasons = []
    shortest = None
    connected = []
    for name, pos, moves in enemy_sources(level, seat_id, raid_default, movement):
        if moves not in walks:
            allowed = set(walkable)
            if moves[0]:
                allowed |= water
            if moves[1]:
                allowed |= lava
            walks[moves] = bfs(hearts, allowed, level.width, level.height)
        walk = walks[moves]
        if pos in walk:
            connected.append((walk[pos], name))
        d = dig.get(pos)
        if d is not None:
            if shortest is None or d < shortest:
                shortest = d
    if connected:
        connected.sort()
        reasons.append("%d enemy source(s) walk to the heart without digging, nearest: %s "
                       "in %d tiles" % (len(connected), connected[0][1], connected[0][0]))
    return reasons, shortest


def largest_open_square(open_tiles, x0, y0, x1, y1):
    """Largest all-open square inside the box; returns (size, x, y) of its corner."""
    best = (0, 0, 0)
    side = {}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if (x, y) not in open_tiles:
                side[(x, y)] = 0
                continue
            value = 1 + min(side.get((x - 1, y), 0), side.get((x, y - 1), 0),
                            side.get((x - 1, y - 1), 0))
            side[(x, y)] = value
            if value > best[0]:
                best = (value, x - value + 1, y - value + 1)
    return best


def check_open_areas(level, seat_id):
    """Check the open area around the seat's heart; return (reasons, size, corner)."""
    walkable, _, room_tiles = build_grids(level)
    hearts = heart_tiles(level, seat_id)
    cx = sum(p[0] for p in hearts) // len(hearts)
    cy = sum(p[1] for p in hearts) // len(hearts)
    x0 = max(0, cx - OPEN_RADIUS)
    x1 = min(level.width - 1, cx + OPEN_RADIUS)
    y0 = max(0, cy - OPEN_RADIUS)
    y1 = min(level.height - 1, cy + OPEN_RADIUS)
    own_tiles = [pos for room_type, owner, tiles in level.rooms
                 if owner == seat_id for pos in tiles]
    if own_tiles:
        x0 = min(x0, min(p[0] for p in own_tiles) - 1)
        x1 = max(x1, max(p[0] for p in own_tiles) + 1)
        y0 = min(y0, min(p[1] for p in own_tiles) - 1)
        y1 = max(y1, max(p[1] for p in own_tiles) + 1)
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(level.width - 1, x1)
        y1 = min(level.height - 1, y1)
    open_tiles = set(p for p in walkable if p not in room_tiles
                     and x0 <= p[0] <= x1 and y0 <= p[1] <= y1)
    size, sx, sy = largest_open_square(open_tiles, x0, y0, x1, y1)
    reasons = []
    if size >= OPEN_SQUARE:
        reasons.append("open area %dx%d at %d,%d" % (size, size, sx, sy))
    own_rooms = [tiles for room_type, owner, tiles in level.rooms
                 if owner == seat_id]
    # rooms that touch each other
    owner_of = {}
    for number, tiles in enumerate(own_rooms):
        for pos in tiles:
            owner_of[pos] = number
    touching = set()
    for pos, number in owner_of.items():
        for dx, dy in NEIGHBOURS:
            other = owner_of.get((pos[0] + dx, pos[1] + dy))
            if other is not None and other != number:
                touching.add((min(number, other), max(number, other)))
    if touching:
        reasons.append("%d room pair(s) touch without rock" % len(touching))
    # wide passage next to an own room
    wide = 0
    wide_at = None
    for (x, y) in open_tiles:
        block = [(x + i, y + j) for i in range(WIDE_PASSAGE) for j in range(WIDE_PASSAGE)]
        if not all(p in open_tiles for p in block):
            continue
        near = False
        for bx, by in block:
            for ox in range(-PASSAGE_ROOM_DISTANCE, PASSAGE_ROOM_DISTANCE + 1):
                for oy in range(-PASSAGE_ROOM_DISTANCE, PASSAGE_ROOM_DISTANCE + 1):
                    if (bx + ox, by + oy) in owner_of:
                        near = True
        if near:
            wide += 1
            if wide_at is None or (y, x) < (wide_at[1], wide_at[0]):
                wide_at = (x, y)
    if wide:
        reasons.append("wide passage (>%d) next to a room, first at %d,%d"
                       % (MAX_PASSAGE_WIDTH, wide_at[0], wide_at[1]))
    return reasons, size, (sx, sy)


def player_seats(level):
    """Human seats; if there is none, the choice seats (any of them may be the player)."""
    humans = [i for i in sorted(level.seats) if level.seats[i].get("player") == "Human"]
    if humans:
        return humans
    return [i for i in sorted(level.seats) if level.seats[i].get("player") == "Choice"]


def is_enemy_seat(level, seat_id, owner):
    """Enemy = a real seat of another team. Neutral seat 0 does not count."""
    if owner == 0 or owner not in level.seats or owner == seat_id:
        return False
    return level.seats[owner].get("teamId") != level.seats[seat_id].get("teamId")


def bfs_parents(sources, allowed, width, height):
    """Like bfs, but return (distances, parents) so that a path can be rebuilt."""
    dist = {}
    parent = {}
    queue = deque()
    for pos in sources:
        if pos in allowed and pos not in dist:
            dist[pos] = 0
            parent[pos] = None
            queue.append(pos)
    while queue:
        x, y = queue.popleft()
        d = dist[(x, y)]
        for dx, dy in NEIGHBOURS:
            nxt = (x + dx, y + dy)
            if 0 <= nxt[0] < width and 0 <= nxt[1] < height and nxt in allowed \
                    and nxt not in dist:
                dist[nxt] = d + 1
                parent[nxt] = (x, y)
                queue.append(nxt)
    return dist, parent


def safe_zone(level, seat_id, radius):
    """Returns (zone, portal_text): zone maps tile -> dig/walk distance (<= radius) from the
    heart, the nearest portal of the seat and the path between them."""
    _, passable, _ = build_grids(level)
    hearts = list(heart_tiles(level, seat_id))
    portals = [pos for room_type, owner, tiles in level.rooms
               if room_type == ROOM_PORTAL and owner in (seat_id, 0) for pos in tiles]
    sources = list(hearts)
    portal_text = "no portal of the seat or unclaimed"
    if portals:
        dist, parent = bfs_parents(hearts, passable, level.width, level.height)
        reachable = sorted((dist[p], p) for p in portals if p in dist)
        if reachable:
            best_dist, best = reachable[0]
            for room_type, owner, tiles in level.rooms:
                if room_type == ROOM_PORTAL and owner in (seat_id, 0) and best in tiles:
                    sources.extend(tiles)
            pos = best
            while pos is not None:
                sources.append(pos)
                pos = parent[pos]
            portal_text = "nearest portal %d,%d path %d tiles" % (best[0], best[1], best_dist)
        else:
            by_air = sorted((min(abs(p[0] - h[0]) + abs(p[1] - h[1]) for h in hearts), p)
                            for p in portals)
            best = by_air[0][1]
            for room_type, owner, tiles in level.rooms:
                if room_type == ROOM_PORTAL and owner in (seat_id, 0) and best in tiles:
                    sources.extend(tiles)
            portal_text = "portal %d,%d not reachable by digging" % (best[0], best[1])
    zone, _ = bfs_parents(sources, passable, level.width, level.height)
    return dict((pos, d) for pos, d in zone.items() if d <= radius), portal_text


def check_safe_zone(level, seat_id, radius):
    """Returns (violations, portal_text); violations are (kind, text) tuples."""
    zone, portal_text = safe_zone(level, seat_id, radius)
    name = os.path.basename(level.path)
    found = []
    for number, (owner, x, y) in enumerate(level.creatures):
        if is_enemy_seat(level, seat_id, owner) and (x, y) in zone:
            label = level.creature_info[number]
            found.append(("enemy creature", "%s:%d seat %d %s at %d,%d (%d tiles)" % (
                name, label[1], owner, label[0], x, y, zone[(x, y)])))
    for trap_name, owner, x, y, line in level.traps:
        if is_enemy_seat(level, seat_id, owner) and (x, y) in zone:
            kind = "enemy door" if "Door" in trap_name else "enemy trap"
            found.append((kind, "%s:%d seat %d %s at %d,%d (%d tiles)" % (
                name, line, owner, trap_name, x, y, zone[(x, y)])))
    for number, (room_type, owner, tiles) in enumerate(level.rooms):
        if room_type == ROOM_PORTAL_WAVE:
            relevant = owner is not None and owner != seat_id and (
                owner not in level.seats or is_enemy_seat(level, seat_id, owner))
            kind = "enemy wave portal"
        else:
            relevant = is_enemy_seat(level, seat_id, owner)
            kind = "enemy room"
        if not relevant:
            continue
        inside = [p for p in tiles if p in zone]
        if inside:
            label = level.room_lines[number]
            found.append((kind, "%s:%d seat %s %s at %d,%d (%d tiles, %d of %d tiles inside)"
                          % (name, label[1], owner, label[0], inside[0][0], inside[0][1],
                             min(zone[p] for p in inside), len(inside), len(tiles))))
    for trigger, owner, x, y, line in level.spawns:
        if is_enemy_seat(level, seat_id, owner) and (x, y) in zone:
            found.append(("enemy spawn", "%s:%d trigger %s seat %d at %d,%d (%d tiles)" % (
                name, line, trigger, owner, x, y, zone[(x, y)])))
    return found, portal_text


def summarize_safe_zone(found, full):
    """Reasons for the output: one text per kind with a few examples."""
    kinds = []
    for kind, _ in found:
        if kind not in kinds:
            kinds.append(kind)
    reasons = []
    for kind in kinds:
        items = [text for k, text in found if k == kind]
        shown = items if full else items[:MAX_EXAMPLES]
        more = "" if len(shown) == len(items) else " +%d more" % (len(items) - len(shown))
        reasons.append("safe zone: %d %s [%s%s]" % (len(items), kind, "; ".join(shown), more))
    return reasons


def check_level(path, campaign_index, radius=SAFE_RADIUS, full=False, raid_default=None,
                movement=None):
    """Returns (status, reasons, numbers, violations). raid_default is RaidCountdownSeconds
    for a raid countdown "-" (None: read from config/global.cfg of the repository);
    movement is the water and lava table of load_movement (None: read from the repository)."""
    if raid_default is None:
        raid_default = default_raid_countdown(repo_root())
    level = parse_level(path)
    if level is None:
        return "SKIP", ["no tiles"], "", []
    seat_id = human_seat(level)
    safe_seats = [i for i in player_seats(level) if heart_tiles(level, i)]
    if not safe_seats:
        return "SKIP", ["no human seat"], "", []
    reasons = []
    shortest = None
    numbers = ""
    if seat_id is not None and heart_tiles(level, seat_id):
        gate_text = ""
        if campaign_index is not None:
            found, shortest = check_enemy_distance(level, seat_id, raid_default, movement)
            reasons.extend(found)
            if gate_mode_room(level, raid_default) is not None:
                gate_text = "gate_mode=%d,%d " % level.raid["gate"]
        found, size, corner = check_open_areas(level, seat_id)
        reasons.extend(found)
        numbers = "shortest_dig_path=%s largest_open=%dx%d@%d,%d %s" % (
            "none" if shortest is None else shortest, size, size, corner[0], corner[1], gate_text)
    violations = []
    portal_texts = []
    for other in safe_seats:
        found, portal_text = check_safe_zone(level, other, radius)
        violations.extend(found)
        portal_texts.append(portal_text)
    reasons.extend(summarize_safe_zone(violations, full))
    numbers += "safe_zone(r=%d): %s" % (radius, "; ".join(portal_texts))
    return ("FAIL" if reasons else "PASS"), reasons, numbers, violations


def repo_root():
    """Return the folder that contains the scripts folder."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def campaign_files(root):
    """Return the level files listed in the campaign config."""
    cfg = os.path.join(root, "levels", "Campaign.cfg")
    if not os.path.isfile(cfg):
        cfg = os.path.join(root, "levels", "campaign", "Campaign.cfg")
    result = []
    with open(cfg, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("File="):
                result.append(os.path.join(root, "levels", line[5:].replace("/", os.sep)))
    return result


def read_allowlist(root):
    """Return the set of level names that are allowed to fail the check for now."""
    names = set()
    path = os.path.join(root, "scripts", "check-campaign-opening.allowlist")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.split("#", 1)[0].strip()
                if line:
                    names.add(line)
    return names


def all_level_files(root):
    """Return all .level files below the levels folder, except the template."""
    result = []
    for folder, _, names in os.walk(os.path.join(root, "levels")):
        for name in sorted(names):
            if name.endswith(".level") and name != "template.level":
                result.append(os.path.join(folder, name))
    return sorted(result)


def run(files, root, use_allowlist, order, radius=SAFE_RADIUS, full=False):
    """Check the level files, print one line per level and return the exit code."""
    allow = read_allowlist(root) if use_allowlist else set()
    failed = 0
    counts = {"PASS": 0, "FAIL": 0, "FAIL known": 0, "SKIP": 0}
    kinds = {}
    for path in files:
        name = os.path.basename(path)
        norm = os.path.normcase(os.path.abspath(path))
        index = order.get(norm)
        if index is None and os.path.basename(os.path.dirname(norm)) == "campaign":
            index = len(order)
        status, reasons, numbers, violations = check_level(path, index, radius, full)
        text = "; ".join(reasons)
        for kind, _ in violations:
            kinds[kind] = kinds.get(kind, 0) + 1
        if status == "FAIL" and name in allow:
            counts["FAIL known"] += 1
            print("FAIL (known, to be fixed) %s %s | %s" % (name, numbers, text))
        elif status == "FAIL":
            failed += 1
            counts["FAIL"] += 1
            print("FAIL %s %s | %s" % (name, numbers, text))
        elif status == "SKIP":
            counts["SKIP"] += 1
            print("SKIP %s %s" % (name, text))
        else:
            counts["PASS"] += 1
            note = " (allowlist entry obsolete)" if name in allow else ""
            print("PASS %s %s%s" % (name, numbers, note))
    print("")
    print("Summary: %d level(s): %d PASS, %d FAIL, %d FAIL (known, allowlisted), %d SKIP" % (
        len(files), counts["PASS"], counts["FAIL"], counts["FAIL known"], counts["SKIP"]))
    if kinds:
        print("Safe zone violations by kind: " + ", ".join(
            "%s %d" % (k, kinds[k]) for k in sorted(kinds)))
    return 1 if failed else 0


# --- Self test ---------------------------------------------------------------------------
def synthetic_level(path, heart_x, enemy_x, rooms_gap, open_hall, portal_x=None, spawn_x=None,
                    trap_x=None, rock_wall_x=None, neutral_x=None, omit_dirt=False,
                    gate_x=None, gate_waves=0, gate_countdown="1800", gate_raid=True,
                    gate_tile_x=None, walker_x=None, enemy_seat=2, enemy_class="Knight",
                    corridor_to=None, liquid_x=None, liquid_type=TILE_WATER, spawn_time=5,
                    spawn_class="Knight"):
    """80x20 map, rock border, human temple around (heart_x, 10), enemy at enemy_x.
    omit_dirt leaves the full dirt tiles out of the file (the game fills them as dirt).
    gate_x puts a 3x3 wave portal room of seat 2 at gate_x..gate_x+2, joined to the temple
    by an open corridor on row 10, with gate_waves waves; gate_raid adds a [Raid] section
    whose Gate tile is (gate_tile_x or the room centre, 10) and whose Countdown is
    gate_countdown. walker_x puts another creature of seat 2 on that corridor.
    enemy_seat and enemy_class are the seat and class of the enemy creature. corridor_to
    opens row 10 from the temple to that x; liquid_x puts one tile of liquid_type (or any
    other tile type) on row 10. The spawn of spawn_x fires at spawn_time seconds and
    spawns spawn_class."""
    width, height = 80, 20
    lines = ["OpenDungeons_Version:0.7.1", "", "[Seats]"]
    for seat_id, team, player, x in ((1, 1, "Human", heart_x), (2, 2, "Inactive", enemy_x)):
        lines += ["[Seat]", "seatId\t%d" % seat_id, "teamId\t%d" % team, "player\t%s" % player,
                  "startingX\t%d" % x, "startingY\t10", "[/Seat]"]
    lines += ["[/Seats]", "", "[Tiles]", "%d # MapSizeX" % width, "%d # MapSizeY" % height]
    open_tiles = set()
    for x in range(heart_x - 2, heart_x + 3):
        for y in range(8, 13):
            open_tiles.add((x, y))
    for x in range(enemy_x - 1, enemy_x + 2):
        for y in range(9, 12):
            open_tiles.add((x, y))
    if enemy_x - heart_x < 20:
        for x in range(heart_x, enemy_x):
            open_tiles.add((x, 10))
    if corridor_to is not None:
        for x in range(heart_x, corridor_to + 1):
            open_tiles.add((x, 10))
    room2 = [(heart_x - 3 - rooms_gap - i, y) for i in range(3) for y in range(8, 11)]
    if open_hall:
        for x in range(heart_x - 12, heart_x - 6):
            for y in range(4, 16):
                open_tiles.add((x, y))
    open_tiles.update(room2)
    portal = []
    if portal_x is not None:
        portal = [(portal_x + i, y) for i in range(3) for y in range(9, 12)]
        open_tiles.update(portal)
    gate = []
    if gate_x is not None:
        gate = [(gate_x + i, y) for i in range(3) for y in range(9, 12)]
        open_tiles.update(gate)
        for x in range(gate_x + 3, heart_x - 2):
            open_tiles.add((x, 10))
    for y in range(height):
        for x in range(width):
            if rock_wall_x is not None and x == rock_wall_x:
                lines.append("%d\t%d\t3\t100" % (x, y))
            elif liquid_x is not None and (x, y) == (liquid_x, 10):
                lines.append("%d\t%d\t%d\t%d" % (x, y, liquid_type,
                                                    100 if liquid_type == TILE_ROCK else 0))
            elif (x, y) in open_tiles:
                lines.append("%d\t%d\t1\t0" % (x, y))
            elif x in (0, width - 1) or y in (0, height - 1):
                lines.append("%d\t%d\t3\t100" % (x, y))
            else:
                lines.append("%d\t%d\t1\t100" % (x, y))
    lines += ["[/Tiles]", "", "[Rooms]", "[Room]", "1\tDungeonTemple1\t1\t25"]
    for x in range(heart_x - 2, heart_x + 3):
        for y in range(8, 13):
            lines.append("%d\t%d" % (x, y))
    lines += ["[/Room]", "[Room]", "2\tDormitory1\t1\t9"]
    for pos in room2:
        lines.append("%d\t%d" % pos)
    if portal:
        lines += ["[/Room]", "[Room]", "4\tPortal1\t1\t%d" % len(portal)]
        for pos in portal:
            lines.append("%d\t%d" % pos)
    if gate:
        lines += ["[/Room]", "[Room]", "10\tMoreyaGate1\t2\t%d" % len(gate)]
        for pos in gate:
            lines.append("%d\t%d" % pos)
        lines += ["9\t100000\t0\t0\t-", "[Waves]"]
        for _ in range(gate_waves):
            lines += ["[Wave]", "[/Wave]"]
        lines.append("[/Waves]")
    lines += ["[/Room]", "[/Rooms]", "", "[Traps]"]
    if trap_x is not None:
        lines += ["1\tCannon1\t2\t1", "%d\t10\t1" % trap_x]
    lines += ["[/Traps]", "", "[Creatures]",
              "%d\tHero1\tKnight.mesh\t%d\t10\t0\t%s\t1\t0\tmax\t100\t0\t0"
              % (enemy_seat, enemy_x, enemy_class)]
    if neutral_x is not None:
        lines.append("0\tRogue1\tKnight.mesh\t%d\t10\t0\tKnight\t1\t0\tmax\t100\t0\t0"
                     % neutral_x)
    if walker_x is not None:
        lines.append("2\tHero2\tKnight.mesh\t%d\t10\t0\tKnight\t1\t0\tmax\t100\t0\t0"
                     % walker_x)
    lines += ["[/Creatures]", "", "[Triggers]"]
    if spawn_x is not None:
        lines += ["[Trigger]", "Name\tambush", "Mode\tonce", "Cond\ttime\t%d" % spawn_time,
                  "Action\tspawn\t2\t%d\t10\t1\t%s:1" % (spawn_x, spawn_class),
                  "[/Trigger]"]
    lines += ["[/Triggers]", ""]
    if gate and gate_raid:
        lines += ["[Raid]", "# Gate X Y RotationDegrees",
                  "Gate\t%d\t10\t0" % (gate_x + 1 if gate_tile_x is None else gate_tile_x),
                  "Seats\t2\t1", "Countdown\t%s" % gate_countdown, "Interval\t-",
                  "Group\t1\t-", "Member\t1\tKnight\t1\t-\t-", "[/Raid]", ""]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


# Fixed water and lava table of the self-test, independent of the configs of the repository.
SELF_TEST_MOVEMENT = {"classes": {"Knight": (True, False), "CaveHornet": (True, True)},
                      "factions": {}}


def self_test():
    """Run the check on generated levels and return the exit code."""
    directory = tempfile.mkdtemp()
    try:
        good = os.path.join(directory, "good.level")
        near = os.path.join(directory, "near.level")
        open_area = os.path.join(directory, "open.level")
        touching = os.path.join(directory, "touch.level")
        synthetic_level(good, 60, 4, 1, False)
        synthetic_level(near, 14, 30, 1, False)
        synthetic_level(open_area, 60, 4, 1, True)
        synthetic_level(touching, 60, 4, 0, False)
        safe_ok = os.path.join(directory, "safe_ok.level")
        safe_far = os.path.join(directory, "safe_far.level")
        safe_spawn = os.path.join(directory, "safe_spawn.level")
        safe_trap = os.path.join(directory, "safe_trap.level")
        safe_rock = os.path.join(directory, "safe_rock.level")
        safe_neutral = os.path.join(directory, "safe_neutral.level")
        synthetic_level(safe_ok, 60, 4, 1, False, portal_x=70, neutral_x=64)
        synthetic_level(safe_far, 60, 4, 1, False, portal_x=70, spawn_x=30)
        synthetic_level(safe_spawn, 60, 4, 1, False, portal_x=70, spawn_x=78)
        synthetic_level(safe_trap, 60, 4, 1, False, portal_x=70, trap_x=75)
        synthetic_level(safe_rock, 60, 4, 1, False, rock_wall_x=66, spawn_x=70)
        synthetic_level(safe_neutral, 60, 4, 1, False, portal_x=70, neutral_x=75)
        sparse_spawn = os.path.join(directory, "sparse_spawn.level")
        sparse_ok = os.path.join(directory, "sparse_ok.level")
        sparse_rock = os.path.join(directory, "sparse_rock.level")
        synthetic_level(sparse_spawn, 60, 4, 1, False, portal_x=70, spawn_x=78, omit_dirt=True)
        synthetic_level(sparse_ok, 60, 4, 1, False, portal_x=70, spawn_x=30, omit_dirt=True)
        synthetic_level(sparse_rock, 60, 4, 1, False, rock_wall_x=66, spawn_x=70,
                        omit_dirt=True)
        expectations = [(good, 5, "PASS"), (near, 5, "FAIL"), (open_area, 5, "FAIL"),
                        (touching, 5, "FAIL"), (safe_ok, 5, "PASS"), (safe_far, 5, "PASS"),
                        (safe_spawn, 5, "FAIL"), (safe_trap, 5, "FAIL"), (safe_rock, 5, "PASS"),
                        (safe_neutral, 5, "PASS"), (sparse_spawn, 5, "FAIL"),
                        (sparse_ok, 5, "PASS"), (sparse_rock, 5, "PASS")]
        ok = True
        for path, index, expected in expectations:
            status, reasons, numbers, _ = check_level(path, index, movement=SELF_TEST_MOVEMENT)
            print("%s (expected %s) %s | %s" % (status, expected, os.path.basename(path),
                                                  "; ".join(reasons)))
            if status != expected:
                ok = False
        # the connected variant must report the walk and the distance reason
        status, reasons, _, _ = check_level(near, 5, movement=SELF_TEST_MOVEMENT)
        if not any("walk to the heart" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(open_area, 5, movement=SELF_TEST_MOVEMENT)
        if not any("open area" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(touching, 5, movement=SELF_TEST_MOVEMENT)
        if not any("touch" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(safe_spawn, 5, movement=SELF_TEST_MOVEMENT)
        if not any("enemy spawn" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(safe_trap, 5, movement=SELF_TEST_MOVEMENT)
        if not any("enemy trap" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(sparse_spawn, 5, movement=SELF_TEST_MOVEMENT)
        if not any("enemy spawn" in r for r in reasons):
            ok = False
        # The Moreya gate in gate mode is no enemy source at the start; anything else that
        # walks to the heart still is: a gate with waves, a raid without countdown, a wave
        # portal without [Raid] section or apart from its Gate tile, a creature on the path.
        gate_cases = [("gate_ok", {}, 600.0, "PASS"),
                      ("gate_default", {"gate_countdown": "-"}, 600.0, "PASS"),
                      ("gate_default_zero", {"gate_countdown": "-"}, 0.0, "FAIL"),
                      ("gate_waves", {"gate_waves": 1}, 600.0, "FAIL"),
                      ("gate_now", {"gate_countdown": "0"}, 600.0, "FAIL"),
                      ("gate_no_raid", {"gate_raid": False}, 600.0, "FAIL"),
                      ("gate_other_tile", {"gate_tile_x": 50}, 600.0, "FAIL"),
                      ("gate_walker", {"walker_x": 40}, 600.0, "FAIL")]
        for name, options, raid_default, expected in gate_cases:
            path = os.path.join(directory, name + ".level")
            synthetic_level(path, 70, 4, 1, False, gate_x=30, **options)
            status, reasons, numbers, _ = check_level(path, 5, raid_default=raid_default,
                                                      movement=SELF_TEST_MOVEMENT)
            print("%s (expected %s) %s | %s | %s" % (status, expected, name, numbers,
                                                       "; ".join(reasons)))
            if status != expected:
                ok = False
            if expected == "FAIL" and not any("walk to the heart" in r for r in reasons):
                ok = False
            if expected == "PASS" and "gate_mode=31,10" not in numbers:
                ok = False
        status, reasons, _, _ = check_level(os.path.join(directory, "gate_walker.level"), 5,
                                            raid_default=600.0,
                                            movement=SELF_TEST_MOVEMENT)
        if not any("creature of seat 2 at 40,10" in r for r in reasons):
            ok = False
        status, reasons, _, _ = check_level(os.path.join(directory, "gate_waves.level"), 5,
                                            raid_default=600.0,
                                            movement=SELF_TEST_MOVEMENT)
        if not any("wave portal of seat 2" in r for r in reasons):
            ok = False
        # Water and lava are walked per class (Knight: water only, CaveHornet: water and
        # lava), the neutral seat 0 is an enemy, and a spawn of a "time 0" trigger is a
        # source at the start while a later spawn is not. Each case: (name, options,
        # expected status, text the walk reason must contain or None).
        corridor = {"enemy_x": 40, "corridor_to": 40}
        start = {"enemy_x": 70, "corridor_to": 40, "spawn_x": 40}
        walk_cases = [
            ("water_knight", dict(corridor, liquid_x=30), "FAIL",
             "creature of seat 2 at 40,10 (Knight)"),
            ("lava_knight", dict(corridor, liquid_x=30, liquid_type=TILE_LAVA), "PASS", None),
            ("lava_hornet", dict(corridor, liquid_x=30, liquid_type=TILE_LAVA,
                                 enemy_class="CaveHornet"), "FAIL",
             "creature of seat 2 at 40,10 (CaveHornet)"),
            ("rock_hornet", dict(corridor, liquid_x=30, liquid_type=TILE_ROCK,
                                 enemy_class="CaveHornet"), "PASS", None),
            ("seat0_walker", dict(corridor, enemy_seat=0), "FAIL",
             "creature of seat 0 at 40,10 (Knight)"),
            ("seat0_water", dict(corridor, enemy_seat=0, liquid_x=30), "FAIL",
             "creature of seat 0 at 40,10"),
            ("seat0_lava", dict(corridor, enemy_seat=0, liquid_x=30, liquid_type=TILE_LAVA),
             "PASS", None),
            ("start_spawn", dict(start, spawn_time=0), "FAIL",
             "start spawn ambush of seat 2 at 40,10 (Knight)"),
            ("start_spawn_water", dict(start, spawn_time=0, liquid_x=30), "FAIL",
             "start spawn ambush"),
            ("start_spawn_lava", dict(start, spawn_time=0, liquid_x=30, liquid_type=TILE_LAVA),
             "PASS", None),
            ("start_spawn_lava_hornet", dict(start, spawn_time=0, liquid_x=30,
                                             liquid_type=TILE_LAVA, spawn_class="CaveHornet"),
             "FAIL", "start spawn ambush of seat 2 at 40,10 (CaveHornet)"),
            ("later_spawn", dict(start, spawn_time=5), "PASS", None)]
        for name, options, expected, text in walk_cases:
            path = os.path.join(directory, name + ".level")
            synthetic_level(path, 14, options.pop("enemy_x"), 1, False, **options)
            status, reasons, numbers, _ = check_level(path, 5, movement=SELF_TEST_MOVEMENT)
            print("%s (expected %s) %s | %s" % (status, expected, name, "; ".join(reasons)))
            if status != expected:
                ok = False
            if text is not None and not any("walk to the heart" in r and text in r
                                            for r in reasons):
                ok = False
        print("self-test %s" % ("passed" if ok else "FAILED"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def main(argv):
    """Entry point: parse the arguments, run the check and return the exit code."""
    if "--self-test" in argv:
        return self_test()
    use_allowlist = "--no-allowlist" not in argv
    full = "--full" in argv
    radius = SAFE_RADIUS
    rest = []
    skip = False
    for position, arg in enumerate(argv):
        if skip:
            skip = False
        elif arg == "--safe-radius" and position + 1 < len(argv):
            radius = int(argv[position + 1])
            skip = True
        else:
            rest.append(arg)
    files = [a for a in rest if not a.startswith("--")]
    root = repo_root()
    order = {}
    for number, path in enumerate(campaign_files(root)):
        order[os.path.normcase(os.path.abspath(path))] = number
    if not files:
        files = all_level_files(root) if "--all" in argv else campaign_files(root)
    return run(files, root, use_allowlist, order, radius, full)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
