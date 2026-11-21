"""Wing packages of the campaign for the check scripts, the load tests and the tools.

The campaign is read from wing packages: a folder with a Package.cfg (the [Level] entries of one wing, in the format
the game reads) and the level files of the wing. Wing 1 comes with the public tree in levels/campaign/wing1/; the
packages of the other wings come from the private content repository (its packages/ folder). The content folder is
the folder named by the environment variable MOREYA_CONTENT_DIR (an empty value means: no content), else the folder
packages/ of a Moreya-Content checkout next to this repository. Without content packages every helper works on the
public packages alone, so the public tree is checked on its own.

The campaign name of a level (File=campaign/<name>.level) stays the name of progress files, saves and level scripts;
the level file of that name lies in the folder of its package. This module holds no campaign content.
"""
import os
import re
from pathlib import Path

CONTENT_VARIABLE = 'MOREYA_CONTENT_DIR'
PUBLIC_FOLDER = 'levels/campaign'
DEFINITION_FILE = 'Package.cfg'
CONTENT_CHECKOUT = 'Moreya-Content'
NUM_WINGS = 6
#: The levels of the public package (wing 1) in campaign order, fixed for this branch: the checks expect exactly these
#: without content packages
PUBLIC_LEVELS = ('Brackenford', 'Coldwell', 'Ravensledge', 'Mossgate')
#: Text the campaign map shows for a wing whose package is missing
MISSING_WING_TEXT = 'Coming in Early Access'


# The folder that holds the content packages, or None when there is no content.
def content_folder(repo):
    repo = Path(repo)
    if CONTENT_VARIABLE in os.environ:
        value = os.environ[CONTENT_VARIABLE].strip()
        return Path(value) if value and Path(value).is_dir() else None
    candidate = repo.resolve().parent / CONTENT_CHECKOUT / 'packages'
    return candidate if candidate.is_dir() else None


# The content repository (the parent of its packages folder), or None when there is no content.
def content_repository(repo):
    folder = content_folder(repo)
    if folder is None:
        return None
    return folder.parent if folder.name == 'packages' else folder


# True when content packages are present.
def has_content(repo):
    return content_folder(repo) is not None


# Environment for a game process: names the content folder when there is one, else removes the variable.
def game_environment(repo, base=None):
    environment = dict(os.environ if base is None else base)
    folder = content_folder(repo)
    if folder is None:
        environment.pop(CONTENT_VARIABLE, None)
    else:
        environment[CONTENT_VARIABLE] = str(folder)
    return environment


# The [Level] entries of a definition text as dictionaries of their keys, in file order.
def parse_entries(text):
    text = text.replace('\r', '')
    return [dict(re.findall(r'^(\w+)=(.*)$', block, re.M))
            for block in re.split(r'^\[Level\]\s*$', text, flags=re.M)[1:]]


# Package folders with a Package.cfg below a folder, in name order.
def _package_dirs(folder):
    if folder is None or not Path(folder).is_dir():
        return []
    return sorted(path for path in Path(folder).iterdir() if (path / DEFINITION_FILE).is_file())


# Every package as (folder, wing, public, entries), public packages first, like the game: a package must name one
# wing of 1 to 6 for all of its levels and the first package of a wing wins.
def packages(repo, with_content=True):
    repo = Path(repo)
    found = []
    wings = set()
    sources = [(path, True) for path in _package_dirs(repo / PUBLIC_FOLDER)]
    if with_content:
        sources += [(path, False) for path in _package_dirs(content_folder(repo))]
    for path, public in sources:
        entries = [entry for entry in parse_entries((path / DEFINITION_FILE).read_text(encoding='utf-8'))
                   if entry.get('File')]
        if not entries:
            continue
        wing = entries[0].get('Wing', '')
        if not wing.isdigit() or not 1 <= int(wing) <= NUM_WINGS or int(wing) in wings:
            continue
        if any(entry.get('Wing') != wing for entry in entries):
            continue
        wings.add(int(wing))
        found.append((path, int(wing), public, entries))
    return sorted(found, key=lambda package: package[1])


