#!/usr/bin/env python3
"""Checks that every 2D image the campaign references exists, has the size the game expects and a CREDITS entry.

Sources of the references: the map description gui/campaign/campaign-world.json (map of Moreya, cave markers), the
Guild and Preview keys of the wing packages (guild banners, leader portraits, level previews; scripts/
campaign_packages.py) and the campaign hall texture named by materials/scripts/MenuScene.material. The public
repository holds no wing: the wing packages of wings 1 to 6 bring their own previews, banners and portraits in their
package folders, where the game looks first (gui/campaign/{previews,banners,portraits} of the public tree is searched
as well and is empty). The map, the cave markers, the hall material and its texture are files of the content
packages, found through scripts/content_packages.py.
The expected counts are the campaign's structure, counted once for this branch: wing 1 4 previews, 3 guild banners and
3 leader portraits (in the public gui/campaign/ folders or the wing 1 package), 1 map and 7 cave markers; the packages
of wings 2 to 6 add 20 previews (15 story and 5 bonus levels), 15 banners and 15 portraits. Without content the parts
that need content files are named as not checked. Run from any directory; it compiles nothing and starts no game.
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
import content_packages  # noqa: E402
HAS_CONTENT = campaign_packages.has_content(root)
# Images the packages present use: all with the content repository, none without it (the public tree has no wing)
USED = (24, 18, 18) if HAS_CONTENT else (0, 0, 0)
art = root / "gui/campaign"
# The wing 1 package (a content package now), None without content
WING1 = next((folder for folder, wing, _, _ in campaign_packages.packages(root) if wing == 1), None)
failures = []


def check(condition, message):
    """Collects a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def credited_paths(folder=None):
    """The set of file paths that start a line of CREDITS (of the repository, or of the given folder)."""
    paths = set()
    credits_file = Path(folder or root) / "CREDITS"
    if not credits_file.is_file():
        return paths
    for line in credits_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if parts:
            paths.add(parts[0])
    return paths


def check_image(relative, size, kind, credits, path=None, credit_name=None):
    """Checks that the image of a game data path exists (in the public tree or a content package, or at the given
    path of a wing package), opens as PNG of the given size and is credited: a file of the public tree in CREDITS of
    the repository, a file of a content package in CREDITS of the content repository (CONTENT_CREDITS), by its game
    data path or by credit_name."""
    path = path or content_packages.resolve(root, relative)
    if path.is_file() and not path.resolve().is_relative_to(root.resolve()):
        credits = CONTENT_CREDITS
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
    check((credit_name or relative) in credits, "%s %s has no CREDITS entry" % (kind, credit_name or relative))


def wing1_images(folder):
    """The images of one image folder of wing 1: the public gui/campaign/<folder> and the wing 1 package folder, as
    {path relative to gui/campaign: file}."""
    found = {path.relative_to(art).as_posix(): path for path in (art / folder).glob("*.png")}
    if WING1 is not None:
        for path in (WING1 / folder).glob("*.png"):
            found.setdefault(path.relative_to(WING1).as_posix(), path)
    return found


def check_wing1_image(relative, path, size, kind, credits):
    """Checks a wing 1 image: one of the public tree is credited in CREDITS by its game data path, one of the wing 1
    package in CREDITS of the content repository by its path in the package."""
    if path.is_relative_to(art):
        check_image("gui/campaign/" + relative, size, kind, credits, path)
    else:
        check_image("gui/campaign/" + relative, size, kind, credits, path, relative)


credits = credited_paths()
# CREDITS of the content repository, for the images of the content packages (empty without content)
CONTENT_CREDITS = credited_paths(campaign_packages.content_repository(root))     if campaign_packages.content_repository(root) is not None else set()
world_file = content_packages.data_file(root, "gui/campaign/campaign-world.json")
world = json.loads(world_file.read_text(encoding="utf-8")) if world_file else None

icons = {}
if world is not None:
    check_image("gui/campaign/" + world.get("base", "-"), MAP_SIZE, "map image", credits)
    icons = world.get("icons", {})
    check(len(icons) == EXPECTED_ICONS, "the map must name %d cave markers, found %d" % (EXPECTED_ICONS, len(icons)))
    for relative in icons.values():
        check_image("gui/campaign/" + relative, ICON_SIZE, "cave marker", credits)
else:
    check(not content_packages.has_content(root), "the map description is missing although the content is present")
    content_packages.unchecked("campaign images", ["gui/campaign/campaign-world.json (map and cave markers)"])

