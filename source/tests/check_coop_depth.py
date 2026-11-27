"""Inspect the coop: fixed points, open doorway, door leaf on its bone, dark interior and bedding; no compilation or
game start.

Proposed replacement of source/tests/check_coop_depth.py for the own coop of the content split (CS9, rooms C). The
previous check compared ChickenCoopHouse.mesh triangle by triangle with the coop of revision a4ac984c8^ (built from a
third-party coop); the own coop is new geometry, so this check keeps the intent (door leaf intact on its bone, doorway
open, a dark lining inside, straw bedding inside, the own skeleton unchanged, the interior material matt and dark) and
checks it on the fixed points of the coop object instead. Apply only after Mario's yes (CLAUDE.md: checks are changed
openly and reported first).
"""
from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402  (the coop files come from the hatchery package when it is present)

# The coop mesh and skeleton lie in the hatchery package: without the content they are named as not checked
if room_packages.asset(ROOT, 'models/ChickenCoopHouse.mesh') is None and not content_packages.has_content(ROOT):
    content_packages.unchecked('check_coop_depth', ['models/ChickenCoopHouse.mesh and .skeleton'])
    sys.exit(0)

OUT = ROOT / 'out' / 'coop-depth-check'
OUT.mkdir(parents=True, exist_ok=True)
# Converter executable: set OGRE_XML_CONVERTER to its full path, otherwise it is looked up on the PATH.
CONVERTER = Path(os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter'))
# Fixed points of the coop object (source/gamemap/RoomObjectBounds.h, source/rooms/HatcheryCoopHouse.h,
# models/ChickenCoopHouse.skeleton): footprint, door hinge and doorway, roof lookout
FOOTPRINT = (-0.203275, -0.4, 0.796725, 0.4)
DOOR_BONE = 'Door'
DOORWAY = (0.56, 0.61, 0.14, 0.20, 0.52)  # x from, x to, |y| below, z from, z to
INTERIOR = (0.02, 0.58, 0.31, 0.19, 0.56)  # x from, x to, |y| below, z from, z to
SKELETON_REVISION = 'a4ac984c8^'  # the own coop skeleton (bones Root, Door, Lookout; clips Door, Idle) of that state


def find(relative):
    """The file of the public tree or of the hatchery package."""
    path = room_packages.asset(ROOT, relative)
    assert path is not None, relative + ' not found (public tree or hatchery package)'
    return Path(path)


def convert(source, target):
    """Converts a binary Ogre file to XML and parses it."""
    subprocess.run([str(CONVERTER), '-q', '-log', str(target) + '.log', str(source), str(target)],
                   check=True, timeout=60, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return ET.parse(target).getroot()


def inside(points, box):
    """True if every point lies in the region (x from, x to, |y| below, z from, z to)."""
    x0, x1, y_abs, z0, z1 = box
    return all(x0 < x < x1 and abs(y) < y_abs and z0 < z < z1 for x, y, z in points)


mesh = convert(find('models/ChickenCoopHouse.mesh'), OUT / 'current.xml')
skeleton_path = find('models/ChickenCoopHouse.skeleton')
skeleton = convert(skeleton_path, OUT / 'skeleton.xml')
bones = {bone.get('name'): int(bone.get('id', index)) for index, bone in enumerate(skeleton.find('bones'))}
assert set(bones) == {'Root', 'Door', 'Lookout'}, bones
# The own coop skeleton is unchanged
assert skeleton_path.read_bytes() == subprocess.run(
    ['git', 'show', SKELETON_REVISION + ':models/ChickenCoopHouse.skeleton'], cwd=ROOT,
    capture_output=True, check=True, timeout=60, stdin=subprocess.DEVNULL).stdout
assert mesh.find('skeletonlink').get('name') == 'ChickenCoopHouse.skeleton'

buffers = mesh.findall('sharedgeometry/vertexbuffer')
points = [tuple(float(p.get(c)) for c in ('x', 'y', 'z')) for p in buffers[0].findall('vertex/position')]
weights = {}
for w in mesh.findall('boneassignments/vertexboneassignment'):
    weights.setdefault(int(w.get('vertexindex')), []).append((int(w.get('boneindex')), float(w.get('weight'))))
faces = {sm.get('material'): [tuple(int(f.get(k)) for k in ('v1', 'v2', 'v3')) for f in sm.findall('faces/face')]
         for sm in mesh.findall('submeshes/submesh')}
assert {'ChickenCoop', 'ChickenCoopInterior', 'ChickenCoopStraw'} <= set(faces), sorted(faces)
assert all(len(w) == 1 and abs(w[0][1] - 1.0) < 1e-6 for w in weights.values()), 'every vertex on one bone'

# Footprint: the whole coop stands inside its object rectangle
x0, y0, x1, y1 = FOOTPRINT
assert all(x0 - 1e-3 <= x <= x1 + 1e-3 and y0 - 1e-3 <= y <= y1 + 1e-3 for x, y, z in points)

# Door leaf: on the bone Door, in the doorway of the front wall, hinged at y -0.133
door = [points[i] for i, w in weights.items() if w[0][0] == bones['Door']]
assert len(door) > 0
assert all(0.57 < x < 0.64 and -0.14 < y < 0.14 and 0.20 < z < 0.53 for x, y, z in door)
assert min(y for x, y, z in door) < -0.12 and max(y for x, y, z in door) > 0.12

# Doorway open: no triangle outside the door leaf closes the opening
static = [f for group in faces.values() for f in group if all(weights[i][0][0] != bones['Door'] for i in f)]
assert not any(inside([points[i] for i in f], DOORWAY) for f in static), 'the doorway is closed'

# Dark lining inside on the back and both side walls
lining = [points[i] for f in faces['ChickenCoopInterior'] for i in f]
assert len(faces['ChickenCoopInterior']) > 0 and inside(lining, INTERIOR)
assert min(p[0] for p in lining) < 0.07 and max(p[0] for p in lining) > 0.5
assert min(p[1] for p in lining) < -0.27 and max(p[1] for p in lining) > 0.27

# Straw bedding on the floor inside, below the top of the doorway
bedding = faces.get('ChickenCoopBedding', []) + faces['ChickenCoopStraw']
bed_inside = [points[i] for f in bedding for i in f if inside([points[j] for j in f], INTERIOR)]
assert bed_inside, 'no straw bedding inside the coop'
assert min(p[2] for p in bed_inside) < 0.23 and max(p[2] for p in bed_inside) < 0.26

# The interior material stays matt and dark with the boards texture
material = find('materials/scripts/ChickenCoop.material').read_text()
interior_material = material[material.index('material ChickenCoopInterior'):]
interior_material = interior_material[:interior_material.index('\n}') + 2]
assert 'texture ChickenCoop.png' in interior_material
assert 'ambient 0.22 0.18 0.14' in interior_material and 'specular 0.0 0.0 0.0' in interior_material
assert 'emissive' not in interior_material
credits = room_packages.credits_text(ROOT)
assert 'build_coop.py' in credits and 'ChickenCoopInterior' in credits
print('coop depth OK: door leaf on its bone in the doorway, doorway open, %d dark lining faces, straw bedding inside, '
      'skeleton unchanged, inside the footprint' % len(faces['ChickenCoopInterior']))
