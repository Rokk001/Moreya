"""Static checks that the campaign has no branches any more (formerly T09A/T09B and T18A/T18B).

The campaign is one straight sequence of 18 story levels in 6 wings: every story level
needs all story levels before it, no level is an optional sister of another, and the
former branch maps Mirewatch and Dunmarrow are no longer listed. Run from any directory.
It does not start a game.
"""
from pathlib import Path
import json
import re
import sys

root = Path(__file__).resolve().parents[2]
campaign_cpp = (root / "source/game/Campaign.cpp").read_text(encoding="utf-8")
campaign_h = (root / "source/game/Campaign.h").read_text(encoding="utf-8")
mode = (root / "source/modes/MenuModeCampaign.cpp").read_text(encoding="utf-8")
definition = (root / "levels/campaign/Campaign.cfg").read_text(encoding="utf-8").replace("\r", "")
world = json.loads((root / "gui/campaign/campaign-world.json").read_text(encoding="utf-8"))
failures = []


def check(condition, message):
    """Collects a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


entries = []
for block in definition.split("[Level]")[1:]:
    fields = dict(re.findall(r"^(\w+)=(.*)$", block, re.M))
    entries.append(fields)
files = [f.get("File", "") for f in entries]

# No level names a branch sister or a province any more
check(not any("Branch" in f for f in entries), "no level may have a Branch setting")
check(not any("Province" in f for f in entries), "no level may have a Province setting")
check(not re.search(r"^Branch=", definition, re.M), "Campaign.cfg must not have Branch settings")
# Both maps of each former branch pair: one is a story level, the other is dropped
for kept, dropped in (("campaign/Saltmere.level", "campaign/Dunmarrow.level"),
                      ("campaign/Goldspire.level", "campaign/Mirewatch.level")):
    check(kept in files, kept + " must stay a story level")
    check(dropped not in files, dropped + " must be dropped from the campaign")
    if kept in files:
        check("Bonus" not in entries[files.index(kept)], kept + " must not be a bonus level")

# The loader no longer reads Branch and the progression has no sister rule
check('key == "Branch"' not in campaign_cpp, "the reader must not know Branch any more")
check("findBranchSisterNoLock" not in campaign_cpp and "findBranchSisterNoLock" not in campaign_h,
      "the branch sister lookup must be gone")
check("mBranch" not in campaign_cpp and "mBranch" not in campaign_h, "levels must not carry a branch sister")
unlocked = campaign_cpp[campaign_cpp.index("bool Campaign::isUnlockedNoLock"):campaign_cpp.index("bool Campaign::isUnlocked(")]
check("if(mCompleted[i] || mLevels[i].mBonus)" in unlocked and "ownSister" not in unlocked,
      "every story level before a story level must be completed")
current = campaign_cpp[campaign_cpp.index("size_t Campaign::getCurrentLevelNoLock"):campaign_cpp.index("size_t Campaign::getCurrentLevel()")]
check("if(!mCompleted[i] && !mLevels[i].mBonus)" in current and "sister" not in current,
      "the current level must be the first story level not completed")

# The map of Moreya has replaced the old world map: one straight line of 18 level caves in 6 wings, the story levels
# of the definition in their order, and its progress counts each defeated story level of the 18
story = [level["file"] for wing in world["wings"] for level in wing["levels"]]
check("provinces" not in world, "the world map must not list provinces any more")
check(len(story) == 18, "the map of Moreya must list 18 level caves")
check(story == [f for f, entry in zip(files, entries) if f and "Bonus" not in entry],
      "the level caves must follow the story levels of Campaign.cfg without a branch")
check("mCaveStates[i] == CampaignCaveState::defeated" in mode and "++levelsDefeated;" in mode,
      "progress must count each defeated story level")
check("++levelTotal;" in mode and "levelsDefeated * PERCENT_FULL / levelTotal" in mode,
      "progress total must be the number of level caves")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign branch checks passed")
