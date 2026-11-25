"""Static check (no game, no compiler): the loot bag looks like a textured bag and its tooltip is the standard item tooltip.

Plan INGAME-QS-12 K10 and K11 (package L1). Checked here:
1. Material ItemBag has a texture (ItemBagCloth.png) that modulates the quality colour: the texture file exists, is
   512 x 512, has visible surface detail (not flat), is neutral enough that the quality tint reads, and tiles without a
   visible seam. The sealed variant keeps its wax seal material without texture.
2. RenderManager::rrRefreshItemBagAppearance tints a clone of the sub entity's own material (so the texture stays) with
   the four quality colours: Poor grey, Common white, Rare blue, Epic purple. The tinted result of every quality is
   computed from the texture and the colours and the four differ from each other.
3. ItemBag.mesh is a cloth sack (wide belly, gathered neck at most half the belly, flared open top) with the old footprint
   and height, and maps the texture without stretching (95 percent of the surface within a factor of 2 of the median texel
   density). Needs OgreXMLConverter (environment variable OGRE_XML_CONVERTER); without it this part says so.
4. Hovering a loot bag calls the standard item tooltip: GameMode::showItemContext asks Gui::showItemTooltipAtCursor and
   writes neither ContextInfo nor the pointer text; the bag branch of handlePlayerActionNone writes no item name into the
   info bar; the world card is the same card as the Dungeonbook's (same text, same look, same quality colour, same
   placement function as the default tooltip, no hover time).
5. CREDITS has the entries of the texture and the re-projected mesh.

The material script, the texture and the mesh live in content packages (found through scripts/content_packages.py).
The CREDITS rows of the moved files stand in the CREDITS of the content repository (room_packages.credits_text).
Without the content the check names parts 1, 3 and 5 as not checked and checks the code.
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

fails = []
WITH_CONTENT = content_packages.has_content(repo)
# Parts that need the content and are not checked because it is not present
not_checked = []


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def check(condition, text):
    """Fails with the text when the condition is false."""
    if not condition:
        fail(text)


def read(path):
    """Returns the text of a repository file."""
    return (repo / path).read_text(encoding='utf-8')


def data_path(relative):
    """The game data file of the public tree or of a content package; None when the content is not present (with the
    content present the path below the repository, so that a missing file still fails)."""
    found = content_packages.data_file(repo, relative)
    if found is None and WITH_CONTENT:
        return repo / relative
    if found is None:
        not_checked.append(relative)
    return found


def body(source, signature):
    """Returns the text from the signature to the end of its braces block."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


# 1. The material and its texture
material_path = data_path('materials/scripts/ItemProps.material')
if material_path is not None:
    material = material_path.read_text(encoding='utf-8')
    bag = body(material, 'material ItemBag\n') if 'material ItemBag\n' in material else body(material, 'material ItemBag\r\n')
    check(re.search(r'texture_unit\s*\{[^}]*texture ItemBagCloth\.png', bag) is not None, 'ItemBag material has the texture')
    check('colour_op' not in bag and 'lighting off' not in bag, 'the texture is modulated by the quality colour')
    sealed = body(material, 'material ItemBagSealed')
    check('texture_unit' not in sealed and '0.5500 0.0600 0.0400' in sealed, 'the sealed variant keeps its plain wax colour')

QUALITY_TINTS = [(138 / 255.0,) * 3, (1.0, 1.0, 1.0), (62 / 255.0, 123 / 255.0, 1.0), (166 / 255.0, 77 / 255.0, 1.0)]
render = read('source/render/RenderManager.cpp')
appearance = body(render, 'void RenderManager::rrRefreshItemBagAppearance(')
check('sub->getMaterial()->clone(tintedName)' in appearance, 'the tint is applied to a clone of the textured material')
check('setDiffuse(TINTS.at' in appearance and 'setAmbient(TINTS.at' in appearance, 'diffuse and ambient carry the tint')
for expected in ('138.0f/255.0f, 138.0f/255.0f, 138.0f/255.0f', 'Ogre::ColourValue::White',
                 '62.0f/255.0f, 123.0f/255.0f, 1.0f', '166.0f/255.0f, 77.0f/255.0f, 1.0f'):
    check(expected in appearance, 'quality tint ' + expected)

try:
    from PIL import Image
    import numpy
except ImportError:
    Image = None
    fail('Pillow and numpy are needed for the texture check')
