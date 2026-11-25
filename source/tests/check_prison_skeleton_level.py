#!/usr/bin/env python3
"""Check the prison skeleton level and its research bonuses."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: True when the content packages are present (the data tables come with their own rows)
WITH_CONTENT = content_packages.has_content(ROOT)
source = (ROOT / 'source/rooms/RoomPrison.cpp').read_text(encoding='utf-8')
assert re.search(r'prisonerLevel\s*=\s*creature->getLevel\(\)', source)
assert re.search(r'setLevel\(std::min<uint32_t>\(30,\s*prisonerLevel\s*\+', source)
assert 'PrisonSkeletonLevelBonus' in source and 'ResearchEffect::SkeletonLevel' in source
if WITH_CONTENT:
    rooms = content_packages.read_text(ROOT, 'config/rooms.cfg')
    assert re.search(r'^\s*PrisonSkeletonLevelBonus\s+0\s*$', rooms, re.M)
    assert not re.search(r'^\s*PrisonSkeletonBaseLevel\s+', rooms, re.M)
    skills = content_packages.read_text(ROOT, 'config/skills.cfg')
    assert re.search(r'^\s*roomPrison\s+SkeletonLevel\s+add\s+0\s+1\s+2\s*$', skills, re.M)
if not WITH_CONTENT:
    content_packages.unchecked('check_prison_skeleton_level', ['skeleton level values (own rows of config/rooms.cfg and config/skills.cfg)'])
print('prison skeleton level ok')
