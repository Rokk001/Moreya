#!/usr/bin/env python3
"""Check the [Info] Description lines of the 24 campaign level files (no compile, no game start).

The levels of all six wings and their rows come from the content repository (scripts/campaign_packages.py); the
public tree holds no wing, so without it no level is checked (named as not checked) and only the public part of the
old warden table is.

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
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import campaign_packages  # noqa: E402

#: Story level file -> (dungeon title, guild of its raid): all 18 come from the content repository
#: (checks/campaign_descriptions.json, wings 1 to 6 in campaign order); the public tree holds no wing.
STORY = []
#: Bonus level file -> chamber title: the 6 bonus levels come from the content repository.
BONUS = []
#: The wardens of the former campaign (names without their titles), 31 entries: the 15 names the public tree
#: may hold; the 16 names that are also paid campaign names come from the content repository.
OLD_WARDENS = [
    'Tobin Marsh',
    'Bram Tull',
    'Osric Vane',
    'Wren',
    'Ysolde Dunn',
    'Oswin',
    'Cassia Thorne',
    'Hald',
    'Ivo Strand',
    'Mora Fenwick',
    'Varn',
    'Sable',
    'Dorian Silt',
    'Aurel',
    'Castellan',
]
#: The rows of the content packages; without them no level is checked and wings 1 to 6 must be missing
CONTENT = campaign_packages.content_data(ROOT, "campaign_descriptions")
if CONTENT is not None:
    STORY += [tuple(row) for row in CONTENT["story"]]
    BONUS += [tuple(row) for row in CONTENT["bonus"]]
    OLD_WARDENS += CONTENT["old_wardens"]

#: Longest description in characters, so that it stays one readable line.
MAX_LENGTH = 240


def names_of(warden):
    """The full name and the first name of an old warden, as whole-word patterns."""
    parts = warden.split()
    return [re.compile(r"\b%s\b" % re.escape(warden), re.I), re.compile(r"\b%s\b" % re.escape(parts[0]), re.I)]


def description_lines(path):
    """The Description lines inside the [Info] block of a level file. The description is a reference to an English
    text of the language files; the check reads that text."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"\[Info\](.*?)\[/Info\]", text, re.S)
    if match is None:
        return None
    return [campaign_packages.resolve_text(ROOT, line.rstrip("\r")[len("Description\t"):])
            for line in match.group(1).split("\n") if line.startswith("Description\t")]


def main():
    """Checks every description and reports each failure."""
    started = time.monotonic()
    failures = []
    expected = (18, 6, 31) if CONTENT is not None else (0, 0, 15)
    if (len(STORY), len(BONUS), len(OLD_WARDENS)) != expected:
        failures.append("the fixed tables must hold %d story levels, %d bonus levels and %d old wardens" % expected)
    if CONTENT is None and campaign_packages.missing_wings(ROOT) != [1, 2, 3, 4, 5, 6]:
        failures.append("without content packages wings 1 to 6 must be missing")
    if CONTENT is None:
        print("campaign descriptions: content not present, not checked: the descriptions of the campaign levels")
    patterns = [(warden, pattern) for warden in OLD_WARDENS for pattern in names_of(warden)]
    entries = [(name, title, guild) for name, title, guild in STORY] + [(name, title, None) for name, title in BONUS]
    for name, title, guild in entries:
        path = campaign_packages.level_path(ROOT, name)
        relative = os.path.relpath(str(path), ROOT).replace("\\", "/")
        lines = description_lines(str(path))
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
    print("campaign level descriptions: %d raid levels and %d chambers, no old warden: PASS" % (len(STORY), len(BONUS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
