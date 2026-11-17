"""K22: the pool attendant is the hairy man and fits his skeleton, towel and whistle move naturally, chair and ring are
textured.

Reads models/PoolAttendant.mesh, models/PoolAttendant.skeleton and models/SpaChair.mesh through OgreXMLConverter, the
material scripts and the textures; no compiler, no game. Checks
(1) the look: the massive, hairy, pot-bellied man (body hair strands standing off the skin on arms, legs and chest, a
    full head of curly hair and a big moustache, a belly far in front of the chest), a shaded face (owner findings of
    2026-11-17: head after the attendant in the game, body hair with volume, real whistle, shaded skin, muted ring);
(2) mesh and skeleton fit each other: every elbow and knee joint lies in the middle of its limb (the mesh restored on
    2026-11-13 sat 7 cm beside the joints of the skeleton);
(3) the towel goes into the hand in TowelWave and no towel face stretches;
(4) TowelWave: the towel is in the hand above the shoulder, the hand goes round a loop on a smooth path, the towel and
    its free end turn smoothly from key to key and the end trails the towel;
(5) Whistle: the hand fetches the whistle and raises it to the lips on a round arc (the elbow swings up and the path
    bows out of the straight line), the whistle stays at the lips while the game plays the sound, the arm turns
    smoothly;
(6) every surface of the chair, the life ring and the attendant's hair, whistle and cord shows texture detail: the
    texture of its material, sampled at its texture coordinates, varies; the face texture carries shading; the life ring
    is muted for the dark room; the whistle is a small whistle: a round barrel and a flat mouthpiece;
(7) the clips the code plays, two seconds each;
(8) owner findings round 2 (2026-11-17): a normal nose, flat dark brows with the eyes (iris and white) showing below
    them, a silver whistle, a darker ring, bare feet with five toes each, and the owner triangle budget: the figure has
    20000 to 35000 triangles (pinned counts of this export) and a small software render of the bind pose from the game
    camera and the front differs from the reviewed render of the same figure before the reduction by at most
    RENDER_MAX_MEAN_DIFFERENCE (with body hair; single hair strands land on other pixels) and
    RENDER_MAX_MEAN_DIFFERENCE_BARE (without body hair) and overlaps its silhouette by at least the named minimum.
"""
from pathlib import Path
import math
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import base64
import sys
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spa_attendant_render as render  # noqa: E402

TRIANGLES, VERTICES = 32983, 33832  # this export (owner budget 20000-35000)
RENDER_MAX_MEAN_DIFFERENCE = 8.5  # export: game 6.1, front 7.1 (with the body hair)
RENDER_MAX_MEAN_DIFFERENCE_BARE = 4.5  # export: game 3.1, front 3.7 (without the body hair)
RENDER_MIN_SILHOUETTE_OVERLAP = 0.96  # export: game 0.979, front 0.974 (with the body hair)
RENDER_MIN_SILHOUETTE_OVERLAP_BARE = 0.99  # export: 0.999 both
RENDER_REFERENCE = {  # zlib + base64 of the uint8 renders of the figure before the reduction (reviewed 2026-11-17)
    'game-all': ((52, 72, 3), (
        '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'
    )),
    'front-all': ((80, 72, 3), (
        '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'
    )),
    'game-bare': ((52, 72, 3), (
        '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'
        'co/j7Tj78B+sc+HB+OD8dv8PgvYryqgg=='
    )),
    'front-bare': ((80, 72, 3), (
        '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'
    )),
}

ROOT = Path(__file__).resolve().parents[2]
helper_source = (ROOT / 'source/tests/check_spa_owner_863.py').read_text(encoding='utf-8')
helpers = {'__file__': str(ROOT / 'source/tests/check_spa_owner_863.py')}
exec(compile(helper_source[:helper_source.index('def check_pose')], 'check_spa_owner_863_helpers', 'exec'), helpers)
CONVERTER = helpers['CONVERTER']
vector, rotation, sample_track, geometry = (helpers[name] for name in ('vector', 'rotation', 'sample_track', 'geometry'))
KEY = 1.0 / 24


