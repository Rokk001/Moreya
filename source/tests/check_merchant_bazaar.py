"""Merchant room as a bazaar (INGAME-QS-10 K21, EQUIPMENT-POTIONS-PLAN 15.3 and 6.1). Owner finding of 2026-11-17: the room
looked like a mix of a slaughterhouse and a library: dark red blotches on the floor planks and on a grey table cloth, a
skull on the table, books and skulls on the shelves; cloth strips, carpets, lanterns and spice sacks were missing.
Owner finding of 2026-11-17 on the first bazaar (A2): "viel zu sauber, grell und farbenfroh". The bazaar elements stay, in
the dark dungeon look of the style guide: dull dyes close to brown-grey, grime, dim warm lanterns. The dye families below
are therefore recognised by hue and HSV saturation (dull dyes), no longer by a strong channel spread.

One check per point, on the shipped files (meshes through OgreXMLConverter, textures sampled at the mesh UVs):
  floor carpets      MerchantFloor.png shows worn planks with carpet remnants: 8 to 45 % of the pixels are dyed carpet,
                     in at least three dye families (red, blue, yellow-ochre)
  no blood stains    floor and table cloth: every 64 px block that is mostly red also holds at least 2 % pattern pixels
                     of a woven carpet (another dye or a light thread); a lone red blotch on planks or linen (the old look)
                     fails
  table cloth        the table cloth texture shows at least three dye families
  carpet under table SalesTable has a carpet (MerchantCarpet) on the floor covering at least 90 % of its footprint
  goods on the table the cloth top lies at 0.69 to 0.712 (the goods are placed at 0.712) over the whole goods strip
                     (|x| <= 0.13, |y| <= 0.31, and the same turned by 90 degrees for the wall-side table), and nothing
                     of the table rises above the top inside that strip
  cloth strips       MerchantShelf has at least 5 separate cloth strips (MerchantClothStrip) hanging from above 1.35 at
                     the top of the wall, in at least three colours sampled from the texture
  lanterns           shelf and table carry at least 3 lanterns (pieces of MerchantLantern) with self-lit glass in at
                     least three colours
  spice sacks        MerchantShelf has at least 2 sacks standing on the floor (MerchantSack) with spice heaps in at
                     least three colours
  no skull           the furniture shows no bone-coloured surface (pale yellowed white, as the skulls) larger than
                     0.01 m2
                     and no flat material other than the dark iron
  dark dungeon look  (style guide, anchor A = claimed floor RGB 56,48,36, luminance 49.0; luminance Y = 0.299 R + 0.587 G
                     + 0.114 B, saturation = mean HSV saturation of the texels)
                     floor texture: mean Y 36.8-56.4 (room floors 0.75-1.15 A), mean saturation 0.10-0.45 (room
                     floors up to 0.40, wood up to 0.45), 99.9 % of the texels with no channel above 170 (no near-white)
                     object textures (table and shelf wood, table cloth, wares atlas): mean Y 49.0-98.0 (objects at least
                     A, at most 2.0 A), mean saturation at most 0.45 (no surface class above 0.45, wood at most 0.45)
                     lantern glass (a glow accent): mean Y at most 78.4 (1.6 A), every pane warm (hue of the pane mean
                     0-60 or 290-360 degrees, no green or blue glass), emissive at most 0.5 and warm (red >= green >=
                     blue); A2 had bright red/amber/green/blue glass with a white emissive 0.75

Call (from the repository root; set OGRE_XML_CONVERTER to the full path of OgreXMLConverter.exe):
  python source/tests/check_merchant_bazaar.py
"""
from pathlib import Path
import colorsys
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
# Largest bone-white surface (m2) a furniture piece may show; a skull of 0.15 m has about 0.07
BONE_MAX_AREA = 0.01
START = time.monotonic()
TEXTURES = ROOT / 'materials' / 'textures'
MATERIALS = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (ROOT / 'materials' / 'scripts').glob('*.material'))
fails = []


def material_block(name):
    m = re.search(r'^material ' + re.escape(name) + r'\b.*?^}', MATERIALS, re.M | re.S)
    assert m, 'material ' + name + ' missing'
    return m.group(0)


def material_texture(name):
    m = re.search(r'^\s*texture\s+(\S+\.png)', material_block(name), re.M)
    return m.group(1) if m else None


