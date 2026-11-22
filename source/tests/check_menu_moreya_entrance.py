#!/usr/bin/env python3
"""Checks the entrance into Moreya on the start screen: the green portal behind the campaign table and its signpost.

No compile needed. Reads config/mainmenuscene.cfg, the particle and material scripts, the textures and the binary
meshes under models/ and asserts:

- the scene places the portal MoreyaPortal (MenuMoreyaPortal.mesh) and the signpost MoreyaSignpost
  (MenuMoreyaSignpost.mesh); the staircase into the ground and the frame of the opening in the hall's back wall are
  gone from the scene and from models/ (GONE_MESHES); the campaign table stays at the entrance of the hall
  (TABLE_POSITION) and Pose campaign stays as it was (CAMPAIGN_POSE);
- the portal stands right behind the table in the campaign hall: centred behind it (MAX_PORTAL_OFFSET), at least
  MIN_TABLE_GAP behind its back edge, in front of the hall's back wall (HALL_BACK_WALL) and between the side walls
  (HALL_HALF_WIDTH), its foot on the hall floor (MAX_FOOT_GAP);
- it is a stone arch filled with green fire: the fire faces (FIRE_MATERIAL) face the table, cover at least
  MIN_FIRE_AREA and an opening at least MIN_FIRE_WIDTH wide and MIN_FIRE_HEIGHT high; stone stands on both sides of
  the fire (pillars) and over its top (arch); the fire material ignores the scene lights and lets its texture rise;
  the texture is green (GREEN_SHARE of its bright texels); the green flame particles rise in the opening and the
  orange flames burn over two fire bowls (MenuEmber patches of the portal) left and right in front of the fire;
- the hall's back wall is whole behind the portal: at least MIN_WALL_SHARE of the sight lines through it over
  WALL_AREA end in it (only the thin joints between its blocks let a line through), and the yard floor where the
  stairwell was is whole again (MAX_FLOOR_STEP);
- the gate_exit frame of the campaign flight to campaign (vertical field of view 45 degrees at 16:9, 16:9 and 4:3,
  path and rotation as RenderSceneMenu::samplePath) shows the middle of the fire and the crown of the arch unhidden;
  it and at least one more frame of the flight show the middle of the fire and the whole signpost board unhidden,
  the board facing the camera and at least MIN_BOARD_PIXELS long on a 1080 line screen;
- the signpost stands on the hall floor left of the portal between the table and the back wall; its board is upright
  (MAX_BOARD_TILT), at least MIN_BOARD_LENGTH long and its arrow points towards the fire (MIN_POINTING);
- no glowing material forms a flat slab in the rear yard (largest flat connected patch at most MAX_FLAT_GLOW);
- the board texture shows the word "Moreya": where it differs from the plain planks matches the letter shapes;
- the files of the entrance (portal, fire textures, signpost, board textures) have CREDITS entries.

Sky and horizon elements (Backdrop, BloodMoon, HorizonCrows, VolcanicRuins) are neither ground nor occluders.
"""
import math
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_menu_flight_geometry as flight  # noqa: E402

