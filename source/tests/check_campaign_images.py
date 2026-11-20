#!/usr/bin/env python3
"""Checks that every 2D image the campaign references exists, has the size the game expects and a CREDITS entry.

Sources of the references: the map description gui/campaign/campaign-world.json (map of Moreya, cave markers,
guild banners, leader portraits), the Preview keys of levels/campaign/Campaign.cfg (level previews) and the
campaign hall texture named by materials/scripts/MenuScene.material. The expected counts are the campaign's
structure, counted once for this branch: 24 previews (18 story and 6 bonus levels), 18 guild banners,
18 leader portraits, 1 map and 7 cave markers. Run from any directory; it compiles nothing and starts no game.
"""
from pathlib import Path
import json
import re
import sys

from PIL import Image

EXPECTED_PREVIEWS = 24
EXPECTED_BANNERS = 18
EXPECTED_PORTRAITS = 18
EXPECTED_ICONS = 7
MAP_SIZE = (2560, 1600)
PREVIEW_SIZE = (640, 360)
BANNER_SIZE = (160, 320)
PORTRAIT_SIZE = (256, 256)
ICON_SIZE = (128, 128)
HALL_TEXTURE = "materials/textures/menu/MenuCampaignMap.png"

root = Path(__file__).resolve().parents[2]
art = root / "gui/campaign"
failures = []


def check(condition, message):
    """Collects a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def credited_paths():
    """The set of file paths that start a line of CREDITS."""
    paths = set()
    for line in (root / "CREDITS").read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if parts:
            paths.add(parts[0])
    return paths


def check_image(relative, size, kind, credits):
    """Checks that the image below the repository root exists, opens as PNG of the given size and is credited."""
    path = root / relative
    check(path.is_file(), "missing %s %s" % (kind, relative))
    if not path.is_file():
        return
    try:
        with Image.open(path) as image:
            check(image.format == "PNG", "%s %s must be a PNG" % (kind, relative))
            check(image.size == size, "%s %s must be %d x %d" % ((kind, relative) + size))
            image.load()
    except OSError:
        failures.append("%s %s cannot be read" % (kind, relative))
    check(relative in credits, "%s %s has no CREDITS entry" % (kind, relative))


credits = credited_paths()
world = json.loads((art / "campaign-world.json").read_text(encoding="utf-8"))

check_image("gui/campaign/" + world.get("base", "-"), MAP_SIZE, "map image", credits)
icons = world.get("icons", {})
check(len(icons) == EXPECTED_ICONS, "the map must name %d cave markers, found %d" % (EXPECTED_ICONS, len(icons)))
for relative in icons.values():
    check_image("gui/campaign/" + relative, ICON_SIZE, "cave marker", credits)

banners = []
portraits = []
for wing in world.get("wings", []):
    for level in wing.get("levels", []):
        guild = level.get("guild", {})
        banners.append(guild.get("banner", "-"))
        portraits.append(guild.get("portrait", "-"))
check(len(set(banners)) == EXPECTED_BANNERS, "expected %d distinct banners, found %d" % (EXPECTED_BANNERS,
                                                                                       len(set(banners))))
check(len(set(portraits)) == EXPECTED_PORTRAITS, "expected %d distinct portraits, found %d" % (EXPECTED_PORTRAITS,
                                                                                               len(set(portraits))))
for relative in banners:
    check_image("gui/campaign/" + relative, BANNER_SIZE, "guild banner", credits)
for relative in portraits:
    check_image("gui/campaign/" + relative, PORTRAIT_SIZE, "leader portrait", credits)

definition = (root / "levels/campaign/Campaign.cfg").read_text(encoding="utf-8")
previews = [value.strip() for value in re.findall(r"(?m)^\s*Preview\s*=\s*(\S+)", definition)]
check(len(set(previews)) == EXPECTED_PREVIEWS, "expected %d distinct previews, found %d" % (EXPECTED_PREVIEWS,
                                                                                           len(set(previews))))
for relative in previews:
    check_image("gui/campaign/" + relative, PREVIEW_SIZE, "level preview", credits)

material = (root / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
block = material[material.index("material MenuCampaignMap"):]
texture = re.search(r"texture\s+(\S+)", block[:block.index("\n}")])
check(texture is not None and texture.group(1) == Path(HALL_TEXTURE).name,
      "the campaign hall material must use " + Path(HALL_TEXTURE).name)
check_image(HALL_TEXTURE, MAP_SIZE, "campaign hall texture", credits)

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign image checks passed: 1 map, %d cave markers, %d banners, %d portraits, %d previews and the campaign "
      "hall texture exist with their sizes and CREDITS entries" % (len(icons), len(set(banners)), len(set(portraits)),
                                                                   len(set(previews))))
