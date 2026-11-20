#!/usr/bin/env python3
"""Makes the placeholder images of the campaign map of Moreya and the campaign hall texture.

The painted art (map, cave markers, guild banners, leader portraits and level previews) is made later
with one fixed brief per image. Until then this script draws clearly marked placeholders under the final
file names, so that the campaign map can be played. Everything is drawn procedurally from the map
description gui/campaign/campaign-world.json and levels/campaign/Campaign.cfg; nothing is random.

The campaign hall of the main menu shows the map of Moreya on its table: its texture
materials/textures/menu/MenuCampaignMap.png is the map image gui/campaign/moreya/moreya_map.png. Run with
--hall-only after the painted map replaced the placeholder to copy it to the hall again.

Usage: python tools/artwork/moreya-map/make_placeholders.py [--hall-only]
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "gui" / "campaign"
WORLD_FILE = ART / "campaign-world.json"
DEFINITION_FILE = ROOT / "levels" / "campaign" / "Campaign.cfg"
HALL_TEXTURE = ROOT / "materials" / "textures" / "menu" / "MenuCampaignMap.png"
FONT_FILE = ROOT / "gui" / "fonts" / "SourceSerif4-Semibold.ttf"

# Sizes of the images in pixels (width, height)
ICON_SIZE = (128, 128)
BANNER_SIZE = (160, 320)
PORTRAIT_SIZE = (256, 256)
PREVIEW_SIZE = (640, 360)
# Colours of the style guide: ember orange, deep red, muted gold, Moreya green, dark stone grey
EMBER = (214, 104, 36)
DEEP_RED = (112, 22, 20)
GOLD = (196, 160, 82)
GREEN = (70, 190, 90)
STONE = (46, 44, 48)
DARK = (14, 12, 15)
PARCHMENT = (230, 211, 163)
MARK = "PLACEHOLDER"


def font(size):
    """The UI font of the game in the given pixel size."""
    return ImageFont.truetype(str(FONT_FILE), size)


def read_levels():
    """Reads the level entries (File, Title, Wing, Bonus) of the campaign definition."""
    levels = []
    for block in DEFINITION_FILE.read_text(encoding="utf-8").replace("\r", "").split("\n[Level]")[1:]:
        fields = {}
        for line in block.splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
        levels.append(fields)
    return levels


def centred_text(draw, box, text, size, colour):
    """Writes the lines of text centred in the box (x0, y0, x1, y1)."""
    face = font(size)
    lines = text.split("\n")
    heights = [draw.textbbox((0, 0), line, font=face)[3] for line in lines]
    total = sum(heights) + (len(lines) - 1) * size // 4
    y = box[1] + (box[3] - box[1] - total) // 2
    for line, height in zip(lines, heights):
        width = draw.textlength(line, font=face)
        draw.text((box[0] + (box[2] - box[0] - width) / 2, y), line, font=face, fill=colour)
        y += height + size // 4


def plaque(draw, rect, outline=GOLD):
    """A dark plaque with a gold border at the rectangle [x, y, width, height]."""
    x, y, w, h = rect
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(24, 20, 22), outline=outline, width=4)


def make_map(world):
    """The placeholder map: the surface with the gate in front of which the guild stands, the 6 wings with
    their caves joined by the descent from the gate, the plaques of title, progress and guild."""
    width, height = world["size"]
    image = Image.new("RGBA", (width, height), DARK + (255,))
    draw = ImageDraw.Draw(image)
    # Rock getting darker towards the depths, the surface band above the gate
    for y in range(height):
        shade = max(0, 34 - y * 26 // height)
        draw.line((0, y, width, y), fill=(shade + 8, shade + 6, shade + 10, 255))
    draw.rectangle((0, 0, width, 420), fill=(30, 27, 34, 255))
    draw.line((0, 420, width, 420), fill=STONE + (255,), width=6)

    for wing in world["wings"]:
        x, y, w, h = wing["area"]
        draw.rounded_rectangle((x, y, x + w, y + h), radius=36, fill=(44, 22, 24, 255), outline=DEEP_RED + (255,),
                               width=6)

    # The descent: from the gate along the gap above the wings to the first cave of wing 1, then from the last cave
    # of each wing to the first cave of the next one; down to the lower row along the right edge of the map
    gate_x, gate_y = world["gate"]
    first = world["wings"][0]["levels"][0]["pos"]
    top = world["wings"][0]["area"][1] - 4
    descent = [(gate_x, gate_y + 120), (gate_x, top), (first[0], top)]
    for index, wing in enumerate(world["wings"]):
        start = tuple(wing["levels"][0]["pos"])
        if index > 0 and start[1] != descent[-1][1]:
            edge = width - 30
            descent.extend([(edge, descent[-1][1]), (edge, start[1])])
        descent.append(start)
        descent.append(tuple(wing["levels"][-1]["pos"]))
    draw.line(descent, fill=EMBER + (255,), width=10, joint="curve")

    for wing in world["wings"]:
        # The tunnel through the caves of the wing. The bonus cave is a secret: the map image does not show it,
        # only its marker once its stone was found.
        points = [tuple(level["pos"]) for level in wing["levels"]]
        draw.line(points, fill=(70, 50, 40, 255), width=18)
        for level in wing["levels"]:
            cx, cy = level["pos"]
            radius = level["size"] // 2
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(10, 8, 10, 255))

    # The gate of Moreya with its green light
    draw.rectangle((gate_x - 150, gate_y - 130, gate_x + 150, gate_y + 120), fill=STONE + (255,))
    draw.pieslice((gate_x - 150, gate_y - 230, gate_x + 150, gate_y - 30), 180, 360, fill=STONE + (255,))
    draw.rectangle((gate_x - 90, gate_y - 60, gate_x + 90, gate_y + 120), fill=(20, 60, 28, 255))
    draw.pieslice((gate_x - 90, gate_y - 150, gate_x + 90, gate_y + 30), 180, 360, fill=(20, 60, 28, 255))
    draw.rectangle((gate_x - 60, gate_y - 30, gate_x + 60, gate_y + 120), fill=GREEN + (255,))

    plaque(draw, world["title_cartouche"])
    plaque(draw, world["progress_panel"])
    plaque(draw, world["guild_panel"]["area"])
    centred_text(draw, (40, height - 110, 900, height - 20), MARK + " - campaign map of Moreya", 40, PARCHMENT)
    return image


def make_icon(kind):
    """A cave marker or seal, without text."""
    image = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    size = ICON_SIZE[0]
    box = (8, 8, size - 8, size - 8)
    inner = (30, 30, size - 30, size - 30)
    if kind == "locked":
        draw.ellipse(box, fill=(60, 58, 62, 255), outline=(120, 116, 110, 255), width=6)
        draw.ellipse(inner, fill=(18, 16, 18, 255))
    elif kind == "current":
        draw.ellipse((0, 0, size, size), fill=EMBER + (120,))
        draw.ellipse(box, fill=EMBER + (255,), outline=GOLD + (255,), width=8)
        draw.ellipse(inner, fill=GREEN + (255,))
    elif kind == "defeated":
        draw.ellipse(box, fill=DEEP_RED + (255,), outline=GOLD + (255,), width=6)
        draw.line((36, 66, 56, 88, 94, 40), fill=GOLD + (255,), width=12)
    elif kind == "bonus_found":
        draw.regular_polygon((size // 2, size // 2, size // 2 - 8), 6, fill=(30, 90, 50, 255), outline=GOLD + (255,))
        draw.ellipse(inner, fill=GREEN + (255,))
    elif kind == "bonus_cleared":
        draw.regular_polygon((size // 2, size // 2, size // 2 - 8), 6, fill=(30, 90, 50, 255), outline=GOLD + (255,))
        draw.line((36, 66, 56, 88, 94, 40), fill=GOLD + (255,), width=12)
    elif kind == "wing_defeated":
        draw.ellipse(box, fill=DEEP_RED + (255,), outline=GOLD + (255,), width=8)
        draw.regular_polygon((size // 2, size // 2, 34), 5, fill=GOLD + (255,))
    elif kind == "hover":
        draw.ellipse((4, 4, size - 4, size - 4), outline=GOLD + (255,), width=8)
    return image


def guild_colour(index):
    """A distinct dark colour per guild for its placeholder banner."""
    palette = [(120, 30, 30), (40, 70, 120), (60, 100, 50), (110, 80, 30), (80, 40, 100), (30, 90, 100)]
    base = palette[index % len(palette)]
    shade = 1.0 - 0.25 * (index // len(palette))
    return tuple(int(c * shade) for c in base)


def make_banner(guild, index):
    """A plain banner in the guild's colour with a simple emblem and the placeholder mark."""
    image = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    width, height = BANNER_SIZE
    colour = guild_colour(index) + (255,)
    draw.rectangle((10, 0, width - 10, 8), fill=(70, 50, 30, 255))
    draw.polygon([(16, 8), (width - 16, 8), (width - 16, height - 10), (width // 2, height - 50), (16, height - 10)],
                 fill=colour, outline=GOLD + (255,))
    draw.regular_polygon((width // 2, 110, 40), 3 + index % 4, fill=GOLD + (255,))
    centred_text(draw, (16, 170, width - 16, 230), MARK, 18, PARCHMENT + (255,))
    return image


def make_portrait(leader):
    """A bust silhouette with the leader's name and the placeholder mark."""
    image = Image.new("RGBA", PORTRAIT_SIZE, (34, 28, 30, 255))
    draw = ImageDraw.Draw(image)
    width, height = PORTRAIT_SIZE
    draw.rectangle((0, 0, width - 1, height - 1), outline=GOLD + (255,), width=6)
    draw.ellipse((88, 40, 168, 130), fill=(70, 62, 60, 255))
    draw.pieslice((40, 130, 216, 300), 180, 360, fill=(70, 62, 60, 255))
    centred_text(draw, (8, 196, width - 8, 250), MARK + "\n" + leader, 18, PARCHMENT + (255,))
    return image


def make_preview(title, subtitle):
    """A dark scene with the gate, the level title and the placeholder mark, 640 x 360 in a palette."""
    width, height = PREVIEW_SIZE
    image = Image.new("RGB", PREVIEW_SIZE, DARK)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = 14 + y * 30 // height
        draw.line((0, y, width, y), fill=(shade + 10, shade // 2 + 6, shade // 2 + 4))
    draw.rectangle((250, 120, 390, 300), fill=STONE)
    draw.rectangle((285, 170, 355, 300), fill=GREEN)
    centred_text(draw, (0, 20, width, 110), title + "\n" + subtitle, 26, PARCHMENT)
    centred_text(draw, (0, 300, width, 350), MARK, 24, GOLD)
    return image.quantize(colors=64)


def preview_names(levels):
    """Maps each level file to its preview file name, its title and its place in the wing."""
    names = {}
    counters = {}
    for fields in levels:
        wing = fields["Wing"]
        if fields.get("Bonus") == "1":
            names[fields["File"]] = ("previews/wing%s-bonus.png" % wing, fields["Title"], "Bonus cave of wing " + wing)
        else:
            counters[wing] = counters.get(wing, 0) + 1
            names[fields["File"]] = ("previews/wing%s-level%d.png" % (wing, counters[wing]), fields["Title"],
                                     "Wing %s, level %d" % (wing, counters[wing]))
    return names


def hall_texture():
    """The texture of the campaign hall's table: the map image of Moreya."""
    return Image.open(ART / "moreya" / "moreya_map.png").convert("RGBA")


def save(image, relative):
    """Writes an image below the campaign art directory and names it."""
    path = ART / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print("wrote", path.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hall-only", action="store_true", help="only copy the map image to the hall texture")
    args = parser.parse_args()
    world = json.loads(WORLD_FILE.read_text(encoding="utf-8"))
    if not args.hall_only:
        save(make_map(world), world["base"])
        for key, relative in world["icons"].items():
            save(make_icon(key), relative)
        index = 0
        for wing in world["wings"]:
            for level in wing["levels"]:
                guild = level["guild"]
                save(make_banner(guild, index), guild["banner"])
                save(make_portrait(guild["leader"]), guild["portrait"])
                index += 1
        for file, (relative, title, subtitle) in sorted(preview_names(read_levels()).items()):
            save(make_preview(title, subtitle), relative)
    hall_texture().save(HALL_TEXTURE, optimize=True)
    print("wrote", HALL_TEXTURE.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
