#!/usr/bin/env python3
"""Non-compiling check of the rooms of the four wing 1 levels (wing 1 rooms plan WR1-WR3, WR5, WR6, WR7).

1. WR1-WR3: for each level the rooms the keeper (seat 1) can build from the start, can research and may never build
   equal the fixed tables below. The start rooms are the [SkillDone] rooms of the seat plus the free level one entries
   of config/skills.cfg that the level neither forbids ([SkillNotAllowed]) nor withholds ([SkillNotFree]); a forbidden
   room is listed in [SkillNotAllowed]; every other room can be researched (a parent the level forbids counts as
   fulfilled, so every allowed room can be reached). Each level withholds exactly the free Tavern.
2. The Tavern stays a free level one entry everywhere else: it is in [FreeLevelOne] of config/skills.cfg and no level
   file outside levels/campaign/wing1 has a [SkillNotFree] section (skirmish and multiplayer levels unchanged).
3. The engine applies [SkillNotFree] (static wiring): the free level one start skips a withheld entry, its level 1 costs
   the full research points (Seat::getSkillCost in the research, the research tooltip and the AI order), the seat
   reads and writes the section in level and save files and sends it to the clients. The behaviour (no free start,
   full cost, save and load) is run by the compiled probe of source/tests/check_research_progression.py.
4. WR6: start gold and every non-room skill entry of the keeper seat are the values of the levels before the change
   (counted once on feature/raid-campaign at f3dc7d946).
5. WR5: on Brackenford the neutral portal is the fixed 3x3 room next to the heart; the keeper's workers
   walk from the heart to it without digging in the fixed number of steps, and no creature or trap of another seat
   stands on the open tiles joined to heart and portal.
6. WR7: every room a trigger condition of a level waits for can be built by the keeper there, no condition waits for
   a keeper trap or door, the goal doors are destroyed by creatures (trapgone), the four crossings of Ravensledge lie
   on its four neutral bridges (no bridge has to be built) and Mossgate keeps its fixed gold tiles to mine.
   The static winning paths of all four levels are checked by source/tests/check_campaign_playability.py, the
   sealing of the start by scripts/check-campaign-opening.py and the keeper rooms of WR9 by
   source/tests/check_raid_maps.py.

All expected values are fixed (here, and the per-level rows of the wing 1 levels in checks/wing1_rooms.json of the
content repository) and were counted once on feature/raid-campaign-r17; nothing is derived from the files under test. The game is not started and nothing is compiled.

The wing 1 levels lie in the wing package and the other levels in the content packages (scripts/campaign_packages.py,
scripts/content_packages.py); without the content the engine items run on the public levels and the wing 1 levels are
named as not checked.

Usage: python -I source/tests/check_wing1_rooms.py
Exit 0 and "wing 1 rooms ok" when every item holds.
"""
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402
START = time.perf_counter()
FAILURES = []

LEVELS = ("Brackenford", "Coldwell", "Ravensledge", "Mossgate")
KEEPER = 1

# The 23 rooms of the research tree (room skills of SkillType)
ROOMS = ("roomAlchemyLab", "roomArena", "roomBridgeStone", "roomBridgeWooden", "roomCasino", "roomCrypt",
         "roomDormitory", "roomGhostRoom", "roomGuardRoom", "roomHatchery", "roomHerbGarden", "roomInfirmary",
         "roomLibrary", "roomMerchant", "roomPrison", "roomSpa", "roomTavern", "roomTemple", "roomToilet",
         "roomTorture", "roomTrainingHall", "roomTreasury", "roomWorkshop")

# WR1: the start rooms of every level; WR2: the researchable rooms per level; WR3: every other room is forbidden
START_ROOMS = ("roomDormitory", "roomHatchery", "roomLibrary", "roomTreasury")
NOT_FREE = ("roomTavern",)