# Dull dyes (style guide: muted, close to brown-grey): least HSV saturation of a dyed pixel per family, and the least
# channel spread (0..255) below which a pixel is grey, soot or dust. The weathered planks and the brown wood are orange-brown
# (hue 15-34 degrees) and never count as a dye.
DYE_MIN_SPREAD = 12
DYE_MIN_SAT = {'red': 0.30, 'ochre': 0.40, 'green': 0.20, 'blue': 0.18, 'purple': 0.18}


def family(rgb):
    """Dye family of a dyed pixel: red (madder), ochre, green, blue (indigo), purple (plum); None for wood, linen, stone,
    grime, soot, dust or dark lines."""
    spread = max(rgb) - min(rgb)
    if spread < DYE_MIN_SPREAD:
        return None
    h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in rgb])
    deg = h * 360
    if deg < 15 or deg >= 335:
        f = 'red'
    elif deg < 34:
        return None
    elif deg < 60:
        f = 'ochre'
    elif deg < 170:
        f = 'green'
    elif deg < 190:
        return None
    elif deg < 265:
        f = 'blue'
    else:
        f = 'purple'
    return f if s >= DYE_MIN_SAT[f] else None


def texture_families(img, threshold):
    """Dye families that cover at least threshold of the pixels, and the share of dyed pixels."""
    px = list(img.convert('RGB').get_flattened_data())
    counts = {}
    for p in px:
        f = family(p)
        if f is not None:
            counts[f] = counts.get(f, 0) + 1
    return {f for f, c in counts.items() if c >= threshold * len(px)}, sum(counts.values()) / float(len(px))


def is_red_stain(rgb):
    """A red pixel as the old blood blotches had them (also dark ones): red clearly above green and blue."""
    r, g, b = rgb
    return r - max(g, b) >= 40 and r >= 1.8 * max(g, b, 1)


def is_pattern(rgb):
    """A pixel of the pattern of a woven carpet: a dye other than red, or a light warm cream thread (not grey linen)."""
    f = family(rgb)
    return (f is not None and f != 'red') or (sum(rgb) / 3.0 > 115 and max(rgb) - min(rgb) < 120 and rgb[0] - rgb[2] >= 30)


def lone_red_blocks(img, block=64):
    """Blocks of mostly red pixels without the pattern dyes or threads of a woven carpet."""
    img = img.convert('RGB')
    w, h = img.size
    bad = 0
    for by in range(0, h, block):
        for bx in range(0, w, block):
            px = list(img.crop((bx, by, bx + block, by + block)).get_flattened_data())
            red = sum(1 for p in px if is_red_stain(p)) / float(len(px))
            pattern = sum(1 for p in px if is_pattern(p)) / float(len(px))
            if red >= 0.30 and pattern < 0.02:
                bad += 1
    return bad


converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
work = Path(tempfile.mkdtemp(prefix='merchant_bazaar_'))


def mesh(name):
    """Returns {material: [triangles of ((x, y, z), (u, v)) corners]} of a shipped mesh."""
    target = work / (name + '.mesh.xml')
    subprocess.run([converter, '-q', '-log', str(target) + '.log', str(ROOT / 'models' / (name + '.mesh')), str(target)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=120, check=True)
    tree = ET.parse(target).getroot()

    def corners(geometry):
        pos, uv = [], []
        for vb in geometry.iter('vertexbuffer'):
            for v in vb.iter('vertex'):
                p = v.find('position')
                t = v.find('texcoord')
                if p is not None:
                    pos.append((float(p.get('x')), float(p.get('y')), float(p.get('z'))))
                if t is not None:
                    uv.append((float(t.get('u')), float(t.get('v'))))
        return pos, uv
    shared = tree.find('sharedgeometry')
    shared_corners = corners(shared) if shared is not None else ([], [])
    out = {}
    for sm in tree.iter('submesh'):
        pos, uv = shared_corners if sm.get('usesharedvertices') == 'true' else corners(sm.find('geometry'))
        tris = out.setdefault(sm.get('material'), [])
        for f in sm.iter('face'):
            idx = [int(f.get(k)) for k in ('v1', 'v2', 'v3')]
            tris.append([(pos[i], uv[i] if i < len(uv) else (0.0, 0.0)) for i in idx])
    return out


def pieces(tris):
    """Connected pieces (lists of positions) of triangles; corners at the same position are joined."""
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for tri in tris:
        keys = [tuple(round(c, 4) for c in p) for p, _ in tri]
        for k in keys:
            parent.setdefault(k, k)
        for k in keys[1:]:
            ra, rb = find(keys[0]), find(k)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)
    return list(groups.values())


