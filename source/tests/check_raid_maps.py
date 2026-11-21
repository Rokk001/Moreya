#!/usr/bin/env python3
"""Non-compiling check of the rebuilt campaign maps of Moreya (raid plan R5, MAP1-MAP4, MAP7, CS2-CS5, RA1, RA5, RA9).

Every story level of the wing packages must have the Moreya gate at its fixed tile (the central tile of the only hero
portal room, owned by the raid seat), a [Raid] section whose groups have the fixed sizes of the structure table, the
named leader(s) of the structure table, members with a fixed skill template each, the attacked keeper as target, a
treasury of that keeper, a main goal completed by "Cond raid defeated", exactly its fixed main goals and victory
triggers, every victory requiring "Cond raid defeated" and the reached state of every main goal (RA9), and no more creatures or spawns for the keeper than the level had before the rebuild. Heartstone shards are
found (brought home) in exactly Coldwell, Greywater and Saltmere; the stone to a bonus level is found in exactly the
first story level of its wing. Bonus levels have no raid, no shard, no discovery and no kept minion.

All expected values are fixed here from the plan's tables (structure table, guild table, table "Gate, path and
phase-1 area per story map") and from the level files before the rebuild (keeper creatures and spawns, counted once on
feature/raid-campaign-r5-d at a22f08005); nothing is derived from the files under test. The game is not started and
nothing is compiled.

Usage: python -I source/tests/check_raid_maps.py
Exit 0 and "raid maps ok" when every item holds.
"""
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import campaign_packages  # noqa: E402
START = time.perf_counter()
FAILURES = []

# Story levels in campaign order: (map, gate tile, raid group sizes, leader of each group (None: not fixed),
# accepted names of the named leader of the last group). Wing 6 level 3: Sabine Rook leads the first raid.
STORY = (
    ("Brackenford", (38, 12), (5,), (None,), ("ElsaBrack",)),
    ("Coldwell", (48, 30), (5,), (None,), ("HugoCole",)),
    ("Ravensledge", (12, 40), (10,), (None,), ("RolfScarrow",)),
    ("Tinmoor", (24, 12), (5, 5), (None, None), ("MerrinTay",)),
    ("Greywater", (38, 24), (5, 5), (None, None), ("CorwinGray",)),
    ("Highcairn", (62, 45), (10, 10), (None, None), ("HildeCairn",)),
    ("Lanternhill", (66, 56), (10,), (None,), ("InesVale",)),
    ("Saltmere", (21, 53), (10,), (None,), ("BramSeward",)),
    ("HollinFen", (42, 42), (25,), (None,), ("AgatheHollin",)),
    ("Cinderhollow", (70, 50), (10, 10), (None, None), ("PellAshgrove",)),
    ("Ashcombe", (46, 12), (10, 10), (None, None), ("LieslAshby",)),
    ("Ironbridge", (22, 14), (25, 25), (None, None), ("GarethFenn",)),
    ("Bellwick", (25, 30), (25,), (None,), ("LorensBell",)),
    ("Goldspire", (47, 67), (25,), (None,), ("AlaricPenn",)),
    ("Kingsfall", (21, 29), (40,), (None,), ("PrinceAurel",)),
    ("VarnsCrossing", (45, 7), (25, 25), (None, None), ("MarshalVarn",)),
    ("Wraithwood", (84, 86), (25, 25), (None, None), ("ElowenAsh",)),
    # The king keeps the creature name of his old level (CastellanKing) or takes his full name.
    ("HollowmarkCitadel", (13, 43), (40, 40), (("SabineRook",), None), ("HighKingCastellan", "CastellanKing")),
)

# Bonus levels in campaign order with the first story level of their wing, whose hidden stone discovers them.
BONUS = (
    ("Mossgate", "Brackenford"),
    ("CrowshotGallery", "Tinmoor"),
    ("SkittleCavern", "Lanternhill"),
    ("SwarmNight", "Cinderhollow"),
    ("BoulderCourse", "Bellwick"),
    ("TwistingHalls", "VarnsCrossing"),
)

