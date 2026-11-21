#!/usr/bin/env python3
"""Age the wood of the start screen "Lords of the Deep" signpost so it matches the worn courtyard.

The courtyard of the main menu is old, cracked and sooty; the signpost wood of tools/blender-assets/moreya_raid_models.py
is a clean dark brown. This module bleaches and greys that wood, adds grime, water stains and soot, splits along the
grain, end checks and chipped edges, and puts the same cracks into the tangent-space normal map. It is used twice:

- run directly, it writes the weathered post wood from the plain post wood (tileable, the cracks wrap around):

      materials/textures/menu/MenuSignpostWeatheredWood.png        from MenuSignpostWood.png
      materials/textures/menu/MenuSignpostWeatheredWoodNormal.png  from MenuSignpostWoodNormal.png

- tools/gen_menu_signpost_lettering.py imports weather_board() and crack_board() to age the board planks before and
  after it carves the subtitle into them.

The plain textures stay as they are (the Moreya signpost of the staircase still uses them). The result is
deterministic (fixed random seeds).

Run from anywhere: python tools/menu_wood_weathering.py [<repo>]
"""
import argparse
import sys
from pathlib import Path

import numpy
from PIL import Image, ImageDraw, ImageFilter

#: Grey of sun- and rain-bleached old wood (sRGB 0..1) and how far the raised grain turns towards it.
SILVER = numpy.array((0.205, 0.192, 0.172))
SILVERING = 0.55
#: Share of the original colour saturation that the bleached wood keeps.
KEPT_SATURATION = 0.65
#: Supersampling of the crack lines.
SUPERSAMPLE = 3


def load_rgb(path):
    """Returns an image as a float array (rows from top to bottom, values 0..1)."""
    return numpy.asarray(Image.open(path).convert("RGB"), dtype=numpy.float64) / 255.0


