"""Text check of config/treasury.cfg against the settings struct: every key of the file is documented in its head
comment, every setting of the struct is in the file with the same default (a missing file changes nothing), every
key is read by fromConfig and every setting is used somewhere in the sources. No compiler needed.
config/treasury.cfg lies in the content packages (scripts/content_packages.py); without the content the struct is
checked against fromConfig and the sources, and the file part is named as not checked."""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402


def read(path):
    """The text of a file below the repository root, with Unix line ends."""
    return (repo / path).read_text(encoding='utf-8').replace('\r\n', '\n')


cfg_file = content_packages.data_file(repo, 'config/treasury.cfg')
cfg = None if cfg_file is None else cfg_file.read_text(encoding='utf-8').replace('\r\n', '\n')
if cfg is None:
    content_packages.unchecked('check_treasury_config', ['config/treasury.cfg'])
header = read('source/rooms/TreasurySettings.h')

if cfg is not None:
    # Keys and values of the [Treasury] block (a '#' starts a comment)
    body = []
    for line in cfg.split('\n'):
        line = line.split('#')[0].strip()
        if line:
            body.append(line)
    assert body[0] == '[Treasury]' and body[-1] == '[/Treasury]'
    values = {}
    for line in body[1:-1]:
        parts = line.split()
        assert len(parts) == 2, line
        assert parts[0] not in values, 'duplicate key ' + parts[0]
        values[parts[0]] = parts[1]

    # Every key is documented in the head comment ("#   Key (default): text")
    documented = set(re.findall(r'^#   (\w+) \(', cfg, re.M))
    assert set(values) == documented, (set(values) ^ documented)

# Settings of the struct with their defaults
struct = header.split('struct TreasurySettings')[1].split('typedef std::map')[0]
members = {}
for kind, name, default in re.findall(r'^    (float|int) (\w+) = ([-0-9.]+)f?;', struct, re.M):
    members[name[0].upper() + name[1:]] = (kind, float(default))
assert len(members) >= 30
if cfg is not None:
    assert set(members) == set(values), (set(members) ^ set(values))
    for key, (kind, default) in members.items():
        assert abs(float(values[key]) - default) < 1e-6, 'default of %s differs from the file' % key
else:
    # Without the file the struct stands in for its keys
    values = members

# Every key is read by fromConfig, with a limit
reads = dict((key, kind) for kind, key in re.findall(r'read(Float|Int)\(config, "(\w+)"', header))
assert set(reads) == set(values), (set(reads) ^ set(values))
for key, (kind, default) in members.items():
    assert reads[key] == kind.capitalize(), key

# Loaded at start-up, and every setting is used outside of the struct
manager = read('source/utils/ConfigManager.cpp')
assert 'loadTreasury(configPath + "treasury.cfg")' in manager and 'TreasurySettings::fromConfig(values)' in manager
sources = ''
for path in (repo / 'source').rglob('*'):
    if path.suffix in ('.cpp', '.h') and path.name != 'TreasurySettings.h':
        sources += path.read_text(encoding='utf-8', errors='replace')
for key in members:
    name = key[0].lower() + key[1:]
    assert re.search(r'current\(\)\.' + name + r'\b|\bs(ettings)?\.' + name + r'\b', sources), 'unused setting ' + name

# Out of range values are limited, a missing key keeps the default
assert 'return parsed < low ? low : (parsed > high ? high : parsed);' in header
assert 'if(it == config.end())' in header
print('ok')
