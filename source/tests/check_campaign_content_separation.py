"""Code and paid campaign content never share a file; never starts a game.

The campaign is split into wing packages (scripts/campaign_packages.py): the public tree holds no wing; all six wings
(wing 1 with its own licence file) come from the private content repository. Paid content is the content of the
private packages: their level files and the in-game texts of their Package.cfg (titles, briefings, debriefings,
wardens, guild names and leaders) and of their level scripts (messages, hints and objective texts).

Checked rules, with fixed expectations of this branch:
  * a package folder holds only content: Package.cfg, level files and its licence or readme text; never code;
  * the public tree has no package and no campaign level (0 public levels, fixed for this branch) and no campaign
    entry of any wing;
  * the content repository holds the packages of wings 1 to 6, wing 1 with its own licence file, and no code file
    (packages, documents and check data only);
  * with the content repository present, no tracked file of the public tree carries an in-game text of a private
    package (texts that the public game data also ships, e.g. a skirmish level, are public).
Without the content repository only the public part is checked; the content part is named as not checked.
Tracked files are taken as they are in the working tree: a tracked file already moved out of it is not read.
"""
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

#: The public packages and their level files, counted once for this branch: none, every wing is content
PUBLIC_WINGS = []
PUBLIC_LEVEL_COUNT = 0
#: The wings of the content repository, counted once for this branch
CONTENT_WINGS = [1, 2, 3, 4, 5, 6]
#: The wing whose package brings its own licence file
LICENSED_WING = 1
#: Files a package folder may hold besides its level files
PACKAGE_TEXT_FILES = {"Package.cfg", "LICENSE.txt", "LICENSE", "README.md"}
#: The image folders a wing package may hold: its own campaign images, PNG files only
PACKAGE_IMAGE_FOLDERS = {"previews", "banners", "portraits"}
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
#: Two words in a row: a line without them holds no name and no sentence
WORDS = re.compile(r"[A-Za-z]{2,} [A-Za-z]")
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


def occurring(candidates, text):
    """The candidate texts that occur in the text, found in one pass (longest first where they start together).
    A candidate hidden inside an overlapping longer one may be missed, which only keeps it as paid text."""
    if not candidates:
        return set()
    pattern = re.compile("|".join(re.escape(item) for item in sorted(candidates, key=len, reverse=True)))
    return {match.group(0) for match in pattern.finditer(text)}


def package_files(folder):
    """Checks that a package folder holds only content files and its campaign image folders with PNG files only."""
    for path in sorted(folder.iterdir()):
        name = path.name
        if path.is_dir() and name in PACKAGE_IMAGE_FOLDERS:
            for image in sorted(path.iterdir()):
                check(image.is_file() and image.suffix == ".png",
                      "%s: %s/%s is no campaign image of a package" % (folder, name, image.name))
            continue
        check(path.is_file(), "%s: a package holds no subfolder (%s)" % (folder, name))
        check(name.endswith(".level") or name in PACKAGE_TEXT_FILES,
              "%s: %s is no content file of a package" % (folder, name))
        check(path.suffix.lower() not in CODE_EXTENSIONS and name not in CODE_NAMES,
              "%s: code file %s in a package" % (folder, name))


def tracked(repo):
    """Tracked files of a repository that are in its working tree, relative paths."""
    output = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [name for name in output.decode("utf-8").split("\0") if name and (Path(repo) / name).is_file()]


# Public packages: none, so no public campaign level
public = campaign_packages.packages(ROOT, with_content=False)
check([wing for _, wing, _, _ in public] == PUBLIC_WINGS, "the public tree must hold no wing package")
public_entries = campaign_packages.entries(ROOT, with_content=False)
check(len(public_entries) == PUBLIC_LEVEL_COUNT, "the public tree must hold %d campaign levels" % PUBLIC_LEVEL_COUNT)
check(all(entry["_path"].is_file() for entry in public_entries), "every public package level file must exist")
for folder in sorted((ROOT / campaign_packages.PUBLIC_FOLDER).iterdir()):
    if folder.is_dir():
        check((folder / campaign_packages.DEFINITION_FILE).is_file(), "%s is a folder without Package.cfg" % folder)
        package_files(folder)
