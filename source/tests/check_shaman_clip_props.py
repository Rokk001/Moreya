"""The infirmary shaman shakes a rattle (RattleShake), trips over a bucket that stands before her (TripOverBucket) and
tastes a potion from a flask (PotionTaste).

Two parts, no compiler:
  wiring
      rrSetObjectAnimationState gives and takes the clip prop on every change into or out of RattleShake,
      TripOverBucket and PotionTaste (isClipWithProp names the clips); updateClipProp hands RattleShake to
      attachRattle, TripOverBucket to placeTripBucket and PotionTaste to attachFlask; the placement constants have the
      fixed values below.
  assets (OgreXMLConverter converts the shipped binaries)
      - the rattle InfirmaryRattle.mesh, the bucket InfirmaryBucket.mesh and the flask InfirmaryFlask.mesh: one
        material each (named like the mesh,
        materials/scripts/<name>.material with texture <name>.png, 512 x 512), 1 unit high with the base at z = 0, at
        most 4000 triangles each;
      - the rattle is posed with the real keys of RattleShake of InfirmaryShaman.skeleton, fixed to the right hand like
        RenderManager::attachRattle (pose in the middle of the clip): in the middle key its handle point lies in the palm
        and it points up and forwards (axis z >= 0.8, y < 0); while the arm is raised (right hand above 0.7 x height)
        the top of the rattle stays above the hand;
      - the bucket hangs without offset on the bone Bucket like RenderManager::placeTripBucket (a root bone, bind pose in
        the origin without rotation), as high as TRIP_BUCKET_HEIGHT_SHARE x the height, and is posed with the keys of
        TripOverBucket: at the first key it stands upright on the floor with a foot within 0.35 x height of its centre
        (before her feet); at no key does it sink more than 0.01 x height below the floor; at the last key it lies on
        its side (axis z at most 0.2) on the floor, away from her feet;
      - the flask hangs without offset on the bone Flask like RenderManager::attachFlask (a root bone, bind pose in the
        origin without rotation), as high as FLASK_HEIGHT_SHARE x the height, and is posed with the keys of
        PotionTaste: it stands upright at the first key (at most 10 degrees), tips at most 50 degrees, its base stays
        within 0.14 x height of the right hand bone at every key, and while she drinks the tip of its neck comes within
        0.14 x height of the head bone.

Fixed expected values of this branch (counted once): RATTLE_HEIGHT_SHARE 0.28, RATTLE_GRIP (0.14, 0, 0.2),
RATTLE_PALM_REACH 0.05, RATTLE_DIRECTION (0, -0.5, 1), RattleShake 2 s; rattle 3204 triangles, bucket 2994 triangles
(limit 4000 each); TRIP_BUCKET_BONE Bucket, TRIP_BUCKET_HEIGHT_SHARE 0.12, bucket radius 0.06 x height,
TripOverBucket 4.4 s, 221 keys; nearest foot at the first key 0.243 x height counted, nearest foot at the last key
0.329 x height counted (at least 0.3), lowest bucket point over the clip -0.0001 x height counted; rattle top at least
0.021 x height above the raised hand counted (37 raised keys); FLASK_BONE Flask, FLASK_HEIGHT_SHARE 0.075, PotionTaste
4.4 s, 221 keys, flask 2986 triangles; flask tilt 0 degrees at the first key and 44.6 at most counted, base at most
0.1277 x height from the right hand counted, neck tip 0.1303 x height from the head bone at the nearest counted.

Without --assets the models, materials and textures are read from the public tree or the content packages
(scripts/content_packages.py); without the content the props (room-infirmary) and the shaman (creatures) are named
as not checked.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_shaman_clip_props.py [--assets <folder with models/ and materials/>]
"""
from pathlib import Path
import json
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