# The fixed per-level rows of the wing 1 levels (WR2 researchable rooms, WR6 start gold and non-room skill entries of
# the keeper seat before the change, WR5 the neutral portal of Brackenford next to the heart and the shortest walk in
# steps from a heart tile to it, WR7 the neutral bridges and crossing regions of Ravensledge and the gold tiles of
# Mossgate) are content: they lie in checks/wing1_rooms.json of the content repository (scripts/campaign_packages.py:
# content_data), with the values counted once on feature/raid-campaign-r17 and at f3dc7d946; None without content.
WING1_ROWS = campaign_packages.content_data(ROOT, "wing1_rooms")
if WING1_ROWS is not None:
    RESEARCH_ROOMS = {name: tuple(rooms) for name, rooms in WING1_ROWS["research_rooms"].items()}
    KEEPER_GOLD = WING1_ROWS["keeper_gold"]
    KEEPER_OTHER_SKILLS = {name: {section: tuple(entries) for section, entries in sections.items()}
                           for name, sections in WING1_ROWS["keeper_other_skills"].items()}
    MOLD_PIT_PORTAL = tuple(tuple(tile) for tile in WING1_ROWS["portal"])
    MOLD_PIT_WALK_STEPS = WING1_ROWS["portal_walk_steps"]
    RAVENSLEDGE_BRIDGES = tuple(WING1_ROWS["bridges"])
    RAVENSLEDGE_CROSSINGS = tuple(WING1_ROWS["crossings"])
    MOSSGATE_GOLD_TILES = WING1_ROWS["bonus_gold_tiles"]

TILE_DIRT = 1
TILE_GOLD = 2
TILE_GEM = 6
ROOM_TEMPLE = 1
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def check(condition, message):
    """Records the message as a failure when the condition does not hold."""
    if not condition:
        FAILURES.append(message)


def read(relative):
    """Returns the text of a file of the repository with Unix line ends; a mixed table of config/ comes joined with its
    own rows of the content (scripts/content_packages.py)."""
    return content_packages.read_text(ROOT, relative).replace("\r\n", "\n")


def wing1_level(name):
    """Returns the path of a wing 1 level in its wing package (or in the public tree), or None without the content."""
    path = campaign_packages.level_path(ROOT, name)
    return str(path) if os.path.isfile(str(path)) else None


def block(text, name):
    """Returns the body of the first section [name] ... [/name] of the text, or None."""
    found = re.search(r"^\[%s\]\n(.*?)^\[/%s\]" % (name, name), text, re.S | re.M)
    return found.group(1) if found else None


def keeper_seat(text):
    """Returns the [Seat] body of the keeper seat."""
    for body in re.findall(r"^\[Seat\]\n(.*?)^\[/Seat\]", block(text, "Seats") or "", re.S | re.M):
        if re.search(r"^seatId\t%d$" % KEEPER, body, re.M):
            return body
    return ""


def seat_list(seat, name):
    """Returns the entries of the section [name] of a seat body (empty when the seat has none)."""
    body = block(seat, name)
    return body.split() if body is not None else []


def tiles(text):
    """Returns {(x, y): (type, fullness, owner or None)} of the listed tiles."""
    result = {}
    for line in (block(text, "Tiles") or "").split("\n"):
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 4:
            result[int(fields[0]), int(fields[1])] = (int(fields[2]), float(fields[3]),
                                                      int(fields[4]) if len(fields) > 4 else None)
    return result


def rooms(text):
    """Returns the rooms of the level as (type, name, seat, [tiles])."""
    result = []
    for body in re.findall(r"^\[Room\]\n(.*?)^\[/Room\]", block(text, "Rooms") or "", re.S | re.M):
        lines = [line.split() for line in body.split("\n") if line.strip()]
        kind, name, seat, count = int(lines[0][0]), lines[0][1], int(lines[0][2]), int(lines[0][3])
        result.append((kind, name, seat, [(int(fields[0]), int(fields[1])) for fields in lines[1:count + 1]]))
    return result


