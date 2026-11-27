"""Static armament config, asset, skeleton and production-source checks; compiles nothing.

Models, skeletons, materials and textures are found in the public tree or the content packages
(scripts/content_packages.py), their CREDITS rows in the public CREDITS or in the CREDITS of the content repository;
without the content the files that lie in a package and their rows are named as not checked."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402
# Roster change (CREATURE-ROSTER W4a): the equipment column of the roster plan (sections 2-4) with the equipment that exists today;
# the weapons still missing (mace, spear, cleaver, bombs, throwing spears) are an open item of the content split
ASSIGNMENTS = {
    'Troll': 'Club', 'PitDemon': 'Trident', 'Cultist': 'RitualDagger', 'Adventurer': 'BasicSword',
    'Skeleton': 'BasicSword', 'Wizard': 'Staff', 'Lich': 'StaffLich', 'LizardMan': 'Staff',
    'RunelordDwarf': 'BasicHammer', 'Priestess': 'Staff', 'Cyclops': 'Club', 'Minotaur': 'BasicAxe',
}
UNCHANGED = {
    'Kobold': ('KoboldPick', 'none'), 'DwarfWorker': ('Pickaxe', 'none'), 'Goblin': ('Knife', 'none'),
    'Knight': ('RustySword', 'RustyShield'), 'Orc': ('HandAxe', 'RustyShield'),
    'Dwarf2': ('BasicHammerDwarf2', 'RustyShield'), 'Paladin': ('none', 'RustyShield'),
    'DarkElf': ('Knife', 'Knife'), 'Elf': ('none', 'Bow'),
    'Defender': ('DefenderWeapon', 'none'),
}
UNARMED = ('Monk', 'Hunter', 'Vampire', 'Ghoul', 'Butcher', 'Banshee', 'Witch', 'CaveHornet', 'CrystalGolem',
           'Werewolf', 'Gnoll', 'Gnome', 'Dragon', 'Champion')
TYPES = {
    'sword': (('RustySword', 'BasicSword', 'ShortSword', 'Sabre', 'T2SwordGood'), 1),
    'dagger': (('Knife', 'RitualDagger'), 1),
    'axe': (('BasicAxe', 'BasicAxeOrc'), 2),
    'staff': (('Staff', 'StaffLich'), 2), 'bow': (('Bow',), 2), 'crossbow': (('Crossbow',), 2),
    'tool': (('KoboldPick', 'Pickaxe'), 1), 'club': (('Club',), 1), 'spear': (('Trident',), 2),
    'wand': (('Wand',), 1),
}
EXPECTED_TYPES = {name: (kind, hands) for kind, (names, hands) in TYPES.items() for name in names}
EXPECTED_TYPES.update({name: ('sword', 2) for name in ('Longsword', 'T3SwordGood', 'T4SwordGood', 'DefenderWeapon')})
EXPECTED_TYPES.update({name: ('hammer', 1) for name in ('BasicHammer', 'BasicHammerDwarf2')})
EXPECTED_TYPES.update({name: ('hammer', 2) for name in ('T2HammerGood', 'T3HammerGood', 'T4HammerGood')})
EXPECTED_TYPES['HandAxe'] = ('axe', 1)
EXPECTED_TYPES.update({name: ('shield', 1) for name in ('RustyShield', 'Roundshield', 'BasicShield')})
EXPECTED_TYPES.update({f'T{tier}Shield{side}': ('shield', 1) for tier in (2, 3, 4) for side in ('Good', 'Evil')})
# The skeleton file of each armed creature class (the skeleton of its MeshName in creatures.cfg; the class Dwarf1 uses
# Jaeger.mesh) and the bone that holds its Weapon_R mount: the right hand bone RightHand of the 24-bone humanoid rig of
# the content package creatures, the same for all twelve figures
PARENTS = {
    'Orc': ('Orc', 'RightHand'), 'Troll': ('Troll', 'RightHand'), 'Cultist': ('Cultist', 'RightHand'),
    'Gnome': ('Gnome', 'RightHand'), 'Adventurer': ('Adventurer', 'RightHand'),
    'Dwarf1': ('Jaeger', 'RightHand'), 'Dwarf2': ('Dwarf2', 'RightHand'), 'Wizard': ('Wizard', 'RightHand'),
    'LizardMan': ('Lizardman', 'RightHand'), 'Skeleton': ('skeleton', 'RightHand'),
    'Lich': ('lich', 'RightHand'), 'PitDemon': ('PitDemon', 'RightHand'),
}
NEW_WEAPONS = {'HandAxe': 2, 'Club': 2, 'Trident': 4, 'RitualDagger': 1, 'Wand': 2}


# Read a tracked production input without invoking any asset tools; a data table of config/ comes with its own rows
# from the content packages, as the game reads it.
def read(path):
    if path.startswith('config/'):
        return content_packages.read_text(ROOT, path)
    return (ROOT / path).read_text(encoding='utf-8')


# The file of a game data path in the public tree or a content package; None only when the content is not present.
def data(path):
    found = content_packages.data_file(ROOT, path)
    if found is None and content_packages.has_content(ROOT):
        return ROOT / path  # the content is present, so a missing file fails
    return found


# Parse named equipment or creature definitions, ignoring comments and nested skill rows.
def definitions(text, tag):
    text = text[text.rindex('[' + tag + 'Definitions]'):]
    result = {}
    for block in re.findall(r'\[' + tag + r'\](.*?)\[/' + tag + r'\]', text, re.S):
        fields = dict(re.findall(r'^\s+(\w+)\s+([^\s#]+)\s*$', block, re.M))
        assert fields['Name'] not in result, fields['Name']
        result[fields['Name']] = fields
    return result


# Extract a source function with balanced braces so nested blocks remain covered.
def body(source, signature):
    start = source.index('{', source.index(signature))
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start + 1:end - 1]


# Read Ogre bone and hierarchy chunks directly; string bytes are outside their recorded sizes.
def skeleton_bones(path):
    data = path.read_bytes()
    assert struct.unpack_from('<H', data)[0] == 0x1000, path
    offset = data.index(b'\n') + 1
    bones, parents = {}, {}
    while offset < len(data):
        kind, size = struct.unpack_from('<HI', data, offset)
        assert size >= 6, (path, offset)
        if kind == 0x2000:
            end = data.index(b'\n', offset + 6)
            name = data[offset + 6:end].decode('utf-8')
            handle = struct.unpack_from('<H', data, end + 1)[0]
            assert handle not in bones, (path, handle)
            bones[handle] = (name, struct.unpack_from('<7f', data, end + 3))
            offset += size + end - (offset + 6) + 1
        elif kind == 0x3000:
            child, parent = struct.unpack_from('<HH', data, offset + 6)
            assert child not in parents, (path, child)
            parents[child] = parent
            offset += size
        elif kind == 0x1010:
            offset += size
        else:
            assert kind in (0x4000, 0x5000), (path, hex(kind))
            break
    return bones, parents


# Check exact metadata, damage- and defence-free assigned weapons and otherwise matching scaled copies.
def check_equipment(equipment):
    assert set(equipment) == set(EXPECTED_TYPES), set(equipment) ^ set(EXPECTED_TYPES)
    for name, (kind, hands) in EXPECTED_TYPES.items():
        assert equipment[name].get('WeaponType') == kind, (name, 'WeaponType')
        assert equipment[name].get('Hands') == str(hands), (name, 'Hands')
    for name, cooldown in NEW_WEAPONS.items():
        item = equipment[name]
        assert item['MeshName'] == name + '.mesh', name
        assert int(item['CooldownNbTurns']) == cooldown, name
        for field in ('PhysicalDamage', 'MagicalDamage', 'ElementDamage', 'PhysicalDefense',
                      'MagicalDefense', 'ElementDefense', 'PhysicalDamageMin', 'MagicalDamageMin',
                      'ElementDamageMin', 'AttackRating', 'DefenseRating'):
            assert float(item.get(field, '0')) == 0, (name, field)
        assert tuple(float(item[key]) for key in ('ParryBase', 'ParryPerLevel', 'ParryMax')) == (10.5, 0, 15), name
    for name in ('BasicSword', 'BasicAxe', 'BasicHammer', 'Staff', 'BasicAxeOrc',
                 'BasicHammerDwarf2', 'StaffLich'):
        for field in ('PhysicalDamage', 'PhysicalDamageMin', 'MagicalDamage', 'MagicalDamageMin',
                      'ElementDamage', 'ElementDamageMin', 'PhysicalDefense', 'MagicalDefense', 'ElementDefense'):
            assert float(equipment[name][field]) == 0, (name, field)
    # The copies differ from their originals only in Name, MeshName and the name the player reads (DisplayName,
    # plan INGAME-QS-11 K6), which every equipment has
    for name, original in (('BasicAxeOrc', 'BasicAxe'), ('BasicHammerDwarf2', 'BasicHammer'), ('StaffLich', 'Staff')):
        expected = dict(equipment[original], Name=name, MeshName=name + '.mesh')
        expected.pop('DisplayName', None)
        copy = dict(equipment[name])
        copy.pop('DisplayName', None)
        assert copy == expected, (name, copy, expected)
    display_names = re.findall(r'^\[Equipment\]\s*\n\s+Name\s+\S+\s*\n\s+DisplayName\s+\S',
                               read('config/equipments.cfg'), re.M)
    assert len(display_names) == len(equipment), ('every equipment has a DisplayName', len(display_names),
                                                  len(equipment))


# Check all requested assignments and reject any occupied second hand beside a two-handed item.
def check_creatures(creatures, equipment):
    for name, weapon in ASSIGNMENTS.items():
        assert creatures[name].get('WeaponSpawnR') == weapon, name
        assert creatures[name].get('WeaponSpawnL', 'none') == 'none', name
    for name, expected in UNCHANGED.items():
        assert tuple(creatures[name].get('WeaponSpawn' + hand, 'none') for hand in ('R', 'L')) == expected, name
    for name in UNARMED:
        assert all(creatures[name].get('WeaponSpawn' + hand, 'none') == 'none' for hand in ('R', 'L')), name
    for name, creature in creatures.items():
        held = [creature.get('WeaponSpawn' + hand, 'none') for hand in ('R', 'L')]
        for weapon in held:
            if weapon != 'none':
                assert weapon in equipment, (name, weapon)
                assert equipment[weapon]['Hands'] != '2' or held.count('none') == 1, (name, held)
    for name, (filename, parent_name) in PARENTS.items():
        skeleton = data('models/' + filename + '.skeleton')
        if skeleton is None:
            content_packages.unchecked('check_creature_armament', ['models/' + filename + '.skeleton mount'])
            continue
        bones, parents = skeleton_bones(skeleton)
        mounts = [handle for handle, (bone_name, _) in bones.items() if bone_name == 'Weapon_R']
        assert len(mounts) == 1, name
        assert bones[parents[mounts[0]]][0] == parent_name, (name, parent_name)


# Require every delivered asset/tool and its explicit credit row, plus the shared material binding.
def check_assets():
    paths = ['models/' + name + '.mesh' for name in NEW_WEAPONS]
    paths += ['models/' + name + '.mesh' for name in ('BasicAxeOrc', 'BasicHammerDwarf2', 'StaffLich')]
    paths += ['models/' + name + '.skeleton' for name in ('StaffLich', 'skeleton', 'lich', 'PitDemon')]
    paths += ['materials/scripts/ArmamentWeapons.material', 'materials/textures/ArmamentWeaponsSurface.png',
              'tools/gen_armament_weapons.py', 'tools/gen_scaled_weapons.py', 'tools/add_weapon_bones.py',
              'tools/blender-assets/armament_blend.py', 'tools/blender-assets/armament_preview.py',
              'source/tests/check_creature_armament.py']
    # The rows of the files of the content packages lie in the CREDITS of the content repository
    credits = read('CREDITS')
    content = campaign_packages.content_repository(ROOT)
    if content is not None and (content / 'CREDITS').is_file():
        credits += '\n' + (content / 'CREDITS').read_text(encoding='utf-8')
    absent = []
    for path in paths:
        if data(path) is None:
            absent.append(path)  # a file of a content package and its row are not checked without the content
            continue
        assert data(path).is_file(), path
        assert re.search(r'^' + re.escape(path) + r'\s+', credits, re.M), 'Missing credit: ' + path
    if absent:
        content_packages.unchecked('check_creature_armament', absent)
        return
    material = data('materials/scripts/ArmamentWeapons.material').read_text(encoding='utf-8')
    assert re.search(r'^material\s+ArmamentWeapons\s*$', material, re.M)
    assert re.search(r'\btexture\s+ArmamentWeaponsSurface\.png\b', material)
    texture = data('materials/textures/ArmamentWeaponsSurface.png').read_bytes()
    assert texture[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', texture[16:24]) == (64, 64)
    for name in NEW_WEAPONS:
        assert b'ArmamentWeapons' in data('models/' + name + '.mesh').read_bytes(), name
    assert b'StaffLich.skeleton' in data('models/StaffLich.mesh').read_bytes()


# Check actual client/server type mappings, serialization and the creature-only timing compensation path.
def check_source():
    weapon = read('source/entities/Weapon.cpp')
    for field in ('WeaponType', 'Hands'):
        assert 'nextParam == "' + field + '"' in weapon
        assert 'file << "    ' + field + '\\t"' in weapon
        assert 'os << weapon->m' + field + ';' in weapon
        assert 'is >> weapon->m' + field in weapon
    writer = body(weapon, 'void Weapon::writeWeaponDiff(')
    assert re.search(r'def1->mWeaponType != def2->mWeaponType\s*\|\|\s*'
                     r'def1->getWeaponType\(\) != def2->getWeaponType\(\)', writer), \
        'Explicit type overrides must survive a changed mesh on an inherited legacy definition'
    fallback = body(weapon, 'std::string Weapon::getWeaponType() const')
    assert 'if(!mWeaponType.empty())' in fallback and 'return mWeaponType;' in fallback
    for keyword in ('shield', 'bow', 'axe', 'hammer', 'mace', 'spear', 'lance', 'pike', 'dagger', 'knife', 'staff', 'wand'):
        assert 'mesh.find("' + keyword + '")' in fallback, keyword
    reaction = body(read('source/render/CreatureCombatReactions.cpp'), 'std::string weaponKind(')
    assert 'weapon->getWeaponType()' in reaction and 'getMeshName' not in reaction
    actual = {}
    for condition, kind in re.findall(r'if\((.*?)\)\s*return "(\w+)";', reaction):
        for name in re.findall(r'type == "(\w+)"', condition):
            actual[name] = kind
    expected = {'axe': 'Axe', 'shield': 'Shield', 'bow': 'Bow', 'crossbow': 'Bow',
                'club': 'Hammer', 'mace': 'Hammer', 'hammer': 'Hammer', 'scepter': 'Hammer',
                'spear': 'Spear', 'polearm': 'Spear', 'javelin': 'Spear', 'dagger': 'Dagger',
                'throwing': 'Dagger', 'claw': 'Dagger', 'staff': 'Staff', 'wand': 'Staff', 'orb': 'Staff'}
    assert actual == expected, (actual, expected)
    assert reaction.rstrip().endswith('return "Sword";')
    defence = read('source/entities/DefenceChance.h')
    assert body(defence, 'inline bool isShieldType(').strip() == 'return type == "shield";'
    parry = body(defence, 'inline bool isParryWeaponType(')
    assert set(re.findall(r'type == "(\w+)"', parry)) == {
        'sword', 'axe', 'dagger', 'club', 'mace', 'hammer', 'scepter', 'spear', 'polearm'}
    creature = read('source/entities/Creature.cpp')
    assert 'const std::string type = weapons[i]->getWeaponType();' in creature
    assert 'DefenceChance::isShieldType(type)' in creature
    assert 'DefenceChance::isParryWeaponType(type)' in creature
    melee = read('source/creatureskill/CreatureSkillMeleeFight.cpp')
    timing = melee[melee.index('uint32_t weaponCooldown = 0;'):melee.index('creatureDamage = CombatDamage::roll')]
    assert 'std::max(weaponCooldown, weapon->getCooldownNbTurns())' in timing
    assert 'weaponCooldown > getCooldownNbTurns() && getCooldownNbTurns() > 0' in timing
    assert 'static_cast<double>(weaponCooldown) / getCooldownNbTurns() : 1.0' in timing
    for channel in ('phyMin', 'phyMax', 'magMin', 'magMax', 'eleMin', 'eleMax'):
        assert channel + ' *= timingFactor;' in timing, channel
    assert melee.rfind('if(attackedObject->getObjectType() == GameEntityType::creature)', 0,
                       melee.index('uint32_t weaponCooldown = 0;')) >= 0
    cooldown = body(creature, 'double Creature::getAppliedCooldownNbTurns(')
    assert 'baseCooldown = std::max(baseCooldown, weaponCooldown);' in cooldown


# Run all static checks with clear failures while leaving build and runtime verification separate.
def main():
    # The equipment and creature rows are own rows of the content package core-config; without the content the
    # assignments, types and hands are named as not checked
    if content_packages.has_content(ROOT):
        equipment = definitions(read('config/equipments.cfg'), 'Equipment')
        creatures = definitions(read('config/creatures.cfg'), 'Creature')
        check_equipment(equipment)
        check_creatures(creatures, equipment)
    else:
        content_packages.unchecked('check_creature_armament', ['config/equipments.cfg and config/creatures.cfg rows'])
    check_assets()
    check_source()
    print('PASS: creature armament assignments, types, hands, skeleton mounts, assets, credits and source wiring')


if __name__ == '__main__':
    main()
