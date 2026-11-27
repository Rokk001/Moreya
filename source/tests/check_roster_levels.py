"""Check that no level names a removed creature class and that the successors are in place.

Every .level file under levels/ is read. A removed class may not appear as a creature class, a mesh, a portal
wave entry, a raid member, a Block trigger, a spawn or generate entry or a creature definition. A DarkElf may only
belong to a hero seat; keeper-side and rogue (seat 0) DarkElfs are Banshees. The number of class uses per successor
across all levels is a fixed value counted once after the successors were put in.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]

REMOVED = ("Rat", "Spider", "Roach", "LavaSpawn", "Slime", "Dwarf1", "NatureMonster", "Scarab",
           "TentacleAlbine", "TentacleGreen", "Kreatur", "Wyvern")

# Class uses per successor over all levels (creature lines, wave entries, raid members, Block triggers, spawn and
# generate entries) and the number of level files that use it, counted once on the branch after the swap.
# Banshee counted again on feature/creature-roster-w5a after the duplicate "Block 1 Banshee" lines of Brackenford,
# Coldwell and Mossgate (Rat and the keeper-side DarkElf both became the Banshee) were removed: 390 - 3 = 387.
EXPECTED_USES = {
    "Banshee": 387,
    "Ghoul": 189,
    "Witch": 70,
    "Butcher": 60,
    "DarkElf": 0,
    "Hunter": 111,
    "Paladin": 89,
    "Priestess": 26,
    "CrystalGolem": 84,
    "Cyclops": 83,
    "Minotaur": 41,
    "Werewolf": 60,
}
EXPECTED_FILES = {
    "Banshee": 41,
    "Ghoul": 37,
    "Witch": 24,
    "Butcher": 18,
    "DarkElf": 0,
    "Hunter": 21,
    "Paladin": 20,
    "Priestess": 8,
    "CrystalGolem": 15,
    "Cyclops": 15,
    "Minotaur": 7,
    "Werewolf": 15,
}

# Lines whose arguments are free text shown to the player; their wording is not a class reference.
TEXT_ACTIONS = ("message", "hint", "objective", "objectiveid", "mainobjectiveid", "optionalobjectiveid")
SECTION_RE = re.compile(r"^\[(/?)([A-Za-z]+)\]$")
TOKEN_SPLIT = re.compile(r"[\s:,;]+")


def seat_factions(lines):
    """Return the faction of every seat of a level; seat 0 is the rogue seat."""
    factions = {0: "Rogue"}
    stack = []
    seat = None
    for line in lines:
        text = line.strip()
        match = SECTION_RE.match(text)
        if match:
            if match.group(1):
                stack.pop()
            else:
                stack.append(match.group(2))
            continue
        if stack[-2:] == ["Seats", "Seat"]:
            fields = text.split()
            if len(fields) >= 2 and fields[0] == "seatId":
                seat = int(fields[1])
            elif len(fields) >= 2 and fields[0] == "faction" and seat is not None:
                factions[seat] = fields[1]
    return factions


def class_uses(lines):
    """Yield (line number, class name, owning seat) for every place a level names a creature class."""
    stack = []
    room_seat = None
    room_header = False
    raid_seat = None
    for number, line in enumerate(lines, 1):
        text = line.strip()
        match = SECTION_RE.match(text)
        if match:
            if match.group(1):
                stack.pop()
            else:
                stack.append(match.group(2))
                room_header = match.group(2) == "Room"
            continue
        if not text or text.startswith("#"):
            continue
        fields = text.split()
        section = "/".join(stack)
        if section == "Rooms/Room" and room_header:
            room_seat = int(fields[2])
            room_header = False
        elif section == "Creatures" and len(fields) >= 7 and fields[0].isdigit():
            yield number, fields[6], int(fields[0])
        elif section.endswith("Wave/Creatures") and len(fields) == 2:
            yield number, fields[0], room_seat
        elif section.endswith("Raid") and fields[0] == "Seats":
            raid_seat = int(fields[1])
        elif section.endswith("Raid") and fields[0] == "Member":
            yield number, fields[2], raid_seat
        elif section == "Triggers" and fields[0] == "Block":
            yield number, fields[2], int(fields[1])
        elif section.startswith("Triggers") and fields[0] == "Action" and len(fields) > 2 \
                and fields[1] in ("spawn", "generate"):
            start = 6 if fields[1] == "spawn" else 3
            for entry in fields[start:]:
                yield number, entry.split(":", 1)[0], int(fields[2])


def removed_tokens(lines):
    """Yield (line number, token) for every token outside free text that names a removed class or its mesh."""
    stack = []
    for number, line in enumerate(lines, 1):
        text = line.strip()
        match = SECTION_RE.match(text)
        if match:
            if match.group(1):
                stack.pop()
            else:
                stack.append(match.group(2))
            continue
        if not text or text.startswith("#") or "Info" in stack:
            continue
        fields = text.split()
        if fields[0] == "Action" and len(fields) > 1 and fields[1] in TEXT_ACTIONS:
            continue
        # The hero worker keeps its own model file Dwarf1.mesh; only the class Dwarf1 is removed.
        worker_line = "/".join(stack) == "Creatures" and len(fields) >= 7 and fields[6] == "DwarfWorker"
        for token in TOKEN_SPLIT.split(text):
            base = token[:-5] if token.endswith(".mesh") else token
            if base in REMOVED and not (worker_line and token == "Dwarf1.mesh"):
                yield number, token


def main():
    """Run the level roster check and report every failure."""
    errors = []
    uses = dict((name, 0) for name in EXPECTED_USES)
    files = dict((name, 0) for name in EXPECTED_USES)
    levels = sorted((repo / "levels").rglob("*.level"))
    assert levels, "no level files found"
    for path in levels:
        name = path.relative_to(repo).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        factions = seat_factions(lines)
        seen = set()
        for number, cls, seat in class_uses(lines):
            if cls in REMOVED:
                errors.append("%s:%d uses removed class %s" % (name, number, cls))
            if cls == "DarkElf" and factions.get(seat) != "Hero":
                errors.append("%s:%d DarkElf on seat %s (%s) must be a Banshee"
                              % (name, number, seat, factions.get(seat, "undefined")))
            if cls in uses:
                uses[cls] += 1
                seen.add(cls)
        for cls in seen:
            files[cls] += 1
        for number, token in removed_tokens(lines):
            errors.append("%s:%d names removed creature %s" % (name, number, token))
    for cls in EXPECTED_USES:
        if uses[cls] != EXPECTED_USES[cls]:
            errors.append("%s used %d times in levels, expected %d" % (cls, uses[cls], EXPECTED_USES[cls]))
        if files[cls] != EXPECTED_FILES[cls]:
            errors.append("%s used in %d level files, expected %d" % (cls, files[cls], EXPECTED_FILES[cls]))
    if errors:
        for error in errors:
            print("FAIL: " + error)
        return 1
    print("OK: %d level files free of removed creature classes; successor counts match" % len(levels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
