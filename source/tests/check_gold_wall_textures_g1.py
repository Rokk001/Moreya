#!/usr/bin/env python3
"""T-G1: the gold wall textures Gold.png, Gold50.png and Gold150.png show dark rock with gold ore in the style guide
gold ore colour (about 150,120,30), not saturated yellow, and the three densities differ in their ore share.
Fixed expected values; the ore pixels are measured in the committed textures."""
import pathlib
import sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEXTURES = ROOT / 'materials' / 'textures'
ORE_TARGET = np.array([150.0, 120.0, 30.0])
ORE_COLOUR_TOLERANCE = 25.0       # per channel, mean of the ore pixels
ORE_MAX_CHANNEL = 220             # no ore pixel brighter than this (no acid yellow)
ORE_SAT_RANGE = (0.60, 0.88)      # style guide gold saturation 0.6-0.85, a little slack
ROCK_MAX_LUMINANCE = 70.0         # the rock stays dark
SHARE_STEP = 0.05                 # each density has at least this much more ore than the next lower one
ORE_SHARE_RANGES = {'Gold50': (0.08, 0.18), 'Gold': (0.20, 0.32), 'Gold150': (0.30, 0.45)}

shares = {}
for name in ('Gold50', 'Gold', 'Gold150'):
    img = np.asarray(Image.open(TEXTURES / (name + '.png')).convert('RGB'), dtype=float)
    # ore pixels: clearly warmer than the neutral rock (red minus blue), the same test the gold shader uses
    ore = (img[..., 0] - img[..., 2]) > 0.28 * 255.0 * 0.5
    share = float(ore.mean())
    shares[name] = share
    assert ORE_SHARE_RANGES[name][0] <= share <= ORE_SHARE_RANGES[name][1], (name, share)
    pixels = img[ore]
    mean = pixels.mean(0)
    assert np.all(np.abs(mean - ORE_TARGET) <= ORE_COLOUR_TOLERANCE), (name, mean)
    assert pixels.max() <= ORE_MAX_CHANNEL, (name, pixels.max())
    mx, mn = pixels.max(1), pixels.min(1)
    sat = (mx - mn) / np.maximum(mx, 1)
    assert ORE_SAT_RANGE[0] <= sat.mean() <= ORE_SAT_RANGE[1], (name, sat.mean())
    rock = img[~ore]
    assert (rock @ [0.299, 0.587, 0.114]).mean() <= ROCK_MAX_LUMINANCE, name
assert shares['Gold'] - shares['Gold50'] >= SHARE_STEP, shares
assert shares['Gold150'] - shares['Gold'] >= SHARE_STEP, shares
print('check_gold_wall_textures_g1 OK', {k: round(v, 3) for k, v in shares.items()})
