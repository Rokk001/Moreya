"""The infirmary reads as an infirmary and its shaman walks facing forward (INGAME-QS-10 K23, owner findings
"komplett texturenlos" and "laeuft rueckwaerts"; INFIRMARY-PLAN 13.1).

Outcome checks on the shipped files (OgreXMLConverter converts the binary meshes and the skeleton):
  textures    every InfirmaryObject*.png that the material script uses is at least 512 x 512 and shows surface detail
              (luminance standard deviation >= 7 and mean absolute 3x3 edge response >= 2.0); today's 12 textures were
              near single-coloured (std 3.5-6.7). Dark dungeon look (STYLE-GUIDE.md): mean saturation <= 0.56, no texel
              brighter than channel 200 (p99.5), mean luminance <= 125.
  mapping     every submesh of the seven furniture meshes and of the shaman maps at least 300 texels per tile onto its
              surface (texture size x sqrt(UV area / surface area)); today's meshes used 38-177 texels of a 256 texture.
  floor       InfirmaryFloor.png is rough dark dungeon stone in the room-floor range of STYLE-GUIDE.md: the room shader
              (Room.frag) shows lighting x texel, so the in-game colour is estimated as texel mean x the per-channel
              factors measured once from the owner's screenshot ODscreenshot_2026-11-17_090817_12 over today's texture
              (3.22, 2.41, 1.38); against the claimed floor of that screenshot (A = Y 102, sat 0.55) the estimate must
              lie at 0.75-1.15 x A and no more saturated than A; the texture itself is neutral to cold stone
              (sat <= 0.25), rough (luminance std >= 9) with dark joints (3-20 % of the texels below Y 15). Today's
              floor is estimated at 1.34 x A, sat 0.67 (the flat orange floor of the screenshot).
  furniture   footprints unchanged (the measured bounds rows of RoomObjectBounds.h, +-0.005), the cots keep wood, straw
              and a grey wool blanket, the blanket is draped (its top varies by >= 25 mm; today 16 mm) and hangs over the side rails
              (at the sides >= 30 mm below the top of the rails);
              each piece at most 20000 triangles.
  shaman      10000 to 36000 triangles; his texture passes the texture limits above and maps at least 300 texels per
              tile; his face (the headfront joint of the rig, in front of the head joint; on the former model the eye
              sockets of the mask above the head joint) lies on the -Y side of the head
              joint (his face lies there), the side the engine turns along the walking direction (RenderManager::rrOrientEntityToward); in the
              Walk clip the foot (the ankle joint LeftFoot / RightFoot) that is off the ground moves along -Y (forward),
              each foot strides >= 0.08 tiles, and each hand swings against the foot of its side
              (correlation <= -0.5). Clip names unchanged, clip lengths as in CLIP_SECONDS (2 s on the former model).
Fixed expected values of this branch (counted once) are the thresholds above.

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
    python source/tests/check_infirmary_look_k23.py [--assets <folder with models/ and materials/textures/>]
"""
from pathlib import Path
import colorsys
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import room_packages  # noqa: E402
import content_packages  # noqa: E402

# The infirmary assets lie in the infirmary room package (scripts/room_packages.py); this check measures only them
INFIRMARY_PACKAGE = room_packages.package(ROOT, 'Infirmary')
ASSETS = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else (INFIRMARY_PACKAGE or ROOT)
#: The shaman figure (mesh, skeleton, material and texture) lies in the creatures content package; with --assets it
#: lies in the given folder
SHAMAN = Path(sys.argv[sys.argv.index('--assets') + 1]) if '--assets' in sys.argv else \
    content_packages.resolve(ROOT, 'models/InfirmaryShaman.mesh').parents[1]
if '--assets' not in sys.argv and INFIRMARY_PACKAGE is None:
    print('infirmary look: not checked, the infirmary room package is not present (the check measures its assets only)')
    sys.exit(0)
FURNITURE = ('InfirmaryCotSmall', 'InfirmaryCotMedium', 'InfirmaryCotLarge', 'MedicineCabinet', 'InstrumentTable',
             'WashBasin', 'HerbShelf')
