"""Content packages for the check scripts, the load tests and the packaging scripts.

The content of the game (models, textures, interface art, portraits, sounds, levels, data tables) lives in content
packages of the private content repository, not in the public tree. A content package is a folder with a Package.cfg
that names it in a line "Content=<package name>"; inside the package every file lies at the same relative path as in
the public tree (models/, materials/, gui/, sounds/, levels/, config/, particles/). The game
(source/utils/ContentPackages.cpp) searches the packages in the same folders as the wing and room packages: the
subfolders of levels/campaign/ and of the content folder (scripts/campaign_packages.py: MOREYA_CONTENT_DIR, else the
packages/ folder of a Moreya-Content checkout next to this repository). Without its required packages the game says
that the content is missing and quits.

Checks that read a game data file use data_file(): it returns the file of the public tree when it is there, else the
file of a found content package (or room package), else None. With None the content is not present: the check checks
its public part and names the part it could not check with unchecked(); with the content present every assertion
runs. This module holds no content.
"""
import re
import sys
from pathlib import Path

import campaign_packages
import room_packages

DEFINITION_FILE = campaign_packages.DEFINITION_FILE
CONTENT_KEY = 'Content'
#: The content packages the game needs, sorted; fixed for this branch, the same table as REQUIRED_PACKAGES in
#: source/utils/ContentPackages.cpp (32 packages)
REQUIRED_PACKAGES = (
    'core-config', 'core-gui', 'core-levels', 'core-menu', 'core-models', 'core-portraits', 'core-sounds', 'creatures',
    'doors', 'effects', 'equipment', 'gui-skin', 'items', 'lang-en', 'room-arena', 'room-casino', 'room-crypt',
    'room-dormitory', 'room-dungeon-temple', 'room-hatchery', 'room-library', 'room-portal', 'room-portal-wave',
    'room-prison', 'room-stone-bridge', 'room-torture', 'room-training-hall', 'room-treasury', 'room-wooden-bridge',
    'room-workshop', 'terrain', 'traps',
)
#: Exit code of the game when it quits because content packages are missing (ContentPackages::MISSING_CONTENT_EXIT_CODE)
MISSING_CONTENT_EXIT_CODE = 7


# The content package named by a definition text (the value of the first line "Content=<name>"), or None.
def parse_definition(text):
    for line in text.replace('\r', '').split('\n'):
        match = re.fullmatch(r'Content=\s*(\S+)\s*', line)
        if match:
            return match.group(1)
    return None


def _package_dirs(folder):
    """Package folders below a folder, in name order, like the game."""
    if folder is None or not Path(folder).is_dir():
        return []
    return sorted(path for path in Path(folder).iterdir() if (path / DEFINITION_FILE).is_file())


#: Found packages by (repository, content folder), so repeated lookups do not scan the folders again
_CACHE = {}


# The found content packages as {package name: folder}, like the game: levels/campaign/ of the repository first, then
# the content folder; the first package of a name wins.
def packages(repo):
    repo = Path(repo)
    content = campaign_packages.content_folder(repo)
    key = (str(repo.resolve()), str(content))
    if key not in _CACHE:
        found = {}
        for folder in (repo / campaign_packages.PUBLIC_FOLDER, content):
            for path in _package_dirs(folder):
                name = parse_definition((path / DEFINITION_FILE).read_text(encoding='utf-8'))
                if name is not None and name not in found:
                    found[name] = path
        _CACHE[key] = found
    return dict(_CACHE[key])


# The required content packages that are not present, sorted.
def missing_packages(repo):
    found = packages(repo)
    return [name for name in REQUIRED_PACKAGES if name not in found]


# True when every required content package is present.
def has_content(repo):
    return not missing_packages(repo)


# The folders the game reads its data from besides the public tree: every content package, then every room package.
def package_roots(repo):
    return list(packages(repo).values()) + list(room_packages.packages(repo).values())


# The file of a game data path: the public file when the public tree has it, else the file of a found content or room
# package, else None (the content is not present).
def data_file(repo, relative):
    repo = Path(repo)
    relative = str(relative).replace('\\', '/')
    public = repo / relative
    if public.exists():
        return public
    for root in package_roots(repo):
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


# The file of a game data path as data_file(), else the path below the repository (for messages and for checks that
# must fail when the file is missing although the content is present).
def resolve(repo, relative):
    return data_file(repo, relative) or (Path(repo) / str(relative).replace('\\', '/'))


