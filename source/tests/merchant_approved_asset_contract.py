"""Native geometry, skeleton and motion contract of the variant-1 merchant (owner finding of 2026-11-17).

The model of 2026-11-15 that this file pinned before (MerchantApproved atlases, 495863 triangles) replaced the chosen
variant 1 of D-6-v2 without a decision; the owner finding of 2026-11-17 brings the variant-1 figure back. This contract pins the delivered files
with fixed values counted once from the reviewed export and checks what the owner saw in the game, on the clips the
game plays (Idle, Walk, CountGold, RubHands), evaluated like Ogre does from the native skeleton:
  walk stiff        "die Arme komplett steif": in Walk each hand swings at least 0.2 forward and back, against the leg
                    of its side, the elbow bends and straightens, the chest turns and both feet stride
  clasped hands     in Idle the hands stay clasped in front of the chest the whole clip
  coin              the coin hangs in the right hand: hidden (scale at most 0.05) in Idle, Walk and RubHands, shown in
                    the whole of CountGold, where it comes up to the mouth; the coin stack is shown in CountGold
  rubbing hands     in RubHands the hands stay together and rub (their height difference changes by at least 0.04)
  see-through hands "dann werden seine Haende transparent": the hands use an opaque material without normal map,
                    blending, alpha rejection or disabled depth writing (the replaced model lit its rotated hands
                    through a tangent-space normal map that GPU skinning does not turn)
  own node          the root bone binds at the origin, so the figure stands on its own node position
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

# Filled once from the reviewed export of 2026-11-17, never derived from the assets during a test.
VERTICES = 95715
TRIANGLES = 118736
MINIMUM = (-0.271832, -0.339525, -0.00154968)
MAXIMUM = (0.261704, 0.363393, 1.27304)
HASHES = {
    'models/Merchant.mesh': 'bb9c1f5bc2bcf806b983c6aa71367b10e846d2871bed8769a8ab2a02ab12258f',
    'models/Merchant.skeleton': 'bf351b9ab3003fb342bbee1e1b40be01d5913947ab1341597114dc15524c3025',
    'materials/textures/MerchantHair.png': 'd20b0458cec8bc9ebdb9598ad3a03c4af582263558eed20d7f689d3f8d3342e6',
}
MATERIALS = {'MerchantRobe', 'MerchantCloak', 'MerchantHood', 'MerchantHide', 'MerchantDark', 'MerchantEye',
             'MerchantGold', 'MerchantHair', 'MerchantBrass', 'MerchantLeather'}
CLIPS = {'Idle': 4.0, 'Walk': 0.6, 'CountGold': 3.2, 'RubHands': 2.0}
BONES = ('Root', 'Pelvis', 'Spine', 'Chest', 'Head', 'UpperArm_R', 'Forearm_R', 'Hand_R', 'UpperArm_L', 'Forearm_L',
         'Hand_L', 'Thigh_R', 'Shin_R', 'Foot_R', 'Thigh_L', 'Shin_L', 'Foot_L', 'Scales', 'Coins', 'Coin')
PARENTS = {'Coin': 'Hand_R', 'Coins': 'Hand_L', 'Scales': 'Pelvis'}
# Least vertices bound to the coin and the coin stack, so they have something to show
COIN_VERTICES = {'Coin': 60, 'Coins': 300}
SAMPLES = 48
WALK_MIN_HAND_SWING = 0.2         # forward and back travel of each hand in Walk
WALK_MIN_ELBOW = 0.15             # change of the elbow angle in Walk (radians)
WALK_MIN_CHEST_TURN = 0.1         # change of the chest rotation in Walk (radians)
WALK_MIN_FOOT_STRIDE = 0.15       # forward and back travel of each foot in Walk
CLASP_MAX_DISTANCE = 0.14         # hands together (bind pose 0.11 apart, clasped)
CLASP_MIN_HEIGHT = 0.78           # in front of the chest, not hanging
CLASP_MAX_FRONT = -0.2            # in front of the body (front is -Y)
HIDDEN_SCALE = 0.05
SHOWN_SCALE = 0.99
COIN_MOUTH_DISTANCE = 0.25        # coin comes this close to the head joint ...
COIN_MOUTH_HEIGHT = 0.95          # ... at mouth height
RUB_MIN_SLIDE = 0.04
ROOT_MAX_OFFSET = 0.01
OPAQUE_FORBIDDEN = ('normal_map', 'scene_blend', 'alpha_rejection', 'depth_write off', 'transparent_sorting')


# Deserialize a native delivered asset once with bounded execution and retain its real exit status.
def deserialize(root, filename, directory):
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    output = directory / (filename + '.xml')
    subprocess.run([converter, '-q', '-log', str(output) + '.log',
                    str(root / 'models' / filename), str(output)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=120, check=True)
    return output


# Keep the delivered files byte-exact against the reviewed export.
def check_files(root):
    for relative, wanted in HASHES.items():
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert digest == wanted, ('Merchant asset changed', relative)


# The hands must not be lit through a normal map nor blended (see-through hands, owner finding of 2026-11-17).
def check_opaque_hands(root, hand_materials):
    text = ''.join(p.read_text(encoding='utf-8', errors='replace')
                   for p in (root / 'materials' / 'scripts').glob('*.material'))
    for name in hand_materials:
        block = re.search(r'^material ' + re.escape(name) + r'\s*\n\{.*?^}', text, re.M | re.S)
        assert block, name
        for word in OPAQUE_FORBIDDEN:
            assert word not in block.group(), (name, word)


# Stream the mesh: counts, bounds, materials, complete skinning and the materials and bones of hands and coins.
def check_mesh(path):
    totals = {}
    influences = {}
    bone_vertices = {}
    vertex_material = {}
    counts = dict(position=0, face=0)
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    materials = set()
    material = None
    skeleton = None
    with path.open('rb') as stream:
        for event, element in ET.iterparse(stream, events=('start', 'end')):
            tag = element.tag
            if event == 'start':
                if tag == 'sharedgeometry':
                    assert int(element.get('vertexcount')) == VERTICES
                elif tag == 'submesh':
                    material = element.get('material')
                    materials.add(material)
                continue
            if tag == 'position':
                value = [float(element.get(axis)) for axis in 'xyz']
                assert all(math.isfinite(v) for v in value)
                minimum = [min(a, b) for a, b in zip(minimum, value)]
                maximum = [max(a, b) for a, b in zip(maximum, value)]
                counts['position'] += 1
            elif tag == 'face':
                for axis in ('v1', 'v2', 'v3'):
                    index = int(element.get(axis))
                    assert 0 <= index < VERTICES
                    vertex_material[index] = material
                counts['face'] += 1
            elif tag == 'vertexboneassignment':
                index = int(element.get('vertexindex'))
                bone = int(element.get('boneindex'))
                weight = float(element.get('weight'))
                assert 0 <= index < VERTICES and 0 <= bone < len(BONES)
                assert math.isfinite(weight) and 0 < weight <= 1
                totals[index] = totals.get(index, 0.0) + weight
                influences[index] = influences.get(index, 0) + 1
                if weight > 0.5:
                    bone_vertices.setdefault(BONES[bone], []).append(index)
            elif tag == 'skeletonlink':
                skeleton = element.get('name')
            element.clear()
    assert counts == dict(position=VERTICES, face=TRIANGLES), counts
    assert materials == MATERIALS, materials
    assert all(abs(a - b) < .00002 for a, b in zip(minimum, MINIMUM)), minimum
    assert all(abs(a - b) < .00002 for a, b in zip(maximum, MAXIMUM)), maximum
    assert skeleton == 'Merchant.skeleton'
    assert len(totals) == VERTICES and all(abs(v - 1) < .001 for v in totals.values()), 'Every vertex must remain bound'
    assert all(1 <= v <= 4 for v in influences.values()), 'Unsupported skin influence count'
    for bone, least in COIN_VERTICES.items():
        coin = bone_vertices.get(bone, [])
        assert len(coin) >= least, (bone, len(coin))
        assert {vertex_material.get(i) for i in coin} == {'MerchantGold'}, bone
    return {vertex_material[i] for side in ('Hand_R', 'Hand_L') for i in bone_vertices[side]}


# Quaternion product (w, x, y, z).
def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2)


# Rotates vector v by the unit quaternion q.
def qrot(q, v):
    return qmul(qmul(q, (0.0,) + tuple(v)), (q[0], -q[1], -q[2], -q[3]))[1:]


# Angle between two orientations (radians).
def qangle(a, b):
    dot = abs(sum(x * y for x, y in zip(a, b)))
    return 2.0 * math.acos(min(1.0, dot))


# Unit quaternion of an Ogre angle-axis element.
def axis_angle(element):
    angle = float(element.get('angle'))
    axis = element.find('axis')
    v = [float(axis.get(k)) for k in 'xyz']
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    s = math.sin(angle / 2)
    return (math.cos(angle / 2), v[0] / n * s, v[1] / n * s, v[2] / n * s)


# Ogre keyframe sampling: linear translation and scale, shortest-path normalised rotation blend.
def sample(keys, time_point):
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= time_point <= k1[0]:
            s = (time_point - k0[0]) / (k1[0] - k0[0]) if k1[0] > k0[0] else 0.0
            q0, q1 = k0[2], k1[2]
            if sum(a * b for a, b in zip(q0, q1)) < 0:
                q1 = tuple(-c for c in q1)
            q = tuple(a + (b - a) * s for a, b in zip(q0, q1))
            n = math.sqrt(sum(c * c for c in q))
            return (tuple(a + (b - a) * s for a, b in zip(k0[1], k1[1])), tuple(c / n for c in q),
                    tuple(a + (b - a) * s for a, b in zip(k0[3], k1[3])))
    return keys[-1][1], keys[-1][2], keys[-1][3]


# World head position, orientation and mean scale of every bone in one clip at one time.
def pose(bones, parents, tracks, time_point):
    world = {}
    for name, position, rotation in bones:
        if name in tracks:
            translate, rotate, scale = sample(tracks[name], time_point)
        else:
            translate, rotate, scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
        local = tuple(a + b for a, b in zip(position, translate))
        orientation = qmul(rotation, rotate)
        size = sum(scale) / 3.0
        parent = parents.get(name)
        if parent is None:
            world[name] = (local, orientation, size)
        else:
            p, q, s = world[parent]
            world[name] = (tuple(a + b for a, b in zip(p, qrot(q, tuple(c * s for c in local)))), qmul(q, orientation),
                           s * size)
    return world


# Largest minus smallest value.
def spread(values):
    return max(values) - min(values)


# Euclidean distance of two points.
def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# Joint hierarchy, bind of the root, closed loops and the motions the owner asked for.
def check_skeleton(path):
    tree = ET.parse(path).getroot()
    bones = []
    for bone in tree.findall('./bones/bone'):
        p = bone.find('position')
        bones.append((bone.get('name'), tuple(float(p.get(k)) for k in 'xyz'), axis_angle(bone.find('rotation'))))
    assert tuple(b[0] for b in bones) == BONES, tuple(b[0] for b in bones)
    parents = {p.get('bone'): p.get('parent') for p in tree.findall('./bonehierarchy/boneparent')}
    for bone, parent in PARENTS.items():
        assert parents.get(bone) == parent, (bone, parents.get(bone))
    assert all(abs(c) <= ROOT_MAX_OFFSET for c in bones[0][1][:2]), ('root beside the node', bones[0][1])
    clips = {}
    for clip in tree.findall('./animations/animation'):
        tracks = {}
        for track in clip.findall('./tracks/track'):
            keys = []
            for key in track.findall('./keyframes/keyframe'):
                translate = key.find('translate')
                scale = key.find('scale')
                keys.append((float(key.get('time')),
                             tuple(float(translate.get(c)) for c in 'xyz') if translate is not None else (0.0, 0.0, 0.0),
                             axis_angle(key.find('rotate')),
                             tuple(float(scale.get(c)) for c in 'xyz') if scale is not None else (1.0, 1.0, 1.0)))
            times = [k[0] for k in keys]
            assert all(a < b for a, b in zip(times, times[1:])), track.get('bone')
            assert all(math.isfinite(v) for k in keys for part in k[1:] for v in part)
            tracks[track.get('bone')] = keys
        clips[clip.get('name')] = (float(clip.get('length')), tracks)
    assert {name: value[0] for name, value in clips.items()} == CLIPS, {name: value[0] for name, value in clips.items()}
    poses = {}
    for name, (length, tracks) in clips.items():
        poses[name] = [pose(bones, parents, tracks, length * i / SAMPLES) for i in range(SAMPLES + 1)]
        first, last = poses[name][0], poses[name][-1]
        for bone in BONES:
            assert distance(first[bone][0], last[bone][0]) < .002, ('loop not closed', name, bone)
            assert abs(first[bone][2] - last[bone][2]) < .002, ('loop not closed', name, bone)

    walk = poses['Walk']
    for side in ('R', 'L'):
        hand_y = [w['Hand_' + side][0][1] for w in walk]
        foot_y = [w['Foot_' + side][0][1] for w in walk]
        assert spread(hand_y) >= WALK_MIN_HAND_SWING, ('stiff arm in Walk', side, spread(hand_y))
        assert spread(foot_y) >= WALK_MIN_FOOT_STRIDE, ('no stride in Walk', side, spread(foot_y))
        mean_hand = sum(hand_y) / len(hand_y)
        mean_foot = sum(foot_y) / len(foot_y)
        together = sum((h - mean_hand) * (f - mean_foot) for h, f in zip(hand_y, foot_y))
        assert together < 0, ('the arm swings with the leg of its side, not against it', side)
        elbow = [qangle(w['UpperArm_' + side][1], w['Forearm_' + side][1]) for w in walk]
        assert spread(elbow) >= WALK_MIN_ELBOW, ('stiff elbow in Walk', side, spread(elbow))
    chest = [qangle(walk[0]['Chest'][1], w['Chest'][1]) for w in walk]
    assert max(chest) >= WALK_MIN_CHEST_TURN, ('stiff upper body in Walk', max(chest))

    for w in poses['Idle']:
        assert distance(w['Hand_R'][0], w['Hand_L'][0]) <= CLASP_MAX_DISTANCE, 'hands not clasped in Idle'
        for side in ('Hand_R', 'Hand_L'):
            assert w[side][0][2] >= CLASP_MIN_HEIGHT and w[side][0][1] <= CLASP_MAX_FRONT, ('hands not at the chest', side)
    for name in ('Idle', 'Walk', 'RubHands'):
        for w in poses[name]:
            assert w['Coin'][2] <= HIDDEN_SCALE and w['Coins'][2] <= HIDDEN_SCALE, ('coin shown in', name)
    near_mouth = False
    for w in poses['CountGold']:
        assert w['Coin'][2] >= SHOWN_SCALE and w['Coins'][2] >= SHOWN_SCALE, 'coin hidden in CountGold'
        if distance(w['Coin'][0], w['Head'][0]) <= COIN_MOUTH_DISTANCE and w['Coin'][0][2] >= COIN_MOUTH_HEIGHT:
            near_mouth = True
    assert near_mouth, 'the coin never comes up to the mouth in CountGold'
    slide = []
    for w in poses['RubHands']:
        assert distance(w['Hand_R'][0], w['Hand_L'][0]) <= CLASP_MAX_DISTANCE, 'hands apart in RubHands'
        slide.append(w['Hand_R'][0][2] - w['Hand_L'][0][2])
    assert spread(slide) >= RUB_MIN_SLIDE, ('hands do not rub', spread(slide))


# Verify the delivered merchant without loading its large XML into a second in-memory tree. converted names a directory
# where this run already deserialized Merchant.mesh and Merchant.skeleton (after the hash check of this run), so the
# converter does not run twice; without it the files are deserialized here.
def verify_merchant_contract(root, converted=None):
    root = Path(root)
    started = time.perf_counter()
    check_files(root)
    with tempfile.TemporaryDirectory(prefix='merchant-') as temporary:
        directory = Path(temporary)
        if converted is not None and (Path(converted) / 'Merchant.mesh.xml').is_file() and                 (Path(converted) / 'Merchant.skeleton.xml').is_file():
            mesh = Path(converted) / 'Merchant.mesh.xml'
            skeleton = Path(converted) / 'Merchant.skeleton.xml'
        else:
            mesh = deserialize(root, 'Merchant.mesh', directory)
            skeleton = deserialize(root, 'Merchant.skeleton', directory)
        prepared = time.perf_counter()
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'setup', 'seconds': prepared - started}))
        check_opaque_hands(root, check_mesh(mesh))
        check_skeleton(skeleton)
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'native asset validation', 'seconds': time.perf_counter() - prepared}))
