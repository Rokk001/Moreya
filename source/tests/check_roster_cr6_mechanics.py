#!/usr/bin/env python3
"""Acceptance check CR6 (new mechanics) of the creature roster plan, config part.

The skill tree of config/creatureSkills.cfg uses every new ability of the approved skill design (section 10 Q5) at
its place: the taunt (tier 1 of Ironclad, all enemies near from rank 3, taunted enemies deal less damage at rank 5),
parry with counter, heal over time on oneself and on all allies near, instant large heal, absorb shield on an ally
and on the group, defence buff on an ally, armour aura, curse over time, mark, hold in place, bleeding, poison
(blade and arrow), burn over time and the flurry; the life drain that heals allies is the tier 4 skill of Pit Demon
and Vampire (CR8). The reused abilities (heal, strength aura, weaken, slow, heavy blow, spin, grenade, lightning,
freeze, drain) sit at their places as well. Every active new ability costs mana (five Mana values), every new
ability that runs for a time has a Duration; every skill of the seven role groups gains properties at rank 3 and at
rank 5 (Rank3 and Rank5 cells) and changes its value with every rank (D22, D25).

The skill kinds, their skill classes and the CR7 experience hook are checked by check_creature_role_skills.py (W1).
The effect of every new ability on a test creature (it happens, ends after its duration, costs its mana) and one
game test per ability in a fight need the integration build.

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr6_mechanics.py
Exit 0 and "roster CR6 ok" when every item holds.
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

SKILLS, TIER_FOURS, _TEMPLATES = plan.parse_skill_config(plan.read("config/creatureSkills.cfg"))
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def kind_of(entry):
    """Returns the Kind token of a skill entry."""
    return entry.get("Kind", "").split()[0] if entry.get("Kind") else ""


def find(group, path, tier):
    """Returns the skill entries of a group, path and tier."""
    return [entry for entry in SKILLS
            if entry.get("Group") == group and entry.get("Path") == path and entry.get("Tier") == str(tier)]


def tokens(cell):
    """Returns the property tokens (upper case words) of a Rank cell."""
    return re.findall(r"\b[A-Z][A-Z_]+[A-Z]\b", cell or "")


def rank_values(cell):
    """Returns the five rank values of a Values cell as tuples of numbers, or None when a value is no number."""
    values = []
    for token in (cell or "").split():
        parts = token.split("/")
        if not all(NUMBER.match(part) for part in parts):
            return None
        values.append(tuple(float(part) for part in parts))
    return values


for table, what in ((plan.NEW_MECHANICS, "new"), (plan.REUSED_MECHANICS, "reused")):
    for (group, path, tier), kinds in sorted(table.items()):
        entries = find(group, path, tier)
        got = [kind_of(entry) for entry in entries]
        check(len(entries) == 1 and got[0] in kinds, "CR6: %s ability %s at tier %d of %s (%s) (config %s)"
              % (what, "/".join(kinds), tier, path, group, got))
        if len(entries) != 1 or what != "new":
            continue
        entry = entries[0]
        kind = got[0]
        mana = (entry.get("Mana") or "-").split()
        if kind in plan.NEVER_CAST_KINDS:
            check(mana == ["-"], "CR6: %s is never cast and costs no mana (config %s)" % (kind, entry.get("Mana")))
        else:
            check(len(mana) == 5 and all(NUMBER.match(value) and float(value) > 0 for value in mana),
                  "CR6: %s of %s costs mana at every rank (config %s)" % (kind, path, entry.get("Mana")))
        if kind in plan.TIMED_KINDS:
            check(NUMBER.match(entry.get("Duration", "-")) is not None and float(entry["Duration"]) > 0,
                  "CR6: %s of %s runs for a duration (config %s)" % (kind, path, entry.get("Duration")))

taunt = find("tank", "Ironclad", 1)
if taunt:
    check(plan.TAUNT_RANK3_PROPERTY in tokens(taunt[0].get("Rank3")), "CR6 D25: the taunt reaches all enemies near "
          "from rank 3 (Rank3 %s)" % taunt[0].get("Rank3"))
    check(plan.TAUNT_RANK5_PROPERTY in tokens(taunt[0].get("Rank5")), "CR6 D25: taunted enemies deal less damage "
          "from rank 5 (Rank5 %s)" % taunt[0].get("Rank5"))
parry = find("tank", "Evader", 3)
if parry:
    cells = " ".join(parry[0].get(key, "") for key in ("Rank1", "Rank3", "Rank5"))
    check(plan.PARRY_COUNTER_PROPERTY in tokens(cells), "CR6: the parry answers with a counter blow (%s)" % cells)
for name in ("PitDemon", "Vampire"):
    entries = [entry for entry in TIER_FOURS if entry.get("Creature") == name]
    check(len(entries) == 1 and kind_of(entries[0]) == "DRAIN_HEAL_ALLIES",
          "CR6: the life drain that heals allies is the tier 4 skill of %s (config %s)"
          % (name, [kind_of(entry) for entry in entries]))

# Ranks (D22, D25): every skill of the role groups gains properties at rank 3 and 5 and changes with every rank
for entry in SKILLS:
    group = entry.get("Group")
    if group is None or group == "worker" or group not in plan.GROUPS:
        continue
    label = "%s (%s)" % (entry.get("Id"), entry.get("Name"))
    check(tokens(entry.get("Rank3")) != [] and tokens(entry.get("Rank5")) != [],
          "CR6 D25: %s gains a property at rank 3 and at rank 5 (Rank3 %s, Rank5 %s)"
          % (label, entry.get("Rank3", "-"), entry.get("Rank5", "-")))
    values = rank_values(entry.get("Values"))
    rising = values is not None and len(values) == 5 and all(a < b for a, b in zip(values, values[1:]))
    falling = values is not None and len(values) == 5 and all(a > b for a, b in zip(values, values[1:]))
    check(rising or falling, "CR6 D25: %s changes its value with every rank (Values %s)"
          % (label, entry.get("Values")))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr6","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR6 ok")
