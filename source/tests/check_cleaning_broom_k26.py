"""Cleaning is visible and starts at every visible stain (INGAME-QS-10 K26, owner finding "keine Putzanimation, dass sie
irgendwie einen Besen nehmen und putzen"; answer to Q6 "Bei jedem Dreck").

Three parts:
  assets (no compiler; OgreXMLConverter converts the shipped binaries)
      The broom the game hangs on Weapon_R while a worker plays Clean (RenderManager: weapon mount, -90 degrees about x,
      scale BROOM_SHARE x the height of the worker mesh) is posed with the real keyframes of the Clean clip of both worker
      skeletons (Kobold, Dwarf1 for the dwarf worker), evaluated like the engine does (bind pose plus translate, times
      rotate, times scale, down the bone hierarchy) at every key:
      - the twig tips sweep the floor: lowest broom point between -0.02 and +0.12 x height, on the floor (<= 0.01 x
        height) in at least 40 % of the keys, and while on the floor the tips travel sideways over at least 0.30 x height;
      - both hands hold the handle: Weapon_L (the left fist) lies within 0.02 x height of the handle axis, above the
        right hand (between 0.15 and 0.30 broom lengths up the handle from the right grip);
      - the kobold's own pick (part of its model, Pick bone) is hidden for the whole clip (scale <= 0.01) and shown in
        Idle, Walk, Dig and Claim (scale 1);
      - clip list and the Clean length 1.6 s unchanged (Global Constraint 4);
      - the broom: at most 600 triangles, two textured materials CleaningBroom and CleaningBroom/Twigs without
        specular, texture CleaningBroom.png 512 x 512 with surface detail (luminance std >= 6), dark dungeon look
        (STYLE-GUIDE.md: mean luminance 45-95, mean saturation <= 0.45, p99.5 channel <= 170).
  wiring (no compiler)
      RenderManager gives the broom on every change into or out of a holdsBroom clip and hides the worker's tool; the
      weapon models stay hidden while sweeping; the search, the keeper's target lists and Room::needsCleaning all use
      CreatureActionSearchDirtToClean::isFloorDirtToClean, nothing uses the old room-stage or third-stage corridor limit,
      and global.cfg sets CleanTileFromStage 1.
  probe (cl)
      The production bodies of TileDirtSync::stageForValue, CreatureActionSearchDirtToClean::isFloorDirtToClean and
      Room::needsCleaning run with the [Dirt] values of global.cfg: a tile below DirtVisibleFrom is not cleaned, every
      visible stain (stage 1, 2, 3) is; a room whose mean is far below stage 2 but has one visible stain needs cleaning,
      a room with only invisible dirt does not, a prison never.
Fixed expected values of this branch (counted once): BROOM_SHARE 0.88, broom 328 triangles (limit 600), Clean 1.6 s,
44 clips in Kobold.skeleton and 53 in Dwarf1.skeleton, DirtVisibleFrom 10 / DirtStage2At 33.3333 / DirtStage3At 66.6667.
The probe compiles with cl, so it runs in the compile phase of the integration; `--no-compile` runs the other parts.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_cleaning_broom_k26.py [--no-compile] [--assets <folder with models/ and materials/>]
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
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else ROOT
BROOM_SHARE = 0.88
CLIP_COUNTS = {'Kobold': 44, 'Dwarf1': 53}
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='cleaning_broom_'))
started = time.monotonic()


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def body(source, signature):
    """Returns the production text from the signature to the end of its braces block."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def convert(name):
    """Converts a shipped binary mesh or skeleton to Ogre XML and returns its parsed root, None if it is missing."""
    source = ASSETS / 'models' / name
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


def qrot(q, v):
    """Rotates the vector v by the unit quaternion q."""
    r = qmul(qmul(q, (0.0, v[0], v[1], v[2])), (q[0], -q[1], -q[2], -q[3]))
    return (r[1], r[2], r[3])


