"""Native geometry, texture, skeleton and motion contract of the CS10a merchant (approved Meshy figure, 2026-11-26).

Since CS10a the merchant is the Meshy figure the owner approved: one closed surface with one material (MerchantMeshy,
one colour texture, no normal map and no tangents) on the shared 24-bone humanoid rig of the creature figures, without
extra parts (no coin, coin stack or scales bones). This contract takes over what merchant_approved_asset_contract.py
checks on the merchant of 2026-11-15, formally adapted to that layout, with fixed values counted once from the approved
export:
  files             mesh, skeleton and colour texture byte-exact, the material names the texture, CREDITS rows
  geometry          vertex and triangle counts, bounds, every vertex fully bound to one to four bones, the legs skinned
                    to the thighs, the wrists and elbows blended between their bones (no hard seam)
  own node          the root bone binds beside the node by at most ROOT_MAX_OFFSET, the bounding box of the figure below
                    the table top is centred on the origin within 0.04 and stays inside its own tile
  opaque hands      the hand faces use a material without normal map, blending, alpha rejection or disabled depth writing
  clips and motion  the clips the game plays with their lengths (Idle, Walk, CountGold, RubHands), closed loops, the arm
                    swing, elbow, chest turn and stride in Walk, the hands together in front of the belly in Idle and
                    RubHands and rubbing in RubHands
  sleeves and hands in the bind pose and in sampled poses of every clip the cloth bound to an arm stays near the arm
                    bones, the wrist stays in its cuff and no hand vertex floats beside the forearm and hand bones
                    (skinned like Ogre with the bind rotations of the rig)
  look              a small software render of the bind pose from the game camera and from the front differs from the
                    stored render of the approved figure by at most RENDER_MAX_MEAN_DIFFERENCE
Not taken over (the approved figure has no such parts): the coin and coin stack bones and their gold geometry, the
scales bone, the separate cloth, hood and hand atlases with their brown-cloth colour checks, the single-shell cloth
materials.
"""
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import time
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from PIL import Image

import merchant_approved_asset_contract as approved
from merchant_approved_asset_contract import (asset_file, axis_angle, deserialize, distance, material_block, pose,
                                              qangle, render_view, rotation_matrix, segment_distance, spread)
import room_packages  # noqa: E402  (CREDITS of the public tree and the content repository)

MATERIAL = 'MerchantMeshy'
SCRIPT = 'materials/scripts/Creatures/MerchantMeshy.material'
TEXTURE = 'materials/textures/MerchantMeshy.png'
# Filled once from the approved CS10a export (2026-11-26), never derived from the assets during a test.
VERTICES = 7679
TRIANGLES = 9429
MINIMUM = (-0.643582, -0.184547, 0.0)
MAXIMUM = (0.643582, 0.184547, 1.29516)
HASHES = {
    'models/Merchant.mesh': 'f45b2c7948aaf050659c41920da5671614e9ede058d92ea6c05f4d5d3e4d70b3',
    'models/Merchant.skeleton': 'a8196309f4793764f5e26f2bcd1932e18410dd4031f3968da3d35347dfd91b63',
    TEXTURE: '3f28d6fbff3a40e8404000b8fe6db7e8e0d1b444aa8fd32ae1da8d891399db4b',
}
# The clips the game plays for the merchant (unchanged from the merchant of 2026-11-15)
CLIPS = approved.CLIPS
BONES = ('Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase', 'RightUpLeg', 'RightLeg', 'RightFoot',
         'RightToeBase', 'Spine02', 'Spine01', 'Spine', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand', 'neck',
         'Head', 'head_end', 'headfront', 'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')
B = {name: index for index, name in enumerate(BONES)}
# Bones of the rig by their role in the motion checks (right side at -x, the figure faces -y)
ARM = {'R': ('RightArm', 'RightForeArm', 'RightHand'), 'L': ('LeftArm', 'LeftForeArm', 'LeftHand')}
THIGH = {'R': 'RightUpLeg', 'L': 'LeftUpLeg'}
FOOT = {'R': 'RightFoot', 'L': 'LeftFoot'}
CHEST = 'Spine'
# Least vertices per skinning group of the approved export (counted once: thighs 403 / 409, wrist blends 70 / 85,
# elbow blends 64 / 55, arm cloth 603 / 592; the merchant of 2026-11-15 had about six times the vertices)
THIGH_MIN_VERTICES = 360
JOINT_BLEND_MIN_VERTICES = 50
SLEEVE_MIN_VERTICES = 530
# Finger tips from the wrist joint in the bind frame of each hand bone (measured once on the approved export)
HAND_TIP = {'R': np.array((-0.003, 0.166, -0.022)), 'L': np.array((-0.004, 0.172, -0.009))}
ROOT_MAX_OFFSET = approved.ROOT_MAX_OFFSET
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the approved CS10a merchant (render_view of the approved
    # contract, delivered mesh and MerchantMeshy.png, 2026-11-26)
    'game': ((96, 72, 3), (
        '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'
    )),
    'front': ((108, 72, 3), (
        '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'
    )),
}


