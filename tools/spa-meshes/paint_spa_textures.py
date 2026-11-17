#!/usr/bin/env python3
"""Paints the surface textures of the pool attendant's chair, life ring, metal parts and hair (K22).

Writes four tileable textures into materials/textures:
- SpaChairWood.png: weathered grey-brown wood with grain running along v, growth rings, knots, cracks and dirt;
- SpaLifebuoy.png: painted canvas of the life ring, light, with weave, paint cracks, chips and grime; the red and white
  materials tint it, so one texture serves both bands;
- SpaMetalWorn.png: worn metal with scratches, pitting and rust spots, light grey; tinted brass for the whistle and dark
  for the iron fittings and the whistle cord;
- SpaAttendantHair.png: hair strands with light and dark streaks along v, light grey-brown; tinted per material for the
  scalp hair, moustache and body hair.

Procedural, deterministic (fixed seeds), original work of the project. Needs numpy and Pillow.

Usage: python paint_spa_textures.py <repository root>
"""

import os
import sys

import numpy as np
from PIL import Image


def periodic_noise(rng, size, cells_x, cells_y):
    """Smooth periodic value noise in [0, 1] with the given number of cells per axis."""
    h, w = size
    grid = rng.random((cells_y, cells_x))
    ys = np.arange(h) * cells_y / h
    xs = np.arange(w) * cells_x / w
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = ys - y0
    fx = xs - x0
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    y1 = (y0 + 1) % cells_y
    x1 = (x0 + 1) % cells_x
    a = grid[np.ix_(y0, x0)]
    b = grid[np.ix_(y0, x1)]
    c = grid[np.ix_(y1, x0)]
    d = grid[np.ix_(y1, x1)]
    top = a + (b - a) * fx[None, :]
    bottom = c + (d - c) * fx[None, :]
    return top + (bottom - top) * fy[:, None]


def fractal(rng, size, cells_x, cells_y, octaves=4):
    """Sum of periodic noise octaves, normalised to [0, 1]."""
    total = np.zeros(size)
    amplitude = 1.0
    norm = 0.0
    for octave in range(octaves):
        total += amplitude * periodic_noise(rng, size, cells_x * 2 ** octave, cells_y * 2 ** octave)
        norm += amplitude
        amplitude *= 0.5
    return total / norm


def save(root, name, rgb):
    """Write an RGB float image as PNG."""
    image = Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')
    image.save(os.path.join(root, 'materials', 'textures', name), optimize=True)


def chair_wood(rng):
    """Weathered wood: grain along v, rings, knots, fine cracks, grey weathering and dirt."""
    size = (512, 512)
    h, w = size
    ys, xs = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    warp = fractal(rng, size, 3, 1, 4) * 0.35 + fractal(rng, size, 8, 2, 3) * 0.08
    rings = np.sin((xs * 26 + warp * 6 + 2.5 * fractal(rng, size, 2, 1, 2)) * 2 * np.pi) * 0.5 + 0.5
    rings = rings ** 3
    fibres = fractal(rng, size, 128, 4, 3)
    tone = 0.55 + 0.25 * fractal(rng, size, 2, 2, 3)
    value = tone * (0.78 + 0.14 * fibres) - 0.16 * rings
    # knots: dark ellipses with rings around them, the grain bends round them
    for _ in range(5):
        cx, cy = rng.random(), rng.random()
        rx, ry = 0.012 + 0.012 * rng.random(), 0.02 + 0.02 * rng.random()
        dx = np.minimum(np.abs(xs - cx), 1 - np.abs(xs - cx)) / rx
        dy = np.minimum(np.abs(ys - cy), 1 - np.abs(ys - cy)) / ry
        r = np.sqrt(dx * dx + dy * dy)
        value -= 0.32 * np.exp(-r * r * 1.5) + 0.06 * np.exp(-((r - 2.2) ** 2) * 2) * (r < 4)
    # long thin cracks along the grain
    cracks = np.zeros(size)
    for _ in range(14):
        x = int(rng.random() * w)
        y0 = int(rng.random() * h)
        length = int(60 + rng.random() * 200)
        for i in range(length):
            y = (y0 + i) % h
            x = (x + (1 if rng.random() < 0.15 else (-1 if rng.random() < 0.15 else 0))) % w
            cracks[y, x] = max(cracks[y, x], 1.0 - i / length * 0.4)
    value -= 0.35 * cracks
    dirt = fractal(rng, size, 4, 4, 4)
    value *= 0.82 + 0.25 * dirt
    grey = 0.35 + 0.3 * fractal(rng, size, 3, 3, 3)
    brown = np.stack([value * 0.95, value * 0.74, value * 0.52], -1)
    weathered = np.stack([value * 0.78, value * 0.74, value * 0.68], -1)
    rgb = brown * (1 - grey[..., None]) + weathered * grey[..., None]
    return rgb


