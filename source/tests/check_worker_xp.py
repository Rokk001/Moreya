#!/usr/bin/env python3
"""Check that worker actions use the configured experience calculations."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
# Read one worker action source.
def read(name):
    return (ROOT / 'source/creatureaction' / name).read_text(encoding='utf-8')

dig = read('CreatureActionDigTile.cpp')
for key in ('DigXpFactor', 'GoldDigXpFactor', 'WorkXpRateDivisor', 'TileDugXp'):
    assert 'get' + key + '()' in dig, key
assert dig.count('getGoldDigXpFactor()') >= 2
claim = read('CreatureActionClaimGroundTile.cpp')
for key in ('ClaimXpFactor', 'ClaimXpDivisorBase', 'ClaimXpDivisorPerLevel'):
    assert 'get' + key + '()' in claim, key
assert 'creature.receiveExp(getClaimExperience(creature))' in claim
for name in ('CreatureActionClaimWallTile.cpp', 'CreatureActionCleanTile.cpp'):
    assert 'creature.receiveExp(CreatureActionClaimGroundTile::getClaimExperience(creature))' in read(name), name
reload = read('CreatureActionReloadTrap.cpp')
assert re.search(r'creature\.receiveExp\(.*?getTrapConfigDoubleOrDefault\("TrapReloadExperience"', reload)
# The key is an own row of config/traps.cfg (content package core-config)
if content_packages.has_content(ROOT):
    traps = content_packages.read_text(ROOT, 'config/traps.cfg')
    assert re.search(r'^\s*TrapReloadExperience\s+9\.828\s*$', traps, re.M)
else:
    content_packages.unchecked('check_worker_xp', ['TrapReloadExperience of config/traps.cfg'])
print('worker xp ok')