CLIPS = {'Idle', 'Walk', 'Chant', 'RattleShake', 'HerbSniff', 'PotionTaste', 'TripOverBucket', 'Dance'}
#: The clip lengths of the creatures package shaman (the game stretches the six pose clips to
#: InfirmaryShamanAnimationSeconds). Idle from the build report; RattleShake and HerbSniff are not built yet and get
#: their measured length when they are added.
CLIP_SECONDS = {'Idle': 4.0, 'Walk': 1.04167, 'Chant': 2.25, 'PotionTaste': 8.875, 'TripOverBucket': 2.5, 'Dance': 7.75}
fails = []
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='infirmary_look_'))


def fail(text):
    """Records one failed expectation."""
    fails.append(text)


def convert(name, models=None):
    """Converts a shipped binary mesh or skeleton to Ogre XML and returns its parsed root (from models, else from the
    models folder of ASSETS)."""
    target = work / (name + '.xml')
    source = (models or ASSETS / 'models') / name
    subprocess.run([converter, '-q', '-log', str(target) + '.log', str(source), str(target)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=120, check=True)
    return ET.parse(target).getroot()


def submeshes(root):
    """Returns {material: (positions, uvs, triangles)} of a converted mesh."""
    def geometry(g):
        pos, uv = [], []
        for vb in g.iter('vertexbuffer'):
            for v in vb.iter('vertex'):
                p = v.find('position')
                t = v.find('texcoord')
                if p is not None:
                    pos.append((float(p.get('x')), float(p.get('y')), float(p.get('z'))))
                if t is not None:
                    uv.append((float(t.get('u')), float(t.get('v'))))
        return pos, uv
    shared = root.find('sharedgeometry')
    shared_geometry = geometry(shared) if shared is not None else ([], [])
    out = {}
    for sm in root.iter('submesh'):
        pos, uv = shared_geometry if sm.get('usesharedvertices') == 'true' else geometry(sm.find('geometry'))
        tris = [tuple(int(f.get(k)) for k in ('v1', 'v2', 'v3')) for f in sm.iter('face')]
        out.setdefault(sm.get('material'), []).append((pos, uv, tris))
    return out


def texel_density(parts, size):
    """Texture pixels per tile on the surface: size x sqrt(UV area / surface area)."""
    area3, area2 = 0.0, 0.0
    for pos, uv, tris in parts:
        for a, b, c in tris:
            p, q, r = pos[a], pos[b], pos[c]
            e1 = [q[i] - p[i] for i in range(3)]
            e2 = [r[i] - p[i] for i in range(3)]
            cr = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            area3 += math.sqrt(sum(x * x for x in cr)) / 2
            if uv:
                u, v, w = uv[a], uv[b], uv[c]
                area2 += abs((v[0] - u[0]) * (w[1] - u[1]) - (w[0] - u[0]) * (v[1] - u[1])) / 2
    return size * math.sqrt(area2 / area3) if area3 > 0 else 0.0


material_text = (ASSETS / 'materials/scripts/InfirmaryObjects.material').read_text(encoding='utf-8') \
    if (ASSETS / 'materials/scripts/InfirmaryObjects.material').exists() else \
    (ROOT / 'materials/scripts/InfirmaryObjects.material').read_text(encoding='utf-8')
texture_of = dict(re.findall(r'material\s+(\S+)\s*:[^{]*\{.*?texture\s+(\S+\.png)', material_text, re.S))
if len(texture_of) != 12:
    fail('InfirmaryObjects.material must give each of the 12 materials its texture, found %d' % len(texture_of))
texture_folder = {material: ASSETS / 'materials/textures' for material in texture_of}
# The shaman's own material (one textured material of the creatures package) passes the same texture limits
shaman_material = SHAMAN / 'materials/scripts/Creatures/InfirmaryShamanMeshy.material'
shaman_textures = dict(re.findall(r'^material\s+(\S+)\s*\{.*?texture\s+(\S+\.png)',
                                  shaman_material.read_text(encoding='utf-8'), re.S | re.M)) \
    if shaman_material.exists() else {}
if shaman_textures != {'InfirmaryShamanMeshy': 'InfirmaryShamanMeshy.png'}:
    fail('InfirmaryShamanMeshy.material must give the shaman material its texture, found %s' % shaman_textures)
texture_of.update(shaman_textures)
texture_folder.update({material: SHAMAN / 'materials/textures' for material in shaman_textures})
size_of = {}
for material, texture in sorted(texture_of.items()):
    img = Image.open(texture_folder[material] / texture).convert('RGB')
    size_of[material] = min(img.size)
    lum = img.convert('L')
    std = ImageStat.Stat(lum).stddev[0]
    edge_abs = sum(abs(i - 128) * n for i, n in enumerate(lum.filter(
        ImageFilter.Kernel((3, 3), (-1, -1, -1, -1, 8, -1, -1, -1, -1), 1, 128)).histogram())) / float(img.size[0] * img.size[1])
    mean = ImageStat.Stat(img).mean
    sat = colorsys.rgb_to_hsv(*[m / 255.0 for m in mean])[1]
    small = img.resize((128, 128))
    channel = sorted(max(small.getpixel((x, y))) for x in range(128) for y in range(128))[int(128 * 128 * 0.995)]
    y = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]
    print('%-28s %dx%d std %.1f edge %.2f Y %.0f sat %.2f p99.5 %d' % (texture, img.size[0], img.size[1], std, edge_abs, y,
                                                                    sat, channel))
    if min(img.size) < 512:
        fail('%s is smaller than 512 x 512' % texture)
    if std < 7.0 or edge_abs < 2.0:
        fail('%s shows no surface detail (std %.1f, edge %.2f)' % (texture, std, edge_abs))
    if sat > 0.56 or channel > 200 or y > 125:
        fail('%s is outside the dark dungeon look (sat %.2f, p99.5 channel %d, Y %.0f)' % (texture, sat, channel, y))

