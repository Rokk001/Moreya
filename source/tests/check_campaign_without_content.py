"""Without the private content packages the game does not play: it says that the content is missing and quits.

The public tree holds no wing (scripts/campaign_packages.py: PUBLIC_LEVELS is empty); every wing, wing 1 included,
comes with the content packages. Static part, always:
  * without content the public tree has no campaign package and no campaign level, and wings 1 to 6 are missing; no
    package folder levels/campaign/wing* is left in the public tree;
  * with the content present the wing 1 package of the content holds exactly its 6 files (4 levels, fixed for this
    branch), every entry names its level as campaign/<file name>, the file lies in the package folder and the hidden
    stone names the bonus level by its campaign name; without content this part is named as not checked;
  * the game quits with exit code 7 (the same value as scripts/content_packages.py) and the missing content message
    when content packages are missing, also in a headless load test run;
  * the game reads the campaign only through the package loader (no hard-coded campaign definition path), keeps the
    campaign name of a level for progress, saves and level scripts, locks every wing after a missing one, never
    finishes the campaign (end message, finished difficulties, Hell) while a wing is missing, keeps the Heartstone at
    its 3 shards and writes the progress of missing wings again (Boost case test_wing_packages);
  * the protected-content allow list covers every tracked file of levels/campaign/ and allows no wing package
    other than wing 1; no wing file is tracked in the public tree at all.
Runtime part, when the built game build/windows/moreya.exe exists (this check never builds it): the game is started
with the load test parameters (--run-level with a public test level, 1 second) without MOREYA_CONTENT_DIR, so no
content package is found; it must quit with exit code 7 and print "The content of Moreya is missing" on its error
output, without playing the level. Without the built game the runtime part is named as not checked.

Usage: python source/tests/check_campaign_without_content.py
"""
import json
import os
import shutil
import socket
import tempfile
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

#: The files of the wing 1 package (now a content package), counted once for this branch
WING1_FILES = ("Package.cfg", "LICENSE.txt", "Brackenford.level", "Coldwell.level", "Ravensledge.level",
               "Mossgate.level")
#: The levels of wing 1 in campaign order, counted once for this branch
WING1_LEVELS = ["Brackenford", "Coldwell", "Ravensledge", "Mossgate"]
#: A public test level of the runtime probe; the game must quit before it plays it
PROBE_LEVEL = "levels/skirmish/TestCleaning.level"
EXECUTABLE = ROOT / "build/windows/moreya.exe"
#: Game seconds of the runtime probe (the load test minimum)
PROBE_SECONDS = 1
#: Wall-clock limit of the runtime probe in seconds (the load test's own limit is 2 * seconds + 400)
PROBE_TIMEOUT = 420
#: Exit code and error text of the game without content packages (source/utils/ContentPackages.*), fixed values
MISSING_CONTENT_EXIT_CODE = 7
MISSING_CONTENT_TEXT = "The content of Moreya is missing"

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
# The wing 1 package of the content, read before the content is switched off below
content_present = content_packages.has_content(ROOT)
wing1 = [entry for entry in campaign_packages.entries(ROOT) if entry.get("Wing") == "1" and not entry["_public"]]
# The public tree alone: no wing, wings 1 to 6 missing
os.environ[campaign_packages.CONTENT_VARIABLE] = ""
check(campaign_packages.content_folder(ROOT) is None, "an empty MOREYA_CONTENT_DIR must mean: no content")
entries = campaign_packages.entries(ROOT)
check([Path(entry["File"]).stem for entry in entries] == list(campaign_packages.PUBLIC_LEVELS) == [],
      "without content the public tree must have no campaign level")
check(campaign_packages.packages(ROOT) == [], "the public tree must hold no wing package")
check(not any(path.name.startswith("wing") for path in (ROOT / campaign_packages.PUBLIC_FOLDER).iterdir()),
      "no wing folder may be left in levels/campaign/ of the public tree")
check(campaign_packages.missing_wings(ROOT) == [1, 2, 3, 4, 5, 6], "without content wings 1 to 6 must be missing")
if wing1:
    folder = wing1[0]["_package"]
    check(sorted(path.name for path in folder.iterdir() if path.is_file()) == sorted(WING1_FILES),
          "the wing 1 package must hold exactly " + ", ".join(WING1_FILES))
    check([Path(entry["File"]).stem for entry in wing1] == WING1_LEVELS, "wing 1 must be its 4 levels in order")
    for entry in wing1:
        check(re.fullmatch(r"campaign/\w+\.level", entry["File"]) is not None,
              entry["File"] + ": the campaign name of a level stays campaign/<file name>")
        check(entry["_path"].is_file() and entry["_path"].parent == folder, entry["File"] + " must lie in wing1/")
        for target in re.findall(r"^Action\tdiscover\t(\S+)", entry["_path"].read_text(encoding="utf-8"), re.M):
            check(target in [other["File"] for other in wing1 if other.get("Bonus") == "1"],
                  entry["File"] + ": the hidden stone must name the bonus level by its campaign name, not " + target)
