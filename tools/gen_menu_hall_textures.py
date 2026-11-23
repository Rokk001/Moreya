#!/usr/bin/env python3
"""Build the floor and wall textures of the campaign hall of the main menu from their sources.

The floor and the walls of the campaign hall (materials MenuHallFloor and MenuHallWall, tools/menu_hall_floor_walls.py)
each get their own look of an abandoned castle: worn, irregular, dirty flagstones laid at random with grime and debris on the floor, rough
masonry with damp stains and soot on the walls. Both albedo images were made with the image generation of OpenAI
Codex from own written briefs (asset sources hall_floor_codex_raw.png and hall_wall_codex_raw.png in
$ODP_ASSETS_SRC/materials/menu-hall, next to the briefs). This script

- makes a source that does not tile yet tile without seams (the source is blended with itself shifted by half its size, the shifted copy
  taking over towards the edges, so the left and right and the top and bottom edges meet),
- scales it to TEXTURE_SIZE and
- derives a tangent space normal map from its brightness (dark joints and cracks lie deep), so the RTSS normal mapping
  of the menu materials gives the stones relief.

    python tools/gen_menu_hall_textures.py [<repo>]

writes materials/textures/menu/MenuHallFloor.png, MenuHallFloorNormal.png, MenuHallWall.png and MenuHallWallNormal.png.
The result depends only on the sources and the fixed values below.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import assets_src  # noqa: E402

#: The sources, the textures written from them and whether the source needs its seams blended.
TEXTURES = (
    ("assets-src/materials/menu-hall/hall_floor_codex_raw.png", "MenuHallFloor", True),
    ("assets-src/materials/menu-hall/hall_wall_codex_raw.png", "MenuHallWall", True),
)
TEXTURE_SIZE = 1024
#: Width of the band at every edge (share of the size) over which the shifted copy takes over.
SEAM_BAND = 0.22
#: Height of the relief derived from the brightness, and the blur (pixels) of the height before the slope is taken.
RELIEF = 6.0
HEIGHT_BLUR = 1.5


def blur(values, sigma):
    """Returns a periodic gaussian blur of a 2D array (sigma in pixels), computed in the frequency domain."""
    height, width = values.shape
    frequency_v = np.fft.fftfreq(height)[:, None]
    frequency_u = np.fft.rfftfreq(width)[None, :]
    kernel = np.exp(-2.0 * (np.pi * sigma) ** 2 * (frequency_u ** 2 + frequency_v ** 2))
    return np.fft.irfft2(np.fft.rfft2(values) * kernel, s=(height, width))


def seamless(colours):
    """Returns the image (H x W x 3, 0..1) blended with itself shifted by half its size, so it tiles without seams."""
    height, width = colours.shape[:2]
    shifted = np.roll(np.roll(colours, height // 2, axis=0), width // 2, axis=1)
    y = (np.arange(height) + 0.5) / height
    x = (np.arange(width) + 0.5) / width
    # 1 in the middle, 0 at the edges: the source keeps the middle, the shifted copy (whose middle is the source's
    # edges, which meet there) the edges
    weight_y = np.clip(np.minimum(y, 1.0 - y) / SEAM_BAND, 0.0, 1.0)
    weight_x = np.clip(np.minimum(x, 1.0 - x) / SEAM_BAND, 0.0, 1.0)
    weight = (weight_y[:, None] * weight_x[None, :])[:, :, None]
    weight = weight * weight * (3.0 - 2.0 * weight)
    return colours * weight + shifted * (1.0 - weight)


def normal_map(colours):
    """Returns an RGB tangent space normal map (0..1) of the relief given by the brightness of the image."""
    height_field = blur(colours @ np.array([0.299, 0.587, 0.114]), HEIGHT_BLUR) * RELIEF
    slope_x = (np.roll(height_field, -1, axis=1) - np.roll(height_field, 1, axis=1)) / 2.0
    slope_y = (np.roll(height_field, -1, axis=0) - np.roll(height_field, 1, axis=0)) / 2.0
    # Image rows run down, the texture v axis of the tangent space up
    normal = np.stack((-slope_x, slope_y, np.ones_like(height_field)), axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    return normal * 0.5 + 0.5


def save(colours, path):
    """Writes an RGB array (0..1) as PNG."""
    Image.fromarray(np.round(np.clip(colours, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB").save(path, optimize=True)


def main():
    """Writes the albedo and normal textures of the hall floor and walls."""
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".."))
    folder = os.path.join(root, "materials", "textures", "menu")
    for source, name, blend_seams in TEXTURES:
        image = Image.open(assets_src.resolve(root, source)).convert("RGB")
        image = image.resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.LANCZOS)
        colours = np.asarray(image, dtype=np.float64) / 255.0
        if blend_seams:
            colours = seamless(colours)
        save(colours, os.path.join(folder, name + ".png"))
        save(normal_map(colours), os.path.join(folder, name + "Normal.png"))
    print("wrote %d hall textures with their normal maps" % len(TEXTURES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
