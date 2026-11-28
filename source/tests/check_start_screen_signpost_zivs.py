#!/usr/bin/env python3
"""Check the start screen subtitle signpost, the removed title crest and the Ziv name of the worker (no compile).

Start screen (config/mainmenuscene.cfg, overview pose of the menu camera):
- the signpost MenuSignpost.mesh stands once in the scene, on the courtyard ground left of the gate; its board points
  diagonally at the gate: the horizontal direction of the board front (measured from the mesh) lies inside the angle
  the Gate entity covers seen from the post, the line of the board meets the gate front inside the gate opening, and
  it is at least MIN_TURN_FROM_X_DEGREES away from +X; MenuTitleCrest.mesh is no longer placed, its mesh file stays;
- the board material shows the lettered board texture; the lettering lies inside the lettering area of the board
  (clear of the iron straps and the arrow tip);
- board, lettering and post look old and weathered like the courtyard, not clean (style guide: dark, worn wood with
  saturation <= 0.45, no near-white texels): the board and post textures have no bright texel and no bright or
  saturated area, they are split by cracks, the post uses the weathered wood, and the letter paint is dull and
  flaked yet stands out from the planks;
- seen from the overview pose the lettering is at least MIN_LETTER_PIXELS high at 1920x1080 at both ends, the board
  front faces the camera, the lettering lies on the screen and left of the menu button column for every supported
  window aspect, and no scenery hides it.

Ziv name: no player-facing text calls the worker "Worker"/"Workers" (layouts, C++ string literals that are not log or
assert messages, player-facing config texts, level and campaign texts); the identifiers stay as they are. Exception by
the owner's decision: the display name "Dwarf Worker" of the hero class DwarfWorker stays (one exact config line).

The menu meshes, materials and textures, the moved layouts and configs are game data of the content packages
(scripts/content_packages.py): they are read from the public tree or from the content packages, and the layouts and
configs of the packages are searched like the public ones. Without the content the scene part and the texts of the
moved files are named as not checked; the code and the public files are checked.
"""
import os
import math
import re
import sys
import time

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_menu_sky_below_horizon as scene  # noqa: E402  (numpy mesh reader of the menu scene check)
from lang_texts import english_texts  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import language_package_texts  # noqa: E402

CHECK = "check_start_screen_signpost_zivs"
#: The game data of the scene part that lies in the public tree or in a content package
SCENE_FILES = ("models/MenuSignpost.mesh", "models/MenuTitleCrest.mesh", "materials/scripts/MenuSignpost.material",
               "materials/scripts/MenuScene.material", "materials/textures/menu/MenuSignpostBoardLettered.png")