# Keep the delivered files byte-exact against the approved export; the material names the texture; CREDITS rows.
def check_files(root):
    for relative, wanted in HASHES.items():
        with asset_file(root, relative).open('rb') as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == wanted, ('Merchant asset changed', relative)
    block = material_block(asset_file(root, SCRIPT).read_text(encoding='utf-8'), MATERIAL)
    assert 'texture MerchantMeshy.png' in block, 'MerchantMeshy must use its colour texture'
    credits = room_packages.credits_text(root)
    for relative in list(HASHES) + [SCRIPT]:
        assert re.search(r'^' + re.escape(relative) + r'\s', credits, re.M), 'CREDITS has no row for ' + relative


# Stream the mesh: counts, bounds, node position, material, complete skinning, legs and joints. Returns the materials
# of the faces that touch a vertex bound mainly to a hand and the data for the skinned checks.
def check_mesh(path):
    root = ET.parse(path).getroot()
    geometry = root.find('sharedgeometry')
    assert int(geometry.get('vertexcount')) == VERTICES
    points = np.array([[float(p.get(c)) for c in 'xyz'] for p in geometry.iter('position')])
    normals = np.array([[float(p.get(c)) for c in 'xyz'] for p in geometry.iter('normal')])
    uvs = np.array([[float(t.get('u')), float(t.get('v'))] for t in geometry.iter('texcoord')])
    assert len(points) == len(normals) == len(uvs) == VERTICES and not list(geometry.iter('tangent'))
    assert np.isfinite(points).all() and np.allclose(np.linalg.norm(normals, axis=1), 1.0, atol=.005)
    assert ((uvs >= -.0001) & (uvs <= 1.0001)).all(), 'texture coordinate outside the atlas'
    faces = {}
    for sub in root.find('submeshes'):
        rows = [tuple(int(f.get(k)) for k in ('v1', 'v2', 'v3')) for f in sub.find('faces')]
        faces.setdefault(sub.get('material'), []).extend(rows)
    assert set(faces) == {MATERIAL}, set(faces)
    assert sum(len(f) for f in faces.values()) == TRIANGLES
    assert all(0 <= i < VERTICES for f in faces.values() for t in f for i in t)
    assert np.allclose(points.min(0), MINIMUM, atol=.00002), points.min(0)
    assert np.allclose(points.max(0), MAXIMUM, atol=.00002), points.max(0)
    assert root.find('skeletonlink').get('name') == 'Merchant.skeleton'
    low = points[points[:, 2] < approved.TABLE_TOP]
    centre = ((low[:, 0].min() + low[:, 0].max()) / 2, (low[:, 1].min() + low[:, 1].max()) / 2)
    assert abs(centre[0]) <= approved.FIGURE_CENTRE_TOLERANCE and abs(centre[1]) <= approved.FIGURE_CENTRE_TOLERANCE, \
        ('the merchant does not stand on his own node position', centre)
    assert not (np.abs(low[:, :2]).max(1) >= approved.HALF_TILE).any(), 'the merchant reaches into the neighbouring tile'
    matrix = np.zeros((VERTICES, len(BONES)))
    for va in root.iter('vertexboneassignment'):
        weight = float(va.get('weight'))
        assert math.isfinite(weight) and 0 < weight <= 1
        matrix[int(va.get('vertexindex')), int(va.get('boneindex'))] = weight
    assert np.allclose(matrix.sum(1), 1.0, atol=.001), 'Every vertex must remain fully bound'
    assert ((matrix > 0).sum(1) <= 4).all(), 'Unsupported skin influence count'
    groups = {}
    for side in ('R', 'L'):
        upper, fore, hand = (B[name] for name in ARM[side])
        assert (matrix[:, B[THIGH[side]]] > .5).sum() >= THIGH_MIN_VERTICES, ('the legs do not follow the thigh', side)
        joint = approved.JOINT_BLEND_WEIGHT
        assert ((matrix[:, fore] > joint) & (matrix[:, hand] > joint)).sum() >= JOINT_BLEND_MIN_VERTICES, \
            ('hard seam at the wrist', side)
        assert ((matrix[:, upper] > joint) & (matrix[:, fore] > joint)).sum() >= JOINT_BLEND_MIN_VERTICES, \
            ('hard seam at the elbow', side)
        sleeve = np.nonzero(matrix[:, [upper, fore, hand]].sum(1) > approved.SLEEVE_MIN_ARM_WEIGHT)[0]
        assert len(sleeve) >= SLEEVE_MIN_VERTICES, ('too few sleeve vertices', side, len(sleeve))
        groups['sleeve_' + side] = sleeve
        groups['hand_' + side] = np.nonzero(matrix[:, hand] > .5)[0]
        groups['forearm_cloth_' + side] = np.nonzero(matrix[:, fore] > .5)[0]
        assert min(len(groups['hand_' + side]), len(groups['forearm_cloth_' + side])) >= approved.HAND_MIN_VERTICES, \
            ('hand or forearm sleeve missing', side)
    hands = set(groups['hand_R']) | set(groups['hand_L'])
    hand_materials = {name for name, rows in faces.items() if any(i in hands for t in rows for i in t)}
    return hand_materials, dict(points=points, uvs=uvs, faces=faces, matrix=matrix, groups=groups)


