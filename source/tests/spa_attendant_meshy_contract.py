"""K22 for the CS10a pool attendant (approved Meshy figure, 2026-11-26), used by check_spa_attendant_k22.py.

Since CS10a the pool attendant is the Meshy figure the owner approved: one closed surface with one material
(PoolAttendantMeshy, one colour texture, no tangents) on the shared 24-bone humanoid rig of the creature figures. What
check_spa_attendant_k22.py checks on the former figure is taken over here where it applies to that layout, formally
adapted, with fixed values counted once from the approved export:
  files             mesh, skeleton and colour texture byte-exact, the material names the texture, CREDITS rows
  geometry          vertex and triangle counts, bounds, one material, the triangle budget (Meshy smart topology, about
                    10000 triangles; the owner budget of 2026-11-17 for the former figure was 20000 to 35000)
  (2) fit           every elbow and knee joint lies in the middle of its limb (bone names of the new rig)
  (6) textures      the figure's texture, sampled at its texture coordinates, varies (texture detail); the chair keeps
                    its four textured materials
  (7) clips         the clips the code plays, two seconds each
  (8) look          a small software render of the bind pose from the game camera and from the front differs from the
                    stored render of the approved figure by at most RENDER_MAX_MEAN_DIFFERENCE
Not taken over (the approved figure has no such parts, materials or bones): the separate skin, face, suit, hair, body
hair, linen, whistle, eye and blood materials and the look measured on them (body hair, curls, belly, brows, nose,
eyes, cheeks), the towel (3, 4), the whistle with its ring, cord and finger pinch (5, 9, 10, 11).
"""
import base64
import hashlib
import re
import zlib

import numpy as np
from PIL import Image

import spa_attendant_render as render

MATERIAL = 'PoolAttendantMeshy'
SCRIPT = 'materials/scripts/Creatures/PoolAttendantMeshy.material'
TEXTURE = 'materials/textures/PoolAttendantMeshy.png'
# Filled once from the approved CS10a export (2026-11-26; skeleton recounted on the rebuild with rest clips), never derived from the assets during a test.
VERTICES = 8322
TRIANGLES = 10025
TRIANGLE_BUDGET = (9000, 35000)
MINIMUM = (-0.506374, -0.136942, 0.0)
MAXIMUM = (0.506374, 0.136942, 0.980984)
HASHES = {
    'models/PoolAttendant.mesh': '09fdb5196cd0ce66e46327305fcf1b83f2104fa817467af964954ae27977a85a',
    'models/PoolAttendant.skeleton': '7eb039f0d92205a21cd7fac61c1c82f0bff336abf9ab210e7e4786eb2d09d477',
    TEXTURE: '3b1bd57732634572d3e46bbd45d474560b26576a9011ff8925ff9f8a722ab852',
}
# Elbows and knees with the bone below them (new rig names; former Forearm_R/Hand_R, Shin_R/Foot_R and left)
JOINTS = (('RightForeArm', 'RightHand'), ('LeftForeArm', 'LeftHand'), ('RightLeg', 'RightFoot'), ('LeftLeg', 'LeftFoot'))
CLIPS = {'Sit', 'Whistle', 'TowelWave', 'Doze', 'Walk', 'Climb', 'Jump'}
CHAIR_MATERIALS = {'SpaChairWood', 'SpaIronWorn', 'SpaLifebuoyRed', 'SpaLifebuoyWhite'}
RENDER_MAX_MEAN_DIFFERENCE = 4.5
RENDER_MIN_SILHOUETTE_OVERLAP = 0.99
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the approved CS10a attendant (render_view of
    # spa_attendant_render.py, delivered mesh and PoolAttendantMeshy.png, 2026-11-26)
    'game': ((52, 72, 3), (
        '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'
        'p0HrpY/lY/lYPpb/afk77b0KcA=='
    )),
    'front': ((80, 72, 3), (
        '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'
    )),
}


def check_files(root, resolve, credits):
    """The delivered files are byte-exact, the material names its texture, and CREDITS has their rows."""
    for relative, wanted in HASHES.items():
        assert hashlib.sha256(resolve(relative).read_bytes()).hexdigest() == wanted, ('pool attendant asset changed',
                                                                                     relative)
    script = resolve(SCRIPT).read_text(encoding='utf-8')
    block = re.search(r'^material ' + MATERIAL + r'\b[^\n]*\n\{.*?^\}', script, re.M | re.S)
    assert block and 'texture PoolAttendantMeshy.png' in block.group(0), MATERIAL + ' must use its colour texture'
    for relative in list(HASHES) + [SCRIPT]:
        assert re.search(r'^' + re.escape(relative) + r'\s', credits, re.M), 'CREDITS has no row for ' + relative


