"""Worker reactions: every event the code shows exists in the config, the hooks are wired, nothing touches the game.
Static checks only, never launches a game.
The config and the particle script lie in the content packages (scripts/content_packages.py); without the content
the code part is checked and the content part is named as not checked."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402


def read(path):
    """The text of a file below the repository root."""
    return (root / path).read_text(encoding='utf-8')


def content(path):
    """The text of a game data file of the public tree or of a content package, or None without the content."""
    found = content_packages.data_file(root, path)
    return None if found is None else found.read_text(encoding='utf-8')


code = read('source/render/WorkerReactions.cpp')
reactions = read('source/render/CreatureReactions.cpp')
reactions_h = read('source/render/CreatureReactions.h')
cfg = content('config/creatureReactions.cfg')
particles = content('particles/WorkerReactions.particle')
if cfg is None or particles is None:
    content_packages.unchecked('check_worker_reactions', ['config/creatureReactions.cfg', 'particles/WorkerReactions.particle'])

# Overlay principle: no animation state, no activity, no refresh, no network in the worker reactions
for forbidden in ('setAnimationState', 'mActivity', 'fireCreatureRefreshIfNeeded', 'ODPacket', 'ServerNotification',
                  'sendCosmeticEvent'):
    assert forbidden not in code, forbidden

# Every event named in the code is a [Event] of the config
used = set(re.findall(r'"((?:Dig|Claim|Reinforce|Pick|Gold|Treasury|Prisoner|Corpse|Trap|Worker)\w*)"', code))
assert used, 'no events found in the code'
# Clip, room, mesh and entity names that look like events
not_events = {'Claim', 'Dig', 'Treasury', 'GoldstackLv', 'WorkerGoldBody_'}
if cfg is not None:
    events = set(re.findall(r'^\s*Name\s+(\w+)\s*$', cfg, re.MULTILINE))
    missing = sorted(name for name in used if name not in events and name not in not_events)
    assert not missing, 'events missing in config/creatureReactions.cfg: %s' % missing

# The hooks of the framework call the worker reactions
for call in ('WorkerReactions::update(', 'WorkerReactions::noteAnimation(', 'WorkerReactions::noteCarry(',
             'WorkerReactions::noteRelease(', 'WorkerReactions::noteHandled(', 'WorkerReactions::noteParticleEffect(',
             'WorkerReactions::noteCosmeticEvent(', 'WorkerReactions::stopAll('):
    assert call in reactions, call
assert 'friend class WorkerReactions;' in reactions_h
assert 'render/WorkerReactions.cpp' in read('CMakeLists.txt')

# The particle systems used by the new events exist
for name in re.findall(r'\b(Worker(?:Dirt|RockSparks|GoldSplinters|GemGlint|CoinCloud|Rubble))\b', cfg or ''):
    assert particles is None or re.search(r'^particle_system\s+%s\s*$' % name, particles, re.MULTILINE), name

print('worker reactions: ok (%d events used by the code)' % len(used))
