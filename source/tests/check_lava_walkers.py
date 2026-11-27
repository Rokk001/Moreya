#!/usr/bin/env python3
"""Check level-scaled lava damage and the creature types that can walk on lava."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
source = (ROOT / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
body = source.split('void Creature::applyLavaDamage()', 1)[1].split('\nbool Creature::', 1)[0]
assert 'getLavaDamageScalesWithHp()' in body
assert re.search(r'lavaDamagePerSecond\s*\*=\s*CreatureProgression::hpMultiplier\(getLevel\(\)\)', body)
assert 'takeDamage(nullptr, lavaDamagePerSecond / ODApplication::turnsPerSecond' in body
# config/creatures.cfg is a mixed table: its creatures are only complete with the own rows of the content
if not content_packages.has_content(ROOT):
    content_packages.unchecked('check_lava_walkers', ['lava walkers of config/creatures.cfg'])
    print('lava walkers ok: code checked, content not present')
    sys.exit(0)
config = content_packages.read_text(ROOT, 'config/creatures.cfg')
walkers = set()
for block in re.findall(r'^\[Creature\]\s*$(.*?)^\[/Creature\]', config, re.M | re.S):
    name = re.search(r'^\s*Name\s+(\S+)', block, re.M)
    speed = re.search(r'^\s*LavaMoveSpeed\s+(\S+)', block, re.M)
    assert name and speed
    if float(speed.group(1)) > 0:
        walkers.add(name.group(1))
# Roster change (CREATURE-ROSTER W4a): Butcher, Werewolf and Gnoll take the lava walking of their predecessors LavaSpawn and Wyvern
assert walkers == {'Butcher', 'PitDemon', 'Dragon', 'Werewolf', 'Gnoll', 'CaveHornet'}, walkers
print('lava walkers ok')