else:
    check(not content_present, "the wing 1 package is missing although the content is present")
    content_packages.unchecked("campaign without content", ["the files and levels of the wing 1 package"])

# Without content packages the game quits with the missing content message and exit code 7
check(content_packages.MISSING_CONTENT_EXIT_CODE == MISSING_CONTENT_EXIT_CODE
      and "const int MISSING_CONTENT_EXIT_CODE = %d;" % MISSING_CONTENT_EXIT_CODE
      in read("source/utils/ContentPackages.h"), "the missing content exit code must be %d" % MISSING_CONTENT_EXIT_CODE)
check('"' + MISSING_CONTENT_TEXT in read("source/utils/ContentPackages.cpp"),
      "the missing content message must start with: " + MISSING_CONTENT_TEXT)
main_cpp = read("source/main.cpp")
refused = main_cpp[main_cpp.index("if(ContentPackages::isStartRefused())"):]
refused = refused[:refused.index("return ContentPackages::MISSING_CONTENT_EXIT_CODE;") + 1]
check("std::cerr << message" in refused and 'options.count("run-level")' in refused,
      "main.cpp must print the missing content message and quit with its exit code, also in a load test run")

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
check('Translation::tr("campaign.code.missing_wing")' in packages_cpp
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

# The protected-content allow list covers the tracked campaign files; no wing package is tracked
guard = read("scripts/check-protected-content.py")
allowed = set(re.findall(r'"(levels/campaign/[^"]+)"', guard[guard.index("CAMPAIGN_ALLOW_LIST = ["):
                                                             guard.index("]", guard.index("CAMPAIGN_ALLOW_LIST = ["))]))
# Tracked files that are still in the working tree (a file moved out of the tree but not committed yet is gone)
tracked = set(name for name in subprocess.run(["git", "-C", str(ROOT), "ls-files", "levels/campaign"],
                                              capture_output=True, text=True, check=True).stdout.split()
              if (ROOT / name).is_file())
check(tracked <= allowed, "tracked campaign files missing in the allow list: %s" % sorted(tracked - allowed))
check(not any(name.startswith("levels/campaign/wing") for name in tracked),
      "the public tree must not track a wing package: %s" % sorted(name for name in tracked
                                                                 if name.startswith("levels/campaign/wing")))
check(not any(name.startswith("levels/campaign/wing") and not name.startswith("levels/campaign/wing1/")
              for name in allowed), "the allow list must not allow a private package in the public tree")
print('ODP_TEST_PHASE ' + json.dumps({"name": "static", "seconds": round(time.monotonic() - started, 3)}))

# Runtime: the game without content packages says that the content is missing and quits with exit code 7
runtime = "runtime not checked: the built game %s is missing" % EXECUTABLE.relative_to(ROOT)
if EXECUTABLE.is_file() and not failures:
    started = time.monotonic()
    environment = dict(os.environ)
    environment.pop(campaign_packages.CONTENT_VARIABLE, None)
    app_data = tempfile.mkdtemp(prefix="od-no-content-")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    try:
        result = subprocess.run([str(EXECUTABLE), "--run-level", str(ROOT / PROBE_LEVEL), "--seconds",
                                 str(PROBE_SECONDS), "--appData", app_data, "--port", str(port)],
                                cwd=str(EXECUTABLE.parent), env=environment, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT, stdin=subprocess.DEVNULL)
    finally:
        shutil.rmtree(app_data, ignore_errors=True)
    print('ODP_TEST_PHASE ' + json.dumps({"name": "runtime", "seconds": round(time.monotonic() - started, 3)}))
    output = result.stdout + result.stderr
    check(result.returncode == MISSING_CONTENT_EXIT_CODE and MISSING_CONTENT_TEXT in result.stderr
          and "PASS " not in output,
          "the game without content packages must quit with exit code %d and the missing content message "
          "(exit code %d):\n" % (MISSING_CONTENT_EXIT_CODE, result.returncode) + "\n".join(output.splitlines()[-12:]))
    runtime = "the game without content packages quits with exit code %d and the missing content message" % (
        MISSING_CONTENT_EXIT_CODE)

if failures:
    print("\n".join(failures).encode("ascii", "replace").decode("ascii"))
    sys.exit(1)
if not EXECUTABLE.is_file():
    content_packages.unchecked("campaign without content", ["runtime (built game missing)"])
print("campaign without content: no public wing, wings 1 to 6 missing; " + runtime + ": PASS")