def qaxis(element):
    """Quaternion of an Ogre XML rotation/rotate element (angle in radians and axis)."""
    if element is None:
        return (1.0, 0.0, 0.0, 0.0)
    angle = float(element.get('angle'))
    axis = element.find('axis')
    x, y, z = (float(axis.get(k)) for k in 'xyz')
    length = math.sqrt(x * x + y * y + z * z)
    if length < 1e-12 or abs(angle) < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    s = math.sin(angle / 2) / length
    return (math.cos(angle / 2), x * s, y * s, z * s)


def vec(element, default=(0.0, 0.0, 0.0)):
    """Vector of an Ogre XML position/translate/scale element."""
    if element is None:
        return default
    return tuple(float(element.get(k)) for k in 'xyz')


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a):
    return math.sqrt(dot(a, a))


class Skeleton:
    """Bind pose, hierarchy and clips of an Ogre skeleton XML; poses keys like the engine (linear keys, exact key times)."""

    def __init__(self, root):
        self.bones = {}
        self.order = []
        for bone in root.find('bones').findall('bone'):
            name = bone.get('name')
            self.order.append(name)
            self.bones[name] = (vec(bone.find('position')), qaxis(bone.find('rotation')),
                                vec(bone.find('scale'), (1.0, 1.0, 1.0)))
        self.parent = {p.get('bone'): p.get('parent') for p in root.find('bonehierarchy').findall('boneparent')}
        self.clips = {}
        for anim in root.find('animations').findall('animation'):
            tracks = {}
            for track in anim.find('tracks').findall('track'):
                keys = []
                for key in track.find('keyframes').findall('keyframe'):
                    keys.append((float(key.get('time')), vec(key.find('translate')), qaxis(key.find('rotate')),
                                 vec(key.find('scale'), (1.0, 1.0, 1.0))))
                tracks[track.get('bone')] = keys
            self.clips[anim.get('name')] = (float(anim.get('length')), tracks)

    def key_times(self, clip):
        """All key times of a clip."""
        return sorted({k[0] for keys in self.clips[clip][1].values() for k in keys})

    def pose(self, clip, t):
        """-> {bone: (position, orientation, scale)} in skeleton space at a key time t of the clip."""
        tracks = self.clips[clip][1]
        local = {}
        for name in self.order:
            position, orientation, scale = self.bones[name]
            keys = tracks.get(name)
            if keys:
                key = min(keys, key=lambda k: abs(k[0] - t))
                position = add(position, key[1])
                orientation = qmul(orientation, key[2])
                scale = (scale[0] * key[3][0], scale[1] * key[3][1], scale[2] * key[3][2])
            local[name] = (position, orientation, scale)
        world = {}

        def solve(name):
            if name in world:
                return world[name]
            position, orientation, scale = local[name]
            parent = self.parent.get(name)
            if parent is None:
                world[name] = (position, orientation, scale)
            else:
                pp, po, ps = solve(parent)
                world[name] = (add(pp, qrot(po, (position[0] * ps[0], position[1] * ps[1], position[2] * ps[2]))),
                               qmul(po, orientation), (ps[0] * scale[0], ps[1] * scale[1], ps[2] * scale[2]))
            return world[name]

        for name in self.order:
            solve(name)
        return world


def positions(mesh_root):
    """All vertex positions of a mesh XML (shared and submesh geometry)."""
    return [vec(p) for p in mesh_root.iter('position')]


def triangles(mesh_root):
    """Number of triangles of a mesh XML."""
    return sum(1 for _ in mesh_root.iter('face'))


# ================================================================================================ assets
MOUNT = (math.cos(math.radians(-45.0)), math.sin(math.radians(-45.0)), 0.0, 0.0)
broom = convert('CleaningBroom.mesh')
broom_info = {}
if broom is None:
    fail('assets: models/CleaningBroom.mesh is missing (a worker has no broom to clean with)')
