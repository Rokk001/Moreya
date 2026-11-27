"""Two dice in the tavern dice game: shaken between the hands, then lying on the table (SitDiceWin, SitDiceLose).

Two parts, no compiler:
  wiring
      rrSetObjectAnimationState gives and takes the dice on every change into or out of SitDiceWin and SitDiceLose
      (isClipWithProp names both clips); updateClipProp hands them to attachDice, which hangs two dice on nodes of the
      guest that updateFollowingClipProps moves every frame through placeDice; removeClipProp also removes the second
      die and forgets the guest; the placement constants have the fixed values below.
  assets (OgreXMLConverter converts the shipped binaries)
      - the die TavernDie.mesh: one material TavernDie (materials/scripts/TavernDie.material, texture
        tavern/TavernDie.png, 512 x 512), a cube 1 unit across with its base at z = 0, at most 4000 triangles;
      - the table top of TavernTable.mesh lies TAVERN_TABLE_TOP above the floor, and the place of the thrown dice,
        DICE_TABLE_REACH before a guest on its bench (BENCH_OFFSET from the middle of the table), lies on the table top
        with both dice (DICE_GAP apart, DIE_SIZE big) inside its width across;
      - for every creature skeleton with SitDiceWin and SitDiceLose: up to the throw (DICE_THROW_SHARE of the clip) the
        hands stay close together (shaking the dice between them), and after it they open: the distance of the hands at
        0.40 of the clip is at least 1.25 times their largest distance while shaking (0.06 to 0.35 of the clip).

Fixed expected values of this branch (counted once): DIE_SIZE 0.05, DICE_GAP 0.07, DICE_PALM_REACH 0.05,
DICE_THROW_SHARE 0.35, DICE_TABLE_REACH 0.2, TAVERN_TABLE_TOP 0.4425; die 1774 triangles (limit 4000); table half width
across 0.323 and bench offset 0.4116 (check_tavern_stools_863.py); 24 skeletons with both clips, largest hand distance while
shaking 0.226 (Troll), smallest opening ratio 1.33 (Troll, SitDiceLose).

Without --assets the models, materials and textures are read from the public tree or the content packages
(scripts/content_packages.py); without the content the die and the table (room-tavern) and the creature skeletons
(creatures) are named as not checked.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_tavern_dice.py [--assets <folder with models/ and materials/>]
"""
from pathlib import Path
import concurrent.futures
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

CHECK = 'check_tavern_dice'
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else ROOT
DIE_SIZE = 0.05
DICE_GAP = 0.07
DICE_THROW_SHARE = 0.35
DICE_TABLE_REACH = 0.2
TABLE_TOP = 0.4425
TABLE_HALF_ACROSS = 0.323
BENCH_OFFSET = 0.4116
TRIANGLE_LIMIT = 4000
SKELETONS_WITH_DICE = 24
MIN_OPENING = 1.25
CLIPS = ('SitDiceWin', 'SitDiceLose')
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='tavern_dice_'))
started = time.monotonic()


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def asset(relative):
    """Returns the path of a shipped asset: below --assets when given, else in the public tree or a content package."""
    if ASSETS != ROOT:
        return ASSETS / relative
    return content_packages.resolve(ROOT, relative)


def convert_file(source, name):
    """Converts a binary mesh or skeleton to an Ogre XML file and returns its path."""
    target = work / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(work / (name + '.log')), str(source), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target


def convert(source, name):
    """Converts a binary mesh or skeleton to Ogre XML and returns its parsed root, None if it is missing."""
    if not source.exists():
        return None
    target = work / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(work / 'convert.log'), str(source), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ET.parse(str(target)).getroot()


def qmul(a, b):
    """Hamilton product of two quaternions (w, x, y, z)."""
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
            a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
            a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def qrot(q, v):
    """Rotates the vector v by the unit quaternion q."""
    r = qmul(qmul(q, (0.0, v[0], v[1], v[2])), (q[0], -q[1], -q[2], -q[3]))
    return (r[1], r[2], r[3])


def qaxis(element):
    """Quaternion of an Ogre XML rotation/rotate element."""
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


def vec(element):
    """Vector of an Ogre XML position/translate element."""
    if element is None:
        return (0.0, 0.0, 0.0)
    return tuple(float(element.get(k)) for k in 'xyz')


