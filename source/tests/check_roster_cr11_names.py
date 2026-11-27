#!/usr/bin/env python3
"""Acceptance check CR11 (names) of the creature roster plan, config part.

The shown class name of config/social-texts.cfg (ClassName lines, read by SocialGenerator::displayClassName for the
Dungeonbook, the social feed and the hover texts) is the English display name of D15 for each of the 36 creatures:
Dwarf2 is shown as Dwarf Warrior, the Champion as Shadow Lord, the Kobold as Ziv; a removed class has no ClassName
line. The skills of config/creatureSkills.cfg carry the approved names of section 5c (D36) per group, path and tier,
and the new families their path and skill names. The template names are asserted by check_roster_cr4_groups.py and
the tier 4 names by check_roster_cr5_cr8_skills.py; that no player text calls the Ziv a worker is asserted by
check_start_screen_signpost_zivs.py. A look at the names in the running game (GUI) needs the integration build.

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr11_names.py
Exit 0 and "roster CR11 ok" when every item holds.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

SKILLS, _TIER_FOURS, _TEMPLATES = plan.parse_skill_config(plan.read("config/creatureSkills.cfg"))

# ------------------------------------------------------------------------------------------ class names
shown = {}
for line in plan.read("config/social-texts.cfg").splitlines():
    cells = line.split("\t")
    if len(cells) >= 3 and cells[0] == "ClassName":
        check(cells[1] not in shown, "CR11: one ClassName line for " + cells[1])
        shown[cells[1]] = cells[2].strip()
for name, row in sorted(plan.ROSTER.items()):
    check(shown.get(name) == row[4], "CR11 D15: %s is shown as %s (config %s)" % (name, row[4], shown.get(name)))
check(sorted(shown) == sorted(plan.ROSTER), "CR11: ClassName lines for exactly the 36 creatures; extra %s"
      % sorted(set(shown) - set(plan.ROSTER)))
for removed in plan.REMOVED:
    check(removed not in shown, "CR11: the removed %s has no shown name" % removed)

# ------------------------------------------------------------------------------------------- skill names
for group, paths in sorted(plan.PATHS.items()):
    for path, names in paths:
        for tier, expected in enumerate(names, 1):
            got = [entry.get("Name") for entry in SKILLS if entry.get("Group") == group and
                   entry.get("Path") == path and entry.get("Tier") == str(tier)]
            check(got == [expected], "CR11 D36: tier %d of %s (%s) is named %s (config %s)"
                  % (tier, path, group, expected, got))
for family, (path, names, _members) in sorted(plan.FAMILIES.items()):
    entries = [entry for entry in SKILLS if entry.get("Family") == family]
    check(entries and all(entry.get("Path") == path for entry in entries),
          "CR11 D36: the path of family %s is named %s (config %s)"
          % (family, path, sorted(set(entry.get("Path") for entry in entries))))
    if names is None:
        continue
    for tier, expected in enumerate(names, 1):
        got = [entry.get("Name") for entry in entries if entry.get("Tier") == str(tier)]
        check(got == [expected], "CR11 D36: tier %d of family %s is named %s (config %s)"
              % (tier, family, expected, got))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr11","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR11 ok")
