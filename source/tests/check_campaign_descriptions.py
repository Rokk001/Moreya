#!/usr/bin/env python3
"""Check the [Info] Description lines of the 24 campaign level files (no compile, no game start).

Every level file of the campaign has exactly one Description line in its [Info] block, written as one plain text line
for the raid campaign: a story level names its dungeon title, the guild of its raid and the Moreya gate; a bonus level
names its chamber title and that no raid comes. No description names an old warden of the former campaign or the word
warden, and none calls the Ziv a worker. The expected titles and guilds are fixed here (structure and guild table of
the raid campaign), counted once on this branch; the old wardens are the 31 Warden values of the former Campaign.cfg.
"""
import os
import re
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

#: Story level file -> (dungeon title, guild of its raid), 18 levels in campaign order.
STORY = [
    ("Brackenford", "Mold Pit", "Mud Fists"),
    ("Coldwell", "Drowned Larder", "Iron Latch"),
    ("Ravensledge", "Rat Warren", "Grey Fang"),
    ("Tinmoor", "Bleeding Seam", "Deep Picks"),
    ("Greywater", "Chain Gallery", "Drowned Oath"),
    ("Highcairn", "Slag Pit", "Stone Crown"),
    ("Lanternhill", "Ossuary", "Pale Flame"),
    ("Saltmere", "Tomb of Whispers", "Salt Wolves"),
    ("HollinFen", "Bone Chapel", "Order of the White Thorn"),
    ("Cinderhollow", "Rack Hall", "Ember Ram"),
    ("Ashcombe", "Iron Maw", "Burnt Wheel"),
    ("Ironbridge", "Torment Cells", "Anvil Host"),
    ("Bellwick", "Charnel Stair", "Silent Bell"),
    ("Goldspire", "Corpse Gate", "Gilded Hand"),
    ("Kingsfall", "Hall of Skulls", "Sun Court"),
    ("VarnsCrossing", "Ember Pit", "Black Legion"),
    ("Wraithwood", "Throne of Ash", "Ash Coven"),
    ("HollowmarkCitadel", "Heart of Moreya", "Crown Eternal"),
]
#: Bonus level file -> chamber title, 6 levels.
BONUS = [
    ("Mossgate", "The Forgotten Pit"),
    ("CrowshotGallery", "The Gallery of Crows"),
    ("SkittleCavern", "The Skull Lanes"),
    ("SwarmNight", "The Swarming Dark"),
    ("BoulderCourse", "The Rolling Tomb"),
    ("TwistingHalls", "The Twisting Abyss"),
]
#: The wardens of the former campaign (names without their titles), 31 entries.
OLD_WARDENS = [
    "Tobin Marsh", "Elsa Brack", "Hugo Cole", "Merrin Tay", "Bram Tull", "Osric Vane", "Liesl Ashby", "Corwin Gray",
    "Agathe Hollin", "Wren", "Bram Seward", "Ysolde Dunn", "Gareth Fenn", "Rolf Scarrow", "Ines Vale", "Oswin",
    "Pell Ashgrove", "Cassia Thorne", "Lorens Bell", "Hilde Cairn", "Hald", "Ivo Strand", "Mora Fenwick",
    "Alaric Penn", "Sabine Rook", "Varn", "Sable", "Dorian Silt", "Elowen Ash", "Aurel", "Castellan",
]
#: Longest description in characters, so that it stays one readable line.
MAX_LENGTH = 240


def names_of(warden):
    """The full name and the first name of an old warden, as whole-word patterns."""
    parts = warden.split()
    return [re.compile(r"\b%s\b" % re.escape(warden), re.I), re.compile(r"\b%s\b" % re.escape(parts[0]), re.I)]


def description_lines(path):
    """The Description lines inside the [Info] block of a level file."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"\[Info\](.*?)\[/Info\]", text, re.S)
    if match is None:
        return None
    return [line.rstrip("\r")[len("Description\t"):] for line in match.group(1).split("\n")
            if line.startswith("Description\t")]


def main():
    """Checks every description and reports each failure."""
    started = time.monotonic()
    failures = []
    if len(STORY) != 18 or len(BONUS) != 6 or len(OLD_WARDENS) != 31:
        failures.append("the fixed tables must hold 18 story levels, 6 bonus levels and 31 old wardens")
    patterns = [(warden, pattern) for warden in OLD_WARDENS for pattern in names_of(warden)]
    entries = [(name, title, guild) for name, title, guild in STORY] + [(name, title, None) for name, title in BONUS]
    for name, title, guild in entries:
        relative = "levels/campaign/%s.level" % name
        lines = description_lines(os.path.join(ROOT, relative))
        if lines is None or len(lines) != 1:
            failures.append("%s must have exactly one Description line in [Info]" % relative)
            continue
        text = lines[0]
        if not text.strip() or text != text.strip() or "\t" in text or len(text) > MAX_LENGTH:
            failures.append("%s: the description must be one plain line of at most %d characters" % (relative, MAX_LENGTH))
        if any(ord(char) > 126 for char in text):
            failures.append("%s: the description must be plain text" % relative)
        if title not in text:
            failures.append("%s: the description must name its title %s" % (relative, title))
        if guild is not None:
            if guild not in text or "Moreya gate" not in text:
                failures.append("%s: the description must name the %s and the Moreya gate" % (relative, guild))
        elif "No raid" not in text:
            failures.append("%s: the description of a bonus chamber must say that no raid comes" % relative)
        if re.search(r"\bwardens?\b", text, re.I):
            failures.append("%s: the description names a warden" % relative)
        for warden, pattern in patterns:
            if pattern.search(text):
                failures.append("%s: the description names the old warden %s" % (relative, warden))
                break
        if re.search(r"\bworkers?\b", text, re.I):
            failures.append("%s: the description calls the Ziv a worker" % relative)

    print('ODP_TEST_PHASE {"name":"descriptions","seconds":%.2f}' % (time.monotonic() - started))
    for failure in failures:
        print("FAIL " + failure)
    if failures:
        return 1
    print("campaign level descriptions: 18 raid levels and 6 chambers, no old warden: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
