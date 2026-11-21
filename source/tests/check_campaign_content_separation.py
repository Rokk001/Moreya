"""Code and paid campaign content never share a file; never starts a game.

The campaign is split into wing packages (scripts/campaign_packages.py): wing 1 lies in the public tree
(levels/campaign/wing1/ with its own licence file), wings 2 to 6 come from the private content repository. Paid content
is the content of the private packages: their level files and the in-game texts of their Package.cfg (titles, briefings,
debriefings, wardens, guild names and leaders) and of their level scripts (messages, hints and objective texts).

Checked rules, with fixed expectations of this branch:
  * a package folder holds only content: Package.cfg, level files and its licence or readme text; never code;
  * the public tree has exactly the fixed public package (wing 1: 4 levels) and no package or entry of another wing;
  * the content repository holds no code file (packages, documents and check data only);
  * with the content repository present, no tracked file of the public tree outside the package folders carries an
    in-game text of a private package (texts that the public game data also ships, e.g. wing 1, the map or a skirmish
    level, are public).
"""
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import campaign_packages  # noqa: E402

#: The public package: folder and its level files, counted once for this branch
PUBLIC_PACKAGE = "levels/campaign/wing1"
PUBLIC_WING = 1
PUBLIC_LEVEL_COUNT = 4
#: Files a package folder may hold besides its level files
PACKAGE_TEXT_FILES = {"Package.cfg", "LICENSE.txt", "LICENSE", "README.md"}
#: Extensions of code files; none of them belongs in a package or in the content repository
CODE_EXTENSIONS = {".py", ".cpp", ".h", ".hpp", ".c", ".cmake", ".ps1", ".sh", ".bat", ".cmd", ".js", ".lua",
                   ".pyw", ".mjs", ".ts"}
#: Code file names without an extension
CODE_NAMES = {"CMakeLists.txt", "Makefile"}
#: Shortest sentence of a briefing, debriefing or script message that counts as a paid text
MIN_SENTENCE = 25
#: Keys of Package.cfg whose whole value is a paid in-game name
NAME_KEYS = ("Title", "Warden", "Guild", "GuildLeader", "GuildFirstLeader")
#: Keys of Package.cfg whose sentences are paid in-game texts
TEXT_KEYS = ("Briefing", "Debriefing")
#: Folders of the public game data; a text the public game ships there is public
PUBLIC_GAME_DATA = ("config/", "gui/", "levels/")
#: Level script actions whose text the player reads
SCRIPT_TEXT = re.compile(r"^Action\t(?:message|hint|objective|objectiveid|mainobjectiveid|optionalobjectiveid|"
                         r"conditionalobjectiveid)\t(.*)$", re.M)

failures = []


