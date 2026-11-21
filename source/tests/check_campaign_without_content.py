"""The game runs without the private content packages: wing 1 is playable, wings 2 to 6 are locked.

The public tree must work completely on its own (scripts/campaign_packages.py). Static part, always:
  * without content the packages are exactly the public package of wing 1 (4 levels, fixed for this branch) and wings
    2 to 6 are missing; every entry names its level as campaign/<file name> and the file lies in the package folder;
  * the game reads the campaign only through the package loader (no hard-coded campaign definition path), keeps the
    campaign name of a level for progress, saves and level scripts, locks every wing after a missing one, never
    finishes the campaign (end message, finished difficulties, Hell) while a wing is missing, keeps the Heartstone at
    its 3 shards and writes the progress of missing wings again (Boost case test_wing_packages);
  * the protected-content allow list names the files of the public package exactly.
Runtime part, when the built game build/windows/moreya.exe exists: the last story level of wing 1 is played with the
load test (MOREYA_CONTENT_DIR empty, so no content package is found); the run must pass and the campaign map must show
the next wing locked ("Coming in Early Access").

Usage: python source/tests/check_campaign_without_content.py
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import campaign_packages  # noqa: E402

#: The public package, counted once for this branch
PUBLIC_FOLDER = ROOT / "levels/campaign/wing1"
PUBLIC_FILES = ("Package.cfg", "LICENSE.txt", "Brackenford.level", "Coldwell.level", "Ravensledge.level",
                "Mossgate.level")
#: The last story level of wing 1: its win leads to the map with wing 2
LAST_PUBLIC_STORY_LEVEL = "levels/campaign/wing1/Ravensledge.level"
EXECUTABLE = ROOT / "build/windows/moreya.exe"
#: Game seconds of the runtime probe (the load test minimum)
PROBE_SECONDS = 1
#: Wall-clock limit of the runtime probe in seconds (the load test's own limit is 2 * seconds + 400)
PROBE_TIMEOUT = 420

failures = []


def check(condition, message):
    """Records a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(relative):
    """A file of the repository as text."""
    return (ROOT / relative).read_text(encoding="utf-8")


def body(source, signature):
    """A complete brace-delimited function starting at its signature."""
    start = source.index(signature)
    depth = 0
    for index in range(source.index("{", start), len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start:index + 1]
    return source[start:]


started = time.monotonic()
# The public tree alone: wing 1 only, wings 2 to 6 missing
os.environ[campaign_packages.CONTENT_VARIABLE] = ""
check(campaign_packages.content_folder(ROOT) is None, "an empty MOREYA_CONTENT_DIR must mean: no content")
entries = campaign_packages.entries(ROOT)
check([Path(entry["File"]).stem for entry in entries] == list(campaign_packages.PUBLIC_LEVELS),
      "without content the campaign must be exactly the levels of wing 1 in order")
check(campaign_packages.missing_wings(ROOT) == [2, 3, 4, 5, 6], "without content wings 2 to 6 must be missing")
check(sorted(path.name for path in PUBLIC_FOLDER.iterdir()) == sorted(PUBLIC_FILES),
      "the wing 1 package must hold exactly " + ", ".join(PUBLIC_FILES))
for entry in entries:
    check(re.fullmatch(r"campaign/\w+\.level", entry["File"]) is not None,
          entry["File"] + ": the campaign name of a level stays campaign/<file name>")
    check(entry["_path"].is_file() and entry["_path"].parent == PUBLIC_FOLDER, entry["File"] + " must lie in wing1/")
    for target in re.findall(r"^Action\tdiscover\t(\S+)", entry["_path"].read_text(encoding="utf-8"), re.M):
        check(target in [other["File"] for other in entries if other.get("Bonus") == "1"],
              entry["File"] + ": the hidden stone must name the bonus level by its campaign name, not " + target)

# The game reads the campaign only through the package loader
sources = [path for path in (ROOT / "source").rglob("*") if path.suffix in (".cpp", ".h") and "tests" not in path.parts]
for path in sources:
    check("Campaign.cfg\"" not in path.read_text(encoding="utf-8", errors="replace"),
          "%s still opens a fixed campaign definition" % path.relative_to(ROOT))
for relative, signature in (("source/modes/MenuModeCampaign.cpp", "bool MenuModeCampaign::loadCampaign("),
                            ("source/gamemap/MapHandler.cpp", "bool loadCampaignProgress(")):
    check("CampaignPackages::loadCampaign(" in body(read(relative), signature),
          relative + " must read the campaign with the package loader")