else:
    points = positions(broom)
    tris = triangles(broom)
    broom_info['triangles'] = tris
    if tris > 600:
        fail('assets: the broom has %d triangles (at most 600)' % tris)
    zs = [p[2] for p in points]
    broom_length = max(zs) - min(zs)
    # the handle axis: the vertices of the stick (|z| small part above the grip) are centred on x = y = 0
    if abs(broom_length - 1.0) > 0.03:
        fail('assets: the broom is %.3f mesh units long, the clips were authored for 1.0' % broom_length)
    materials = sorted({s.get('material') for s in broom.iter('submesh')})
    if materials != ['CleaningBroom', 'CleaningBroom/Twigs']:
        fail('assets: broom materials are %s' % materials)
    material_text = (ASSETS / 'materials' / 'scripts' / 'CleaningBroom.material').read_text(encoding='utf-8') \
        if (ASSETS / 'materials' / 'scripts' / 'CleaningBroom.material').exists() else ''
    for name in ('CleaningBroom', 'CleaningBroom/Twigs'):
        block = re.search(r'^material ' + re.escape(name) + r'\b[^\n]*\n\{.*?^\}', material_text, re.M | re.S)
        if block is None:
            fail('assets: material %s is not defined' % name)
            continue
        if 'texture CleaningBroom.png' not in block.group(0):
            fail('assets: material %s has no CleaningBroom.png texture' % name)
        if not re.search(r'specular 0(\.0)? 0(\.0)? 0(\.0)?', block.group(0)):
            fail('assets: material %s shines (specular must be 0)' % name)
    texture = ASSETS / 'materials' / 'textures' / 'CleaningBroom.png'
    if not texture.exists():
        fail('assets: materials/textures/CleaningBroom.png is missing')
    else:
        image = Image.open(texture).convert('RGB')
        if image.size != (512, 512):
            fail('assets: CleaningBroom.png is %s, expected 512 x 512' % (image.size,))
        raw = image.tobytes()
        pixels = list(zip(raw[0::3], raw[1::3], raw[2::3]))
        lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
        mean = sum(lum) / len(lum)
        std = math.sqrt(sum((v - mean) ** 2 for v in lum) / len(lum))
        sat = sum((max(p) - min(p)) / max(p) if max(p) > 0 else 0.0 for p in pixels) / len(pixels)
        channel = sorted(max(p) for p in pixels)[int(0.995 * len(pixels))]
        broom_info.update({'texture_mean': round(mean, 1), 'texture_std': round(std, 1), 'texture_sat': round(sat, 3),
                           'texture_p995': channel})
        if not 45.0 <= mean <= 95.0:
            fail('assets: broom texture mean luminance %.1f outside 45-95 (dark dungeon look)' % mean)
        if std < 6.0:
            fail('assets: broom texture luminance std %.1f < 6 (no surface detail)' % std)
        if sat > 0.45:
            fail('assets: broom texture saturation %.2f > 0.45' % sat)
        if channel > 170:
            fail('assets: broom texture p99.5 channel %d > 170 (too bright)' % channel)

