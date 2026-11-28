#!/usr/bin/env python3
"""Acceptance checks CR2 (removed creatures) and CR3 (successors, temple recipes) of the creature roster plan.

CR2: no shipped config file (config/*.cfg) and no GUI layout or image set (gui/) names a removed class (Rat, Roach,
Spider, Scarab, TentacleAlbine, TentacleGreen, NatureMonster, Dwarf1, Slime, LavaSpawn, Kreatur, Wyvern) as a word;
the model file Dwarf1.mesh of the hero worker is the one allowed use. No config file uses the removed families
tentacle and wild (SkillFamily, Family, Path lines). No player text of a level (the Info block and the message, hint
and objective actions) names a removed creature. The class uses inside the levels are checked by
check_roster_levels.py; the old-name table of the savegames keeps only hashes and is checked by
check_name_aliases.py.

CR3: the temple recipes of rooms.cfg are the 23 recipes of the base commit with the successors put in (the keeper
DarkElf of recipes 8 and 18-23 is the Banshee, D20); the number of recipes per successor is fixed. The level counts
per successor are fixed in check_roster_levels.py; loading an old savegame with every removed class and a keeper and
a rogue DarkElf is checked by check_old_save_successors.py (compiled probe).

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr2_removed.py
Exit 0 and "roster CR2 CR3 ok" when every item holds.
"""
import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

CLASS_WORD = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(plan.REMOVED) + r")(?![A-Za-z0-9_])")
FAMILY_LINE = re.compile(r"^\s*(SkillFamily|Family|Path)\s+(tentacle|wild|Tentacle|Wild)\s*$", re.M)
# Words a player text uses for a removed creature (singular and plural, the display names of the removed classes)
TEXT_WORD = re.compile(r"\b(rats?|roach(es)?|spiders?|scarabs?|tentacles?|nature ?monsters?|slimes?|lava ?spawns?|"
                       r"kreatur(en)?|wyverns?)\b", re.I)
TEXT_ACTIONS = ("message", "hint", "objective", "objectiveid", "mainobjectiveid", "optionalobjectiveid")
SECTION_RE = re.compile(r"^\[(/?)([A-Za-z]+)\]$")


def relative(path):
    """Returns the path relative to the repository with forward slashes."""
    return os.path.relpath(path, plan.ROOT).replace(os.sep, "/")


def class_uses(path):
    """Yields (line number, word) for every removed class name a text file names (Dwarf1.mesh excepted)."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            for match in CLASS_WORD.finditer(line):
                following = line[match.end():match.end() + 5]
                if match.group(1) + following in plan.KEPT_MESH_OF_REMOVED:
                    continue
                yield number, match.group(1)


def level_texts(path):
    """Yields (line number, text) of the player texts of a level: the Info block and the text actions."""
    stack = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            text = line.strip()
            match = SECTION_RE.match(text)
            if match:
                if match.group(1):
                    if stack:
                        stack.pop()
                else:
                    stack.append(match.group(2))
                continue
            fields = text.split()
            is_action = len(fields) > 1 and fields[0] == "Action" and fields[1] in TEXT_ACTIONS
            if ("Info" in stack and fields) or is_action:
                yield number, text


# ------------------------------------------------------------------------------------- CR2 config and GUI
files = sorted(glob.glob(os.path.join(plan.ROOT, "config", "*.cfg")))
files += sorted(glob.glob(os.path.join(plan.ROOT, "gui", "*.layout")))
files += sorted(glob.glob(os.path.join(plan.ROOT, "gui", "*.imageset")))
check(len(files) > 40, "CR2: config and GUI files found (%d)" % len(files))
for path in files:
    uses = list(class_uses(path))
    check(not uses, "CR2: %s names a removed class: %s" % (relative(path), ", ".join(
        "%d %s" % use for use in uses[:8]) + (" ..." if len(uses) > 8 else "")))
for path in sorted(glob.glob(os.path.join(plan.ROOT, "config", "*.cfg"))):
    text = plan.read(relative(path))
    lines = [text[:match.start()].count("\n") + 1 for match in FAMILY_LINE.finditer(text)]
    check(not lines, "CR2: %s uses a removed family (tentacle, wild) on lines %s%s"
          % (relative(path), lines[:8], " ..." if len(lines) > 8 else ""))

# ----------------------------------------------------------------------------------- CR2 level player texts
levels = sorted(glob.glob(os.path.join(plan.ROOT, "levels", "**", "*.level"), recursive=True))
check(len(levels) > 50, "CR2: level files found (%d)" % len(levels))
for path in levels:
    hits = [(number, TEXT_WORD.search(text).group(0)) for number, text in level_texts(path) if TEXT_WORD.search(text)]
    check(not hits, "CR2: a player text of %s names a removed creature: %s"
          % (relative(path), ", ".join("line %d '%s'" % hit for hit in hits)))

# ------------------------------------------------------------------------------------------ CR3 temple recipes
rooms = plan.read("config/rooms.cfg")
recipes = re.findall(r"^\s*TempleRecipe(\d+)\s+(\S+)", rooms, re.M)
count = re.search(r"^\s*TempleRecipeCount\s+(\d+)", rooms, re.M)
check(count is not None and int(count.group(1)) == len(plan.TEMPLE_RECIPES),
      "CR3: TempleRecipeCount %d (config %s)" % (len(plan.TEMPLE_RECIPES), count.group(1) if count else None))
check([int(index) for index, _ in recipes] == list(range(1, len(plan.TEMPLE_RECIPES) + 1)),
      "CR3: recipes numbered 1 to %d" % len(plan.TEMPLE_RECIPES))
for index, expected in enumerate(plan.TEMPLE_RECIPES, 1):
    got = recipes[index - 1][1] if index <= len(recipes) else None
    check(got == expected, "CR3: TempleRecipe%d %s (config %s)" % (index, expected, got))
for successor, expected in sorted(plan.RECIPES_PER_SUCCESSOR.items()):
    got = sum(1 for _, recipe in recipes if successor in re.split(r"[+=]", recipe))
    check(got == expected, "CR3: %d temple recipes name the %s (config %d)" % (expected, successor, got))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr2_cr3","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR2 CR3 ok")