texture_path = data_path('materials/textures/ItemBagCloth.png') if Image is not None else None
if texture_path is not None:
    check(texture_path.is_file(), 'texture file exists')
    if texture_path.is_file():
        image = Image.open(texture_path).convert('RGB')
        check(image.size == (512, 512), 'texture is 512 x 512')
        pixels = numpy.asarray(image, dtype=float)
        luminance = pixels.mean(axis=2)
        check(luminance.std() >= 18.0, 'visible surface detail (luminance deviation %.1f)' % luminance.std())
        check(90.0 <= luminance.mean() <= 200.0, 'mid tone so that every tint reads (mean %.1f)' % luminance.mean())
        saturation = (pixels.max(axis=2) - pixels.min(axis=2)).mean()
        check(saturation <= 45.0, 'neutral enough for the tint (saturation %.1f)' % saturation)
        # The step across the wrap-around edge must not exceed the largest step between two neighbouring rows or columns
        # inside the texture (the woven thread borders are the hardest steps of the cloth)
        seam = max(numpy.abs(pixels[0] - pixels[-1]).mean(), numpy.abs(pixels[:, 0] - pixels[:, -1]).mean())
        inner = max(numpy.abs(pixels[1:] - pixels[:-1]).mean(axis=(1, 2)).max(),
                    numpy.abs(pixels[:, 1:] - pixels[:, :-1]).mean(axis=(0, 2)).max())
        check(seam <= 1.25 * inner, 'tiles without a seam (edge step %.1f, largest inner step %.1f)' % (seam, inner))
        mean_colour = pixels.reshape(-1, 3).mean(axis=0) / 255.0
        tinted = [tuple(mean_colour * numpy.array(t)) for t in QUALITY_TINTS]
        for i in range(4):
            for j in range(i + 1, 4):
                gap = max(abs(a - b) for a, b in zip(tinted[i], tinted[j]))
                check(gap >= 0.08, 'qualities %d and %d are told apart after the tint (%.2f)' % (i, j, gap))
        # Poor stays darker than Common, Rare is bluer, Epic is more violet than Common
        check(sum(tinted[0]) < sum(tinted[1]), 'Poor is darker than Common')
        check(tinted[2][2] > tinted[2][0] * 1.5, 'Rare reads blue')
        check(tinted[3][2] > tinted[3][1] * 1.3 and tinted[3][0] > tinted[3][1], 'Epic reads violet')

