"""Creature skill icons: every skill of config/creatureSkills.cfg has an image named by its skill id in
gui/CreatureSkillIcons.imageset, the imageset is loaded by gui/ODSkin.scheme, every image lies inside
gui/CreatureSkillIcons.png and the picture has a CREDITS row.

Expected: 124 skill ids (90 path skills and 34 tier-4 skills), counted once in config/creatureSkills.cfg.

Calls (from the repository root):
  python source/tests/check_creature_skill_icons.py   plain file checks, no compiler, no game

The skill catalog, the imageset and the picture lie in the content packages (scripts/content_packages.py); without
the content they and their CREDITS rows (CREDITS of the content repository) are named as not checked and the scheme
is still checked.
"""
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

# Skill ids of config/creatureSkills.cfg: 90 path skills and 34 tier-4 skills
EXPECTED_SKILLS = 124
EXPECTED_PATH_SKILLS = 90
EXPECTED_TIER_FOUR = 34

errors = []


def read(path):
    """Returns the text of a repository file or of a game data file of the public tree or a content package."""
    return content_packages.read_text(root, path)


def skill_ids():
    """Returns (path skill ids, tier-4 skill ids) of config/creatureSkills.cfg in config order."""
    path_ids = []
    tier_four = []
    block = None
    for raw in read('config/creatureSkills.cfg').splitlines():
        line = raw.split('#', 1)[0].strip()
        if line in ('[Skill]', '[TierFour]', '[Template]'):
            block = line
        elif line.startswith('[/'):
            block = None
        elif block == '[Skill]' and re.match(r'Id\s', line):
            path_ids.append(line.split(None, 1)[1])
        elif block == '[TierFour]' and re.match(r'Creature\s', line):
            tier_four.append('T4_' + line.split(None, 1)[1])
    return path_ids, tier_four


# Returns (width, height) of a PNG file from its header.
def png_size(path):
    data = content_packages.resolve(root, path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path + ' is not a PNG'
    return struct.unpack('>II', data[16:24])


# The skill catalog, the imageset and the picture lie in the content packages (core-config, core-gui)
ids = []
if not content_packages.has_content(root):
    content_packages.unchecked('check_creature_skill_icons', ['config/creatureSkills.cfg', 'gui/CreatureSkillIcons.imageset',
                                                          'gui/CreatureSkillIcons.png', 'their CREDITS rows'])
else:
    path_ids, tier_four = skill_ids()
    ids = path_ids + tier_four
    if len(path_ids) != EXPECTED_PATH_SKILLS:
        errors.append('path skills: expected %d, found %d' % (EXPECTED_PATH_SKILLS, len(path_ids)))
    if len(tier_four) != EXPECTED_TIER_FOUR:
        errors.append('tier-4 skills: expected %d, found %d' % (EXPECTED_TIER_FOUR, len(tier_four)))
    if len(ids) != EXPECTED_SKILLS or len(set(ids)) != EXPECTED_SKILLS:
        errors.append('skill ids: expected %d distinct, found %d (%d distinct)' % (EXPECTED_SKILLS, len(ids), len(set(ids))))

    imageset = ET.fromstring(read('gui/CreatureSkillIcons.imageset'))
    if imageset.get('name') != 'CreatureSkillIcons' or imageset.get('imagefile') != 'CreatureSkillIcons.png':
        errors.append('gui/CreatureSkillIcons.imageset: name or imagefile wrong')
    width, height = png_size('gui/CreatureSkillIcons.png')
    images = {}
    for image in imageset.findall('Image'):
        name = image.get('name')
        x, y = int(image.get('xPos')), int(image.get('yPos'))
        w, h = int(image.get('width')), int(image.get('height'))
        images[name] = (x, y, w, h)
        if x < 0 or y < 0 or x + w > width or y + h > height:
            errors.append('image %s lies outside gui/CreatureSkillIcons.png' % name)
    for skill_id in ids:
        if skill_id not in images:
            errors.append('skill %s has no image in gui/CreatureSkillIcons.imageset' % skill_id)
    for name in images:
        if name not in ids:
            errors.append('image %s is no skill id of config/creatureSkills.cfg' % name)

scheme = ET.fromstring(read('gui/ODSkin.scheme'))
if scheme.find("Imageset[@filename='CreatureSkillIcons.imageset'][@name='CreatureSkillIcons']") is None:
    errors.append('gui/ODSkin.scheme does not load CreatureSkillIcons.imageset')

# The rows of the picture and the imageset lie in the CREDITS of the content repository, with the files
if content_packages.has_content(root):
    credits = read('CREDITS') + '\n' + (campaign_packages.content_repository(root) / 'CREDITS').read_text(encoding='utf-8')
    for asset in ('gui/CreatureSkillIcons.png', 'gui/CreatureSkillIcons.imageset'):
        if asset not in credits:
            errors.append('CREDITS has no row for ' + asset)

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: %d skill ids, each with an image in gui/CreatureSkillIcons.imageset' % len(ids))
