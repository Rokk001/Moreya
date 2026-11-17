#!/usr/bin/env python3
"""Cut the thorned iron ring of the loading indicator out of its painted source as 256x256 RGBA PNGs.

The ring is not drawn by this script. The painted ring (asset source gui/loading/loading-ring-painted.png below
ODP_ASSETS_SRC, a 160x160 crop of the chosen painted loading screen) shows the dark iron ring with eight thorns;
the quarter from the top thorn clockwise to the right thorn glows as embers, the other three quarters are plain iron.
The ring repeats every 90 degrees (long thorns at 0, 90, 180 and 270 degrees, short ones between), so:
- loading_ring_empty.png, the empty track, is the plain iron quarter between the left and the top thorn, cut out
  and turned four times round the centre;
- loading_ring.png, the fill drawn clockwise by the loading progress, is the glowing quarter between the top and the
  right thorn, cut out and turned four times.
The quarters meet in a short cross-fade, so no seam shows. The alpha is cut from the painted pixels: the dark
background (wall, inner hole) becomes transparent, iron, thorns and the ember glow stay.

The painted band is thin next to its thorns. It is widened radially around its centre to BAND_INNER..BAND_OUTER
(24 of 256 px): the painted band is stretched over that width, and the thorns, which lie on the band, are taken
from the unstretched painting so they keep their painted shape.

Usage: python tools/make_loading_ring.py [output folder]
Needs Pillow and numpy.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from assets_src import assets_src_dir  # noqa: E402

SOURCE = "gui/loading/loading-ring-painted.png"
SIZE = 256
SAMPLES = 3
# Centre of the painted ring in the source crop, in pixel index coordinates (x, y).
SOURCE_CENTRE = (80.2, 78.1)
# Distance of the tip of a long thorn from the centre in the source, and where it lands in the texture.
SOURCE_THORN_TIP = 67.0
TEXTURE_THORN_TIP = 124.0
# Nothing beyond this source radius belongs to the ring (the painted text above it starts further out).
SOURCE_CUT_RADIUS = 68.0
# The iron band of the painted ring, source radii; its core is always opaque.
SOURCE_INNER_EDGE = 44.5
SOURCE_OUTER_EDGE = 52.5
# The widened band in the texture, radii in pixels of the 256 px texture (24 px wide, centred on the painted band).
BAND_INNER = 78.0
BAND_OUTER = 102.0
# Painted background luminance (0 to 255) is transparent below the first value and opaque above the second.
ALPHA_LUMINANCE = (36.0, 58.0)
# Unstretched painted pixels at least this opaque inside the widened band but outside the painted band are thorn.
THORN_ALPHA = 0.08
# Headings of the eight thorns (degrees clockwise from the top) and the half width of the wedge each thorn may cover.
THORN_HEADINGS = [45.0 * index for index in range(8)]
THORN_HALF_WEDGE = 14.0
# First angle (degrees clockwise from the top) of the quarter cut for the empty track and for the glowing fill.
EMPTY_QUARTER_START = 247.5
FILL_QUARTER_START = 0.0
# Width in degrees of the cross-fade where two turned quarters meet.
SEAM_DEGREES = 6.0

PAINTING = None


def sample(image, x, y):
    """Bilinear sample of an HxWxC float array at index coordinates; outside the crop is black."""
    height, width = image.shape[:2]
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    result = 0.0
    for dy, wy in ((0, 1.0 - fy), (1, fy)):
        for dx, wx in ((0, 1.0 - fx), (1, fx)):
            inside = ((x0 + dx >= 0) & (x0 + dx < width) & (y0 + dy >= 0) & (y0 + dy < height))[..., None]
            xi = np.clip(x0 + dx, 0, width - 1)
            yi = np.clip(y0 + dy, 0, height - 1)
            result = result + PAINTING[yi, xi] * wx * wy * inside
    return result


def painted(radius, heading):
    """RGB of the painted ring at a source radius and a heading in degrees clockwise from the top."""
    angle = np.radians(heading)
    x = SOURCE_CENTRE[0] + radius * np.sin(angle)
    y = SOURCE_CENTRE[1] - radius * np.cos(angle)
    return sample(PAINTING, x, y)


def quarter(radius, heading, start):
    """RGB of the quarter starting at start, turned so that it covers the heading, with a cross-fade at its end."""
    offset = np.mod(heading - start, 90.0)
    colour = painted(radius, start + offset)
    # Near the end of the quarter, fade into the painted pixels just before its start: the next turned copy
    # begins there, so both sides of the seam show the same painted pixels.
    blend = np.clip((offset - (90.0 - SEAM_DEGREES)) / SEAM_DEGREES, 0.0, 1.0)
    blend = (blend * blend * (3.0 - 2.0 * blend))[..., None]
    before = painted(radius, start + offset - 90.0)
    return colour * (1.0 - blend) + before * blend


def cut_out(colour, radius):
    """Alpha of painted pixels at source radii: background transparent, painted band core always opaque."""
    luminance = colour.mean(axis=-1)
    alpha = np.clip((luminance - ALPHA_LUMINANCE[0]) / (ALPHA_LUMINANCE[1] - ALPHA_LUMINANCE[0]), 0.0, 1.0)
    core = (radius >= SOURCE_INNER_EDGE + 1.0) & (radius <= SOURCE_OUTER_EDGE - 1.0)
    alpha = np.where(core, 1.0, alpha)
    return alpha * np.clip(SOURCE_CUT_RADIUS - radius, 0.0, 1.0)


def shade(x, y, ember):
    """RGB and alpha of the ring at texture points (arrays of x, y); ember selects the glowing fill."""
    start = FILL_QUARTER_START if ember else EMPTY_QUARTER_START
    dx = x - SIZE / 2.0
    dy = y - SIZE / 2.0
    texture_radius = np.hypot(dx, dy)
    heading = np.degrees(np.arctan2(dx, -dy))
    scale = SOURCE_THORN_TIP / TEXTURE_THORN_TIP
    # Unstretched painting: thorns and everything outside the widened band.
    plain_radius = texture_radius * scale
    plain = quarter(plain_radius, heading, start)
    plain_alpha = cut_out(plain, plain_radius)
    # Stretched band: the widened band shows the painted band from its inner to its outer edge.
    centre = (BAND_INNER + BAND_OUTER) / 2.0
    stretch = (BAND_OUTER - BAND_INNER) / ((SOURCE_OUTER_EDGE - SOURCE_INNER_EDGE) / scale)
    band_radius = (SOURCE_INNER_EDGE + SOURCE_OUTER_EDGE) / 2.0 + (texture_radius - centre) * scale / stretch
    band = quarter(band_radius, heading, start)
    band_alpha = cut_out(band, band_radius)
    # The whole widened band is solid iron (or embers), with a soft edge of one pixel.
    edge = np.minimum(texture_radius - BAND_INNER, BAND_OUTER - texture_radius)
    band_alpha = np.maximum(band_alpha, np.clip(edge + 0.5, 0.0, 1.0))
    in_band = (texture_radius >= BAND_INNER) & (texture_radius <= BAND_OUTER)
    # Inside the widened band but outside the painted band, a thorn of the painting stays on top of the band.
    near_thorn = np.zeros(heading.shape, dtype=bool)
    for thorn in THORN_HEADINGS:
        near_thorn |= np.abs(np.mod(heading - thorn + 180.0, 360.0) - 180.0) <= THORN_HALF_WEDGE
    outside_painted_band = (plain_radius < SOURCE_INNER_EDGE - 1.0) | (plain_radius > SOURCE_OUTER_EDGE + 1.0)
    thorn = near_thorn & outside_painted_band & (plain_alpha > THORN_ALPHA)
    # A thorn lies over the band with its own painted alpha, so the band stays closed below its soft edges.
    cover = np.where(thorn, plain_alpha, 0.0)
    colour = np.where(in_band[..., None], plain * cover[..., None] + band * (1.0 - cover[..., None]), plain)
    alpha = np.where(in_band, cover + band_alpha * (1.0 - cover), plain_alpha)
    return colour, alpha


def render(ember):
    """Renders one 256x256 RGBA texture with SAMPLES x SAMPLES samples per pixel."""
    total = np.zeros((SIZE, SIZE, 4))
    ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(float)
    for sy in range(SAMPLES):
        for sx in range(SAMPLES):
            colour, alpha = shade(xs + (sx + 0.5) / SAMPLES, ys + (sy + 0.5) / SAMPLES, ember)
            total[..., :3] += colour * alpha[..., None]
            total[..., 3] += alpha
    alpha = total[..., 3] / float(SAMPLES * SAMPLES)
    colour = np.where(alpha[..., None] > 0.0, total[..., :3] / np.maximum(total[..., 3:4], 1e-6), 0.0)
    rgba = np.concatenate([colour, alpha[..., None] * 255.0], axis=2)
    return Image.fromarray(np.clip(np.round(rgba), 0, 255).astype(np.uint8), "RGBA")


def main():
    """Writes the glowing fill and the empty iron track next to the loading screens unless a folder is given."""
    global PAINTING
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "materials/textures/loading"
    PAINTING = np.asarray(Image.open(assets_src_dir(ROOT) / SOURCE).convert("RGB"), dtype=float)
    for name, ember in (("loading_ring.png", True), ("loading_ring_empty.png", False)):
        render(ember).save(folder / name)


if __name__ == "__main__":
    main()
