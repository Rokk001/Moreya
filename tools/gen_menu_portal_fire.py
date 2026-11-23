#!/usr/bin/env python3
"""Paint the green fire that fills the portal into Moreya on the start screen (MenuMoreyaPortal.mesh).

The portal behind the campaign table is the other side of the green start gate of the campaign map: a stone arch
whose opening is filled with green fire. The fire face of the mesh (material MenuMoreyaPortalFire,
materials/scripts/MenuMoreyaPortal.material) maps this texture once across the opening (u 0..1 from left to right,
v 0..1 from the top of the arch to its foot) and scrolls it upwards, so it must tile vertically:

- tongues of flame: noise that is periodic in both directions, stretched along v so it reads as rising streaks;
- a brighter core along the middle of the opening and darker, almost black-green edges near the stone;
- colours from black green through deep and bright green to a pale yellow green at the hottest points; between the
  tongues the fire stays dark, so it reads as flames and not as a lit green plane.

A second texture, MenuMoreyaPortalFireShade.png, does not scroll: it is grey scale and darkens the fire towards the
crown of the arch and towards the stone at both sides, so the flames burn brightest low in the middle of the opening.

    python tools/gen_menu_portal_fire.py [<repo>]

writes materials/textures/menu/MenuMoreyaPortalFire.png (256 x 512, RGB) and MenuMoreyaPortalFireShade.png (64 x 128,
grey). The result depends only on the fixed seed.
"""
import os
import sys

import numpy as np
from PIL import Image

#: Size of the texture (width across the opening, height along it) and the seed of the noise.
WIDTH, HEIGHT, SEED = 256, 512, 7411
#: Colour ramp of the fire: (intensity, red, green, blue), intensities rising from 0 to 1.
RAMP = ((0.0, 0.0, 0.02, 0.005), (0.3, 0.01, 0.16, 0.03), (0.55, 0.05, 0.48, 0.07), (0.8, 0.28, 0.86, 0.16),
        (1.0, 0.78, 1.0, 0.5))


def periodic_noise(rng, scale_u, scale_v):
    """Returns noise in -1..1 that tiles in both directions; scale_u and scale_v are the feature sizes in texels."""
    white = rng.standard_normal((HEIGHT, WIDTH))
    frequency_v = np.fft.fftfreq(HEIGHT)[:, None]
    frequency_u = np.fft.fftfreq(WIDTH)[None, :]
    falloff = np.exp(-((frequency_u * scale_u) ** 2 + (frequency_v * scale_v) ** 2))
    field = np.real(np.fft.ifft2(np.fft.fft2(white) * falloff))
    return field / np.abs(field).max()


def paint():
    """Returns the fire texture as an (HEIGHT, WIDTH, 3) uint8 array."""
    rng = np.random.default_rng(SEED)
    # Streaks: features far longer along v than across u; a finer layer breaks their edges.
    flames = 0.65 * periodic_noise(rng, 22.0, 90.0) + 0.35 * periodic_noise(rng, 7.0, 26.0)
    u = (np.arange(WIDTH) + 0.5) / WIDTH
    # The core is brightest along the middle and falls off towards the stone at both sides.
    core = np.exp(-((u - 0.5) / 0.3) ** 2)[None, :]
    intensity = np.clip(0.08 + 0.4 * core + 0.95 * flames * (0.5 + 0.5 * core), 0.0, 1.0) ** 1.6
    points = np.array([step[0] for step in RAMP])
    colour = np.stack([np.interp(intensity, points, np.array([step[channel] for step in RAMP]))
                       for channel in (1, 2, 3)], axis=-1)
    return np.round(colour * 255).astype(np.uint8)


def shade():
    """Returns the fixed shade of the opening as a (128, 64) uint8 array: bright low in the middle, dark at the rim."""
    u = (np.arange(64) + 0.5) / 64
    v = (np.arange(128) + 0.5) / 128
    across = 0.25 + 0.75 * np.exp(-((u - 0.5) / 0.36) ** 2)
    # v runs from the crown (0) to the foot (1) of the opening.
    along = 0.35 + 0.65 * v ** 0.8
    return np.round(np.clip(along[:, None] * across[None, :], 0.0, 1.0) * 255).astype(np.uint8)


def main():
    """Writes both textures into the menu texture folder of the repository."""
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    target = os.path.join(repo, "materials", "textures", "menu", "MenuMoreyaPortalFire.png")
    Image.fromarray(paint(), "RGB").save(target, optimize=True)
    print("wrote " + target)
    target = os.path.join(repo, "materials", "textures", "menu", "MenuMoreyaPortalFireShade.png")
    Image.fromarray(shade(), "L").save(target, optimize=True)
    print("wrote " + target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
