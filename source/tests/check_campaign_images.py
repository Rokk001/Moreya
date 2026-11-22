#!/usr/bin/env python3
"""Checks that every 2D image the campaign references exists, has the size the game expects and a CREDITS entry.

Sources of the references: the map description gui/campaign/campaign-world.json (map of Moreya, cave markers), the
Guild and Preview keys of the wing packages (guild banners, leader portraits, level previews; scripts/
campaign_packages.py) and the campaign hall texture named by materials/scripts/MenuScene.material. The public
repository holds only the images of wing 1 in gui/campaign/; the private content packages of wings 2 to 6 bring
their own previews, banners and portraits in their package folders, where the game looks first.
The expected counts are the campaign's structure, counted once for this branch: public 4 previews, 3 guild banners,
3 leader portraits (wing 1), 1 map and 7 cave markers; the content packages add 20 previews (15 story and 5 bonus
levels), 15 banners and 15 portraits. Run from any directory; it compiles nothing and starts no game.
"""
from pathlib import Path
import json
import re
import sys

from PIL import Image

EXPECTED_PREVIEWS = 4
EXPECTED_BANNERS = 3
EXPECTED_PORTRAITS = 3
# Images of the private content packages: previews, banners, portraits
EXPECTED_CONTENT = (20, 15, 15)
EXPECTED_ICONS = 7
MAP_SIZE = (2560, 1600)
PREVIEW_SIZE = (640, 360)
BANNER_SIZE = (160, 320)
PORTRAIT_SIZE = (256, 256)
ICON_SIZE = (128, 128)
HALL_TEXTURE = "materials/textures/menu/MenuCampaignMap.png"

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "scripts"))
import campaign_packages  # noqa: E402
HAS_CONTENT = campaign_packages.has_content(root)
# Images the packages present use: all with the content repository, those of wing 1 without it
USED = (24, 18, 18) if HAS_CONTENT else (4, 3, 3)
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

# The banners and portraits the packages use, and all public ones in their folders
package_entries = campaign_packages.entries(root)
used_banners = {entry["GuildBanner"] for entry in package_entries if entry.get("GuildBanner")}
used_portraits = {entry["GuildPortrait"] for entry in package_entries if entry.get("GuildPortrait")}
check((len(used_banners), len(used_portraits)) == USED[1:], "the packages must use %d banners and %d portraits"
      % USED[1:])
public_entries = [entry for entry in package_entries if entry["_public"]]
content_entries = [entry for entry in package_entries if not entry["_public"]]
used_banners = {entry["GuildBanner"] for entry in public_entries if entry.get("GuildBanner")}
used_portraits = {entry["GuildPortrait"] for entry in public_entries if entry.get("GuildPortrait")}
banners = sorted(path.relative_to(art).as_posix() for path in (art / "banners").glob("*.png"))
portraits = sorted(path.relative_to(art).as_posix() for path in (art / "portraits").glob("*.png"))
check(used_banners <= set(banners) and used_portraits <= set(portraits),
      "every banner and portrait of a public package must lie in gui/campaign")
check(len(set(banners)) == EXPECTED_BANNERS, "expected %d distinct banners, found %d" % (EXPECTED_BANNERS,
                                                                                       len(set(banners))))
check(len(set(portraits)) == EXPECTED_PORTRAITS, "expected %d distinct portraits, found %d" % (EXPECTED_PORTRAITS,
                                                                                               len(set(portraits))))
for relative in banners:
    check_image("gui/campaign/" + relative, BANNER_SIZE, "guild banner", credits)
for relative in portraits:
    check_image("gui/campaign/" + relative, PORTRAIT_SIZE, "leader portrait", credits)

definition = campaign_packages.definition_text(root)
used_previews = {value.strip() for value in re.findall(r"(?m)^\s*Preview\s*=\s*(\S+)", definition)}
check(len(used_previews) == USED[0], "the packages must use %d distinct previews" % USED[0])
previews = sorted(path.relative_to(art).as_posix() for path in (art / "previews").glob("*.png"))
public_previews = {entry["Preview"].strip() for entry in public_entries if entry.get("Preview")}
check(public_previews <= set(previews), "every preview of a public package must lie in gui/campaign/previews")
check(len(set(previews)) == EXPECTED_PREVIEWS, "expected %d distinct previews, found %d" % (EXPECTED_PREVIEWS,
                                                                                           len(set(previews))))
for relative in previews:
    check_image("gui/campaign/" + relative, PREVIEW_SIZE, "level preview", credits)

# Images of the private content packages lie in their own package folders and are credited in their CREDITS
content_counts = (0, 0, 0)
if HAS_CONTENT:
    content_credits = (campaign_packages.content_repository(root) / "CREDITS").read_text(encoding="utf-8")
    kinds = (("Preview", PREVIEW_SIZE, "level preview", "previews"),
             ("GuildBanner", BANNER_SIZE, "guild banner", "banners"),
             ("GuildPortrait", PORTRAIT_SIZE, "leader portrait", "portraits"))
    counts = []
    for key, size, kind, folder in kinds:
        files = sorted({(entry["_package"], entry[key].strip()) for entry in content_entries if entry.get(key)})
        counts.append(len(files))
        check("-> %s/*.png" % folder in content_credits, "the content CREDITS must name the %s images" % folder)
        for package, relative in files:
            path = package / relative
            check(path.is_file(), "missing %s %s in %s" % (kind, relative, package.name))
            if path.is_file():
                with Image.open(path) as image:
                    check(image.format == "PNG" and image.size == size,
                          "%s %s in %s must be a PNG of %d x %d" % ((kind, relative, package.name) + size))
    content_counts = tuple(counts)
    check(content_counts == EXPECTED_CONTENT, "the content packages must bring %d previews, %d banners and %d "
          "portraits, found %d, %d and %d" % (EXPECTED_CONTENT + content_counts))

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
      "hall texture exist with their sizes and CREDITS entries; content packages: %d previews, %d banners, %d "
      "portraits" % ((len(icons), len(set(banners)), len(set(portraits)), len(set(previews))) + content_counts))
