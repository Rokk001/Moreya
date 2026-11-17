#!/usr/bin/env python3
"""Paints the floor dirt decals and the toilet seat texture and writes their material scripts.

    python tools/gen_dirt_decals.py [output folder]

Writes
    materials/textures/DirtStage1.png   256 x 256 RGBA, a few stains
    materials/textures/DirtStage2.png   256 x 256 RGBA, stains with litter (bone chips, scraps, straw)
    materials/textures/DirtStage3.png   256 x 256 RGBA, a dark layer of filth with wet puddles
    materials/textures/ToiletSeat.png   512 x 512 RGB atlas: stone top and sides on the left half, the wooden lid,
                                        plank edges, iron fittings and the inside of the hole on the right half
    materials/scripts/DirtStage.material   materials DirtStage1, DirtStage2, DirtStage3 (alpha blended decals)
    materials/scripts/ToiletSeat.material  material ToiletSeat (opaque)

The decal meshes (models/DirtStage1.mesh ...) cover one tile and use the material of the same name; the seat mesh
(models/ToiletSeat.mesh) maps its faces into the rectangles of SEAT_REGIONS.
The decals fade to nothing at the border, so neighbouring tiles blend without a seam. Original work of the project,
everything is procedural with fixed seeds, so a second run gives byte-identical files. Needs numpy and Pillow.
"""

import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw

from gen_pile_textures import fbm, smoothstep, to_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECAL_SIZE = 256
SEAT_SIZE = 512
SUPER = 2
# Atlas of the toilet seat (pixels, rows from the top): stone top and sides on the left half, wood and iron on the right
SEAT_REGIONS = {'stone_top': (0, 0, 256, 256), 'stone_side': (0, 256, 256, 512), 'lid': (256, 0, 512, 256),
                'wood_edge': (256, 256, 512, 384), 'iron': (256, 384, 384, 512), 'hole': (384, 384, 512, 512)}
# Metres of the seat top covered by the stone top region (256 pixels) and its top-left corner (-x, y)
SEAT_TOP_SPAN = 0.48
SEAT_TOP_EXTENT = (0.24, 0.47)
# Hole of the seat: centre x, centre y, half width, half depth in metres (mesh coordinates, the back is at +y)
SEAT_HOLE = (0.0, 0.20, 0.055, 0.065)
# Height of the seat top in metres
SEAT_HEIGHT = 0.18
# Height of the joint between the base block and the cap slab of the seat
SEAT_CAP_BOTTOM = 0.13
# Metres of height covered by the stone side region (256 pixels); the sides span SEAT_TOP_SPAN horizontally
SEAT_SIDE_SPAN = 0.24

STAIN_RGB = (74, 52, 34)
FILTH_RGB = (38, 30, 24)
PUDDLE_RGB = (72, 70, 56)
LITTER_RGBS = ((222, 214, 190), (150, 120, 78), (196, 168, 104), (110, 92, 70))
STONE_RGB = (84, 78, 70)
GRIME_RGB = (46, 38, 27)
WOOD_RGB = (70, 54, 41)
IRON_RGB = (52, 50, 48)
RUST_RGB = (92, 56, 34)
HOLE_RGB = (16, 13, 10)


def seeded(name):
    """A random state seeded by the texture name."""
    return np.random.RandomState(zlib.crc32(name.encode('ascii')))


def edge_fade(size):
    """Alpha factor that is 1 inside and falls to 0 at the border of the decal (so tiles blend without a seam)."""
    idx = np.arange(size)
    edge = np.minimum(idx, size - 1 - idx).astype(float)
    ramp = smoothstep(2.0, size * 0.16, edge)
    return ramp[:, None] * ramp[None, :]


def stain_alpha(rng, size, threshold, softness):
    """Alpha of blotches: noise above a threshold, with a soft edge."""
    n = fbm(rng, size, 6.0, 3)
    return smoothstep(threshold, threshold + softness, n)