def creature_positions(text, seat):
    """Returns the tiles of the creatures in [Creatures] that do not belong to the given seat."""
    result = []
    for line in (block(text, "Creatures") or "").split("\n"):
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 6 and int(fields[0]) != seat:
            result.append((int(round(float(fields[3]))), int(round(float(fields[4])))))
    return result


def trap_tiles(text, seat):
    """Returns the tiles of the traps and doors in [Traps] that do not belong to the given seat."""
    result = []
    for body in re.findall(r"^\[Trap\]\n(.*?)^\[/Trap\]", block(text, "Traps") or "", re.S | re.M):
        lines = [line.split() for line in body.split("\n") if line.strip()]
        if int(lines[0][2]) != seat:
            result.extend((int(fields[0]), int(fields[1])) for fields in lines[1:int(lines[0][3]) + 1])
    return result


def conditions(text):
    """Returns the fields of every Cond line of the triggers."""
    return [line.split("\t") for line in (block(text, "Triggers") or "").split("\n") if line.startswith("Cond\t")]


def check_rooms(name, text, free):
    """Item 1 (WR1-WR3) for one level."""
    seat = keeper_seat(text)
    done = set(seat_list(seat, "SkillDone"))
    forbidden = set(seat_list(seat, "SkillNotAllowed"))
    withheld = set(seat_list(seat, "SkillNotFree"))
    check(sorted(withheld) == sorted(NOT_FREE), name + ": the level must withhold exactly the free Tavern, found %s"
          % sorted(withheld))
    start = set(room for room in ROOMS if room in done or (room in free and room not in forbidden and
                                                            room not in withheld))
    forbidden_rooms = set(room for room in ROOMS if room in forbidden)
    research = set(ROOMS) - start - forbidden_rooms
    check(sorted(start) == sorted(START_ROOMS), name + ": start rooms %s, expected %s"
          % (sorted(start), sorted(START_ROOMS)))
    check(sorted(research) == sorted(RESEARCH_ROOMS[name]), name + ": researchable rooms %s, expected %s"
          % (sorted(research), sorted(RESEARCH_ROOMS[name])))
    expected_forbidden = set(ROOMS) - set(START_ROOMS) - set(RESEARCH_ROOMS[name])
    check(forbidden_rooms == expected_forbidden, name + ": forbidden rooms %s, expected %s"
          % (sorted(forbidden_rooms), sorted(expected_forbidden)))
    check(not (done & forbidden_rooms) and not (withheld & done), name + ": a room is both given and forbidden")


def check_unchanged(name, text):
    """Item 4 (WR6) for one level."""
    seat = keeper_seat(text)
    gold = re.search(r"^gold\t(\d+)$", seat, re.M)
    check(gold is not None and int(gold.group(1)) == KEEPER_GOLD[name], name + ": the start gold changed")
    for section_name, expected in KEEPER_OTHER_SKILLS[name].items():
        found = sorted(entry for entry in seat_list(seat, section_name) if not entry.startswith("room"))
        check(found == sorted(expected), name + ": the non-room entries of [%s] changed: %s" % (section_name, found))


