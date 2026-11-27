#!/usr/bin/env python3
"""Check that keeper slaps use the configured fixed HP damage."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: True when the content packages are present (the data tables come with their own rows)
WITH_CONTENT = content_packages.has_content(ROOT)
source = (ROOT / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
start = source.index('void Creature::slap()')
opening = source.index('{', start)
end = opening + 1
depth = 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
body = source[opening:end]
assert re.search(r'mHp\s*-=\s*ConfigManager::getSingleton\(\)\.getSlapDamage\(\)', body)
assert 'getMaxHp' not in body and 'mMaxHP' not in body
if WITH_CONTENT:
    config = content_packages.read_text(ROOT, 'config/global.cfg')
    game = re.search(r'^\[GameConfig\]\s*$(.*?)^\[/GameConfig\]', config, re.M | re.S).group(1)
    assert re.search(r'^\s*SlapDamage\s+10\s*$', game, re.M)
    assert not re.search(r'^\s*Slap\w*Percent\s+', game, re.M)
if not WITH_CONTENT:
    content_packages.unchecked('check_slap_damage', ['SlapDamage (own row of config/global.cfg)'])
print('slap damage ok')
