#!/usr/bin/env python3
"""A skill that the map does not allow must not show a cast or build button.

The cast/build button of a room, spell, trap or door is visible only when the seat has
learned it (level above 0). The server refuses everything else
(SkillManager::isRoomAvailable, isSpellAvailable, isTrapAvailable), so a visible button
for a locked skill is a button that does nothing. In a campaign level a room, trap or door
the level allows is also shown before it is learned, but only as a question mark placeholder
that is disabled; a skill the level does not allow stays hidden there too.
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
    check(argument == "isVisible", "the cast button must follow the computed visibility: " + argument)
check(len(re.findall(r"getChild\(castButtonName\)->setVisible\(", text)) == 0,
      "no second visibility rule for the cast button")
# The visibility starts from the learned level and is only widened for an allowed entry of a campaign level,
# which then is a disabled placeholder until it is learned
check(text.count("bool isVisible = level > 0;") == 1, "the cast button must depend on the skill level")
assignments = re.findall(r"isVisible = ([^;]*);", text)
check(sorted(assignments) == ["false", "level > 0", "true"],
      "the visibility is only the learned level, hidden or the placeholder case: " + str(assignments))
check("if(!isAllowed || (isTrapEntry && !mHasWorkshopShown))\n                    isVisible = false;\n"
      "                else\n                {\n                    isVisible = true;\n"
      "                    isPlaceholder = (level == 0);" in text,
      "a locked skill must not show its cast button; an allowed unlearned one is a placeholder")
check("castButton->setEnabled(!isLockedByLibrary && !isPlaceholder);" in text,
      "a placeholder for an unlearned skill cannot be used")

server = (root / "source/network/ODServer.cpp").read_text(encoding="utf-8")
for name in ("isRoomAvailable", "isSpellAvailable", "isTrapAvailable"):
    check(name in server or name in (root / "source/game/SkillManager.cpp").read_text(encoding="utf-8"),
          name + " must exist so the server refuses locked skills")

if failures:
    sys.exit(1)
print("locked skill buttons: ok")
