#!/usr/bin/env python3
"""Paint the start screen subtitle "Lords of the Deep" onto a copy of the signpost board texture.

The board of models/MenuSignpost.mesh carries the material MenuSignpostBoard; its texture spans the whole board
outline (u 0..1 from the back end to the arrow tip, v 0..1 from the upper to the lower edge in image rows) and the
rectangular lettering area is u 0..0.875 (tools/blender-assets/moreya_raid_models.py writes the plain planks).
This script reads the plain board colour and normal map and writes lettered copies next to them:

    materials/textures/menu/MenuSignpostBoardLettered.png        the planks aged like the courtyard, the letters carved
                                                                 into them with the old paint worn and darkened
    materials/textures/menu/MenuSignpostBoardLetteredNormal.png  the plain normal map with chips, grooves and cracks
                                                                 added

By default the board is weathered (tools/menu_wood_weathering.py): bleached grey wood, grime, water stains, soot,
chipped edges, splits along the grain that run through the letters, and paint that is dull, flaked and dirty, never
clean or bright. --clean writes the earlier clean planks with bone white paint instead.

The letters keep clear of the two iron straps at the back end (u up to about 0.2) and of the arrow tip; their font is
gui/fonts/SourceSerif4-Semibold.ttf, the menu font. The result is deterministic (fixed random seed).

Run from anywhere: python tools/gen_menu_signpost_lettering.py [<repo>]

The Moreya signpost at the staircase behind the campaign table (models/MenuMoreyaSignpost.mesh,
tools/blender-assets/menu_moreya_entrance.py) uses the same planks with the word "Moreya":

    python tools/gen_menu_signpost_lettering.py [<repo>] --text Moreya --output MenuMoreyaSignpostBoard --paint-keep 1.1

writes materials/textures/menu/MenuMoreyaSignpostBoard.png and MenuMoreyaSignpostBoardNormal.png.
"""
import argparse
import sys
from pathlib import Path

import numpy
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import menu_wood_weathering as weathering  # noqa: E402  (ageing of the signpost wood)

#: The subtitle of the game.
TEXT = "Lords of the Deep"
#: Lettering box in texture fractions: from the right edge of the inner iron strap to the shoulder nails, and inside
#: the worn borders of the board.
BOX_LEFT, BOX_RIGHT = 0.215, 0.86
BOX_TOP, BOX_BOTTOM = 0.17, 0.83
#: Supersampling factor of the letter mask.
SUPERSAMPLE = 4
#: Paint colour (sRGB, like the board texture) and its weathering.
PAINT = numpy.array((0.84, 0.75, 0.56))
#: Colour of the old paint of the weathered board: a dull, darkened bone that kept a little of its warmth.
OLD_PAINT = numpy.array((0.46, 0.42, 0.35))
#: How much of the old paint survives the flaking by default (higher keeps more; the large "Moreya" letters of the
#: staircase signpost use --paint-keep 1.1 so their shapes stay whole from the campaign flight).
PAINT_KEEP = 0.9
#: Groove depth relative to the plank grain of the plain normal map and the width of the carved bevel in pixels.
GROOVE_DEPTH = 6.0
BEVEL_PIXELS = 3.0


def load_rgb(path):
    """Returns an image as a float array (rows from top to bottom, values 0..1)."""
    return numpy.asarray(Image.open(path).convert("RGB"), dtype=numpy.float64) / 255.0