FLOOR_FACTORS = (3.22, 2.41, 1.38)
CLAIMED_Y, CLAIMED_SAT = 102.0, 0.55
floor = Image.open(ASSETS / 'materials/textures/InfirmaryFloor.png').convert('RGB')
floor_mean = ImageStat.Stat(floor).mean
game = [min(255.0, floor_mean[i] * FLOOR_FACTORS[i]) for i in range(3)]
game_y = 0.299 * game[0] + 0.587 * game[1] + 0.114 * game[2]
game_sat = colorsys.rgb_to_hsv(*[g / 255.0 for g in game])[1]
floor_sat = colorsys.rgb_to_hsv(*[m / 255.0 for m in floor_mean])[1]
floor_lum = floor.convert('L')
floor_std = ImageStat.Stat(floor_lum).stddev[0]
joints = sum(floor_lum.histogram()[:15]) / float(floor.size[0] * floor.size[1])
print('InfirmaryFloor.png mean %s sat %.2f std %.1f joints %.3f; in game about Y %.0f (%.2f x A) sat %.2f'
      % ([round(m) for m in floor_mean], floor_sat, floor_std, joints, game_y, game_y / CLAIMED_Y, game_sat))
if not 0.75 * CLAIMED_Y <= game_y <= 1.15 * CLAIMED_Y:
    fail('infirmary floor in game about %.2f x the claimed floor (room floors 0.75-1.15)' % (game_y / CLAIMED_Y))
if game_sat > CLAIMED_SAT:
    fail('infirmary floor in game more saturated (%.2f) than the claimed floor (%.2f): orange' % (game_sat, CLAIMED_SAT))
if floor_sat > 0.25 or floor_std < 9.0 or not 0.03 <= joints <= 0.20:
    fail('infirmary floor is no rough dark stone (sat %.2f, std %.1f, dark joints %.3f)' % (floor_sat, floor_std, joints))

