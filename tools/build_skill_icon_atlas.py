#!/usr/bin/env python3
"""Builds the atlas of the painted creature skill icons.

Every skill of config/creatureSkills.cfg (the path skills and the tier-4 skills) has a painted 256x256 icon named by its
skill id in the asset sources: <ODP_ASSETS_SRC>/skill-trees/icons/<skill id>.png, else <repo>/assets-src/... The script
places them in the order of the config, eight per row, and writes one image per skill id, so the image names of the
former placeholders (tools/gen_skill_placeholder_icons.py) stay unchanged.

Run it from the repository root:

    python tools/build_skill_icon_atlas.py

Output:
    gui/CreatureSkillIcons.png        atlas of one 256x256 icon per skill
    gui/CreatureSkillIcons.imageset   one image per skill id

Needs Pillow.
"""

import os
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "creatureSkills.cfg"
OUT_PNG = ROOT / "gui" / "CreatureSkillIcons.png"
OUT_IMAGESET = ROOT / "gui" / "CreatureSkillIcons.imageset"

CELL = 256
COLUMNS = 8


def source_dir():
    """Returns the folder of the painted icons: ODP_ASSETS_SRC, else assets-src in the repository."""
    base = os.environ.get("ODP_ASSETS_SRC")
    root = Path(base) if base else ROOT / "assets-src"
    return root / "skill-trees" / "icons"


def skill_ids():
    """Returns the skill ids in config order: the path skills, then T4_<Creature> of every tier-4 skill."""
    text = CONFIG.read_text(encoding="utf-8")
    ids = re.findall(r"(?m)^Id\s+(\S+)\s*$", text)
    ids += ["T4_" + c for c in re.findall(r"(?m)^Creature\s+(\S+)\s*$", text)]
    return ids


def main():
    """Writes the atlas and the imageset from the painted icons; fails when an icon is missing."""
    ids = skill_ids()
    src = source_dir()
    missing = [i for i in ids if not (src / (i + ".png")).is_file()]
    if missing:
        print("missing icons in %s: %s" % (src, ", ".join(missing)))
        return 1
    rows = (len(ids) + COLUMNS - 1) // COLUMNS
    atlas = Image.new("RGBA", (COLUMNS * CELL, rows * CELL), (0, 0, 0, 0))
    lines = []
    for index, skill_id in enumerate(ids):
        x, y = (index % COLUMNS) * CELL, (index // COLUMNS) * CELL
        with Image.open(src / (skill_id + ".png")) as icon:
            icon = icon.convert("RGBA")
            if icon.size != (CELL, CELL):
                icon = icon.resize((CELL, CELL), Image.LANCZOS)
            atlas.paste(icon, (x, y))
        lines.append('    <Image height="%d" name="%s" width="%d" xPos="%d" yPos="%d" />' % (CELL, skill_id, CELL, x, y))
    atlas.save(OUT_PNG, optimize=True)
    with open(OUT_IMAGESET, "w", encoding="utf-8", newline="\n") as out:
        out.write('<?xml version="1.0" encoding="utf-8"?>\n')
        out.write('<Imageset autoScaled="true" imagefile="CreatureSkillIcons.png" name="CreatureSkillIcons" '
                  'nativeHorzRes="%d" nativeVertRes="%d" version="2">\n' % (COLUMNS * CELL, rows * CELL))
        out.write("\n".join(lines) + "\n</Imageset>\n")
    print("%d icons, atlas %dx%d" % (len(ids), COLUMNS * CELL, rows * CELL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