CHECK = 'check_shaman_clip_props'
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else ROOT
RATTLE_SHARE = 0.28
RATTLE_GRIP = (0.14, 0.0, 0.2)
RATTLE_REACH = 0.05
RATTLE_DIRECTION = (0.0, -0.5, 1.0)
BUCKET_SHARE = 0.12
BUCKET_RADIUS = 0.06
BUCKET_FLOOR_GAP = 0.01
BUCKET_LYING_AXIS = 0.2
BUCKET_LAST_FOOT = 0.3
TRIANGLE_LIMIT = 4000
RATTLE_SECONDS = 2.0
TRIP_SECONDS = 4.4
FIRST_FOOT_REACH = 0.35
RAISED_HAND = 0.7
FLASK_SHARE = 0.075
FLASK_SECONDS = 4.4
FLASK_START_TILT = 10.0
FLASK_MOST_TILT = 50.0
FLASK_HAND_GAP = 0.14
FLASK_TIP_GAP = 0.14
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='shaman_props_'))
started = time.monotonic()


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def asset(relative):
    """Returns the path of a shipped asset: below --assets when given, else in the public tree or a content package."""
    if ASSETS != ROOT:
        return ASSETS / relative
    return content_packages.resolve(ROOT, relative)


def convert(name):
    """Converts a shipped binary mesh or skeleton to Ogre XML and returns its parsed root, None if it is missing."""
    source = asset('models/' + name)
    if not source.exists():
        return None
    target = work / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(work / 'convert.log'), str(source), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ET.parse(str(target)).getroot()


# ---- small quaternion and vector helpers (w, x, y, z)
def qmul(a, b):
    """Hamilton product of two quaternions."""
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
            a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
            a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def qinv(q):
    """Inverse of a unit quaternion."""
    return (q[0], -q[1], -q[2], -q[3])


def qrot(q, v):
    """Rotates the vector v by the unit quaternion q."""
    r = qmul(qmul(q, (0.0, v[0], v[1], v[2])), qinv(q))
    return (r[1], r[2], r[3])


def qaxis(element):
    """Quaternion of an Ogre XML rotation/rotate element (angle in radians and axis)."""
    if element is None:
        return (1.0, 0.0, 0.0, 0.0)
    angle = float(element.get('angle'))
    axis = element.find('axis')
    x, y, z = (float(axis.get(k)) for k in 'xyz')
    norm = math.sqrt(x * x + y * y + z * z)
    if norm < 1e-12 or abs(angle) < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    s = math.sin(angle / 2) / norm
    return (math.cos(angle / 2), x * s, y * s, z * s)


def qframe(direction, hint):
    """Quaternion whose z axis is the direction and whose x axis is as near to the hint as possible (alignMeshAxes)."""
    z = mul(direction, 1.0 / length(direction))
    x = sub(hint, mul(z, dot(hint, z)))
    x = mul(x, 1.0 / length(x))
    y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
    m = ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        return (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    i = max(range(3), key=lambda k: m[k][k])
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + m[i][i] - m[j][j] - m[k][k]) * 2
    q = [0.0, 0.0, 0.0, 0.0]
    q[0] = (m[k][j] - m[j][k]) / s
    q[1 + i] = 0.25 * s
    q[1 + j] = (m[j][i] + m[i][j]) / s
    q[1 + k] = (m[k][i] + m[i][k]) / s
    return tuple(q)


def vec(element, default=(0.0, 0.0, 0.0)):
    """Vector of an Ogre XML position/translate element."""
    if element is None:
        return default
    return tuple(float(element.get(k)) for k in 'xyz')


def add(a, b):
    """Sum of two vectors."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    """Difference of two vectors."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    """Vector times a number."""
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    """Dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a):
    """Length of a vector."""
    return math.sqrt(dot(a, a))