images = {}


BARYCENTRIC = ((1 / 3.0, 1 / 3.0), (0.6, 0.2), (0.2, 0.6), (0.2, 0.2), (0.45, 0.45), (0.1, 0.45), (0.45, 0.1))


def samples(material, tri):
    """Texture colours at seven points inside a triangle's UVs (one point could hit a thin line of the pattern)."""
    tex = material_texture(material)
    if tex not in images:
        images[tex] = Image.open(TEXTURES / tex).convert('RGB')
    img = images[tex]
    out = []
    for a, b in BARYCENTRIC:
        u = (tri[0][1][0] * (1 - a - b) + tri[1][1][0] * a + tri[2][1][0] * b) % 1.0
        v = (tri[0][1][1] * (1 - a - b) + tri[1][1][1] * a + tri[2][1][1] * b) % 1.0
        out.append(img.getpixel((min(img.width - 1, int(u * img.width)), min(img.height - 1, int(v * img.height)))))
    return out


def sample(material, tri):
    """Mean texture colour inside a triangle."""
    px = samples(material, tri)
    return tuple(sum(p[i] for p in px) / float(len(px)) for i in range(3))


def tri_family(material, tri):
    """The most common dye family of the samples inside a triangle, or None."""
    votes = {}
    for p in samples(material, tri):
        f = family(p)
        if f is not None:
            votes[f] = votes.get(f, 0) + 1
    return max(votes, key=votes.get) if votes else None


def piece_families(material, tris, piece_list):
    """Dye family of each piece (the most common family of its triangle samples)."""
    owner = {}
    for i, piece in enumerate(piece_list):
        for k in piece:
            owner[k] = i
    votes = {}
    for tri in tris:
        i = owner[tuple(round(c, 4) for c in tri[0][0])]
        f = tri_family(material, tri)
        if f is not None:
            votes.setdefault(i, {}).setdefault(f, 0)
            votes[i][f] += 1
    return {i: max(v, key=v.get) for i, v in votes.items()}


def is_bone(rgb):
    """Pale yellowed bone (the skulls of the old table and shelf, 162/143/109): light, with little colour; burlap, cream
    threads and pots are more saturated or darker."""
    r, g, b = rgb
    light = (max(rgb) + min(rgb)) / 2.0
    return light >= 125 and max(rgb) - min(rgb) <= 60


def area(tri):
    (a, _), (b, _), (c, _) = tri
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    cr = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
    return 0.5 * sum(x * x for x in cr) ** 0.5


# Floor and table cloth textures
floor = Image.open(TEXTURES / 'MerchantFloor.png')
floor_families, floor_dyed = texture_families(floor, 0.01)
if not 0.08 <= floor_dyed <= 0.45:
    fails.append('floor carpets: %.0f %% of the floor is dyed carpet (8-45 %% wanted: planks with carpet remnants)' % (100 * floor_dyed))
if not {'red', 'blue', 'ochre'} <= floor_families:
    fails.append('floor carpets: the carpet remnants need red, blue and ochre dyes, found %s' % sorted(floor_families))
cloth = Image.open(TEXTURES / material_texture('MerchantTableCloth'))
cloth_families, _ = texture_families(cloth, 0.02)
if len(cloth_families) < 3:
    fails.append('table cloth: at least three dye families wanted, found %s' % sorted(cloth_families))
for name, img in (('floor', floor), ('table cloth', cloth)):
    bad = lone_red_blocks(img)
    if bad:
        fails.append('no blood stains: %d red blotches on the %s without a carpet pattern' % (bad, name))

table = mesh('SalesTable')
shelf = mesh('MerchantShelf')

# Carpet under the table
rug_top = [t for t in table.get('MerchantCarpet', []) if all(0.004 < c[0][2] < 0.02 for c in t)]
footprint = 0.77 * 0.72
rug_area = sum(area(t) for t in rug_top)
if rug_area < 0.9 * footprint:
    fails.append('carpet under table: the carpet covers %.2f of %.2f m2 on the floor' % (rug_area, footprint))