def lifebuoy(rng):
    """Painted canvas: light paint with weave, crack network, chipped spots and grime (tinted by the material)."""
    size = (256, 512)
    h, w = size
    ys, xs = np.mgrid[0:h, 0:w]
    weave = (np.sin(xs * np.pi / 2.0) * np.sin(ys * np.pi / 2.0)) * 0.025
    base = 0.86 + weave + 0.06 * (fractal(rng, size, 16, 8, 3) - 0.5)
    # crack network: thin dark lines where a cellular noise changes its nearest cell
    points = rng.random((90, 2)) * np.array([h, w])
    nearest = np.full(size, 1e9)
    second = np.full(size, 1e9)
    for py, px in points:
        dy = np.minimum(np.abs(ys - py), h - np.abs(ys - py))
        dx = np.minimum(np.abs(xs - px), w - np.abs(xs - px))
        d = np.sqrt(dx * dx + dy * dy)
        second = np.where(d < nearest, nearest, np.minimum(second, d))
        nearest = np.minimum(nearest, d)
    crack = np.clip(1.0 - (second - nearest) / 2.2, 0, 1)
    crack *= fractal(rng, size, 8, 4, 2) > 0.5
    value = base - 0.16 * crack
    # chips: patches where the paint is gone and the grey canvas shows
    chips = fractal(rng, size, 12, 6, 4)
    chip_mask = np.clip((chips - 0.66) * 12, 0, 1)
    canvas = 0.42 + 0.08 * fractal(rng, size, 40, 20, 2)
    value = value * (1 - chip_mask) + canvas * chip_mask
    grime = fractal(rng, size, 4, 2, 4)
    value *= 0.78 + 0.26 * grime
    rgb = np.stack([value, value * 0.97, value * 0.9], -1)
    return rgb


def metal(rng):
    """Worn metal: fine scratches, pitting, rubbed edges and a few rust spots."""
    size = (256, 256)
    h, w = size
    value = 0.66 + 0.12 * (fractal(rng, size, 6, 6, 4) - 0.5)
    for _ in range(260):
        y, x = rng.random() * h, rng.random() * w
        angle = rng.random() * np.pi
        length = 6 + rng.random() * 40
        for i in range(int(length)):
            py = int(y + np.sin(angle) * i) % h
            px = int(x + np.cos(angle) * i) % w
            value[py, px] += 0.12 * (1 if rng.random() < 0.6 else -1)
    pits = rng.random(size) < 0.01
    value[pits] -= 0.3
    rust = np.clip((fractal(rng, size, 8, 8, 4) - 0.68) * 6, 0, 1)
    rgb = np.stack([value, value, value * 0.97], -1)
    rust_colour = np.array([0.45, 0.25, 0.12])
    rgb = rgb * (1 - rust[..., None]) + rust_colour * rust[..., None]
    return rgb


def hair(rng):
    """Hair strands along v: thin light and dark streaks with slow waves."""
    size = (256, 256)
    h, w = size
    ys, xs = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    wave = fractal(rng, size, 2, 4, 3) * 0.12
    strands = np.zeros(size)
    for frequency, weight in ((40, 0.45), (95, 0.35), (170, 0.2)):
        phase = rng.random() * 2 * np.pi
        strands += weight * (np.sin((xs + wave) * frequency * 2 * np.pi + phase) * 0.5 + 0.5)
    clumps = fractal(rng, size, 12, 3, 3)
    value = 0.45 + 0.4 * strands * (0.6 + 0.6 * clumps) - 0.1 * fractal(rng, size, 3, 3, 3)
    grey = np.clip((fractal(rng, size, 24, 6, 2) - 0.62) * 5, 0, 1)
    rgb = np.stack([value, value * 0.9, value * 0.8], -1)
    rgb = rgb * (1 - grey[..., None]) + np.stack([value, value, value], -1) * 1.15 * grey[..., None]
    return rgb


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    save(root, 'SpaChairWood.png', chair_wood(np.random.default_rng(2211)))
    save(root, 'SpaLifebuoy.png', lifebuoy(np.random.default_rng(2212)))
    save(root, 'SpaMetalWorn.png', metal(np.random.default_rng(2213)))
    save(root, 'SpaAttendantHair.png', hair(np.random.default_rng(2214)))


if __name__ == '__main__':
    main()