def read(name):
    """Read a repository text file."""
    return (ROOT / name).read_text(encoding='utf-8', errors='replace')


with tempfile.TemporaryDirectory(prefix='spa-k22-') as folder:
    converted = {}
    for name in ('PoolAttendant.mesh', 'PoolAttendant.skeleton', 'SpaChair.mesh'):
        path = Path(folder) / (name + '.xml')
        result = subprocess.run([str(CONVERTER), str(ROOT / 'models' / name), str(path)], capture_output=True, text=True,
                                cwd=folder)
        assert result.returncode == 0, result.stdout + result.stderr
        converted[name] = ET.parse(path).getroot()
mesh, skeleton, chair = converted['PoolAttendant.mesh'], converted['PoolAttendant.skeleton'], converted['SpaChair.mesh']

positions, _, uvs = geometry(mesh.find('sharedgeometry'))
faces_by_material = {}
for sub in mesh.findall('submeshes/submesh'):
    faces = np.array([[int(f.get(k)) for k in ('v1', 'v2', 'v3')] for f in sub.findall('faces/face')])
    faces_by_material.setdefault(sub.get('material'), []).append(faces)
faces_by_material = {m: np.vstack(f) for m, f in faces_by_material.items()}
bones = {bone.get('name'): bone for bone in skeleton.findall('bones/bone')}
names = {int(bone.get('id', index)): bone.get('name') for index, bone in enumerate(skeleton.findall('bones/bone'))}
parents = {item.get('bone'): item.get('parent') for item in skeleton.findall('bonehierarchy/boneparent')}
weights = {}
for item in mesh.findall('boneassignments/vertexboneassignment'):
    weights.setdefault(int(item.get('vertexindex')), {})[names[int(item.get('boneindex'))]] = float(item.get('weight'))


def verts(material):
    """Vertex indices of a material."""
    return np.unique(faces_by_material[material])


# ---- 1. The look: massive, hairy, pot-bellied ---------------------------------------------------------------------------
for material in ('SpaSkin', 'SpaAttendantFace', 'SpaSuit', 'SpaHair', 'SpaBodyHair', 'SpaLinen', 'SpaWhistle', 'SpaEyes',
                 'SpaBlood'):
    assert material in faces_by_material, 'the attendant needs the material ' + material
face_points = positions[verts('SpaAttendantFace')]
hair_points = positions[verts('SpaHair')]
scalp = hair_points[hair_points[:, 2] > np.percentile(face_points[:, 2], 60)]
assert np.ptp(scalp[:, 0]) > .2 and np.ptp(scalp[:, 1]) > .18, 'a full head of hair, not a receding scalp'
assert hair_points[:, 2].max() > face_points[:, 2].max() + .01, 'the curls stand on top of the head'
assert len(faces_by_material['SpaBodyHair']) >= 10000, 'full body hair'
hair_bones = {}
for v in verts('SpaBodyHair'):
    bone = max(weights[v].items(), key=lambda item: item[1])[0]
    hair_bones[bone] = hair_bones.get(bone, 0) + 1
for part in ('UpperArm_R', 'UpperArm_L', 'Thigh_R', 'Thigh_L', 'Shin_R', 'Shin_L', 'Chest'):
    assert hair_bones.get(part, 0) >= 300, 'body hair on ' + part
assert 0 < len(faces_by_material['SpaBlood']) <= 200, 'a very little blood'
skin_cells = {}
for v in verts('SpaSkin'):
    skin_cells.setdefault(tuple(np.floor(positions[v] / .02).astype(int)), []).append(positions[v])
skin_cells = {k: np.array(v) for k, v in skin_cells.items()}


def off_skin(p):
    """Distance of a point to the nearest skin vertex (within 4 cm)."""
    key = np.floor(p / .02).astype(int)
    near = [skin_cells[k] for k in ((key[0] + a, key[1] + b, key[2] + c) for a in (-1, 0, 1) for b in (-1, 0, 1)
                                    for c in (-1, 0, 1)) if k in skin_cells]
    return min(np.min(np.linalg.norm(c - p, axis=1)) for c in near) if near else 1.0