class Skeleton:
    """Bind pose, hierarchy and clips of an Ogre skeleton XML; poses exact key times like the engine."""

    def __init__(self, root):
        self.bones = {}
        self.order = []
        for bone in root.find('bones').findall('bone'):
            name = bone.get('name')
            self.order.append(name)
            self.bones[name] = (vec(bone.find('position')), qaxis(bone.find('rotation')))
        self.parent = {p.get('bone'): p.get('parent') for p in root.find('bonehierarchy').findall('boneparent')}
        self.clips = {}
        for anim in root.find('animations').findall('animation'):
            tracks = {}
            for track in anim.find('tracks').findall('track'):
                tracks[track.get('bone')] = [(float(k.get('time')), vec(k.find('translate')), qaxis(k.find('rotate')))
                                             for k in track.find('keyframes').findall('keyframe')]
            self.clips[anim.get('name')] = (float(anim.get('length')), tracks)

    def key_times(self, clip):
        """All key times of a clip."""
        return sorted({k[0] for keys in self.clips[clip][1].values() for k in keys})

    def pose(self, clip, t, interpolate=False):
        """-> {bone: (position, orientation)} in model space at time t (nearest key, or interpolated like the engine)."""
        tracks = self.clips[clip][1]
        world = {}

        def local(name):
            position, orientation = self.bones[name]
            keys = tracks.get(name)
            if not keys:
                return position, orientation
            if not interpolate:
                key = min(keys, key=lambda k: abs(k[0] - t))
                return add(position, key[1]), qmul(orientation, key[2])
            i = 0
            while i < len(keys) - 1 and keys[i + 1][0] <= t:
                i += 1
            a, b = keys[i], keys[min(i + 1, len(keys) - 1)]
            f = 0.0 if b[0] <= a[0] else max(0.0, min(1.0, (t - a[0]) / (b[0] - a[0])))
            qa, qb = a[2], b[2]
            if sum(x * y for x, y in zip(qa, qb)) < 0:
                qb = tuple(-x for x in qb)
            q = tuple(x + (y - x) * f for x, y in zip(qa, qb))
            n = math.sqrt(sum(x * x for x in q))
            return add(position, add(a[1], mul(sub(b[1], a[1]), f))), qmul(orientation, tuple(x / n for x in q))

        def solve(name):
            if name in world:
                return world[name]
            position, orientation = local(name)
            parent = self.parent.get(name)
            if parent is not None:
                pp, po = solve(parent)
                position, orientation = add(pp, qrot(po, position)), qmul(po, orientation)
            world[name] = (position, orientation)
            return world[name]

        for name in self.order:
            solve(name)
        return world


def positions(mesh_root):
    """All vertex positions of a mesh XML."""
    return [vec(p) for p in mesh_root.iter('position')]


# ================================================================================================ wiring
source = (ROOT / 'source/render/RenderManager.cpp').read_text(encoding='utf-8')
constants = {
    'RATTLE_MESH = "InfirmaryRattle.mesh";': 'rattle mesh InfirmaryRattle.mesh',
    'RATTLE_BONE = "RightHand";': 'rattle in the right hand',
    'RATTLE_HEIGHT_SHARE = 0.28f;': 'rattle height share 0.28',
    'RATTLE_GRIP(0.14f, 0.0f, 0.2f);': 'rattle grip point (0.14, 0, 0.2)',
    'RATTLE_PALM_REACH = 0.05f;': 'rattle palm reach 0.05',
    'RATTLE_DIRECTION(0.0f, -0.5f, 1.0f);': 'rattle direction (0, -0.5, 1)',
    'TRIP_BUCKET_MESH = "InfirmaryBucket.mesh";': 'bucket mesh InfirmaryBucket.mesh',
    'TRIP_BUCKET_BONE = "Bucket";': 'bucket on the bone Bucket',
    'TRIP_BUCKET_HEIGHT_SHARE = 0.12f;': 'bucket height share 0.12',
    'attachObjectToBone(TRIP_BUCKET_BONE, bucketEntity);': 'bucket hung on its bone without offset',
    'FLASK_MESH = "InfirmaryFlask.mesh";': 'flask mesh InfirmaryFlask.mesh',
    'FLASK_BONE = "Flask";': 'flask on the bone Flask',
    'FLASK_HEIGHT_SHARE = 0.075f;': 'flask height share 0.075',
    'attachObjectToBone(FLASK_BONE, flaskEntity);': 'flask hung on its bone without offset',
}
for text, name in constants.items():
    if text not in source:
        fail('RenderManager.cpp: ' + name + ' missing (' + text + ')')
figure_clips = re.search(r'bool isClipWithProp\(const std::string& clip\)\s*\{[^}]*\}', source)
if figure_clips is None or 'EntityAnimation::rattle_shake_anim' not in figure_clips.group(0) or \
        'EntityAnimation::trip_over_bucket_anim' not in figure_clips.group(0) or \
        'EntityAnimation::potion_taste_anim' not in figure_clips.group(0):
    fail('isClipWithProp does not name RattleShake, TripOverBucket and PotionTaste')
if not re.search(r'if\(isClipWithProp\(anim\) \|\|\s*\(\(previousState != nullptr\) && '
                 r'isClipWithProp\(previousState->getAnimationName\(\)\)\)\)\s*updateClipProp\(objectName, anim\);',
                 source):
    fail('rrSetObjectAnimationState does not give and take the figure clip props')