def check(condition, message):
    """Records a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def sentences(text):
    """The sentences of a campaign text (\\n and line ends split too) that are long enough to be distinctive."""
    parts = re.split(r"(?<=[.!?])\s+|\\n|\n|\t", text)
    return {part.strip() for part in parts if len(part.strip()) >= MIN_SENTENCE}


def texts_of(entries, level_files):
    """The in-game names and sentences of package entries and of the script texts of their level files."""
    names = set()
    lines = set()
    for entry in entries:
        for key in NAME_KEYS:
            value = entry.get(key, "").strip()
            if value:
                names.add(value)
        for key in TEXT_KEYS:
            lines |= sentences(entry.get(key, ""))
    for path in level_files:
        for match in SCRIPT_TEXT.finditer(path.read_text(encoding="utf-8", errors="replace").replace("\r", "")):
            # The text is the last field; seat and objective id before it are no text
            lines |= sentences(match.group(1).split("\t")[-1])
    return names, lines


def package_files(folder):
    """Checks that a package folder holds only content files."""
    for path in sorted(folder.iterdir()):
        name = path.name
        check(path.is_file(), "%s: a package holds no subfolder (%s)" % (folder, name))
        check(name.endswith(".level") or name in PACKAGE_TEXT_FILES,
              "%s: %s is no content file of a package" % (folder, name))
        check(path.suffix.lower() not in CODE_EXTENSIONS and name not in CODE_NAMES,
              "%s: code file %s in a package" % (folder, name))


def tracked(repo):
    """Tracked files of a repository, relative paths."""
    output = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [name for name in output.decode("utf-8").split("\0") if name]


# Public packages: exactly wing 1, only content files, its licence file
public = campaign_packages.packages(ROOT, with_content=False)
check([wing for _, wing, _, _ in public] == [PUBLIC_WING], "the public tree must hold exactly the package of wing 1")
public_entries = campaign_packages.entries(ROOT, with_content=False)
check(len(public_entries) == PUBLIC_LEVEL_COUNT, "the public package must hold %d levels" % PUBLIC_LEVEL_COUNT)
check(all(entry["_path"].is_file() for entry in public_entries), "every public package level file must exist")
check((ROOT / PUBLIC_PACKAGE / "LICENSE.txt").is_file(), "the wing 1 package needs its own licence file")
for folder in sorted((ROOT / campaign_packages.PUBLIC_FOLDER).iterdir()):
    if folder.is_dir():
        check((folder / campaign_packages.DEFINITION_FILE).is_file(), "%s is a folder without Package.cfg" % folder)
        package_files(folder)
public_files = tracked(ROOT)
for name in public_files:
    if name.endswith((".cfg", ".level")) and not name.startswith(PUBLIC_PACKAGE + "/"):
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        check(re.search(r"^Wing=[2-6]\s*$", text, re.M) is None, name + " holds a campaign entry of a private wing")

content = campaign_packages.content_repository(ROOT)
paid_count = 0
if content is not None:
    private = campaign_packages.packages(ROOT)
    private = [package for package in private if not package[2]]
    check(sorted(wing for _, wing, _, _ in private) == [2, 3, 4, 5, 6],
          "the content repository must hold the packages of wings 2 to 6")
    for folder, _, _, _ in private:
        package_files(folder)
    for name in tracked(content):
        path = Path(name)
        check(path.suffix.lower() not in CODE_EXTENSIONS and path.name not in CODE_NAMES,
              "the content repository must hold no code: " + name)

    # The in-game texts of the private packages, without the texts the public tree uses itself
    private_entries = [entry for entry in campaign_packages.entries(ROOT) if not entry["_public"]]
    names, lines = texts_of(private_entries, [entry["_path"] for entry in private_entries])
    public_names, public_lines = texts_of(public_entries, [entry["_path"] for entry in public_entries])
    # Texts the public game ships itself (wing 1, the map, other levels and the configuration) are public: a name
    # or sentence that also stands there is no paid text
    shipped = [(ROOT / name).read_text(encoding="utf-8", errors="replace").replace("\r", "").replace("\\n", " ")
               for name in public_files if name.startswith(PUBLIC_GAME_DATA)]
    shipped += [entry.get(key, "") for entry in public_entries for key in TEXT_KEYS]
    names = {name for name in names - public_names if not any(name in text for text in shipped)}
    lines = {line for line in lines - public_lines if not any(line in text for text in shipped)}
    paid_count = len(names) + len(lines)
    name_pattern = re.compile(r"(?<![A-Za-z])(?:%s)(?![A-Za-z])" % "|".join(
        re.escape(name) for name in sorted(names, key=len, reverse=True))) if names else None
    for name in public_files:
        if name.startswith(PUBLIC_PACKAGE + "/"):
            continue
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        flat = text.replace("\r", "").replace("\\n", " ")
        found = name_pattern.search(flat) if name_pattern else None
        if found is None:
            found_line = next((line for line in lines if line in flat), None)
            check(found_line is None, "%s carries paid campaign text: %s" % (name, (found_line or "")[:70]))
        else:
            check(False, "%s carries the paid campaign name %s" % (name, found.group(0)))

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign content separation: public package wing 1 (%d levels), content %s, %d paid texts scanned: PASS" % (
    len(public_entries), "present" if content is not None else "absent", paid_count))