def add(a, b):
    """Sum of two vectors."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def distance(a, b):
    """Distance of two points."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class Hands:
    """Both hands of a skeleton over its clips: the bones are read once, only the chains up from LeftHand and RightHand
    are posed, keys interpolated like the engine."""

    def __init__(self, root):
        self.bones = {b.get('name'): (vec(b.find('position')), qaxis(b.find('rotation'))) for b in root.find('bones')}
        self.parent = {p.get('bone'): p.get('parent') for p in root.find('bonehierarchy')}
        chain = set()
        for name in ('LeftHand', 'RightHand'):
            while name is not None and name in self.bones:
                chain.add(name)
                name = self.parent.get(name)
        self.clips = {}
        for anim in root.find('animations'):
            if anim.get('name') not in CLIPS:
                continue
            tracks = {}
            for track in anim.find('tracks'):
                if track.get('bone') in chain:
                    tracks[track.get('bone')] = [(float(k.get('time')), vec(k.find('translate')), qaxis(k.find('rotate')))
                                                 for k in track.find('keyframes')]
            self.clips[anim.get('name')] = (float(anim.get('length')), tracks)

    def at(self, clip, share):
        """Model space positions of LeftHand and RightHand at a share of the clip."""
        length_clip, tracks = self.clips[clip]
        t = share * length_clip
        world = {}

        def solve(name):
            if name in world:
                return world[name]
            position, orientation = self.bones[name]
            keys = tracks.get(name)
            if keys:
                i = 0
                while i < len(keys) - 1 and keys[i + 1][0] <= t:
                    i += 1
                a, b = keys[i], keys[min(i + 1, len(keys) - 1)]
                f = 0.0 if b[0] <= a[0] else max(0.0, min(1.0, (t - a[0]) / (b[0] - a[0])))
                qb = b[2] if sum(x * y for x, y in zip(a[2], b[2])) >= 0 else tuple(-x for x in b[2])
                q = tuple(x + (y - x) * f for x, y in zip(a[2], qb))
                n = math.sqrt(sum(x * x for x in q))
                position = add(position, tuple(x + (y - x) * f for x, y in zip(a[1], b[1])))
                orientation = qmul(orientation, tuple(x / n for x in q))
            if self.parent.get(name) is not None:
                pp, po = solve(self.parent[name])
                position, orientation = add(pp, qrot(po, position)), qmul(po, orientation)
            world[name] = (position, orientation)
            return world[name]
        return solve('LeftHand')[0], solve('RightHand')[0]


# ================================================================================================ wiring
source = (ROOT / 'source/render/RenderManager.cpp').read_text(encoding='utf-8')
constants = {
    'DIE_MESH = "TavernDie.mesh";': 'die mesh TavernDie.mesh',
    'DIE_SIZE = 0.05f;': 'die size 0.05',
    'DICE_GAP = 0.07f;': 'dice gap 0.07',
    'DICE_PALM_REACH = 0.05f;': 'palm reach 0.05',
    'DICE_THROW_SHARE = 0.35f;': 'throw at 0.35 of the clip',
    'DICE_TABLE_REACH = 0.2f;': 'dice 0.2 before the guest',
    'TAVERN_TABLE_TOP = 0.4425f;': 'table top 0.4425',
}
for text, name in constants.items():
    if text not in source:
        fail('RenderManager.cpp: ' + name + ' missing (' + text + ')')
clips = re.search(r'bool isClipWithProp\(const std::string& clip\)\s*\{[^}]*\}', source)
if clips is None or 'EntityAnimation::sit_dice_win_anim' not in clips.group(0) or \
        'EntityAnimation::sit_dice_lose_anim' not in clips.group(0):
    fail('isClipWithProp does not name SitDiceWin and SitDiceLose')
if 'attachDice(objectName, holder, *skeleton, clip);' not in source:
    fail('updateClipProp does not give the guest its dice')
if not re.search(r'void RenderManager::updateFollowingClipProps\(\)\s*\{.*?placeDice\(it->first, it->second\);', source, re.S):
    fail('updateFollowingClipProps does not move the dice every frame')
if not re.search(r'void RenderManager::removeClipProp\(const std::string& objectName\)\s*\{[^}]*mDiceHolders\.erase\(objectName\);'
                 r'.*?SECOND_DIE_SUFFIX', source, re.S):
    fail('removeClipProp does not remove the second die and forget the guest')

# ================================================================================================ assets
info = {}
die = convert(asset('models/TavernDie.mesh'), 'TavernDie.mesh')
table = convert(asset('models/TavernTable.mesh'), 'TavernTable.mesh')
skeleton_dir = asset('models/Goblin.skeleton').parent
missing = [name for name, root in (('models/TavernDie.mesh, its material and texture', die),
                                   ('models/TavernTable.mesh', table)) if root is None]
if not (skeleton_dir / 'Goblin.skeleton').exists():
    missing.append('creature skeletons (SitDiceWin, SitDiceLose)')
if missing and ASSETS == ROOT and not content_packages.has_content(ROOT):
    content_packages.unchecked(CHECK, missing)
elif missing:
    for name in missing:
        fail('missing: ' + name)
