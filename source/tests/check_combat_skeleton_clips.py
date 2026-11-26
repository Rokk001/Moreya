#!/usr/bin/env python3
"""Checks that the combat clips are present in the skeleton files, without a compiler.

The skeletons of the weapon-carrying creatures hold the clips the combat reactions play:
- Attack1Left: the mirror image of Attack1, for the second hand of creatures with two weapons,
- WeaponParry: the creature lifts its weapon in front of the body to parry a blow,
- the weapon bones Weapon_L and Weapon_R of the creatures that carry a weapon model.

The file is read as bytes; a clip or bone name is stored in the Ogre skeleton file as plain text,
so a name search is enough to see that the clip is in the file.

The skeletons lie in the public tree or in a content package (the creature figures in the package creatures) and are
found through scripts/content_packages.py; without the content the skeletons it holds are named as not checked.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import content_packages  # noqa: E402  (skeletons are read from the public tree or the content packages)

# Skeletons that carry the mirrored blow clip
ATTACK_LEFT = ['Adventurer', 'Cultist', 'Dwarf1', 'Dwarf2', 'Gnome', 'Goblin', 'Knight', 'Monk', 'Orc', 'RunelordDwarf']
# Skeletons that carry the parry clip
WEAPON_PARRY = ['Adventurer', 'Cultist', 'Dwarf2', 'Gnome', 'Goblin', 'Knight', 'LavaSpawn', 'Monk', 'NatureMonster',
                'Orc', 'RunelordDwarf']
# Skeletons that must carry the weapon bones (appended after the existing bones, so the meshes stay valid)
WEAPON_BONES = ['Dwarf1', 'Goblin', 'LavaSpawn', 'NatureMonster']
# Every clip a skeleton of the combat set already had stays in the file
BASE_CLIPS = [b'Idle', b'Walk', b'Attack1']


def read_skeleton(name):
    """Returns the bytes of models/<name>.skeleton from the public tree or a content package, or None when the content
    that holds it is not present."""
    path = content_packages.data_file(ROOT, 'models/' + name + '.skeleton')
    if path is None:
        if content_packages.has_content(ROOT):
            raise FileNotFoundError('models/' + name + '.skeleton')
        return None
    with open(str(path), 'rb') as handle:
        return handle.read()


def main():
    """Checks every skeleton of the combat set that is present and prints each failure; returns the exit code."""
    failures = []
    missing = []
    for name in sorted(set(ATTACK_LEFT + WEAPON_PARRY + WEAPON_BONES)):
        data = read_skeleton(name)
        if data is None:
            missing.append(name + '.skeleton')
            continue
        if not data.startswith(b'\x00\x10[Serializer_v1.80]'):
            failures.append(name + ': not an Ogre skeleton file (version 1.80)')
        for clip in BASE_CLIPS:
            if clip not in data:
                failures.append(name + ': base clip ' + clip.decode() + ' missing')
        if name in ATTACK_LEFT and b'Attack1Left' not in data:
            failures.append(name + ': clip Attack1Left missing')
        if name in WEAPON_PARRY and b'WeaponParry' not in data:
            failures.append(name + ': clip WeaponParry missing')
        if name in WEAPON_BONES and (b'Weapon_L' not in data or b'Weapon_R' not in data):
            failures.append(name + ': weapon bones Weapon_L/Weapon_R missing')
    if failures:
        for failure in failures:
            print('FAIL', failure)
        return 1
    content_packages.unchecked('check_combat_skeleton_clips', missing)
    print('ok: %d skeletons carry the combat clips and weapon bones'
          % (len(set(ATTACK_LEFT + WEAPON_PARRY + WEAPON_BONES)) - len(missing)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
