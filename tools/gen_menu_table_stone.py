#!/usr/bin/env python3
"""Build the stone of the campaign table of the main menu: the same stone as the map carved into its top.

The map is not laid on the table, it is cut into it: the slab of the table (top, bevels, cut-off corners and side
faces) is one piece of the same stone as the carved map. This script derives the tileable texture of that stone
(material MenuTableStone) from the fortress stone (MenuFortressStone.png, which tiles and fits its normal map) by giving
it the colour of the carved map's stone: every colour channel is moved to STONE_MEAN and STONE_SPREAD, the mean and
the spread (times 0.55, so the slab reads as dressed stone, not rough rock) of the light, flat stone of the outer band
of the carved map texture (MenuCampaignMap.png, 50 pixels wide, its pixels brighter than the median), measured once
on the carved map of 2026-11-23 before that band was faded into this stone (tools/gen_campaign_map_art.py).

    python tools/gen_menu_table_stone.py [<repo>]

writes materials/textures/menu/MenuTableStone.png (the size of MenuFortressStone.png). The result depends only on
MenuFortressStone.png and the fixed values below.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
#: Mean and spread of every colour channel (0..1) of the stone of the carved map.
STONE_MEAN = np.array([0.444, 0.355, 0.272])
STONE_SPREAD = np.array([0.085, 0.075, 0.062])


def main():
    """Writes the table stone texture."""
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".."))
    folder = os.path.join(root, "materials", "textures", "menu")
    stone = np.asarray(Image.open(os.path.join(folder, "MenuFortressStone.png")).convert("RGB"),
                       dtype=np.float64) / 255.0
    mean = stone.reshape(-1, 3).mean(axis=0)
    spread = stone.reshape(-1, 3).std(axis=0)
    result = np.clip((stone - mean) / spread * STONE_SPREAD + STONE_MEAN, 0.0, 1.0)
    Image.fromarray(np.round(result * 255.0).astype(np.uint8), "RGB").save(os.path.join(folder, "MenuTableStone.png"),
                                                                           optimize=True)
    print("wrote MenuTableStone.png: mean %s" % np.round(result.reshape(-1, 3).mean(axis=0), 3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