bounds = (ROOT / 'source/gamemap/RoomObjectBounds.h').read_text(encoding='utf-8')
for name in FURNITURE:
    meshes = submeshes(convert(name + '.mesh'))
    tris = sum(len(t) for parts in meshes.values() for _, _, t in parts)
    if tris > 20000:
        fail('%s has %d triangles (furniture at most 20000)' % (name, tris))
    pts = [p for parts in meshes.values() for pos, _, t in parts for tri in t for p in (pos[i] for i in tri)]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    row = re.search(r'\{"' + name + r'",\s*([-\d.]+)f,\s*([-\d.]+)f,\s*([-\d.]+)f,\s*([-\d.]+)f', bounds)
    want = [float(row.group(i)) for i in range(1, 5)]
    got = [lo[0], lo[1], hi[0], hi[1]]
    if any(abs(a - b) > 0.005 for a, b in zip(want, got)):
        fail('%s footprint %s differs from its measured bounds %s' % (name, [round(g, 3) for g in got], want))
    for material, parts in meshes.items():
        density = texel_density(parts, size_of.get(material, 0))
        if density < 300:
            fail('%s: %s maps only %.0f texels per tile' % (name, material, density))
    print('%-18s %5d triangles, densities %s' % (name, tris, ', '.join('%s %.0f' % (m[15:], texel_density(p, size_of.get(m, 0)))
                                                                     for m, p in sorted(meshes.items()))))
    if name.startswith('InfirmaryCot'):
        if not {'InfirmaryObjectWood', 'InfirmaryObjectStraw', 'InfirmaryObjectCloth'} <= set(meshes):
            fail('%s lost its wood, straw or blanket' % name)
            continue
        blanket = [pos[i] for pos, _, t in meshes['InfirmaryObjectCloth'] for tri in t for i in tri]
        top = max(p[2] for p in blanket)
        upper = [p for p in blanket if abs(p[0]) < hi[0] * 0.6 and p[2] > top - 0.05]
        relief = max(p[2] for p in upper) - min(p[2] for p in upper)
        wood = [pos[i] for pos, _, t in meshes['InfirmaryObjectWood'] for tri in t for i in tri]
        rail = max(p[2] for p in wood if abs(p[0]) > hi[0] - 0.06 and p[2] < top)
        hanging = min(p[2] for p in blanket if abs(p[0]) > hi[0] - 0.08)
        print('    blanket relief %.3f, lowest blanket at the side %.3f, rail top %.3f' % (relief, hanging, rail))
        if relief < 0.025:
            fail('%s: the blanket lies flat (relief %.3f)' % (name, relief))
        if hanging > rail - 0.03:
            fail('%s: the blanket does not hang over the sides' % name)


def quat(el):
    """Ogre angle/axis rotation as a quaternion (w, x, y, z)."""
    if el is None:
        return (1.0, 0.0, 0.0, 0.0)
    a = float(el.get('angle'))
    ax = el.find('axis')
    v = [float(ax.get(k)) for k in 'xyz']
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    s = math.sin(a / 2)
    return (math.cos(a / 2), v[0] / n * s, v[1] / n * s, v[2] / n * s)


def qmul(a, b):
    """Quaternion product a * b."""
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def qrot(q, v):
    """Rotates v by q."""
    p = qmul(qmul(q, (0.0,) + tuple(v)), (q[0], -q[1], -q[2], -q[3]))
    return p[1:]


