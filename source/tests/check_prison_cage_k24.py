"""K24 (INGAME-QS-10 A5): the prison is a coarse cage of simple, thick, dark iron bars with a door on the gate tile, and
the cage stands still. No compiler needed.

One check per point, on the shipped files (meshes through OgreXMLConverter, the skeleton as XML, textures as pixels):
  coarse bars     FenceStraight carries 3 to 5 separate upright bars (taller than 1.2 m), FenceCorner 6 to 10; every bar
                  is at least 0.035 m thick, and the free gap between neighbouring bars, also across the joint to the
                  next tile, is at least 0.15 m (not a fine picket fence)
  dark iron       FenceStraight, FenceCorner and PrisonDoor use one material; its texture has a mean luminance of at
                  most 70, a mean HSV saturation of at most 0.25 and at most 1 % texels brighter than 120 (no bright
                  steel); the material has no emissive part and its diffuse is at most 1
  door            PrisonDoor links PrisonDoor.skeleton; the leaf hangs on the bone Leaf; in the clip Open the leaf turns
                  about its hinge (the centre of the hinge knuckles moves at
                  most 0.01 m), its free edge swings at least 0.5 m into
                  the cell (towards -y), and the clip starts and ends closed, so the door is still before and after;
                  the closed leaf stands in the line of the bars of FenceStraight
  door placement  RoomPrison puts PrisonDoor on getGateTile(), the tile where prisoners are delivered
                  (askSpotForCarriedEntity), and turns it like the straight bar piece would stand on that tile (the four
                  rotations of createGateMesh equal those createFencingMesh gives EW, WE, SN and NS)
  stands still    no room ambience effect moves a cage piece by itself: no Motion effect and no Clip effect with When
                  Always matches FenceStraight, FenceCorner or PrisonDoor; the only clip on the door is played by the
                  event PrisonerArrived; the door skeleton has no other clip that could loop
  size            every cage mesh has at most 2000 triangles (comparable furniture), and the navigation catalog
                  (RoomObjectBounds.h) holds its XY bounds (within 0.00002) and keeps it unscaled

The cage meshes, the skeleton, the material scripts, the texture and the room ambience files live in content and room
packages (found through scripts/content_packages.py). Without the content the check names the mesh, material and
ambience points as not checked (no converter is started) and checks the door placement and the catalog names.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
  python source/tests/check_prison_cage_k24.py
"""
from pathlib import Path
import colorsys
import math
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

START = time.monotonic()
CAGE = ('FenceStraight', 'FenceCorner', 'PrisonDoor')
# the material scripts of the public tree and of the content and room packages
MATERIALS = ''.join(p.read_text(encoding='utf-8', errors='replace')
                    for base in [ROOT] + content_packages.package_roots(ROOT)
                    for p in (base / 'materials' / 'scripts').glob('*.material'))
#: False when the cage meshes are not there because the content is not present: the mesh points are not checked
WITH_MESHES = content_packages.has_content(ROOT) or all(
    content_packages.data_file(ROOT, 'models/' + name + '.mesh') is not None for name in CAGE)
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='prison_cage_'))
fails = []


def check(condition, message):
    """Records a failed point."""
    if not condition:
        fails.append(message)


def convert(name):
    """Converts a shipped binary model file to XML and returns its root element."""
    target = work / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(target) + '.log', str(content_packages.resolve(ROOT, 'models/' + name)),
                    str(target)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=120, check=True)
    return ET.parse(target).getroot()


