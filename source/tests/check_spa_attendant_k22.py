"""K22: the pool attendant is the hairy man and fits his skeleton, towel and whistle move naturally, chair and ring are
textured.

Reads models/PoolAttendant.mesh, models/PoolAttendant.skeleton and models/SpaChair.mesh through OgreXMLConverter, the
material scripts and the textures; no compiler, no game. Checks
(1) the look: the massive, hairy, pot-bellied man (body hair on arms, legs and chest, scalp hair and moustache, a belly
    far in front of the chest);
(2) mesh and skeleton fit each other: every elbow and knee joint lies in the middle of its limb (the mesh restored on
    2026-11-13 sat 7 cm beside the joints of the skeleton);
(3) the towel goes into the hand in TowelWave and no towel face stretches;
(4) TowelWave: the towel is in the hand above the shoulder, the hand goes round a loop on a smooth path, the towel and
    its free end turn smoothly from key to key and the end trails the towel;
(5) Whistle: the hand fetches the whistle and raises it to the lips on a round arc (the elbow swings up and the path
    bows out of the straight line), the whistle stays at the lips while the game plays the sound, the arm turns
    smoothly;
(6) every surface of the chair, the life ring and the attendant's hair, whistle and cord shows texture detail: the
    texture of its material, sampled at its texture coordinates, varies;
(7) the clips the code plays, two seconds each.
"""
from pathlib import Path
import math
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

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
for material in ('SpaSkin', 'SpaSuit', 'SpaHair', 'SpaBodyHair', 'SpaLinen', 'SpaWhistle', 'SpaEyes', 'SpaBlood'):
    assert material in faces_by_material, 'the attendant needs the material ' + material
assert len(faces_by_material['SpaHair']) >= 20000, 'full scalp hair and moustache'
assert len(faces_by_material['SpaBodyHair']) >= 10000, 'full body hair'
hair_bones = {}
for v in verts('SpaBodyHair'):
    bone = max(weights[v].items(), key=lambda item: item[1])[0]
    hair_bones[bone] = hair_bones.get(bone, 0) + 1
for part in ('UpperArm_R', 'UpperArm_L', 'Thigh_R', 'Thigh_L', 'Shin_R', 'Shin_L', 'Chest'):
    assert hair_bones.get(part, 0) >= 300, 'body hair on ' + part
assert 0 < len(faces_by_material['SpaBlood']) <= 200, 'a very little blood'
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
head = [v for v in verts('SpaSkin') if weights[v].get('Head', 0) > .5 and abs(positions[v][0]) < .012]
nose = min(head, key=lambda v: positions[v][1])
under = [v for v in head if positions[nose][2] - .06 < positions[v][2] < positions[nose][2] - .025]
lips = positions[min(under, key=lambda v: positions[v][1])]
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
# the way up: from the last key the whistle still hangs on the chest until it is at the lips
arrived = next(i for i in range(49) if np.linalg.norm(
    whistle[i]['WhistleHang'][:3, 3] - (whistle[i]['Head'] @ np.linalg.inv(BIND['Head']) @ np.append(lips, 1))[:3]) < .035)
fetched = max(i for i in range(arrived) if np.linalg.norm(whistle[i]['WhistleHang'][:3, 3] - whistle[0]['WhistleHang'][:3, 3]) < .01)
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
        [(mesh, m) for m in ('SpaHair', 'SpaBodyHair', 'SpaWhistle', 'SpaIronWorn', 'SpaSkin', 'SpaSuit', 'SpaLinen')]:
    spread, distinct = shown_detail(root, material)
    assert spread > .03 and distinct > .3, '%s shows no texture detail (spread %.3f, distinct %.2f)' % (material, spread,
                                                                                                         distinct)
credits = read('CREDITS')
for texture in ('SpaChairWood.png', 'SpaLifebuoy.png', 'SpaMetalWorn.png', 'SpaAttendantHair.png'):
    assert re.search(r'^materials/textures/' + re.escape(texture) + r' AI-generated', credits, re.M), texture

print('check_spa_attendant_k22 ok: hairy attendant on a fitting rig, round whistle arc, swinging towel, textured chair, '
      'ring, hair and metal')