def save_rgb(path, rgb):
    """Writes a float RGB array (values 0..1) as an 8-bit PNG."""
    Image.fromarray((numpy.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(numpy.uint8), "RGB").save(path, optimize=True)


def periodic_noise(rng, height, width, cells_v, cells_u):
    """Returns tileable smooth noise (mean 0, standard deviation 1) with about cells_v x cells_u blobs.

    White noise is low-pass filtered in the frequency domain, so the result wraps around both edges.
    """
    spectrum = numpy.fft.fft2(rng.standard_normal((height, width)))
    fv = numpy.fft.fftfreq(height)[:, None] * height / max(cells_v, 1e-3)
    fu = numpy.fft.fftfreq(width)[None, :] * width / max(cells_u, 1e-3)
    field = numpy.real(numpy.fft.ifft2(spectrum * numpy.exp(-(fv * fv + fu * fu) * 2.0)))
    return (field - field.mean()) / max(field.std(), 1e-9)


def luminance(rgb):
    """Returns the Rec. 601 luminance of an RGB array."""
    return rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114


def crack_lines(rng, height, width, count, length, along_u, wrap, width_range=(0.8, 2.6), starts=None):
    """Returns a 0..1 mask of thin splits that follow the grain with a slight wander.

    along_u: the grain runs along the image columns (u), else along the rows (v). wrap draws every line again shifted
    by the image size so a tileable texture stays tileable. starts optionally gives (u, v) start fractions.
    """
    canvas = Image.new("L", (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(canvas)
    for index in range(count):
        if starts is not None:
            u, v = starts[index]
            start = numpy.array((u * width, v * height))
        else:
            start = numpy.array((rng.random() * width, rng.random() * height))
        total = length[0] + rng.random() * (length[1] - length[0])
        heading = numpy.array((1.0, 0.0)) if along_u else numpy.array((0.0, 1.0))
        if rng.random() < 0.5 and starts is None:
            heading = -heading
        points = [start.copy()]
        drift = 0.0
        travelled = 0.0
        while travelled < total:
            step = 6.0
            drift = 0.85 * drift + rng.normal(0.0, 0.06)
            side = numpy.array((-heading[1], heading[0]))
            points.append(points[-1] + heading * step + side * drift * step)
            travelled += step
        thickness = width_range[0] + rng.random() * (width_range[1] - width_range[0])
        shifts = [(0, 0)]
        if wrap:
            shifts = [(dx, dy) for dx in (-width, 0, width) for dy in (-height, 0, height)]
        segments = len(points) - 1
        for shift in shifts:
            for segment in range(segments):
                # The split is widest in its middle and closes towards both ends.
                taper = numpy.sin(numpy.pi * (segment + 0.5) / segments) ** 0.6
                line_width = max(1, int(round(thickness * taper * SUPERSAMPLE)))
                a = (points[segment] + shift) * SUPERSAMPLE
                b = (points[segment + 1] + shift) * SUPERSAMPLE
                draw.line([tuple(a), tuple(b)], fill=255, width=line_width)
    canvas = canvas.resize((width, height), Image.LANCZOS)
    return numpy.asarray(canvas, dtype=numpy.float64) / 255.0


def blurred(mask, radius):
    """Returns a Gaussian blurred copy of a 0..1 mask."""
    image = Image.fromarray((numpy.clip(mask, 0.0, 1.0) * 255.0).astype(numpy.uint8), "L")
    return numpy.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=numpy.float64) / 255.0


def add_relief(normal, depth):
    """Adds the slope of a height field (in pixels of height per pixel) to a tangent-space normal map (0..1 encoded)."""
    du = (numpy.roll(depth, -1, axis=1) - numpy.roll(depth, 1, axis=1)) * 0.5
    dv = (numpy.roll(depth, 1, axis=0) - numpy.roll(depth, -1, axis=0)) * 0.5
    plain = normal * 2.0 - 1.0
    slope_u = plain[:, :, 0] / numpy.maximum(plain[:, :, 2], 1e-3) - du
    slope_v = plain[:, :, 1] / numpy.maximum(plain[:, :, 2], 1e-3) - dv
    result = numpy.dstack((slope_u, slope_v, numpy.ones_like(slope_u)))
    result /= numpy.linalg.norm(result, axis=2, keepdims=True)
    return result * 0.5 + 0.5


def age_colour(colour, rng, along_u):
    """Bleaches, greys and dirties wood colour: weathered grain, grime blotches and a few soot stains."""
    height, width = colour.shape[:2]
    grey = luminance(colour)[:, :, None]
    aged = grey + (colour - grey) * KEPT_SATURATION
    # Raised grain bleaches to grey; the bleaching follows the grain in long streaks.
    streaks = periodic_noise(rng, height, width, *((40, 3) if along_u else (3, 40)))
    patches = periodic_noise(rng, height, width, 4, 4)
    bleach = numpy.clip(0.45 + 0.25 * streaks + 0.25 * patches, 0.0, 1.0) * SILVERING
    target = SILVER * (0.75 + 0.5 * numpy.clip(grey / 0.12, 0.0, 1.0))
    aged = aged + (target - aged) * bleach[:, :, None]
    # Grime and old water stains darken in broad, soft blotches.
    grime = numpy.clip(0.5 + 0.35 * periodic_noise(rng, height, width, 6, 6), 0.0, 1.0)
    aged *= (1.0 - 0.38 * grime)[:, :, None]
    # Soot: a few dark sooty stains with ragged borders.
    soot_field = periodic_noise(rng, height, width, 5, 5) + 0.35 * periodic_noise(rng, height, width, 40, 40)
    soot = numpy.clip((soot_field - 1.0) / 0.8, 0.0, 1.0)
    aged *= (1.0 - 0.55 * soot)[:, :, None]
    # Fine pitting of the worn surface.
    pits = numpy.clip((periodic_noise(rng, height, width, 160, 160) - 1.8) / 0.6, 0.0, 1.0)
    aged *= (1.0 - 0.5 * pits)[:, :, None]
    return aged, pits


def weather_post_wood(colour, normal, rng):
    """Returns the weathered tileable post wood (grain along v) and its normal map."""
    height, width = colour.shape[:2]
    aged, pits = age_colour(colour, rng, along_u=False)
    splits = crack_lines(rng, height, width, 26, (60, 260), along_u=False, wrap=True)
    hairlines = crack_lines(rng, height, width, 40, (20, 90), along_u=False, wrap=True, width_range=(0.5, 1.0))
    cracks = numpy.clip(splits + 0.7 * hairlines, 0.0, 1.0)
    # Dark split with a slightly lighter, dried edge.
    edge = numpy.clip(blurred(cracks, 1.5) * 1.5 - cracks, 0.0, 1.0)
    aged = aged * (1.0 + 0.18 * edge)[:, :, None]
    aged = aged * (1.0 - 0.85 * cracks)[:, :, None]
    depth = -3.0 * blurred(cracks, 0.8) - 0.6 * pits
    return aged, add_relief(normal, depth)


def board_rows_cols(height, width):
    """Returns row and column fractions (v from the upper edge, u from the back end) of the board texture."""
    return numpy.arange(height)[:, None] / float(height), numpy.arange(width)[None, :] / float(width)


def weather_board(colour, normal, rng):
    """Ages the plain board planks before lettering: bleaching, grime, water stains running down, chipped edges.

    Returns the aged colour, the normal map with the chips and pits, and the chip mask.
    """
    height, width = colour.shape[:2]
    rows, columns = board_rows_cols(height, width)
    aged, pits = age_colour(colour, rng, along_u=True)
    # Rain ran down the board: darker streaks below the plank joints and a stained lower edge.
    runs = numpy.clip(0.5 + 0.5 * periodic_noise(rng, height, width, 2, 60), 0.0, 1.0)
    joints = numpy.zeros((height, width))
    for seam in (1.0 / 3.0, 2.0 / 3.0):
        below = rows - seam
        joints = numpy.maximum(joints, numpy.where(below > 0, numpy.exp(-below * 14.0), 0.0) * numpy.ones_like(columns))
    stain = numpy.clip(joints * runs * 0.9 + numpy.clip((rows - 0.75) / 0.25, 0.0, 1.0) * 0.6, 0.0, 1.0)
    aged *= (1.0 - 0.35 * stain)[:, :, None]
    # Chipped and broken edges: ragged dark notches along the board outline and the plank joints.
    ragged = periodic_noise(rng, height, width, 6, 36) + 0.3 * periodic_noise(rng, height, width, 40, 200)
    edge_distance = numpy.minimum(numpy.minimum(rows, 1.0 - rows) * height,
                                  numpy.minimum(columns, 1.0 - columns) * width)
    for seam in (1.0 / 3.0, 2.0 / 3.0):
        edge_distance = numpy.minimum(edge_distance, numpy.abs(rows - seam) * height + 2.0)
    chips = numpy.clip((3.0 + 9.0 * numpy.clip(ragged - 0.5, 0.0, 3.0) - edge_distance) / 3.0, 0.0, 1.0)
    aged *= (1.0 - 0.6 * chips)[:, :, None]
    depth = -2.0 * blurred(chips, 1.5) - 0.6 * pits
    return aged, add_relief(normal, depth), chips


def crack_board(colour, normal, rng):
    """Splits the finished board (lettering included) along the grain and checks its ends; returns colour and normal.

    The cracks run through the planks and the carved letters alike, so the paint looks as old as the wood.
    """
    height, width = colour.shape[:2]
    splits = crack_lines(rng, height, width, 34, (120, 900), along_u=True, wrap=False)
    hairlines = crack_lines(rng, height, width, 60, (40, 220), along_u=True, wrap=False, width_range=(0.5, 1.1))
    # End checks: short deep splits running in from the back end and the arrow tip.
    ends = [(0.0, 0.08 + 0.84 * rng.random()) for _ in range(7)]
    back = crack_lines(rng, height, width, len(ends), (80, 260), along_u=True, wrap=False, width_range=(1.5, 3.2),
                       starts=ends)
    cracks = numpy.clip(splits + 0.7 * hairlines + back, 0.0, 1.0)
    edge = numpy.clip(blurred(cracks, 1.5) * 1.5 - cracks, 0.0, 1.0)
    result = colour * (1.0 + 0.15 * edge)[:, :, None]
    result = result * (1.0 - 0.85 * cracks)[:, :, None]
    return result, add_relief(normal, -3.5 * blurred(cracks, 0.8))


def main():
    """Writes the weathered post wood and its normal map from the plain post wood."""
    parser = argparse.ArgumentParser(description="Write the weathered signpost post wood.")
    parser.add_argument("repo", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args(sys.argv[1:])
    folder = arguments.repo / "materials/textures/menu"
    colour = load_rgb(folder / "MenuSignpostWood.png")
    normal = load_rgb(folder / "MenuSignpostWoodNormal.png")
    aged, carved = weather_post_wood(colour, normal, numpy.random.default_rng(1913))
    save_rgb(folder / "MenuSignpostWeatheredWood.png", aged)
    save_rgb(folder / "MenuSignpostWeatheredWoodNormal.png", carved)


if __name__ == "__main__":
    main()
