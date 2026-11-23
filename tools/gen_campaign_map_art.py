#!/usr/bin/env python3
"""Build the carved stone campaign map of Moreya and the art drawn on it from their sources.

The campaign map (layout variant B) is carved into stone: on the top of the stone table in the campaign hall of the
main menu and as the clickable full screen map. The carved version of the painted map was made with the image
generation of OpenAI Codex from an own written brief (asset source moreya_map_carved_codex_raw.png in
$ODP_ASSETS_SRC/gui/campaign-map-carved, next to the painted map it was made from and the brief); its layout is that
of the painted map, so the cave markers of gui/campaign/campaign-world.json stay where they were. This script writes:

- gui/campaign/moreya/moreya_map.png (2560 x 1600): the carved map as the top of the stone table in the campaign
  hall: inside TABLE_CROP the carved map scaled up to the map size and slightly sharpened, around it the edge of the
  stone table and the hall floor of the menu scene (asset source moreya_map_table_render.png next to the carved map,
  rendered from the menu meshes by tools/render_campaign_map_table.py), stretched so that the table top of the
  render is exactly TABLE_CROP, toned like the hall floor in the game and darkened towards the edges, so the title,
  the progress and the guild panel read on it; the rock around the carved map frame is no longer shown there;
- materials/textures/menu/MenuCampaignMap.png (2560 x 1600): the carved map frame, TABLE_CROP, which covers the whole
  table top (the table is fitted to its aspect ratio by tools/menu_table_map_plane.py), stretched to the map size; the
  plane maps it back to its own aspect ratio;
- gui/campaign/moreya/wing<N>_locked.png: for every wing a greyed out, darkened copy of its basin (WING_BASINS, outlines
  traced on the map, feathered), drawn over a wing that is still locked; the place of each is written into the map
  description as "locked" (image and area);
- the art of the map in the carved stone look, all drawn here: tooltip_plaque.png (the stone tablet of the hover
  display), guild_plaque.png (the stone slab of the guild panel with a niche for the banner and a frame round the
  portrait), current_glow.png (the golden glow under the current level), current_pointer.png (the golden arrow above
  it) and raid_ember.png (an ember of the trail of the attacking guild to the current level).

    python tools/gen_campaign_map_art.py [<repo>]

The result depends only on the sources and the fixed values below.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import assets_src  # noqa: E402

#: Asset source of the carved map (Codex output at its own resolution) and the size of the map.
CARVED_SOURCE = "assets-src/gui/campaign-map-carved/moreya_map_carved_codex_raw.png"
MAP_SIZE = (2560, 1600)
#: Asset source of the table and the hall floor around the map (tools/render_campaign_map_table.py; a JSON file of the
#: same name gives the pixels of the corners of the map plane in it).
TABLE_RENDER = "assets-src/gui/campaign-map-carved/moreya_map_table_render.png"
#: The carved map frame in map pixels (x, y, width, height); outside it the rock darkens towards the edges.
MAP_FRAME = (395, 410, 1765, 1000)
#: Share of brightness kept at the map edges and the width of the transition in map pixels.
EDGE_DARKEN = 0.62
EDGE_FEATHER = 260.0
#: Tone of the hall floor and the table edge around the table top of the full screen map (mean and spread of every
#: colour channel, 0..1), the dark warm stone of the hall floor in the game, and the share of brightness kept at the
#: screen edges (over FLOOR_FEATHER map pixels from the table top).
FLOOR_MEAN = np.array([0.196, 0.133, 0.118])
FLOOR_SPREAD = np.array([0.058, 0.040, 0.035])
FLOOR_EDGE_DARKEN = 0.72
FLOOR_FEATHER = 420.0
#: The part of the map on the table top (x, y, width, height): exactly the carved map frame, no stone around it; the
#: table follows its aspect ratio (map plane 6.15 x 3.44, tools/menu_table_map_plane.py).
TABLE_CROP = (400, 418, 1752, 980)
#: Outlines of the six wing basins of the map in map pixels, traced on the map; a wing gets the basin that holds its
#: caves. Feather of their edge and the brightness and saturation kept when a wing is locked.
WING_BASINS = (
    ((422, 531), (461, 474), (550, 448), (666, 442), (768, 461), (896, 461), (1024, 480), (1114, 512), (1139, 576),
     (1126, 666), (1088, 717), (1024, 730), (973, 736), (896, 730), (819, 710), (717, 717), (614, 698), (538, 666),
     (474, 627), (429, 582)),
    ((1408, 486), (1472, 448), (1613, 442), (1766, 448), (1920, 461), (2010, 512), (2035, 576), (2022, 666),
     (1971, 717), (1869, 736), (1766, 742), (1664, 730), (1562, 736), (1472, 717), (1421, 666), (1402, 589)),
    ((416, 781), (442, 749), (538, 755), (666, 742), (768, 755), (870, 768), (934, 819), (947, 883), (922, 960),
     (858, 1011), (768, 1024), (666, 1011), (563, 1062), (486, 1062), (429, 1011), (410, 922), (407, 845)),
    ((1574, 781), (1651, 742), (1766, 755), (1856, 742), (1997, 755), (2099, 768), (2138, 845), (2131, 947),
     (2099, 1024), (1997, 1050), (1869, 1037), (1766, 1024), (1664, 1011), (1600, 973), (1562, 896), (1555, 832)),
    ((499, 1126), (576, 1060), (717, 1040), (845, 1030), (973, 1025), (1101, 1060), (1203, 1101), (1235, 1178),
     (1216, 1280), (1152, 1331), (973, 1357), (819, 1344), (666, 1357), (563, 1331), (512, 1267), (493, 1190)),
    ((1293, 1126), (1357, 1069), (1485, 1050), (1613, 1043), (1766, 1043), (1920, 1062), (2022, 1101), (2067, 1178),
     (2048, 1267), (1984, 1331), (1843, 1357), (1664, 1344), (1510, 1357), (1382, 1331), (1306, 1267), (1280, 1190)),
)
BASIN_FEATHER = 14.0
LOCKED_BRIGHTNESS = 0.48
LOCKED_SATURATION = 0.0
LOCKED_TINT = np.array([0.95, 0.96, 1.0])
#: Light direction of the carved art (from the top left, as on the map) and the gold and ember colours.
LIGHT = np.array([-0.5, -0.55, 0.67])
GOLD = np.array([1.0, 0.80, 0.38])
EMBER = np.array([1.0, 0.36, 0.08])


def blur(values, sigma):
    """Returns a gaussian blur of a 2D array (sigma in pixels), computed in the frequency domain."""
    height, width = values.shape
    frequency_v = np.fft.fftfreq(height)[:, None]
    frequency_u = np.fft.rfftfreq(width)[None, :]
    kernel = np.exp(-2.0 * (np.pi * sigma) ** 2 * (frequency_u ** 2 + frequency_v ** 2))
    return np.fft.irfft2(np.fft.rfft2(values) * kernel, s=(height, width))


def rounded_box(width, height, box, radius):
    """Returns the signed distance (negative inside) of every pixel to a rounded rectangle (x, y, w, h)."""
    y, x = np.mgrid[0:height, 0:width].astype(np.float64) + 0.5
    centre_x, centre_y = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
    qx = np.abs(x - centre_x) - (box[2] / 2.0 - radius)
    qy = np.abs(y - centre_y) - (box[3] / 2.0 - radius)
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    return outside + np.minimum(np.maximum(qx, qy), 0.0) - radius


def shade(height_field, strength):
    """Returns the lambert shading (0..1) of a height field lit from LIGHT."""
    gradient_y, gradient_x = np.gradient(height_field)
    normal = np.stack((-gradient_x * strength, -gradient_y * strength, np.ones_like(height_field)), axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    light = LIGHT / np.linalg.norm(LIGHT)
    return np.clip(normal @ light, 0.0, 1.0)


def stone_patch(stone, width, height, offset):
    """Returns a width x height patch of the stone texture (tiled), starting at offset."""
    reps_y = (height + offset[1]) // stone.shape[0] + 1
    reps_x = (width + offset[0]) // stone.shape[1] + 1
    tiled = np.tile(stone, (reps_y, reps_x, 1))
    return tiled[offset[1]:offset[1] + height, offset[0]:offset[0] + width]


def carved_plaque(stone, width, height, radius, bevel, recesses, offset, lift=1.0):
    """Returns an RGBA carved stone tablet: a raised slab with a bevelled edge, recessed frames (x, y, w, h, radius)
    cut into it, a soft shadow round it, the stone texture over it."""
    margin = 10.0
    slab = rounded_box(width, height, (margin, margin, width - 2 * margin, height - 2 * margin), radius)
    relief = np.clip(-slab / bevel, 0.0, 1.0)
    relief = relief * relief * (3.0 - 2.0 * relief)
    for recess in recesses:
        cut = rounded_box(width, height, recess[:4], recess[4])
        depth = np.clip(-cut / (bevel * 0.6), 0.0, 1.0)
        relief = relief - 0.7 * depth * depth * (3.0 - 2.0 * depth)
    light = shade(relief * bevel, 1.2)
    texture = stone_patch(stone, width, height, offset)
    colour = texture * (0.55 + 0.9 * light)[:, :, None] * lift
    # The recesses are darker, the rim catches a little more light
    for recess in recesses:
        inside = np.clip(-rounded_box(width, height, recess[:4], recess[4]) / 6.0, 0.0, 1.0)
        colour = colour * (1.0 - 0.45 * inside)[:, :, None]
    alpha = np.clip(0.5 - slab, 0.0, 1.0)
    shadow = np.clip(1.0 - np.maximum(slab, 0.0) / margin, 0.0, 1.0) * 0.55 * (1.0 - alpha)
    rgba = np.zeros((height, width, 4))
    rgba[:, :, :3] = colour * alpha[:, :, None]
    rgba[:, :, 3] = alpha + shadow
    rgba[:, :, :3] /= np.maximum(rgba[:, :, 3:4], 1e-6)
    return rgba


def save_rgba(rgba, path):
    """Writes an RGBA array (0..1) as PNG."""
    Image.fromarray(np.round(np.clip(rgba, 0.0, 1.0) * 255.0).astype(np.uint8), "RGBA").save(path, optimize=True)


def table_surroundings(root):
    """Returns the table edge and the hall floor around the table top as RGB array (0..1) of the map size: the table
    render stretched so that its map plane covers exactly TABLE_CROP, toned to FLOOR_MEAN and FLOOR_SPREAD outside the
    table top and darkened towards the screen edges."""
    render_path = assets_src.resolve(root, TABLE_RENDER)
    render = Image.open(render_path).convert("RGB")
    corners = json.load(open(os.path.splitext(str(render_path))[0] + ".json", encoding="utf-8"))["map_plane_corners"]
    render_left = min(corner[0] for corner in corners)
    render_right = max(corner[0] for corner in corners)
    render_top = min(corner[1] for corner in corners)
    render_bottom = max(corner[1] for corner in corners)
    left, top, width, height = TABLE_CROP
    scale_x = (render_right - render_left) / float(width)
    scale_y = (render_bottom - render_top) / float(height)
    # Map pixel (x, y) shows render pixel (render_left + (x - left) * scale_x, render_top + (y - top) * scale_y)
    stretched = render.transform(MAP_SIZE, Image.AFFINE, (scale_x, 0.0, render_left - left * scale_x,
                                                          0.0, scale_y, render_top - top * scale_y), Image.BICUBIC)
    colours = np.asarray(stretched, dtype=np.float64) / 255.0
    outside = rounded_box(MAP_SIZE[0], MAP_SIZE[1], TABLE_CROP, 0.5) > 0.0
    mean = colours[outside].mean(axis=0)
    spread = colours[outside].std(axis=0)
    toned = np.clip((colours - mean) * (FLOOR_SPREAD / spread) + FLOOR_MEAN, 0.0, 1.0)
    distance = rounded_box(MAP_SIZE[0], MAP_SIZE[1], TABLE_CROP, 0.5)
    keep = 1.0 - (1.0 - FLOOR_EDGE_DARKEN) * np.clip(distance / FLOOR_FEATHER, 0.0, 1.0)
    return toned * keep[:, :, None]


def build_map(root):
    """Writes the full screen map (the carved map as the table top in the hall) and the table texture; returns the
    carved map with its rock around the frame as RGB array (0..1), the stone of the locked wings and the plaques."""
    source = Image.open(assets_src.resolve(root, CARVED_SOURCE)).convert("RGB")
    scaled = source.resize(MAP_SIZE, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    colours = np.asarray(scaled, dtype=np.float64) / 255.0
    frame = rounded_box(MAP_SIZE[0], MAP_SIZE[1], MAP_FRAME, 20.0)
    keep = 1.0 - (1.0 - EDGE_DARKEN) * np.clip(frame / EDGE_FEATHER, 0.0, 1.0)
    colours = colours * keep[:, :, None]
    # The full screen map: the carved map frame (TABLE_CROP) unchanged, around it the table edge and the hall floor
    left, top, width, height = TABLE_CROP
    screen = table_surroundings(root)
    screen[top:top + height, left:left + width] = colours[top:top + height, left:left + width]
    folder = os.path.join(root, "gui", "campaign", "moreya")
    Image.fromarray(np.round(screen * 255.0).astype(np.uint8), "RGB").save(os.path.join(folder, "moreya_map.png"),
                                                                           optimize=True)
    table = Image.fromarray(np.round(colours * 255.0).astype(np.uint8), "RGB")
    table = table.crop((left, top, left + width, top + height)).resize(MAP_SIZE, Image.LANCZOS)
    table.save(os.path.join(root, "materials", "textures", "menu", "MenuCampaignMap.png"), optimize=True)
    return colours


def build_locked_wings(root, colours):
    """Writes the greyed out basin of every wing and returns {wing number: [x, y, w, h]} of their images."""
    world = json.load(open(os.path.join(root, "gui", "campaign", "campaign-world.json"), encoding="utf-8"))
    areas = {}
    for wing in world["wings"]:
        caves = [cave["pos"] for cave in wing["levels"]]
        basin = None
        for outline in WING_BASINS:
            mask = Image.new("L", MAP_SIZE, 0)
            ImageDraw.Draw(mask).polygon(outline, fill=255)
            if all(mask.getpixel((x, y)) for x, y in caves):
                basin = outline
                break
        if basin is None:
            raise ValueError("no basin holds the caves of wing %d" % wing["wing"])
        xs = [point[0] for point in basin]
        ys = [point[1] for point in basin]
        pad = int(BASIN_FEATHER * 3)
        box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        mask = Image.new("L", MAP_SIZE, 0)
        ImageDraw.Draw(mask).polygon(basin, fill=255)
        mask = mask.crop(box).filter(ImageFilter.GaussianBlur(BASIN_FEATHER))
        alpha = np.asarray(mask, dtype=np.float64) / 255.0
        part = colours[box[1]:box[3], box[0]:box[2]]
        grey = (part @ np.array([0.299, 0.587, 0.114]))[:, :, None]
        locked = (grey + (part - grey) * LOCKED_SATURATION) * LOCKED_BRIGHTNESS * LOCKED_TINT
        rgba = np.concatenate((locked, alpha[:, :, None]), axis=2)
        name = "wing%d_locked.png" % wing["wing"]
        save_rgba(rgba, os.path.join(root, "gui", "campaign", "moreya", name))
        areas[wing["wing"]] = [box[0], box[1], box[2] - box[0], box[3] - box[1]]
    return areas


def build_ui_art(root, colours):
    """Writes the plaques, the glow, the pointer and the ember of the map."""
    folder = os.path.join(root, "gui", "campaign", "moreya")
    # Stone of the plaques: the rock of the map below its frame, a little lighter than the rock around it
    stone = colours[1440:1600, 0:2560] * 1.35
    save_rgba(carved_plaque(stone, 512, 200, 26.0, 9.0, [(30, 26, 452, 148, 16.0)], (37, 5), 1.0),
              os.path.join(folder, "tooltip_plaque.png"))
    world = json.load(open(os.path.join(root, "gui", "campaign", "campaign-world.json"), encoding="utf-8"))
    panel = world["guild_panel"]
    area = panel["area"]

    def local(rect, grow, radius):
        """Returns a panel rectangle in plaque pixels, grown by grow on every side, with its corner radius."""
        return (rect[0] - area[0] - grow, rect[1] - area[1] - grow, rect[2] + 2 * grow, rect[3] + 2 * grow, radius)

    recesses = [local(panel["banner"], 8, 14.0), local(panel["portrait"], 12, 10.0),
                local([panel["name"][0], panel["name"][1] + 30, panel["name"][2], 120], 0, 18.0),
                local(panel["details"], 0, 18.0)]
    save_rgba(carved_plaque(stone, area[2], area[3], 34.0, 14.0, recesses, (900, 12), 1.0),
              os.path.join(folder, "guild_plaque.png"))
    # Golden glow under the current level: a soft disc with a brighter ring
    size = 256
    y, x = np.mgrid[0:size, 0:size].astype(np.float64) + 0.5
    radius = np.hypot(x - size / 2.0, y - size / 2.0) / (size / 2.0)
    glow = 0.75 * np.exp(-(radius / 0.55) ** 2) + 0.6 * np.exp(-((radius - 0.62) / 0.12) ** 2)
    glow *= np.clip((1.0 - radius) * 6.0, 0.0, 1.0)
    rgba = np.zeros((size, size, 4))
    rgba[:, :, :3] = GOLD
    rgba[:, :, 3] = np.clip(glow, 0.0, 1.0)
    save_rgba(rgba, os.path.join(folder, "current_glow.png"))
    # Golden arrow pointing down at the current level, drawn large and scaled down, with a soft glow
    scale = 4
    width, height = 128, 160
    big = Image.new("L", (width * scale, height * scale), 0)
    arrow = [(64, 150), (14, 82), (44, 82), (44, 14), (84, 14), (84, 82), (114, 82)]
    ImageDraw.Draw(big).polygon([(px * scale, py * scale) for px, py in arrow], fill=255)
    shape = np.asarray(big.resize((width, height), Image.LANCZOS), dtype=np.float64) / 255.0
    relief = blur(shape, 3.0)
    light = shade(relief * 12.0, 1.0)
    halo = np.clip(blur(shape, 7.0) * 1.6, 0.0, 1.0)
    rgba = np.zeros((height, width, 4))
    rgba[:, :, :3] = GOLD * (0.45 + 0.85 * light)[:, :, None]
    rgba[:, :, :3] = rgba[:, :, :3] * shape[:, :, None] + GOLD * (1.0 - shape[:, :, None])
    rgba[:, :, 3] = np.maximum(shape, halo * 0.55)
    save_rgba(rgba, os.path.join(folder, "current_pointer.png"))
    # Ember of the raid trail: a hot core in a red orange halo
    size = 64
    y, x = np.mgrid[0:size, 0:size].astype(np.float64) + 0.5
    radius = np.hypot(x - size / 2.0, y - size / 2.0) / (size / 2.0)
    rgba = np.zeros((size, size, 4))
    core = np.exp(-(radius / 0.28) ** 2)
    rgba[:, :, :3] = EMBER * (1.0 - core[:, :, None]) + np.array([1.0, 0.85, 0.5]) * core[:, :, None]
    rgba[:, :, 3] = np.clip(np.exp(-(radius / 0.55) ** 2) * np.clip((1.0 - radius) * 5.0, 0.0, 1.0), 0.0, 1.0)
    save_rgba(rgba, os.path.join(folder, "raid_ember.png"))


def main():
    """Builds every image and writes the places of the locked wing images into the map description."""
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".."))
    colours = build_map(root)
    areas = build_locked_wings(root, colours)
    build_ui_art(root, colours)
    path = os.path.join(root, "gui", "campaign", "campaign-world.json")
    world = json.load(open(path, encoding="utf-8"))
    for wing in world["wings"]:
        wing["locked"] = {"image": "moreya/wing%d_locked.png" % wing["wing"], "area": areas[wing["wing"]]}
    with open(path, "w", encoding="utf-8", newline="\n") as target:
        json.dump(world, target, indent=2)
        target.write("\n")
    print("wrote the carved map, the table texture, %d locked wings and the map art" % len(areas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