def colours(resolve, uvs, faces):
    """Triangles and their flat colours: the colour texture at the triangle's texture-coordinate centre."""
    image = np.asarray(Image.open(resolve(TEXTURE)).convert('RGB'), dtype=np.float64)
    uv = uvs[faces].mean(1)
    h, w = image.shape[:2]
    return faces, image[np.floor(uv[:, 1] * h).astype(int) % h, np.floor(uv[:, 0] * w).astype(int) % w]


def texture_detail(resolve, uvs, faces):
    """Spread of the texture values the figure shows and the share of distinct texture coordinates."""
    image = np.asarray(Image.open(resolve(TEXTURE)).convert('L'), dtype=float) / 255
    h, w = image.shape
    coords = uvs[np.unique(faces)]
    rows = np.floor(coords[:, 1] * h).astype(int) % h
    cols = np.floor(coords[:, 0] * w).astype(int) % w
    return float(np.std(image[rows, cols])), len(np.unique(np.round(coords, 3), axis=0)) / len(coords)


def verify(root, resolve, credits, mesh, skeleton, chair_materials, shown_detail, positions, uvs, faces_by_material,
           weights, parents, bind):
    """Runs the CS10a pool attendant checks on the converted mesh and skeleton; returns a report line."""
    check_files(root, resolve, credits)
    assert set(faces_by_material) == {MATERIAL}, sorted(faces_by_material)
    faces = faces_by_material[MATERIAL]
    geometry = mesh.find('sharedgeometry')
    assert len(positions) == VERTICES and not list(geometry.iter('tangent')), (len(positions), VERTICES)
    assert len(faces) == TRIANGLES, len(faces)
    assert TRIANGLE_BUDGET[0] <= len(faces) <= TRIANGLE_BUDGET[1], 'triangle budget %s, found %d' % (TRIANGLE_BUDGET,
                                                                                                   len(faces))
    assert np.allclose(positions.min(0), MINIMUM, atol=.00002) and np.allclose(positions.max(0), MAXIMUM, atol=.00002)
    assert mesh.find('skeletonlink').get('name') == 'PoolAttendant.skeleton'
    # (2) every elbow and knee joint lies in the middle of its limb
    for joint, child in JOINTS:
        centre = bind[joint][:3, 3]
        axis = bind[child][:3, 3] - centre
        axis /= np.linalg.norm(axis)
        near = [v for v in weights if (weights[v].get(joint, 0) + weights[v].get(parents[joint], 0)) > .5]
        points = positions[near]
        ring = points[np.abs((points - centre) @ axis) < .02]
        assert len(ring) >= 30, joint + ': too few vertices around the joint'
        offset = ring.mean(axis=0) - centre
        offset -= axis * (offset @ axis)
        assert np.linalg.norm(offset) < .02, '%s: the joint lies %.3f beside the middle of the limb' % (
            joint, np.linalg.norm(offset))
    # (6) texture detail on the chair and on the figure
    assert chair_materials == CHAIR_MATERIALS, chair_materials
    for material in sorted(chair_materials):
        spread, distinct = shown_detail(material)
        assert spread > .03 and distinct > .3, '%s shows no texture detail (spread %.3f, distinct %.2f)' % (
            material, spread, distinct)
    spread, distinct = texture_detail(resolve, uvs, faces)
    assert spread > .03 and distinct > .3, '%s shows no texture detail (spread %.3f, distinct %.2f)' % (
        MATERIAL, spread, distinct)
    # (8) look of the approved figure
    triangles, flat = colours(resolve, uvs, faces)
    assert set(RENDER_REFERENCE) == set(render.VIEWS), 'a reference render is missing'
    measured = {}
    for view, (shape, encoded) in RENDER_REFERENCE.items():
        reference = np.frombuffer(zlib.decompress(base64.b64decode(''.join(encoded))), dtype=np.uint8).reshape(shape)
        image = render.render_view(positions, triangles, flat, view)
        assert image.shape == reference.shape, (view, image.shape)
        difference, overlap = render.compare(image, reference)
        assert difference <= RENDER_MAX_MEAN_DIFFERENCE, ('the attendant looks different', view, difference)
        assert overlap >= RENDER_MIN_SILHOUETTE_OVERLAP, ('the attendant has another silhouette', view, overlap)
        measured[view] = (round(difference, 2), round(overlap, 3))
    # (7) the clips the code plays, two seconds each
    clips = {clip.get('name'): clip for clip in skeleton.findall('animations/animation')}
    assert set(clips) == CLIPS, sorted(clips)
    assert all(abs(float(clip.get('length')) - 2) < 1e-6 for clip in clips.values())
    return 'CS10a figure: %d triangles, render difference/overlap %s' % (len(faces), measured)