# Goods strip on the table top
cloth_tris = table.get('MerchantTableCloth', [])


def cloth_height(x, y):
    """Height of the highest cloth triangle whose outline holds the point x, y, or None."""
    best = None
    for t in cloth_tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = [c[0] for c in t]
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            continue
        l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
        l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
        l3 = 1.0 - l1 - l2
        if min(l1, l2, l3) >= -1e-6:
            z = l1 * az + l2 * bz + l3 * cz
            best = z if best is None else max(best, z)
    return best


for turned in (False, True):
    def in_strip(p):
        x, y = (p[1], p[0]) if turned else (p[0], p[1])
        return abs(x) <= 0.13 and abs(y) <= 0.31
    above = [p for tris in table.values() for t in tris for p, _ in t if in_strip(p) and 0.713 < p[2] < 1.0]
    if above:
        fails.append('goods on the table: %d vertices stand in the goods strip above the top (turned %s)' % (len(above), turned))
    for gx in (-0.1, 0.0, 0.1):
        for gy in (-0.29, -0.21, 0.0, 0.21, 0.29):
            x, y = (gy, gx) if turned else (gx, gy)
            z = cloth_height(x, y)
            if z is None or not 0.69 <= z <= 0.712:
                fails.append('goods on the table: no cloth top at 0.69-0.712 under the goods place %.2f %.2f (%s)' % (x, y, z))

# Cloth strips at the top of the wall
strips = shelf.get('MerchantClothStrip', [])
hanging = [p for p in pieces(strips) if max(k[2] for k in p) > 1.35 and max(k[2] for k in p) - min(k[2] for k in p) > 0.12]
if len(hanging) < 5:
    fails.append('cloth strips: %d strips hang under the top of the shelf (at least 5)' % len(hanging))
high_tris = [t for t in strips if min(c[0][2] for c in t) > 1.1]
strip_families = set(piece_families('MerchantClothStrip', high_tris, pieces(high_tris)).values())
if len(strip_families) < 3:
    fails.append('cloth strips: at least three colours wanted, found %s' % sorted(strip_families))

# Coloured lanterns
lantern_families = set()
lantern_count = 0
for furniture in (table, shelf):
    tris = furniture.get('MerchantLantern', [])
    found = [p for p in pieces(tris)]
    lantern_count += len([p for p in found if max(k[2] for k in p) > 0.9])
    lantern_families |= set(piece_families('MerchantLantern', tris, found).values())
    lantern_families |= {tri_family('MerchantLantern', t) for t in tris} - {None}
emissive = re.search(r'^\s*emissive\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', material_block('MerchantLantern'), re.M)
if not emissive or max(float(x) for x in emissive.groups()) < 0.4:
    fails.append('lanterns: the lantern glass is not self-lit')
if lantern_count < 3:
    fails.append('lanterns: %d lantern glass pieces above 0.9 (at least 3)' % lantern_count)
if len(lantern_families) < 3:
    fails.append('lanterns: at least three glass colours wanted, found %s' % sorted(lantern_families))

# Spice sacks
sack_tris = shelf.get('MerchantSack', [])
sacks = [p for p in pieces(sack_tris) if min(k[2] for k in p) < 0.01 and max(k[2] for k in p) > 0.15]
if len(sacks) < 2:
    fails.append('spice sacks: %d sacks stand on the floor at the shelf (at least 2)' % len(sacks))
heaps = [t for t in sack_tris if min(c[0][2] for c in t) > 0.18]
spice_families = {tri_family('MerchantSack', t) for t in heaps} - {None}
if len(spice_families) < 3:
    fails.append('spice sacks: at least three spice colours wanted, found %s' % sorted(spice_families))

# No skull, no books: no bone-white surfaces, only textured materials besides the dark iron
for name, furniture in (('SalesTable', table), ('MerchantShelf', shelf)):
    total = 0.0
    bone = 0.0
    for material, tris in furniture.items():
        if material_texture(material) is None:
            if material != 'ItemIron':
                fails.append('no skull: %s uses the flat material %s' % (name, material))
            continue
        for t in tris:
            a = area(t)
            total += a
            if material != 'MerchantLantern' and is_bone(sample(material, t)):
                bone += a
    print('%s bone-white area %.4f m2 of %.3f' % (name, bone, total))
    if bone > BONE_MAX_AREA:
        fails.append('no skull: %.4f m2 of %s is bone-white (a skull or bone, at most %.3f)' % (bone, name, BONE_MAX_AREA))