def sample(keys, t):
    """Linear key interpolation of (translate, rotate) at time t."""
    if not keys:
        return (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)
    if t <= keys[0][0]:
        return keys[0][1], keys[0][2]
    for (t0, p0, q0), (t1, p1, q1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            if sum(a * b for a, b in zip(q0, q1)) < 0:
                q1 = tuple(-x for x in q1)
            q = tuple(a + (b - a) * f for a, b in zip(q0, q1))
            n = math.sqrt(sum(x * x for x in q))
            return tuple(a + (b - a) * f for a, b in zip(p0, p1)), tuple(x / n for x in q)
    return keys[-1][1], keys[-1][2]


skeleton = convert('InfirmaryShaman.skeleton', SHAMAN / 'models')
bones, parent = {}, {}
for b in skeleton.find('bones'):
    p = b.find('position')
    bones[b.get('name')] = ((float(p.get('x')), float(p.get('y')), float(p.get('z'))), quat(b.find('rotation')))
for bp in skeleton.find('bonehierarchy'):
    parent[bp.get('bone')] = bp.get('parent')
clips = {}
for anim in skeleton.find('animations'):
    tracks = {}
    for tr in anim.find('tracks'):
        keys = []
        for k in tr.find('keyframes'):
            t = k.find('translate')
            keys.append((float(k.get('time')), (float(t.get('x')), float(t.get('y')), float(t.get('z'))) if t is not None
                         else (0.0, 0.0, 0.0), quat(k.find('rotate'))))
        tracks[tr.get('bone')] = keys
    clips[anim.get('name')] = (float(anim.get('length')), tracks)
if set(clips) != CLIPS or any(n not in CLIP_SECONDS or abs(length - CLIP_SECONDS[n]) > 1e-4
                              for n, (length, _) in clips.items()):
    fail('shaman clips changed: %s' % sorted((n, l) for n, (l, _) in clips.items()))


def world(bone, tracks, t, cache):
    """World position and orientation of a bone at time t (Ogre: position = bind + key, orientation = bind * key)."""
    if bone in cache:
        return cache[bone]
    pos, rot = bones[bone]
    kp, kq = sample(tracks.get(bone, []), t) if tracks is not None else ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    local_p = tuple(a + b for a, b in zip(pos, kp))
    local_q = qmul(rot, kq)
    if bone in parent:
        pp, pq = world(parent[bone], tracks, t, cache)
        result = (tuple(a + b for a, b in zip(pp, qrot(pq, local_p))), qmul(pq, local_q))
    else:
        result = (local_p, local_q)
    cache[bone] = result
    return result


def point(bone, offset, tracks, t):
    """World position of a point given in the bone's frame."""
    p, q = world(bone, tracks, t, {})
    return tuple(a + b for a, b in zip(p, qrot(q, offset)))


shaman = submeshes(convert('InfirmaryShaman.mesh', SHAMAN / 'models'))
tris = sum(len(t) for parts in shaman.values() for _, _, t in parts)
print('InfirmaryShaman %d triangles, densities %s' % (tris, ', '.join('%s %.0f' % (m[15:], texel_density(p, size_of.get(m, 0)))
                                                                      for m, p in sorted(shaman.items()))))
if not 10000 <= tris <= 36000:
    fail('shaman has %d triangles (a detailed figure has 10000 to 36000)' % tris)
for material, parts in shaman.items():
    if material not in texture_of:
        fail('shaman material %s has no texture' % material)
    elif texel_density(parts, size_of[material]) < 300:
        fail('shaman %s maps only %.0f texels per tile' % (material, texel_density(parts, size_of[material])))
head = point('Head', (0.0, 0.0, 0.0), None, 0.0)
# The rig's headfront joint marks the face (one textured material: no separate mask material any more)
if 'headfront' not in bones:
    fail('shaman has no face joint (headfront) in front of the head joint')
else:
    face_y = point('headfront', (0.0, 0.0, 0.0), None, 0.0)[1] - head[1]
    print('face joint %.3f tiles from the head joint along y (forward is -y)' % face_y)
    if face_y > -0.02:
        fail('the shaman faces +Y; the engine walks him along -Y, so he walks backwards (face at %+.3f)' % face_y)
length, tracks = clips.get('Walk', (2.0, {}))
steps = 96
for side in ('Left', 'Right'):
    feet = [point(side + 'Foot', (0.0, 0.0, 0.0), tracks, length * i / steps) for i in range(steps + 1)]
    hands = [point(side + 'Hand', (0.0, 0.0, 0.0), tracks, length * i / steps) for i in range(steps + 1)]
    low = min(f[2] for f in feet)
    forward = backward = 0.0
    for a, b in zip(feet, feet[1:]):
        if min(a[2], b[2]) > low + 0.008:
            dy = b[1] - a[1]
            forward += max(0.0, -dy)
            backward += max(0.0, dy)
    stride = max(f[1] for f in feet) - min(f[1] for f in feet)
    fy = [f[1] for f in feet]
    hy = [h[1] for h in hands]
    mf, mh = sum(fy) / len(fy), sum(hy) / len(hy)
    cov = sum((a - mf) * (b - mh) for a, b in zip(fy, hy))
    var = math.sqrt(sum((a - mf) ** 2 for a in fy) * sum((b - mh) ** 2 for b in hy)) or 1.0
    corr = cov / var
    print('Walk %s: lifted foot moves %.3f forward (-y) and %.3f backward, stride %.3f, hand/foot correlation %.2f'
          % (side, forward, backward, stride, corr))
    if forward <= backward * 2 or forward < 0.03:
        fail('Walk: the lifted %s foot does not move forward along -Y (forward %.3f, backward %.3f)' % (side, forward, backward))
    if stride < 0.08:
        fail('Walk: the %s foot strides only %.3f' % (side, stride))
    if corr > -0.5:
        fail('Walk: the %s hand does not swing against its foot (correlation %.2f)' % (side, corr))

if fails:
    print('FAIL')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('infirmary look (K23): ok')