body_hair = positions[verts('SpaBodyHair')]
sample = body_hair[np.linspace(0, len(body_hair) - 1, 3000).astype(int)]
standing = np.mean([off_skin(p) > .006 for p in sample])
assert standing > .2, 'the body hair has volume: strands stand off the skin (%.2f of the hair points)' % standing
suit = positions[verts('SpaSuit')]
belly = suit[(suit[:, 2] > .45) & (suit[:, 2] < .6)]
chest = suit[(suit[:, 2] > .7) & (suit[:, 2] < .8)]
assert chest[:, 1].min() - belly[:, 1].min() > .1, 'the belly bulges far in front of the chest'
skin = positions[verts('SpaSkin')]
assert np.ptp(skin[(skin[:, 2] > .6) & (skin[:, 2] < .8)][:, 0]) > .5, 'massive shoulders and arms'


# ---- 2. Mesh and skeleton fit ---------------------------------------------------------------------------------------------
def bind_world():
    """World matrices of the bind pose."""
    result = {}

    def world(name):
        if name not in result:
            bone = bones[name]
            local = np.eye(4)
            local[:3, :3] = rotation(bone.find('rotation'))
            local[:3, 3] = vector(bone.find('position'))
            result[name] = world(parents[name]) @ local if name in parents else local
        return result[name]
    for name in bones:
        world(name)
    return result


BIND = bind_world()
body = set(verts('SpaSkin')) | set(verts('SpaSuit'))
for joint, child in (('Forearm_R', 'Hand_R'), ('Forearm_L', 'Hand_L'), ('Shin_R', 'Foot_R'), ('Shin_L', 'Foot_L')):
    centre = BIND[joint][:3, 3]
    axis = BIND[child][:3, 3] - centre
    axis /= np.linalg.norm(axis)
    near = [v for v in body if (weights[v].get(joint, 0) + weights[v].get(parents[joint], 0)) > .5]
    points = positions[near]
    ring = points[np.abs((points - centre) @ axis) < .02]
    assert len(ring) >= 30, joint + ': too few vertices around the joint'
    offset = ring.mean(axis=0) - centre
    offset -= axis * (offset @ axis)
    assert np.linalg.norm(offset) < .02, '%s: the joint lies %.3f beside the middle of the limb' % (joint, np.linalg.norm(offset))

# ---- 7. Clips ---------------------------------------------------------------------------------------------------------------
clips = {clip.get('name'): clip for clip in skeleton.findall('animations/animation')}
assert set(clips) == {'Sit', 'Whistle', 'TowelWave', 'Doze', 'Walk', 'Climb', 'Jump'}, sorted(clips)
assert all(abs(float(clip.get('length')) - 2) < 1e-6 for clip in clips.values())
tracks = {name: {track.get('bone'): track.findall('keyframes/keyframe') for track in clip.findall('tracks/track')}
          for name, clip in clips.items()}


def pose(clip, seconds):
    """World matrices of all bones in a clip at a time."""
    result = {}

    def world(name):
        if name not in result:
            bone = bones[name]
            local = np.eye(4)
            local[:3, :3] = rotation(bone.find('rotation'))
            local[:3, 3] = vector(bone.find('position'))
            if name in tracks[clip]:
                translation, orientation = sample_track(tracks[clip][name], seconds)
                local[:3, 3] += translation
                local[:3, :3] = local[:3, :3] @ orientation
            result[name] = world(parents[name]) @ local if name in parents else local
        return result[name]
    for name in bones:
        world(name)
    return result


def turn(a, b):
    """Angle in degrees between two rotation matrices."""
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(a.T @ b) - 1) / 2))))


def series(clip):
    """Poses of a clip at every key (24 per second)."""
    return [pose(clip, i * KEY) for i in range(49)]


def grip(p):
    """Point the fist closes around: past the wrist along the forearm."""
    wrist, elbow = p['Hand_R'][:3, 3], p['Forearm_R'][:3, 3]
    return wrist + .08 * (wrist - elbow) / np.linalg.norm(wrist - elbow)