def litter_layer(rng, count):
    """Returns an RGBA float image of small bits (bone chips, scraps, straw) scattered at random places."""
    big = Image.new('RGBA', (DECAL_SIZE * SUPER, DECAL_SIZE * SUPER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    margin = DECAL_SIZE * 0.2
    for _ in range(count):
        cx = rng.uniform(margin, DECAL_SIZE - margin) * SUPER
        cy = rng.uniform(margin, DECAL_SIZE - margin) * SUPER
        ang = rng.uniform(0.0, np.pi)
        length = rng.uniform(5.0, 14.0) * SUPER
        width = rng.uniform(1.6, 3.4) * SUPER
        rgb = LITTER_RGBS[rng.randint(0, len(LITTER_RGBS))]
        dx, dy = np.cos(ang) * length / 2.0, np.sin(ang) * length / 2.0
        draw.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=rgb + (255,), width=int(width))
    small = big.resize((DECAL_SIZE, DECAL_SIZE), Image.BOX)
    return np.asarray(small).astype(float) / 255.0


def paint_stage(stage):
    """Returns the RGBA float image of dirt stage 1, 2 or 3."""
    size = DECAL_SIZE
    rng = seeded('DirtStage%d' % stage)
    fade = edge_fade(size)
    rgb = np.array(STAIN_RGB if stage < 3 else FILTH_RGB) / 255.0
    tone = 0.85 + 0.2 * fbm(rng, size, 14.0, 2)
    col = rgb[None, None, :] * tone[..., None]
    if stage == 1:
        alpha = stain_alpha(rng, size, 1.15, 0.5) * 0.75
    elif stage == 2:
        alpha = np.maximum(stain_alpha(rng, size, 0.55, 0.6) * 0.8, 0.0)
        bits = litter_layer(rng, 46)
        col = col * (1.0 - bits[..., 3:4]) + bits[..., :3] * bits[..., 3:4]
        alpha = np.maximum(alpha, bits[..., 3])
    else:
        alpha = np.clip(0.55 + 0.35 * smoothstep(-0.8, 0.8, fbm(rng, size, 5.0, 3)), 0.0, 1.0)
        puddle = smoothstep(1.0, 1.4, fbm(rng, size, 7.0, 3))
        pud_rgb = np.array(PUDDLE_RGB) / 255.0
        col = col * (1.0 - puddle[..., None]) + pud_rgb[None, None, :] * (0.8 + 0.4 * tone[..., None]) * puddle[..., None]
        alpha = np.maximum(alpha, puddle * 0.9)
    return np.dstack([np.clip(col, 0.0, 1.0), np.clip(alpha * fade, 0.0, 1.0)])


def seat_region(name):
    """Pixel rectangle (x0, y0, x1, y1, rows from the top) of a part of the seat atlas. models/ToiletSeat.mesh maps
    its faces into these rectangles; keep both in step."""
    return SEAT_REGIONS[name]


def stone_blocks(height, width, courses, rng):
    """Rough stone blocks in courses: returns the distance (pixels) of every pixel to the nearest joint and a random
    tone per block. The joints wobble and every course has its own block lengths, so no grid shows."""
    yy = np.arange(height)[:, None].astype(float)
    xx = np.arange(width)[None, :].astype(float)
    wobble = 3.0 * fbm(rng, max(height, width), 9.0, 2)[:height, :width]
    distance = np.full((height, width), 1e9)
    tone = np.zeros((height, width))
    bounds = [0.0] + list(courses) + [float(height)]
    for k in range(len(bounds) - 1):
        top, bottom = bounds[k], bounds[k + 1]
        inside = (yy + wobble >= top) & (yy + wobble < bottom)
        vertical = np.minimum(np.abs(yy + wobble - top), np.abs(yy + wobble - bottom))
        joints = [-rng.uniform(10.0, 60.0)]
        while joints[-1] < width:
            joints.append(joints[-1] + rng.uniform(55.0, 120.0))
        for left, right in zip(joints[:-1], joints[1:]):
            lean = rng.uniform(-0.12, 0.12) * (yy - top)
            cell = inside & (xx + wobble + lean >= left) & (xx + wobble + lean < right)
            across = np.minimum(np.abs(xx + wobble + lean - left), np.abs(xx + wobble + lean - right))
            distance = np.where(cell, np.minimum(vertical, across), distance)
            tone = np.where(cell, rng.uniform(-1.0, 1.0), tone)
    return distance, tone


def paint_stone_top(rng, size):
    """The worn top of the stone seat around the hole: grain, chisel marks, a dark grime ring at the hole and dried
    streaks towards the front edge (rows run from the back of the seat to the front)."""
    stone = np.array(STONE_RGB) / 255.0
    yy = np.arange(size)[:, None].astype(float)
    xx = np.arange(size)[None, :].astype(float)
    grain = fbm(rng, size, 40.0, 2)
    mottle = fbm(rng, size, 5.0, 3)
    tone = 1.0 + 0.11 * mottle + 0.07 * grain
    # chisel marks: short parallel strokes in patches
    strokes = 0.5 + 0.5 * np.sin((xx * 0.9 + yy * 0.35) * 0.55 + 2.0 * fbm(rng, size, 3.0, 1))
    tone -= 0.07 * smoothstep(0.75, 1.0, strokes) * smoothstep(0.0, 1.0, fbm(rng, size, 4.0, 2))
    # distance to the rim of the hole in hole radii
    pixels = size / SEAT_TOP_SPAN
    hole_col = (SEAT_HOLE[0] + SEAT_TOP_EXTENT[0]) * pixels
    hole_row = (SEAT_TOP_EXTENT[1] - SEAT_HOLE[1]) * pixels
    hx = (xx - hole_col) / (SEAT_HOLE[2] * pixels)
    hy = (yy - hole_row) / (SEAT_HOLE[3] * pixels)
    radius = np.sqrt(hx * hx + hy * hy)
    ring = np.exp(-((radius - 1.0) / 0.8) ** 2) * (0.8 + 0.2 * fbm(rng, size, 12.0, 2))
    # dried streaks running from the hole to the front edge
    front = smoothstep(0.0, 1.0, (yy - hole_row) / 40.0)
    streaks = smoothstep(0.6, 1.6, fbm(rng, size, 9.0, 2) + 0.8 * np.exp(-(hx / 2.0) ** 2)) * front * 0.7
    # the front edge where the users step and sit is rubbed a little lighter
    rubbed = smoothstep(150.0, 230.0, yy) * 0.06
    col = stone[None, None, :] * (tone + rubbed)[..., None]
    grime = np.array(GRIME_RGB) / 255.0
    stain = np.clip(0.75 * ring + 0.55 * streaks, 0.0, 0.85)
    col = col * (1.0 - stain[..., None]) + grime[None, None, :] * (0.8 + 0.25 * grain[..., None]) * stain[..., None]
    # hairline cracks
    crack = np.abs(fbm(rng, size, 6.0, 2))
    col *= (1.0 - 0.35 * (crack < 0.035) * smoothstep(0.3, 1.0, fbm(rng, size, 3.0, 1)))[..., None]
    return col


def paint_stone_side(rng, size):
    """The sides of the seat: two courses of rough stone blocks under the cap slab with dark joints, damp and grime at the foot and dark
    runs below the top edge (rows from the top of the region, the floor is at the last row)."""
    stone = np.array(STONE_RGB) / 255.0
    yy = np.arange(size)[:, None].astype(float)
    grain = fbm(rng, size, 40.0, 2)
    mottle = fbm(rng, size, 5.0, 3)

    def row_of(z):
        """Row of the region at the height z (metres above the floor)."""
        return size - z / SEAT_SIDE_SPAN * size

    distance, block_tone = stone_blocks(size, size, [row_of(SEAT_HEIGHT), row_of(SEAT_CAP_BOTTOM), row_of(SEAT_CAP_BOTTOM * 0.5)], rng)
    joints = smoothstep(3.0, 0.5, distance)
    bevel = smoothstep(9.0, 2.0, distance) * 0.18
    tone = (1.0 + 0.10 * mottle + 0.08 * grain + 0.07 * block_tone) * (1.0 - bevel)
    damp = smoothstep(row_of(0.06), row_of(0.0), yy) * (0.55 + 0.25 * fbm(rng, size, 8.0, 2))
    drips = smoothstep(0.9, 1.8, fbm(rng, size, 10.0, 2) + 0.9 * np.cos(np.arange(size)[None, :] / size * 18.0)) \
        * smoothstep(row_of(SEAT_HEIGHT), row_of(SEAT_HEIGHT * 0.4), yy) * 0.5
    col = stone[None, None, :] * (tone * (0.92 - 0.55 * joints))[..., None]
    grime = np.array(GRIME_RGB) / 255.0
    stain = np.clip(damp + drips, 0.0, 0.85)
    col = col * (1.0 - stain[..., None]) + grime[None, None, :] * (0.7 + 0.2 * grain[..., None]) * stain[..., None]
    return col


def paint_lid(rng, width, height):
    """The wooden lid: three dark oak planks with grain, a knot, gaps between the planks and worn, darker edges."""
    wood = np.array(WOOD_RGB) / 255.0
    yy = np.arange(height)[:, None].astype(float)
    xx = np.arange(width)[None, :].astype(float)
    big = max(width, height)
    warp = fbm(rng, big, 3.0, 2)[:height, :width]
    fibres = np.sin((xx / width * 3.0 + 0.04 * yy / height) * np.pi * 2.0 * 9.0 + 6.0 * warp)
    fine = fbm(rng, big, 60.0, 1)[:height, :width]
    plank_width = width / 3.0
    plank = np.floor(xx / plank_width)
    shade = 1.0 + 0.10 * np.sin(plank * 2.3 + 1.0)
    tone = shade * (0.9 + 0.10 * fibres + 0.06 * fine + 0.05 * fbm(rng, big, 6.0, 2)[:height, :width])
    within = xx % plank_width
    gap = np.exp(-(within / 2.5) ** 2) + np.exp(-((within - plank_width) / 2.5) ** 2)
    knot = np.exp(-(((xx - width * 0.62) / 9.0) ** 2 + ((yy - height * 0.35) / 13.0) ** 2))
    edge = np.minimum(np.minimum(xx, width - 1 - xx), np.minimum(yy, height - 1 - yy))
    worn = 1.0 - 0.25 * smoothstep(14.0, 0.0, edge)
    tone = tone * (1.0 - 0.6 * np.clip(gap, 0.0, 1.0)) * (1.0 - 0.45 * knot) * worn
    col = wood[None, None, :] * tone[..., None]
    grime = np.array(GRIME_RGB) / 255.0
    lower = smoothstep(height * 0.55, height, yy) * 0.35 * (0.7 + 0.3 * fbm(rng, big, 7.0, 2)[:height, :width])
    return col * (1.0 - lower[..., None]) + grime[None, None, :] * lower[..., None]


def paint_iron(rng, width, height):
    """Dark forged iron of the bands and hinges with hammer marks and small rust flecks."""
    iron = np.array(IRON_RGB) / 255.0
    big = max(width, height)
    tone = 1.0 + 0.12 * fbm(rng, big, 10.0, 2)[:height, :width] + 0.06 * fbm(rng, big, 40.0, 1)[:height, :width]
    rust = smoothstep(1.3, 1.9, fbm(rng, big, 14.0, 2)[:height, :width])
    col = iron[None, None, :] * tone[..., None]
    rust_rgb = np.array(RUST_RGB) / 255.0
    return col * (1.0 - rust[..., None]) + rust_rgb[None, None, :] * rust[..., None]


def paint_hole(rng, width, height):
    """The inside of the hole: almost black, wet and a little lighter towards the rim (top rows)."""
    hole = np.array(HOLE_RGB) / 255.0
    big = max(width, height)
    tone = 1.0 + 0.25 * fbm(rng, big, 8.0, 2)[:height, :width]
    yy = np.arange(height)[:, None].astype(float)
    top = 1.0 + 0.6 * smoothstep(height * 0.6, 0.0, yy)
    return hole[None, None, :] * (tone * top)[..., None]


def paint_seat():
    """Returns the SEAT_SIZE x SEAT_SIZE RGB float atlas of the seat: stone top and sides on the left half, the wooden
    lid, plank edges, iron fittings and the inside of the hole on the right half (see SEAT_REGIONS)."""
    size = SEAT_SIZE
    rng = seeded('ToiletSeat')
    atlas = np.zeros((size, size, 3))
    x0, y0, x1, y1 = seat_region('stone_top')
    atlas[y0:y1, x0:x1] = paint_stone_top(rng, x1 - x0)
    x0, y0, x1, y1 = seat_region('stone_side')
    atlas[y0:y1, x0:x1] = paint_stone_side(rng, x1 - x0)
    x0, y0, x1, y1 = seat_region('lid')
    atlas[y0:y1, x0:x1] = paint_lid(rng, x1 - x0, y1 - y0)
    x0, y0, x1, y1 = seat_region('wood_edge')
    atlas[y0:y1, x0:x1] = paint_lid(rng, x1 - x0, y1 - y0) * 0.8
    x0, y0, x1, y1 = seat_region('iron')
    atlas[y0:y1, x0:x1] = paint_iron(rng, x1 - x0, y1 - y0)
    x0, y0, x1, y1 = seat_region('hole')
    atlas[y0:y1, x0:x1] = paint_hole(rng, x1 - x0, y1 - y0)
    return np.clip(atlas, 0.0, 1.0)


def decal_material(name):
    """Material text of one alpha blended decal."""
    return '\n'.join([
        'material %s' % name,
        '{',
        '    receive_shadows on',
        '',
        '    technique',
        '    {',
        '        pass',
        '        {',
        '            ambient 0.8 0.8 0.8 1.0',
        '            diffuse 0.7 0.7 0.7 1.0',
        '            specular 0.0 0.0 0.0 1.0 12.5',
        '            scene_blend alpha_blend',
        '            depth_write off',
        '            depth_bias 1',
        '            cull_hardware none',
        '',
        '            texture_unit',
        '            {',
        '                texture %s.png' % name,
        '                tex_address_mode clamp',
        '                filtering trilinear',
        '            }',
        '        }',
        '    }',
        '}',
        ''])


def seat_material():
    """Material text of the toilet seat (opaque, stone and wood in one texture)."""
    return '\n'.join([
        'material ToiletSeat',
        '{',
        '    receive_shadows on',
        '',
        '    technique',
        '    {',
        '        pass',
        '        {',
        '            ambient 0.8 0.8 0.8 1.0',
        '            diffuse 0.75 0.75 0.75 1.0',
        '            specular 0.05 0.05 0.05 1.0 12.5',
        '',
        '            texture_unit',
        '            {',
        '                texture ToiletSeat.png',
        '                tex_address_mode clamp',
        '                filtering trilinear',
        '            }',
        '        }',
        '    }',
        '}',
        ''])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else os.path.join(ROOT, 'materials', 'textures')
    scripts = os.path.join(ROOT, 'materials', 'scripts')
    texts = ['// Floor dirt decals, one per stage (textures made by tools/gen_dirt_decals.py)', '']
    for stage in (1, 2, 3):
        to_image(paint_stage(stage)).save(os.path.join(out, 'DirtStage%d.png' % stage), optimize=True)
        texts.append(decal_material('DirtStage%d' % stage))
    with open(os.path.join(scripts, 'DirtStage.material'), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(texts))
    to_image(paint_seat()).save(os.path.join(out, 'ToiletSeat.png'), optimize=True)
    with open(os.path.join(scripts, 'ToiletSeat.material'), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('// Toilet seat: one atlas, stone on the left half of the UV space, wooden lid, iron and the hole on the right half\n')
        handle.write(seat_material())
    print('wrote DirtStage1-3.png, ToiletSeat.png and their materials')
    return 0


if __name__ == '__main__':
    sys.exit(main())