# The levels that hide a Heartstone shard: level 2 of wings 1 to 3.
SHARD_LEVELS = ("Coldwell", "Greywater", "Saltmere")

# Keeper seat creatures in [Creatures] and creatures spawned or generated for the keeper seat by the level script,
# counted once before the rebuild; the rebuild adds none (MAP7, no extra troops for the keeper).
KEEPER_BEFORE = {
    "Brackenford": (3, 3), "Coldwell": (3, 0), "Ravensledge": (3, 0), "Tinmoor": (3, 2), "Greywater": (3, 6),
    "Highcairn": (3, 3), "Lanternhill": (3, 6), "Saltmere": (3, 5), "HollinFen": (12, 2), "Cinderhollow": (7, 3),
    "Ashcombe": (9, 0), "Ironbridge": (9, 0), "Bellwick": (11, 3), "Goldspire": (4, 2), "Kingsfall": (5, 0),
    "VarnsCrossing": (5, 0), "Wraithwood": (6, 0), "HollowmarkCitadel": (5, 0),
}

# RA9: the main goals of each story level (the kept main goals of the table "Per-map goals after the rebuild" plus
# the raid goal) and the triggers that may win it, counted once on feature/raid-campaign-r5 after the RA9 repair:
# 18 levels, 75 main goals, 27 victory triggers. Every victory trigger must require "Cond raid defeated" and the
# reached state of every main goal of its level.
MAIN_GOALS = {
    "Brackenford": (("brackenford-main-home", "brackenford-main-grove", "brackenford-main-ford", "brackenford-main-keep",
                     "brackenford-main-raid"), ("mainVictory",)),
    "Coldwell": (("coldwell-main-heart", "coldwell-main-plaza", "coldwell-main-gate", "coldwell-main-raid"), ("mainVictory",)),
    "Ravensledge": (("ravensledge-main-heart", "ravensledge-main-shelf", "ravensledge-main-gate", "ravensledge-main-raid"),
                    ("mainVictory",)),
    "Tinmoor": (("tinmoor-main-heart", "tinmoor-main-seams", "tinmoor-main-posts", "tinmoor-main-raid"), ("mainVictory",)),
    "Greywater": (("greywater-main-heart", "greywater-main-gold", "greywater-main-siege", "greywater-main-raid"),
                  ("mainVictory",)),
    "Highcairn": (("highcairn-main-home", "highcairn-main-terraces", "highcairn-main-captain", "highcairn-main-raid"),
                  ("mainVictory",)),
    "Lanternhill": (("lanternhill-main-home", "lanternhill-main-road", "lanternhill-main-rival", "lanternhill-main-raid"),
                    ("rivalFalls", "rivalHeartDown", "mainVictory")),
    "Saltmere": (("saltmere-main-heart", "saltmere-main-gold", "saltmere-main-port", "saltmere-main-raid"), ("mainVictory",)),
    "HollinFen": (("hollinfen-main-home", "hollinfen-main-gate", "hollinfen-main-raid"), ("mainVictory",)),
    "Cinderhollow": (("cinderhollow-main-heart", "cinderhollow-main-seams", "cinderhollow-main-bridge",
                      "cinderhollow-main-rival", "cinderhollow-main-raid"),
                     ("rivalFalls", "rivalHeartDown", "rivalHeartFalls", "mainVictory")),
    "Ashcombe": (("ashcombe-main-heart", "ashcombe-main-basin", "ashcombe-main-raid"), ("mainVictory",)),
    "Ironbridge": (("ironbridge-main-home", "ironbridge-main-spans", "ironbridge-main-sites", "ironbridge-main-hold",
                    "ironbridge-main-raid"), ("rivalFalls", "rivalHeartDown")),
    "Bellwick": (("bellwick-main-heart", "bellwick-main-nave", "bellwick-main-keeper", "bellwick-main-raid"),
                 ("keeperFalls", "mainVictory")),
    "Goldspire": (("goldspire-main-home", "goldspire-main-town", "goldspire-main-route", "goldspire-main-vault",
                   "goldspire-main-raid"), ("mainVictory",)),
    "Kingsfall": (("kingsfall-main-heart", "kingsfall-main-champions", "kingsfall-main-army", "kingsfall-main-raid"),
                  ("mainVictory",)),
    "VarnsCrossing": (("varnscrossing-main-home", "varnscrossing-main-keep", "varnscrossing-main-rivals",
                       "varnscrossing-main-raid"), ("crossingHeld", "mainVictory")),
    "Wraithwood": (("wraithwood-main-heart", "wraithwood-main-witch", "wraithwood-main-rival", "wraithwood-main-forces",
                    "wraithwood-main-raid"), ("bothFall", "mainVictory")),
    "HollowmarkCitadel": (("hollowmark-main-heart", "hollowmark-main-courts", "hollowmark-main-raid",
                           "hollowmark-main-throne"), ("mainVictory",)),
}