def sharpest_turn(points):
    """Largest change of direction in degrees between two steps of a sampled path (steps under 5 mm are skipped)."""
    steps = np.diff(np.array(points), axis=0)
    worst = 0.0
    for a, b in zip(steps, steps[1:]):
        if np.linalg.norm(a) > .005 and np.linalg.norm(b) > .005:
            cosine = float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b))
            worst = max(worst, math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
    return worst


# ---- 4. TowelWave -------------------------------------------------------------------------------------------------------
# the back half of the towel hangs from the fold at the Towel joint, the front half from the TowelTip joint
BACK, TIP = [0.0, 0.1, -0.2], [0.0, -0.075, -0.111]
towel = series('TowelWave')
held = [i for i in range(49) if .45 <= i * KEY <= 1.45]
for i in held:
    p = towel[i]
    assert np.linalg.norm(p['Towel'][:3, 3] - grip(p)) < .05, 'TowelWave: the towel is in his hand at %.2f s' % (i * KEY)
    assert p['Towel'][2, 3] > p['UpperArm_R'][2, 3] + .1, 'TowelWave: the towel is above his shoulder'
loop = np.array([grip(towel[i])[[0, 2]] for i in held])
area = .5 * abs(np.dot(loop[:, 0], np.roll(loop[:, 1], 1)) - np.dot(loop[:, 1], np.roll(loop[:, 0], 1)))
assert area > .01, 'TowelWave: the hand swings the towel round a loop, not back and forth (%.4f m2)' % area
swing = [i for i in range(49) if .55 <= i * KEY <= 1.4]
turning = sharpest_turn([grip(towel[i]) for i in swing])
assert turning < 60, 'TowelWave: the hand swings on a smooth curve, it turns %.0f degrees between two keys' % turning
for bone, limit in (('Towel', 25), ('TowelTip', 25), ('UpperArm_R', 30), ('Forearm_R', 30)):
    worst = max(turn(towel[i][bone][:3, :3], towel[i + 1][bone][:3, :3]) for i in range(48))
    assert worst < limit, 'TowelWave: %s turns %.0f degrees between two keys' % (bone, worst)
spread = max(np.linalg.norm(towel[i]['Towel'][:3, 3] - towel[j]['Towel'][:3, 3]) for i in held for j in held)
assert spread > .2, 'TowelWave: the towel is visibly waved'


def hanging(p, bone, local):
    """Unit direction a half of the towel hangs to."""
    d = p[bone][:3, :3] @ np.array(local)
    return d / np.linalg.norm(d)


def angle(a, b):
    """Angle in degrees between unit vectors."""
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b)))))


# folded in the hand both halves hang the same way; the free end follows the towel a moment later
now = np.mean([angle(hanging(towel[i], 'TowelTip', TIP), hanging(towel[i], 'Towel', BACK)) for i in swing])
later = np.mean([angle(hanging(towel[i], 'TowelTip', TIP), hanging(towel[i - 2], 'Towel', BACK)) for i in swing])
assert later < now and now > 3, 'TowelWave: the free end trails behind the towel (%.1f / %.1f degrees)' % (later, now)
sit0 = pose('Sit', 0)

# ---- 3. The towel goes into the hand without stretching ----------------------------------------------------------------
INVERSE = {name: np.linalg.inv(matrix) for name, matrix in BIND.items()}
linen = faces_by_material['SpaLinen']
edges = {tuple(sorted((int(f[i]), int(f[(i + 1) % 3])))) for f in linen for i in range(3)}


def skinned(p, vertex):
    """Position of a vertex in a pose (linear blend skinning as the game does it)."""
    point = np.append(positions[vertex], 1)
    return sum(w * (p[bone] @ INVERSE[bone] @ point)[:3] for bone, w in weights[vertex].items())