ROOT = flight.ROOT
PORTAL, PORTAL_MESH = "MoreyaPortal", "MenuMoreyaPortal.mesh"
SIGNPOST, SIGNPOST_MESH = "MoreyaSignpost", "MenuMoreyaSignpost.mesh"
TABLE, TABLE_MESH = "CampaignTable", "MenuMapTable.mesh"
HALL, HALL_MESH = "CampaignHall", "MenuCampaignHall.mesh"
#: The staircase into the ground and the frame of the opening in the hall's back wall gave way to the portal.
GONE_MESHES = ("MenuMoreyaStairs.mesh", "MenuHallRearArch.mesh")
#: The table stays at the entrance of the campaign hall and the campaign camera pose stays as it was.
TABLE_POSITION = (0.0, 22.0, 0.0)
CAMPAIGN_POSE = (0.0, 19.0, 7.0, 29.5, 0.0, 0.0)
#: The inner face of the hall's back wall (scene y) and the half width of the hall between its side walls.
HALL_BACK_WALL = 29.25
HALL_HALF_WIDTH = 5.8
#: The portal is centred behind the table (x offset at most), at least this far behind its back edge, and its foot
#: lies at most this far from the hall floor.
MAX_PORTAL_OFFSET = 0.3
MIN_TABLE_GAP = 1.5
MAX_FOOT_GAP = 0.15
#: The green fire: its material, the least area of its faces and the least width and top height of the opening.
FIRE_MATERIAL = "MenuMoreyaPortalFire"
MIN_FIRE_AREA = 10.0
MIN_FIRE_WIDTH = 3.0
MIN_FIRE_HEIGHT = 4.5
#: Share of the bright texels of the fire texture that must be green (green above twice red and twice blue).
GREEN_SHARE = 0.95
#: The stone of the arch and the pillars, the glowing coals of the fire bowls.
STONE_MATERIALS = ("MenuChippedStone", "MenuCarvedStone")
BOWL_MATERIAL = "MenuEmber"
#: The particle systems of the portal: green flames in the opening, orange flames over the bowls; an emitter lies at
#: most BOWL_REACH from the middle of a bowl's coals (horizontally) and up to BOWL_LIFT above them.
GREEN_FIRE, BOWL_FIRE = "MenuPortalGreenFire", "MenuPortalBowlFire"
BOWL_REACH, BOWL_LIFT = 0.3, 0.3
#: The hall's back wall: the area over which sight lines through it are sampled (x min, x max, z min, z max, step)
#: and the least share of them that must end in the wall (the old opening let every line through).
WALL_AREA = (-3.5, 3.5, 0.5, 4.0, 0.25)
MIN_WALL_SHARE = 0.85
#: The yard floor where the stairwell was (scene x, y) is whole again: the paving lies at most this far from z 0.
OLD_STAIRWELL = ((-2.0, 32.0), (0.0, 34.0), (2.0, 36.0))
MAX_FLOOR_STEP = 0.25
#: The board is upright (arrow and normal at most this far out of the horizontal) and at least this long; in the
#: flight frames it spans at least MIN_BOARD_PIXELS on a 1080 line screen; its arrow points towards the fire
#: (cosine between the arrow and the direction from the board's back end to the middle of the fire, at least).
MAX_BOARD_TILT = 0.1
MIN_BOARD_LENGTH = 2.8
MIN_BOARD_PIXELS = 150
MIN_POINTING = 0.7
#: Glowing materials that must not form a flat slab in the rear yard (YARD: x min, x max, y min, y max), and the
#: largest flat connected patch of them allowed there in square units.
GLOW_SLAB_MATERIALS = ("MenuEmber", "MenuFlame", "MenuFlameCore")
YARD = (-9.0, 9.0, 30.3, 44.0)
MAX_FLAT_GLOW = 0.1
BOARD_MATERIAL = "MenuMoreyaSignpostBoard"
SKY = ("Backdrop", "BloodMoon", "HorizonCrows", "VolcanicRuins")

#: Vertical field of view of the menu camera at 16:9 (REFERENCE_ASPECT) and the checked aspect ratios.
FOV_Y = 45.0
ASPECTS = (16.0 / 9.0, 4.0 / 3.0)
REFERENCE_ASPECT = 16.0 / 9.0

#: The board front must face the flight camera: cosine between its normal and the direction to the camera.
MIN_FACING = 0.3
#: Share of the letter shapes that must coincide with the painted change of the board texture.
MIN_LETTER_MATCH = 0.8


def positions(data, start, end):
    """Returns the vertex positions (n, 3) of one Ogre geometry chunk, read straight from its vertex buffer."""
    count, = struct.unpack_from("<I", data, start)
    elements = []
    buffers = {}
    for chunk_id, s, e in flight.chunks(data, start + 4, end):
        if chunk_id == 0x5100:
            for _, s3, _ in flight.chunks(data, s, e):
                source, _, semantic, offset, _ = struct.unpack_from("<HHHHH", data, s3)
                elements.append((source, semantic, offset))
        elif chunk_id == 0x5200:
            bind, stride = struct.unpack_from("<HH", data, s)
            for kind, s3, _ in flight.chunks(data, s + 4, e):
                if kind == 0x5210:
                    buffers[bind] = (stride, s3)
    source, _, offset = [element for element in elements if element[1] == 1][0]
    stride, base = buffers[source]
    raw = np.frombuffer(data, dtype=np.uint8, count=count * stride, offset=base).reshape(count, stride)
    return raw[:, offset:offset + 12].copy().view("<f4").astype(np.float64)


