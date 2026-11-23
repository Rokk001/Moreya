#!/usr/bin/env python3
"""Build the carved stone campaign map of Moreya and the art drawn on it from their sources.

The campaign map (layout variant B) is carved into stone: on the top of the stone table in the campaign hall of the
main menu and as the clickable full screen map. The carved version of the painted map was made with the image
generation of OpenAI Codex from an own written brief (asset source moreya_map_carved_codex_raw.png in
$ODP_ASSETS_SRC/gui/campaign-map-carved, next to the painted map it was made from and the brief); its layout is that
of the painted map, so the places of the flat layout (tools/campaign_map_flat_layout.json, on the flat carved map with
its frame on TABLE_CROP) stay on their caves. This script writes:

- gui/campaign/moreya/moreya_map.png (2560 x 1600): the stone table of the campaign hall as a solid table with length,
  width and height: the carved map texture (MenuCampaignMap.png, below) set into its top inside the cut-off corners,
  the stone rim and side faces of the thick slab round it, its front side, trestles and shadow and the hall floor
  (asset source moreya_map_table_render.png next to the carved map, rendered from the menu meshes by
  tools/render_campaign_map_table.py), scaled to the map size, seen in perspective; outside the carved map it
  darkens towards the screen edges, so the title,
  the progress and the guild panel read on it; nothing is laid over the table and the rock around the carved map
  frame is not shown;
- the places of the map description gui/campaign/campaign-world.json (gate, wing areas, wing labels, seals, caves and
  bonus caves): the places of the flat layout mapped through the view of the render onto the map plane
  (map_plane_projection), so every marker stays on its cave of the carved map; sizes stay;
- materials/textures/menu/MenuCampaignMap.png (2560 x 1600): the carved map frame, TABLE_CROP, which covers the whole
  table top (the table is fitted to its aspect ratio by tools/menu_table_map_plane.py), stretched to the map size; the
  plane maps it back to its own aspect ratio;
- gui/campaign/moreya/wing<N>_locked.png: for every wing a greyed out, darkened copy of its basin (WING_BASINS, outlines
  traced on the flat map, feathered, mapped onto the map plane) of the full screen map, drawn over a wing that is
  still locked; the place of each is written into the map description as "locked" (image and area);
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
#: The map plane on the table (width and depth in mesh units), the cut-off of its corners, the width over which the
#: carving fades into the slab towards the outline of the table top and the size of one tile of the slab stone.
MAP_PLANE = (6.15, 3.44)
MAP_PLANE_CHAMFER = 0.6
SLAB_FADE = 0.15
SLAB_TILE = 2.0
#: The flat layout of the map description (places on the flat carved map) and the y of the centre of the map plane on
#: the table in the scene (tools/render_campaign_map_table.py: table at y 22).
FLAT_LAYOUT = os.path.join("tools", "campaign_map_flat_layout.json")
TABLE_CENTRE_Y = 22.0
#: The cut-off corners of the table top on the flat map (map pixels along both edges from every corner of TABLE_CROP):
#: the chamfer of 0.6 mesh units of tools/menu_table_map_chamfer.py on the 6.15 x 3.44 map plane.
MAP_CHAMFER = 0.6 / 6.15 * 1752.0
#: Size of a level cave and of a bonus cave marker on the flat map (map pixels).
FLAT_CAVE_SIZES = {"level": 72, "bonus": 64}
#: Share of the size of a cave that the area of its wing holds round it (the hover display of a cave has its size,
#: HOVER_SCALE of source/modes/MenuModeCampaign.cpp).
CAVE_REACH = 1.0
#: Share of brightness of the table render kept at the screen edges (over FLOOR_FEATHER map pixels from the table top).
FLOOR_EDGE_DARKEN = 0.85
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


def map_plane_projection(root):
    """Returns how the render lies on the full screen map: a function that maps a point (x, y) of the flat map (the
    carved map frame on TABLE_CROP) to the full screen map point where the same spot of the carved map lies, the
    corners of the map plane there (an octagon with cut-off corners, in outline order) and the affine placement of the
    render (scale_x, scale_y, offset_x, offset_y: map pixel = render pixel * scale + offset). The render is the full
    screen map at a larger size (render_scale of its JSON file), seen in perspective; the function is the homography
    through the corners of the map plane (the JSON file of the render gives them with their places on the table)."""
    render_path = assets_src.resolve(root, TABLE_RENDER)
    description = json.load(open(os.path.splitext(str(render_path))[0] + ".json", encoding="utf-8"))
    points = description["map_plane_corners"]
    left, top, width, height = TABLE_CROP
    # The render is the full screen map, RENDER_SCALE times its size
    scale = 1.0 / description["render_scale"]
    placement = (scale, scale, 0.0, 0.0)
    half_width = max(abs(point[2]) for point in points)
    half_depth = max(abs(point[3] - TABLE_CENTRE_Y) for point in points)
    rows = []
    values = []
    outline = []
    for pixel_x, pixel_y, world_x, world_y in points:
        # The left of the map lies at -x of the table, its top (the gate) at the far side, +y
        x = left + (world_x + half_width) / (2.0 * half_width) * width
        y = top + (half_depth - (world_y - TABLE_CENTRE_Y)) / (2.0 * half_depth) * height
        u = pixel_x * placement[0] + placement[2]
        v = pixel_y * placement[1] + placement[3]
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.extend([u, v])
        outline.append((u, v))
    solution = np.linalg.lstsq(np.array(rows), np.array(values), rcond=None)[0]
    homography = np.append(solution, 1.0).reshape(3, 3)

    def project(point):
        """Returns the full screen map point of a flat map point."""
        mapped = homography @ np.array([point[0], point[1], 1.0])
        return (mapped[0] / mapped[2], mapped[1] / mapped[2])

    centre_x = sum(point[0] for point in outline) / len(outline)
    centre_y = sum(point[1] for point in outline) / len(outline)

    def angle(point):
        """Returns the angle of a corner round the centre of the map plane (outline order)."""
        return np.arctan2(point[1] - centre_y, point[0] - centre_x)

    outline.sort(key=angle)
    return project, outline, placement


def table_view(root, outline, placement):
    """Returns the stone table in the hall as RGB array (0..1) of the map size: the table render placed by placement
    (map pixel = render pixel * scale + offset), darkened towards the screen edges outside the box of the carved map
    (outline, the corners of the map plane); table, floor and walls keep the light and contrast of the render."""
    render = Image.open(assets_src.resolve(root, TABLE_RENDER)).convert("RGB")
    scale_x, scale_y, offset_x, offset_y = placement
    # Map pixel (x, y) shows render pixel ((x - offset_x) / scale_x, (y - offset_y) / scale_y)
    placed = render.transform(MAP_SIZE, Image.AFFINE, (1.0 / scale_x, 0.0, -offset_x / scale_x,
                                                       0.0, 1.0 / scale_y, -offset_y / scale_y), Image.BICUBIC)
    colours = np.asarray(placed, dtype=np.float64) / 255.0
    mask = Image.new("L", MAP_SIZE, 0)
    ImageDraw.Draw(mask).polygon([(point[0], point[1]) for point in outline], fill=255)
    inside = np.asarray(mask, dtype=np.float64) / 255.0
    xs = [point[0] for point in outline]
    ys = [point[1] for point in outline]
    box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    distance = rounded_box(MAP_SIZE[0], MAP_SIZE[1], box, 0.5)
    keep = 1.0 - (1.0 - FLOOR_EDGE_DARKEN) * np.clip(distance / FLOOR_FEATHER, 0.0, 1.0)
    return colours * keep[:, :, None]


def projected_rect(project, rect):
    """Returns the box [x, y, w, h] (whole pixels) of a flat map rectangle [x, y, w, h] mapped onto the map plane."""
    corners = [project((rect[0] + dx, rect[1] + dy)) for dx in (0, rect[2]) for dy in (0, rect[3])]
    low_x = int(round(min(point[0] for point in corners)))
    low_y = int(round(min(point[1] for point in corners)))
    return [low_x, low_y, int(round(max(point[0] for point in corners))) - low_x,
            int(round(max(point[1] for point in corners))) - low_y]


def projected_text_rect(project, rect):
    """Returns a flat map text rectangle [x, y, w, h] moved onto the map plane: its centre is mapped, its size stays,
    so the text keeps the room it is measured for."""
    centre = project((rect[0] + rect[2] / 2.0, rect[1] + rect[3] / 2.0))
    return [int(round(centre[0] - rect[2] / 2.0)), int(round(centre[1] - rect[3] / 2.0)), rect[2], rect[3]]


def inside_chamfers(rect):
    """Returns a flat map rectangle [x, y, w, h] moved diagonally inwards until it lies inside the cut-off corners of
    the table top (MAP_CHAMFER from every corner of TABLE_CROP along both edges); a rectangle inside stays."""
    left, top, width, height = TABLE_CROP
    x, y = float(rect[0]), float(rect[1])
    for sign_x in (-1.0, 1.0):
        for sign_y in (-1.0, 1.0):
            # The rectangle corner nearest to this table corner and how far it lies beyond the chamfer line
            corner_x = x + (rect[2] if sign_x > 0 else 0)
            corner_y = y + (rect[3] if sign_y > 0 else 0)
            from_x = (left + width - corner_x) if sign_x > 0 else (corner_x - left)
            from_y = (top + height - corner_y) if sign_y > 0 else (corner_y - top)
            excess = MAP_CHAMFER - from_x - from_y
            if excess > 0:
                x -= sign_x * excess / 2.0
                y -= sign_y * excess / 2.0
    return [int(round(x)), int(round(y)), rect[2], rect[3]]


def union_rect(first, second):
    """Returns the smallest rectangle [x, y, w, h] that holds both rectangles."""
    low_x = min(first[0], second[0])
    low_y = min(first[1], second[1])
    return [low_x, low_y, max(first[0] + first[2], second[0] + second[2]) - low_x,
            max(first[1] + first[3], second[1] + second[3]) - low_y]


def projected_scale(project, point):
    """Returns how much the map plane enlarges the flat map at a flat map point: the smaller of its scale across and
    its scale down the map (the far side is foreshortened), so markers that kept apart on the flat map keep apart."""
    step = 8.0
    origin = np.array(project(point))
    across = np.array(project((point[0] + step, point[1]))) - origin
    down = np.array(project((point[0], point[1] + step))) - origin
    return min(float(np.hypot(across[0], across[1])), float(np.hypot(down[0], down[1]))) / step


def projected_point(project, point):
    """Returns a flat map point mapped onto the map plane, in whole pixels."""
    mapped = project(point)
    return [int(round(mapped[0])), int(round(mapped[1]))]


def place_layout(root, world, project):
    """Writes the places of the flat layout (FLAT_LAYOUT: gate, wing areas, labels, seals and caves) mapped onto the
    map plane into the map description world, and the eight corners of the carved table top as "table_top" (pixel of
    the table texture, place on the full screen map); names and the other entries stay. Labels and seals that reached into a
    cut-off corner of the table top are first moved inside it (inside_chamfers), a wing label together with its seal. A cave marker is as large as its cave
    seen on the map plane (its flat size FLAT_CAVE_SIZES times projected_scale); text rectangles keep their size
    (projected_text_rect); the area of a wing is the box of its mapped area grown to hold its label, seal and caves."""
    flat = json.load(open(os.path.join(root, FLAT_LAYOUT), encoding="utf-8"))
    world["gate"] = projected_point(project, flat["gate"])
    # The corners of the carved table top: their pixel in the table texture and their place on the full screen map
    left, top, width, height = TABLE_CROP
    chamfer = MAP_CHAMFER
    corners = [(left + chamfer, top), (left + width - chamfer, top), (left + width, top + chamfer),
               (left + width, top + height - chamfer), (left + width - chamfer, top + height),
               (left + chamfer, top + height), (left, top + height - chamfer), (left, top + chamfer)]
    world["table_top"] = []
    for corner in corners:
        screen = project(corner)
        world["table_top"].append([round((corner[0] - left) / width * MAP_SIZE[0], 1),
                                   round((corner[1] - top) / height * MAP_SIZE[1], 1),
                                   round(screen[0], 1), round(screen[1], 1)])
    flat_wings = dict((wing["wing"], wing) for wing in flat["wings"])
    for wing in world["wings"]:
        source = flat_wings[wing["wing"]]
        area = projected_rect(project, source["area"])
        # The label and the seal beside it move together, so they keep apart
        seal = wing["seal_size"]
        flat_seal = [source["seal"][0] - seal // 2, source["seal"][1] - seal // 2, seal, seal]
        group = union_rect(source["label"], flat_seal)
        moved = inside_chamfers(group)
        shift_x, shift_y = moved[0] - group[0], moved[1] - group[1]
        label = source["label"]
        wing["label"] = projected_text_rect(project, [label[0] + shift_x, label[1] + shift_y, label[2], label[3]])
        wing["seal"] = projected_point(project, (source["seal"][0] + shift_x, source["seal"][1] + shift_y))
        area = union_rect(area, wing["label"])
        area = union_rect(area, [wing["seal"][0] - seal // 2, wing["seal"][1] - seal // 2, seal, seal])
        for cave, flat_cave in zip(wing["levels"] + [wing["bonus"]], source["levels"] + [source["bonus"]]):
            cave["pos"] = projected_point(project, flat_cave["pos"])
            flat_size = FLAT_CAVE_SIZES["bonus" if flat_cave is source["bonus"] else "level"]
            cave["size"] = int(round(flat_size * projected_scale(project, flat_cave["pos"])))
            if "label" in flat_cave:
                cave["label"] = projected_text_rect(project, inside_chamfers(flat_cave["label"]))
                area = union_rect(area, cave["label"])
            reach = int(cave["size"] * CAVE_REACH)
            area = union_rect(area, [cave["pos"][0] - reach // 2, cave["pos"][1] - reach // 2, reach, reach])
        wing["area"] = area


def fade_into_slab(root, texture):
    """Returns the table texture (RGB array 0..1 of the map size over the 6.15 x 3.44 map plane) with its outer border
    faded into the plain stone of the slab (MenuTableStone.png, one tile per SLAB_TILE mesh units) along the octagon of
    the table top (the map plane with its corners cut off MAP_PLANE_CHAMFER, tools/menu_table_map_chamfer.py): within
    SLAB_FADE of that outline the carving runs out into the slab, so the rectangular rim of the carved map frame does
    not show and the carving follows the cut-off corners."""
    height, width = texture.shape[:2]
    half_width, half_depth = MAP_PLANE[0] / 2.0, MAP_PLANE[1] / 2.0
    x = ((np.arange(width) + 0.5) / width * 2.0 - 1.0) * half_width
    y = (1.0 - (np.arange(height) + 0.5) / height * 2.0) * half_depth
    across = np.abs(x)[None, :]
    down = np.abs(y)[:, None]
    limit = half_width + half_depth - MAP_PLANE_CHAMFER
    distance = np.minimum(np.minimum(half_width - across, half_depth - down), (limit - across - down) / np.sqrt(2.0))
    carving = np.clip(distance / SLAB_FADE, 0.0, 1.0)
    carving = carving * carving * (3.0 - 2.0 * carving)
    stone = np.asarray(Image.open(os.path.join(root, "materials", "textures", "menu", "MenuTableStone.png"))
                       .convert("RGB"), dtype=np.float64) / 255.0
    columns = ((np.mod(x / SLAB_TILE, 1.0)) * stone.shape[1]).astype(int) % stone.shape[1]
    rows = ((np.mod(-y / SLAB_TILE, 1.0)) * stone.shape[0]).astype(int) % stone.shape[0]
    slab = stone[rows[:, None], columns[None, :]]
    return texture * carving[:, :, None] + slab * (1.0 - carving[:, :, None])


def build_map(root):
    """Writes the table texture and the full screen map (the stone table in the hall with the carved map as its top);
    returns the carved map with its rock around the frame (the stone of the plaques) and the full screen map, both as
    RGB array (0..1)."""
    source = Image.open(assets_src.resolve(root, CARVED_SOURCE)).convert("RGB")
    scaled = source.resize(MAP_SIZE, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    colours = np.asarray(scaled, dtype=np.float64) / 255.0
    frame = rounded_box(MAP_SIZE[0], MAP_SIZE[1], MAP_FRAME, 20.0)
    keep = 1.0 - (1.0 - EDGE_DARKEN) * np.clip(frame / EDGE_FEATHER, 0.0, 1.0)
    colours = colours * keep[:, :, None]
    left, top, width, height = TABLE_CROP
    table = Image.fromarray(np.round(colours * 255.0).astype(np.uint8), "RGB")
    table = table.crop((left, top, left + width, top + height)).resize(MAP_SIZE, Image.LANCZOS)
    table = fade_into_slab(root, np.asarray(table, dtype=np.float64) / 255.0)
    table = Image.fromarray(np.round(table * 255.0).astype(np.uint8), "RGB")
    table.save(os.path.join(root, "materials", "textures", "menu", "MenuCampaignMap.png"), optimize=True)
    # The full screen map: the rendered table with that texture on its map plane
    project, outline, placement = map_plane_projection(root)
    screen = table_view(root, outline, placement)
    folder = os.path.join(root, "gui", "campaign", "moreya")
    Image.fromarray(np.round(screen * 255.0).astype(np.uint8), "RGB").save(os.path.join(folder, "moreya_map.png"),
                                                                           optimize=True)
    return colours, screen, project


def build_locked_wings(root, world, colours, project):
    """Writes the greyed out basin of every wing of the full screen map (colours; the basins of the flat map mapped
    onto the map plane by project) and returns {wing number: [x, y, w, h]} of their images."""
    areas = {}
    basins = [[tuple(int(round(value)) for value in project(point)) for point in outline] for outline in WING_BASINS]
    for wing in world["wings"]:
        caves = [cave["pos"] for cave in wing["levels"]]
        basin = None
        for outline in basins:
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
    """Builds every image and writes the places of the layout on the map plane and of the locked wing images into the
    map description."""
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".."))
    colours, screen, project = build_map(root)
    path = os.path.join(root, "gui", "campaign", "campaign-world.json")
    world = json.load(open(path, encoding="utf-8"))
    place_layout(root, world, project)
    areas = build_locked_wings(root, world, screen, project)
    build_ui_art(root, colours)
    for wing in world["wings"]:
        wing["locked"] = {"image": "moreya/wing%d_locked.png" % wing["wing"], "area": areas[wing["wing"]]}
    with open(path, "w", encoding="utf-8", newline="\n") as target:
        json.dump(world, target, indent=2)
        target.write("\n")
    print("wrote the carved map, the table texture, %d locked wings and the map art" % len(areas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