# Skill templates a raid member may be fixed to (fighter templates of config/creatureSkills.cfg; workers do not raid).
TEMPLATES = frozenset((
    "Berserker", "Guardian", "Warlord", "Crusader", "Protector", "Vanguard", "Shade", "Venomist", "Dancer",
    "Marksman", "Hunter", "Skirmisher", "Destroyer", "Healer", "Hexer",
))

PORTAL_WAVE_ROOM = 10
TREASURY_ROOM = 3
RAID_ACTIONS = ("raidmember", "raidleader", "raidopen", "raidcountdown")


def check(condition, message):
    """Records the message as a failure when the condition does not hold."""
    if not condition:
        FAILURES.append(message)


def read(relative):
    """Returns the text of a file of the repository with Unix line ends."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n")


def section(text, name):
    """Returns the body of the top-level section [name] ... [/name], or None when the level has none.

    A section of the same name nested in another section (such as the [Creatures] of the wave data inside a hero
    portal [Room]) is skipped: only a header that stands outside every other open section counts.
    """
    stack = []
    body = None
    for line in text.split("\n"):
        marker = re.fullmatch(r"\[(/?)(\w+)\]", line.split("#", 1)[0].strip())
        if body is not None and not (marker and marker.group(1) and marker.group(2) == name and stack == [name]):
            body.append(line)
        if marker is None:
            continue
        tag = marker.group(2)
        if not marker.group(1):
            if not stack and tag == name and body is None:
                body = []
            stack.append(tag)
        elif tag in stack:
            while stack.pop() != tag:
                pass
            if body is not None and not stack:
                return "\n".join(body) + "\n"
    return None


def rows(body):
    """Returns the tab or space separated fields of the non-empty, non-comment lines of a section body."""
    result = []
    for line in (body or "").split("\n"):
        line = line.split("#", 1)[0].strip()
        if line:
            result.append(line.split())
    return result


def seats(text):
    """Returns {seatId: {key: value}} of the [Seats] section."""
    result = {}
    for block in re.findall(r"\[Seat\](.*?)\[/Seat\]", section(text, "Seats") or "", re.S):
        values = {}
        for fields in rows(block):
            if len(fields) == 2 and not fields[0].startswith("["):
                values[fields[0]] = fields[1]
        if "seatId" in values:
            result[int(values["seatId"])] = values
    return result


def human_seat(text):
    """Returns the seat id of the human keeper, or None."""
    humans = [seat for seat, values in seats(text).items() if values.get("player") == "Human"]
    return humans[0] if len(humans) == 1 else None


def rooms(text):
    """Returns the rooms of the level as (type, name, seat, [tiles])."""
    result = []
    for block in re.findall(r"\[Room\](.*?)\[/Room\]", section(text, "Rooms") or "", re.S):
        lines = rows(block)
        if not lines or len(lines[0]) < 4:
            continue
        kind, name, seat, count = int(lines[0][0]), lines[0][1], int(lines[0][2]), int(lines[0][3])
        tiles = [(int(fields[0]), int(fields[1])) for fields in lines[1:count + 1]]
        result.append((kind, name, seat, tiles))
    return result


def traps(text):
    """Returns the traps of the level (doors included) as (type, name, seat, [tiles])."""
    result = []
    for block in re.findall(r"\[Trap\](.*?)\[/Trap\]", section(text, "Traps") or "", re.S):
        lines = rows(block)
        if not lines or len(lines[0]) < 4:
            continue
        kind, name, seat, count = int(lines[0][0]), lines[0][1], int(lines[0][2]), int(lines[0][3])
        tiles = [(int(fields[0]), int(fields[1])) for fields in lines[1:count + 1]]
        result.append((kind, name, seat, tiles))
    return result


def triggers(text):
    """Returns the triggers of the level as (name, [condition fields], [action fields])."""
    result = []
    for block in re.findall(r"\[Trigger\](.*?)\[/Trigger\]", section(text, "Triggers") or "", re.S):
        lines = [line.strip().split("\t") for line in block.split("\n") if line.strip()]
        name = next((fields[1] for fields in lines if fields[0] == "Name" and len(fields) > 1), "")
        conditions = [fields for fields in lines if fields[0] == "Cond"]
        actions = [fields for fields in lines if fields[0] == "Action"]
        result.append((name, conditions, actions))
    return result


def brought_home(conditions, human):
    """True when the trigger requires an item to be brought to the keeper's heart."""
    for fields in conditions:
        if len(fields) == 5 and fields[1] == "reached" and fields[3] == "heart" and fields[4] == str(human):
            return True
        if len(fields) == 3 and fields[1] == "deliveredstone":
            return True
    return False


