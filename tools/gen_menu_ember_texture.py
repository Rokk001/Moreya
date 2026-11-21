#!/usr/bin/env python3
"""Paint the glowing coal bed of the menu braziers and forge (material MenuEmber, menu scene).

The ember surfaces of the brazier bowls (models/MenuBrazier*.mesh) and of the forge hearth (models/MenuFortressRear.mesh)
were one flat untextured colour, seen from above in the settings flight as flat orange quads. This script writes a
tileable coal texture; the material multiplies its diffuse and emissive ember colour with it, so the bed shows dark
charcoal lumps with glowing cracks between them:

    materials/textures/menu/MenuEmberCoals.png   512 x 512, tileable, grey-warm values (texture x ember colour)

The lumps are the cells of a wrapped Voronoi pattern; the gaps between neighbouring cells glow (some white-hot, some
dull red), the lump tops stay dark charcoal. The result is deterministic (fixed random seed).

Run from anywhere: python tools/gen_menu_ember_texture.py [<repo>]
"""
import sys
from pathlib import Path

import numpy
from PIL import Image

#: Texture size in pixels and number of coal lumps in it.
SIZE = 512
LUMPS = 70
#: Value of the glowing cracks and of the dark lump tops (0..1, multiplied with the ember colour of the material).
CRACK = 1.0
LUMP = 0.12


def coal_bed(rng):
    """Returns the coal bed values (SIZE x SIZE, 0..1): glowing cracks between dark lumps, tileable."""
    seeds = rng.random((LUMPS, 2)) * SIZE
    rows, columns = numpy.mgrid[0:SIZE, 0:SIZE].astype(numpy.float64)
    nearest = numpy.full((SIZE, SIZE), numpy.inf)
    second = numpy.full((SIZE, SIZE), numpy.inf)
    for sy, sx in seeds:
        dy = numpy.abs(rows - sy)
        dx = numpy.abs(columns - sx)
        dy = numpy.minimum(dy, SIZE - dy)
        dx = numpy.minimum(dx, SIZE - dx)
        distance = numpy.sqrt(dx * dx + dy * dy)
        second = numpy.where(distance < nearest, nearest, numpy.minimum(second, distance))
        nearest = numpy.minimum(nearest, distance)
    edge = second - nearest
    crack = numpy.clip(1.0 - edge / 6.0, 0.0, 1.0) ** 1.5
    grain = tileable_noise(rng, 8)
    heat = tileable_noise(rng, 4)
    # Some cracks glow white-hot, others only dull red; the lump tops stay dark charcoal with a fine grain.
    return numpy.clip(LUMP * (0.7 + 0.6 * grain) + (CRACK - LUMP) * crack * (0.35 + 0.65 * heat), 0.0, 1.0)


def tileable_noise(rng, cells):
    """Returns smooth tileable value noise (SIZE x SIZE, 0..1) from a cells x cells random grid."""
    grid = rng.random((cells, cells))
    tiled = numpy.tile(grid, (3, 3))
    image = Image.fromarray((tiled * 255).astype(numpy.uint8)).resize((SIZE * 3, SIZE * 3), Image.BICUBIC)
    return numpy.asarray(image, dtype=numpy.float64)[SIZE:2 * SIZE, SIZE:2 * SIZE] / 255.0


def main():
    """Writes the tileable ember coal texture of the menu scene."""
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    rng = numpy.random.default_rng(6203)
    value = coal_bed(rng)
    # Warm grey: the hot cracks turn slightly yellow under the orange ember colour, the lumps stay neutral.
    rgb = numpy.dstack((value, value * (0.85 + 0.15 * value), value * (0.75 + 0.25 * value)))
    path = repo / "materials/textures/menu/MenuEmberCoals.png"
    Image.fromarray((numpy.clip(rgb, 0, 1) * 255 + 0.5).astype(numpy.uint8), "RGB").save(path, optimize=True)
    print("written %s, mean %.3f" % (path, float(value.mean())))


if __name__ == "__main__":
    main()