# The text of a game data file (see resolve). A mixed data table (config/global.cfg, ...) comes with its own rows from
# the content packages in place of its marker lines, as the game reads it (scripts/config_own_rows.py); without the
# content it is the public table alone, whose markers are comments.
def read_text(repo, relative, encoding='utf-8'):
    text = resolve(repo, relative).read_text(encoding=encoding)
    if '#@own ' not in text:
        return text
    import config_own_rows
    return config_own_rows.joined_text(repo, str(relative).replace('\\', '/'), text)


# The existing folders of a game data folder: the public folder and the same folder of every found content and room
# package, in that order.
def data_folders(repo, relative):
    repo = Path(repo)
    relative = str(relative).replace('\\', '/').rstrip('/')
    folders = [repo / relative] + [root / relative for root in package_roots(repo)]
    return [folder for folder in folders if folder.is_dir()]


# Every file below a game data folder matching the glob pattern, from the public folder and every package, sorted by
# their path relative to the folder (a file of the public tree first).
def data_glob(repo, relative, pattern='*', recursive=False):
    found = {}
    for folder in data_folders(repo, relative):
        for path in (folder.rglob(pattern) if recursive else folder.glob(pattern)):
            key = path.relative_to(folder).as_posix()
            if path.is_file() and key not in found:
                found[key] = path
    return [found[key] for key in sorted(found)]


# The relative game data path of a file of the public tree or of a package (for messages and lookups).
def relative_path(repo, path):
    path = Path(path).resolve()
    for root in [Path(repo)] + package_roots(repo):
        try:
            return path.relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            continue
    return path.as_posix()


# Environment for a game process: names the content folder when there is one, else removes the variable.
def game_environment(repo, base=None):
    return campaign_packages.game_environment(repo, base)


# Prints which content part a check could not check because the content is not present; returns the names.
def unchecked(check, names):
    names = [str(name) for name in names]
    if names:
        shown = ', '.join(names[:8]) + (' and %d more' % (len(names) - 8) if len(names) > 8 else '')
        print('%s: content not present, not checked: %s' % (check, shown))
    return names


#: Language texts already read, {(repository, language): {key: text}}
_LANGUAGE_TEXTS = {}


# The texts of a language package as {key: text} ("<key>=<text>" lines of its texts/*.txt files, "\n" kept as written).
def language_texts(repo, language='en'):
    cache_key = (str(Path(repo).resolve()), language)
    if cache_key not in _LANGUAGE_TEXTS:
        texts = {}
        for root in package_roots(repo):
            definition = (Path(root) / DEFINITION_FILE).read_text(encoding='utf-8', errors='replace')
            if ('Language=' + language) not in definition.replace('\r', '').split('\n'):
                continue
            for path in sorted((Path(root) / 'texts').glob('*.txt')):
                for line in path.read_text(encoding='utf-8-sig').replace('\r', '').split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        texts[key.strip()] = value
        _LANGUAGE_TEXTS[cache_key] = texts
    return _LANGUAGE_TEXTS[cache_key]


# The text of a layout Text or TooltipText value: "@<key>" gives the text of the language package (the value itself when
# the key or the content is missing), any other value is returned unchanged.
def layout_text(repo, value, language='en'):
    if value is not None and value.startswith('@'):
        return language_texts(repo, language).get(value[1:], value)
    return value


# The text of a layout (a gui/*.layout game data file, see read_text) with every "@<key>" text value replaced by the text
# of the language package, written as an XML attribute value. Checks that test the English wording of a layout read it
# through this function (localization plan R11); the layout files themselves hold the keys. Any other file is read as
# read_text does.
def read_layout_text(repo, relative, language='en', encoding='utf-8'):
    import re
    if not str(relative).endswith('.layout'):
        return read_text(repo, relative, encoding)
    texts = language_texts(repo, language)

    def replace(match):
        key = match.group(2)
        if key not in texts:
            return match.group(0)
        value = texts[key].replace('\\n', '\n').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        value = value.replace('"', '&quot;').replace('\n', '&#10;')
        return match.group(1) + value + '"'

    return re.sub(r'(<Property name="(?:Text|TooltipText)" value=")@([^"]+)"', replace,
                  read_text(repo, relative, encoding))