rig_info = {}
for rig in ('Kobold', 'Dwarf1'):
    skeleton_root = convert(rig + '.skeleton')
    mesh_root = convert(rig + '.mesh')
    skeleton = Skeleton(skeleton_root)
    if len(skeleton.clips) != CLIP_COUNTS[rig]:
        fail('%s: %d clips, expected %d (no clip may go)' % (rig, len(skeleton.clips), CLIP_COUNTS[rig]))
    if 'Clean' not in skeleton.clips:
        fail('%s: no Clean clip' % rig)
        continue
    if abs(skeleton.clips['Clean'][0] - 1.6) > 1e-4:
        fail('%s: Clean lasts %.3f s, expected 1.6' % (rig, skeleton.clips['Clean'][0]))
    zs = [p[2] for p in positions(mesh_root)]
    height = max(zs) - min(zs)
    scale = BROOM_SHARE * height
    info = {'height': round(height, 4), 'keys': 0, 'on_floor': 0}
    lows, floor_x, left_off, left_along, pick_scale = [], [], [], [], []
    for t in skeleton.key_times('Clean'):
        world = skeleton.pose('Clean', t)
        grip, orientation, _scale = world['Weapon_R']
        tag = qmul(orientation, MOUNT)
        axis = qrot(tag, (0.0, 0.0, 1.0))
        if broom is not None:
            placed = [add(grip, qrot(tag, mul(p, scale))) for p in points]
            low = min(placed, key=lambda p: p[2])
            lows.append(low[2] / height)
            if low[2] <= 0.01 * height:
                floor_x.append(low[0] / height)
        left = sub(world['Weapon_L'][0], grip)
        along = dot(left, axis)
        left_along.append(-along / scale)
        left_off.append(length(sub(left, mul(axis, along))) / height)
        if rig == 'Kobold':
            pick_scale.append(max(world['Pick'][2]))
        info['keys'] += 1
    if broom is not None and lows:
        info.update({'lowest_min': round(min(lows), 4), 'lowest_max': round(max(lows), 4),
                     'on_floor': len(floor_x), 'floor_sweep': round(max(floor_x) - min(floor_x), 3) if floor_x else 0})
        if min(lows) < -0.02:
            fail('%s: the broom goes %.3f x height into the floor' % (rig, -min(lows)))
        if max(lows) > 0.12:
            fail('%s: the broom is lifted %.3f x height off the floor (not sweeping)' % (rig, max(lows)))
        if len(floor_x) < 0.4 * len(lows):
            fail('%s: the twigs touch the floor in %d of %d keys (at least 40 %%)' % (rig, len(floor_x), len(lows)))
        if not floor_x or max(floor_x) - min(floor_x) < 0.30:
            fail('%s: on the floor the twigs travel sideways over %.3f x height (at least 0.30)' %
                 (rig, (max(floor_x) - min(floor_x)) if floor_x else 0.0))
    info.update({'left_off_max': round(max(left_off), 4), 'left_along': [round(min(left_along), 3), round(max(left_along), 3)]})
    if max(left_off) > 0.02:
        fail('%s: the left hand is %.3f x height away from the handle' % (rig, max(left_off)))
    if min(left_along) < 0.15 or max(left_along) > 0.30:
        fail('%s: the left hand holds the handle %.2f-%.2f broom lengths above the right one (0.15-0.30)' %
             (rig, min(left_along), max(left_along)))
    if rig == 'Kobold':
        info['pick_scale_max'] = max(pick_scale)
        if max(pick_scale) > 0.01:
            fail('Kobold: its own pick shows while it sweeps (Pick scale %.3f)' % max(pick_scale))
        for clip in ('Idle', 'Walk', 'Dig', 'Claim'):
            for t in skeleton.key_times(clip)[::5]:
                if abs(max(skeleton.pose(clip, t)['Pick'][2]) - 1.0) > 1e-3:
                    fail('Kobold: the pick is not shown in %s at %.2f s' % (clip, t))
                    break
    rig_info[rig] = info
assets_seconds = time.monotonic() - started
print('ODP_TEST_PHASE ' + json.dumps({'name': 'assets', 'seconds': round(assets_seconds, 3)}))

# ================================================================================================ wiring
render = read('source/render/RenderManager.cpp')
animation = read('source/entities/MovableGameEntity.h')
combat = read('source/render/CreatureCombatReactions.cpp')
search = read('source/creatureaction/CreatureActionSearchDirtToClean.cpp')
targets = read('source/game/WorkerTargets.cpp')
room = read('source/rooms/Room.cpp')
global_cfg = read('config/global.cfg')

if not re.search(r'inline bool holdsBroom\(const std::string& clip\)\s*\{\s*return clip == clean_anim;', animation):
    fail('wiring: EntityAnimation::holdsBroom is not the Clean clip')
if 'const Ogre::Real CLEANING_BROOM_HEIGHT_SHARE = %sf;' % BROOM_SHARE not in render:
    fail('wiring: the broom is not sized to %s x the worker height' % BROOM_SHARE)
