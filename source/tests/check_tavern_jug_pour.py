"""The innkeeper holds a jug while he pours a drink (Pour clip of the tavern innkeeper).

Two parts, no compiler:
  wiring
      RenderManager gives the jug on every change into or out of the Pour clip (rrSetObjectAnimationState calls
      updateClipProp for InnkeeperPose::pour as for HerbSniff), attachPourJug hangs it on a node that
      updateFollowingClipProps moves with the left hand in every frame (called from updateRenderAnimations), and
      removeClipProp also forgets the hold; the placement constants have the fixed values below.
  assets (OgreXMLConverter converts the shipped binaries)
      - the jug TavernJug.mesh: one material TavernJug (materials/scripts/TavernJug.material), 1 unit high with its
        base at z = 0, the handle on +x and the spout on -x, at most 4000 triangles; texture tavern/TavernJug.png 512 x 512
        named by the material;
      - the counter top (TavernCounter.mesh) lies POUR_JUG_COUNTER_SHARE x the height of the innkeeper mesh above the
        floor;
      - the jug is posed with the real keys of the Pour clip of Innkeeper.skeleton, placed like
        RenderManager::placeFollowingClipProp: fixed to the left hand as it is at the start of the clip, lifted by the
        deepest point of its base ring below the counter top. At the first key it stands on the counter without a lift,
        its handle point in the palm; at no key does the base ring go below the counter top; the lift stays small (the
        handle stays near the palm); the rolling hand tips the jug at least 25 degrees towards the other hand (spout
        side down, -x of the innkeeper).

Fixed expected values of this branch (counted once): POUR_JUG_HEIGHT_SHARE 0.17, POUR_JUG_GRIP (0.40, 0, 0.32),
POUR_JUG_PALM_REACH 0.07, POUR_JUG_BASE_RING (-0.09, 0, 0.365), POUR_JUG_COUNTER_SHARE 0.5248, 12 ring points; jug 3123
triangles (limit 4000), handle out to x > 0.30 at the grip height, spout out to x < -0.45 above z 0.85; Pour 5 s, 151 keys;
lift at most 0.08 x height (0.0682 counted), tilt at least 25 degrees (50.1 counted), counter top 0.5248 x height.

Without --assets the models, materials and textures are read from the public tree or the content packages
(scripts/content_packages.py); without the content the jug (room-tavern), the innkeeper (creatures) and the counter
(room-tavern) are named as not checked.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_tavern_jug_pour.py [--assets <folder with models/ and materials/>]
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

CHECK = 'check_tavern_jug_pour'
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else ROOT
JUG_SHARE = 0.17
GRIP = (0.40, 0.0, 0.32)
PALM_REACH = 0.07
BASE_RING = (-0.09, 0.0, 0.365)
COUNTER_SHARE = 0.5248
RING_POINTS = 12
JUG_TRIANGLES_LIMIT = 4000
POUR_SECONDS = 5.0
MAX_LIFT = 0.08
MIN_TILT_DEGREES = 25.0
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='tavern_jug_'))
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


def vec(element, default=(0.0, 0.0, 0.0)):
    """Vector of an Ogre XML position/translate/scale element."""
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


def length(a):
    """Length of a vector."""
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


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

    def pose(self, clip, t):
        """-> {bone: (position, orientation)} in model space at a key time t of the clip."""
        tracks = self.clips[clip][1]
        world = {}

        def solve(name):
            if name in world:
                return world[name]
            position, orientation = self.bones[name]
            keys = tracks.get(name)
            if keys:
                key = min(keys, key=lambda k: abs(k[0] - t))
                position = add(position, key[1])
                orientation = qmul(orientation, key[2])
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
    'POUR_JUG_HEIGHT_SHARE = 0.17f;': 'jug height share 0.17',
    'POUR_JUG_GRIP(0.40f, 0.0f, 0.32f);': 'grip point (0.40, 0, 0.32)',
    'POUR_JUG_PALM_REACH = 0.07f;': 'palm reach 0.07',
    'POUR_JUG_BASE_RING(-0.09f, 0.0f, 0.365f);': 'base ring (-0.09, 0, 0.365)',
    'POUR_JUG_COUNTER_SHARE = 0.5248f;': 'counter share 0.5248',
    'POUR_JUG_RING_POINTS = 12;': '12 ring points',
    'POUR_JUG_MESH = "TavernJug.mesh";': 'jug mesh TavernJug.mesh',
    'POUR_JUG_BONE = "LeftHand";': 'jug in the left hand',
}
for text, name in constants.items():
    if text not in source:
        fail('RenderManager.cpp: ' + name + ' missing (' + text + ')')
hook = re.search(r'if\(isFigureClipWithProp\(anim\) \|\|\s*\(\(previousState != nullptr\) && '
                 r'isFigureClipWithProp\(previousState->getAnimationName\(\)\)\)\)\s*updateClipProp\(objectName, anim\);',
                 source)
figure_clips = re.search(r'bool isFigureClipWithProp\(const std::string& clip\)\s*\{[^}]*\}', source)
if hook is None or figure_clips is None or 'InnkeeperPose::pour' not in figure_clips.group(0):
    fail('rrSetObjectAnimationState does not give and take the jug on every change into or out of Pour')
if not re.search(r'void RenderManager::updateRenderAnimations\(Ogre::Real timeSinceLastFrame\)\s*\{[^}]*'
                 r'updateFollowingClipProps\(\);', source):
    fail('updateRenderAnimations does not move the following clip props every frame')
if not re.search(r'void RenderManager::removeClipProp\(const std::string& objectName\)\s*\{\s*'
                 r'mFollowingClipProps\.erase\(objectName\);', source):
    fail('removeClipProp does not forget the hold of a following clip prop')
if 'attachPourJug(objectName, holder, *skeleton);' not in source:
    fail('updateClipProp does not give the innkeeper his jug')

# ================================================================================================ assets
assets_started = time.monotonic()
info = {}
jug = convert('TavernJug.mesh')
keeper_mesh = convert('Innkeeper.mesh')
keeper_skeleton = convert('Innkeeper.skeleton')
counter = convert('TavernCounter.mesh')
missing = [name for name, root in (('models/TavernJug.mesh, its material and texture', jug),
                                   ('models/Innkeeper.mesh and its skeleton (Pour clip)', keeper_skeleton),
                                   ('models/TavernCounter.mesh', counter)) if root is None]
if keeper_mesh is None and keeper_skeleton is not None:
    missing.append('models/Innkeeper.mesh')
if missing and ASSETS == ROOT and not content_packages.has_content(ROOT):
    content_packages.unchecked(CHECK, missing)
elif missing:
    for name in missing:
        fail('missing: ' + name)
else:
    # ---- the jug
    points = positions(jug)
    lo = tuple(min(p[i] for p in points) for i in range(3))
    hi = tuple(max(p[i] for p in points) for i in range(3))
    triangles = sum(1 for _ in jug.iter('face'))
    materials = sorted({s.get('material') for s in jug.iter('submesh')})
    info['jug'] = {'triangles': triangles, 'materials': materials, 'min': [round(v, 4) for v in lo],
                   'max': [round(v, 4) for v in hi]}
    if triangles > JUG_TRIANGLES_LIMIT:
        fail('TavernJug.mesh: %d triangles, at most %d' % (triangles, JUG_TRIANGLES_LIMIT))
    if materials != ['TavernJug']:
        fail('TavernJug.mesh: materials %s, expected only TavernJug' % materials)
    if abs(lo[2]) > 1e-3 or abs(hi[2] - 1.0) > 1e-3:
        fail('TavernJug.mesh: z from %.4f to %.4f, expected base at 0 and 1 unit high' % (lo[2], hi[2]))
    # handle on +x: the mesh has vertices at the grip point's height out at the handle, the spout lip on -x at the top
    handle = [p for p in points if abs(p[2] - GRIP[2]) < 0.05 and p[0] > 0.30]
    spout = [p for p in points if p[2] > 0.85 and p[0] < -0.45]
    if not handle or not spout:
        fail('TavernJug.mesh: handle not on +x at the grip height or spout not on -x at the top')
    material_file = asset('materials/scripts/TavernJug.material')
    material_text = material_file.read_text(encoding='utf-8') if material_file.exists() else ''
    block = re.search(r'material TavernJug\s*\{.*?\n\}', material_text, re.S)
    if block is None or 'texture TavernJug.png' not in block.group(0):
        fail('material TavernJug with texture TavernJug.png not found')
    texture = asset('materials/textures/tavern/TavernJug.png')
    if not texture.exists():
        fail('materials/textures/tavern/TavernJug.png missing')
    else:
        with Image.open(texture) as image:
            if image.size != (512, 512):
                fail('TavernJug.png: %s, expected 512 x 512' % (image.size,))

    # ---- the innkeeper and the counter
    body = positions(keeper_mesh)
    height = max(p[2] for p in body) - min(p[2] for p in body)
    counter_top = max(p[2] for p in positions(counter))
    info['counter_share'] = round(counter_top / height, 4)
    if abs(counter_top / height - COUNTER_SHARE) > 1e-3:
        fail('counter top %.4f of %.4f = %.4f, expected %.4f' % (counter_top, height, counter_top / height, COUNTER_SHARE))
    skeleton = Skeleton(keeper_skeleton)
    if 'Pour' not in skeleton.clips or 'LeftHand' not in skeleton.bones:
        fail('Innkeeper.skeleton: no Pour clip or no LeftHand bone')
    else:
        clip_length = skeleton.clips['Pour'][0]
        if abs(clip_length - POUR_SECONDS) > 1e-3:
            fail('Pour: %.3f s, expected %.1f s' % (clip_length, POUR_SECONDS))
        times = skeleton.key_times('Pour')
        hand0, turn0 = skeleton.pose('Pour', times[0])['LeftHand']
        scale = JUG_SHARE * height / (hi[2] - lo[2])
        palm0 = add(hand0, qrot(turn0, (0.0, PALM_REACH * height, 0.0)))
        rotation = qinv(turn0)
        offset = qrot(qinv(turn0), sub(sub(palm0, mul(GRIP, scale)), hand0))
        rest = COUNTER_SHARE * height
        ring = [(BASE_RING[0] + BASE_RING[2] * math.cos(2 * math.pi * i / RING_POINTS),
                 BASE_RING[1] + BASE_RING[2] * math.sin(2 * math.pi * i / RING_POINTS), 0.0) for i in range(RING_POINTS)]
        lifts, tilts, gaps, lows = [], [], [], []
        for t in times:
            hand, hand_turn = skeleton.pose('Pour', t)['LeftHand']
            turn = qmul(hand_turn, rotation)
            origin = add(hand, qrot(hand_turn, offset))
            lowest = min([origin[2]] + [add(origin, qrot(turn, mul(p, scale)))[2] for p in ring])
            lift = max(0.0, rest - lowest)
            origin = (origin[0], origin[1], origin[2] + lift)
            lows.append(min([origin[2]] + [add(origin, qrot(turn, mul(p, scale)))[2] for p in ring]) - rest)
            lifts.append(lift / height)
            up = qrot(turn, (0.0, 0.0, 1.0))
            # tipping towards -x of the innkeeper (the other hand) counts positive
            tilts.append(math.degrees(math.atan2(-up[0], up[2])))
            palm = add(hand, qrot(hand_turn, (0.0, PALM_REACH * height, 0.0)))
            gaps.append(length(sub(add(origin, qrot(turn, mul(GRIP, scale))), palm)) / height)
        info['pour'] = {'keys': len(times), 'lift_first': round(lifts[0], 4), 'lift_max': round(max(lifts), 4),
                        'tilt_max_deg': round(max(tilts), 1), 'grip_gap_first': round(gaps[0], 4),
                        'grip_gap_max': round(max(gaps), 4), 'base_below_counter': round(min(lows), 6)}
        if lifts[0] > 1e-4 or gaps[0] > 1e-4:
            fail('Pour start: the jug is lifted %.4f or its handle %.4f x height from the palm' % (lifts[0], gaps[0]))
        if min(lows) < -1e-5:
            fail('Pour: the base of the jug goes %.5f below the counter top' % -min(lows))
        if max(lifts) > MAX_LIFT:
            fail('Pour: the jug is lifted up to %.4f x height off the palm, at most %.2f' % (max(lifts), MAX_LIFT))
        if max(gaps) > MAX_LIFT + 1e-4:
            fail('Pour: the handle leaves the palm by %.4f x height' % max(gaps))
        if max(tilts) < MIN_TILT_DEGREES:
            fail('Pour: the jug tips only %.1f degrees towards the other hand, at least %.0f' % (max(tilts), MIN_TILT_DEGREES))
assets_seconds = time.monotonic() - assets_started
print('ODP_TEST_PHASE ' + json.dumps({'name': 'assets', 'seconds': round(assets_seconds, 3)}))
print(json.dumps(info, indent=1))
print('ODP_TEST_PHASE ' + json.dumps({'name': 'total', 'seconds': round(time.monotonic() - started, 3)}))
if fails:
    for text in fails:
        print(CHECK + ': ' + text)
    sys.exit(1)
print('tavern jug pour ok')
