"""The mana crystal, the soul crystal, the reward casket, the research tome and the trap crate are the Meshy models of their approved Codex
templates, at the size of the models they replace.

Two parts, no compiler:
  wiring
      a finished trap that is not a door shows the trap crate (CraftedTrap uses TRAP_CRATE_MESH "TrapCrate" for every
      trap type except the six door types, which keep their own mesh); the item meshes keep their names (ManaCrystal,
      SoulCrystal, MysteryBox).
  assets (OgreXMLConverter converts the shipped binaries)
      every model: one submesh with its own material, defined in a material script with its 512 x 512 texture, base at
      z = 0 (the tome floats 0.14 above it like the tome it replaces), the fixed height, at most 4000 triangles; the casket
      is bound to MysteryBox.skeleton with every vertex on its one bone, the tome to Grimoire.skeleton with every vertex on
      Bone1 (their Loop clips turn and float them), and the old normal maps of both are gone.

Fixed expected values of this branch (counted once): ManaCrystal 0.33 high (material ManaCrystalMeshy, 3038
triangles), SoulCrystal 0.35 (SoulCrystalMeshy, 2991), MysteryBox 0.195 (MysteryBox, 3234), TrapCrate 0.30 (TrapCrate,
3058), Grimoire 0.14 to 0.628 (Grimoire, 2715); limit 4000 triangles each.

Without --assets the models, materials and textures are read from the public tree or the content packages
(scripts/content_packages.py); without the content the models are named as not checked.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_item_props_meshy.py [--assets <folder with models/ and materials/>]
"""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

CHECK = 'check_item_props_meshy'
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else ROOT
#: mesh: (material, material script, texture, height, triangles counted, skeleton)
MODELS = {
    'ManaCrystal': ('ManaCrystalMeshy', 'ItemCrystals.material', 'ManaCrystalMeshy.png', 0.33, 3038, None),
    'SoulCrystal': ('SoulCrystalMeshy', 'ItemCrystals.material', 'SoulCrystalMeshy.png', 0.35, 2991, None),
    'MysteryBox': ('MysteryBox', 'MysteryBox.material', 'MysteryBox.png', 0.195, 3234, 'MysteryBox.skeleton'),
    'TrapCrate': ('TrapCrate', 'TrapCrate.material', 'TrapCrate.png', 0.30, 3058, None),
    'Grimoire': ('Grimoire', 'Grimoire.material', 'Grimoire.png', 0.628, 2715, 'Grimoire.skeleton'),
}
#: lowest point of a model above the floor (the tome floats), and the bone index of the vertices of a rigged model
BASE = {'Grimoire': 0.14}
BONE = {'MysteryBox': '0', 'Grimoire': '1'}
TRIANGLE_LIMIT = 4000
DOORS = ('doorWooden', 'doorIronbound', 'doorSteel', 'doorBarricade', 'doorSecret', 'doorRuned')
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='item_props_'))
started = time.monotonic()


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def asset(relative):
    """Returns the path of a shipped asset: below --assets when given, else in the public tree or a content package."""
    if ASSETS != ROOT:
        return ASSETS / relative
    return content_packages.resolve(ROOT, relative)


def convert(name):
    """Converts a shipped binary mesh to Ogre XML and returns its parsed root, None if it is missing."""
    source = asset('models/' + name)
    if not source.exists():
        return None
    target = work / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(work / 'convert.log'), str(source), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ET.parse(str(target)).getroot()


# ================================================================================================ wiring
crafted = (ROOT / 'source/entities/CraftedTrap.cpp').read_text(encoding='utf-8')
if 'const std::string TRAP_CRATE_MESH = "TrapCrate";' not in crafted:
    fail('CraftedTrap.cpp: TRAP_CRATE_MESH "TrapCrate" missing')
chooser = re.search(r'const std::string& getCraftedTrapMesh\(TrapType type\)\s*\{(.*?)\n\}', crafted, re.S)
if chooser is None or any('TrapType::' + door not in chooser.group(1) for door in DOORS) or \
        'return door ? TrapManager::getMeshFromTrapType(type) : TRAP_CRATE_MESH;' not in chooser.group(1):
    fail('getCraftedTrapMesh does not give the crate to every trap and its own mesh to the six doors')
if 'RenderedMovableEntity(gameMap, workshopName, getCraftedTrapMesh(trapType), 0.0f, false)' not in crafted:
    fail('a new crafted trap does not take the mesh of getCraftedTrapMesh')