update = body(render, 'void RenderManager::updateCreatureCleaningBroom(')
for token, what in (('getWeaponMount(skeleton, "R", CLEANING_BROOM_MESH, mount)', 'the right hand weapon mount'),
                    ('createEntity(broomName, CLEANING_BROOM_MESH)', 'the broom mesh'),
                    ('CLEANING_BROOM_HEIGHT_SHARE * objectEntity->getMesh()->getBounds().getSize().z', 'the size'),
                    ('grip->setInheritScale(false);', 'no rig scale'),
                    ('mSceneManager->getEntity(toolName)->setVisible(!sweeping);', 'the worker tool hidden'),
                    ('removeCreatureCleaningBroom(creature);', 'the broom taken away after sweeping')):
    if token not in update:
        fail('wiring: updateCreatureCleaningBroom lacks ' + what)
state = body(render, 'void RenderManager::rrSetObjectAnimationState(')
if not re.search(r'EntityAnimation::holdsBroom\(anim\) != \(\(previousState != nullptr\) && '
                 r'EntityAnimation::holdsBroom\(previousState->getAnimationName\(\)\)\)\)\)\s*\{\s*'
                 r'updateCreatureCleaningBroom\(dropCreature\);\s*CreatureCombatReactions::showWeaponsForClip\(dropCreature\);',
                 state):
    fail('wiring: rrSetObjectAnimationState does not give or take the broom when the clip changes')
for signature in ('void RenderManager::rrDestroyCreature(', 'void RenderManager::rrPickUpEntity('):
    if 'removeCreatureCleaningBroom(' not in body(render, signature):
        fail('wiring: %s leaves the broom behind' % signature)
visible = body(combat, 'void setWeaponsVisible(')
if 'setVisible(visible && !sweeping)' not in visible or 'EntityAnimation::holdsBroom' not in visible:
    fail('wiring: the weapon models are shown while the worker sweeps')
rule = body(search, 'bool CreatureActionSearchDirtToClean::isFloorDirtToClean(')
if 'TileDirtSync::stageForValue(tile.getDirt())' not in rule or '"CleanTileFromStage"' not in rule:
    fail('wiring: isFloorDirtToClean does not compare the drawn tile stage with CleanTileFromStage')
for text, signature in ((search, 'static Tile* findDirtiestReachableTile('), (search, 'static Tile* findCorridorTile('),
                        (targets, 'void collectCleaningTile('), (targets, 'void collectRooms('),
                        (room, 'bool Room::needsCleaning(')):
    part = body(text, signature)
    if 'isFloorDirtToClean(' not in part:
        fail('wiring: %s does not use isFloorDirtToClean' % signature)
    if 'DirtStage3At' in part or 'CleanRoomFromStage' in part or 'getDirtStage()' in part or 'getDirt() > 0.0' in part:
        fail('wiring: %s still uses an old cleaning limit' % signature)
dirt_block = re.search(r'^\[Dirt\]\s*$(.*?)^\[/Dirt\]', global_cfg, re.M | re.S).group(1)
if not re.search(r'^\s*CleanTileFromStage\s+1\s*$', dirt_block, re.M):
    fail('wiring: global.cfg [Dirt] does not set CleanTileFromStage 1')
if 'CleanRoomFromStage' in global_cfg:
    fail('wiring: the old key CleanRoomFromStage is still in global.cfg')