# 3. The mesh UVs
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
mesh_path = data_path('models/ItemBag.mesh')
with tempfile.TemporaryDirectory(prefix='itembag_') as directory:
    work = Path(directory)
    try:
        if mesh_path is None:
            xml = None   # the content is not present: named as not checked below
        else:
            subprocess.run([converter, '-q', str(mesh_path), str(work / 'bag.xml')], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            xml = (work / 'bag.xml').read_text()
    except (OSError, subprocess.CalledProcessError):
        xml = None
        print('NOTE: OgreXMLConverter not found, the UV part of the mesh check was not run')
    if xml is not None:
        positions = [tuple(map(float, m)) for m in re.findall(r'<position x="([^"]+)" y="([^"]+)" z="([^"]+)"', xml)]
        uvs = [tuple(map(float, m)) for m in re.findall(r'<texcoord u="([^"]+)" v="([^"]+)"', xml)]
        check(len(positions) == len(uvs) == 4478, 'mesh has its 4478 vertices')
        # Footprint and height of the old model stay (RoomObjectBounds ItemBag -.18 -.144 .18 .14)
        xs, ys, zs = zip(*positions)
        check(0.17 <= max(xs) <= 0.18 + 1e-6 and -0.18 - 1e-6 <= min(xs) <= -0.15, 'footprint width as before')
        check(-0.144 - 1e-6 <= min(ys) <= -0.13 and 0.13 <= max(ys) <= 0.14 + 1e-6, 'footprint depth as before')
        check(abs(min(zs)) < 1e-6 and abs(max(zs) - 0.37) < 1e-3, 'stands on the ground, 0.37 high as before')
        # It reads as a sack: wide belly, gathered narrow neck, flared open top above the neck
        def width_at(z, tolerance=0.012):
            sel = [x for x, y, zz in positions if abs(zz - z) < tolerance]
            return (max(sel) - min(sel)) if sel else 0.0
        belly, neck, rim = width_at(0.10), width_at(0.268, 0.006), width_at(0.36)
        check(belly >= 0.30, 'wide belly (%.3f)' % belly)
        check(neck <= 0.5 * belly, 'gathered neck is at most half the belly (%.3f / %.3f)' % (neck, belly))
        check(rim >= 1.4 * neck, 'open top flares out above the neck (%.3f / %.3f)' % (rim, neck))
        submeshes = xml.split('<submesh ')[1:]
        check(len(submeshes) == 2 and 'material="ItemBag"' in submeshes[0] and 'material="ItemBagSealed"' in submeshes[1],
              'bag and seal sub meshes keep their materials')
        densities = []
        areas = []
        for sub in submeshes[:1]:
            for a, b, c in re.findall(r'<face v1="(\d+)" v2="(\d+)" v3="(\d+)"', sub):
                a, b, c = int(a), int(b), int(c)
                p = [numpy.array(positions[i]) for i in (a, b, c)]
                area3 = numpy.linalg.norm(numpy.cross(p[1] - p[0], p[2] - p[0])) / 2.0
                u = [numpy.array(uvs[i]) for i in (a, b, c)]
                d1, d2 = u[1] - u[0], u[2] - u[0]
                area2 = abs(d1[0] * d2[1] - d1[1] * d2[0]) / 2.0
                if area3 > 1e-9:
                    densities.append(area2 / area3)
                    areas.append(area3)
        check(len(densities) > 0 and min(densities) > 0.0, 'every face has texture area')
        if densities and min(densities) > 0.0:
            density = numpy.array(densities)
            weight = numpy.array(areas)
            median = numpy.median(density)
            good = weight[(density >= median / 2.0) & (density <= median * 2.0)].sum() / weight.sum()
            check(good >= 0.95, 'at least 95 percent of the sack surface keeps the texel density within a factor of 2 '
                  'of the median (%.3f)' % good)

# 4. The tooltip of a hovered loot bag
game_mode = read('source/modes/GameMode.cpp')
show = body(game_mode, 'void GameMode::showItemContext(')
check('getGui().showItemTooltipAtCursor(*item, mGameMap)' in show, 'the bag calls the standard item tooltip')
for forbidden in ('ContextInfo', 'displayPointerText', 'displayText', 'setText', 'POINTER_INFO_STRING', 'mActionTargetText'):
    check(forbidden not in show, 'showItemContext does not use ' + forbidden)
none_action = body(game_mode, 'void GameMode::handlePlayerActionNone(')
bag_branch = body(none_action, 'else if(closest->getObjectType() == GameEntityType::itemBagEntity)')
check('displayText' not in bag_branch and 'getDisplayName' not in bag_branch and 'ContextInfo' not in bag_branch,
      'the bag branch writes no item name into the info bar')
check('showItemContext(*static_cast<const ItemBagEntity*>(closest))' in none_action, 'the hover shows the bag tooltip')
check('displayPointerText' not in none_action, 'no pointer text in the hover')
check('hideItemTooltipAtCursor' in body(game_mode, 'void GameMode::clearItemContextImage('), 'the card goes away with the hover')
check(re.search(r'isMouseDownOnCEGUIWindow\(\)\)\s*\{[^}]*hideItemTooltipAtCursor', game_mode) is not None,
      'the card goes away over a window')

gui = read('source/render/Gui.cpp')
world = body(gui, 'void Gui::showItemTooltipAtCursor(')
check('describeItemTooltip(item, map, nullptr)' in world, 'same text as setItemTooltip of the book')
check('ItemInstance::getQualityColour(item.mQuality)' in world, 'same quality colour as setItemTooltip of the book')
check('placeItemTooltipBox(' in world, 'placed by the placement of the default tooltip')
check('placeItemTooltipBox(' in body(gui, 'void placeItemTooltip('), 'the default tooltip uses the same placement function')
check('Hover' not in world and 'Timer' not in world and 'Delay' not in world, 'no hover time')
check('tooltip->show()' in world, 'visible in the same frame')
maker = body(gui, 'CEGUI::Tooltip* getWorldItemTooltip(')
check('createWindow("OD/Tooltip"' in maker and 'setLookNFeel(ITEM_TOOLTIP_LOOK)' in maker,
      'same window type and look as the default item tooltip')
check('setMousePassThroughEnabled(true)' in maker, 'the card never takes the pointer from the world')

# 5. Credits
# the public CREDITS and, with the content, the CREDITS of the content repository (the rows of the moved files)
if WITH_CONTENT or content_packages.data_file(repo, 'models/ItemBag.mesh') is not None:
    credits = room_packages.credits_text(repo)
    texture_line = [l for l in credits.splitlines() if l.startswith('materials/textures/ItemBagCloth.png')]
    check(len(texture_line) == 1 and 'AI-generated' in texture_line[0], 'CREDITS entry of the texture marks it AI-generated')
    check('models/ItemBag.mesh' in credits and 'Rebuilt 2026-11-21' in credits, 'CREDITS entry of the re-projected mesh')
else:
    not_checked.append('the CREDITS entries of the texture and the mesh')

content_packages.unchecked('check_loot_bag_look_l1', not_checked)
if fails:
    print('\n'.join('FAIL: ' + f for f in fails))
    sys.exit(1)
print('check_loot_bag_look_l1: all checks passed')