# Dark dungeon look (style guide ranges, see the header)
ANCHOR_Y = 0.299 * 56 + 0.587 * 48 + 0.114 * 36
FLOOR_Y = (0.75 * ANCHOR_Y, 1.15 * ANCHOR_Y)
FLOOR_SAT = (0.10, 0.45)
FLOOR_MAX_CHANNEL = 170
OBJECT_Y = (1.0 * ANCHOR_Y, 2.0 * ANCHOR_Y)
OBJECT_MAX_SAT = 0.45
GLOW_MAX_Y = 1.6 * ANCHOR_Y
EMISSIVE_MAX = 0.5


def texel_stats(img):
    """Mean luminance, mean HSV saturation and the 99.9 % percentile of the strongest channel of a texture."""
    px = list(img.convert('RGB').get_flattened_data())
    lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)
    sat = sum((max(p) - min(p)) / float(max(p)) if max(p) else 0.0 for p in px) / len(px)
    top = sorted(max(p) for p in px)[int(0.999 * (len(px) - 1))]
    return lum, sat, top


lum, sat, top = texel_stats(floor)
print('MerchantFloor.png Y %.1f sat %.2f channel p99.9 %d' % (lum, sat, top))
if not FLOOR_Y[0] <= lum <= FLOOR_Y[1]:
    fails.append('dark look: floor mean luminance %.1f outside %.1f-%.1f' % (lum, FLOOR_Y[0], FLOOR_Y[1]))
if not FLOOR_SAT[0] <= sat <= FLOOR_SAT[1]:
    fails.append('dark look: floor mean saturation %.2f outside %.2f-%.2f' % (sat, FLOOR_SAT[0], FLOOR_SAT[1]))
if top > FLOOR_MAX_CHANNEL:
    fails.append('dark look: floor has near-white or glaring texels (channel %d above %d)' % (top, FLOOR_MAX_CHANNEL))
for material in ('MerchantTableWood', 'MerchantTableCloth', 'MerchantWares'):
    tex = material_texture(material)
    lum, sat, _ = texel_stats(Image.open(TEXTURES / tex))
    print('%s Y %.1f sat %.2f' % (tex, lum, sat))
    if not OBJECT_Y[0] <= lum <= OBJECT_Y[1]:
        fails.append('dark look: %s mean luminance %.1f outside %.1f-%.1f' % (tex, lum, OBJECT_Y[0], OBJECT_Y[1]))
    if sat > OBJECT_MAX_SAT:
        fails.append('dark look: %s mean saturation %.2f above %.2f (garish colours)' % (tex, sat, OBJECT_MAX_SAT))
glass = Image.open(TEXTURES / material_texture('MerchantLantern')).convert('RGB')
lum, sat, _ = texel_stats(glass)
print('%s Y %.1f sat %.2f' % (material_texture('MerchantLantern'), lum, sat))
if lum > GLOW_MAX_Y:
    fails.append('dark look: lantern glass mean luminance %.1f above %.1f (glow accent at most 1.6 A)' % (lum, GLOW_MAX_Y))
half = glass.width // 2
for cy in range(2):
    for cx in range(2):
        pane = list(glass.crop((cx * half, cy * half, (cx + 1) * half, (cy + 1) * half)).get_flattened_data())
        mean = [sum(p[i] for p in pane) / float(len(pane)) for i in range(3)]
        deg = colorsys.rgb_to_hsv(*[c / 255.0 for c in mean])[0] * 360
        if 60 < deg < 290:
            fails.append('dark look: lantern pane %d,%d is green or blue glass (hue %.0f)' % (cx, cy, deg))
if emissive:
    em = [float(x) for x in emissive.groups()]
    if max(em) > EMISSIVE_MAX or not em[0] >= em[1] >= em[2]:
        fails.append('dark look: lantern emissive %s is not a dim warm glow (at most %.1f, red >= green >= blue)' % (em, EMISSIVE_MAX))

print('ODP_TEST_PHASE {"name": "bazaar checks", "seconds": %.3f}' % (time.monotonic() - START))
if fails:
    print('FAIL')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('OK check_merchant_bazaar')
