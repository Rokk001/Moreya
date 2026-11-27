"""Check config/portrait-tints.cfg and the code that applies it to the profile portraits.

The tint config and the portraits lie in the content packages (scripts/content_packages.py); without the content only
the code is checked and they are named as not checked."""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
sys.path.insert(0, str(repo / 'tools/portraits'))
import preview_tints as tints

# The tint config and the portraits lie in the content packages (core-config, core-portraits)
if not content_packages.has_content(repo):
    content_packages.unchecked('check_creature_portrait_tints', ['config/portrait-tints.cfg', 'portrait textures'])
    portraits = None
else:
    # load_config() applies the same parsing rules as PortraitTint::loadFromFile(): every line the game
    # would reject (for example a commented-out [Palette] opener) is reported here
    palettes, portraits, errors = tints.load_config(content_packages.resolve(repo, 'config/portrait-tints.cfg'))
    assert not errors, 'portrait-tints.cfg would not load in game: ' + '; '.join(errors)

    required = ('Kobold Dwarf1 Dwarf2 RunelordDwarf Gnome Adventurer Monk Knight Wizard Defender Cultist Elf DarkElf '
                'Goblin Orc Troll Lizardman').split()
    for mesh in required:
        assert mesh + '.mesh' in portraits and portraits[mesh + '.mesh'], 'no tint regions for ' + mesh

    # Every gender image has its own regions (the base regions do not fit another painting)
    for image in content_packages.data_glob(repo, 'materials/textures', 'portrait-*.mesh-*.png'):
        key = image.name[len('portrait-'):-len('.png')]
        assert key in portraits and portraits[key], 'no tint regions for gender image ' + image.name

    for mesh, regions in portraits.items():
        assert content_packages.data_file(repo, 'materials/textures/portrait-%s.png' % mesh) is not None, 'no portrait for ' + mesh
        for region_name, region in regions:
            where = '%s/%s' % (mesh, region_name)
            if 'palette' in region:
                assert region['palette'] in palettes, where + ': unknown palette'
            else:
                assert len(region['shift']) == 3, where
            x0, y0, x1, y1 = region['box']
            assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, where + ': box'
            assert len(region.get('not', [])) % 4 == 0, where + ': not'
            assert len(region['hue']) == 2 and len(region['sat']) == 2 and len(region['val']) == 2, where
            assert 0 <= region['sat'][0] <= region['sat'][1] <= 1 and 0 <= region['val'][0] <= region['val'][1] <= 1, where

creature = (repo / 'source/entities/Creature.cpp').read_text()
# The Dungeonbook falls back to the round tinted portrait (the shared profile page that used the square one was deleted,
# owner decision 2026-11-18)
assert 'getCircularCreatureProfilePortraitImage(creatureName, definition->getMeshName(), profile.mGender)' in (
    repo / 'source/render/SocialWindow.cpp').read_text()
assert 'clearCreatureProfilePortraits();' in (repo / 'source/modes/GameMode.cpp').read_text()
assert 'render/PortraitTint.cpp' in (repo / 'CMakeLists.txt').read_text()
print('portrait tints ok: %s meshes' % ('no' if portraits is None else len(portraits)))