def check_mold_pit_portal(text):
    """Item 5 (WR5) on Brackenford."""
    portals = [(name, seat, fields) for kind, name, seat, fields in rooms(text) if kind == 4]
    check([(name, seat, sorted(fields)) for name, seat, fields in portals] ==
          [("Portal1", 0, sorted(MOLD_PIT_PORTAL))], "Brackenford: the neutral portal must be the fixed room next to "
          "the heart, found %s" % portals)
    listed = tiles(text)
    heart = set(tile for kind, _, seat, fields in rooms(text) if kind == ROOM_TEMPLE and seat == KEEPER
                for tile in fields)
    room_tiles = set(tile for _, _, _, fields in rooms(text) for tile in fields)

    def open_tile(tile):
        """A tile the workers walk on without digging: a room tile or dug dirt, gold or gem."""
        if tile in room_tiles:
            return True
        kind, fullness, _ = listed.get(tile, (TILE_DIRT, 100.0, None))
        return kind in (TILE_DIRT, TILE_GOLD, TILE_GEM) and fullness == 0.0

    steps = {tile: 0 for tile in heart}
    queue = list(heart)
    while queue:
        tile = queue.pop(0)
        for dx, dy in NEIGHBOURS:
            other = (tile[0] + dx, tile[1] + dy)
            if other not in steps and open_tile(other):
                steps[other] = steps[tile] + 1
                queue.append(other)
    walk = min([steps[tile] for tile in MOLD_PIT_PORTAL if tile in steps] or [None], key=lambda value: value or 0)
    check(walk == MOLD_PIT_WALK_STEPS, "Brackenford: the workers must walk from the heart to the portal without "
          "digging in %d steps, found %s" % (MOLD_PIT_WALK_STEPS, walk))
    joined = set(steps)
    enemies = [tile for tile in creature_positions(text, KEEPER) if tile in joined]
    check(not enemies, "Brackenford: creatures of another seat stand between heart and portal: %s" % enemies)
    traps = [tile for tile in trap_tiles(text, KEEPER) if tile in joined]
    check(not traps, "Brackenford: traps of another seat lie between heart and portal: %s" % traps)


def check_winnable(name, text, built):
    """Item 6 (WR7) for one level; built is the set of rooms the keeper can build there."""
    for fields in conditions(text):
        if fields[1] == "room" and fields[2] == str(KEEPER):
            check("room" + fields[3] in built, name + ": a trigger waits for the room %s that the keeper cannot "
                  "build" % fields[3])
        check(fields[1] not in ("trap", "traps"), name + ": a trigger waits for a keeper trap or door")
        if fields[1] == "trapgone":
            owners = [seat for body in re.findall(r"^\[Trap\]\n(.*?)^\[/Trap\]", block(text, "Traps") or "",
                                                  re.S | re.M) for _, trap, seat in [body.split()[:3]]
                      if trap == fields[2]]
            check(len(owners) == 1 and owners[0] != str(KEEPER), name + ": the goal door %s must be a door of "
                  "another seat that creatures destroy" % fields[2])
    if name == "Ravensledge":
        bridges = [(room, seat, fields) for kind, room, seat, fields in rooms(text) if room.startswith("WoodenBridge")]
        check(sorted(room for room, seat, _ in bridges if seat == 0) == sorted(RAVENSLEDGE_BRIDGES),
              "Ravensledge: the four neutral wooden bridges must stay on the map")
        bridge_tiles = set(tile for _, _, fields in bridges for tile in fields)
        regions = {}
        for line in (block(text, "Triggers") or "").split("\n"):
            fields = line.split("\t")
            if fields[0] == "Region" and len(fields) == 6:
                regions[fields[1]] = tuple(int(value) for value in fields[2:])
        crossed = [fields[3] for fields in conditions(text) if fields[1] == "crossed"]
        check(sorted(crossed) == sorted(RAVENSLEDGE_CROSSINGS), "Ravensledge: the crossings changed: %s" % crossed)
        for region in RAVENSLEDGE_CROSSINGS:
            x1, y1, x2, y2 = regions.get(region, (0, 0, -1, -1))
            area = set((x, y) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1))
            check(area and area <= bridge_tiles, "Ravensledge: the crossing %s must lie on a neutral bridge" % region)
    if name == "Mossgate":
        gold = [tile for tile, (kind, fullness, _) in tiles(text).items() if kind == TILE_GOLD and fullness > 0.0]
        check(len(gold) == MOSSGATE_GOLD_TILES, "Mossgate: %d gold tiles, expected %d" % (len(gold),
                                                                                         MOSSGATE_GOLD_TILES))


