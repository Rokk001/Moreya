#!/usr/bin/env python3
"""Check prisoner wake health, needs and captivity mood."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: True when the content packages are present (the data tables come with their own rows)
WITH_CONTENT = content_packages.has_content(ROOT)
prison = (ROOT / 'source/rooms/RoomPrison.cpp').read_text(encoding='utf-8')
creature = (ROOT / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
mood = (ROOT / 'source/creaturemood/CreatureMoodManager.cpp').read_text(encoding='utf-8')
assert re.search(r'setHP\(std::max\(prisonerCreature->getHP\(\),\s*.*?PrisonWakeHpShare.*?\*\s*prisonerCreature->getMaxHp\(\)\)\)', prison, re.S)
jail = creature.split('// If the creature is in jail, it should not auto heal or do anything', 1)[1].split('// If we are not standing somewhere on the map', 1)[0]
for expression in ('getHungerGrowthPerTurn()', 'getThirstGrowthPerTurn()', 'increaseHunger(', 'increaseThirst(', 'PrisonMoodPerSecond', 'ResearchEffect::MoodLoss', 'ODApplication::turnsPerSecond', 'computeMood()', 'computeCreatureOverlayMoodValue()'):
    assert expression in jail, expression
# The prison and the torture chamber take mood points from the stored mood, which is all a captive's effective mood is
header = (ROOT / 'source/entities/Creature.h').read_text(encoding='utf-8')
assert re.search(r'void addPrisonMood\(double points\)\s*\{\s*changeStoredMood\(points\);', header)
assert re.search(r'void addTortureMood\(double points\)\s*\{\s*changeStoredMood\(points\);', header)
assert re.search(r'double Creature::getEffectiveMood\(\) const\s*\{\s*if\(isInContainment\(\)\)\s*return mStoredMood;', creature)
assert 'getPrisonMood' not in mood and 'getTortureMood' not in mood
if WITH_CONTENT:
    rooms = content_packages.read_text(ROOT, 'config/rooms.cfg')
    assert re.search(r'^\s*PrisonMoodPerSecond\s+-0\.9333\s*$', rooms, re.M)
    assert re.search(r'^\s*TortureMoodPerSecond\s+-10\.5024\s*$', rooms, re.M)
if not WITH_CONTENT:
    content_packages.unchecked('check_prison_mood', ['prison and torture mood values (own rows of config/rooms.cfg)'])
print('prison mood ok')