def submeshes(path):
    """Returns {material: (vertices, triangles)} of an Ogre binary mesh (all submeshes, decals included)."""
    data = open(path, "rb").read()
    offset = data.index(b"\n") + 1
    result = {}
    for chunk_id, s, e in flight.chunks(data, offset, len(data)):
        if chunk_id != 0x3000:
            continue
        shared = None
        parts = []
        for kind, s2, e2 in flight.chunks(data, s + 1, e):
            if kind == 0x5000:
                shared = positions(data, s2, e2)
            elif kind == 0x4000:
                parts.append((s2, e2))
        for s2, e2 in parts:
            material = data[s2:data.index(b"\n", s2)].decode("ascii")
            p = data.index(b"\n", s2) + 1
            uses_shared = data[p]
            count, = struct.unpack_from("<I", data, p + 1)
            wide = data[p + 5]
            p += 6
            indices = struct.unpack_from("<%d%s" % (count, "I" if wide else "H"), data, p)
            p += count * (4 if wide else 2)
            vertices = shared
            if not uses_shared:
                for kind, s3, e3 in flight.chunks(data, p, e2):
                    if kind == 0x5000:
                        vertices = positions(data, s3, e3)
                        break
            triangles = np.array(indices, dtype=np.int64).reshape(-1, 3)
            old_vertices, old_triangles = result.get(material, (np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)))
            result[material] = (np.vstack((old_vertices, vertices)),
                                np.vstack((old_triangles, triangles + len(old_vertices))))
    return result


def world_triangles(mesh, position):
    """Returns the triangles (n, 3, 3) of every submesh of a mesh at a scene position."""
    parts = [vertices[triangles] for vertices, triangles in submeshes(os.path.join(flight.MODELS, mesh)).values()
             if len(triangles)]
    return np.concatenate(parts) + position


def heights_at(triangles, x, y):
    """Returns the heights of all triangles that a vertical line through (x, y) crosses."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    v0, v1 = b - a, c - a
    det = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    valid = np.abs(det) > 1e-12
    safe = np.where(valid, det, 1.0)
    w1 = ((x - a[:, 0]) * v1[:, 1] - v1[:, 0] * (y - a[:, 1])) / safe
    w2 = (v0[:, 0] * (y - a[:, 1]) - (x - a[:, 0]) * v0[:, 1]) / safe
    inside = valid & (w1 >= 0) & (w2 >= 0) & (w1 + w2 <= 1)
    return (a[:, 2] + w1 * v0[:, 2] + w2 * v1[:, 2])[inside]


def floor_height(triangles, x, y, spread=0.2):
    """Returns the highest surface below z 1 at (x, y) and four points around it (None when there is none).

    The yard paving has open joints down to its bedding; looking at a few points finds the flagstone tops.
    """
    found = []
    for dx, dy in ((0, 0), (spread, 0), (-spread, 0), (0, spread), (0, -spread)):
        heights = heights_at(triangles, x + dx, y + dy)
        found.extend(heights[heights < 1.0])
    return max(found) if found else None


def blocked(triangles, start, end, margin=0.03, bounds=None):
    """Tells whether a segment from start to end hits a triangle before it comes within margin of the end.

    bounds, the per-triangle (minimum, maximum) corners computed once, skips triangles away from the segment.
    """
    if bounds is not None:
        near = np.all(bounds[0] <= np.maximum(start, end), axis=1) & np.all(bounds[1] >= np.minimum(start, end), axis=1)
        triangles = triangles[near]
    direction = end - start
    length = np.linalg.norm(direction)
    direction = direction / length
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    e1, e2 = b - a, c - a
    p = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, p)
    valid = np.abs(det) > 1e-12
    inverse = 1.0 / np.where(valid, det, 1.0)
    t_vec = start - a
    u = np.einsum("ij,ij->i", t_vec, p) * inverse
    q = np.cross(t_vec, e1)
    v = (q @ direction) * inverse
    t = np.einsum("ij,ij->i", e2, q) * inverse
    hit = valid & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4) & (t < length - margin)
    return bool(hit.any())


def camera(pose):
    """Returns the position and the rotation matrix (columns: right, up, back) of a CameraMove-style pose."""
    x, y, z = (math.radians(value) for value in pose[3:6])
    rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return np.array(pose[:3]), rx @ ry @ rz


def in_view(eye, rotation, point, aspect):
    """Tells whether a point lies inside the camera frame of the given aspect ratio.

    Like CameraManager::setViewportSize for the menu: the vertical field of view is FOV_Y at 16:9; a narrower
    window keeps the horizontal field of view of 16:9 and sees more vertically.
    """
    local = rotation.T @ (point - eye)
    depth = -local[2]
    if depth < 0.1:
        return False
    half_x = math.tan(math.radians(FOV_Y) / 2) * max(aspect, REFERENCE_ASPECT)
    half_y = half_x / aspect
    return abs(local[0] / depth) <= half_x and abs(local[1] / depth) <= half_y


def poses():
    """Returns the camera poses {name: [x, y, z, rx, ry, rz]} of the [MenuCamera] section."""
    result = {}
    for line in open(flight.CONFIG, encoding="utf-8"):
        words = line.split()
        if len(words) == 8 and words[0] == "Pose":
            result[words[1]] = [float(value) for value in words[2:]]
    return result


def arrow(board):
    """Returns (back end centre, tip, unit direction, unit front normal) of the board front triangles."""
    points = board.reshape(-1, 3)
    centre = points.mean(axis=0)
    normal = np.cross(board[:, 1] - board[:, 0], board[:, 2] - board[:, 0]).sum(axis=0)
    normal /= np.linalg.norm(normal)
    _, _, axes = np.linalg.svd(points - centre)
    axis = axes[0]
    along = (points - centre) @ axis
    across = (points - centre) @ np.cross(normal, axis)
    length = along.max() - along.min()
    # The arrow shoulders lie 12.5 % of the length before the tip, so only the tip falls into the last tenth.
    high = along > along.max() - 0.1 * length
    low = along < along.min() + 0.1 * length
    # The pointed end narrows to the tip: its points spread less across the board than those of the square end.
    if np.ptp(across[high]) > np.ptp(across[low]):
        axis, along, high, low = -axis, -along, low, high
    tip = points[np.argmax(along)]
    back = points[low].mean(axis=0)
    direction = tip - back
    return back, tip, direction / np.linalg.norm(direction), normal


def board_pixels(eye, rotation, board, aspect, lines=1080):
    """Returns the larger screen extent in pixels of the board on a screen with the given number of lines."""
    half_x = math.tan(math.radians(FOV_Y) / 2) * max(aspect, REFERENCE_ASPECT)
    half_y = half_x / aspect
    points = []
    for point in board.reshape(-1, 3):
        local = rotation.T @ (point - eye)
        depth = -local[2]
        points.append((local[0] / depth / half_x * lines * aspect / 2, local[1] / depth / half_y * lines / 2))
    points = np.array(points)
    return max(np.ptp(points[:, 0]), np.ptp(points[:, 1]))


def largest_flat_patch(triangles):
    """Returns the area of the largest connected group of coplanar triangles (shared corners connect them)."""
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(normals, axis=1) / 2
    units = normals / np.maximum(areas * 2, 1e-12)[:, None]
    offsets = np.einsum("ij,ij->i", units, triangles[:, 0])
    parent = list(range(len(triangles)))

    def find(index):
        """Returns the representative of a triangle's group."""
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owners = {}
    for index, triangle in enumerate(triangles):
        plane = (tuple(np.round(units[index] * 50).astype(int)), int(round(offsets[index] * 50)))
        for corner in triangle:
            key = (plane, tuple(np.round(corner * 1000).astype(int)))
            if key in owners:
                parent[find(index)] = find(owners[key])
            else:
                owners[key] = index
    totals = {}
    for index in range(len(triangles)):
        root = find(index)
        totals[root] = totals.get(root, 0.0) + areas[index]
    return max(totals.values()) if totals else 0.0