def keeper_creatures(text, human):
    """Returns (creatures of the keeper seat in [Creatures], creatures spawned or generated for it by script)."""
    placed = sum(1 for fields in rows(section(text, "Creatures")) if fields[0] == str(human))
    spawned = 0
    for _, _, actions in triggers(text):
        for fields in actions:
            if len(fields) > 2 and fields[1] == "spawn" and fields[2] == str(human):
                spawned += sum(1 for token in fields[6:] if ":" in token)
            elif len(fields) > 2 and fields[1] == "generate" and fields[2] == str(human):
                spawned += sum(1 for token in fields[3:] if ":" in token)
    return placed, spawned


def check_raid(name, text, human, gate, sizes, fixed_leaders, leader_names):
    """Checks the gate, the [Raid] section, the groups, their leaders and members of one story level."""
    raid = section(text, "Raid")
    check(raid is not None, name + ": no [Raid] section")
    if raid is None:
        return None
    lines = rows(raid)
    gates = [fields for fields in lines if fields[0] == "Gate"]
    check(len(gates) == 1 and len(gates[0]) == 4 and (int(gates[0][1]), int(gates[0][2])) == gate,
          name + ": the Moreya gate must stand at %d,%d" % gate)
    seat_lines = [fields for fields in lines if fields[0] == "Seats"]
    raid_seat = None
    if len(seat_lines) == 1 and len(seat_lines[0]) == 3:
        raid_seat, target = int(seat_lines[0][1]), int(seat_lines[0][2])
        check(target == human, name + ": the raid must attack the human keeper's seat %d" % human)
        check(seats(text).get(raid_seat, {}).get("faction") not in (None, "Keeper"),
              name + ": the raid seat %d must be a hero seat" % raid_seat)
    else:
        check(False, name + ": the [Raid] section needs one Seats line")
    # RA1: the gate is the central tile of the only hero portal room, which belongs to the raid seat.
    portals = [room for room in rooms(text) if room[0] == PORTAL_WAVE_ROOM]
    check(len(portals) == 1, name + ": exactly one hero portal room (the gate) must remain, found %d" % len(portals))
    if len(portals) == 1:
        _, _, owner, tiles = portals[0]
        centre = (round(sum(x for x, _ in tiles) / len(tiles)), round(sum(y for _, y in tiles) / len(tiles)))
        check(owner == raid_seat and centre == gate and gate in tiles,
              name + ": the gate room must belong to the raid seat and be centred on the gate tile")
        # RA1: no other room and no trap or door stands on a tile of the gate room (a door on the gate tile hides the
        # gate room from the raid, which then comes without the gate)
        others = [other[1] for other in rooms(text) + traps(text)
                  if other[1] != portals[0][1] and set(other[3]) & set(tiles)]
        check(not others, name + ": no other building may stand on the gate room, found %s" % others)
    groups = [fields for fields in lines if fields[0] == "Group"]
    members = [fields for fields in lines if fields[0] == "Member"]
    check([len(fields) for fields in groups] == [3] * len(groups) and len(groups) == len(sizes),
          name + ": the raid needs %d group(s)" % len(sizes))
    for fields in members:
        check(len(fields) == 6, name + ": malformed Member line " + " ".join(fields))
    members = [fields for fields in members if len(fields) == 6]
    if len(groups) != len(sizes):
        return raid_seat
    for index, (fields, size, fixed) in enumerate(zip(groups, sizes, fixed_leaders)):
        group_id, leader = fields[1], fields[2]
        own = [member for member in members if member[1] == group_id]
        check(len(own) == size, name + ": raid group %s must have %d members, found %d" % (group_id, size, len(own)))
        for member in own:
            check(member[5] in TEMPLATES, name + ": raid member %s of group %s needs a fixed fighter skill template, has %s"
                  % (member[4], group_id, member[5]))
            check(member[3].isdigit() and int(member[3]) > 0, name + ": raid member level must be a positive number")
        last = index == len(groups) - 1
        expected = leader_names if last else fixed
        if expected is not None:
            check(leader in expected, name + ": raid group %s must be led by %s, found %s"
                  % (group_id, " or ".join(expected), leader))
            check(any(member[4] == leader for member in own),
                  name + ": the leader %s must be a member of raid group %s" % (leader, group_id))
        else:
            check(leader not in leader_names, name + ": the named leader comes with the last raid group, not group " + group_id)
    named = [member for member in members if member[4] in leader_names]
    check(len(named) == 1, name + ": the named leader must be exactly one raid member")
    return raid_seat