# All campaign entries in campaign order (wing order, then file order), each with '_path' (level file), '_package'
# (package folder) and '_public' (True for a package of the public tree).
def entries(repo, with_content=True):
    result = []
    for path, wing, public, package_entries in packages(repo, with_content):
        for entry in package_entries:
            entry = dict(entry)
            entry['_path'] = path / entry['File'].split('/')[-1]
            entry['_package'] = path
            entry['_public'] = public
            result.append(entry)
    return result


# The definition texts of all packages joined in campaign order, as one Campaign.cfg-like text.
def definition_text(repo, with_content=True):
    return '\n'.join((path / DEFINITION_FILE).read_text(encoding='utf-8').replace('\r', '')
                     for path, _, _, _ in packages(repo, with_content))


# The file of a level: a campaign name (campaign/<name>.level) or a bare level name resolves to the level file of
# its package; any other name is relative to the levels/ folder of the repository.
def level_path(repo, name):
    repo = Path(repo)
    file = name if name.endswith('.level') else name + '.level'
    if '/' not in file:
        file = 'campaign/' + file
    for entry in entries(repo):
        if entry['File'] == file:
            return entry['_path']
    return repo / 'levels' / file


# The text of a level file (see level_path).
def read_level(repo, name):
    return level_path(repo, name).read_text(encoding='utf-8')


# Wings that have no package.
def missing_wings(repo, with_content=True):
    present = {wing for _, wing, _, _ in packages(repo, with_content)}
    return [wing for wing in range(1, NUM_WINGS + 1) if wing not in present]


# Every level file of the campaign and the dropped maps of levels/campaign/, the files a full level check covers.
def all_level_files(repo, with_content=True):
    repo = Path(repo)
    files = [entry['_path'] for entry in entries(repo, with_content)]
    files += sorted((repo / PUBLIC_FOLDER).glob('*.level'))
    return files


# The guild of a story entry in the form of the former map description (name, leader, first_leader, origin, groups,
# size, kind, banner, portrait), or None for an entry without guild.
def guild_of(entry):
    if not entry.get('Guild'):
        return None
    guild = {'name': entry['Guild'], 'leader': entry.get('GuildLeader', ''), 'origin': entry.get('GuildOrigin', ''),
             'groups': int(entry.get('GuildGroups', '0') or 0), 'size': int(entry.get('GuildSize', '0') or 0),
             'kind': entry.get('GuildKind', ''), 'banner': entry.get('GuildBanner', ''),
             'portrait': entry.get('GuildPortrait', '')}
    if entry.get('GuildFirstLeader'):
        guild['first_leader'] = entry['GuildFirstLeader']
    return guild


# The fixed expectations of a check for the content packages (checks/<name>.json of the content repository), or None
# without content. With content present the file must exist: a check never skips the content it has.
def content_data(repo, name):
    import json
    root = content_repository(repo)
    if root is None:
        return None
    path = root / 'checks' / (name + '.json')
    if not path.is_file():
        raise RuntimeError('content check data missing: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


# The files of the content packages with one of the suffixes (e.g. ('.level', '.cfg')), sorted; empty without
# content. Checks that scan every level file of levels/ add these, so they cover wings 2 to 6 as well.
def content_files(repo, suffixes):
    folder = content_folder(repo)
    if folder is None:
        return []
    return sorted(path for path in folder.rglob('*') if path.is_file() and path.suffix in tuple(suffixes))


# A path for messages: relative to the repository, or content/<path in the content folder> for a content file.
def display_path(repo, path):
    path = Path(path).resolve()
    try:
        return path.relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        folder = content_folder(repo)
        return 'content/' + path.relative_to(folder.resolve()).as_posix() if folder else path.as_posix()


# The level names (file stems) a check covers: every name of its table with content packages, else the names of
# the public package.
def checked_names(repo, names):
    if has_content(repo):
        return list(names)
    return [name for name in names if name in PUBLIC_LEVELS]
