#!/usr/bin/env python3
"""Checks the entrance into Moreya on the start screen: the staircase behind the campaign table and its signpost.

No compile needed. Reads config/mainmenuscene.cfg and the binary meshes under models/ and asserts:

- the scene places the staircase MoreyaStairs (MenuMoreyaStairs.mesh) and the signpost MoreyaSignpost
  (MenuMoreyaSignpost.mesh); both lie behind the campaign table (further along +Y than every point of the table);
- the staircase is wide and deep and leads down: its treads span at least MIN_WIDTH across, form at least
  MIN_STEP_LEVELS levels that drop step by step along +Y, and the lowest lies at least MIN_DEPTH below the floor;
- both stand on the ground: the ground of the other entities under the corners of the stair rim lies between the
  bottom and the top of the rim, and the foot of the signpost post reaches the ground (or the kerb) below it;
- the hall floor is open over the stairwell: no other entity covers the treads of the open part from above;
- from the camera pose "campaign" (vertical field of view 45 degrees, 16:9 and 4:3) the signpost board lies in the
  view and is not hidden, and at least MIN_VISIBLE_STEPS step levels are seen, down to MIN_VISIBLE_DEPTH;
- the board front faces that camera, its arrow tip points down (at least MIN_POINTER_DROP) and along the descent,
  and the line from the tip along the arrow enters the stairwell opening;
- the board texture shows the word "Moreya": where it differs from the plain planks matches the letter shapes;
- the new files have CREDITS entries.

Sky and horizon elements (Backdrop, BloodMoon, HorizonCrows, VolcanicRuins) are neither ground nor occluders.
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_menu_flight_geometry as flight  # noqa: E402

ROOT = flight.ROOT
STAIRS, STAIRS_MESH = "MoreyaStairs", "MenuMoreyaStairs.mesh"
SIGNPOST, SIGNPOST_MESH = "MoreyaSignpost", "MenuMoreyaSignpost.mesh"
TABLE = "CampaignTable"
BOARD_MATERIAL = "MenuMoreyaSignpostBoard"
#: The material of the step stones (treads, landing and the steps behind the doorway).
STEP_MATERIAL = "MenuChippedStone"
SKY = ("Backdrop", "BloodMoon", "HorizonCrows", "VolcanicRuins")
#: Wide: the treads span at least this many units across (the campaign table is 4.4 wide).
MIN_WIDTH = 5.5
#: Deep: the lowest tread lies at least this far below the hall floor, over at least this many step levels.
MIN_DEPTH = 5.0
MIN_STEP_LEVELS = 15
#: Seen from the campaign pose: number of step levels with a visible tread and the depth the view reaches.
MIN_VISIBLE_STEPS = 6
MIN_VISIBLE_DEPTH = -2.0
#: Vertical field of view of the menu camera and the checked aspect ratios.
FOV_Y = 45.0
ASPECTS = (16.0 / 9.0, 4.0 / 3.0)
#: The arrow drops at least this much per unit along its length (about 20 degrees).
MIN_POINTER_DROP = 0.34
#: The board front must face the camera: cosine between its normal and the direction to the camera.
MIN_FACING = 0.3
#: Share of the letter shapes that must coincide with the painted change of the board texture.
MIN_LETTER_MATCH = 0.8


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
                shared = flight.read_geometry(data, s2, e2)
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
                        vertices = flight.read_geometry(data, s3, e3)
                        break
            triangles = np.array(indices, dtype=np.int64).reshape(-1, 3)
            old_vertices, old_triangles = result.get(material, (np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)))
            result[material] = (np.vstack((old_vertices, np.array(vertices, dtype=np.float64))),
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


def blocked(triangles, start, end, margin=0.03):
    """Tells whether a segment from start to end hits a triangle before it comes within margin of the end."""
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
    """Tells whether a point lies inside the camera frame of the given aspect ratio."""
    local = rotation.T @ (point - eye)
    depth = -local[2]
    if depth < 0.1:
        return False
    half = math.tan(math.radians(FOV_Y) / 2)
    return abs(local[0] / depth) <= half * aspect and abs(local[1] / depth) <= half


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
    high = along > along.max() - 0.15 * length
    low = along < along.min() + 0.15 * length
    # The pointed end narrows to the tip: its points spread less across the board than those of the square end.
    if np.ptp(across[high]) > np.ptp(across[low]):
        axis, along, high, low = -axis, -along, low, high
    tip = points[np.argmax(along)]
    back = points[low].mean(axis=0)
    direction = tip - back
    return back, tip, direction / np.linalg.norm(direction), normal


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


def main():
    """Runs every assertion and prints each failure; returns 1 on a failure."""
    failures = []
    entities, _, _ = flight.parse_config()
    for name, mesh in ((STAIRS, STAIRS_MESH), (SIGNPOST, SIGNPOST_MESH)):
        if entities.get(name, (None,))[0] != mesh:
            print("FAIL scene has no AddEntity %s %s" % (name, mesh))
            return 1
    stairs = world_triangles(STAIRS_MESH, entities[STAIRS][1])
    sign_parts = submeshes(os.path.join(flight.MODELS, SIGNPOST_MESH))
    signpost = world_triangles(SIGNPOST_MESH, entities[SIGNPOST][1])
    vertices, triangles = sign_parts[BOARD_MATERIAL]
    board = vertices[triangles] + entities[SIGNPOST][1]
    table = world_triangles(entities[TABLE][0], entities[TABLE][1])
    others = [world_triangles(mesh, position) for name, (mesh, position) in entities.items()
              if name not in SKY and name not in (STAIRS, SIGNPOST)]
    ground = np.concatenate(others)

    # Behind the table.
    table_back = table[:, :, 1].max()
    for name, part in ((STAIRS, stairs), (SIGNPOST, signpost)):
        if part[:, :, 1].min() <= table_back:
            failures.append("%s reaches y %.2f, not behind the table (back edge y %.2f)"
                            % (name, part[:, :, 1].min(), table_back))

    # Wide, deep, leading down: upward faces of the step stones grouped by height.
    origin = entities[STAIRS][1]
    vertices, triangles = submeshes(os.path.join(flight.MODELS, STAIRS_MESH))[STEP_MATERIAL]
    steps = vertices[triangles] + origin
    normals = np.cross(steps[:, 1] - steps[:, 0], steps[:, 2] - steps[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None] + 1e-12
    centres = steps.mean(axis=1)
    treads = (normals[:, 2] > 0.95) & (centres[:, 2] < -0.1)
    levels = {}
    for centre, triangle in zip(centres[treads], steps[treads]):
        levels.setdefault(round(centre[2] / 0.1), []).append(triangle)
    rows = []
    for key in sorted(levels, reverse=True):
        points = np.concatenate(levels[key])
        if np.ptp(points[:, 0]) >= MIN_WIDTH:
            rows.append((points[:, 2].mean(), points[:, 1].mean(), np.ptp(points[:, 0]), points[:, 1].max()))
    if len(rows) < MIN_STEP_LEVELS:
        failures.append("only %d tread levels at least %.1f wide (need %d)" % (len(rows), MIN_WIDTH, MIN_STEP_LEVELS))
    elif rows[-1][0] > -MIN_DEPTH:
        failures.append("lowest tread at %.2f, not %.1f deep" % (rows[-1][0], MIN_DEPTH))
    if any(lower[1] <= upper[1] for upper, lower in zip(rows, rows[1:])):
        failures.append("the tread levels do not drop step by step along +Y")

    # Standing on the ground: the rim corners and the signpost foot.
    for dx, dy in ((-3.3, -0.2), (3.3, -0.2), (-3.3, 4.8), (3.3, 4.8)):
        x, y = origin[0] + dx, origin[1] + dy
        ground_heights = heights_at(ground, x, y)
        ground_heights = ground_heights[ground_heights < 1.0]
        rim = heights_at(stairs, x, y)
        if not len(ground_heights) or not len(rim) or not rim.min() <= ground_heights.max() <= rim.max():
            failures.append("stair rim at (%.1f, %.1f) does not stand on the ground" % (x, y))
    foot = entities[SIGNPOST][1]
    below = np.concatenate((heights_at(ground, foot[0], foot[1]), heights_at(stairs, foot[0], foot[1])))
    below = below[below < 1.0]
    post = heights_at(signpost, foot[0], foot[1])
    if not len(below) or not len(post) or not post.min() <= below.max() <= post.min() + 0.6 or post.max() < 2.0:
        failures.append("signpost post at (%.2f, %.2f) does not stand on the ground" % (foot[0], foot[1]))

    # The hall floor is open over the stairwell: nothing of another entity lies over the treads of the open part.
    covering = set()
    for name, (mesh, position) in entities.items():
        if name in SKY or name in (STAIRS, SIGNPOST):
            continue
        part = world_triangles(mesh, position)
        for dx in (-2.0, 0.0, 2.0):
            for dy in (0.6, 2.0, 3.5, 4.7):
                tread = heights_at(stairs, origin[0] + dx, origin[1] + dy)
                over = heights_at(part, origin[0] + dx, origin[1] + dy)
                if len(tread) and len(over[(over > tread.max() + 0.01) & (over < 8.0)]):
                    covering.add(name)
    if covering:
        failures.append("the stairwell opening is covered by " + ", ".join(sorted(covering)))

    # The campaign pose sees the board and the steps going down.
    eye, rotation = camera(poses()["campaign"])
    occluders = np.concatenate((ground, stairs, signpost))
    back, tip, direction, normal = arrow(board)
    for aspect in ASPECTS:
        outside = [point for point in board.reshape(-1, 3) if not in_view(eye, rotation, point, aspect)]
        if outside:
            failures.append("signpost board leaves the campaign view at aspect %.2f" % aspect)
        seen = []
        # Each tread is sampled just before its far edge: the nosing of the step above hides its near part.
        for depth, _, _, far in rows:
            y = far - 0.1
            for dx in (-2.0, 0.0, 2.0):
                surface = heights_at(steps, origin[0] + dx, y)
                surface = surface[np.abs(surface - depth) < 0.1]
                if not len(surface):
                    continue
                point = np.array([origin[0] + dx, y, surface.max() + 0.03])
                if in_view(eye, rotation, point, aspect) and not blocked(occluders, eye, point):
                    seen.append(depth)
                    break
        if len(seen) < MIN_VISIBLE_STEPS or min(seen, default=0.0) > MIN_VISIBLE_DEPTH:
            failures.append("campaign view at aspect %.2f sees %d step levels down to %.2f (need %d, %.1f)"
                            % (aspect, len(seen), min(seen, default=0.0), MIN_VISIBLE_STEPS, MIN_VISIBLE_DEPTH))
    centre = board.reshape(-1, 3).mean(axis=0)
    for label, point in (("centre", centre + normal * 0.03), ("tip", tip + normal * 0.03)):
        if blocked(occluders, eye, point):
            failures.append("signpost board %s is hidden from the campaign view" % label)
    towards_camera = (eye - centre) / np.linalg.norm(eye - centre)
    if normal @ towards_camera < MIN_FACING:
        failures.append("signpost board faces away from the campaign camera (%.2f)" % (normal @ towards_camera))

    # The pointer points down the stairs.
    if direction[2] > -MIN_POINTER_DROP or direction[1] <= 0.25:
        failures.append("signpost arrow (%.2f, %.2f, %.2f) does not point down along the stairs" % tuple(direction))
    else:
        reach = tip + direction * ((tip[2] + 1.0) / -direction[2])
        if not (abs(reach[0] - origin[0]) < 3.0 and origin[1] < reach[1] < origin[1] + 5.0):
            failures.append("signpost arrow line meets z -1 at (%.2f, %.2f), outside the stairwell" % tuple(reach[:2]))

    # The board shows "Moreya".
    covered, stray = letters_match()
    if covered < MIN_LETTER_MATCH or stray > 1.0 - MIN_LETTER_MATCH:
        failures.append("board texture does not show the letters of Moreya (%.2f covered, %.2f stray)"
                        % (covered, stray))

    # CREDITS.
    credits = open(os.path.join(ROOT, "CREDITS"), encoding="utf-8").read()
    for name in (STAIRS_MESH, SIGNPOST_MESH, "MenuMoreyaEntrance.material", "MenuMoreyaSignpostBoard.png",
                 "MenuMoreyaSignpostBoardNormal.png"):
        if name not in credits:
            failures.append("CREDITS has no entry for " + name)

    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: stairs %d levels down to %.2f, %.1f wide; board arrow (%.2f, %.2f, %.2f); letters %.2f"
          % (len(rows), rows[-1][0], rows[0][2], direction[0], direction[1], direction[2], covered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