# ================================================================================================ probe
probe_note = 'skipped (--no-compile)'
if '--no-compile' not in sys.argv:
    values = {}
    for line in dirt_block.splitlines():
        words = line.split()
        if len(words) >= 2 and not words[0].startswith('#'):
            values[words[0]] = words[1]
    config = ',\n'.join('        {"%s", %s}' % (k, v) for k, v in values.items())
    stage = body(read('source/gamemap/TileDirtSync.cpp'), 'int32_t TileDirtSync::stageForValue(')
    needs = body(room, 'bool Room::needsCleaning(')
    source = r'''
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <vector>
static int failures = 0;
static void expect(bool ok, const std::string& what) { if(!ok) { ++failures; std::cout << "FAIL: " << what << std::endl; } }
struct ConfigManager
{
    std::map<std::string, double> values;
    static ConfigManager& getSingleton() { static ConfigManager c; return c; }
    double getDirtConfigDouble(const std::string& key) const
    {
        std::map<std::string, double>::const_iterator it = values.find(key);
        if(it == values.end()) { ++failures; std::cout << "FAIL: unknown key " << key << std::endl; return 0.0; }
        return it->second;
    }
};
struct Tile { double mDirt; double getDirt() const { return mDirt; } };
struct TileDirtSync { static int32_t stageForValue(double dirt); };
@@STAGE@@
struct CreatureActionSearchDirtToClean { static bool isFloorDirtToClean(const Tile& tile); };
@@RULE@@
struct Room
{
    std::vector<Tile*> mCoveredTiles;
    bool mCleanable;
    bool isCleanableByWorkers() const { return mCleanable; }
    bool needsCleaning();
};
@@NEEDS@@
static Room makeRoom(std::vector<Tile>& tiles, bool cleanable)
{
    Room room; room.mCleanable = cleanable;
    for(Tile& tile : tiles) room.mCoveredTiles.push_back(&tile);
    return room;
}
int main()
{
    struct { const char* key; double value; } table[] = {
@@CONFIG@@
    };
    for(unsigned i = 0; i < sizeof(table) / sizeof(table[0]); ++i)
        ConfigManager::getSingleton().values[table[i].key] = table[i].value;
    // corridor and room tiles: invisible dirt stays, every drawn stage is cleaned
    double invisible[] = {0.0, 5.0, 9.99};
    for(double dirt : invisible) { Tile t = {dirt}; expect(!CreatureActionSearchDirtToClean::isFloorDirtToClean(t), "invisible dirt is cleaned"); }
    double visible[] = {10.0, 12.0, 25.0, 33.3333, 50.0, 66.6667, 100.0};
    for(double dirt : visible) { Tile t = {dirt}; expect(CreatureActionSearchDirtToClean::isFloorDirtToClean(t), "a visible stain is not cleaned"); }
    // a 3 x 3 room with one stain of 12 (mean 1.3, far below stage 2) needs cleaning
    std::vector<Tile> one(9, Tile{0.0}); one[4].mDirt = 12.0;
    Room stained = makeRoom(one, true);
    expect(stained.needsCleaning(), "a room with one visible stain is not cleaned");
    // only invisible dirt (all 9.5, mean 9.5): nothing to do
    std::vector<Tile> faint(9, Tile{9.5});
    Room clean = makeRoom(faint, true);
    expect(!clean.needsCleaning(), "a room with invisible dirt only is cleaned");
    // a filthy room workers never clean (prison, torture chamber, crypt)
    std::vector<Tile> filth(9, Tile{80.0});
    Room prison = makeRoom(filth, false);
    expect(!prison.needsCleaning(), "a prison is cleaned");
    std::cout << (failures == 0 ? "probe ok" : "probe failed") << std::endl;
    return failures == 0 ? 0 : 1;
}
'''
    source = (source.replace('@@CONFIG@@', config).replace('@@STAGE@@', stage).replace('@@RULE@@', rule)
              .replace('@@NEEDS@@', needs))
    (work / 'probe.cpp').write_text(source, encoding='utf-8')
    compiled = subprocess.run(['cl', '/nologo', '/EHsc', '/std:c++14', 'probe.cpp', '/Fe:probe.exe'], cwd=str(work),
                              capture_output=True, text=True)
    if compiled.returncode != 0:
        fail('probe: does not compile:\n' + compiled.stdout[-3000:])
    else:
        ran = subprocess.run([str(work / 'probe.exe')], cwd=str(work), capture_output=True, text=True)
        if ran.returncode != 0:
            fail('probe: ' + ran.stdout)
        probe_note = ran.stdout.strip()

print(json.dumps({'broom': broom_info, 'rigs': rig_info, 'probe': probe_note}, indent=1))
print('ODP_TEST_PHASE ' + json.dumps({'name': 'total', 'seconds': round(time.monotonic() - started, 3)}))
if fails:
    for line in fails:
        print('FAIL: ' + line)
    sys.exit(1)
print('cleaning broom k26 ok')