#: Placement of the signpost, chosen once on this branch (left front of the courtyard, foot on the paving, its board
#: between the replay camera flight and the left brazier). Moved 1.3 m right and 2.4 m towards the camera on the
#: INGAME-QS-12 branch, so that the board turned towards the gate ends short of the left brazier, stays clear of the
#: replay flight (which now passes behind its back end) and its far end stays as readable as before.
SIGNPOST_LINE = "AddEntity Signpost MenuSignpost.mesh -9.5 -13.5 -0.05"
#: Board of MenuSignpost.mesh in the board frame (tools/blender-assets/moreya_raid_models.py, before the turn about
#: the post foot by tools/menu_turn_signpost.py): back end, tip, lower and upper edge and the front face.
BOARD_BACK, BOARD_TIP, BOARD_BOTTOM, BOARD_TOP, BOARD_FRONT_Y = -0.5, 3.5, 3.7, 4.7, -0.36
#: Board front vertices may differ from this layout by this much (mesh units).
LAYOUT_TOLERANCE = 0.03
#: Half width of the gate opening around the Gate entity position along X, measured once from MenuGate.mesh (the
#: wall stones beside the portcullis end at about |x| 4 at 2 m height), and the smallest angle between the board
#: direction and +X (the old direction, which pointed past the gate).
GATE_OPENING_HALF_WIDTH = 4.0
MIN_TURN_FROM_X_DEGREES = 30.0
#: Lettering box of tools/gen_menu_signpost_lettering.py and the carved letters measured once in its letter mask
#: (u from the back end, v from the upper edge). The flaked paint (texels brighter than PAINT_LUMINANCE) lies inside
#: the carved letters and still spans at least MIN_PAINT_SPAN of their width and height.
LETTER_BOX = (0.215, 0.17, 0.86, 0.83)
LETTERS = (0.218, 0.342, 0.856, 0.656)
LETTER_TOLERANCE = 0.004
PAINT_LUMINANCE = 60.0
MIN_PAINT_SPAN = 0.9
#: Weathering limits (style guide: wood saturation <= 0.45, no white speckles or near-white texels; the courtyard is
#: dark and worn). Luminance is Rec. 601 in 0..255, saturation the HSV saturation, areas are blocks of BLOCK_PIXELS.
#: The clean bone white paint had areas of 182; the old paint keeps the letters readable in the menu light at 100.
MAX_TEXEL_LUMINANCE = 140.0
MAX_BLOCK_LUMINANCE = 105.0
MAX_MEAN_SATURATION = 0.40
MAX_BLOCK_SATURATION = 0.45
BLOCK_PIXELS = 16
#: Cracks: share of the open wood whose texels are at most CRACK_RATIO as bright as their surroundings (Gaussian
#: radius CRACK_RADIUS). On the board the open wood leaves out the plank joints, the edges and the letters with
#: their soot rim (OPEN_WOOD_MARGIN board fractions, LETTER_RIM_PIXELS). Measured once: the clean board 0.0019 and
#: the clean post wood 0.0021, the weathered board 0.0075 and the weathered post wood 0.0109.
MIN_CRACK_SHARE = 0.005
CRACK_RATIO = 0.3
CRACK_RADIUS = 6
OPEN_WOOD_MARGIN = (0.03, 0.05, 0.03)
LETTER_RIM_PIXELS = 21
#: The old paint stays dull (mean luminance of the letters), is flaked (share of letter texels still brighter than
#: PAINT_LUMINANCE) and the letters stay readable (mean luminance against the planks just around them).
MAX_PAINT_LUMINANCE = 110.0
PAINT_COVER = (0.35, 0.92)
MIN_LETTER_CONTRAST = 1.8
#: Smallest height of the lettering at 1920x1080 seen from the overview pose (measured 19.2 pixels).
MIN_LETTER_PIXELS = 18.0
#: The board front faces the overview camera at least this much (cosine; 1 = straight at it).
MIN_FACING = 0.7
#: The menu button column of MenuMain.layout never reaches further left than 0.36 of the window width (640x480 at
#: UI scale 120 %, measured once); the lettering ends left of this share.
BUTTON_COLUMN_LEFT_SHARE = 0.35
#: Window aspects from 5:4 to 32:9.
ASPECTS = ((1280, 1024), (640, 480), (1920, 1200), (1920, 1080), (2560, 1080), (5120, 1440))
#: CameraManager::setViewportSize: vertical field of view at the 16:9 reference aspect.
MENU_FOV_Y_DEGREES = 45.0
MENU_REFERENCE_ASPECT = 16.0 / 9.0