# The banners and portraits the packages use, and all public ones in their folders
package_entries = campaign_packages.entries(root)
used_banners = {entry["GuildBanner"] for entry in package_entries if entry.get("GuildBanner")}
used_portraits = {entry["GuildPortrait"] for entry in package_entries if entry.get("GuildPortrait")}
check((len(used_banners), len(used_portraits)) == USED[1:], "the packages must use %d banners and %d portraits"
      % USED[1:])
# The entries whose images are the wing 1 images: a public package and the wing 1 package
public_entries = [entry for entry in package_entries if entry["_public"] or entry["_package"] == WING1]
content_entries = [entry for entry in package_entries if not entry["_public"]]
used_banners = {entry["GuildBanner"] for entry in public_entries if entry.get("GuildBanner")}
used_portraits = {entry["GuildPortrait"] for entry in public_entries if entry.get("GuildPortrait")}
banner_files = wing1_images("banners")
portrait_files = wing1_images("portraits")
banners = sorted(banner_files)
portraits = sorted(portrait_files)
check(used_banners <= set(banners) and used_portraits <= set(portraits),
      "every banner and portrait of a public package must lie in gui/campaign")
if banners or portraits or WING1 is not None:
    check(len(set(banners)) == EXPECTED_BANNERS, "expected %d distinct banners, found %d" % (EXPECTED_BANNERS,
                                                                                           len(set(banners))))
    check(len(set(portraits)) == EXPECTED_PORTRAITS, "expected %d distinct portraits, found %d" % (
        EXPECTED_PORTRAITS, len(set(portraits))))
else:
    check(not content_packages.has_content(root), "the wing 1 package is missing although the content is present")
    content_packages.unchecked("campaign images", ["the banners and portraits of wing 1"])
for relative in banners:
    check_wing1_image(relative, banner_files[relative], BANNER_SIZE, "guild banner", credits)
for relative in portraits:
    check_wing1_image(relative, portrait_files[relative], PORTRAIT_SIZE, "leader portrait", credits)

definition = campaign_packages.definition_text(root)
used_previews = {value.strip() for value in re.findall(r"(?m)^\s*Preview\s*=\s*(\S+)", definition)}
check(len(used_previews) == USED[0], "the packages must use %d distinct previews" % USED[0])
preview_files = wing1_images("previews")
previews = sorted(preview_files)
public_previews = {entry["Preview"].strip() for entry in public_entries if entry.get("Preview")}
check(public_previews <= set(previews), "every preview of a public package must lie in gui/campaign/previews")
if previews or WING1 is not None:
    check(len(set(previews)) == EXPECTED_PREVIEWS, "expected %d distinct previews, found %d" % (EXPECTED_PREVIEWS,
                                                                                               len(set(previews))))
else:
    content_packages.unchecked("campaign images", ["the previews of wing 1"])
for relative in previews:
    check_wing1_image(relative, preview_files[relative], PREVIEW_SIZE, "level preview", credits)

# Images of the private content packages lie in their own package folders and are credited in their CREDITS; the
# counts of wings 2 to 6 are EXPECTED_CONTENT, the wing 1 package brings the wing 1 images counted above
content_counts = (0, 0, 0)
if HAS_CONTENT:
    content_credits = (campaign_packages.content_repository(root) / "CREDITS").read_text(encoding="utf-8")
    kinds = (("Preview", PREVIEW_SIZE, "level preview", "previews"),
             ("GuildBanner", BANNER_SIZE, "guild banner", "banners"),
             ("GuildPortrait", PORTRAIT_SIZE, "leader portrait", "portraits"))
    counts = []
    for key, size, kind, folder in kinds:
        files = sorted({(entry["_package"], entry[key].strip()) for entry in content_entries if entry.get(key)
                        and entry["_package"] != WING1})
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

material_file = content_packages.data_file(root, "materials/scripts/MenuScene.material")
if material_file is not None:
    material = material_file.read_text(encoding="utf-8")
    block = material[material.index("material MenuCampaignMap"):]
    texture = re.search(r"texture\s+(\S+)", block[:block.index("\n}")])
    check(texture is not None and texture.group(1) == Path(HALL_TEXTURE).name,
          "the campaign hall material must use " + Path(HALL_TEXTURE).name)
    check_image(HALL_TEXTURE, MAP_SIZE, "campaign hall texture", credits)
else:
    check(not content_packages.has_content(root), "the hall material is missing although the content is present")
    content_packages.unchecked("campaign images", ["materials/scripts/MenuScene.material", HALL_TEXTURE])

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign image checks passed: 1 map, %d cave markers, %d banners, %d portraits, %d previews and the campaign "
      "hall texture exist with their sizes and CREDITS entries; content packages: %d previews, %d banners, %d "
      "portraits" % ((len(icons), len(set(banners)), len(set(portraits)), len(set(previews))) + content_counts))