def mesh(name):
    """Returns (positions, triangles, materials, bone weights {vertex: {bone index: weight}}, skeleton link)."""
    root = convert(name + '.mesh')
    shared = root.find('sharedgeometry')
    pos = []
    for vb in shared.iter('vertexbuffer'):
        for v in vb.iter('vertex'):
            p = v.find('position')
            if p is not None:
                pos.append(tuple(float(p.get(k)) for k in 'xyz'))
    tris, mats = [], set()
    for sm in root.iter('submesh'):
        mats.add(sm.get('material'))
        for f in sm.iter('face'):
            tris.append(tuple(int(f.get(k)) for k in ('v1', 'v2', 'v3')))
    weights = {}
    for a in root.iter('vertexboneassignment'):
        weights.setdefault(int(a.get('vertexindex')), {})[int(a.get('boneindex'))] = float(a.get('weight'))
    link = root.find('skeletonlink')
    return pos, tris, mats, weights, (link.get('name') if link is not None else None)


def components(pos, tris):
    """Connected parts of a mesh (vertices joined by triangles or by equal positions), as lists of positions."""
    parent = list(range(len(pos)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b, c in tris:
        union(a, b)
        union(b, c)
    first = {}
    for i, p in enumerate(pos):
        key = tuple(round(x, 5) for x in p)
        if key in first:
            union(i, first[key])
        else:
            first[key] = i
    parts = {}
    for i in range(len(pos)):
        parts.setdefault(find(i), []).append(pos[i])
    return list(parts.values())


def uprights(pos, tris):
    """Upright bars: parts taller than 1.2 m and at most 0.1 m wide; (centre x, centre y, thickness) each."""
    bars = []
    for part in components(pos, tris):
        xs, ys, zs = [p[0] for p in part], [p[1] for p in part], [p[2] for p in part]
        if max(zs) - min(zs) > 1.2 and max(xs) - min(xs) <= 0.1 and max(ys) - min(ys) <= 0.1:
            # thickness measured in the lower half, below the forged tip
            low = [p for p in part if p[2] < (min(zs) + max(zs)) / 2]
            w = min(max(p[0] for p in low) - min(p[0] for p in low), max(p[1] for p in low) - min(p[1] for p in low))
            bars.append(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, w))
    return bars


def material_block(name):
    m = re.search(r'^material ' + re.escape(name) + r'\b.*?^}', MATERIALS, re.M | re.S)
    return m.group(0) if m else ''


models = {}
for name in CAGE if WITH_MESHES else ():
    if content_packages.data_file(ROOT, 'models/' + name + '.mesh') is not None:
        models[name] = mesh(name)
    else:
        check(False, 'models/%s.mesh is missing' % name)
        models[name] = ([], [], set(), {}, None)
print('ODP_TEST_PHASE {"name": "setup", "seconds": %.3f}' % (time.monotonic() - START))

# The points on the meshes need them (named as not checked without the content)
if WITH_MESHES:
    # coarse bars
    pos, tris = models['FenceStraight'][:2]
    bars = sorted(uprights(pos, tris))
    check(3 <= len(bars) <= 5, 'FenceStraight has %d upright bars, wanted 3 to 5 coarse bars' % len(bars))
    if bars:
        check(min(b[2] for b in bars) >= 0.035, 'thinnest bar of FenceStraight is %.3f m, wanted at least 0.035' %
              min(b[2] for b in bars))
        gaps = [bars[i + 1][0] - bars[i][0] - (bars[i + 1][2] + bars[i][2]) / 2 for i in range(len(bars) - 1)]
        gaps.append(1.0 - (bars[-1][0] - bars[0][0]) - (bars[-1][2] + bars[0][2]) / 2)
        check(min(gaps) >= 0.15, 'narrowest gap between bars is %.3f m, wanted at least 0.15' % min(gaps))
        line_y = sum(b[1] for b in bars) / len(bars)
    else:
        line_y = -0.48
    corner = uprights(*models['FenceCorner'][:2])
    check(6 <= len(corner) <= 10, 'FenceCorner has %d upright bars, wanted 6 to 10' % len(corner))
    check(all(b[2] >= 0.035 for b in corner), 'FenceCorner has bars thinner than 0.035 m')

    # dark iron
    mats = set()
    for name in CAGE:
        mats |= models[name][2]
    check(len(mats) == 1, 'the cage pieces use %s, wanted one material' % sorted(mats))
    for mat in mats:
        block = material_block(mat)
        check(block != '', 'material %s missing' % mat)
        tex = re.search(r'^\s*texture\s+(\S+\.png)', block, re.M)
        check(tex is not None, 'material %s has no texture' % mat)
        check(not re.search(r'^\s*emissive\s+(?!0+(\.0*)?\s+0+(\.0*)?\s+0+(\.0*)?\b)', block, re.M),
              'material %s glows (emissive)' % mat)
        dif = re.search(r'^\s*diffuse\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', block, re.M)
        check(dif is None or max(float(x) for x in dif.groups()) <= 1.0, 'material %s brightens its texture' % mat)
        if tex is not None:
            img = Image.open(content_packages.resolve(ROOT, 'materials/textures/' + tex.group(1))).convert('RGB').resize((128, 128))
            px = list(img.get_flattened_data())
            lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
            sat = [colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[1] for r, g, b in px]
            mean = sum(lum) / len(lum)
            check(mean <= 70, 'cage texture %s mean luminance %.1f, wanted at most 70 (dark iron)' % (tex.group(1), mean))
            check(sum(sat) / len(sat) <= 0.25, 'cage texture %s is coloured (saturation %.2f)' % (tex.group(1),
                                                                                                sum(sat) / len(sat)))
            bright = sum(1 for y in lum if y > 120) / float(len(lum))
            check(bright <= 0.01, 'cage texture %s has %.1f %% bright texels' % (tex.group(1), 100 * bright))

    # door
    pos, tris, _, weights, link = models['PrisonDoor']
    check(link == 'PrisonDoor.skeleton', 'PrisonDoor links skeleton %s' % link)
    skel = (convert('PrisonDoor.skeleton') if content_packages.data_file(ROOT, 'models/PrisonDoor.skeleton') is not None
            else ET.fromstring('<skeleton><bones/></skeleton>'))
    # bones in file order (the converter writes no ids; the order is the bone index)
    bones = {b.get('name'): (i, tuple(float(b.find('position').get(k)) for k in 'xyz'))
             for i, b in enumerate(skel.find('bones').iter('bone'))}
    anims = {a.get('name'): a for a in skel.iter('animation')}
    check(set(anims) == {'Open'}, 'PrisonDoor clips %s, wanted only Open' % sorted(anims))
    if 'Leaf' in bones and 'Open' in anims:
        leaf_id, pivot = bones['Leaf']
        leaf = [pos[v] for v, w in weights.items() if w.get(leaf_id, 0) > 0.99]
        check(len(leaf) > 50, 'the door leaf has %d vertices on the bone Leaf' % len(leaf))
        track = [t for t in anims['Open'].iter('track') if t.get('bone') == 'Leaf']
        check(len(track) == 1, 'the clip Open does not turn the leaf')
        if track and leaf:
            keys = []
            for k in track[0].iter('keyframe'):
                r = k.find('rotate')
                ax = r.find('axis')
                tr = k.find('translate')
                keys.append((float(k.get('time')), float(r.get('angle')), tuple(float(ax.get(c)) for c in 'xyz'),
                             tuple(float(tr.get(c)) for c in 'xyz')))

            def moved(p, angle, axis, shift):
                """Position of a leaf vertex for a key (turn about the bone pivot, then the key translation)."""
                x, y, z = p[0] - pivot[0], p[1] - pivot[1], p[2] - pivot[2]
                n = math.sqrt(sum(a * a for a in axis)) or 1.0
                ux, uy, uz = (a / n for a in axis)
                c, s = math.cos(angle), math.sin(angle)
                dot = ux * x + uy * y + uz * z
                rx = x * c + (uy * z - uz * y) * s + ux * dot * (1 - c)
                ry = y * c + (uz * x - ux * z) * s + uy * dot * (1 - c)
                rz = z * c + (ux * y - uy * x) * s + uz * dot * (1 - c)
                return (rx + pivot[0] + shift[0], ry + pivot[1] + shift[1], rz + pivot[2] + shift[2])

            # the hinge knuckles: leaf vertices around the pivot axis; their centre stays put when the leaf turns about its joint
            hinge = [p for p in leaf if math.hypot(p[0] - pivot[0], p[1] - pivot[1]) <= 0.025]
            free_x = max(p[0] for p in leaf)
            free = [p for p in leaf if p[0] >= free_x - 0.03]
            check(len(hinge) > 0, 'no leaf vertex at the hinge axis')
            worst_hinge, widest, deepest = 0.0, 0.0, 0.0
            for t, angle, axis, shift in keys:
                if hinge:
                    moved_hinge = [moved(p, angle, axis, shift) for p in hinge]
                    centre = [sum(p[i] for p in hinge) / len(hinge) for i in range(3)]
                    centre_now = [sum(p[i] for p in moved_hinge) / len(hinge) for i in range(3)]
                    worst_hinge = max(worst_hinge, math.dist(centre, centre_now))
                for p in free:
                    q = moved(p, angle, axis, shift)
                    widest = max(widest, math.dist(p, q))
                    deepest = min(deepest, q[1] - p[1])
            check(worst_hinge <= 0.01, 'the leaf turns beside its hinge (the knuckle centre moves %.3f m)' % worst_hinge)
            check(widest >= 0.5, 'the door opens only %.2f m' % widest)
            check(deepest <= -0.4, 'the door does not swing into the cell (towards -y)')
            for t, angle, axis, shift in (keys[0], keys[-1]):
                check(abs(angle) < 1e-4 and max(abs(c) for c in shift) < 1e-5, 'the clip Open is not closed at %.2f s' % t)
        leaf_y = [p[1] for p in leaf]
        if leaf_y:
            check(abs((max(leaf_y) + min(leaf_y)) / 2 - line_y) <= 0.05, 'the closed door is not in the line of the bars')
    else:
        check(False, 'PrisonDoor skeleton lacks the bone Leaf or the clip Open')

# door placement
prison = (ROOT / 'source' / 'rooms' / 'RoomPrison.cpp').read_text(encoding='utf-8').replace('\r\n', '\n')


def section(start, end):
    """Text of RoomPrison.cpp from start to end (empty when start is missing; to the end of file when end is)."""
    a = prison.find(start)
    if a < 0:
        return ''
    b = prison.find(end, a)
    return prison[a:b] if b >= 0 else prison[a:]


put = section('void RoomPrison::putFenceMeshes()', 'BuildingObject* RoomPrison::createGateMesh')
check(re.search(r'Tile\* gateTile = getGateTile\(\);', put) is not None, 'putFenceMeshes does not look up the gate tile')
check(re.search(r'if\(tt == gateTile\)\s*\n\s*ro = createGateMesh\(tt, actualSouth != mActualTilesCoords\.end\(\), '
                r'actualNorth != mActualTilesCoords\.end\(\),\s*actualWest != mActualTilesCoords\.end\(\)\);', put)
      is not None, 'the gate tile does not get the door')
ask = section('Tile* RoomPrison::askSpotForCarriedEntity', '\n}\n')
check('return getGateTile();' in ask, 'prisoners are not delivered on the gate tile')
gate = section('BuildingObject* RoomPrison::createGateMesh', 'BuildingObject* RoomPrison::createFencingMesh')
fencing = section('BuildingObject* RoomPrison::createFencingMesh', '\n}\n')
straight = dict((d, float(a)) for d, a in re.findall(
    r'case FencingDirection::(\w+) :\s*\n\s*return new BuildingObject\(getGameMap\(\), \*this, "FenceStraight", \*tt, ([\d.]+)', fencing))
door = {}
m = re.search(r'double rotation = ([\d.]+);\s*if\(cellSouth\)\s*rotation = ([\d.]+);\s*else if\(cellNorth\)\s*'
              r'rotation = ([\d.]+);\s*else if\(cellWest\)\s*rotation = ([\d.]+);', gate)
check(m is not None and '"PrisonDoor", *tt, rotation' in gate, 'createGateMesh does not turn the door by the cell side')
if m:
    door = {'NS': float(m.group(1)), 'EW': float(m.group(2)), 'WE': float(m.group(3)), 'SN': float(m.group(4))}
    for d in ('EW', 'WE', 'SN', 'NS'):
        check(straight.get(d) == door[d], 'door turned %s for cell side %s, the bars stand at %s' % (door[d], d,
                                                                                                straight.get(d)))

# stands still
# the room ambience files of the public tree and of the content packages
for path in content_packages.data_glob(ROOT, 'config', 'roomAmbience*.cfg'):
    text = open(path, encoding='utf-8', errors='replace').read()
    for block in re.findall(r'\[Effect\](.*?)\[/Effect\]', text, re.S):
        fields = {}
        for line in block.splitlines():
            words = line.split('#', 1)[0].split()
            if words:
                fields[words[0]] = words[1:]
        patterns = fields.get('Match', []) + fields.get('Object', [])

        def hits(pattern):
            for name in CAGE:
                if pattern.startswith('*') and name.endswith(pattern[1:]):
                    return True
                if pattern.endswith('*') and name.startswith(pattern[:-1]):
                    return True
                if pattern == name:
                    return True
            return False

        if not any(hits(p) for p in patterns):
            continue
        name = (fields.get('Name') or ['?'])[0]
        kind = (fields.get('Kind') or [''])[0]
        check(kind != 'Motion', '%s moves a cage piece (%s)' % (name, os.path.basename(path)))
        if kind in ('Clip', 'CreatureClip'):
            check(fields.get('Target') == ['Event'] and fields.get('Event') == ['PrisonerArrived'] and 'Loop' not in fields,
                  '%s plays a cage clip without a delivered prisoner' % name)

# size and navigation catalog
catalog = (ROOT / 'source' / 'gamemap' / 'RoomObjectBounds.h').read_text(encoding='utf-8')
scale = catalog[catalog.index('inline FurnitureScale furnitureScale'):]
scale = scale[:scale.index('return {1.0f, 1.0f};', scale.index('name == "FenceCorner"'))]
for name in CAGE:
    pos, tris = models[name][:2] if WITH_MESHES else ([], [])
    check(not WITH_MESHES or len(tris) <= 2000, '%s has %d triangles, wanted at most 2000' % (name, len(tris)))
    row = re.search(r'\{"' + name + r'", ([-.\df]+), ([-.\df]+), ([-.\df]+), ([-.\df]+)', catalog)
    check(row is not None, '%s is not in the navigation catalog' % name)
    if row and WITH_MESHES:
        want = (min(p[0] for p in pos), min(p[1] for p in pos), max(p[0] for p in pos), max(p[1] for p in pos)) if pos else ()
        have = tuple(float(v.rstrip('f')) for v in row.groups())
        check(len(want) == 4 and all(abs(a - b) <= 0.00002 for a, b in zip(want, have)), '%s bounds %s, the mesh has %s' % (name, have, want))
    check('name == "%s"' % name in scale, '%s is narrowed like furniture' % name)

if not WITH_MESHES:
    content_packages.unchecked('check_prison_cage_k24', ['coarse bars, dark iron, door clip, cage stands still and mesh '
                                                         'sizes (cage meshes, material, texture, room ambience files)'])
print('ODP_TEST_PHASE {"name": "checks", "seconds": %.3f}' % (time.monotonic() - START))
if fails:
    print('FAIL')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('OK check_prison_cage_k24')