trap_types = (ROOT / 'source/traps/TrapType.h').read_text(encoding='utf-8')
door_names = set(re.findall(r'\b(door[A-Z]\w*)\b', trap_types))
if door_names != set(DOORS):
    fail('TrapType.h names the doors %s, expected %s' % (sorted(door_names), sorted(DOORS)))
for path, text in (('source/entities/ItemBagEntity.cpp', 'LEVEL_CRYSTAL_MESH = "SoulCrystal"'),
                   ('source/entities/ItemBagEntity.cpp', 'MANA_CRYSTAL_MESH = "ManaCrystal"'),
                   ('source/giftboxes/GiftBoxItem.cpp', '"MysteryBox"')):
    if text not in (ROOT / path).read_text(encoding='utf-8'):
        fail('%s: %s missing' % (path, text))

# ================================================================================================ assets
info = {}
roots = {name: convert(name + '.mesh') for name in MODELS}
missing = ['models/%s.mesh, its material and texture' % name for name, root in roots.items() if root is None]
if missing and ASSETS == ROOT and not content_packages.has_content(ROOT):
    content_packages.unchecked(CHECK, missing)
elif missing:
    for name in missing:
        fail('missing: ' + name)
else:
    for name, (material, script, texture, height, counted, skeleton) in MODELS.items():
        root = roots[name]
        points = [tuple(float(p.get(k)) for k in 'xyz') for p in root.iter('position')]
        low, high = min(p[2] for p in points), max(p[2] for p in points)
        triangles = sum(1 for _ in root.iter('face'))
        materials = sorted({s.get('material') for s in root.iter('submesh')})
        info[name] = {'triangles': triangles, 'materials': materials, 'height': round(high - low, 4)}
        if triangles > TRIANGLE_LIMIT or triangles != counted:
            fail('%s.mesh: %d triangles, counted %d (limit %d)' % (name, triangles, counted, TRIANGLE_LIMIT))
        if materials != [material]:
            fail('%s.mesh: materials %s, expected %s' % (name, materials, material))
        base = BASE.get(name, 0.0)
        if abs(low - base) > 1e-3 or abs(high - height) > 2e-3:
            fail('%s.mesh: z from %.4f to %.4f, expected %.3f to %.3f' % (name, low, high, base, height))
        link = root.find('skeletonlink')
        if (link.get('name') if link is not None else None) != skeleton:
            fail('%s.mesh: skeleton %s, expected %s' % (name, link.get('name') if link is not None else None, skeleton))
        if skeleton:
            vertices = int(root.find('sharedgeometry').get('vertexcount'))
            bound = {(int(a.get('vertexindex')), a.get('boneindex'), float(a.get('weight')))
                     for a in root.find('boneassignments')}
            if len(bound) != vertices or any(b != BONE[name] or abs(w - 1.0) > 1e-6 for _, b, w in bound):
                fail('%s.mesh: not every vertex is bound with weight 1 to the one bone' % name)
        script_path = asset('materials/scripts/' + script)
        text = script_path.read_text(encoding='utf-8') if script_path.exists() else ''
        block = re.search(r'^material %s\s*\{.*?^\}' % material, text, re.S | re.M)
        if block is None or ('texture %s' % texture) not in block.group(0):
            fail('material %s with texture %s not found in %s' % (material, texture, script))
        texture_path = asset('materials/textures/' + texture)
        if not texture_path.exists():
            fail('materials/textures/%s missing' % texture)
        else:
            with Image.open(texture_path) as image:
                if image.size != (512, 512):
                    fail('%s: %s, expected 512 x 512' % (texture, image.size))
    for old in ('MysteryBox', 'Grimoire'):
        script = asset('materials/scripts/%s.material' % old)
        if script.exists() and (old + 'Normal') in script.read_text(encoding='utf-8'):
            fail('%s.material still names the normal map of the old model' % old)
        if asset('materials/textures/%sNormal.png' % old).exists():
            fail('the normal map of the old %s is still shipped' % old)
print('ODP_TEST_PHASE ' + json.dumps({'name': 'total', 'seconds': round(time.monotonic() - started, 3)}))
print(json.dumps(info, indent=1))
if fails:
    for text in fails:
        print(CHECK + ': ' + text)
    sys.exit(1)
print('item props meshy ok')