def save_rgb(path, rgb):
    """Writes a float RGB array (values 0..1) as an 8-bit PNG."""
    Image.fromarray((numpy.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(numpy.uint8), "RGB").save(path, optimize=True)


def letter_mask(font_path, width, height, text=TEXT):
    """Returns the antialiased coverage (0..1) of a text (the subtitle by default), as large as fits into the box."""
    box_width = (BOX_RIGHT - BOX_LEFT) * width * SUPERSAMPLE
    box_height = (BOX_BOTTOM - BOX_TOP) * height * SUPERSAMPLE
    size = int(box_height)
    while True:
        font = ImageFont.truetype(str(font_path), size)
        left, top, right, bottom = font.getbbox(text)
        if right - left <= box_width and bottom - top <= box_height:
            break
        size -= 2
    canvas = Image.new("L", (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    centre_x = (BOX_LEFT + BOX_RIGHT) * 0.5 * width * SUPERSAMPLE
    centre_y = (BOX_TOP + BOX_BOTTOM) * 0.5 * height * SUPERSAMPLE
    ImageDraw.Draw(canvas).text((centre_x - (left + right) * 0.5, centre_y - (top + bottom) * 0.5), text, fill=255,
                                font=font)
    canvas = canvas.resize((width, height), Image.LANCZOS)
    return numpy.asarray(canvas, dtype=numpy.float64) / 255.0


def blurred(mask, radius):
    """Returns a Gaussian blurred copy of a 0..1 mask."""
    image = Image.fromarray((numpy.clip(mask, 0.0, 1.0) * 255.0).astype(numpy.uint8), "L")
    return numpy.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=numpy.float64) / 255.0


def smooth_noise(rng, height, width, cells):
    """Returns smooth value noise in 0..1 made by upscaling a coarse random grid."""
    coarse = Image.fromarray((rng.random((max(2, height * cells // width), cells)) * 255.0).astype(numpy.uint8), "L")
    return numpy.asarray(coarse.resize((width, height), Image.BICUBIC), dtype=numpy.float64) / 255.0


def lettered_board(colour, normal, mask, rng):
    """Carves and paints the letter mask into the board colour and normal map and returns both."""
    height, width = mask.shape
    # Weathered paint: a few small flakes leave wood showing in the grooves without breaking the letter shapes.
    wear = 0.6 * smooth_noise(rng, height, width, 64) + 0.4 * smooth_noise(rng, height, width, 512)
    paint_cover = mask * (0.25 + 0.75 * numpy.clip((wear - 0.1) / 0.15, 0.0, 1.0))
    shade = 0.82 + 0.18 * smooth_noise(rng, height, width, 256)
    paint = PAINT[None, None, :] * shade[:, :, None]
    # The groove is darker than the planks; a soot rim around each letter keeps it readable from afar.
    rim = numpy.clip(blurred(mask, 4.0) * 1.6 - mask, 0.0, 1.0)
    result = colour * (1.0 - 0.55 * rim)[:, :, None]
    result = result * (1.0 - 0.35 * mask)[:, :, None]
    result = result + (paint - result) * paint_cover[:, :, None]
    # Carved groove: a bevelled depression whose slope is added to the tangent-space normal of the planks.
    depth = -blurred(mask, BEVEL_PIXELS) * GROOVE_DEPTH / BEVEL_PIXELS
    du = (numpy.roll(depth, -1, axis=1) - numpy.roll(depth, 1, axis=1)) * 0.5
    dv = (numpy.roll(depth, 1, axis=0) - numpy.roll(depth, -1, axis=0)) * 0.5
    plain = normal * 2.0 - 1.0
    slope_u = plain[:, :, 0] / numpy.maximum(plain[:, :, 2], 1e-3) - du
    slope_v = plain[:, :, 1] / numpy.maximum(plain[:, :, 2], 1e-3) - dv
    carved = numpy.dstack((slope_u, slope_v, numpy.ones_like(slope_u)))
    carved /= numpy.linalg.norm(carved, axis=2, keepdims=True)
    return result, carved * 0.5 + 0.5


def weathered_lettering(colour, normal, mask, rng, keep=PAINT_KEEP):
    """Carves the letter mask into weathered planks and paints it with old, flaked and dirty paint.

    keep sets how much paint survives the flaking (PAINT_KEEP by default).

    The planks are aged first (weathering.weather_board), the letter edges are worn ragged, the paint keeps only
    patches in the grooves, grime and soot lie over it, and the splits of weathering.crack_board run through
    planks and letters. Returns the colour and the normal map.
    """
    height, width = mask.shape
    aged, aged_normal, _ = weathering.weather_board(colour, normal, rng)
    # Worn letter edges: the carved outline frays where the wood broke away.
    fray = weathering.periodic_noise(rng, height, width, 60, 240)
    worn = numpy.clip(mask * 1.25 - 0.18 - 0.12 * fray, 0.0, 1.0)
    # The groove is darker than the planks and collected dirt; a soot rim keeps the letters readable from afar.
    rim = numpy.clip(blurred(worn, 4.0) * 1.6 - worn, 0.0, 1.0)
    result = aged * (1.0 - 0.6 * rim)[:, :, None]
    result = result * (1.0 - 0.5 * worn)[:, :, None]
    # Old paint: large flaked-off areas, a few bare streaks along the grain and a dull uneven tone.
    flakes = 0.75 * weathering.periodic_noise(rng, height, width, 10, 40)         + 0.25 * weathering.periodic_noise(rng, height, width, 90, 360)
    grain = weathering.periodic_noise(rng, height, width, 80, 4)
    cover = numpy.clip((flakes + keep - 0.35 * numpy.clip(grain - 0.8, 0.0, 2.0)) / 0.35, 0.0, 1.0)
    paint_cover = worn * (0.15 + 0.85 * cover)
    shade = 0.78 + 0.22 * numpy.clip(0.5 + 0.3 * weathering.periodic_noise(rng, height, width, 30, 120), 0.0, 1.0)
    paint = OLD_PAINT[None, None, :] * shade[:, :, None]
    result = result + (paint - result) * paint_cover[:, :, None]
    # Grime and soot settle over paint and wood alike, heavier towards the lower edge.
    rows = numpy.arange(height)[:, None] / float(height)
    grime = numpy.clip(0.45 + 0.3 * weathering.periodic_noise(rng, height, width, 8, 30) + 0.35 * (rows - 0.5),
                       0.0, 1.0)
    result *= (1.0 - 0.3 * grime * paint_cover)[:, :, None]
    # Carved groove: a bevelled depression whose slope is added to the tangent-space normal of the aged planks.
    depth = -blurred(worn, BEVEL_PIXELS) * GROOVE_DEPTH / BEVEL_PIXELS
    carved = weathering.add_relief(aged_normal, depth)
    return weathering.crack_board(result, carved, rng)


def main():
    """Writes the lettered board texture and normal map of a signpost (the subtitle board unless --text is given)."""
    parser = argparse.ArgumentParser(description="Paint a text onto a copy of the signpost board planks.")
    parser.add_argument("repo", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--text", default=TEXT)
    parser.add_argument("--output", default="MenuSignpostBoardLettered",
                        help="base name of the written colour texture (the normal map adds Normal)")
    parser.add_argument("--paint-keep", type=float, default=PAINT_KEEP,
                        help="how much of the old paint survives the flaking of the weathered board")
    parser.add_argument("--clean", action="store_true",
                        help="clean planks and bone white paint instead of the weathered board")
    arguments = parser.parse_args(sys.argv[1:])
    repo = arguments.repo
    folder = repo / "materials/textures/menu"
    colour = load_rgb(folder / "MenuSignpostBoard.png")
    normal = load_rgb(folder / "MenuSignpostBoardNormal.png")
    height, width = colour.shape[:2]
    mask = letter_mask(repo / "gui/fonts/SourceSerif4-Semibold.ttf", width, height, arguments.text)
    rng = numpy.random.default_rng(4711)
    if arguments.clean:
        lettered, carved = lettered_board(colour, normal, mask, rng)
    else:
        lettered, carved = weathered_lettering(colour, normal, mask, rng, arguments.paint_keep)
    save_rgb(folder / (arguments.output + ".png"), lettered)
    save_rgb(folder / (arguments.output + "Normal.png"), carved)
    columns = numpy.nonzero(mask.max(axis=0) > 0.5)[0]
    rows = numpy.nonzero(mask.max(axis=1) > 0.5)[0]
    print("lettering u %.3f..%.3f, v %.3f..%.3f" % (columns[0] / width, columns[-1] / width, rows[0] / height,
                                                    rows[-1] / height))


if __name__ == "__main__":
    main()