for call, name in (('attachRattle(objectName, holder, *skeleton);', 'the rattle'),
                   ('placeTripBucket(objectName, holder);', 'the bucket'),
                   ('attachFlask(objectName, holder, *skeleton);', 'the flask')):
    if call not in source:
        fail('updateClipProp does not give the shaman ' + name)
animations = (ROOT / 'source/entities/MovableGameEntity.h').read_text(encoding='utf-8')
for text in ('rattle_shake_anim = "RattleShake";', 'trip_over_bucket_anim = "TripOverBucket";',
             'potion_taste_anim = "PotionTaste";'):
    if text not in animations:
        fail('MovableGameEntity.h: ' + text + ' missing')

# ================================================================================================ assets
assets_started = time.monotonic()
info = {}
props = {name: convert(name + '.mesh') for name in ('InfirmaryRattle', 'InfirmaryBucket', 'InfirmaryFlask')}
shaman_mesh = convert('InfirmaryShaman.mesh')
shaman_skeleton = convert('InfirmaryShaman.skeleton')
missing = ['models/%s.mesh, its material and texture' % name for name, root in props.items() if root is None]
if shaman_mesh is None or shaman_skeleton is None:
    missing.append('models/InfirmaryShaman.mesh and its skeleton (RattleShake, TripOverBucket, PotionTaste)')
if missing and ASSETS == ROOT and not content_packages.has_content(ROOT):
    content_packages.unchecked(CHECK, missing)
elif missing:
    for name in missing:
        fail('missing: ' + name)