# The hands must not be lit through a normal map nor blended (see-through hands, owner finding of 2026-11-17); the
# figure material lies in its own script of the content package creatures.
def check_opaque_hands(root, hand_materials):
    script = asset_file(root, SCRIPT).read_text(encoding='utf-8')
    assert hand_materials, 'no hand faces found'
    for name in hand_materials:
        block = material_block(script, name)
        for word in approved.OPAQUE_FORBIDDEN:
            assert word not in block, (name, word)


# Skins the given vertices like Ogre: linear blend of every bone's move from its bind pose (bind rotations included).
def skin_points(mesh, indices, bind, world):
    points = mesh['points'][indices]
    matrix = mesh['matrix'][indices]
    skinned = np.zeros_like(points)
    for bone in np.nonzero(matrix.any(0))[0]:
        name = BONES[bone]
        turn = rotation_matrix(world[name][1]) @ rotation_matrix(bind[name][1]).T
        moved = (points - bind[name][0]) * world[name][2]
        skinned += matrix[:, bone:bone + 1] * (moved @ turn.T + np.array(world[name][0]))
    return skinned


# Finger tips of one hand in a pose: the wrist joint plus the bind-frame tip offset turned with the hand bone.
def hand_tip(world, side):
    hand = ARM[side][2]
    return np.array(world[hand][0]) + rotation_matrix(world[hand][1]) @ HAND_TIP[side]


