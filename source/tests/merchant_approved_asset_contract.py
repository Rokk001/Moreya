"""Native geometry, texture, skeleton and motion contract of the merchant (INGAME-QS-10 K20, package A1b).

Owner finding of 2026-11-17: the variant-1 figure brought back by A1 looked worse than the merchant of 2026-11-15 that is
in the game; the owner wants that merchant kept and only reworked. So the delivered merchant is the model of 2026-11-15
(MerchantApproved atlases, look unchanged: the 20 atlases stay byte-exact) with the changes K20 names. This contract pins
the delivered files with fixed values counted once from the reviewed export and checks what the owner saw in the game, on
the clips the game plays (Idle, Walk, CountGold, RubHands), evaluated like Ogre does from the native skeleton:
  walk stiff        "die Arme komplett steif": in Walk each hand swings at least 0.2 forward and back, against the leg
                    of its side, the elbow bends and straightens, the chest turns and both feet stride; the legs are
                    skinned to the thighs (before, no vertex hung on a thigh and the trousers stayed on the pelvis)
  clasped hands     in Idle the hands stay clasped in front of the chest the whole clip
  coin              no coin was seen: the coin hangs in the right hand and the coin stack in the left hand, both with
                    gold geometry (before, no vertex hung on the coin bones); hidden (scale at most 0.05) in Idle, Walk and
                    RubHands, shown in the whole of CountGold, where the coin comes up to the mouth
  rubbing hands     in RubHands the hands stay together and rub (their height difference changes by at least 0.04)
  see-through hands "dann werden seine Haende transparent": every face of the hands uses an opaque hand material without
                    normal map, blending, alpha rejection or disabled depth writing (the tangent-space normal map is lit
                    wrong once GPU skinning turns the hand), and wrist and elbow are blended between their bones so the
                    skin does not open at a hard seam when the joint bends
  own node          the root bone binds at the origin, the figure below the table top is centred on the origin within
                    0.04 and stays inside its own tile
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

# Filled once from the reviewed export of 2026-11-17 (A1b), never derived from the assets during a test.
VERTICES = 416951
TRIANGLES = 496519
MINIMUM = (-0.392404, -0.25321, 0.00864)
MAXIMUM = (0.39241, 0.243949, 1.30284)
HASHES = {
    'models/Merchant.mesh': '7995c151863319c3dd4bdfd7312298dfbc8370718aabcbbb3e0f91939ff9798b',
    'models/Merchant.skeleton': '890b21631dda994d39411e5e0bdd8d84412ec6fdb1108fb4a4ecf7dc56561b55',
    # The look of the merchant of 2026-11-15: the baked atlases stay byte-exact
    'materials/textures/MerchantBrassApprovedColor.png': '13e0088f101ba4207e80a63c091ed4bbb236abb751ca4b5dae95a32f30add3bb',
    'materials/textures/MerchantBrassApprovedNormal.png': 'f559243be3489daa2d323ee85f3329346dc1f4c416d77087b02c3ea3a6a4309a',
    'materials/textures/MerchantCloakApprovedColor.png': '95fbbdb204beaeef31ac5d3e8f227548a5f09739585271c34231b980351d2ebf',
    'materials/textures/MerchantCloakApprovedNormal.png': '116205b04f27035ec83ac4d1d0821a367ae532643ed9714304c1c6375c820205',
    'materials/textures/MerchantDetailsApprovedColor.png': '05c66a1f06fc1a083f46ea46b4756f245ccc58df61bc262a244d9410dceacdf9',
    'materials/textures/MerchantDetailsApprovedNormal.png': 'ca7533d30a23ba2613f963f0976fdcdc5b3a7b0d49772d16062eedb4b2cbeef0',
    'materials/textures/MerchantGoldApprovedColor.png': '89f19664b2cf1e7783cbc7a35f7933fa6763ba4aeac073698cf4bd29eaa17e73',
    'materials/textures/MerchantGoldApprovedNormal.png': '51b606bd56088b165f734de7d6f6c1fbf174ebf9b091dcafafea9a6eec3d4d6a',
    'materials/textures/MerchantHairApprovedColor.png': '8a7f782dc060c358d00484ee76a555dd33213e556a378d75534000da647ee643',
    'materials/textures/MerchantHairApprovedNormal.png': '1019976e0f4208990906e5a03f82024fa7424830e41bd6fd43b3e5f9a72291c9',
    'materials/textures/MerchantHideApprovedColor.png': '4b42b80dce02d37b9cb0a4b4d39d66c880d78928adfaecf7ab0cf64cfa3165a7',
    'materials/textures/MerchantHideApprovedNormal.png': 'cf6f6fe2ae5cd4ac4c2345227dbcd24a319f19e0ff6514cc601f6c38df3c40ee',
    'materials/textures/MerchantHoodApprovedColor.png': 'f6d2d351a5b46a1e897af0bf8a88f129a420aab5e371bf08f28c575a6205d878',
    'materials/textures/MerchantHoodApprovedNormal.png': '0fa11e685e19c55fc06616a68ce7faf57bdecbc6e81fcea594dc79c155bc9c69',
    'materials/textures/MerchantLeatherApprovedColor.png': '06c119d122c8a11ae27c018e7b6ced96d82a99df2289d10c6215c550c0a6c5a7',
    'materials/textures/MerchantLeatherApprovedNormal.png': 'db04e79d17f179b1b0bdfbf013ef45b41f18a5dddb2dd821e9e6d9f70cee6221',
    'materials/textures/MerchantLinenApprovedColor.png': '044fab840b1b3963d5b24e84f687c1991f8dc4f4d1b4ed68e7c98168a6de7e29',
    'materials/textures/MerchantLinenApprovedNormal.png': 'fb4dbccfba52bebc3022ebf60b6ff268562a6036a0ed5ab2dc2c9e7929c5baa5',
    'materials/textures/MerchantRobeApprovedColor.png': '3458d9e9b198be35dc7569294cd0b5329081135509f86023309c862895a2edab',
    'materials/textures/MerchantRobeApprovedNormal.png': '6b9f50ddf5605e3753704b9ae9e65f1828229b6351c3483899eb7ba7ef7cffe8',
}
ATLASES = {'Robe': 2048, 'Cloak': 2048, 'Linen': 2048, 'Leather': 2048,
           'Brass': 1024, 'Details': 1024, 'Hair': 1024, 'Hood': 2048,
           'Hide': 2048, 'Gold': 1024}
# Opaque hand variants: the colour atlas of their family without the normal map
HAND_FAMILIES = ('Hide', 'Details', 'Gold')
MATERIALS = {'MerchantApproved' + name for name in ATLASES} | {'MerchantApproved' + name + 'Hand' for name in HAND_FAMILIES}
CLIPS = {'Idle': 4.0, 'Walk': 0.6, 'CountGold': 3.2, 'RubHands': 2.0}
BONES = ('Root', 'Pelvis', 'Spine', 'Chest', 'Head', 'UpperArm_R', 'Forearm_R', 'Hand_R', 'UpperArm_L', 'Forearm_L',
         'Hand_L', 'Thigh_R', 'Shin_R', 'Foot_R', 'Thigh_L', 'Shin_L', 'Foot_L', 'Scales', 'Coins', 'Coin')
B = {name: index for index, name in enumerate(BONES)}
PARENTS = {'Coin': 'Hand_R', 'Coins': 'Hand_L', 'Scales': 'Pelvis'}
# Least vertices bound to the coin and the coin stack, so they have something to show (export: 100 and 588)
COIN_VERTICES = {'Coin': 60, 'Coins': 300}
COIN_MATERIAL = 'MerchantApprovedGoldHand'
# Least vertices bound to each thigh (export: 10214 and 8671; before: none)
THIGH_MIN_VERTICES = 8000
# Least vertices blended between forearm and hand and between upper arm and forearm on each side (export: about 1000;
# before: none, hard seams)
JOINT_BLEND_MIN_VERTICES = 800
JOINT_BLEND_WEIGHT = 0.1
SAMPLES = 48
WALK_MIN_HAND_SWING = 0.2         # forward and back travel of each hand in Walk
WALK_MIN_ELBOW = 0.15             # change of the elbow angle in Walk (radians)
WALK_MIN_CHEST_TURN = 0.1         # change of the chest rotation in Walk (radians)
WALK_MIN_FOOT_STRIDE = 0.15       # forward and back travel of each foot in Walk
CLASP_MAX_DISTANCE = 0.14         # hands together
CLASP_MIN_HEIGHT = 0.78           # in front of the chest, not hanging (bind pose: wrists at 0.63)
CLASP_MAX_FRONT = -0.2            # in front of the body (front is -Y)
HIDDEN_SCALE = 0.05
SHOWN_SCALE = 0.99
COIN_MOUTH_DISTANCE = 0.25        # coin comes this close to the head joint ...
COIN_MOUTH_HEIGHT = 0.95          # ... at mouth height
RUB_MIN_SLIDE = 0.04
ROOT_MAX_OFFSET = 0.01
TABLE_TOP = 0.71                  # the figure below the table top ...
FIGURE_CENTRE_TOLERANCE = 0.04    # ... is centred on the node ...
HALF_TILE = 0.5                   # ... and stays inside its own tile
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


# Keep the delivered files byte-exact against the reviewed export, the atlases against the look of 2026-11-15.
def check_files(root):
    for relative, wanted in HASHES.items():
        with (root / relative).open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        assert digest.hexdigest() == wanted, ('Merchant asset changed', relative)


# The material block of one material in a material script text.
def material_block(script, name):
    block = re.search(r'^material ' + re.escape(name) + r'\s*\n\{.*?^}', script, re.M | re.S)
    assert block, name
    return block.group()


# Atlases with their normal maps on the body, opaque hand variants on the colour atlas, sizes and credits of every atlas.
def check_surfaces(root):
    script = (root / 'materials/scripts/MerchantApproved.material').read_text(encoding='utf-8')
    credits = (root / 'CREDITS').read_text(encoding='utf-8')
    for family, size in ATLASES.items():
        block = material_block(script, 'MerchantApproved' + family)
        assert 'normal_map tangent_space' in block, family
        for kind in ('Color', 'Normal'):
            name = 'Merchant' + family + 'Approved' + kind + '.png'
            assert 'texture ' + name in block, name
            relative = 'materials/textures/' + name
            with (root / relative).open('rb') as stream:
                header = stream.read(33)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', name
            assert struct.unpack('>II', header[16:24]) == (size, size), name
            assert relative in credits, name
    for family in HAND_FAMILIES:
        block = material_block(script, 'MerchantApproved' + family + 'Hand')
        assert 'texture Merchant' + family + 'ApprovedColor.png' in block, family
    for source in ('Fabric062', 'Fabric066', 'Leather014'):
        assert 'https://ambientcg.com/view?id=' + source in credits, source


# The hands must not be lit through a normal map nor blended (see-through hands, owner finding of 2026-11-17).
def check_opaque_hands(root, hand_materials):
    text = ''.join(p.read_text(encoding='utf-8', errors='replace')
                   for p in (root / 'materials' / 'scripts').glob('*.material'))
    assert hand_materials, 'no hand faces found'
    for name in hand_materials:
        block = material_block(text, name)
        for word in OPAQUE_FORBIDDEN:
            assert word not in block, (name, word)


# Stream the mesh: counts, bounds, node position, materials, complete skinning, legs, joints, hands and coins. Returns
# the materials of every face that touches a vertex bound mainly to a hand.
def check_mesh(path):
    weights = {}
    counts = dict(position=0, face=0)
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    low = [0.0, 0.0, 0]
    outside = 0
    faces = {}
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
                    faces.setdefault(material, [])
                continue
            if tag == 'position':
                value = [float(element.get(axis)) for axis in 'xyz']
                assert all(math.isfinite(v) for v in value)
                minimum = [min(a, b) for a, b in zip(minimum, value)]
                maximum = [max(a, b) for a, b in zip(maximum, value)]
                if value[2] < TABLE_TOP:
                    low[0] += value[0]
                    low[1] += value[1]
                    low[2] += 1
                    if max(abs(value[0]), abs(value[1])) >= HALF_TILE:
                        outside += 1
                counts['position'] += 1
            elif tag == 'face':
                triangle = tuple(int(element.get(axis)) for axis in ('v1', 'v2', 'v3'))
                assert all(0 <= index < VERTICES for index in triangle)
                faces[material].append(triangle)
                counts['face'] += 1
            elif tag == 'vertexboneassignment':
                index = int(element.get('vertexindex'))
                bone = int(element.get('boneindex'))
                weight = float(element.get('weight'))
                assert 0 <= index < VERTICES and 0 <= bone < len(BONES)
                assert math.isfinite(weight) and 0 < weight <= 1
                weights.setdefault(index, {})[bone] = weight
            elif tag == 'skeletonlink':
                skeleton = element.get('name')
            element.clear()
    assert counts == dict(position=VERTICES, face=TRIANGLES), counts
    assert set(faces) == MATERIALS, set(faces)
    assert all(abs(a - b) < .00002 for a, b in zip(minimum, MINIMUM)), minimum
    assert all(abs(a - b) < .00002 for a, b in zip(maximum, MAXIMUM)), maximum
    assert skeleton == 'Merchant.skeleton'
    assert low[2] and abs(low[0] / low[2]) <= FIGURE_CENTRE_TOLERANCE and abs(low[1] / low[2]) <= FIGURE_CENTRE_TOLERANCE, \
        ('the merchant does not stand on his own node position', low[0] / max(low[2], 1), low[1] / max(low[2], 1))
    assert outside == 0, ('the merchant reaches into the neighbouring tile', outside)
    assert len(weights) == VERTICES, 'Every vertex must remain bound'
    assert all(abs(sum(w.values()) - 1) < .001 for w in weights.values()), 'Every vertex must remain fully bound'
    assert all(1 <= len(w) <= 4 for w in weights.values()), 'Unsupported skin influence count'

    # Vertices bound mainly to one bone.
    def strong(bone):
        return [i for i, w in weights.items() if w.get(B[bone], 0.0) > 0.5]

    # Number of vertices blended between two bones.
    def blended(first, second):
        return sum(1 for w in weights.values()
                   if w.get(B[first], 0.0) > JOINT_BLEND_WEIGHT and w.get(B[second], 0.0) > JOINT_BLEND_WEIGHT)
    for side in ('R', 'L'):
        assert len(strong('Thigh_' + side)) >= THIGH_MIN_VERTICES, ('the legs do not follow the thigh', side)
        assert blended('Forearm_' + side, 'Hand_' + side) >= JOINT_BLEND_MIN_VERTICES, ('hard seam at the wrist', side)
        assert blended('UpperArm_' + side, 'Forearm_' + side) >= JOINT_BLEND_MIN_VERTICES, ('hard seam at the elbow', side)
    vertex_materials = {}
    for name, triangles in faces.items():
        for triangle in triangles:
            for index in triangle:
                vertex_materials.setdefault(index, set()).add(name)
    for bone, least in COIN_VERTICES.items():
        coin = strong(bone)
        assert len(coin) >= least, (bone, len(coin))
        assert set().union(*(vertex_materials.get(i, set()) for i in coin)) == {COIN_MATERIAL}, bone
    hands = set(strong('Hand_R')) | set(strong('Hand_L'))
    return {name for name, triangles in faces.items() if any(index in hands for t in triangles for index in t)}


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


# Verify the delivered merchant without loading its large XML into an in-memory tree. converted names a directory
# where this run already deserialized Merchant.mesh and Merchant.skeleton (after the hash check of this run), so the
# converter does not run twice; without it the files are deserialized here.
def verify_merchant_contract(root, converted=None):
    root = Path(root)
    started = time.perf_counter()
    check_files(root)
    check_surfaces(root)
    with tempfile.TemporaryDirectory(prefix='merchant-') as temporary:
        directory = Path(temporary)
        if converted is not None and (Path(converted) / 'Merchant.mesh.xml').is_file() and \
                (Path(converted) / 'Merchant.skeleton.xml').is_file():
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