def read(relative):
    """Returns a repository text file, a game data file from the public tree or a content package; a mixed table or
    interface file comes with its own rows of the content (scripts/content_packages.py)."""
    with open(data(relative), encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    return content_packages.read_text(ROOT, relative) if "#@own " in text else text


def data(relative):
    """Path of a game data file from the public tree or a content package (below the repository when not found)."""
    return str(content_packages.resolve(ROOT, relative))


def missing_data(relative):
    """True when a game data file is not found and the content is not present (then it cannot be checked)."""
    return content_packages.data_file(ROOT, relative) is None and not content_packages.has_content(ROOT)


def missing_own_rows(relative):
    """True when a game data file is a mixed table or interface file and the content is not present: its own rows
    (content packages core-config and core-gui) are missing, so the texts of those rows cannot be checked."""
    if content_packages.has_content(ROOT) or content_packages.data_file(ROOT, relative) is None:
        return False
    with open(data(relative), encoding="utf-8", errors="replace") as handle:
        return "#@own " in handle.read()


#: Game data folders of a content package besides its levels; their configs and layouts are checked with the public
#: ones (config and gui parts), the others hold no level texts
PACKAGE_DATA_FOLDERS = ("config", "gui", "materials", "models", "particles", "sounds")


def content_level_walk(content):
    """os.walk of the content folder without the game data folders of the packages, so it yields the files of the wing
    and room packages and the levels of the content packages."""
    walk = []
    for folder, folders, files in os.walk(content):
        if os.path.dirname(os.path.normpath(folder)) == os.path.normpath(content):
            folders[:] = [name for name in folders if name not in PACKAGE_DATA_FOLDERS]
        walk.append((folder, folders, files))
    return walk


def scene_lines():
    """Returns the non-comment command lines of the menu scene."""
    return [line.strip() for line in read("config/mainmenuscene.cfg").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def overview_camera():
    """Returns the position and rotation matrix of the overview pose (rotation X then Y then Z)."""
    pose = [line.split() for line in scene_lines() if line.startswith("Pose overview ")][0]
    position = np.array([float(value) for value in pose[2:5]])
    rx, ry, rz = [math.radians(float(value)) for value in pose[5:8]]
    x_rot = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    y_rot = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    z_rot = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return position, x_rot @ y_rot @ z_rot


def project(point, camera, screen):
    """Screen pixel (x, y) of a world point with the menu projection of CameraManager::setViewportSize."""
    position, rotation = camera
    local = rotation.T @ (np.asarray(point, dtype=float) - position)
    assert local[2] < 0, "the point is behind the overview camera"
    aspect = screen[0] / float(screen[1])
    half_fov_y = math.atan(math.tan(math.radians(MENU_FOV_Y_DEGREES) / 2.0) * max(1.0, MENU_REFERENCE_ASPECT / aspect))
    ndc_x = (local[0] / -local[2]) / (math.tan(half_fov_y) * aspect)
    ndc_y = (local[1] / -local[2]) / math.tan(half_fov_y)
    return screen[0] / 2.0 * (1.0 + ndc_x), screen[1] / 2.0 * (1.0 - ndc_y)


def board_point(origin, u, v, yaw):
    """World point of the board front at texture coordinates u (back end to tip) and v (upper to lower edge).

    yaw is the turn of the board about the post foot in radians (0: the board points along +X).
    """
    local_x = BOARD_BACK + u * (BOARD_TIP - BOARD_BACK)
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return origin + np.array([cosine * local_x - sine * BOARD_FRONT_Y, sine * local_x + cosine * BOARD_FRONT_Y,
                              BOARD_TOP - v * (BOARD_TOP - BOARD_BOTTOM)])


def board_yaw(vertices, faces, materials):
    """Returns the yaw (radians) of the board of MenuSignpost.mesh and the board front vertices in mesh units.

    The direction is the horizontal main axis of the board front vertices (material MenuSignpostBoard), directed from
    the post foot (mesh origin) towards the arrow tip.
    """
    used = faces[np.array([material == "MenuSignpostBoard" for material in materials])]
    board = vertices[np.unique(used)]
    flat = board[:, :2]
    centre = flat.mean(axis=0)
    axis = np.linalg.svd(flat - centre)[2][0]
    if np.dot(axis, centre) < 0:
        axis = -axis
    return math.atan2(axis[1], axis[0]), board


def angle_between(a, b):
    """Unsigned angle in degrees between two horizontal directions given as angles in radians."""
    return abs(math.degrees(math.atan2(math.sin(a - b), math.cos(a - b))))


def texture_stats(rgb):
    """Returns the luminance (0..255) and HSV saturation (0..1) arrays of an 8-bit RGB float array."""
    luminance = rgb @ np.array([0.299, 0.587, 0.114])
    high = rgb.max(axis=2)
    saturation = np.where(high > 0, (high - rgb.min(axis=2)) / np.maximum(high, 1e-6), 0.0)
    return luminance, saturation


def block_means(values, size):
    """Returns the means of the size x size blocks of a 2D array (cut to whole blocks)."""
    height, width = (values.shape[0] // size) * size, (values.shape[1] // size) * size
    return values[:height, :width].reshape(height // size, size, width // size, size).mean(axis=(1, 3))


def check_weathered(name, rgb, failures, open_wood=None):
    """A board or post texture is dark, dull and cracked like the courtyard: no bright texel, no bright or saturated
    area, and splits in the open wood (all texels unless the boolean array open_wood is given). Returns the
    luminance array."""
    luminance, saturation = texture_stats(rgb)
    if luminance.max() > MAX_TEXEL_LUMINANCE:
        failures.append("%s has a near-white texel (luminance %.0f > %.0f)" % (name, luminance.max(), MAX_TEXEL_LUMINANCE))
    bright = block_means(luminance, BLOCK_PIXELS).max()
    if bright > MAX_BLOCK_LUMINANCE:
        failures.append("%s has a clean bright area (block luminance %.0f > %.0f)" % (name, bright, MAX_BLOCK_LUMINANCE))
    if saturation.mean() > MAX_MEAN_SATURATION:
        failures.append("%s is too saturated for weathered wood (%.2f > %.2f)" % (name, saturation.mean(), MAX_MEAN_SATURATION))
    saturated = block_means(saturation, BLOCK_PIXELS).max()
    if saturated > MAX_BLOCK_SATURATION:
        failures.append("%s has a saturated area (block saturation %.2f > %.2f)" % (name, saturated, MAX_BLOCK_SATURATION))
    image = Image.fromarray(np.clip(luminance, 0, 255).astype(np.uint8), "L")
    surroundings = np.asarray(image.filter(ImageFilter.GaussianBlur(CRACK_RADIUS)), dtype=float)
    split = luminance < CRACK_RATIO * surroundings
    cracks = (split[open_wood] if open_wood is not None else split).mean()
    if cracks < MIN_CRACK_SHARE:
        failures.append("%s shows no cracks or splits (%.4f of the texels, at least %.4f)" % (name, cracks, MIN_CRACK_SHARE))
    return luminance


def ray_hits(origin, direction, a, b, c):
    """Distances along the ray to the triangles (a, b, c) it hits (inf where it misses; Moller-Trumbore)."""
    e1 = b - a
    e2 = c - a
    p = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, p)
    usable = np.abs(det) > 1e-12
    inverse = np.where(usable, 1.0 / np.where(usable, det, 1.0), 0.0)
    s = origin - a
    u = np.einsum("ij,ij->i", s, p) * inverse
    q = np.cross(s, e1)
    v = (q @ direction) * inverse
    t = np.einsum("ij,ij->i", e2, q) * inverse
    hit = usable & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    return np.where(hit, t, np.inf)


def check_scene(failures):
    """Signpost placed once on the ground left of the gate, crest gone, lettering readable from the overview pose;
    without the content the scene is named as not checked."""
    missing = [path for path in SCENE_FILES if missing_data(path)]
    if missing:
        content_packages.unchecked(CHECK, ["the signpost scene"] + missing)
        return
    lines = scene_lines()
    entities = [line.split() for line in lines if line.startswith("AddEntity ")]
    signposts = [words for words in entities if words[2] == "MenuSignpost.mesh"]
    if [" ".join(words) for words in signposts] != [SIGNPOST_LINE]:
        failures.append("the scene places the signpost once as '%s': %s" % (SIGNPOST_LINE, signposts))
        return
    if any(words[2] == "MenuTitleCrest.mesh" for words in entities):
        failures.append("the green title crest MenuTitleCrest.mesh is still placed in the menu scene")
    if content_packages.data_file(ROOT, "models/MenuTitleCrest.mesh") is None:
        failures.append("models/MenuTitleCrest.mesh must stay in the repository")
    origin = np.array([float(value) for value in signposts[0][3:6]])
    gate = [words for words in entities if words[1] == "Gate"][0]
    gate_position = np.array([float(value) for value in gate[3:6]])

    # Direction: the board points from the post at the gate, not along +X.
    vertices, faces, materials = scene.load_mesh(data("models/MenuSignpost.mesh"))
    yaw, board_vertices = board_yaw(vertices, faces, materials)
    gate_points = scene.load_mesh(data("models/" + gate[2]))[0][:, :2] + gate_position[:2]
    gate_angles = np.arctan2(gate_points[:, 1] - origin[1], gate_points[:, 0] - origin[0])
    if not gate_angles.min() <= yaw <= gate_angles.max():
        failures.append("the board points at %.1f degrees, outside the angle %.1f..%.1f the gate covers"
                        % (math.degrees(yaw), math.degrees(gate_angles.min()), math.degrees(gate_angles.max())))
    start = board_point(origin, 0.5, 0.5, yaw)
    if math.sin(yaw) <= 0:
        failures.append("the board points away from the gate (%.1f degrees)" % math.degrees(yaw))
    else:
        meets = start[0] + (gate_position[1] - start[1]) * math.cos(yaw) / math.sin(yaw)
        if abs(meets - gate_position[0]) > GATE_OPENING_HALF_WIDTH:
            failures.append("the board points at x %.1f of the gate front, outside the gate opening %.1f..%.1f"
                            % (meets, gate_position[0] - GATE_OPENING_HALF_WIDTH,
                               gate_position[0] + GATE_OPENING_HALF_WIDTH))
    if angle_between(yaw, 0.0) < MIN_TURN_FROM_X_DEGREES:
        failures.append("the board still points along +X (%.1f degrees)" % math.degrees(yaw))
    # The board keeps its outline: turned back, its front matches the layout the letters are placed by.
    cosine, sine = math.cos(-yaw), math.sin(-yaw)
    local_x = cosine * board_vertices[:, 0] - sine * board_vertices[:, 1]
    local_y = sine * board_vertices[:, 0] + cosine * board_vertices[:, 1]
    front = np.abs(local_y - BOARD_FRONT_Y) < LAYOUT_TOLERANCE
    if not front.any():
        failures.append("the board front is not at its layout distance from the post")
    else:
        measured = (local_x[front].min(), local_x[front].max(), board_vertices[front, 2].min(), board_vertices[front, 2].max())
        if any(abs(a - b) > LAYOUT_TOLERANCE for a, b in zip(measured, (BOARD_BACK, BOARD_TIP, BOARD_BOTTOM, BOARD_TOP))):
            failures.append("the board front left its layout: %s" % (np.round(measured, 3),))

    # Materials: the board shows the weathered lettered planks, the post the weathered wood.
    material = read("materials/scripts/MenuSignpost.material")
    board = material.split("material MenuSignpostBoard ", 1)[1].split("\nmaterial ", 1)[0]
    for texture in ("MenuSignpostBoardLettered.png", "MenuSignpostBoardLetteredNormal.png"):
        if texture not in board:
            failures.append("MenuSignpostBoard does not use " + texture)
    if "MenuSignpostWood" in set(materials):
        failures.append("the signpost still uses the clean wood MenuSignpostWood")
    if "MenuSignpostWeatheredWood" not in set(materials):
        failures.append("the signpost does not use the weathered wood MenuSignpostWeatheredWood")
    post = material.split("material MenuSignpostWeatheredWood ", 1)[-1].split("\nmaterial ", 1)[0]
    if "texture MenuSignpostWeatheredWood.png" not in post:
        failures.append("MenuSignpostWeatheredWood does not use MenuSignpostWeatheredWood.png")
    folder = os.path.dirname(data("materials/textures/menu/MenuSignpostBoardLettered.png"))
    lettered = np.asarray(Image.open(os.path.join(folder, "MenuSignpostBoardLettered.png")).convert("RGB"), dtype=float)
    height, width = lettered.shape[:2]
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import gen_menu_signpost_lettering as lettering
    mask = lettering.letter_mask(data("gui/fonts/SourceSerif4-Semibold.ttf"), width, height)
    rows = np.arange(height)[:, None] / float(height)
    columns = np.arange(width)[None, :] / float(width)
    rim = np.asarray(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(LETTER_RIM_PIXELS)),
                     dtype=float) > 0
    joint, edge_v, edge_u = OPEN_WOOD_MARGIN
    open_wood = (~rim & (np.abs(rows - 1.0 / 3.0) > joint) & (np.abs(rows - 2.0 / 3.0) > joint)
                 & (rows > edge_v) & (rows < 1.0 - edge_v) & (columns > edge_u) & (columns < 1.0 - edge_u))
    luminance = check_weathered("the lettered board", lettered, failures, open_wood)
    post_path = data("materials/textures/menu/MenuSignpostWeatheredWood.png")
    if os.path.isfile(post_path):
        check_weathered("the post wood", np.asarray(Image.open(post_path).convert("RGB"), dtype=float), failures)
    else:
        failures.append("the weathered post wood MenuSignpostWeatheredWood.png is missing")

    # The old paint: dull, flaked, and the letters still stand out from the planks.
    inside = mask > 0.5
    grown = np.asarray(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(15)), dtype=float)
    ring = (grown > 0) & (mask < 0.02)
    if luminance[inside].mean() > MAX_PAINT_LUMINANCE:
        failures.append("the letter paint is bright and clean (mean luminance %.0f > %.0f)"
                        % (luminance[inside].mean(), MAX_PAINT_LUMINANCE))
    cover = (luminance[inside] > PAINT_LUMINANCE).mean()
    if not PAINT_COVER[0] <= cover <= PAINT_COVER[1]:
        failures.append("the letter paint covers %.2f of the letters, not worn to %.2f..%.2f" % ((cover,) + PAINT_COVER))
    if luminance[inside].mean() < MIN_LETTER_CONTRAST * luminance[ring].mean():
        failures.append("the letters do not stand out from the planks (%.0f against %.0f)"
                        % (luminance[inside].mean(), luminance[ring].mean()))
    paint = luminance > PAINT_LUMINANCE
    rows, columns = np.nonzero(paint)
    if len(rows) == 0:
        failures.append("the lettered board shows no painted letters")
        return
    box = (columns.min() / float(width), rows.min() / float(height), columns.max() / float(width), rows.max() / float(height))
    carved_rows, carved_columns = np.nonzero(inside)
    carved = (carved_columns.min() / float(width), carved_rows.min() / float(height),
              carved_columns.max() / float(width), carved_rows.max() / float(height))
    if carved[0] < LETTER_BOX[0] or carved[1] < LETTER_BOX[1] or carved[2] > LETTER_BOX[2] or carved[3] > LETTER_BOX[3]:
        failures.append("the letters leave the lettering box: %s" % (carved,))
    if any(abs(measured - expected) > LETTER_TOLERANCE for measured, expected in zip(carved, LETTERS)):
        failures.append("the letters cover u %.3f..%.3f, v %.3f..%.3f instead of %s"
                        % (carved[0], carved[2], carved[1], carved[3], LETTERS))
    if box[0] < LETTERS[0] - LETTER_TOLERANCE or box[1] < LETTERS[1] - LETTER_TOLERANCE             or box[2] > LETTERS[2] + LETTER_TOLERANCE or box[3] > LETTERS[3] + LETTER_TOLERANCE:
        failures.append("paint lies outside the carved letters: %s" % (box,))
    if box[2] - box[0] < MIN_PAINT_SPAN * (LETTERS[2] - LETTERS[0]) or box[3] - box[1] < MIN_PAINT_SPAN * (LETTERS[3] - LETTERS[1]):
        failures.append("the paint is gone from whole letters: it spans %s of %s" % (box, LETTERS))

    # Size and place of the lettering on the screen.
    camera = overview_camera()
    corners = [board_point(origin, u, v, yaw) for u in (LETTERS[0], LETTERS[2]) for v in (LETTERS[1], LETTERS[3])]
    for u in (LETTERS[0], LETTERS[2]):
        top = project(board_point(origin, u, LETTERS[1], yaw), camera, (1920, 1080))
        bottom = project(board_point(origin, u, LETTERS[3], yaw), camera, (1920, 1080))
        if bottom[1] - top[1] < MIN_LETTER_PIXELS:
            failures.append("the lettering is %.1f pixels high at 1920x1080 at u %.3f, less than %.0f"
                            % (bottom[1] - top[1], u, MIN_LETTER_PIXELS))
    # The turned board still shows its front to the overview camera.
    normal = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
    centre = board_point(origin, 0.5 * (LETTERS[0] + LETTERS[2]), 0.5 * (LETTERS[1] + LETTERS[3]), yaw)
    towards = (camera[0] - centre) / np.linalg.norm(camera[0] - centre)
    if np.dot(normal, towards) < MIN_FACING:
        failures.append("the board front turns away from the overview camera (cosine %.2f < %.2f)"
                        % (np.dot(normal, towards), MIN_FACING))
    for screen in ASPECTS:
        points = [project(corner, camera, screen) for corner in corners]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        if min(xs) < 0 or min(ys) < 0 or max(ys) > screen[1]:
            failures.append("the lettering leaves the %dx%d window" % screen)
        if max(xs) > BUTTON_COLUMN_LEFT_SHARE * screen[0]:
            failures.append("the lettering reaches under the menu buttons at %dx%d" % screen)

    # Nothing of the scenery stands between the overview camera and the lettering.
    flags = scene.material_flags(read("materials/scripts/MenuScene.material"))
    see_through = set(scene.SKY_MATERIALS) | {name for name, (blended, _) in flags.items() if blended}
    triangles = []
    meshes = {}
    for words in entities:
        if words[2] == "MenuSignpost.mesh":
            continue
        if words[2] not in meshes:
            meshes[words[2]] = scene.load_mesh(data("models/" + words[2]))
        vertices, faces, materials = meshes[words[2]]
        if len(faces) == 0:
            continue
        solid = np.array([material not in see_through for material in materials])
        triangles.append(vertices[faces[solid]] + np.array([float(value) for value in words[3:6]]))
    triangles = np.concatenate(triangles)
    position = camera[0]
    # Only triangles in front of the board and inside the cone towards it can hide the lettering.
    target = board_point(origin, 0.5 * (LETTERS[0] + LETTERS[2]), 0.5 * (LETTERS[1] + LETTERS[3]), yaw)
    axis = (target - position) / np.linalg.norm(target - position)
    reach = np.linalg.norm(target - position)
    radius = 0.5 * (LETTERS[2] - LETTERS[0]) * (BOARD_TIP - BOARD_BACK) + 0.5
    centres = triangles.mean(axis=1)
    sizes = np.linalg.norm(triangles - centres[:, None, :], axis=2).max(axis=1)
    along = (centres - position) @ axis
    across = np.linalg.norm((centres - position) - along[:, None] * axis, axis=1)
    near = (along > -sizes) & (along < reach + sizes) & (across < radius * np.clip(along / reach, 0.0, 1.0) + sizes)
    a, b, c = triangles[near, 0], triangles[near, 1], triangles[near, 2]
    hidden = 0
    samples = 0
    for u in np.linspace(LETTERS[0], LETTERS[2], 9):
        for v in np.linspace(LETTERS[1], LETTERS[3], 3):
            point = board_point(origin, u, v, yaw)
            direction = point - position
            distance = np.linalg.norm(direction)
            samples += 1
            if ray_hits(position, direction / distance, a, b, c).min() < distance - 0.05:
                hidden += 1
    if hidden:
        failures.append("scenery hides %d of %d sample points of the lettering from the overview pose" % (hidden, samples))


#: C++ string literals with the word worker that are identifiers or file paths, never shown to the player (counted
#: once on this branch): the config/network job name, the temple recipe result, the social text scope, the reaction
#: resource folder and the level test report.
SOURCE_IDENTIFIERS = {
    ("source/entities/CreatureDefinition.cpp", '"Worker"'): 2,
    ("source/rooms/RoomTemple.cpp", '"Workers"'): 1,
    ("source/social/SocialGenerator.cpp", '"worker"'): 2,
    ("source/render/WorkerExtras.cpp", '"Creatures/Worker/"'): 1,
    ("source/utils/RunLevelTest.cpp", '" workers="'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.corpses"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.enemyknockedout"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.giftboxes"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.gold"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.items"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.ownknockedout"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.carry.trapsdoors"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.carry"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.claimground"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.claimwall"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.clean"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.dig"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.job.reload"'): 1,
    ("source/render/WorkersWindow.cpp", '"ui.workers.working"'): 1,
}
#: Player-facing config text that keeps the word by the owner's decision: the display name "Dwarf Worker" of the hero
#: class DwarfWorker stays (it names a hero class, not the keeper's Ziv). Only this exact line is excepted, and it must
#: stay exactly once; every other text is checked as strictly as before.
DECIDED_EXCEPTIONS = {("config/social-texts.cfg", "ClassName\tDwarfWorker\tDwarf Worker")}
#: Config keys whose value names the worker as an identifier or a resource path.
CONFIG_IDENTIFIER_KEYS = ("Group", "SkillGroup", "CreatureJob", "SoundFamilyDie")
WORD = re.compile(r"\bworkers?\b", re.I)
LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"')


def check_ziv_names(failures):
    """No player-facing Worker/Workers; the Ziv names are shown and the identifiers stay."""
    # Layouts: texts, tooltips and context help (of the public tree and of the content packages).
    for path in content_packages.data_glob(ROOT, "gui", "*.layout"):
        name = path.name
        for number, line in enumerate(read("gui/" + name).splitlines(), 1):
            match = re.search(r'<(?:Property|UserString) name="(Text|TooltipText|ContextHelp|Tooltip)" value="([^"]*)"', line)
            if match and WORD.search(match.group(2)):
                failures.append("gui/%s:%d shows '%s'" % (name, number, match.group(2)))

    # C++ string literals outside log and assert messages.
    found = {}
    for folder, _, files in os.walk(os.path.join(ROOT, "source")):
        relative_folder = os.path.relpath(folder, ROOT).replace("\\", "/")
        if relative_folder.startswith("source/tests"):
            continue
        for name in files:
            if not name.endswith((".cpp", ".h")):
                continue
            relative = relative_folder + "/" + name
            for number, line in enumerate(read(relative).splitlines(), 1):
                if line.lstrip().startswith(("#include", "//")) or re.search(r"\bOD_(LOG_\w+|ASSERT\w*)\(", line):
                    continue
                for literal in LITERAL.findall(line):
                    if WORD.search(literal):
                        found[(relative, literal)] = found.get((relative, literal), 0) + 1
    for key, count in sorted(found.items()):
        if SOURCE_IDENTIFIERS.get(key) != count:
            failures.append("%s: player-facing string %s (%d times)" % (key[0], key[1], count))
    for key, count in SOURCE_IDENTIFIERS.items():
        if found.get(key) != count:
            failures.append("%s: identifier %s expected %d times, found %d" % (key[0], key[1], count, found.get(key, 0)))

    # Config files: player-facing social texts and no other worker word outside identifiers and comments.
    # The configs of the public tree and of the content packages
    for path in content_packages.data_glob(ROOT, "config", "*.cfg"):
        name = path.name
        relative = "config/" + name
        for number, line in enumerate(read(relative).splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or (relative, stripped) in DECIDED_EXCEPTIONS:
                continue
            fields = stripped.split()
            if name == "social-texts.cfg":
                parts = stripped.split("\t")
                if len(parts) >= 3 and WORD.search("\t".join(parts[2:])):
                    failures.append("%s:%d shows '%s'" % (relative, number, "\t".join(parts[2:])))
                continue
            if fields[0] in CONFIG_IDENTIFIER_KEYS or fields[0].startswith("TempleRecipe"):
                continue
            if WORD.search(stripped):
                failures.append("%s:%d names the worker: %s" % (relative, number, stripped))
    for path, text in DECIDED_EXCEPTIONS:
        if missing_data(path):
            content_packages.unchecked(CHECK, [path])
            continue
        count = [line.strip() for line in read(path).splitlines()].count(text)
        if count != 1:
            failures.append("%s: the decided line '%s' is there %d times, expected once" % (path, text, count))

    # Levels and the campaign: messages, objectives, descriptions, briefings.
    levels = os.path.join(ROOT, "levels")
    # The levels of the content packages too, when the content repository is present
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import campaign_packages
    content = campaign_packages.content_folder(ROOT)
    walks = list(os.walk(levels)) + (content_level_walk(str(content)) if content is not None else [])
    for folder, _, files in walks:
        for name in sorted(files):
            if not name.endswith((".level", ".cfg")):
                continue
            relative = os.path.relpath(os.path.join(folder, name), ROOT).replace("\\", "/")
            for number, line in enumerate(read(relative).splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("#", "//")):
                    continue
                if WORD.search(stripped):
                    failures.append("%s:%d names the worker: %s" % (relative, number, stripped[:120]))

    # The Ziv names are shown where the worker names were.
    shown = {
        "gui/ModeGame.layout": ('value="Zivs (J)"', 'value="Zivs: fixed Zivs per job, free Zivs, priority and carry order (J)"'),
        "gui/WindowWorkers.layout": ('<Property name="Text" value="Zivs" />', '<Property name="Text" value="Free Zivs" />'),
        "gui/WindowSkillTree.layout": ('value="Spell: Summon Ziv"',),
        "source/render/SocialWindow.cpp": ('"ui.dungeonbook.filter.zivs"',),
        "source/render/CreaturePanel.cpp": ('"ui.panel.zivs"',),
        "source/modes/GameMode.cpp": ('std::make_pair(Gui::BUTTON_CREATURE_WORKER, "Zivs")',),
        "source/game/Player.cpp": ('"You redeemed your Ziv into "', '"You have no Ziv to fulfill your dark wishes."'),
        "source/gamemap/GameMap.cpp": ('"Your Zivs vanished because the mana ran out"',),
    }
    # The names and hints of the code are entries of the English language package, found by their keys
    shown_in_language = {
        "research.spellsummonworker.name": "The 'Summon Ziv' Spell",
        "spell.summonworker.name": "Summon Ziv",
        "spell.hint.summon_on_claimed_ground": "Summon Zivs on your claimed ground.",
        "gift.stunworkers.name": "Stun Zivs",
        "gift.receiveworkers.name": "Receive Zivs",
        "spell.hint.no_plague_on_ziv": "Zivs and champions never get sick.",
    }
    if content_packages.has_content(ROOT):
        english = language_package_texts.english(ROOT)
        for key, expected in shown_in_language.items():
            if english.get(key) != expected:
                failures.append("the English entry %s is not %r" % (key, expected))
    else:
        content_packages.unchecked(CHECK, sorted(shown_in_language))
    # The texts of these language keys say Zivs (the language file lang-en holds the English texts of the code)
    english = english_texts(ROOT)
    for key, expected in (("ui.dungeonbook.filter.zivs", "Zivs"), ("ui.panel.zivs", "Zivs")):
        if english is not None and english.get(key) != expected:
            failures.append("lang-en says %r for %s, expected %r" % (english.get(key), key, expected))
    for path, texts in shown.items():
        if missing_data(path) or missing_own_rows(path):
            content_packages.unchecked(CHECK, [path])
            continue
        text = read(path)
        for expected in texts:
            if expected not in text:
                failures.append("%s does not show %s" % (path, expected))

    # Identifiers of saves, network, config and scripts stay unchanged.
    kept = {
        "source/entities/CreatureDefinition.cpp": ('if (s.compare("Worker") == 0)', 'return "Worker";'),
        "source/spells/SpellSummonWorker.cpp": ('SpellSummonWorkerName = "summonWorker";',),
        "source/game/SkillType.cpp": ('"spellSummonWorker"',),
        "config/creatures.cfg": ("CreatureJob\tWorker",),
        "config/factions.cfg": ("WorkerClass\tKobold",),
    }
    for path, texts in kept.items():
        if missing_own_rows(path):
            content_packages.unchecked(CHECK, [path + " (own rows)"])
            continue
        text = read(path)
        for expected in texts:
            if expected not in text:
                failures.append("%s lost the identifier %s" % (path, expected))


def main():
    """Runs both parts and reports every failure."""
    started = time.monotonic()
    failures = []
    check_scene(failures)
    scene_seconds = time.monotonic() - started
    check_ziv_names(failures)
    print('ODP_TEST_PHASE {"name":"scene","seconds":%.2f}' % scene_seconds)
    print('ODP_TEST_PHASE {"name":"names","seconds":%.2f}' % (time.monotonic() - started - scene_seconds))
    for failure in failures:
        print("FAIL " + failure)
    if failures:
        return 1
    print("OK: signpost with the subtitle placed and readable, title crest removed, Ziv names shown, identifiers kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