def letters_match():
    """Returns the share of the "Moreya" letter shapes that coincide with the painted change of the board texture."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import gen_menu_signpost_lettering as lettering
    folder = os.path.join(ROOT, "materials", "textures", "menu")
    plain = lettering.load_rgb(os.path.join(folder, "MenuSignpostBoard.png"))
    painted = lettering.load_rgb(os.path.join(folder, "MenuMoreyaSignpostBoard.png"))
    height, width = plain.shape[:2]
    mask = lettering.letter_mask(os.path.join(ROOT, "gui", "fonts", "MedievalSharp-Bold.ttf"), width, height,
                                 "Moreya") > 0.5
    changed = np.abs(painted - plain).max(axis=2) > 0.12
    return (mask & changed).sum() / float(mask.sum()), (changed & ~mask).sum() / float(changed.sum())


def flight_pose(all_poses, share):
    """Returns the camera [x, y, z, rx, ry, rz] at a share (0..1) of the campaign flight from gate_exit to campaign.

    Positions follow the Catmull-Rom curve of RenderSceneMenu::samplePath (gate_entry before, campaign after); the
    rotation is the slerp of the two poses, which for two turns about X alone is the blend of their X angles.
    """
    before, first, second = (np.array(all_poses[name][:3]) for name in ("gate_entry", "gate_exit", "campaign"))
    after = second
    position = 0.5 * ((2 * first) + (-before + second) * share
                      + (2 * before - 5 * first + 4 * second - after) * share ** 2
                      + (-before + 3 * first - 3 * second + after) * share ** 3)
    angles = [all_poses["gate_exit"][3 + k] + (all_poses["campaign"][3 + k] - all_poses["gate_exit"][3 + k]) * share
              for k in range(3)]
    return list(position) + angles


def particle_system(name):
    """Returns (emitter positions, emitter start colours) of one system of particles/MenuScene.particle."""
    text = open(os.path.join(ROOT, "particles", "MenuScene.particle"), encoding="utf-8").read()
    block = text.split("particle_system %s\n" % name, 1)[1].split("\nparticle_system ", 1)[0]
    positions_found = [np.array([float(value) for value in found.split()])
                       for found in re.findall(r"\bposition\s+(\S+\s+\S+\s+\S+)", block)]
    colours = [np.array([float(value) for value in found.split()])
               for found in re.findall(r"\bcolour_range_start\s+(\S+\s+\S+\s+\S+)", block)]
    return positions_found, colours


def material_block(name):
    """Returns the text of one material of materials/scripts/MenuMoreyaPortal.material."""
    text = open(os.path.join(ROOT, "materials", "scripts", "MenuMoreyaPortal.material"), encoding="utf-8").read()
    return text.split("material %s\n" % name, 1)[1].split("\nmaterial ", 1)[0]


def patches(triangles, gap=0.05):
    """Returns the centres of the groups of triangles that touch (corners closer than gap), largest first."""
    centres = triangles.mean(axis=1)
    groups = []
    for index in range(len(triangles)):
        joined = [group for group in groups
                  if np.min(np.linalg.norm(triangles[group].reshape(-1, 1, 3) - triangles[index][None], axis=2)) < gap]
        merged = [index] + [member for group in joined for member in group]
        groups = [group for group in groups if group not in joined] + [merged]
    groups.sort(key=len, reverse=True)
    return [centres[group].mean(axis=0) for group in groups]


def visible_frames(all_poses, aspect, points, occluders, bounds, extra=None):
    """Returns the flight shares whose frame shows every point in view and unhidden (and passes extra, if given)."""
    showing = []
    for share in np.arange(0.0, 1.0001, 0.05):
        eye, rotation = camera(flight_pose(all_poses, share))
        if any(not in_view(eye, rotation, point, aspect) for point in points):
            continue
        if any(blocked(occluders, eye, point, bounds=bounds) for point in points):
            continue
        if extra is not None and not extra(eye, rotation):
            continue
        showing.append(round(float(share), 2))
    return showing


def main():
    """Runs every assertion and prints each failure; returns 1 on a failure."""
    failures = []
    entities, _, _ = flight.parse_config()
    all_poses = poses()
    for name, mesh in ((PORTAL, PORTAL_MESH), (SIGNPOST, SIGNPOST_MESH), (TABLE, TABLE_MESH), (HALL, HALL_MESH)):
        if entities.get(name, (None,))[0] != mesh:
            print("FAIL scene has no AddEntity %s %s" % (name, mesh))
            return 1
    for mesh in GONE_MESHES:
        users = [name for name, (used, _) in entities.items() if used == mesh]
        if users or os.path.exists(os.path.join(flight.MODELS, mesh)):
            failures.append("%s is still in the scene (%s) or in models/" % (mesh, ", ".join(users) or "unused"))

    # The table stays at the entrance of the hall and the campaign camera stays where it was.
    if tuple(entities[TABLE][1]) != TABLE_POSITION:
        failures.append("the campaign table moved to %s (stays at %s)" % (tuple(entities[TABLE][1]), TABLE_POSITION))
    if tuple(all_poses.get("campaign", ())) != CAMPAIGN_POSE:
        failures.append("Pose campaign changed to %s (stays %s)" % (all_poses.get("campaign"), CAMPAIGN_POSE))

    origin = entities[PORTAL][1]
    parts = submeshes(os.path.join(flight.MODELS, PORTAL_MESH))
    if FIRE_MATERIAL not in parts or BOWL_MATERIAL not in parts:
        print("FAIL the portal mesh has no %s or no %s faces" % (FIRE_MATERIAL, BOWL_MATERIAL))
        return 1
    portal = world_triangles(PORTAL_MESH, origin)
    vertices, triangles = parts[FIRE_MATERIAL]
    fire = vertices[triangles] + origin
    stone = np.concatenate([parts[material][0][parts[material][1]] for material in STONE_MATERIALS
                            if material in parts]) + origin
    signpost = world_triangles(SIGNPOST_MESH, entities[SIGNPOST][1])
    vertices, triangles = submeshes(os.path.join(flight.MODELS, SIGNPOST_MESH))[BOARD_MATERIAL]
    board = vertices[triangles] + entities[SIGNPOST][1]
    table = world_triangles(TABLE_MESH, entities[TABLE][1])
    others = {name: world_triangles(mesh, position) for name, (mesh, position) in entities.items()
              if name not in SKY and name not in (PORTAL, SIGNPOST)}
    ground = np.concatenate(list(others.values()))

    # Right behind the table, centred, in front of the back wall and between the side walls, its foot on the floor.
    table_back = table[:, :, 1].max()
    low, high = portal.reshape(-1, 3).min(axis=0), portal.reshape(-1, 3).max(axis=0)
    middle_x = (low[0] + high[0]) / 2
    table_x = (table[:, :, 0].min() + table[:, :, 0].max()) / 2
    if abs(middle_x - table_x) > MAX_PORTAL_OFFSET:
        failures.append("the portal (middle x %.2f) is not centred behind the table (x %.2f)" % (middle_x, table_x))
    if low[1] < table_back + MIN_TABLE_GAP or high[1] > HALL_BACK_WALL:
        failures.append("the portal (y %.2f..%.2f) does not stand between the table (back edge y %.2f, gap %.1f) and "
                        "the hall's back wall (y %.2f)" % (low[1], high[1], table_back, MIN_TABLE_GAP, HALL_BACK_WALL))
    if low[0] < -HALL_HALF_WIDTH or high[0] > HALL_HALF_WIDTH:
        failures.append("the portal (x %.2f..%.2f) reaches into the hall's side walls" % (low[0], high[0]))
    for x, y in ((low[0] + 0.6, low[1] + 0.6), (high[0] - 0.6, low[1] + 0.6), (low[0] + 0.6, high[1] - 0.6),
                 (high[0] - 0.6, high[1] - 0.6)):
        floor = floor_height(ground, x, y)
        foot = heights_at(portal, x, y)
        if floor is None or not len(foot) or abs(foot.min() - floor) > MAX_FOOT_GAP:
            failures.append("the portal foot at (%.1f, %.1f) does not stand on the hall floor" % (x, y))

    # A stone arch filled with green fire that faces the table.
    normals = np.cross(fire[:, 1] - fire[:, 0], fire[:, 2] - fire[:, 0])
    areas = np.linalg.norm(normals, axis=1) / 2
    facing = normals[:, 1] / (2 * areas + 1e-12)
    fire_area = areas.sum()
    fire_low, fire_high = fire.reshape(-1, 3).min(axis=0), fire.reshape(-1, 3).max(axis=0)
    fire_centre = (fire_low + fire_high) / 2
    if (facing > -0.9).any():
        failures.append("%d fire faces do not face the table (-y)" % int((facing > -0.9).sum()))
    if (fire_area < MIN_FIRE_AREA or fire_high[0] - fire_low[0] < MIN_FIRE_WIDTH
            or fire_high[2] - fire_low[2] < MIN_FIRE_HEIGHT):
        failures.append("the fire covers %.2f m2, %.2f wide and %.2f high (need %.1f, %.1f, %.1f)"
                        % (fire_area, fire_high[0] - fire_low[0], fire_high[2] - fire_low[2], MIN_FIRE_AREA,
                           MIN_FIRE_WIDTH, MIN_FIRE_HEIGHT))
    for x, label in ((fire_low[0] - 0.3, "left pillar"), (fire_high[0] + 0.3, "right pillar")):
        heights = heights_at(stone, x, fire_centre[1])
        if not len(heights) or heights.max() < fire_centre[2]:
            failures.append("no stone %s beside the fire at x %.2f" % (label, x))
    crown = heights_at(stone, fire_centre[0], fire_centre[1])
    if not len(crown) or crown.max() < fire_high[2] + 0.3:
        failures.append("no stone arch over the top of the fire (z %.2f)" % fire_high[2])
    block = material_block(FIRE_MATERIAL)
    if "lighting off" not in block or "texture MenuMoreyaPortalFire.png" not in block or "scroll_anim" not in block:
        failures.append(FIRE_MATERIAL + " must ignore the scene lights and let MenuMoreyaPortalFire.png rise")
    texture = np.asarray(Image.open(os.path.join(ROOT, "materials", "textures", "menu", "MenuMoreyaPortalFire.png"))
                         .convert("RGB"), dtype=float)
    bright = texture[texture.max(axis=2) > 60]
    green = ((bright[:, 1] > 2 * bright[:, 0]) & (bright[:, 1] > 2 * bright[:, 2])).mean() if len(bright) else 0.0
    if green < GREEN_SHARE:
        failures.append("only %.2f of the bright fire texels are green (need %.2f)" % (green, GREEN_SHARE))

    # The particle effects: green flames in the opening, orange flames over the two bowls in front of the fire.
    effects = set(re.findall(r"(?m)^AddParticleEffect %s (\S+)" % PORTAL,
                             open(flight.CONFIG, encoding="utf-8").read()))
    if effects != {GREEN_FIRE, BOWL_FIRE}:
        failures.append("the portal carries the particle effects %s, need %s and %s"
                        % (sorted(effects), GREEN_FIRE, BOWL_FIRE))
    emitters, colours = particle_system(GREEN_FIRE)
    if not emitters or any(not (colour[1] > colour[0] and colour[1] > colour[2]) for colour in colours):
        failures.append(GREEN_FIRE + " has no green flames")
    for emitter in emitters:
        point = emitter + origin
        if abs(point[0] - fire_centre[0]) > 0.5 or not fire_low[2] < point[2] < fire_high[2]:
            failures.append("%s emits at %s, not in the opening of the portal" % (GREEN_FIRE, tuple(point)))
    vertices, triangles = parts[BOWL_MATERIAL]
    bowls = patches(vertices[triangles] + origin)[:2]
    emitters, colours = particle_system(BOWL_FIRE)
    if len(bowls) < 2 or len(emitters) != 2:
        failures.append("the portal needs two fire bowls with one flame emitter each (%d bowls, %d emitters)"
                        % (len(bowls), len(emitters)))
    else:
        if (bowls[0][0] - fire_centre[0]) * (bowls[1][0] - fire_centre[0]) >= 0:
            failures.append("the fire bowls do not stand left and right of the fire")
        for bowl in bowls:
            if bowl[1] >= fire_centre[1]:
                failures.append("a fire bowl at y %.2f does not stand in front of the fire (y %.2f)"
                                % (bowl[1], fire_centre[1]))
            near = [emitter + origin for emitter in emitters
                    if np.linalg.norm((emitter + origin - bowl)[:2]) <= BOWL_REACH
                    and 0.0 <= (emitter + origin - bowl)[2] <= BOWL_LIFT]
            if not near:
                failures.append("no flame emitter over the fire bowl at (%.2f, %.2f, %.2f)" % tuple(bowl))
        if any(not colour[0] > colour[1] > colour[2] for colour in colours):
            failures.append(BOWL_FIRE + " has no orange flames")

    # The back wall is whole behind the portal and the yard floor where the stairwell was is whole again.
    hall = others[HALL]
    hall_bounds = (hall.min(axis=1), hall.max(axis=1))
    x_min, x_max, z_min, z_max, step = WALL_AREA
    closed = [blocked(hall, np.array([x, HALL_BACK_WALL - 1.0, z]), np.array([x, HALL_BACK_WALL + 2.0, z]),
                      bounds=hall_bounds)
              for x in np.arange(x_min, x_max + 1e-6, step) for z in np.arange(z_min, z_max + 1e-6, step)]
    if np.mean(closed) < MIN_WALL_SHARE:
        failures.append("the hall's back wall is open: only %.2f of the sight lines through it end in it (need %.2f)"
                        % (np.mean(closed), MIN_WALL_SHARE))
    for x, y in OLD_STAIRWELL:
        floor = floor_height(ground, x, y)
        if floor is None or abs(floor) > MAX_FLOOR_STEP:
            failures.append("the yard floor where the stairwell was has a hole at (%.1f, %.1f)" % (x, y))

    # The campaign flight shows the fire and the arch crown, and the signpost board, in the gate_exit frame and in at
    # least one later frame; only triangles near the box around the flight path and both can hide them.
    path = np.array([flight_pose(all_poses, share)[:3] for share in np.arange(0.0, 1.0001, 0.05)])
    corridor = np.vstack((path, portal.reshape(-1, 3), signpost.reshape(-1, 3)))
    box_low, box_high = corridor.min(axis=0) - 0.5, corridor.max(axis=0) + 0.5
    occluders = np.concatenate((ground, portal, signpost))
    occluders = occluders[np.all(occluders.max(axis=1) >= box_low, axis=1)
                          & np.all(occluders.min(axis=1) <= box_high, axis=1)]
    bounds = (occluders.min(axis=1), occluders.max(axis=1))
    crown_top = np.array([fire_centre[0], fire_centre[1] - 0.6, crown.max() + 0.02]) if len(crown) else fire_high
    fire_middle = fire_centre - np.array([0.0, 0.03, 0.0])
    back, tip, direction, normal = arrow(board)
    centre = board.reshape(-1, 3).mean(axis=0)

    def board_readable(eye, rotation, aspect):
        """Tells whether the whole board is in view, facing the camera and long enough on screen."""
        if any(not in_view(eye, rotation, point, aspect) for point in board.reshape(-1, 3)):
            return False
        if normal @ ((eye - centre) / np.linalg.norm(eye - centre)) < MIN_FACING:
            return False
        return board_pixels(eye, rotation, board, aspect) >= MIN_BOARD_PIXELS

    for aspect in ASPECTS:
        showing = visible_frames(all_poses, aspect, [fire_middle], occluders, bounds)
        if 0.0 not in showing or len(showing) < 2:
            failures.append("at aspect %.2f the middle of the fire shows in flight frames %s, need gate_exit and one "
                            "more" % (aspect, showing))
        if 0.0 not in visible_frames(all_poses, aspect, [fire_middle, crown_top], occluders, bounds):
            failures.append("at aspect %.2f the gate_exit frame does not show the crown of the arch" % aspect)
        board_points = [point + normal * 0.03 for point in (centre, tip, back)]
        showing = visible_frames(all_poses, aspect, board_points, occluders, bounds,
                                 lambda eye, rotation: board_readable(eye, rotation, aspect))
        if 0.0 not in showing or len(showing) < 2:
            failures.append("at aspect %.2f the board (readable, at least %d pixels long) shows in flight frames %s, "
                            "need gate_exit and one more" % (aspect, MIN_BOARD_PIXELS, showing))

    # The signpost stands on the hall floor left of the portal; its board is upright and points towards the fire.
    foot = entities[SIGNPOST][1]
    floor = floor_height(ground, foot[0], foot[1])
    post = heights_at(signpost, foot[0], foot[1])
    if floor is None or not len(post) or not post.min() <= floor <= post.min() + 0.6 or post.max() < 2.0:
        failures.append("signpost post at (%.2f, %.2f) does not stand on the ground" % (foot[0], foot[1]))
    sign_low, sign_high = signpost.reshape(-1, 3).min(axis=0), signpost.reshape(-1, 3).max(axis=0)
    if not (table_back < foot[1] < HALL_BACK_WALL and foot[0] < low[0] and sign_low[0] > -HALL_HALF_WIDTH
            and sign_high[1] < HALL_BACK_WALL):
        failures.append("signpost at (%.2f, %.2f) does not stand in the hall left of the portal" % (foot[0], foot[1]))
    if abs(direction[2]) > MAX_BOARD_TILT or abs(normal[2]) > MAX_BOARD_TILT:
        failures.append("signpost board is not upright: arrow (%.2f, %.2f, %.2f), normal z %.2f"
                        % (direction[0], direction[1], direction[2], normal[2]))
    towards = fire_centre - back
    towards[2] = 0.0
    pointing = direction @ (towards / np.linalg.norm(towards))
    if pointing < MIN_POINTING:
        failures.append("signpost arrow (%.2f, %.2f, %.2f) does not point towards the portal (%.2f)"
                        % (direction[0], direction[1], direction[2], pointing))
    if np.linalg.norm(tip - back) < MIN_BOARD_LENGTH:
        failures.append("signpost board is only %.2f long (need %.1f)" % (np.linalg.norm(tip - back), MIN_BOARD_LENGTH))

    # No flat glowing slab in the rear yard: embers there are lumps, not a plane.
    for name, (mesh, position) in entities.items():
        for material, (vertices, triangles) in submeshes(os.path.join(flight.MODELS, mesh)).items():
            if material not in GLOW_SLAB_MATERIALS or not len(triangles):
                continue
            glowing = vertices[triangles] + position
            middle = glowing.mean(axis=1)
            inside = ((middle[:, 0] > YARD[0]) & (middle[:, 0] < YARD[1]) & (middle[:, 1] > YARD[2])
                      & (middle[:, 1] < YARD[3]))
            largest = largest_flat_patch(glowing[inside]) if inside.any() else 0.0
            if largest > MAX_FLAT_GLOW:
                failures.append("%s has a flat %s patch of %.2f m2 in the rear yard (at most %.2f)"
                                % (name, material, largest, MAX_FLAT_GLOW))
    # The board shows "Moreya".
    covered, stray = letters_match()
    if covered < MIN_LETTER_MATCH or stray > 1.0 - MIN_LETTER_MATCH:
        failures.append("board texture does not show the letters of Moreya (%.2f covered, %.2f stray)"
                        % (covered, stray))

    # CREDITS.
    credits = open(os.path.join(ROOT, "CREDITS"), encoding="utf-8").read()
    for name in (PORTAL_MESH, SIGNPOST_MESH, "MenuMoreyaPortalFire.png", "MenuMoreyaPortalFireShade.png",
                 "MenuMoreyaSignpostBoard.png", "MenuMoreyaSignpostBoardNormal.png"):
        if name not in credits:
            failures.append("CREDITS has no entry for " + name)

    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: portal %.2f behind the table, fire %.2f m2 (%.2f x %.2f), arch crown at %.2f, %.2f of the fire texels "
          "green; board arrow (%.2f, %.2f, %.2f) points at the portal (%.2f); letters %.2f"
          % (low[1] - table_back, fire_area, fire_high[0] - fire_low[0], fire_high[2] - fire_low[2], crown.max(),
             green, direction[0], direction[1], direction[2], pointing, covered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