# Joint hierarchy, bind of the root, clips, closed loops and the motions the owner asked for; sleeves and hands.
def check_skeleton(path, mesh):
    tree = ET.parse(path).getroot()
    bones = []
    for bone in tree.findall('./bones/bone'):
        p = bone.find('position')
        bones.append((bone.get('name'), tuple(float(p.get(k)) for k in 'xyz'), axis_angle(bone.find('rotation'))))
    assert tuple(b[0] for b in bones) == BONES, tuple(b[0] for b in bones)
    parents = {p.get('bone'): p.get('parent') for p in tree.findall('./bonehierarchy/boneparent')}
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
            tracks[track.get('bone')] = keys
        clips[clip.get('name')] = (float(clip.get('length')), tracks)
    assert {name: value[0] for name, value in clips.items()} == CLIPS, {name: value[0] for name, value in clips.items()}
    poses = {}
    for name, (length, tracks) in clips.items():
        poses[name] = [pose(bones, parents, tracks, length * i / approved.SAMPLES) for i in range(approved.SAMPLES + 1)]
        first, last = poses[name][0], poses[name][-1]
        for bone in BONES:
            assert distance(first[bone][0], last[bone][0]) < .002, ('loop not closed', name, bone)
            assert abs(first[bone][2] - last[bone][2]) < .002, ('loop not closed', name, bone)
    walk = poses['Walk']
    for side in ('R', 'L'):
        upper, fore, hand = ARM[side]
        hand_y = [w[hand][0][1] for w in walk]
        foot_y = [w[FOOT[side]][0][1] for w in walk]
        assert spread(hand_y) >= approved.WALK_MIN_HAND_SWING, ('stiff arm in Walk', side, spread(hand_y))
        assert spread(foot_y) >= approved.WALK_MIN_FOOT_STRIDE, ('no stride in Walk', side, spread(foot_y))
        mean_hand = sum(hand_y) / len(hand_y)
        mean_foot = sum(foot_y) / len(foot_y)
        together = sum((h - mean_hand) * (f - mean_foot) for h, f in zip(hand_y, foot_y))
        assert together < 0, ('the arm swings with the leg of its side, not against it', side)
        elbow = [qangle(w[upper][1], w[fore][1]) for w in walk]
        assert spread(elbow) >= approved.WALK_MIN_ELBOW, ('stiff elbow in Walk', side, spread(elbow))
    chest = [qangle(walk[0][CHEST][1], w[CHEST][1]) for w in walk]
    assert max(chest) >= approved.WALK_MIN_CHEST_TURN, ('stiff upper body in Walk', max(chest))
    right, left = ARM['R'][2], ARM['L'][2]
    for name in ('Idle', 'RubHands'):
        for w in poses[name]:
            assert distance(w[right][0], w[left][0]) <= approved.CLASP_MAX_DISTANCE, ('hands not together', name)
            for side in (right, left):
                assert approved.BELLY_HEIGHT[0] <= w[side][0][2] <= approved.BELLY_HEIGHT[1] and \
                    w[side][0][1] <= approved.CLASP_MAX_FRONT, ('hands not in front of the belly', name, side, w[side][0])
    slide = [w[right][0][2] - w[left][0][2] for w in poses['RubHands']]
    assert spread(slide) >= approved.RUB_MIN_SLIDE, ('hands do not rub', spread(slide))
    rest = pose(bones, parents, {}, 0.0)
    bind = {name: (np.array(rest[name][0]), rest[name][1]) for name in BONES}
    samples = [rest] + [pose(bones, parents, tracks, length * i / approved.SLEEVE_SAMPLES)
                        for length, tracks in clips.values() for i in range(approved.SLEEVE_SAMPLES)]
    groups = mesh['groups']
    for side in ('R', 'L'):
        upper, fore, hand = ARM[side]
        sleeve, skin, cloth = groups['sleeve_' + side], groups['hand_' + side], groups['forearm_cloth_' + side]
        axis = bind[hand][0] - bind[fore][0]
        axis /= np.linalg.norm(axis)
        along = (mesh['points'][cloth] - bind[fore][0]) @ axis
        cuff = cloth[along >= along.max() - approved.CUFF_DEPTH]
        along = (mesh['points'][skin] - bind[fore][0]) @ axis
        wrist = skin[along <= along.min() + approved.CUFF_DEPTH]
        for world in samples:
            joints = [np.array(world[name][0]) for name in (upper, fore, hand)] + [hand_tip(world, side)]
            near = np.min([segment_distance(skin_points(mesh, sleeve, bind, world), a, b)
                           for a, b in zip(joints, joints[1:])], axis=0)
            assert near.max() <= approved.SLEEVE_MAX_DISTANCE, ('a sleeve stands off the arm', side, float(near.max()))
            assert np.percentile(near, 99) <= approved.SLEEVE_MAX_P99, ('the sleeves stand off the arm', side)
            gap = np.linalg.norm(skin_points(mesh, cuff, bind, world).mean(0) - skin_points(mesh, wrist, bind, world).mean(0))
            assert gap <= approved.CUFF_MAX_GAP, ('the hand is not in its sleeve cuff', side, float(gap))
            near = np.min([segment_distance(skin_points(mesh, skin, bind, world), a, b)
                           for a, b in zip(joints[1:], joints[2:])], axis=0)
            assert near.max() <= approved.HAND_MAX_DISTANCE, ('a hand floats beside its forearm', side, float(near.max()))


# Colour of every triangle: the colour texture at the triangle's UV centre (Ogre v runs downwards).
def triangle_colours(root, mesh):
    image = np.asarray(Image.open(asset_file(root, TEXTURE)).convert('RGB'), dtype=np.float64)
    tri = np.array(mesh['faces'][MATERIAL], dtype=np.int64)
    uv = mesh['uvs'][tri].mean(1)
    h, w = image.shape[:2]
    return tri, image[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)]


# Render comparison: the merchant from the game camera and from the front differs from the stored render of the approved
# figure by at most RENDER_MAX_MEAN_DIFFERENCE (mean absolute difference per channel) and covers the same silhouette.
def check_render(root, mesh):
    triangles, colours = triangle_colours(root, mesh)
    assert set(RENDER_REFERENCE) == set(approved.VIEWS), 'a reference render is missing'
    for view, (shape, encoded) in RENDER_REFERENCE.items():
        reference = np.frombuffer(zlib.decompress(base64.b64decode(''.join(encoded))), dtype=np.uint8).reshape(shape)
        image = render_view(mesh['points'], triangles, colours, view)
        assert image.shape == reference.shape, (view, image.shape)
        difference = np.abs(image.astype(np.float64) - reference).mean()
        assert difference <= approved.RENDER_MAX_MEAN_DIFFERENCE, ('the merchant looks different', view, difference)
        a, b = image.any(-1), reference.any(-1)
        overlap = (a & b).sum() / max((a | b).sum(), 1)
        assert overlap >= approved.RENDER_MIN_SILHOUETTE_OVERLAP, ('the merchant has another silhouette', view, overlap)


# Verify the delivered CS10a merchant. converted names a directory where this run already deserialized Merchant.mesh
# and Merchant.skeleton, so the converter does not run twice.
def verify_meshy_merchant_contract(root, converted=None):
    root = Path(root)
    started = time.perf_counter()
    check_files(root)
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
        check_render(root, data)
        check_skeleton(skeleton, data)
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'native asset validation', 'seconds': time.perf_counter() - prepared}))
