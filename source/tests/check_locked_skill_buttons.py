#!/usr/bin/env python3
"""A skill that the map does not allow must not show a cast or build button.

The cast/build button of a room, spell, trap or door is visible only when the seat has
learned it (level above 0). The server refuses everything else
(SkillManager::isRoomAvailable, isSpellAvailable, isTrapAvailable), so a visible button
for a locked skill is a button that does nothing. In a campaign level the navigation also
shows only learned entries that the level allows, traps and doors only with a built Workshop;
the padlock and the question mark appear in the research window alone, never in the navigation.
"""

import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
text = (root / "source/modes/GameMode.cpp").read_text(encoding="utf-8")

failures = 0


def check(condition, message):
    global failures
    if not condition:
        failures += 1
        print("FAIL: " + message)


calls = re.findall(r"castButton->setVisible\(([^;]*)\);", text)
check(len(calls) == 1, "expected exactly one setVisible call for the cast button, found %d" % len(calls))
for argument in calls:
    # The computed visibility, and a skill whose room package is missing keeps its build button hidden in every mode
    check(argument == "isVisible && isContentAvailable",
          "the cast button must follow the computed visibility and the content package: " + argument)
check(len(re.findall(r"getChild\(castButtonName\)->setVisible\(", text)) == 0,
      "no second visibility rule for the cast button")
# The visibility starts from the learned level; a campaign level shows only learned and allowed entries
check(text.count("bool isVisible = level > 0;") == 1, "the cast button must depend on the skill level")
assignments = re.findall(r"isVisible = ([^;]*);", text)
check(sorted(assignments) == ["isAllowed && (level > 0) && !(isTrapEntry && !mHasWorkshopShown)", "level > 0"],
      "the visibility is the learned level, in a campaign level also allowed and a Workshop for traps: " + str(assignments))
check('castButton->setProperty(NAVIGATION_MARK_PROPERTY, "");' in text and
      'castButton->setUserString(NAVIGATION_LOCKED, "false");' in text and
      'castButton->setProperty("NormalImage", castButton->getUserString(NAVIGATION_REAL_IMAGE));' in text,
      "the navigation never carries a padlock or a question mark")
check("castButton->setEnabled(!isLockedByLibrary);" in text, "the library lock stays on the cast button")
server = (root / "source/network/ODServer.cpp").read_text(encoding="utf-8")
for name in ("isRoomAvailable", "isSpellAvailable", "isTrapAvailable"):
    check(name in server or name in (root / "source/game/SkillManager.cpp").read_text(encoding="utf-8"),
          name + " must exist so the server refuses locked skills")

if failures:
    sys.exit(1)
print("locked skill buttons: ok")