packages_cpp = read("source/game/CampaignPackages.cpp")
check('MISSING_WING_TEXT = "%s"' % campaign_packages.MISSING_WING_TEXT in packages_cpp
      and 'CONTENT_VARIABLE = "%s"' % campaign_packages.CONTENT_VARIABLE in packages_cpp
      and 'GAME_PACKAGE_FOLDER = "levels/campaign/"' in packages_cpp, "the game must name packages as the checks do")
level_test = body(read("source/utils/RunLevelTest.cpp"), "void RunLevelTest::prepareCampaignLevel(")
check("CampaignPackages::getLevelFile(" in level_test and "boost::filesystem::equivalent(" in level_test,
      "the load test must find the campaign level by its package file, not by <folder>/<file>")

# Missing wings: locked later wings, no early end, Heartstone total, kept progress
campaign = read("source/game/Campaign.cpp")
check("*mMissingWings.begin() < mLevels[index].mWing" in body(campaign, "bool Campaign::isUnlockedNoLock(")
      and "*mMissingWings.begin() < mLevels[i].mWing" in body(campaign, "size_t Campaign::getCurrentLevelNoLock("),
      "a missing wing must lock every later wing")
check("mMissingWings.empty()" in body(campaign, "bool Campaign::isCampaignCompleteNoLock(")
      and "isCampaignCompleteNoLock()" in body(campaign, "bool Campaign::isFinished(")
      and "isCampaignCompleteNoLock()" in body(campaign, "bool Campaign::isPlayedLevelCampaignEnd(")
      and "if(isCampaignCompleteNoLock())" in body(campaign, "bool Campaign::completePlayedLevel("),
      "the end message, the finished difficulties and Hell must wait for every wing")
check("HEARTSTONE_SHARDS" in body(campaign, "size_t Campaign::getHeartstoneTotalNoLock("),
      "the Heartstone total must not shrink while a wing is missing")
for keyword in ("Completed", "Discovered", "Shards"):
    check('writeOtherProgressNoLock(os, "%s");' % keyword in body(campaign, "void Campaign::exportProgress("),
          "the progress of missing wings must be written again: " + keyword)
tests = read("source/tests/test_Campaign.cpp")
check(re.search(r"//! \\brief [^\n]+\n(?://![^\n]*\n)*BOOST_AUTO_TEST_CASE\(test_wing_packages\)", tests) is not None,
      "test_Campaign.cpp must have the commented Boost case test_wing_packages")

# The protected-content allow list names the public package exactly
guard = read("scripts/check-protected-content.py")
allowed = set(re.findall(r'"(levels/campaign/[^"]+)"', guard[guard.index("CAMPAIGN_ALLOW_LIST = ["):
                                                             guard.index("]", guard.index("CAMPAIGN_ALLOW_LIST = ["))]))
tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files", "levels/campaign"], capture_output=True, text=True,
                             check=True).stdout.split())
check(tracked <= allowed, "tracked campaign files missing in the allow list: %s" % sorted(tracked - allowed))
check({"levels/campaign/wing1/" + name for name in PUBLIC_FILES} <= allowed,
      "the allow list must name every file of the public package")
check(not any(name.startswith("levels/campaign/wing") and not name.startswith("levels/campaign/wing1/")
              for name in allowed), "the allow list must not allow a private package in the public tree")
print('ODP_TEST_PHASE ' + json.dumps({"name": "static", "seconds": round(time.monotonic() - started, 3)}))

# Runtime: the game without content packages plays wing 1 and shows wing 2 locked
runtime = "not run: the built game %s is missing" % EXECUTABLE.relative_to(ROOT)
if EXECUTABLE.is_file() and not failures:
    started = time.monotonic()
    environment = dict(os.environ)
    environment[campaign_packages.CONTENT_VARIABLE] = ""
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run-level-test.py"), "--exe", str(EXECUTABLE),
                             "--seconds", str(PROBE_SECONDS), "--menu-seconds", "0", str(ROOT / LAST_PUBLIC_STORY_LEVEL)],
                            cwd=str(ROOT), env=environment, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=PROBE_TIMEOUT, stdin=subprocess.DEVNULL)
    print('ODP_TEST_PHASE ' + json.dumps({"name": "runtime", "seconds": round(time.monotonic() - started, 3)}))
    output = result.stdout + result.stderr
    expected = "campaign map shows the next wing locked (%s)" % campaign_packages.MISSING_WING_TEXT
    check(result.returncode == 0 and expected in output,
          "the game without content packages must pass Ravensledge and show wing 2 locked:\n"
          + "\n".join(output.splitlines()[-12:]))
    runtime = "Ravensledge passed without content packages, next wing shown locked (%s)" % (
        campaign_packages.MISSING_WING_TEXT)

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign without content: wing 1 only (4 levels), wings 2 to 6 locked; " + runtime + ": PASS")
