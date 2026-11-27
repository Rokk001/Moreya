#!/usr/bin/env python3
"""Non-compiling check of the simulated raid values (raid plan R3C, V1, SIM1, RA2, RA11, HL1).

No config key of [GroupCombat], [Raid] and [HandLimit] in config/global.cfg is marked PLACEHOLDER and their
documentation does not name a placeholder at all (every value is final: simulated or decided by the owner), no story level
keeps a PLACEHOLDER line in its [Raid] section, every key of those blocks that the simulation sets has the fixed value of
the third simulation pass, every story level sets its countdown inside 1800-3600 game seconds (raid plan R13: wing 1
one value each for Normal, Hard and Hell, Hard and Hell never above Normal; all 3600 by the owner decision Frage 44 of
2026-11-21 until the owner has played the maps), and the countdown,
interval and escape share of every story level, the member levels of its raid and the number of its healers (Wizards
with the Healer template) have the fixed values of the third simulation pass. All expected values are fixed here
(counted once on feature/raid-campaign-r3c); nothing is derived from the files under test.

Usage: python -I source/tests/check_raid_simulation_values.py
Exit 0 and "raid simulation values ok" when every item holds.
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

# Keys set by the simulation and their values after R3C
CONFIG = {
    "GroupCombat": {"GroupFormingDistance": "20", "GroupDissolveDistance": "24", "GroupRetreatHealthShare": "0.5",
                    "GroupRetreatMaxSeconds": "30", "GroupRetreatCooldownSeconds": "30", "GroupGatherRadius": "3",
                    "GroupAggroMemorySeconds": "3", "GroupFormationRowSpacing": "1", "GroupFormationRowWidth": "6",
                    "GroupFormationTolerance": "2"},
    "Raid": {"RaidCountdownSeconds": "3600", "RaidPlunderDetourTiles": "6", "RaidWaveIntervalSeconds": "90", "RaidLeaderEscapeShare": "0.25"},
    "HandLimit": {"HandLimitCooldownSeconds": "60"},
}


def levels(*pairs):
    """The sorted member levels of a raid from (level, count) pairs."""
    result = []
    for index in range(0, len(pairs), 2):
        result.extend([pairs[index]] * pairs[index + 1])
    return result


# Story level: (Countdown values as written: Normal, Hard, Hell or one value for all three, Interval or "-",
# EscapeShare or "-", sorted member levels, healers). R13: wing 1 writes one countdown per campaign difficulty; all are
# 3600 by the owner decision of 2026-11-21 (Frage 44: no measured values, every wing 1 map keeps 3600 s on Normal, Hard
# and Hell until the owner has played it). The levels of wings 2-6 keep their single 3600 (R13 scope: wing 1 only).
LEVELS = {
    "Brackenford": (("3600", "3600", "3600"), "-", "-", levels(4, 4, 5, 1), 0),
    "Coldwell": (("3600", "3600", "3600"), "-", "-", levels(4, 4, 6, 1), 0),
    "Ravensledge": (("3600", "3600", "3600"), "-", "-", levels(2, 9, 3, 1), 0),
    "Tinmoor": ("3600", "60", "-", levels(2, 8, 3, 1, 4, 1), 0),
    "Greywater": ("3600", "90", "-", levels(2, 8, 3, 1, 4, 1), 0),
    "Highcairn": ("3600", "150", "-", levels(3, 10, 4, 9, 6, 1), 0),
    "Lanternhill": ("3600", "-", "0.5", levels(3, 9, 5, 1), 0),
    "Saltmere": ("3600", "-", "-", levels(3, 9, 5, 1), 0),
    "HollinFen": ("3600", "-", "-", levels(4, 24, 6, 1), 8),
    "Cinderhollow": ("3600", "60", "-", levels(3, 19, 5, 1), 0),
    "Ashcombe": ("3600", "120", "-", levels(4, 19, 6, 1), 0),
    "Ironbridge": ("3600", "60", "-", levels(4, 49, 7, 1), 0),
    "Bellwick": ("3600", "-", "-", levels(5, 24, 6, 1), 1),
    "Goldspire": ("3600", "-", "-", levels(6, 24, 8, 1), 1),
    "Kingsfall": ("3600", "-", "-", levels(5, 39, 8, 1), 1),
    # VarnsCrossing: 1 healer per group, measured again in FINAL (R3C gave all 3 to the second group)
    "VarnsCrossing": ("3600", "180", "-", levels(7, 49, 9, 1), 2),
    "Wraithwood": ("3600", "90", "-", levels(4, 49, 6, 1), 6),
    "HollowmarkCitadel": ("3600", "180", "-", levels(6, 78, 8, 1, 10, 1), 6),
}


# RA11 levels whose guild needs healers: every raid group of them has at least one healer (rule of R3C.2)
HEALER_EVERY_GROUP = ("Bellwick", "Goldspire", "Kingsfall", "VarnsCrossing", "HollowmarkCitadel")


def check(condition, message):
    """Records the message as a failure when the condition does not hold."""
    if not condition:
        FAILURES.append(message)


def read(relative):
    """Returns the text of a file of the repository with Unix line ends; a mixed table comes with its own rows of the
    content (scripts/content_packages.py)."""
    return content_packages.read_text(ROOT, relative).replace("\r\n", "\n")


def block(text, name):
    """The documentation lines before the [name] block and its key -> first word."""
    start = text.index("[%s]\n" % name)
    end = text.index("[/%s]" % name, start)
    previous = text.rfind("[/", 0, start)
    documentation = text[text.index("\n", previous) + 1:start]
    values = {}
    for line in text[start:end].split("\n")[1:]:
        words = line.split()
        if words:
            values[words[0]] = words[1] if len(words) > 1 else ""
    return documentation, values


def main():
    """Runs every item of the check and prints the result."""
    # The [GroupCombat], [Raid] and [HandLimit] blocks are own rows of config/global.cfg (content package core-config)
    if content_packages.has_content(ROOT):
        cfg = read("config/global.cfg")
        for name, expected in sorted(CONFIG.items()):
            documentation, values = block(cfg, name)
            marked = re.findall(r"(?m)^#\s+(\w+)\s.*PLACEHOLDER:", documentation)
            check(not marked, "V1: [%s] keys still marked PLACEHOLDER: %s" % (name, marked))
            check("PLACEHOLDER" not in documentation, "V1: the documentation of [%s] still names a placeholder" % name)
            for key, value in sorted(expected.items()):
                check(values.get(key) == value, "SIM1: [%s] %s must be %s, is %s" % (name, key, value, values.get(key)))
    else:
        content_packages.unchecked("check_raid_simulation_values",
                                   ["V1/SIM1 keys of [GroupCombat], [Raid] and [HandLimit] (own rows of config/global.cfg)"])
    # The levels of the wing packages present: all 18 story levels with the content repository, else wing 1
    for name in campaign_packages.checked_names(ROOT, sorted(LEVELS)):
        countdown, interval, escape, levels, healers = LEVELS[name]
        text = campaign_packages.read_level(ROOT, name).replace("\r\n", "\n")
        raid = re.search(r"(?ms)^\[Raid\]$(.*?)^\[/Raid\]$", text).group(1)
        check("PLACEHOLDER" not in raid, name + ": the [Raid] section keeps a PLACEHOLDER line")
        rows = [line.split("\t") for line in raid.split("\n") if line and not line.startswith("#")]
        values = dict((row[0], row[1]) for row in rows if row[0] in ("Interval", "EscapeShare"))
        written = tuple(next((row[1:] for row in rows if row[0] == "Countdown"), ()))
        expected = countdown if isinstance(countdown, tuple) else (countdown,)
        check(written == expected, name + ": countdown (RA2) must be %s, is %s" % (expected, written))
        check(len(written) in (1, 3) and all(1800 <= int(value) <= 3600 for value in written),
              name + ": every countdown inside 1800-3600 s (RA2)")
        if len(written) == 3:
            # RA2 wants Hard and Hell below Normal; suspended by the owner decision of 2026-11-21 (Frage 44): until the
            # owner has played the map, Normal, Hard and Hell are equal (3600). Never above Normal.
            check(int(written[1]) <= int(written[0]) and int(written[2]) <= int(written[0]),
                  name + ": Hard and Hell not above Normal (RA2, Frage 44)")
        check(values.get("Interval") == interval, name + ": interval")
        check(values.get("EscapeShare") == escape, name + ": escape share")
        members = [row for row in rows if row[0] == "Member"]
        check(sorted(int(row[3]) for row in members) == levels, name + ": member levels (SIM1)")
        check(sum(1 for row in members if row[2] == "Wizard" and row[5] == "Healer") == healers,
              name + ": healers (RA11)")
        if name in HEALER_EVERY_GROUP:
            groups = sorted(set(row[1] for row in rows if row[0] == "Group"))
            without = [group for group in groups
                       if not any(row[1] == group and row[2] == "Wizard" and row[5] == "Healer" for row in members)]
            check(not without, name + ": every raid group has a healer (RA11), not groups %s" % without)
    check(len(LEVELS) == 18, "SIM1: the values of all 18 story levels are fixed here")
    print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % (time.perf_counter() - START))
    for failure in FAILURES:
        print("FAIL " + failure)
    if FAILURES:
        return 1
    print("raid simulation values ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
