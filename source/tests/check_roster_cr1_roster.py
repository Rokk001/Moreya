#!/usr/bin/env python3
"""Acceptance check CR1 (roster) and the config part of CR10 (first-estimate values) of the creature roster plan.

config/creatures.cfg and config/factions.cfg hold exactly the 36 creatures of the plan (sections 2-4). For every one
the check asserts the side (spawn pool, worker class, prison or crypt, neutral), the wage class, the skill group, the
family, the pre-skill id, the model file and the attack lines as listed; the life, wage, mana pool and attributes of
the first estimate (section 7); the walking speed the plan sets (Butcher slow, Werewolf fast, Crystal Golem slow); and
that every value of a new creature the plan does not set itself equals that of its predecessor (D23, D30, D38): the
need values, the mood problems, the behaviours, the rooms other than its favourite room, the temple prayer mana, the
racial relationships and the number of reaction lists that name it. The expected values are the fixed data of
source/tests/roster_plan_data.py (counted once from the plan and from the base commit 525317fb1).

Not covered here (see the report of the acceptance work): the load test with keeper and hero creatures of the new
roster (integration build) and the equipment lines (the weapons of the plan are partly missing until the content
split delivers them).

Usage: python -I source/tests/check_roster_cr1_roster.py
Exit 0 and "roster CR1 ok" when every item holds.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

CREATURES = plan.parse_creatures(plan.read("config/creatures.cfg"))
FACTIONS = "\n".join(line.split("#")[0] for line in plan.read("config/factions.cfg").splitlines())
ROOMS_CFG = plan.read("config/rooms.cfg")
RELATIONSHIPS = plan.read("config/relationships.cfg")
REACTIONS = plan.read("config/creatureReactions.cfg")


def stat(name, key, default=None):
    """Returns the first token of a [Stats] key of a creature, or the default."""
    words = CREATURES[name].get(key)
    return words[0] if words else default


def number(name, key, default):
    """Returns a [Stats] key of a creature as a float."""
    return float(stat(name, key, default))


def faction_blocks():
    """Returns {faction name: (worker class, [spawn pool classes in order])} of factions.cfg."""
    result = {}
    for block in re.findall(r"\[Faction\](.*?)\[/Faction\]", FACTIONS, re.S):
        name = re.search(r"^\s*Name\s+(\S+)", block, re.M).group(1)
        worker = re.search(r"^\s*WorkerClass\s+(\S+)", block, re.M).group(1)
        pool_text = re.search(r"\[SpawnPool\](.*?)\[/SpawnPool\]", block, re.S).group(1)
        pool = [line.split("#")[0].strip() for line in pool_text.splitlines() if line.split("#")[0].strip()]
        result[name] = (worker, pool)
    return result


def side_of(name, factions):
    """Returns (side, way of coming) of a class as the configuration gives it."""
    for faction, (worker, pool) in factions.items():
        side = plan.KEEPER if faction == "Keeper" else plan.HERO
        if name == worker:
            return side, plan.WORKER
        if name in pool:
            return side, "portal"
    if name == re.search(r"^\s*PrisonSpawnClass\s+(\S+)", ROOMS_CFG, re.M).group(1):
        return plan.KEEPER, plan.PRISON
    if name == re.search(r"^\s*CryptSpawnClass\s+(\S+)", ROOMS_CFG, re.M).group(1):
        return plan.KEEPER, plan.CRYPT
    if stat(name, "Champion", "0") == "1":
        return plan.NEUTRAL, plan.SUMMONED
    return plan.NEUTRAL, "rogue"


# ------------------------------------------------------------------------------------------- roster and side
check(sorted(CREATURES) == sorted(plan.ROSTER),
      "CR1: creatures.cfg holds exactly the 36 creatures of the plan; extra %s, missing %s"
      % (sorted(set(CREATURES) - set(plan.ROSTER)), sorted(set(plan.ROSTER) - set(CREATURES))))
FACTION_DATA = faction_blocks()
for name, (side, wage, group, family, _display) in sorted(plan.ROSTER.items()):
    if name not in CREATURES:
        continue
    got_side, way = side_of(name, FACTION_DATA)
    check(got_side == side, "CR1: %s is on the %s side (config: %s)" % (name, side, got_side))
    if wage in (plan.WORKER, plan.PRISON, plan.CRYPT, plan.SUMMONED):
        check(way == wage, "CR1: %s comes as %s (config: %s)" % (name, wage, way))
    elif side != plan.NEUTRAL:
        check(way == "portal", "CR1: %s comes through the portal (config: %s)" % (name, way))
    else:
        check(way == "rogue", "CR1: %s is a rogue creature (config: %s)" % (name, way))
    if isinstance(wage, int):
        check(stat(name, "FeeBase") == str(wage), "CR1: %s wage class %d (FeeBase %s)"
              % (name, wage, stat(name, "FeeBase")))
    check(stat(name, "SkillGroup", "none") == group, "CR1: %s skill group %s (config %s)"
          % (name, group, stat(name, "SkillGroup", "none")))
    check(stat(name, "SkillFamily", "none") == family, "CR1: %s family %s (config %s)"
          % (name, family, stat(name, "SkillFamily", "none")))
    pre = plan.PRE_SKILL[name]
    expected_pre = pre[0] if pre else "none"
    check(stat(name, "PreSkill", "none") == expected_pre, "CR1: %s pre-skill %s (config %s)"
          % (name, expected_pre, stat(name, "PreSkill", "none")))
    check(stat(name, "MeshName") == plan.MESH[name], "CR1: %s model %s (config %s)"
          % (name, plan.MESH[name], stat(name, "MeshName")))
    expected_tier4 = "none" if name == "Champion" else "T4_" + name
    check(stat(name, "TierFourSkill", "none") == expected_tier4, "CR1/CR8: %s tier 4 skill id %s (config %s)"
          % (name, expected_tier4, stat(name, "TierFourSkill", "none")))
    lines = tuple(row[0] for row in (CREATURES[name]["[CreatureSkills]"] or []))
    if name == "Dragon":
        expected_lines = plan.ATTACK_LINES_DRAGON
    elif name == "Champion":
        expected_lines = plan.ATTACK_LINES_CHAMPION
    elif name in plan.RANGED:
        expected_lines = ("MissileLaunch",)
    else:
        expected_lines = ("Melee",)
    check(lines == expected_lines, "CR1: %s attack lines %s (config %s)" % (name, expected_lines, lines))

# Spawn pools in the order of the plan: three per wage class 50, 100, 200, 400 (CR9 asserts the rooms)
for faction, classes in plan.SPAWN_POOLS.items():
    expected_pool = [name for tier in classes for name in tier]
    worker, pool = FACTION_DATA.get(faction, (None, []))
    check(pool == expected_pool, "CR1/CR9: %s spawn pool %s (config %s)" % (faction, expected_pool, pool))
    check(worker == plan.WORKER_CLASS[faction], "CR1: %s worker class %s (config %s)"
          % (faction, plan.WORKER_CLASS[faction], worker))
check(sorted(FACTION_DATA) == ["Hero", "Keeper"], "CR1: the factions Keeper and Hero")

# ------------------------------------------------------------------------------- CR10: first-estimate values
for name, (side, wage, group, family, _display) in sorted(plan.ROSTER.items()):
    if name not in CREATURES:
        continue
    if name in plan.KEPT_VALUES:
        life, growth, fee, fee_level = plan.KEPT_VALUES[name]
    else:
        life, growth, fee, fee_level = plan.CLASS_VALUES[wage]
        life = life * plan.LOW_LIFE.get(name, 1.0)
    tolerance = 0.2 if name in plan.LOW_LIFE else 0.001
    check(abs(number(name, "MinHP", "0") - life) <= tolerance, "CR10: %s life %.2f at level 1 (config %s)"
          % (name, life, stat(name, "MinHP")))
    check(abs(number(name, "HP/Level", "0") - growth) <= 0.001, "CR10: %s life growth %.2f (config %s)"
          % (name, growth, stat(name, "HP/Level")))
    if fee is None:
        check(stat(name, "FeeBase") is None and stat(name, "FeePerLevel") is None, "CR10: %s has no wage" % name)
    else:
        check(stat(name, "FeeBase") == str(fee) and stat(name, "FeePerLevel") == str(fee_level),
              "CR10: %s wage %d + %d per level (config %s + %s)"
              % (name, fee, fee_level, stat(name, "FeeBase"), stat(name, "FeePerLevel")))
    pool, strength, dexterity = plan.ATTRIBUTES[name]
    got_pool = number(name, "Mana", "20") * number(name, "ManaPerPoint", "1.5")
    check(abs(got_pool - pool) <= plan.MANA_POOL_TOLERANCE, "CR10: %s mana pool %s (config %.2f)"
          % (name, pool, got_pool))
    check(number(name, "Strength", "20") == strength and number(name, "Dexterity", "20") == dexterity,
          "CR10: %s Strength/Dexterity %d/%d (config %s/%s)"
          % (name, strength, dexterity, stat(name, "Strength", "20"), stat(name, "Dexterity", "20")))
for name, speed in plan.SPEED_EXACT.items():
    check(abs(number(name, "GroundMoveSpeed", "0") - speed) <= 0.001, "CR1: %s walks at %.2f (config %s)"
          % (name, speed, stat(name, "GroundMoveSpeed")))
for name, speed in plan.SPEED_AT_MOST.items():
    check(number(name, "GroundMoveSpeed", "9") <= speed + 0.001, "CR1: %s walks at most %.2f (config %s)"
          % (name, speed, stat(name, "GroundMoveSpeed")))

# ------------------------------------------------------------------- D23, D30, D38: values of the predecessor
for name, old in sorted(plan.PREDECESSOR.items()):
    if name not in CREATURES:
        continue
    entry = CREATURES[name]
    for key, value in zip(plan.NEED_KEYS, plan.PREDECESSOR_NEEDS[old]):
        got = stat(name, key, "0")
        check(got == value, "CR1 D23: %s %s %s as the %s (config %s)" % (name, key, value, old, got))
    check(plan.rows_hash(entry["[MoodModifiers]"] or []) == plan.PREDECESSOR_MOODS[old],
          "CR1 D23: %s has the mood problems of the %s" % (name, old))
    check(plan.rows_hash(entry["[CreatureBehaviours]"] or []) == plan.PREDECESSOR_BEHAVIOURS[old],
          "CR1 D23: %s has the behaviours (reactions to weakness and fear) of the %s" % (name, old))
    # Rooms (D23): every room of the predecessor stays with its likeness and efficiency, except its favourite
    # room, which the required room replaces. The favourite room of the predecessor is its first listed room of the
    # highest likeness among the rooms that are not on every type (training hall, casino, tavern, temple, arena,
    # guard room). The ghost room line of the ghost feature and the new favourite line are not compared here (CR9
    # asserts the favourite room).
    rooms = dict((row[0], tuple(row)) for row in entry["[RoomAffinity]"] or [])
    old_rooms = plan.PREDECESSOR_ROOMS[old]
    own = [row for row in old_rooms if row[0] not in plan.ROOMS_OF_EVERY_TYPE and int(row[1]) > 0]
    replaced = None
    if own:
        top = max(int(row[1]) for row in own)
        replaced = [row for row in own if int(row[1]) == top][0]
    favourite = plan.REQUIRED_ROOM.get(name, plan.NEUTRAL_FAVOURITE.get(name))
    for row in old_rooms:
        if row == replaced or row[0] == favourite:
            continue
        check(rooms.get(row[0]) == row, "CR1 D23: %s keeps the room line %s of the %s (config %s)"
              % (name, " ".join(row), old, rooms.get(row[0])))
    extra = sorted(room for room in rooms if room not in [row[0] for row in old_rooms]
                   and room not in (favourite, "GhostRoom"))
    check(not extra, "CR1 D23: %s has no room line of its own beyond its favourite room: %s" % (name, extra))
    prayer = re.search(r"^\s*TemplePrayerMana%s\s+(\S+)" % name, ROOMS_CFG, re.M)
    check(prayer is not None and prayer.group(1) == plan.PREDECESSOR_PRAYER_MANA[old],
          "CR1 D38: %s temple prayer mana %s as the %s (config %s)"
          % (name, plan.PREDECESSOR_PRAYER_MANA[old], old, prayer.group(1) if prayer else None))
    reaction_lines = sum(1 for line in REACTIONS.splitlines()
                         if line.split() and line.split()[0] == "Creatures" and name in line.split())
    check(reaction_lines == plan.PREDECESSOR_REACTION_LINES[old],
          "CR1 D38: %s is named on %d reaction lists as the %s (config %d)"
          % (name, plan.PREDECESSOR_REACTION_LINES[old], old, reaction_lines))
pairs = dict((tuple(match[0].split("_")), match[1])
             for match in re.findall(r"^\s*Racial_(\w+)\s+(-?\d+)", RELATIONSHIPS, re.M))
for pair, value in plan.RELATIONSHIP_PAIRS.items():
    check(pairs.get(pair) == value, "CR1 D38: racial relationship %s %s (config %s)" % (pair, value, pairs.get(pair)))
new_names = set(plan.PREDECESSOR)
for pair in pairs:
    if new_names & set(pair):
        check(pair in plan.RELATIONSHIP_PAIRS, "CR1 D38: racial relationship %s has no pair of a predecessor" % (pair,))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr1","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR1 ok")
