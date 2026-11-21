#!/usr/bin/env python3
"""Draws the Moreya application icon: the Moreya gate (stone arch with a lowered portcullis in front of
green light) on a dark rounded tile with a bronze rim, so it reads on light and dark backgrounds.

One shape description drives every output:
- dist/hicolor/scalable/apps/moreya.svg (vector source, 256 x 256 units) and meta/gui/moreya.svg (snap copy),
- dist/hicolor/<n>x<n>/apps/moreya.png for 16, 32, 48, 64, 128 and 256 pixels,
- dist/moreya.ico (16, 24, 32, 48, 64, 128 and 256 pixels) for the Windows executable and window.

Small sizes use their own simpler layout (fewer portcullis bars, thicker arch and rim snapped to whole
pixels), so the gate stays clear at 16, 24 and 32 pixels. The raster images are drawn 8 times larger and
reduced, no SVG renderer is needed.

Usage: python tools/artwork/moreya-icon/make_moreya_icon.py [--repo <worktree>] [--preview <png>]
--preview writes a sheet with the 16, 32 and 48 pixel icons on a light and a dark background (also
enlarged 4 times without smoothing) to the given file; it belongs outside the repository.
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

SUPERSAMPLE = 8
PNG_SIZES = (16, 32, 48, 64, 128, 256)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Palette: dark slate tile, bronze rim, pale warm stone, green light of Moreya, near-black iron.
TILE_TOP = (52, 58, 66)
TILE_BOTTOM = (17, 19, 23)
RIM = (201, 150, 66)
STONE_LIGHT = (240, 226, 190)
STONE_SHADE = (190, 160, 104)
KEYSTONE = (255, 244, 214)
GLOW_CENTRE = (150, 255, 140)
GLOW_EDGE = (22, 120, 52)
IRON = (14, 15, 17)
# Radius of the green light around the middle of the threshold, in 256-unit coordinates.
GLOW_REACH = 190


def layout(size):
    """Returns the shape parameters in 256-unit coordinates for an icon of the given pixel size."""
    if size <= 24:
        # 16 px grid: 1 unit = 16 px / 256; values are multiples of 16 units = one pixel at 16 px.
        return {'radius': 48, 'rim': 16, 'left': 32, 'right': 224, 'bottom': 240, 'spring': 112,
                'thickness': 40, 'bars': 2, 'rails': 1, 'bar': 16, 'rail': 16, 'spikes': False, 'keystone': False}
    if size <= 32:
        return {'radius': 44, 'rim': 12, 'left': 32, 'right': 224, 'bottom': 240, 'spring': 112,
                'thickness': 36, 'bars': 3, 'rails': 2, 'bar': 10, 'rail': 10, 'spikes': False, 'keystone': True}
    return {'radius': 40, 'rim': 9, 'left': 36, 'right': 220, 'bottom': 236, 'spring': 112,
            'thickness': 32, 'bars': 4, 'rails': 2, 'bar': 9, 'rail': 9, 'spikes': True, 'keystone': True}


def arch_points(cx, spring, half_width, bottom, steps=96):
    """Outline of an arch: two upright sides from bottom to the springing line and a half circle on top."""
    points = [(cx - half_width, bottom)]
    for i in range(steps + 1):
        angle = math.pi + math.pi * i / steps
        points.append((cx + half_width * math.cos(angle), spring + half_width * math.sin(angle)))
    points.append((cx + half_width, bottom))
    return points


def geometry(size):
    """Returns the shapes of the icon in 256-unit coordinates: tile, arch, opening, bars, rails, spikes, keystone."""
    p = layout(size)
    cx = (p['left'] + p['right']) / 2.0
    outer_half = (p['right'] - p['left']) / 2.0
    inner_half = outer_half - p['thickness']
    shapes = {'layout': p, 'cx': cx}
    shapes['outer'] = arch_points(cx, p['spring'], outer_half, p['bottom'])
    shapes['inner'] = arch_points(cx, p['spring'], inner_half, p['bottom'])
    opening_top = p['spring'] - inner_half
    left = cx - inner_half
    width = 2 * inner_half
    bars = []
    for i in range(p['bars']):
        x = left + width * (i + 1) / (p['bars'] + 1)
        bars.append((x - p['bar'] / 2.0, opening_top, x + p['bar'] / 2.0, p['bottom'] - (8 if p['spikes'] else 0)))
    shapes['bars'] = bars
    rails = []
    for i in range(p['rails']):
        y = p['spring'] + (p['bottom'] - p['spring']) * (i + 1) / (p['rails'] + 1) - (p['bottom'] - p['spring']) * 0.15
        rails.append((left, y - p['rail'] / 2.0, left + width, y + p['rail'] / 2.0))
    shapes['rails'] = rails
    spikes = []
    if p['spikes']:
        for x0, _, x1, y1 in bars:
            mid = (x0 + x1) / 2.0
            spikes.append([(x0, y1), (x1, y1), (mid, y1 + 12)])
    shapes['spikes'] = spikes
    shapes['keystone'] = None
    if p['keystone']:
        top_outer = p['spring'] - outer_half
        top_inner = opening_top
        shapes['keystone'] = [(cx - 14, top_outer + 1), (cx + 14, top_outer + 1), (cx + 9, top_inner + 2), (cx - 9, top_inner + 2)]
    return shapes


def lerp(a, b, t):
    """Mixes two RGB colours."""
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def render(size):
    """Draws the icon at the given pixel size (supersampled, then reduced)."""
    big = size * SUPERSAMPLE
    scale = big / 256.0
    shapes = geometry(size)
    p = shapes['layout']

    def pts(points):
        return [(x * scale, y * scale) for x, y in points]

    def box(rect):
        return [rect[0] * scale, rect[1] * scale, rect[2] * scale - 1, rect[3] * scale - 1]

    image = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    # Tile: rim colour as the outer rounded square, the dark gradient inside it.
    mask = Image.new('L', (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=p['radius'] * scale, fill=255)
    rim = Image.new('RGBA', (big, big), RIM + (255,))
    image.paste(rim, (0, 0), mask)
    inset = p['rim'] * scale
    inner_mask = Image.new('L', (big, big), 0)
    ImageDraw.Draw(inner_mask).rounded_rectangle([inset, inset, big - 1 - inset, big - 1 - inset],
                                                 radius=max(1.0, (p['radius'] - p['rim']) * scale), fill=255)
    gradient = Image.new('RGBA', (big, big))
    draw = ImageDraw.Draw(gradient)
    for y in range(big):
        draw.line([(0, y), (big, y)], fill=lerp(TILE_TOP, TILE_BOTTOM, y / float(big)) + (255,))
    image.paste(gradient, (0, 0), inner_mask)

    # Green light inside the opening: bright low in the middle, darker towards the arch.
    glow = Image.new('RGBA', (big, big), GLOW_EDGE + (255,))
    gdraw = ImageDraw.Draw(glow)
    cx = shapes['cx'] * scale
    cy = p['bottom'] * scale
    reach = GLOW_REACH * scale
    for r in range(int(reach), 0, -max(1, SUPERSAMPLE // 2)):
        t = r / reach
        gdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=lerp(GLOW_CENTRE, GLOW_EDGE, t) + (255,))
    opening_mask = Image.new('L', (big, big), 0)
    ImageDraw.Draw(opening_mask).polygon(pts(shapes['inner']), fill=255)
    image.paste(glow, (0, 0), opening_mask)

    draw = ImageDraw.Draw(image)
    # Portcullis in iron in front of the light.
    for rect in shapes['rails']:
        draw.rectangle(box(rect), fill=IRON + (255,))
    for rect in shapes['bars']:
        draw.rectangle(box(rect), fill=IRON + (255,))
    for spike in shapes['spikes']:
        draw.polygon(pts(spike), fill=IRON + (255,))

    # Stone arch: the outer shape minus the opening, lit from the left.
    arch_mask = Image.new('L', (big, big), 0)
    adraw = ImageDraw.Draw(arch_mask)
    adraw.polygon(pts(shapes['outer']), fill=255)
    adraw.polygon(pts(shapes['inner']), fill=0)
    stone = Image.new('RGBA', (big, big))
    sdraw = ImageDraw.Draw(stone)
    for x in range(big):
        t = max(0.0, min(1.0, (x / float(big) - 0.25) / 0.6))
        sdraw.line([(x, 0), (x, big)], fill=lerp(STONE_LIGHT, STONE_SHADE, t) + (255,))
    image.paste(stone, (0, 0), arch_mask)
    if shapes['keystone']:
        draw.polygon(pts(shapes['keystone']), fill=KEYSTONE + (255,))
    # Clip everything to the tile so nothing leaves the rounded square.
    alpha = image.getchannel('A')
    alpha = Image.composite(alpha, Image.new('L', (big, big), 0), mask)
    image.putalpha(alpha)
    return image.resize((size, size), Image.Resampling.BOX)


def svg_path(points):
    """SVG path data of a closed polygon."""
    return 'M' + ' L'.join('%.2f %.2f' % (x, y) for x, y in points) + ' Z'


def make_svg():
    """Returns the scalable icon (the layout of the large sizes) as SVG text."""
    shapes = geometry(256)
    p = shapes['layout']
    rim = p['rim']
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!-- Moreya application icon: the Moreya gate. Generated by tools/artwork/moreya-icon/make_moreya_icon.py. -->',
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">',
        '  <defs>',
        '    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">',
        '      <stop offset="0" stop-color="#%02x%02x%02x"/>' % TILE_TOP,
        '      <stop offset="1" stop-color="#%02x%02x%02x"/>' % TILE_BOTTOM,
        '    </linearGradient>',
        '    <linearGradient id="stone" x1="0" y1="0" x2="1" y2="0">',
        '      <stop offset="0.25" stop-color="#%02x%02x%02x"/>' % STONE_LIGHT,
        '      <stop offset="0.85" stop-color="#%02x%02x%02x"/>' % STONE_SHADE,
        '    </linearGradient>',
        '    <radialGradient id="glow" gradientUnits="userSpaceOnUse" cx="%.2f" cy="%.2f" r="%d">' % (shapes['cx'], p['bottom'], GLOW_REACH),
        '      <stop offset="0" stop-color="#%02x%02x%02x"/>' % GLOW_CENTRE,
        '      <stop offset="1" stop-color="#%02x%02x%02x"/>' % GLOW_EDGE,
        '    </radialGradient>',
        '  </defs>',
        '  <rect x="0" y="0" width="256" height="256" rx="%d" fill="#%02x%02x%02x"/>' % ((p['radius'],) + RIM),
        '  <rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="url(#tile)"/>' % (rim, rim, 256 - 2 * rim, 256 - 2 * rim, p['radius'] - rim),
        '  <path d="%s" fill="url(#glow)"/>' % svg_path(shapes['inner']),
    ]
    for x0, y0, x1, y1 in shapes['rails'] + shapes['bars']:
        lines.append('  <rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="#%02x%02x%02x"/>' % ((x0, y0, x1 - x0, y1 - y0) + IRON))
    for spike in shapes['spikes']:
        lines.append('  <path d="%s" fill="#%02x%02x%02x"/>' % ((svg_path(spike),) + IRON))
    lines.append('  <path d="%s %s" fill="url(#stone)" fill-rule="evenodd"/>' % (svg_path(shapes['outer']), svg_path(shapes['inner'])))
    if shapes['keystone']:
        lines.append('  <path d="%s" fill="#%02x%02x%02x"/>' % ((svg_path(shapes['keystone']),) + KEYSTONE))
    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def preview(path):
    """Writes the 16, 32 and 48 pixel icons on a light and a dark background, as they are and enlarged."""
    sizes = (16, 32, 48)
    backgrounds = ((245, 245, 245), (32, 32, 32))
    zoom = 4
    margin = 16
    width = margin + sum(s + margin for s in sizes) + sum(s * zoom + margin for s in sizes)
    height = margin + max(sizes) * zoom + margin
    sheet = Image.new('RGB', (width, height * len(backgrounds)))
    for row, colour in enumerate(backgrounds):
        band = Image.new('RGB', (width, height), colour)
        x = margin
        for s in sizes:
            band.paste(render(s), (x, margin), render(s))
            x += s + margin
        for s in sizes:
            icon = render(s)
            band.paste(icon.resize((s * zoom, s * zoom), Image.Resampling.NEAREST), (x, margin),
                       icon.resize((s * zoom, s * zoom), Image.Resampling.NEAREST))
            x += s * zoom + margin
        sheet.paste(band, (0, row * height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def main():
    """Writes the SVG, the PNG sizes and the ICO file into the repository (and the preview when asked)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    repo = args.repo
    svg = make_svg()
    for target in (repo / 'dist/hicolor/scalable/apps/moreya.svg', repo / 'meta/gui/moreya.svg'):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding='utf-8', newline='\n')
    for size in PNG_SIZES:
        target = repo / ('dist/hicolor/%dx%d/apps/moreya.png' % (size, size))
        target.parent.mkdir(parents=True, exist_ok=True)
        render(size).save(target, optimize=True)
    images = [render(size) for size in ICO_SIZES]
    images[-1].save(repo / 'dist/moreya.ico', format='ICO', sizes=[(s, s) for s in ICO_SIZES], append_images=images[:-1])
    if args.preview:
        preview(args.preview)


if __name__ == '__main__':
    main()