def check_engine():
    """Items 2 and 3: the Tavern stays free elsewhere and the engine applies [SkillNotFree]."""
    # [FreeLevelOne] is an own row block of config/skills.cfg (content package core-config)
    if content_packages.has_content(ROOT):
        skills = read("config/skills.cfg")
        free = block(skills, "FreeLevelOne").split()
        check("roomTavern" in free, "the Tavern must stay a free level one entry of config/skills.cfg")
    else:
        free = []
        content_packages.unchecked("check_wing1_rooms", ["[FreeLevelOne] of config/skills.cfg"])
    # The levels/ folder of the public tree and of every content package (the wing 1 package lies outside of them)
    for levels in content_packages.data_folders(ROOT, "levels"):
        for folder, _, names in os.walk(str(levels)):
            for file_name in names:
                path = os.path.join(folder, file_name)
                if not file_name.endswith(".level") or os.path.dirname(path) == os.path.join(str(levels), "campaign",
                                                                                             "wing1"):
                    continue
                with open(path, encoding="utf-8", errors="replace") as handle:
                    check("[SkillNotFree]" not in handle.read(), content_packages.relative_path(ROOT, path) +
                          ": only the wing 1 levels withhold a free level one entry")
    seat = read("source/game/Seat.cpp")
    check("!skill->isFreeLevelOne() || isSkillNotAllowed(type) || isSkillNotFree(type)" in seat,
          "the free level one start must skip a withheld entry")
    check('str == "[SkillNotFree]"' in seat and 'os << "[SkillNotFree]"' in seat and 'os << "[/SkillNotFree]"' in seat,
          "the seat must read and write [SkillNotFree] in level and save files")
    check(seat.count("getSkillCost(") >= 3 and "skill->getNeededSkillPoints(level, isSkillNotFree(type))" in seat,
          "the research must pay the full level 1 cost of a withheld entry")
    check("mCurrentSkill->getNeededSkillPoints(" not in seat, "the research must use Seat::getSkillCost")
    seat_data = read("source/game/SeatData.cpp")
    check(seat_data.count("mSkillNotFree") >= 3, "the withheld entries must be sent to the clients")
    check("seat.getSkillCost(left," in read("source/ai/AiResearch.cpp"), "the AI must order research by its real cost")
    check("localPlayerSeat->getSkillCost(resType, level + 1)" in read("source/modes/GameMode.cpp"),
          "the research tooltip must show the real cost")
    probe = read("source/tests/check_research_progression.py")
    check("a withheld free level one entry is not given at the start" in probe and
          "the withheld list survives a save and load" in probe,
          "the compiled research probe must run the withheld entry and its save and load")
    return free


def main():
    """Runs every item of the check and prints the result."""
    room_skills = re.findall(r"^\s*(room[A-Z]\w*),", read("source/game/SkillType.h"), re.M)
    check(sorted(room_skills) == sorted(ROOMS), "the room skills changed: %s" % sorted(room_skills))
    free = check_engine()
    missing = [name for name in LEVELS if wing1_level(name) is None or WING1_ROWS is None]
    check(not missing or not content_packages.has_content(ROOT), "wing 1 levels or rows missing although the content "
          "is present: %s" % missing)
    content_packages.unchecked("check_wing1_rooms", ["wing 1 level " + name for name in missing])
    for name in LEVELS:
        if name in missing:
            continue
        with open(wing1_level(name), encoding="utf-8") as handle:
            text = handle.read().replace("\r\n", "\n")
        check_rooms(name, text, free)
        check_unchanged(name, text)
        check_winnable(name, text, set(START_ROOMS) | set(RESEARCH_ROOMS[name]))
        if name == "Brackenford":
            check_mold_pit_portal(text)
    print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % (time.perf_counter() - START))
    for failure in FAILURES:
        print("FAIL " + failure)
    if FAILURES:
        print("wing 1 rooms: %d failures" % len(FAILURES))
        return 1
    print("wing 1 rooms ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
