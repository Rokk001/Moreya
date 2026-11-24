#!/usr/bin/env python3
"""Check that the "Moreya" signpost at the staircase looks as old and weathered as the courtyard (no compile).

models/MenuMoreyaSignpost.mesh (config/mainmenuscene.cfg, entity MoreyaSignpost) must not look clean (style guide:
dark, worn wood with saturation <= 0.45, no near-white texels), the same way as the "Lords of the Deep" signpost of
check_start_screen_signpost_zivs.py, with the same limits:
- its post, brace and board edges use the weathered wood MenuSignpostWeatheredWood, not the clean MenuSignpostWood;
- its board texture MenuMoreyaSignpostBoard.png has no bright texel and no bright or saturated area, and its open
  wood (outside the plank joints, the edges and the letters with their soot rim) is split by cracks;
- the paint of the carved "Moreya" is dull and flaked and the letters still stand out from the planks around them.

The mesh, the material, the board texture and the font live in content packages (found through
scripts/content_packages.py); without the content the check names them as not checked.
"""
import os
import sys
import time

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_menu_sky_below_horizon as scene  # noqa: E402  (numpy mesh reader of the menu scene check)
import check_start_screen_signpost_zivs as subtitle  # noqa: E402  (weathering limits of the subtitle signpost)
import content_packages  # noqa: E402  (scripts/ is on the path through the menu scene check)

#: The word on the board.
TEXT = "Moreya"
#: The game data files the check reads
CONTENT_FILES = ("models/MenuMoreyaSignpost.mesh", "materials/scripts/MenuSignpost.material",
                 "materials/textures/menu/MenuMoreyaSignpostBoard.png", "gui/fonts/MedievalSharp-Bold.ttf")


def data_path(relative):
    """Returns the game data file of the public tree or of a content package (else the path below the repository)."""
    return str(content_packages.resolve(ROOT, relative))


def check(failures):
    """Weathered wood on the mesh, weathered board texture, dull flaked paint that stays readable."""
    vertices, faces, materials = scene.load_mesh(data_path("models/MenuMoreyaSignpost.mesh"))
    if "MenuSignpostWood" in set(materials):
        failures.append("the Moreya signpost still uses the clean wood MenuSignpostWood")
    if "MenuSignpostWeatheredWood" not in set(materials):
        failures.append("the Moreya signpost does not use the weathered wood MenuSignpostWeatheredWood")
    material = open(data_path("materials/scripts/MenuSignpost.material"), encoding="utf-8").read()
    board = material.split("material MenuMoreyaSignpostBoard ", 1)[-1].split("\nmaterial ", 1)[0]
    if "texture MenuMoreyaSignpostBoard.png" not in board:
        failures.append("MenuMoreyaSignpostBoard does not use MenuMoreyaSignpostBoard.png")

    rgb = np.asarray(Image.open(data_path("materials/textures/menu/MenuMoreyaSignpostBoard.png")).convert("RGB"),
                     dtype=float)
    height, width = rgb.shape[:2]
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import gen_menu_signpost_lettering as lettering
    mask = lettering.letter_mask(data_path("gui/fonts/MedievalSharp-Bold.ttf"), width, height, TEXT)
    rows = np.arange(height)[:, None] / float(height)
    columns = np.arange(width)[None, :] / float(width)
    rim = np.asarray(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(
        ImageFilter.MaxFilter(subtitle.LETTER_RIM_PIXELS)), dtype=float) > 0
    joint, edge_v, edge_u = subtitle.OPEN_WOOD_MARGIN
    open_wood = (~rim & (np.abs(rows - 1.0 / 3.0) > joint) & (np.abs(rows - 2.0 / 3.0) > joint)
                 & (rows > edge_v) & (rows < 1.0 - edge_v) & (columns > edge_u) & (columns < 1.0 - edge_u))
    luminance = subtitle.check_weathered("the Moreya board", rgb, failures, open_wood)

    inside = mask > 0.5
    grown = np.asarray(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(15)), dtype=float)
    ring = (grown > 0) & (mask < 0.02)
    if luminance[inside].mean() > subtitle.MAX_PAINT_LUMINANCE:
        failures.append("the Moreya paint is bright and clean (mean luminance %.0f > %.0f)"
                        % (luminance[inside].mean(), subtitle.MAX_PAINT_LUMINANCE))
    cover = (luminance[inside] > subtitle.PAINT_LUMINANCE).mean()
    if not subtitle.PAINT_COVER[0] <= cover <= subtitle.PAINT_COVER[1]:
        failures.append("the Moreya paint covers %.2f of the letters, not worn to %.2f..%.2f"
                        % ((cover,) + subtitle.PAINT_COVER))
    if luminance[inside].mean() < subtitle.MIN_LETTER_CONTRAST * luminance[ring].mean():
        failures.append("the Moreya letters do not stand out from the planks (%.0f against %.0f)"
                        % (luminance[inside].mean(), luminance[ring].mean()))


def main():
    """Runs the check and reports every failure (names the files as not checked when the content is not present)."""
    missing = [relative for relative in CONTENT_FILES if content_packages.data_file(ROOT, relative) is None]
    if missing and not content_packages.has_content(ROOT):
        content_packages.unchecked("check_menu_moreya_signpost_weathered", missing)
        return 0
    started = time.monotonic()
    failures = []
    check(failures)
    print('ODP_TEST_PHASE {"name":"check","seconds":%.2f}' % (time.monotonic() - started))
    for failure in failures:
        print("FAIL " + failure)
    if failures:
        return 1
    print("OK: the Moreya signpost has weathered wood, a weathered board and old flaked paint that stays readable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