public_files = tracked(ROOT)
for name in public_files:
    if name.endswith((".cfg", ".level")):
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        check(re.search(r"^Wing=[1-6]\s*$", text, re.M) is None, name + " holds a campaign entry of a private wing")

content = campaign_packages.content_repository(ROOT)
paid_count = 0
if content is not None:
    private = campaign_packages.packages(ROOT)
    private = [package for package in private if not package[2]]
    check(sorted(wing for _, wing, _, _ in private) == CONTENT_WINGS,
          "the content repository must hold the packages of wings 1 to 6")
    for folder, wing, _, _ in private:
        package_files(folder)
        if wing == LICENSED_WING:
            check((folder / "LICENSE.txt").is_file(), "the wing 1 package needs its own licence file")
    for name in tracked(content):
        path = Path(name)
        check(path.suffix.lower() not in CODE_EXTENSIONS and path.name not in CODE_NAMES,
              "the content repository must hold no code: " + name)

    # The in-game texts of the private packages, without the texts the public tree uses itself
    private_entries = [entry for entry in campaign_packages.entries(ROOT) if not entry["_public"]]
    names, lines = texts_of(private_entries, [entry["_path"] for entry in private_entries])
    public_names, public_lines = texts_of(public_entries, [entry["_path"] for entry in public_entries])
    # Texts the public game ships itself (the public levels and the public configuration) are public: a name or
    # sentence that also stands there is no paid text
    shipped = [(ROOT / name).read_text(encoding="utf-8", errors="replace").replace("\r", "").replace("\\n", " ")
               for name in public_files if name.startswith(PUBLIC_GAME_DATA)]
    # The game data moved from the public tree into the content and room packages (config/, gui/, levels/ there)
    # is still the game data the game ships; the wing packages have no such folder
    shipped += [path.read_text(encoding="utf-8", errors="replace").replace("\r", "").replace("\\n", " ")
                for package in content_packages.package_roots(ROOT) for folder in PUBLIC_GAME_DATA
                for path in sorted((package / folder).rglob("*")) if path.is_file()]
    shipped += [entry.get(key, "") for entry in public_entries for key in TEXT_KEYS]
    # One joined text (the separator occurs in no name or sentence) keeps the lookups linear
    # Only lines with words can hold a name or a sentence (tile and number rows of the levels cannot)
    shipped_text = "\0".join(line for text in shipped for line in text.split("\n") if WORDS.search(line))
    names = (names - public_names) - occurring(names - public_names, shipped_text)
    lines = (lines - public_lines) - occurring(lines - public_lines, shipped_text)
    paid_count = len(names) + len(lines)
    name_pattern = re.compile(r"(?<![A-Za-z])(?:%s)(?![A-Za-z])" % "|".join(
        re.escape(name) for name in sorted(names, key=len, reverse=True))) if names else None
    # The sentences as one alternation: one pass over a file instead of one search per sentence
    line_pattern = re.compile("|".join(re.escape(line) for line in sorted(lines, key=len, reverse=True))) \
        if lines else None
    for name in public_files:
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        flat = "\n".join(line for line in text.replace("\r", "").replace("\\n", " ").split("\n") if WORDS.search(line))
        found = name_pattern.search(flat) if name_pattern else None
        if found is None:
            found_line = line_pattern.search(flat) if line_pattern else None
            check(found_line is None, "%s carries paid campaign text: %s" % (
                name, found_line.group(0)[:70] if found_line else ""))
        else:
            check(False, "%s carries the paid campaign name %s" % (name, found.group(0)))

else:
    content_packages.unchecked("campaign content separation", ["the packages of wings 1 to 6", "paid texts"])

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign content separation: no public wing (%d levels), content %s, %d paid texts scanned: PASS" % (
    len(public_entries), "present" if content is not None else "absent", paid_count))
