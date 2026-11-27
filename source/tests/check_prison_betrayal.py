#!/usr/bin/env python3
"""Check the prisoner betrayal research, mood gate, timing and reveal."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: True when the content packages are present (the data tables come with their own rows)
WITH_CONTENT = content_packages.has_content(ROOT)
prison = (ROOT / 'source/rooms/RoomPrison.cpp').read_text(encoding='utf-8')
torture = (ROOT / 'source/rooms/RoomTorture.cpp').read_text(encoding='utf-8')
if WITH_CONTENT:
    skills = content_packages.read_text(ROOT, 'config/skills.cfg')
    assert re.search(r'^\s*roomPrison\s+BetrayChance\s+add\s+0\s+0\.00033175355450236967\s+0\.0065727699530516446\s*$', skills, re.M)
assert re.search(r'getResearchValue\(getSeat\(\),\s*SkillType::roomPrison,\s*0\.0,\s*ResearchEffect::BetrayChance\)', prison)
assert re.search(r'betrayChance\s*>\s*0\.0.*?creature->getMoodPoints\(\)\s*<\s*.*?getCreatureMoodFurious\(\)', prison, re.S)
assert not re.search(r'getCreatureBaseMood\(\)\s*\+\s*creature->getMoodPoints\(\)', prison), 'the effective mood is compared directly'
assert re.search(r'increasePrisonBrokenTurns\(\).*?floor\(brokenTurns\s*/\s*ODApplication::turnsPerSecond\).*?floor\(\(brokenTurns\s*-\s*1\)\s*/\s*ODApplication::turnsPerSecond\).*?secondPassed\s*&&\s*\(Random::Double\(0\.0,\s*1\.0\)\s*<\s*betrayChance\).*?RoomTorture::revealEnemyInformation\(\*getSeat\(\),\s*\*creature\)', prison, re.S)
assert 'resetPrisonBrokenTurns()' in prison
assert 'void RoomTorture::revealEnemyInformation(Seat& keeperSeat, Creature& creature)' in torture
if not WITH_CONTENT:
    content_packages.unchecked('check_prison_betrayal', ['prison betrayal research values (own rows of config/skills.cfg)'])
print('prison betrayal ok')
