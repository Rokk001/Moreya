#!/usr/bin/env python3
"""Check torture mood and the conversion roll."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

torture = (ROOT / 'source/rooms/RoomTorture.cpp').read_text(encoding='utf-8')
definition = (ROOT / 'source/entities/CreatureDefinition.cpp').read_text(encoding='utf-8')
header = (ROOT / 'source/entities/CreatureDefinition.h').read_text(encoding='utf-8')
# The mixed table comes joined with its own rows of the content (scripts/content_packages.py)
config = content_packages.read_text(ROOT, 'config/creatures.cfg')
for obsolete in ('TORTURE_LEVEL_PERCENT', 'tortureTurnsToConvert', 'TortureTimeToConvert'):
    for text in (torture, definition, header, config):
        assert obsolete not in text, obsolete
assert re.search(r'addTortureMood\(.*?TortureMoodPerSecond.*?ResearchEffect::ConversionSpeed.*?ODApplication::turnsPerSecond', torture, re.S)
assert re.search(r'getSeat\(\)\s*!=\s*creature->getSeat\(\).*?creature->getMoodPoints\(\)\s*<\s*config.getCreatureMoodFurious\(\).*?increaseTortureBrokenTurns\(\).*?floor\(brokenTurns\s*/\s*ODApplication::turnsPerSecond\).*?floor\(\(brokenTurns\s*-\s*1\)\s*/\s*ODApplication::turnsPerSecond\).*?secondPassed.*?Random::Double\(0\.0,\s*1\.0\).*?TortureConvertChancePerSecond.*?convertVictim\(\*creature\)', torture, re.S)
assert not re.search(r'getCreatureBaseMood\(\)\s*\+\s*creature->getMoodPoints\(\)', torture), 'the effective mood is compared directly'
assert 'resetTortureBrokenTurns()' in torture
if not content_packages.has_content(ROOT):
    content_packages.unchecked('check_torture_mood', ['own rows of config/creatures.cfg'])
print('torture mood ok')
