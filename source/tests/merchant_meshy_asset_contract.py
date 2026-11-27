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
# Filled once from the approved CS10a export (2026-11-26; recounted on the rebuild with rest clips and the figure
# centred on its node), never derived from the assets during a test.
VERTICES = 7679
TRIANGLES = 9429
MINIMUM = (-0.6352, -0.198587, 0.0)
MAXIMUM = (0.651964, 0.170507, 1.29516)
HASHES = {
    'models/Merchant.mesh': 'ebe09388bfb9b584e08da76c9ea4ded14e89f934eb4653b29d777b498a6f997c',
    'models/Merchant.skeleton': '7d811fbd01866d106293fd938262c798284bbce141a24927b3f912bffa0a4d85',
    TEXTURE: '3f28d6fbff3a40e8404000b8fe6db7e8e0d1b444aa8fd32ae1da8d891399db4b',
}
# The clips the game plays for the merchant (unchanged from the merchant of 2026-11-15)
# CountGold is the clip approved on 2026-11-27 (two coins in a 2.0 s loop); the other lengths stay as approved
CLIPS = dict(approved.CLIPS, CountGold=2.0)
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
        'mI7pmI7pmI7fyPFfuEWQfg=='
    )),
    'front': ((108, 72, 3), (
        'eNrt3FdzJNd5BmBQizyxp3MOM9NhZnpyDphBHOS8wBLYnLSRqxWDqESKpOWyaEumTdnlKt/Y5bJ84bIv7Sv7D/hP+QWPPAIhiiKosmZW'
        'pa63tvYGW/vgO31Sn+6xsT9ef7z+eP0hXHNFf7nq/yGJ3jla/MdPPkIe7K9Wktpczn3VRX9yex1583j5779z45Nne6t1v5VPGwJny8yr'
        'izJl9t1rG0Ahb1xdWsyaR+3i1aU6XIglvaq0vCnAtTdfRX7y4vrbB0t/9vD4Ozd2geJpSudjpkC/cihbkXpZ6+ZqDaj//OT9f3j34Z/e'
        '3P+rh6//zcsHR/N14urmEq8WKqUK61X35eubP33z3noj/6/vvfGL7z39+P7xv3/w5p9/8/TJ9gpcpszB9WqVzFOlnbb/YHfxjdPDF8er'
        'dzYXf/Hey1u9yr999OaPn9w5WepstSrEVUuZrwoqY6jXun4z77442YLr6c7yz3/0nQU/+T+ffuiJzPvHB+vV/P5cdatbAQpJvCJ943F/'
        'TohFjldacP3kxS24vr23/It3vvkvLx+0HfOj6zsHteKtfvtwubm/WIOrW/BGH7VWz8C1UkmjXje3F4BC/vbRjY9v7v3zi7t1S32523+x'
        'Nb9RzX3w4jZcCUl4JVwrhQRPhYHCzfXsaJ24vv/67qf3T//jg7c6jnFYLbw83Li11oXr2lo3rUpt38zGlZHuBuWoQIVrntEr+988WPz4'
        'rYdA/ezpzRtL7Q9uHvz3xz+cT7uH8/XlWg6ulzd2Ua+sbax1yvPlzEiPWboAFCLSIdBIveD6u3fvvzxZf7LW7xdTS5nEo71FuK73G8RV'
        'NHnQqq42yq6Gb6ls5N1b+89Ptn748Ji4vndj8y/euPF0Y+EHJ3utrHPS7w5cb5zswtXKuiPravrJZjYBl85TcJ2s91aq2ceHK3D95TsP'
        '/+vn7/3146ufPDrZa+ffPN0krqOl5tVu4ep8Fa6VamFk6wXUcjUD12YzDdfJ5gJxdbLJO1u9T791582rqycbC6cLrfOu1Zp/d7U+yvfX'
        'ciUH10Y9fX2l3q1k4dppF+D68O7R4/X288O1k+VmzTHzlg7XTre41yvf3WrD1ckkkaPF2mhNMHTlLKZUiEt5VczI/HYru9H6nOuto/WX'
        '13aWS5ndVnG5lsYi5d5W76Nnt+Aq22oyGrMUJa3J652qTocPivnf9/BUzdVTccQRmZZvI2lDQopunKSZSojBMFybteR8ySslpI2m1y24'
        '7906OJ5vXF3s/PB0Kzo7JVChp3vze+3stcVy3dHCY2PRUICdnUE2M85pp7VhG6e1TNdUtrIu8jWWfqWkTvL6YsXRuIKT7OTdVs5BlipZ'
        'xBIYz9KlaNS3NfRmftL46PHR093efNZLWaZCU0gnlwJKF1m45HBgq5qBa6uV++6jU9DgclX2pFf/9Pnd+ZIPF1AqE96drwPFhGYGrn6p'
        'WDLkd3YWttKpdjxxWCu3dC2bjBctWRYiflyTuVi3nPft+LOTbeT2dg+xZT6bsBw+Ol9IbXeqSDmV2O1WSZarWZ3nkFxcU1laExkSS+CE'
        'WDjvaEjOlBGgHu4sIAOXSlPnXff7jZWyA9fjq6tpUy7b0vX1tqMIP75/7WCuhJUXXDXfFqKhs2JNTsIVHBsDas7QievA9+BC4qrQb5U2'
        'Glk1POWosi6x+bgaC87aMkfSqeQNNiowFDJf9t5+eAPJWMrhfA2BCwsHlQ7BlU2ocA1oQCkC62oSXJ7Gw+XpAheYQjSWITRT5BOqEpgY'
        'tzgGLuTB+lxWZ+B6uNmt2woTDoqxqMbTXCT0eLudVDBmJVaKNlxt1ympypxt1eNGO2EXRWnRS1cUdYAauIBCqNmpgWuAsjUByVkKUKcb'
        '3XBwtpF1EFPigtOTVDiE4EfZcMCUJRJX45C8q0dCAYkKIpbEgoYk5LMAhfimDpdER81wCHmy2gBtqeJjm4aEDc7GgsHDTs4Q6JQmA4Xw'
        '4SBxWUyMuDqeS1x0JEhQFVtWOBpROQox6enI7CQbDpJEQrNMLHqWSNjRpX6niug8DRFJaHYGGbgkhgYqKTNxlP4zFB0KInAZbAQ0JHTl'
        'CsoqURRy3uVTUTE09bQ/Z0tMzdVeHq2t1OzVasY3RIIiLpWKmKFIz7QGLhRr4FJYBiKEDoeAyqB4dASBKzA5TlB0JMyEZ8/yfy4SdB2u'
        'yJAosXA2riL4dyLBWSo4g8CF+8bWZaRVyCKgwUVoYowauBA+Gh64+GAQtK5vdzIJlY0ezvlrxUQtzpeTGlAlS0R2beeCy6EouMqKaiki'
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
