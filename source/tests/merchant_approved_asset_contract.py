"""Native geometry, texture, skeleton and motion contract of the merchant (INGAME-QS-10 K20, package A1b).

Owner finding of 2026-11-17: the variant-1 figure brought back by A1 looked worse than the merchant of 2026-11-15 that is
in the game; the owner wants that merchant kept and only reworked. So the delivered merchant is the model of 2026-11-15
(MerchantApproved atlases, look unchanged: the 20 atlases stay byte-exact) with the changes K20 names. This contract pins
the delivered files with fixed values counted once from the reviewed export and checks what the owner saw in the game, on
the clips the game plays (Idle, Walk, CountGold, RubHands), evaluated like Ogre does from the native skeleton:
  walk stiff        "die Arme komplett steif": in Walk each hand swings at least 0.2 forward and back, against the leg
                    of its side, the elbow bends and straightens, the chest turns and both feet stride; the legs are
                    skinned to the thighs (before, no vertex hung on a thigh and the trousers stayed on the pelvis)
  rubbing hands     owner finding on A1b: hunched and greedy, in Idle and RubHands the hands stay together in front of the
                    belly the whole clip (not a prayer pose at the chest)
  sleeves           owner finding on A1b ("die Arme sollten in den Aermeln der Jacke sein"): every sleeve and shoulder cape
                    vertex bound to an arm stays within SLEEVE_MAX_DISTANCE of the arm bones of its side, in the bind pose
                    and in every sampled pose of every clip (skinned like the game does), so no sleeve stands off the arm
  dark brown cloth  owner finding on A1b ("dunkelbraun", decisions 862/863): the hood and cloak atlases are a dark brown,
                    not the mottled olive: red at least 1.35 x green, blue 0.82-0.95 x green, mean hue under the yellow
                    front light at most 28 degrees, at most 10 % yellow-olive pixels, no large blotches
  coin              no coin was seen: the coin hangs in the right hand and the coin stack in the left hand, both with
                    gold geometry (before, no vertex hung on the coin bones); hidden (scale at most 0.05) in Idle, Walk and
                    RubHands, shown in the whole of CountGold, where the coin comes up to the mouth
                    in RubHands they rub (their height difference changes by at least 0.04)
  see-through hands "dann werden seine Haende transparent": every face of the hands uses an opaque hand material without
                    normal map, blending, alpha rejection or disabled depth writing (the tangent-space normal map is lit
                    wrong once GPU skinning turns the hand), and wrist and elbow are blended between their bones so the
                    skin does not open at a hard seam when the joint bends
  hands in sleeves  second owner finding on A1b ("Haende schweben neben den Aermeln"): in the bind pose and 12 poses of every
                    clip the wrist (first 3 cm of the hand skin) lies within CUFF_MAX_GAP of the centre of the cuff opening
                    (last 3 cm of the forearm sleeve), and no hand vertex is farther than HAND_MAX_DISTANCE from the forearm
                    and hand bones
  triangle budget   owner decision of 2026-11-17: about 33k triangles instead of 497k; the cloth keeps only its outer shell
                    (drawn from both sides), and a small software render of the bind pose from the game camera and from
                    the front differs from the reviewed render before the reduction by at most RENDER_MAX_MEAN_DIFFERENCE
  own node          the root bone binds at the origin, the bounding box of the figure below the table top is centred on the origin within
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
import base64
import zlib

import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import room_packages  # noqa: E402  (the merchant assets come from the merchant room package)

# Filled once from the reviewed export of 2026-11-17 (A1b rework), never derived from the assets during a test.
VERTICES = 47741
TRIANGLES = 32601
MINIMUM = (-0.318828, -0.253266, 0.00864491)
MAXIMUM = (0.318643, 0.243533, 1.3038)
HASHES = {
    'models/Merchant.mesh': '9727c328e5eb948557b25633f21905d4f746a6f6af1c8bcd52d1e1c76f7dad29',
    'models/Merchant.skeleton': '90dd8c3da6bbab8f838b3aae379c093e7dfa8a893352b0b77d42639d373a88fa',
    # The look of the merchant of 2026-11-15: the baked atlases stay byte-exact, hood and cloak colour recoloured dark brown
    'materials/textures/MerchantBrassApprovedColor.png': '13e0088f101ba4207e80a63c091ed4bbb236abb751ca4b5dae95a32f30add3bb',
    'materials/textures/MerchantBrassApprovedNormal.png': 'f559243be3489daa2d323ee85f3329346dc1f4c416d77087b02c3ea3a6a4309a',
    'materials/textures/MerchantCloakApprovedColor.png': '87a5418e3ad0b4a9cb4721b9d1bd5acd680143ddd8b516dbfa69142ade971524',
    'materials/textures/MerchantCloakApprovedNormal.png': '116205b04f27035ec83ac4d1d0821a367ae532643ed9714304c1c6375c820205',
    'materials/textures/MerchantDetailsApprovedColor.png': '05c66a1f06fc1a083f46ea46b4756f245ccc58df61bc262a244d9410dceacdf9',
    'materials/textures/MerchantDetailsApprovedNormal.png': 'ca7533d30a23ba2613f963f0976fdcdc5b3a7b0d49772d16062eedb4b2cbeef0',
    'materials/textures/MerchantGoldApprovedColor.png': '89f19664b2cf1e7783cbc7a35f7933fa6763ba4aeac073698cf4bd29eaa17e73',
    'materials/textures/MerchantGoldApprovedNormal.png': '51b606bd56088b165f734de7d6f6c1fbf174ebf9b091dcafafea9a6eec3d4d6a',
    'materials/textures/MerchantHairApprovedColor.png': '8a7f782dc060c358d00484ee76a555dd33213e556a378d75534000da647ee643',
    'materials/textures/MerchantHairApprovedNormal.png': '1019976e0f4208990906e5a03f82024fa7424830e41bd6fd43b3e5f9a72291c9',
    'materials/textures/MerchantHideApprovedColor.png': '4b42b80dce02d37b9cb0a4b4d39d66c880d78928adfaecf7ab0cf64cfa3165a7',
    'materials/textures/MerchantHideApprovedNormal.png': 'cf6f6fe2ae5cd4ac4c2345227dbcd24a319f19e0ff6514cc601f6c38df3c40ee',
    'materials/textures/MerchantHoodApprovedColor.png': '75b0d50fc8cfdd0241bc6fed8cb7998810a55a77bb29a8f9a8db72178c19a89e',
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
# Cloth reduced to its outer shell (triangle budget): drawn from both sides
SINGLE_SHELL = ('Robe', 'Cloak', 'Hood')
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
# Least vertices bound to each thigh (export: 1057 and 959; before: none)
THIGH_MIN_VERTICES = 900
# Least vertices blended between forearm and hand and between upper arm and forearm on each side (export: 310 to 425;
# before: none, hard seams)
JOINT_BLEND_MIN_VERTICES = 250
JOINT_BLEND_WEIGHT = 0.1
SAMPLES = 48
WALK_MIN_HAND_SWING = 0.2         # forward and back travel of each hand in Walk
WALK_MIN_ELBOW = 0.15             # change of the elbow angle in Walk (radians)
WALK_MIN_CHEST_TURN = 0.1         # change of the chest rotation in Walk (radians)
WALK_MIN_FOOT_STRIDE = 0.15       # forward and back travel of each foot in Walk
CLASP_MAX_DISTANCE = 0.14         # hands together
BELLY_HEIGHT = (0.62, 0.85)       # wrists in front of the belly, not hanging (bind pose: wrists at 0.60) nor at the chest
CLASP_MAX_FRONT = -0.17           # in front of the body (front is -Y)
# Sleeves and shoulder cape: cloth vertices bound mainly to the arm bones of one side
SLEEVE_MATERIALS = ('MerchantApprovedCloak', 'MerchantApprovedLinen', 'MerchantApprovedHood', 'MerchantApprovedRobe')
SLEEVE_MIN_VERTICES = 1500
SLEEVE_MIN_ARM_WEIGHT = 0.75     # sleeve cloth: bound at least this much to the arm (cape cloth in between is shared)
SLEEVE_MAX_DISTANCE = 0.13        # from the shoulder-elbow-wrist-hand bones (export: 0.124, rejected A1b: 0.176)
SLEEVE_MAX_P99 = 0.11             # 99 % of the sleeve cloth (export: 0.105; the single outer cloth shell)
SLEEVE_SAMPLES = 12               # sampled poses per clip for the sleeve and hand checks
# Hands at the end of the sleeves (owner finding on A1b: "Haende schweben neben den Aermeln")
HAND_SKIN_MATERIAL = 'MerchantApprovedHideHand'
HAND_MIN_VERTICES = 100
CUFF_DEPTH = 0.03                 # cuff opening = last 3 cm of the forearm sleeve, wrist = first 3 cm of the hand
CUFF_MAX_GAP = 0.095              # cuff centre to wrist centre (export: 0.088; floating hands of the rejected rework: 0.115)
HAND_TIP = np.array((0.043, 0.0, -0.134))  # finger tips of the right hand from its wrist joint in the bind pose
HAND_MAX_DISTANCE = 0.075         # hand skin from the forearm and hand bones (export: 0.068)
# Render comparison against the merchant before the triangle reduction (bind pose, flat atlas colour, two-sided light)
RENDER_PIXEL = 0.0125
RENDER_HALF_WIDTH = 0.45
RENDER_LIGHT = (-0.4, -0.6, 0.7)
RENDER_AMBIENT = 0.35
VIEWS = {'game': ((0.0, math.sin(math.radians(25)), -math.cos(math.radians(25))),
                  (0.0, math.cos(math.radians(25)), math.sin(math.radians(25))), -0.35, 0.85),
         'front': ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.0, 1.35)}
RENDER_MAX_MEAN_DIFFERENCE = 4.0  # export: game 2.0, front 2.9
RENDER_MIN_SILHOUETTE_OVERLAP = 0.97  # export: game 0.986, front 0.984
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the merchant before the reduction (reviewed 2026-11-17)
    'game': ((96, 72, 3), (
        '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'
    )),
    'front': ((108, 72, 3), (
        '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'
    )),
}
# Dark brown hood and cloak (decisions 836/862/863), measured on the 2048 atlases in 8 x 8 blocks
BROWN_ATLASES = ('materials/textures/MerchantHoodApprovedColor.png', 'materials/textures/MerchantCloakApprovedColor.png')
BROWN_MIN_RED_OVER_GREEN = 1.35
BROWN_BLUE_OVER_GREEN = (0.82, 0.95)
FRONT_LIGHT = (1.0, 0.94, 0.64)
BROWN_MAX_LIT_HUE = 28.0
OLIVE_HUE = (35.0, 90.0)
OLIVE_MIN_SATURATION = 0.15
BROWN_MAX_OLIVE_SHARE = 0.10
BROWN_MAX_BLOCK_STD = 7.0
BROWN_LUMINANCE = (30.0, 50.0)    # dark brown (mottled olive of 2026-11-15: 40 / 43 at r/g 1.22, 80 % olive pixels)
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
                    str(room_packages.resolve(root, 'models/' + filename)), str(output)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=120, check=True)
    return output


# Keep the delivered files byte-exact against the reviewed export, the atlases against the look of 2026-11-15.
def check_files(root):
    for relative, wanted in HASHES.items():
        with room_packages.resolve(root, relative).open('rb') as stream:
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
    script = room_packages.resolve(root, 'materials/scripts/MerchantApproved.material').read_text(encoding='utf-8')
    credits = room_packages.credits_text(root)
    for family, size in ATLASES.items():
        block = material_block(script, 'MerchantApproved' + family)
        assert 'normal_map tangent_space' in block, family
        for kind in ('Color', 'Normal'):
            name = 'Merchant' + family + 'Approved' + kind + '.png'
            assert 'texture ' + name in block, name
            relative = 'materials/textures/' + name
            with room_packages.resolve(root, relative).open('rb') as stream:
                header = stream.read(33)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', name
            assert struct.unpack('>II', header[16:24]) == (size, size), name
            assert relative in credits, name
    for family in SINGLE_SHELL:
        block = material_block(script, 'MerchantApproved' + family)
        assert 'cull_hardware none' in block and 'cull_software none' in block, ('single cloth shell drawn one-sided', family)
    for family in HAND_FAMILIES:
        block = material_block(script, 'MerchantApproved' + family + 'Hand')
        assert 'texture Merchant' + family + 'ApprovedColor.png' in block, family
    for source in ('Fabric062', 'Fabric066', 'Leather014'):
        assert 'https://ambientcg.com/view?id=' + source in credits, source


# Hood and cloak atlases are a dark brown, not the mottled olive (decisions 862/863, owner finding on A1b).
def check_brown_cloth(root):
    for relative in BROWN_ATLASES:
        rgb = np.asarray(Image.open(room_packages.resolve(root, relative)).convert('RGB'), dtype=np.float64)
        mean = rgb.reshape(-1, 3).mean(0)
        luminance = rgb @ np.array([0.299, 0.587, 0.114])
        assert BROWN_LUMINANCE[0] <= luminance.mean() <= BROWN_LUMINANCE[1], (relative, luminance.mean())
        assert mean[0] >= BROWN_MIN_RED_OVER_GREEN * mean[1], (relative, 'not brown', mean)
        assert BROWN_BLUE_OVER_GREEN[0] * mean[1] <= mean[2] <= BROWN_BLUE_OVER_GREEN[1] * mean[1], (relative, mean)
        lit = rgb * np.array(FRONT_LIGHT)
        lm = mean * np.array(FRONT_LIGHT)
        hue = 60.0 * (lm[1] - lm[2]) / (lm[0] - lm[2])
        assert lm[0] >= lm[1] >= lm[2] and hue <= BROWN_MAX_LIT_HUE, (relative, 'olive under the front light', hue)
        hi, lo = lit.max(-1), lit.min(-1)
        span = hi - lo
        safe = np.where(span > 0, span, 1.0)
        r, g, b = lit[..., 0], lit[..., 1], lit[..., 2]
        h = np.where(hi == r, (60.0 * (g - b) / safe) % 360.0,
                     np.where(hi == g, 60.0 * ((b - r) / safe + 2), 60.0 * ((r - g) / safe + 4)))
        s = np.where(hi + lo <= 255, span / np.maximum(hi + lo, 1e-9), span / np.maximum(510.0 - hi - lo, 1e-9))
        olive = ((span > 0) & (h >= OLIVE_HUE[0]) & (h <= OLIVE_HUE[1]) & (s >= OLIVE_MIN_SATURATION)).mean()
        assert olive <= BROWN_MAX_OLIVE_SHARE, (relative, 'yellow-olive pixels', olive)
        n = luminance.shape[0] // 8
        blocks = luminance[:8 * n, :8 * n].reshape(8, n, 8, n).mean((1, 3))
        assert blocks.std() <= BROWN_MAX_BLOCK_STD, (relative, 'large camouflage blotches', blocks.std())


# The hands must not be lit through a normal map nor blended (see-through hands, owner finding of 2026-11-17).
def check_opaque_hands(root, hand_materials):
    text = ''.join(p.read_text(encoding='utf-8', errors='replace')
                   for p in room_packages.glob_files(root, 'materials/scripts', '*.material'))
    assert hand_materials, 'no hand faces found'
    for name in hand_materials:
        block = material_block(text, name)
        for word in OPAQUE_FORBIDDEN:
            assert word not in block, (name, word)


# Stream the mesh: counts, bounds, node position, materials, complete skinning, legs, joints, hands and coins. Returns
# the materials of every face that touches a vertex bound mainly to a hand.
def check_mesh(path):
    weights = {}
    counts = dict(position=0, normal=0, tangent=0, texcoord=0, face=0)
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    low = [math.inf, math.inf, -math.inf, -math.inf]
    outside = 0
    faces = {}
    positions = []
    uvs = []
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
                    low = [min(low[0], value[0]), min(low[1], value[1]), max(low[2], value[0]), max(low[3], value[1])]
                    if max(abs(value[0]), abs(value[1])) >= HALF_TILE:
                        outside += 1
                positions.append(value)
                counts['position'] += 1
            elif tag in ('normal', 'tangent'):
                # unit normals and tangents with a handedness of +-1 for the lighting and the normal maps
                value = [float(element.get(axis)) for axis in 'xyz']
                assert all(math.isfinite(v) for v in value), tag
                assert abs(math.sqrt(sum(v * v for v in value)) - 1.0) < .005, (tag, value)
                if tag == 'tangent':
                    assert abs(abs(float(element.get('w'))) - 1.0) < .001, ('tangent handedness', element.get('w'))
                counts[tag] += 1
            elif tag == 'texcoord':
                uv = (float(element.get('u')), float(element.get('v')))
                # every texture coordinate inside the atlas (the atlases use clamp addressing)
                assert all(-.0001 <= value <= 1.0001 for value in uv), ('texture coordinate outside the atlas', uv)
                uvs.append(uv)
                counts['texcoord'] += 1
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
    assert counts == dict(position=VERTICES, normal=VERTICES, tangent=VERTICES, texcoord=VERTICES, face=TRIANGLES), counts
    assert set(faces) == MATERIALS, set(faces)
    assert all(abs(a - b) < .00002 for a, b in zip(minimum, MINIMUM)), minimum
    assert all(abs(a - b) < .00002 for a, b in zip(maximum, MAXIMUM)), maximum
    assert skeleton == 'Merchant.skeleton'
    # centre of the bounding box of the figure below the table top (a vertex average would follow the mesh density)
    centre = ((low[0] + low[2]) / 2, (low[1] + low[3]) / 2)
    assert abs(centre[0]) <= FIGURE_CENTRE_TOLERANCE and abs(centre[1]) <= FIGURE_CENTRE_TOLERANCE, \
        ('the merchant does not stand on his own node position', centre)
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
    hand_materials = {name for name, triangles in faces.items() if any(index in hands for t in triangles for index in t)}
    matrix = np.zeros((VERTICES, len(BONES)))
    for i, w in weights.items():
        for bone, weight in w.items():
            matrix[i, bone] = weight
    points = np.array(positions)
    cloth = np.zeros(VERTICES, bool)
    skin = np.zeros(VERTICES, bool)
    for name, triangles in faces.items():
        flat = np.array(triangles, dtype=np.int64).ravel()
        if name in SLEEVE_MATERIALS:
            cloth[flat] = True
        if name == HAND_SKIN_MATERIAL:
            skin[flat] = True
    groups = {}
    for side in ('R', 'L'):
        arm = [B['UpperArm_' + side], B['Forearm_' + side], B['Hand_' + side]]
        # sleeve and cape cloth bound mainly to the arm bones of one side
        sleeve = np.nonzero(cloth & (matrix[:, arm].sum(1) > SLEEVE_MIN_ARM_WEIGHT))[0]
        assert len(sleeve) >= SLEEVE_MIN_VERTICES, ('too few sleeve vertices', side, len(sleeve))
        groups['sleeve_' + side] = sleeve
        # the hand skin and the cloth of the forearm sleeve
        hand = np.nonzero(skin & (matrix[:, B['Hand_' + side]] > 0.5))[0]
        fore = np.nonzero(cloth & (matrix[:, B['Forearm_' + side]] > 0.5))[0]
        assert len(hand) >= HAND_MIN_VERTICES and len(fore) >= HAND_MIN_VERTICES, ('hand or forearm sleeve missing', side)
        groups['hand_' + side] = hand
        groups['forearm_cloth_' + side] = fore
    return hand_materials, dict(points=points, uvs=np.array(uvs), faces=faces, matrix=matrix, groups=groups)


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
def check_skeleton(path, mesh=None):
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

    for name in ('Idle', 'RubHands'):
        for w in poses[name]:
            assert distance(w['Hand_R'][0], w['Hand_L'][0]) <= CLASP_MAX_DISTANCE, ('hands not together', name)
            for side in ('Hand_R', 'Hand_L'):
                assert BELLY_HEIGHT[0] <= w[side][0][2] <= BELLY_HEIGHT[1] and w[side][0][1] <= CLASP_MAX_FRONT, \
                    ('hands not in front of the belly', name, side, w[side][0])
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
    if mesh is not None:
        rest = pose(bones, parents, {}, 0.0)
        bind = {name: np.array(rest[name][0]) for name in BONES}
        samples = [rest] + [pose(bones, parents, tracks, length * i / SLEEVE_SAMPLES)
                            for length, tracks in clips.values() for i in range(SLEEVE_SAMPLES)]
        groups = mesh['groups']
        for side in ('R', 'L'):
            sleeve = groups['sleeve_' + side]
            hand = groups['hand_' + side]
            fore = groups['forearm_cloth_' + side]
            # cuff opening and wrist in the bind pose: the last CUFF_DEPTH of the forearm sleeve and the first
            # CUFF_DEPTH of the hand skin along the forearm bone
            axis = bind['Hand_' + side] - bind['Forearm_' + side]
            axis /= np.linalg.norm(axis)
            along = (mesh['points'][fore] - bind['Forearm_' + side]) @ axis
            cuff = fore[along >= along.max() - CUFF_DEPTH]
            along = (mesh['points'][hand] - bind['Forearm_' + side]) @ axis
            wrist = hand[along <= along.min() + CUFF_DEPTH]
            for world in samples:
                check_sleeve(skin_points(mesh, sleeve, bind, world), world, side)
                gap = np.linalg.norm(skin_points(mesh, cuff, bind, world).mean(0) - skin_points(mesh, wrist, bind, world).mean(0))
                assert gap <= CUFF_MAX_GAP, ('the hand is not in its sleeve cuff', side, float(gap))
                joints = [np.array(world[name][0]) for name in ('Forearm_' + side, 'Hand_' + side)]
                joints.append(joints[1] + rotation_matrix(world['Hand_' + side][1]) @ hand_tip(side))
                near = np.min([segment_distance(skin_points(mesh, hand, bind, world), a, b)
                               for a, b in zip(joints, joints[1:])], axis=0)
                assert near.max() <= HAND_MAX_DISTANCE, ('a hand floats beside its forearm', side, float(near.max()))


# Finger tips from the wrist joint of one side in the bind pose (the left hand mirrors the right one).
def hand_tip(side):
    return HAND_TIP * np.array([1.0 if side == 'R' else -1.0, 1.0, 1.0])


# Skins the given vertices like Ogre (linear blend, every bind rotation is the identity).
def skin_points(mesh, indices, bind, world):
    points = mesh['points'][indices]
    matrix = mesh['matrix'][indices]
    skinned = np.zeros_like(points)
    for bone in np.nonzero(matrix.any(0))[0]:
        name = BONES[bone]
        moved = (points - bind[name]) * world[name][2]
        skinned += matrix[:, bone:bone + 1] * (moved @ rotation_matrix(world[name][1]).T + np.array(world[name][0]))
    return skinned


# Rotation matrix of a unit quaternion (w, x, y, z).
def rotation_matrix(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


# Distance of every point to the segment a-b.
def segment_distance(points, a, b):
    ab = b - a
    t = np.clip(((points - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(points - (a + t[:, None] * ab), axis=1)


# Every sleeve and cape vertex stays close to the shoulder-elbow-wrist-hand bones of its side.
def check_sleeve(skinned, world, side):
    joints = [np.array(world[name][0]) for name in ('UpperArm_' + side, 'Forearm_' + side, 'Hand_' + side)]
    joints.append(joints[2] + rotation_matrix(world['Hand_' + side][1]) @ hand_tip(side))
    near = np.min([segment_distance(skinned, a, b) for a, b in zip(joints, joints[1:])], axis=0)
    assert near.max() <= SLEEVE_MAX_DISTANCE, ('a sleeve stands off the arm', side, float(near.max()))
    assert np.percentile(near, 99) <= SLEEVE_MAX_P99, ('the sleeves stand off the arm', side, float(np.percentile(near, 99)))


# Colour of every triangle: its material's colour atlas at the triangle's UV centre (Ogre v runs downwards).
def triangle_colours(root, mesh):
    script = room_packages.resolve(root, 'materials/scripts/MerchantApproved.material').read_text(encoding='utf-8')
    colours, triangles = [], []
    for name in sorted(mesh['faces']):
        texture = re.search(r'texture\s+(\S+Color\.png)', material_block(script, name)).group(1)
        image = np.asarray(Image.open(room_packages.resolve(root, 'materials/textures/' + texture)).convert('RGB'), dtype=np.float64)
        tri = np.array(mesh['faces'][name], dtype=np.int64)
        uv = mesh['uvs'][tri].mean(1)
        h, w = image.shape[:2]
        colours.append(image[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)])
        triangles.append(tri)
    return np.concatenate(triangles), np.concatenate(colours)


# Small depth-buffered orthographic render of the bind pose: flat colour of the atlas times a two-sided Lambert light.
def render_view(points, triangles, colours, view):
    forward, up, low, high = VIEWS[view]
    forward = np.array(forward) / np.linalg.norm(forward)
    up = np.array(up) / np.linalg.norm(up)
    right = np.cross(forward, up)
    width = int(round(2 * RENDER_HALF_WIDTH / RENDER_PIXEL))
    height = int(round((high - low) / RENDER_PIXEL))
    sx = (points @ right + RENDER_HALF_WIDTH) / RENDER_PIXEL
    sy = (high - points @ up) / RENDER_PIXEL
    depth_of = points @ forward
    light = np.array(RENDER_LIGHT) / np.linalg.norm(RENDER_LIGHT)
    image = np.zeros((height, width, 3))
    depth = np.full((height, width), np.inf)
    a, b, c = points[triangles[:, 0]], points[triangles[:, 1]], points[triangles[:, 2]]
    normal = np.cross(b - a, c - a)
    normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]
    shade = RENDER_AMBIENT + (1 - RENDER_AMBIENT) * np.abs(normal @ light)
    for k, (i, j, l) in enumerate(triangles):
        xs = (sx[i], sx[j], sx[l])
        ys = (sy[i], sy[j], sy[l])
        x0, x1 = max(int(math.floor(min(xs))), 0), min(int(math.ceil(max(xs))), width - 1)
        y0, y1 = max(int(math.floor(min(ys))), 0), min(int(math.ceil(max(ys))), height - 1)
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-12:
            continue
        w1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / area
        w2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / area
        w0 = 1 - w1 - w2
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * depth_of[i] + w1 * depth_of[j] + w2 * depth_of[l]
        block = depth[y0:y1 + 1, x0:x1 + 1]
        nearer = inside & (z < block)
        block[nearer] = z[nearer]
        image[y0:y1 + 1, x0:x1 + 1][nearer] = colours[k] * shade[k]
    return np.clip(image, 0, 255).astype(np.uint8)


# Render comparison (owner decision on the triangle budget): the reduced merchant seen from the game camera and from the
# front differs from the reviewed render of the merchant before the reduction by at most RENDER_MAX_MEAN_DIFFERENCE
# (mean absolute difference per channel, 0..255) and covers the same silhouette (intersection over union).
def check_render(root, mesh):
    triangles, colours = triangle_colours(root, mesh)
    for view, (shape, encoded) in RENDER_REFERENCE.items():
        reference = np.frombuffer(zlib.decompress(base64.b64decode(encoded)), dtype=np.uint8).reshape(shape)
        image = render_view(mesh['points'], triangles, colours, view)
        assert image.shape == reference.shape, (view, image.shape)
        difference = np.abs(image.astype(np.float64) - reference).mean()
        assert difference <= RENDER_MAX_MEAN_DIFFERENCE, ('the reduced merchant looks different', view, difference)
        a, b = image.any(-1), reference.any(-1)
        overlap = (a & b).sum() / max((a | b).sum(), 1)
        assert overlap >= RENDER_MIN_SILHOUETTE_OVERLAP, ('the reduced merchant has another silhouette', view, overlap)


# Verify the delivered merchant without loading its large XML into an in-memory tree. converted names a directory
# where this run already deserialized Merchant.mesh and Merchant.skeleton (after the hash check of this run), so the
# converter does not run twice; without it the files are deserialized here.
def verify_merchant_contract(root, converted=None):
    root = Path(root)
    started = time.perf_counter()
    check_files(root)
    check_surfaces(root)
    check_brown_cloth(root)
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
        hand_materials, data = check_mesh(mesh)
        check_opaque_hands(root, hand_materials)
        check_skeleton(skeleton, data)
        check_render(root, data)
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'native asset validation', 'seconds': time.perf_counter() - prepared}))