def check_victory(name, text, human):
    """Checks the main goal 'raid defeated' and that every victory of the keeper requires the defeated raid and the
    reached state of every main goal of the level (RA9), with the fixed main goals and victory triggers."""
    all_triggers = triggers(text)
    main_goals = {fields[3] for _, _, actions in all_triggers for fields in actions
                  if len(fields) >= 5 and fields[1] == "mainobjectiveid" and fields[2] == str(human)}
    raid_goals = set()
    for trigger, conditions, actions in all_triggers:
        if ["Cond", "raid", "defeated"] in conditions:
            raid_goals.update(fields[3] for fields in actions if len(fields) == 5 and fields[1] == "objectivestate"
                              and fields[2] == str(human) and fields[4] == "reached" and fields[3] in main_goals)
    check(bool(raid_goals), name + ": a main goal of the keeper must be reached by 'Cond raid defeated'")
    fixed_goals, fixed_victories = MAIN_GOALS[name]
    check(sorted(main_goals) == sorted(fixed_goals),
          name + ": the main goals must be exactly %s, found %s" % (", ".join(fixed_goals), ", ".join(sorted(main_goals))))
    victories = []
    for trigger, conditions, actions in all_triggers:
        if not any(len(fields) >= 3 and fields[1] == "win" for fields in actions):
            continue
        victories.append(trigger)
        check(["Cond", "raid", "defeated"] in conditions,
              name + ": the victory of trigger %s must require 'Cond raid defeated'" % trigger)
        for goal in fixed_goals:
            check(["Cond", "objective", str(human), goal, "reached"] in conditions,
                  name + ": the victory of trigger %s must require the main goal %s" % (trigger, goal))
    check(victories == list(fixed_victories),
          name + ": the victory triggers must be exactly %s, found %s" % (", ".join(fixed_victories), ", ".join(victories)))