else:
    bounds = {}
    for name, root in props.items():
        points = positions(root)
        lo = tuple(min(p[i] for p in points) for i in range(3))
        hi = tuple(max(p[i] for p in points) for i in range(3))
        bounds[name] = (lo, hi)
        triangles = sum(1 for _ in root.iter('face'))
        materials = sorted({s.get('material') for s in root.iter('submesh')})
        info[name] = {'triangles': triangles, 'materials': materials}
        if triangles > TRIANGLE_LIMIT:
            fail('%s.mesh: %d triangles, at most %d' % (name, triangles, TRIANGLE_LIMIT))
        if materials != [name]:
            fail('%s.mesh: materials %s, expected only %s' % (name, materials, name))
        if abs(lo[2]) > 1e-3 or abs(hi[2] - 1.0) > 1e-3:
            fail('%s.mesh: z from %.4f to %.4f, expected base at 0 and 1 unit high' % (name, lo[2], hi[2]))
        material_file = asset('materials/scripts/%s.material' % name)
        material_text = material_file.read_text(encoding='utf-8') if material_file.exists() else ''
        block = re.search(r'material %s\s*\{.*?\n\}' % name, material_text, re.S)
        if block is None or ('texture %s.png' % name) not in block.group(0):
            fail('material %s with texture %s.png not found' % (name, name))
        texture = asset('materials/textures/%s.png' % name)
        if not texture.exists():
            fail('materials/textures/%s.png missing' % name)
        else:
            with Image.open(texture) as image:
                if image.size != (512, 512):
                    fail('%s.png: %s, expected 512 x 512' % (name, image.size))

    body = positions(shaman_mesh)
    height = max(p[2] for p in body) - min(p[2] for p in body)
    skeleton = Skeleton(shaman_skeleton)
    for clip, seconds in (('RattleShake', RATTLE_SECONDS), ('TripOverBucket', TRIP_SECONDS),
                          ('PotionTaste', FLASK_SECONDS)):
        if clip not in skeleton.clips:
            fail('InfirmaryShaman.skeleton: no %s clip' % clip)
        elif abs(skeleton.clips[clip][0] - seconds) > 1e-3:
            fail('%s: %.3f s, expected %.2f s' % (clip, skeleton.clips[clip][0], seconds))
    if 'RattleShake' in skeleton.clips and 'RightHand' in skeleton.bones:
        # ---- the rattle, placed like RenderManager::attachRattle
        length_clip = skeleton.clips['RattleShake'][0]
        hand, hand_turn = skeleton.pose('RattleShake', 0.5 * length_clip, interpolate=True)['RightHand']
        lo, hi = bounds['InfirmaryRattle']
        scale = RATTLE_SHARE * height / (hi[2] - lo[2])
        wanted = qframe(RATTLE_DIRECTION, (1.0, 0.0, 0.0))
        palm = add(hand, qrot(hand_turn, (0.0, RATTLE_REACH * height, 0.0)))
        origin = sub(palm, qrot(wanted, mul(RATTLE_GRIP, scale)))
        rotation = qmul(qinv(hand_turn), wanted)
        offset = qrot(qinv(hand_turn), sub(origin, hand))
        tops = []
        for t in skeleton.key_times('RattleShake'):
            key_hand, key_turn = skeleton.pose('RattleShake', t)['RightHand']
            turn = qmul(key_turn, rotation)
            key_origin = add(key_hand, qrot(key_turn, offset))
            if key_hand[2] > RAISED_HAND * height:
                tops.append((qrot(turn, (0.0, 0.0, 1.0))[2], add(key_origin, qrot(turn, (0.0, 0.0, hi[2] * scale)))[2]
                             - key_hand[2]))
        axis = qrot(qmul(hand_turn, rotation), (0.0, 0.0, 1.0))
        grip = add(add(hand, qrot(hand_turn, offset)), qrot(qmul(hand_turn, rotation), mul(RATTLE_GRIP, scale)))
        info['rattle'] = {'axis_mid': [round(v, 3) for v in axis], 'grip_gap_mid': round(length(sub(grip, palm)) / height, 5),
                          'raised_keys': len(tops), 'top_above_hand_min': round(min(t[1] for t in tops) / height, 3)
                          if tops else None}
        if length(sub(grip, palm)) > 1e-4 * height:
            fail('RattleShake middle: the handle of the rattle is not in the palm')
        if axis[2] < 0.8 or axis[1] >= 0.0:
            fail('RattleShake middle: the rattle points %s, expected up and forwards' % (tuple(round(v, 3) for v in axis),))
        if not tops:
            fail('RattleShake: the right hand is never raised above %.1f x height' % RAISED_HAND)
        elif min(t[1] for t in tops) <= 0.0:
            fail('RattleShake: the rattle hangs below the raised hand')
    if 'TripOverBucket' in skeleton.clips and 'Bucket' not in skeleton.bones:
        fail('InfirmaryShaman.skeleton: no bone Bucket for the bucket of TripOverBucket')
    elif 'TripOverBucket' in skeleton.clips and 'LeftFoot' in skeleton.bones and 'RightFoot' in skeleton.bones:
        # ---- the bucket, hung on the bone Bucket like RenderManager::placeTripBucket
        bind_position, bind_turn = skeleton.bones['Bucket']
        if 'Bucket' in skeleton.parent or length(bind_position) > 1e-6 or abs(abs(bind_turn[0]) - 1.0) > 1e-6:
            fail('bone Bucket: expected a root bone with its bind pose in the origin without rotation')
        lo, hi = bounds['InfirmaryBucket']
        scale = BUCKET_SHARE * height / (hi[2] - lo[2])
        radius = 0.5 * max(hi[0] - lo[0], hi[1] - lo[1]) * scale / height
        if abs(radius - BUCKET_RADIUS) > 1e-3:
            fail('bucket radius %.4f x height, expected %.3f' % (radius, BUCKET_RADIUS))
        times = skeleton.key_times('TripOverBucket')
        lows, axes, gaps = [], [], []
        for t in times:
            pose = skeleton.pose('TripOverBucket', t)
            base, turn = pose['Bucket']
            axis = qrot(turn, (0.0, 0.0, 1.0))
            top = add(base, mul(axis, (hi[2] - lo[2]) * scale))
            rim = radius * height * math.sqrt(max(0.0, 1.0 - axis[2] * axis[2]))
            centre = add(base, mul(axis, 0.5 * (hi[2] - lo[2]) * scale))
            lows.append(min(base[2], top[2]) - rim)
            axes.append(axis[2])
            gaps.append(min(math.hypot(pose[f][0][0] - centre[0], pose[f][0][1] - centre[1])
                            for f in ('LeftFoot', 'RightFoot')) / height)
        info['bucket'] = {'keys': len(times), 'first_foot_gap': round(gaps[0], 3), 'last_foot_gap': round(gaps[-1], 3),
                          'lowest_point': round(min(lows) / height, 4), 'first_axis_z': round(axes[0], 3),
                          'last_axis_z': round(axes[-1], 3), 'last_floor_gap': round(lows[-1] / height, 4)}
        if axes[0] < 0.99 or abs(lows[0]) > BUCKET_FLOOR_GAP * height:
            fail('TripOverBucket start: the bucket does not stand upright on the floor')
        if gaps[0] > FIRST_FOOT_REACH:
            fail('TripOverBucket start: the nearest foot is %.3f x height from the bucket, at most %.2f'
                 % (gaps[0], FIRST_FOOT_REACH))
        if min(lows) < -BUCKET_FLOOR_GAP * height:
            fail('TripOverBucket: the bucket sinks %.4f x height below the floor' % (-min(lows) / height))
        if abs(axes[-1]) > BUCKET_LYING_AXIS or abs(lows[-1]) > BUCKET_FLOOR_GAP * height:
            fail('TripOverBucket end: the bucket does not lie on its side on the floor')
        if gaps[-1] < BUCKET_LAST_FOOT:
            fail('TripOverBucket end: the bucket lies %.3f x height from her feet, at least %.2f'
                 % (gaps[-1], BUCKET_LAST_FOOT))
    if 'PotionTaste' in skeleton.clips and 'Flask' not in skeleton.bones:
        fail('InfirmaryShaman.skeleton: no bone Flask for the flask of PotionTaste')
    elif 'PotionTaste' in skeleton.clips and 'RightHand' in skeleton.bones and 'Head' in skeleton.bones:
        # ---- the flask, hung on the bone Flask like RenderManager::attachFlask
        bind_position, bind_turn = skeleton.bones['Flask']
        if 'Flask' in skeleton.parent or length(bind_position) > 1e-6 or abs(abs(bind_turn[0]) - 1.0) > 1e-6:
            fail('bone Flask: expected a root bone with its bind pose in the origin without rotation')
        lo, hi = bounds['InfirmaryFlask']
        scale = FLASK_SHARE * height / (hi[2] - lo[2])
        hand_gaps, tip_gaps, tilts, lows = [], [], [], []
        for t in skeleton.key_times('PotionTaste'):
            pose = skeleton.pose('PotionTaste', t)
            base, turn = pose['Flask']
            axis = qrot(turn, (0.0, 0.0, 1.0))
            tip = add(base, mul(axis, (hi[2] - lo[2]) * scale))
            hand_gaps.append(length(sub(base, pose['RightHand'][0])) / height)
            tip_gaps.append(length(sub(tip, pose['Head'][0])) / height)
            tilts.append(math.degrees(math.acos(max(-1.0, min(1.0, axis[2])))))
            lows.append(min(base[2], tip[2]) / height)
        info['flask'] = {'keys': len(tilts), 'first_tilt': round(tilts[0], 1), 'largest_tilt': round(max(tilts), 1),
                         'largest_hand_gap': round(max(hand_gaps), 4), 'nearest_tip_head_gap': round(min(tip_gaps), 4),
                         'lowest_point': round(min(lows), 3)}
        if tilts[0] > FLASK_START_TILT:
            fail('PotionTaste start: the flask leans %.1f degrees, at most %.0f' % (tilts[0], FLASK_START_TILT))
        if max(tilts) > FLASK_MOST_TILT:
            fail('PotionTaste: the flask tips %.1f degrees, at most %.0f' % (max(tilts), FLASK_MOST_TILT))
        if max(hand_gaps) > FLASK_HAND_GAP:
            fail('PotionTaste: the flask base leaves the right hand by %.4f x height, at most %.2f'
                 % (max(hand_gaps), FLASK_HAND_GAP))
        if min(tip_gaps) > FLASK_TIP_GAP:
            fail('PotionTaste: the neck of the flask comes no nearer than %.4f x height to the head bone, at most %.2f'
                 % (min(tip_gaps), FLASK_TIP_GAP))
assets_seconds = time.monotonic() - assets_started
print('ODP_TEST_PHASE ' + json.dumps({'name': 'assets', 'seconds': round(assets_seconds, 3)}))
print(json.dumps(info, indent=1))
print('ODP_TEST_PHASE ' + json.dumps({'name': 'total', 'seconds': round(time.monotonic() - started, 3)}))
if fails:
    for text in fails:
        print(CHECK + ': ' + text)
    sys.exit(1)
print('shaman clip props ok')
