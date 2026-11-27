#!/usr/bin/env python3
"""Acceptance check CR9 (wage classes, portal and required rooms) of the creature roster plan, config part.

config/factions.cfg offers the creatures of each side by wage class (three per class 50, 100, 200, 400; sections 2-3);
config/spawnconditions.cfg gives every portal creature exactly one condition, its required room of D32 (at least one
tile, no further points), and nothing else (D27: no dormitory, gold or creature conditions); the Skeleton comes from
the prison, the Lich from the crypt and the workers by spell, so none of them has a spawn condition or a place in a
pool. Every new portal creature has its required room as its favourite room (D23), every neutral creature its room
of D32 (the Dragon keeps today's rooms). The favourite room is the room with the highest likeness, held by no other
room of the creature.

The skirmish game test (a creature arrives only after its required room was built) needs the integration build.

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr9_portal.py
Exit 0 and "roster CR9 ok" when every item holds.
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


def strip_comments(text):
    """Returns the text without its comments."""
    return "\n".join(line.split("#")[0] for line in text.splitlines())


CREATURES = plan.parse_creatures(plan.read("config/creatures.cfg"))
FACTIONS = strip_comments(plan.read("config/factions.cfg"))
SPAWN = strip_comments(plan.read("config/spawnconditions.cfg"))
ROOMS_CFG = plan.read("config/rooms.cfg")

# ------------------------------------------------------------------------------------------- spawn pools
pools = {}
for block in re.findall(r"\[Faction\](.*?)\[/Faction\]", FACTIONS, re.S):
    name = re.search(r"^\s*Name\s+(\S+)", block, re.M).group(1)
    text = re.search(r"\[SpawnPool\](.*?)\[/SpawnPool\]", block, re.S).group(1)
    pools[name] = [line.strip() for line in text.splitlines() if line.strip()]
for faction, tiers in sorted(plan.SPAWN_POOLS.items()):
    expected = [name for tier in tiers for name in tier]
    check(pools.get(faction) == expected, "CR9: %s spawn pool by wage class %s (config %s)"
          % (faction, expected, pools.get(faction)))
    for wage, tier in zip((50, 100, 200, 400), tiers):
        for name in tier:
            check(plan.ROSTER[name][1] == wage and (CREATURES.get(name, {}).get("FeeBase") or [None])[0] == str(wage),
                  "CR9: %s of the %s pool has the wage class %d (config %s)"
                  % (name, faction, wage, (CREATURES.get(name, {}).get("FeeBase") or [None])[0]))
pooled = set(name for pool in pools.values() for name in pool)
for name in ("Skeleton", "Lich", "Kobold", "DwarfWorker"):
    check(name not in pooled, "CR9: %s does not come through the portal" % name)
check(re.search(r"^\s*PrisonSpawnClass\s+(\S+)", ROOMS_CFG, re.M).group(1) == plan.PRISON_CLASS,
      "CR9: the Skeleton comes from the prison")
check(re.search(r"^\s*CryptSpawnClass\s+(\S+)", ROOMS_CFG, re.M).group(1) == plan.CRYPT_CLASS,
      "CR9: the Lich comes from the crypt")

# -------------------------------------------------------------------------------------- required rooms
conditions = {}
for block in re.findall(r"\[SpawnCondition\](.*?)\[/SpawnCondition\]", SPAWN, re.S):
    name = re.search(r"^\s*CreatureClass\s+(\S+)", block, re.M).group(1)
    rows = []
    for inner in re.findall(r"\[Condition\](.*?)\[/Condition\]", block, re.S):
        rows += [tuple(line.split()) for line in inner.splitlines() if line.split()]
    check(name not in conditions, "CR9: one spawn condition block for " + name)
    conditions[name] = rows
check(sorted(conditions) == sorted(plan.REQUIRED_ROOM),
      "CR9: spawn conditions for exactly the 24 portal creatures; extra %s, missing %s"
      % (sorted(set(conditions) - set(plan.REQUIRED_ROOM)), sorted(set(plan.REQUIRED_ROOM) - set(conditions))))
for name, room in sorted(plan.REQUIRED_ROOM.items()):
    expected = [("RoomTiles", room, "1", "0")]
    check(conditions.get(name) == expected, "CR9 D32 D27: %s needs only its room %s (config %s)"
          % (name, room, conditions.get(name)))


def favourite(name):
    """Returns the room of the highest likeness of a creature, or None when it is shared or the creature has none."""
    rows = CREATURES.get(name, {}).get("[RoomAffinity]") or []
    if not rows:
        return None
    top = max(int(row[1]) for row in rows)
    best = [row[0] for row in rows if int(row[1]) == top]
    return best[0] if len(best) == 1 else None


# ------------------------------------------------------------------------------------- favourite rooms
for name in sorted(plan.PREDECESSOR):
    if name in plan.REQUIRED_ROOM:
        check(favourite(name) == plan.REQUIRED_ROOM[name], "CR9 D23: the favourite room of %s is its required room %s "
              "(config %s)" % (name, plan.REQUIRED_ROOM[name], favourite(name)))
for name, room in sorted(plan.NEUTRAL_FAVOURITE.items()):
    check(favourite(name) == room, "CR9 D32: the favourite room of the neutral %s is %s (config %s)"
          % (name, room, favourite(name)))
dragon = tuple(tuple(row) for row in CREATURES.get("Dragon", {}).get("[RoomAffinity]") or [])
check(dragon == plan.DRAGON_ROOMS, "CR9 D32: the Dragon keeps today's rooms (config %s)" % (dragon,))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr9","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR9 ok")
