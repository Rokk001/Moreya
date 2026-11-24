#!/usr/bin/env python3
"""Worker extras: struggling prisoners, coins of a dying worker and worker sounds.

Static checks only (no compiling, never launches a game):
- the extras code does not touch the game (no animation state, no activity, no refresh, no network)
- every event with a sound exists in the config and every sound family has at least one .ogg file
- every sound file is listed in CREDITS
- the death coins event exists, is made for the dying creature and its effect exists
- the hooks in the worker reactions are in place and the source is in the build file

config/creatureReactions.cfg, the worker sounds, the particle scripts and their CREDITS rows are content (found through
scripts/content_packages.py, rows in the CREDITS of the content repository); without the content the parts that need
them are named as not checked and the code side is checked.
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

WITH_CONTENT = content_packages.has_content(root)


def read(path):
    """Text of a file of the repository, or of a game data file of a content package."""
    return content_packages.read_text(root, path)


extras = read('source/render/WorkerExtras.cpp')
reactions = read('source/render/WorkerReactions.cpp')
# None without the content: the parts that need the reaction config are then not checked
cfg = read('config/creatureReactions.cfg') \
    if WITH_CONTENT or content_packages.data_file(root, 'config/creatureReactions.cfg') is not None else None
# the public CREDITS plus the CREDITS of the content repository
credits = room_packages.credits_text(root)

for forbidden in ('setAnimationState', 'mActivity', 'fireCreatureRefreshIfNeeded', 'ODPacket', 'ServerNotification',
                  'sendCosmeticEvent'):
    assert forbidden not in extras, forbidden

events = set(re.findall(r'^\s*Name\s+(\w+)\s*$', cfg, re.MULTILINE)) if cfg is not None else None

# Sound table: event -> family
table = re.findall(r'eventName == "(\w+)"\)', extras)
families = set(re.findall(r'PREFIX \+ "(\w+)"', extras))
assert table and families
if events is None:
    content_packages.unchecked('check_worker_extras', ['sound events of config/creatureReactions.cfg'])
else:
    for name in table:
        assert name in events, 'sound event missing in the config: %s' % name
for family in families:
    files = content_packages.data_glob(root, 'sounds/Spatial/Creatures/Worker/' + family, '*.ogg')
    if not files and not WITH_CONTENT:
        content_packages.unchecked('check_worker_extras', ['sounds and CREDITS of the worker sound family ' + family])
        continue
    assert files, 'no sound files for %s' % family
    assert ('Spatial/Creatures/Worker/%s/' % family) in credits, 'no CREDITS entry for %s' % family
    for item in files:
        assert item.stat().st_size > 1000, item
        assert item.read_bytes()[:4] == b'OggS', item

if cfg is None:
    content_packages.unchecked('check_worker_extras', ['death coins event (config/creatureReactions.cfg)'])
else:
    # Death coins: for the dying creature, with an effect that exists
    match = re.search(r'Name\s+WorkerDeathCoins\s*\r?\n(.*?)\[/Event\]', cfg, re.DOTALL)
    assert match, 'WorkerDeathCoins missing'
    assert re.search(r'^\s*Dying\s+yes\s*$', match.group(1), re.MULTILINE)
    particles = read('particles/WorkerReactions.particle') + read('particles/CreatureReactions.particle')
    for effect in re.findall(r'^\s*(?:Late)?Effect\s+(\w+)', match.group(1), re.MULTILINE):
        assert re.search(r'^particle_system\s+%s\s*$' % effect, particles, re.MULTILINE), effect

# Hooks and build
for call in ('WorkerExtras::startStruggle(', 'WorkerExtras::endStruggle(', 'WorkerExtras::update(',
             'WorkerExtras::stopAll(', 'WorkerExtras::playSound('):
    assert call in reactions, call
assert '"WorkerDeathCoins"' in reactions
assert 'render/WorkerExtras.cpp' in read('CMakeLists.txt')

if cfg is None:
    content_packages.unchecked('check_worker_extras', ['gold digging events (config/creatureReactions.cfg)'])
else:
    # Gold digging shows small splinters only: no big additive glow over the worker
    for name in ('DigHitGold', 'DigFinishGold'):
        block = re.search(r'Name\s+%s\s*$(.*?)\[/Event\]' % name, cfg, re.MULTILINE | re.DOTALL)
        assert block, name
        assert 'ReactionGlow' not in block.group(1), '%s must not use the big glow' % name

# Diggers stand in front of the wall tile, not half inside it
creature_src = read('source/entities/Creature.cpp')
share = re.search(r'parkingShare\s*=\s*([0-9.]+)', creature_src)
assert share and float(share.group(1)) <= 0.25, 'parking point too close to the wall edge'
assert 'getPosition2d())*parkingShare' in creature_src

print('worker extras: ok (%d sound events, %d families)' % (len(table), len(families)))