def main():
    """Runs every item of the check and prints the result."""
    # The wing packages: all 24 levels with the content repository, the 4 of wing 1 without it
    campaign = campaign_packages.definition_text(ROOT)
    configured = re.findall(r"^File=campaign/(\w+)\.level\s*$", campaign, re.M)
    story_names = campaign_packages.checked_names(ROOT, [entry[0] for entry in STORY])
    bonus_names = campaign_packages.checked_names(ROOT, [entry[0] for entry in BONUS])
    check(sorted(configured) == sorted(story_names + bonus_names),
          "the packages must list exactly the story and bonus levels of the structure table")
    discover_expected = {first: "campaign/%s.level" % bonus for bonus, first in BONUS}

    for name, gate, sizes, fixed_leaders, leader_names in STORY:
        if name not in story_names:
            continue
        text = campaign_packages.read_level(ROOT, name).replace("\r\n", "\n")
        human = human_seat(text)
        check(human is not None, name + ": no single human keeper seat")
        if human is None:
            continue
        check_raid(name, text, human, gate, sizes, fixed_leaders, leader_names)
        check(any(room[0] == TREASURY_ROOM and room[2] == human for room in rooms(text)),
              name + ": the keeper needs a treasury the raid can plunder")
        check_victory(name, text, human)
        placed, spawned = keeper_creatures(text, human)
        before = KEEPER_BEFORE[name]
        check(placed <= before[0], name + ": %d keeper creatures placed, at most %d allowed" % (placed, before[0]))
        check(spawned <= before[1], name + ": %d keeper creatures spawned by script, at most %d allowed"
              % (spawned, before[1]))

    for name in story_names + bonus_names:
        text = campaign_packages.read_level(ROOT, name).replace("\r\n", "\n")
        human = human_seat(text)
        all_triggers = triggers(text)
        shards = [(trigger, conditions) for trigger, conditions, actions in all_triggers
                  for fields in actions if fields[1:2] == ["shard"]]
        discovers = [(trigger, conditions, fields[2] if len(fields) > 2 else "") for trigger, conditions, actions
                     in all_triggers for fields in actions if fields[1:2] == ["discover"]]
        if name in SHARD_LEVELS:
            check(len(shards) > 0, name + ": the Heartstone shard is missing (Action shard)")
        else:
            check(not shards, name + ": only Coldwell, Greywater and Saltmere hide a Heartstone shard")
        for trigger, conditions in shards:
            check(brought_home(conditions, human), name + ": the shard of trigger %s must be brought home" % trigger)
        targets = {target for _, _, target in discovers}
        if name in discover_expected:
            check(targets == {discover_expected[name]}, name + ": the hidden stone must discover exactly "
                  + discover_expected[name] + ", found " + ", ".join(sorted(targets)))
        else:
            check(not targets, name + ": only the first story level of a wing discovers a bonus level, found "
                  + ", ".join(sorted(targets)))
        for trigger, conditions, _ in discovers:
            check(brought_home(conditions, human), name + ": the stone of trigger %s must be brought home" % trigger)
        check(not any(fields[1:2] == ["keepminion"] for _, _, actions in all_triggers for fields in actions),
              name + ": nothing is carried to the next level (keepminion)")

    for name in bonus_names:
        text = campaign_packages.read_level(ROOT, name).replace("\r\n", "\n")
        check(section(text, "Raid") is None, name + ": a bonus level has no raid ([Raid] section)")
        groups = section(text, "CombatGroups")
        check(not any(fields[0] in ("RaidGroup", "RaidMember") for fields in rows(groups)),
              name + ": a bonus level has no raid groups")
        all_triggers = triggers(text)
        check(not any(fields[1:2] == ["raid"] for _, conditions, _ in all_triggers for fields in conditions),
              name + ": a bonus level has no raid conditions")
        check(not any(len(fields) > 1 and fields[1] in RAID_ACTIONS for _, _, actions in all_triggers for fields in actions),
              name + ": a bonus level has no raid actions")
        check(not any(room[0] == PORTAL_WAVE_ROOM for room in rooms(text)), name + ": a bonus level has no hero portal")

    seconds = time.perf_counter() - START
    print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % seconds)
    for failure in FAILURES:
        print("FAIL " + failure)
    if FAILURES:
        print("raid maps: %d failures" % len(FAILURES))
        return 1
    print("raid maps ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