# edge lengths as the towel lies on his shoulder when the clip starts (the seated pose)
seated = {v: skinned(towel[0], v) for v in np.unique(linen)}
seated_length = {e: np.linalg.norm(seated[e[0]] - seated[e[1]]) for e in edges}
for i in range(2, 49, 2):
    moved = {v: skinned(towel[i], v) for v in np.unique(linen)}
    for e in edges:
        if seated_length[e] > 1e-4:
            ratio = np.linalg.norm(moved[e[0]] - moved[e[1]]) / seated_length[e]
            assert ratio < 1.5, 'TowelWave: a towel face stretches %.1f times at %.2f s' % (ratio, i * KEY)
held_pose = towel[held[len(held) // 2]]
lifted = [v for v in np.unique(linen) if np.linalg.norm(skinned(held_pose, v) - grip(held_pose)) < .4]
assert len(lifted) > .7 * len(np.unique(linen)), 'TowelWave: most of the towel is in his hand (%d of %d vertices)' % (
    len(lifted), len(np.unique(linen)))
assert np.linalg.norm(sit0['Towel'][:3, 3] - grip(sit0)) > .25, 'the towel lies on the shoulder at rest'

# ---- 5. Whistle --------------------------------------------------------------------------------------------------------------
head = [v for v in verts('SpaAttendantFace') if weights[v].get('Head', 0) > .5 and abs(positions[v][0]) < .012]
nose = min(head, key=lambda v: positions[v][1])
under = [v for v in head if positions[nose][2] - .06 < positions[v][2] < positions[nose][2] - .025]
lips = positions[min(under, key=lambda v: positions[v][1])]
moustache = hair_points[(hair_points[:, 1] < lips[1] + .01) & (np.abs(hair_points[:, 2] - lips[2]) < .04)]
assert len(moustache) > 50 and np.ptp(moustache[:, 0]) > .12, 'a big moustache over the lips (%.3f wide)' % (
    np.ptp(moustache[:, 0]) if len(moustache) else 0)
whistle = series('Whistle')
blow = float(re.search(r'const double WHISTLE_BLOW_SECONDS = ([0-9.]+);', read('source/entities/PoolAttendantEntity.cpp')).group(1))
for i in range(49):
    if blow <= i * KEY <= 1.15:
        p = whistle[i]
        mouth = (p['Head'] @ np.linalg.inv(BIND['Head']) @ np.append(lips, 1))[:3]
        distance = np.linalg.norm(p['WhistleHang'][:3, 3] - mouth)
        assert distance < .035, 'Whistle: the whistle is at the lips while it sounds (%.3f at %.2f s)' % (distance, i * KEY)
        assert np.linalg.norm(p['WhistleHang'][:3, 3] - grip(p)) < .08, 'Whistle: the whistle is in his hand'
rest_mouth = (sit0['Head'] @ np.linalg.inv(BIND['Head']) @ np.append(lips, 1))[:3]
assert np.linalg.norm(sit0['WhistleHang'][:3, 3] - rest_mouth) > .2, 'the whistle hangs on his chest at rest'
# the way up: from the moment the hand grasps the whistle on his chest until it is at the lips
arrived = next(i for i in range(49) if np.linalg.norm(
    whistle[i]['WhistleHang'][:3, 3] - (whistle[i]['Head'] @ np.linalg.inv(BIND['Head']) @ np.append(lips, 1))[:3]) < .035)
grips = [grip(p) for p in whistle]
at_chest = [i for i in range(1, arrived) if np.linalg.norm(whistle[i]['WhistleHang'][:3, 3] - grips[i]) < .08 and
            np.linalg.norm(whistle[i - 1]['WhistleHang'][:3, 3] - whistle[0]['WhistleHang'][:3, 3]) < .01]
assert at_chest, 'Whistle: the hand takes the whistle from his chest'
# the hand grasps where it stands still at the whistle
fetched = min(at_chest, key=lambda i: np.linalg.norm(grips[i + 1] - grips[i - 1]))
assert np.linalg.norm(whistle[fetched]['WhistleHang'][:3, 3] - grip(whistle[fetched])) < .08, 'Whistle: the hand takes the whistle'
path = np.array([grip(whistle[i]) for i in range(fetched, arrived + 1)])
chord = path[-1] - path[0]
chord /= np.linalg.norm(chord)
bow = max(np.linalg.norm((q - path[0]) - chord * ((q - path[0]) @ chord)) for q in path)
assert arrived - fetched >= 4, 'Whistle: the whistle is raised, not snapped to the mouth'
assert bow > .04, 'Whistle: the hand raises the whistle on a round arc (bows %.3f out of the straight line)' % bow
assert whistle[arrived]['Forearm_R'][2, 3] - sit0['Forearm_R'][2, 3] > .1, 'Whistle: the elbow swings up'
turning = sharpest_turn(path)
assert turning < 60, 'Whistle: the hand rises on a smooth curve, it turns %.0f degrees between two keys' % turning
for bone in ('UpperArm_R', 'Forearm_R'):
    worst = max(turn(whistle[i][bone][:3, :3], whistle[i + 1][bone][:3, :3]) for i in range(48))
    assert worst < 30, 'Whistle: %s turns %.0f degrees between two keys' % (bone, worst)

# ---- 6. Textures show on every surface ----------------------------------------------------------------------------------
materials = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (ROOT / 'materials/scripts').glob('*.material'))


def texture_of(material):
    """Texture image of a material (first texture unit)."""
    block = re.search(r'^material ' + re.escape(material) + r'\b[^\n]*\n\{.*?^\}', materials, re.M | re.S)
    assert block, material + ' is not defined'
    name = re.search(r'^\s*texture\s+(\S+)', block.group(0), re.M)
    assert name, material + ' has no texture'
    image = np.asarray(Image.open(ROOT / 'materials/textures' / name.group(1)).convert('L'), dtype=float) / 255
    return image


UV_CACHE = {}


def shown_detail(root, material):
    """Spread of the texture values the surface shows: the texture sampled at the texture coordinates of its corners."""
    if id(root) not in UV_CACHE:
        UV_CACHE[id(root)] = uvs if root is mesh else geometry(root.find('sharedgeometry'))[2]
    uv = UV_CACHE[id(root)]
    corners = set()
    for sub in root.findall('submeshes/submesh'):
        if sub.get('material') == material:
            corners.update(int(f.get(k)) for f in sub.findall('faces/face') for k in ('v1', 'v2', 'v3'))
    image = texture_of(material)
    h, w = image.shape
    coords = uv[sorted(corners)]
    rows = (np.floor(coords[:, 1] * h).astype(int)) % h
    cols = (np.floor(coords[:, 0] * w).astype(int)) % w
    return float(np.std(image[rows, cols])), len(np.unique(np.round(coords, 3), axis=0)) / len(coords)


chair_materials = {sub.get('material') for sub in chair.findall('submeshes/submesh')}
assert chair_materials == {'SpaChairWood', 'SpaIronWorn', 'SpaLifebuoyRed', 'SpaLifebuoyWhite'}, chair_materials
for root, material in [(chair, m) for m in sorted(chair_materials)] + \
        [(mesh, m) for m in ('SpaHair', 'SpaBodyHair', 'SpaWhistle', 'SpaIronWorn', 'SpaSkin', 'SpaSuit', 'SpaLinen',
                             'SpaAttendantFace')]:
    spread, distinct = shown_detail(root, material)
    assert spread > .03 and distinct > .3, '%s shows no texture detail (spread %.3f, distinct %.2f)' % (material, spread,
                                                                                                         distinct)
# the whistle: a round barrel across (x) below the mouthpiece, a flat mouthpiece up to the joint at its tip
joint = BIND['WhistleHang'][:3, 3]
whistle_points = positions[verts('SpaWhistle')] - joint
barrel = whistle_points[whistle_points[:, 2] < -.06]
centre = np.array([np.median(barrel[:, 1]), (barrel[:, 2].max() + barrel[:, 2].min()) / 2])
radius = np.hypot(barrel[:, 1] - centre[0], barrel[:, 2] - centre[1])
rim = radius[radius > .5 * radius.max()]
assert np.ptp(barrel[:, 0]) > .04 and .012 < np.median(rim) < .03 and np.std(rim) < .005, 'the whistle has a round barrel'
mouthpiece = whistle_points[(whistle_points[:, 2] > -.045)]
assert np.ptp(mouthpiece[:, 0]) < .03 and np.ptp(mouthpiece[:, 1]) < .016 and mouthpiece[:, 2].max() > -.005, \
    'the whistle has a flat mouthpiece that ends at the lips'
# the face is shaded: its texture, sampled at its texture coordinates, has dark folds and a ruddy nose
face_image = np.asarray(Image.open(ROOT / 'materials/textures' / re.search(
    r'^material SpaAttendantFace\b[^\n]*\n\{.*?texture\s+(\S+)', materials, re.M | re.S).group(1)).convert('RGB'), float) / 255
fh, fw, _ = face_image.shape
face_uv = uvs[verts('SpaAttendantFace')]
texels = face_image[np.clip((face_uv[:, 1] * fh).astype(int), 0, fh - 1), (face_uv[:, 0] * fw).astype(int) % fw]
luma = texels @ np.array([.299, .587, .114])
assert np.std(luma) > .04 and np.percentile(luma, 10) < .8 * np.median(luma), 'the face has skin shading, not one flat tone'
nose_uv = uvs[nose]
nose_rgb = face_image[int(nose_uv[1] * fh), int(nose_uv[0] * fw) % fw]
assert nose_rgb[0] - nose_rgb[1] > np.median(texels[:, 0] - texels[:, 1]) + .03, 'the nose is ruddier than the face'
# the life ring is muted for the dark room: worn paint, no glow, no bright white
for material in ('SpaLifebuoyRed', 'SpaLifebuoyWhite'):
    block = re.search(r'^material ' + material + r'\b[^\n]*\n\{.*?^\}', materials, re.M | re.S).group(0)
    diffuse = np.array([float(x) for x in re.search(r'diffuse ([\d.]+) ([\d.]+) ([\d.]+)', block).groups()])
    emissive = np.array([float(x) for x in re.search(r'emissive ([\d.]+) ([\d.]+) ([\d.]+)', block).groups()])
    shown = texture_of(material).mean() * diffuse + emissive
    assert shown @ np.array([.299, .587, .114]) < .36 and emissive.max() <= .02, material + ' is too bright for the dark room'
    assert diffuse.max() - diffuse.min() < .5, material + ' is too saturated for the dark room'
# owner findings round 2: the whistle is silver metal (neutral colour, a strong tight highlight)
block = re.search(r'^material SpaWhistle\b[^\n]*\n\{.*?^\}', materials, re.M | re.S).group(0)
diffuse = np.array([float(x) for x in re.search(r'diffuse ([\d.]+) ([\d.]+) ([\d.]+)', block).groups()])
specular = re.search(r'specular ([\d.]+) [\d.]+ [\d.]+ [\d.]+ ([\d.]+)', block)
assert np.ptp(diffuse) <= .08 and .35 <= diffuse.mean() <= .7, 'the whistle is neutral silver, not white or brass'
assert float(specular.group(1)) >= .8 and float(specular.group(2)) >= 40, 'the whistle shines like polished metal'
# a normal nose, flat brows, eyes with iris and white showing below them
assert 'SpaAttendantSclera' in faces_by_material, 'the eyes have whites'
eye_points = positions[np.unique(np.vstack([faces_by_material['SpaEyes'], faces_by_material['SpaAttendantSclera']]))]
eye_points = eye_points[eye_points[:, 2] > .8]
tip = positions[nose]
cheeks = face_points[(np.abs(np.abs(face_points[:, 0]) - .06) < .012) & (np.abs(face_points[:, 2] - tip[2]) < .012)]
assert cheeks[:, 1].min() - tip[1] < .026, 'a normal nose, no bulb (%.3f in front of the cheeks)' % (cheeks[:, 1].min() - tip[1])
eye_z = eye_points[:, 2].mean()
brows = face_points[(np.abs(face_points[:, 0]) > .02) & (np.abs(face_points[:, 0]) < .05) & (face_points[:, 2] > eye_z + .008)
                    & (face_points[:, 2] < eye_z + .035)]
assert eye_points[:, 1].min() - brows[:, 1].min() < .004, 'the brows do not hide the eyes'
brow_uv = uvs[[v for v in verts('SpaAttendantFace') if .02 < abs(positions[v][0]) < .05 and
               eye_z + .004 < positions[v][2] < eye_z + .016 and positions[v][1] < tip[1] + .04]]
brow_rgb = face_image[np.clip((brow_uv[:, 1] * fh).astype(int), 0, fh - 1), (brow_uv[:, 0] * fw).astype(int) % fw]
assert (brow_rgb @ np.array([.299, .587, .114])).mean() < .75 * np.median(luma), 'the brows are darker than the face'
# bare feet: five separate toes in front of each foot
skin_faces = faces_by_material['SpaSkin']
toe_faces = [f for f in skin_faces if (positions[f][:, 1] < -.03).all() and (positions[f][:, 2] < .045).all()]
parent = {}


def find(v):
    while parent.setdefault(v, v) != v:
        parent[v] = parent[parent[v]]
        v = parent[v]
    return v


for f in toe_faces:
    a = find(int(f[0]))
    for v in f[1:]:
        parent[find(int(v))] = a
groups = {}
for f in toe_faces:
    groups.setdefault(find(int(f[0])), set()).update(int(v) for v in f)
for sign, side in ((-1, 'right'), (1, 'left')):
    # a toe: its own piece of skin in front of the foot, narrow across, long forwards
    toes = [g for g in groups.values() if np.sign(positions[list(g)][:, 0].mean()) == sign and
            positions[list(g)][:, 1].mean() < -.06 and np.ptp(positions[list(g)][:, 0]) < .035 and
            np.ptp(positions[list(g)][:, 1]) > .025]
    assert len(toes) == 5, 'the %s foot has five toes, found %d' % (side, len(toes))
# owner triangle budget and the render comparison with the figure before the reduction
triangle_count = sum(len(f) for f in faces_by_material.values())
assert 20000 <= triangle_count <= 35000, 'owner budget 20000-35000 triangles, found %d' % triangle_count
assert (triangle_count, len(positions)) == (TRIANGLES, VERTICES), (triangle_count, len(positions))
for hair in ('all', 'bare'):
    chosen = {m: f for m, f in faces_by_material.items() if hair == 'all' or m != 'SpaBodyHair'}
    triangles, colours = render.triangle_colours(ROOT, positions, uvs, chosen)
    for view in render.VIEWS:
        shape, encoded = RENDER_REFERENCE[view + '-' + hair]
        reference = np.frombuffer(zlib.decompress(base64.b64decode(''.join(encoded))), dtype=np.uint8).reshape(shape)
        image = render.render_view(positions, triangles, colours, view)
        difference, overlap = render.compare(image, reference)
        limit = RENDER_MAX_MEAN_DIFFERENCE if hair == 'all' else RENDER_MAX_MEAN_DIFFERENCE_BARE
        least = RENDER_MIN_SILHOUETTE_OVERLAP if hair == 'all' else RENDER_MIN_SILHOUETTE_OVERLAP_BARE
        assert difference <= limit, 'the reduced attendant looks different (%s, %s: %.2f)' % (view, hair, difference)
        assert overlap >= least, 'the reduced attendant has another silhouette (%s, %s: %.3f)' % (view, hair, overlap)
credits = read('CREDITS')
for texture in ('SpaChairWood.png', 'SpaLifebuoy.png', 'SpaMetalWorn.png', 'SpaAttendantHair.png', 'SpaAttendantFace.png'):
    assert re.search(r'^materials/textures/' + re.escape(texture) + r' AI-generated', credits, re.M), texture

print('check_spa_attendant_k22 ok: hairy attendant on a fitting rig, round whistle arc, swinging towel, textured chair, '
      'ring, hair and metal')
