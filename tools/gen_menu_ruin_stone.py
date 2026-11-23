#!/usr/bin/env python3
"""Age the stone of the forecourt, its portal and the frame of the hall opening of the main menu into a dark ruin.

The forecourt behind the campaign hall and the portal into Moreya at its far end looked clean and pale under the
light of the fire bowls: smooth, light stone and glossy paving. Like the stone arch with the green fire on the campaign
map they are to look dark, weathered and abandoned. This script derives two tileable albedo textures from the stone
of the fortress:

- MenuRuinStone.png from MenuFortressStone.png: darkened and partly desaturated, with broad grime patches, dark rain
  streaks running down, soot in the low areas of the stone and grey green lichen specks;
- MenuRuinPaving.png from MenuWetPaving.png: the same treatment without streaks, plus dark dirt in the joints, so the
  paving reads as old, dry, dirty flagstones instead of polished wet stone.

Every added layer is periodic noise (filtered in the frequency domain), so the textures tile like their sources. The
normal maps of the sources stay valid, because the relief is not changed.

    python tools/gen_menu_ruin_stone.py [<repo>]

writes materials/textures/menu/MenuRuinStone.png and MenuRuinPaving.png (the size of their sources, RGB). The result
depends only on the fixed seed and the source textures.
"""
import os
import sys

import numpy as np
from PIL import Image

#: Seed of the noise layers.
SEED = 23112
#: Brightness kept of the source, share of saturation kept, and the grey brown the stone is pulled towards.
DARKEN = 0.62
SATURATION = 0.55
GRIME_COLOUR = np.array([0.075, 0.068, 0.060])
#: Strength of the grime patches, the rain streaks, the soot in low areas and the lichen specks.
GRIME = 0.45
STREAKS = 0.38
SOOT = 0.35
LICHEN = 0.20
LICHEN_COLOUR = np.array([0.20, 0.22, 0.16])


def periodic_noise(rng, height, width, scale_u, scale_v):
    """Returns noise in -1..1 that tiles in both directions; scale_u and scale_v are the feature sizes in texels."""
    white = rng.standard_normal((height, width))
    frequency_v = np.fft.fftfreq(height)[:, None]
    frequency_u = np.fft.fftfreq(width)[None, :]
    falloff = np.exp(-((frequency_u * scale_u) ** 2 + (frequency_v * scale_v) ** 2))
    noise = np.real(np.fft.ifft2(np.fft.fft2(white) * falloff))
    noise -= noise.mean()
    return noise / max(np.abs(noise).max(), 1e-9)


def periodic_blur(values, scale):
    """Returns a periodic gaussian blur of a 2D array (feature size scale in texels)."""
    height, width = values.shape
    frequency_v = np.fft.fftfreq(height)[:, None]
    frequency_u = np.fft.fftfreq(width)[None, :]
    falloff = np.exp(-((frequency_u * scale) ** 2 + (frequency_v * scale) ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(values) * falloff))


def age(source, rng, streaks):
    """Returns the aged colours (0..1) of a source texture (0..1, height x width x 3)."""
    height, width = source.shape[:2]
    luminance = source @ np.array([0.299, 0.587, 0.114])
    grey = luminance[:, :, None]
    colour = grey + (source - grey) * SATURATION
    colour = colour * DARKEN + GRIME_COLOUR * (1.0 - DARKEN) * 0.5
    # Broad grime patches
    patches = np.clip(periodic_noise(rng, height, width, 90.0, 90.0) * 1.4, -1.0, 1.0)
    grime = GRIME * np.clip(patches, 0.0, 1.0)
    # Soot gathers in the low (dark) areas of the relief
    relief = luminance - periodic_blur(luminance, 24.0)
    soot = SOOT * np.clip(-relief * 6.0, 0.0, 1.0)
    darkening = grime + soot
    if streaks:
        # Rain streaks: noise stretched along v, strongest where it peaks
        lines = periodic_noise(rng, height, width, 2.5, 140.0)
        mask = np.clip(periodic_noise(rng, height, width, 60.0, 60.0) + 0.2, 0.0, 1.0)
        darkening = darkening + STREAKS * np.clip(lines * 1.8 - 0.3, 0.0, 1.0) * mask
    else:
        # Dirt in the joints of the paving (its darkest lines)
        joints = np.clip((0.18 - luminance) * 5.0, 0.0, 1.0)
        darkening = darkening + 0.4 * joints
    darkening = np.clip(darkening, 0.0, 0.85)[:, :, None]
    colour = colour * (1.0 - darkening) + GRIME_COLOUR * darkening * 0.6
    # Grey green lichen specks on the raised parts
    specks = periodic_noise(rng, height, width, 3.0, 3.0)
    spots = np.clip(periodic_noise(rng, height, width, 70.0, 70.0), 0.0, 1.0)
    lichen = (LICHEN * np.clip(specks * 3.0 - 1.4, 0.0, 1.0) * spots * np.clip(relief * 8.0 + 0.5, 0.0, 1.0))[:, :, None]
    colour = colour * (1.0 - lichen) + LICHEN_COLOUR * lichen
    return np.clip(colour, 0.0, 1.0)


def main():
    """Writes the two aged textures next to their sources."""
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    folder = os.path.join(root, "materials", "textures", "menu")
    rng = np.random.default_rng(SEED)
    for source_name, target_name, streaks in (("MenuFortressStone.png", "MenuRuinStone.png", True),
                                              ("MenuWetPaving.png", "MenuRuinPaving.png", False)):
        source = np.asarray(Image.open(os.path.join(folder, source_name)).convert("RGB"), dtype=np.float64) / 255.0
        aged = age(source, rng, streaks)
        Image.fromarray(np.round(aged * 255.0).astype(np.uint8), "RGB").save(os.path.join(folder, target_name),
                                                                             optimize=True)
        print("wrote %s (%d x %d)" % (target_name, source.shape[1], source.shape[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