else:
    points = [vec(p) for p in die.iter('position')]
    lo = tuple(min(p[i] for p in points) for i in range(3))
    hi = tuple(max(p[i] for p in points) for i in range(3))
    triangles = sum(1 for _ in die.iter('face'))
    materials = sorted({s.get('material') for s in die.iter('submesh')})
    info['die'] = {'triangles': triangles, 'materials': materials, 'size': [round(hi[i] - lo[i], 4) for i in range(3)]}
    if triangles > TRIANGLE_LIMIT:
        fail('TavernDie.mesh: %d triangles, at most %d' % (triangles, TRIANGLE_LIMIT))
    if materials != ['TavernDie']:
        fail('TavernDie.mesh: materials %s, expected only TavernDie' % materials)
    if abs(lo[2]) > 1e-3 or any(abs(hi[i] - lo[i] - 1.0) > 1e-2 for i in range(3)):
        fail('TavernDie.mesh: not a cube 1 unit across on z = 0 (%s to %s)' % (lo, hi))
    material_file = asset('materials/scripts/TavernDie.material')
    text = material_file.read_text(encoding='utf-8') if material_file.exists() else ''
    block = re.search(r'material TavernDie\s*\{.*?\n\}', text, re.S)
    if block is None or 'texture TavernDie.png' not in block.group(0):
        fail('material TavernDie with texture TavernDie.png not found')
    texture = asset('materials/textures/tavern/TavernDie.png')
    if not texture.exists():
        fail('materials/textures/tavern/TavernDie.png missing')
    else:
        with Image.open(texture) as image:
            if image.size != (512, 512):
                fail('TavernDie.png: %s, expected 512 x 512' % (image.size,))

    top = max(p[2] for p in (vec(q) for q in table.iter('position')))
    info['table_top'] = round(top, 4)
    if abs(top - TABLE_TOP) > 1e-3:
        fail('TavernTable.mesh: top %.4f, expected %.4f' % (top, TABLE_TOP))
    # the thrown dice lie across the table from the guest: from the near edge to the far edge of the table top
    near, far = BENCH_OFFSET - TABLE_HALF_ACROSS, BENCH_OFFSET + TABLE_HALF_ACROSS
    reach_near, reach_far = DICE_TABLE_REACH - 0.5 * DIE_SIZE, DICE_TABLE_REACH + 0.3 * DICE_GAP + 0.5 * DIE_SIZE
    if reach_near < near or reach_far > far:
        fail('the thrown dice (%.3f to %.3f before the guest) do not lie on the table top (%.3f to %.3f)'
             % (reach_near, reach_far, near, far))

    rows = []
    skeletons_started = time.monotonic()
    # the clip names are stored as text in the binary skeleton: only skeletons that name both clips are converted, the
    # conversions (own processes) run side by side
    paths = [path for path in sorted(skeleton_dir.glob('*.skeleton'))
             if all(clip.encode('ascii') in path.read_bytes() for clip in CLIPS)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        converted = list(pool.map(lambda path: convert_file(path, path.name), paths))
    for path, target in zip(paths, converted):
        # one parsed skeleton at a time: only the hand chains of the two clips are kept
        root = ET.parse(str(target)).getroot()
        names = {a.get('name') for a in root.find('animations')}
        bones = {b.get('name') for b in root.find('bones')}
        if not all(c in names for c in CLIPS) or not {'LeftHand', 'RightHand'} <= bones:
            continue
        posed = Hands(root)
        del root
        for clip in CLIPS:
            shake = max(distance(*posed.at(clip, 0.06 + (DICE_THROW_SHARE - 0.06) * k / 29)) for k in range(30))
            opened = distance(*posed.at(clip, 0.40))
            rows.append((path.stem, clip, shake, opened / shake))
    print('ODP_TEST_PHASE ' + json.dumps({'name': 'skeletons', 'seconds': round(time.monotonic() - skeletons_started, 3)}))
    info['skeletons'] = len({r[0] for r in rows})
    info['largest_shake'] = max(rows, key=lambda r: r[2])[:3] if rows else None
    info['smallest_opening'] = min(rows, key=lambda r: r[3]) if rows else None
    if len({r[0] for r in rows}) != SKELETONS_WITH_DICE:
        fail('%d skeletons with SitDiceWin and SitDiceLose, expected %d' % (len({r[0] for r in rows}), SKELETONS_WITH_DICE))
    for name, clip, shake, opening in rows:
        if opening < MIN_OPENING:
            fail('%s %s: the hands open only %.2f times their shaking distance after the throw, at least %.2f'
                 % (name, clip, opening, MIN_OPENING))
print('ODP_TEST_PHASE ' + json.dumps({'name': 'total', 'seconds': round(time.monotonic() - started, 3)}))
print(json.dumps(info, indent=1, default=str))
if fails:
    for text in fails:
        print(CHECK + ': ' + text)
    sys.exit(1)
print('tavern dice ok')
