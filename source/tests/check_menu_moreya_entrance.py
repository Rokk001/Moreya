#!/usr/bin/env python3
"""Checks the entrance into Moreya on the start screen: the staircase in the rear yard and its signpost.

No compile needed. Reads config/mainmenuscene.cfg and the binary meshes under models/ and asserts:

- the scene places the staircase MoreyaStairs (MenuMoreyaStairs.mesh) and the signpost MoreyaSignpost
  (MenuMoreyaSignpost.mesh); the campaign table stays at the entrance of the hall (TABLE_POSITION) and Pose campaign
  stays as it was (CAMPAIGN_POSE);
- the staircase is wide and deep and leads down: its treads span at least MIN_WIDTH across, form at least
  MIN_STEP_LEVELS levels that drop step by step in one direction, and the lowest lies at least MIN_DEPTH down;
  at least MIN_OPEN_LEVELS of them lie open to the sky;
- it lies in the rear yard: its open part starts behind the hall's back wall, at least MIN_GAP behind the table's
  back edge, and the stair head and signpost stay in front of the abandoned castle;
- both stand on the ground: the ground of the other entities under the corners of the stair rim lies between the
  bottom and the top of the rim, the foot of the signpost post reaches the ground, and the signpost stands beside
  the stair head (within MAX_SIGN_FROM_HEAD of it, beside the opening);
- the yard floor is open over the stairwell (no other entity covers its open treads) and whole around it (left,
  right, behind the head, beyond the tunnel mouth), and the hall floor behind the table has no hole;
- some frame of the campaign flight from gate_exit to campaign (vertical field of view 45 degrees, 16:9 and 4:3,
  path and rotation as RenderSceneMenu::samplePath) shows the whole board unhidden and facing the camera together
  with at least MIN_FLIGHT_STEPS open step levels;
- the board's arrow tip points down (at least MIN_POINTER_DROP) and along the descent, and the line from the tip
  along the arrow enters the stairwell opening;
- the board texture shows the word "Moreya": where it differs from the plain planks matches the letter shapes;
- the new files (stairs, signpost, the frame of the hall's back opening, board textures) have CREDITS entries.

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
TABLE, TABLE_MESH = "CampaignTable", "MenuMapTable.mesh"
#: The table stays at the entrance of the campaign hall and the campaign camera pose stays as it was.
TABLE_POSITION = (0.0, 22.0, 0.0)
CAMPAIGN_POSE = (0.0, 19.0, 7.0, 29.5, 0.0, 0.0)
#: The hall, the castle behind the rear yard and the stone frame of the opening in the hall's back wall.
HALL, CASTLE, ARCH_MESH = "CampaignHall", "AbandonedCastle", "MenuHallRearArch.mesh"
#: The hall floor behind the table stays whole up to this y (the back wall stands behind it).
HALL_FLOOR_END = 29.0
#: Free floor between the table's back edge and the stairwell, at least.
MIN_GAP = 6.0
#: Tread levels open to the sky (not under the tunnel ceiling), at least.
MIN_OPEN_LEVELS = 10
#: The signpost stands beside the stair head: at most this far from the head along the stairs and beside the opening.
MAX_SIGN_FROM_HEAD = 1.0
#: Some frame of the campaign flight from gate_exit to campaign shows the whole board and this many step levels.
MIN_FLIGHT_STEPS = 3
BOARD_MATERIAL = "MenuMoreyaSignpostBoard"
#: The material of the step stones (treads, landing and the steps behind the doorway).
STEP_MATERIAL = "MenuChippedStone"
SKY = ("Backdrop", "BloodMoon", "HorizonCrows", "VolcanicRuins")
#: Wide: the treads span at least this many units across (the campaign table is 4.4 wide).
MIN_WIDTH = 5.5
#: Deep: the lowest tread lies at least this far below the hall floor, over at least this many step levels.
MIN_DEPTH = 5.0
MIN_STEP_LEVELS = 15

#: Vertical field of view of the menu camera at 16:9 (REFERENCE_ASPECT) and the checked aspect ratios.
FOV_Y = 45.0
ASPECTS = (16.0 / 9.0, 4.0 / 3.0)
REFERENCE_ASPECT = 16.0 / 9.0
#: The arrow drops at least this much per unit along its length (about 20 degrees).
MIN_POINTER_DROP = 0.34
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


def main():
    """Runs every assertion and prints each failure; returns 1 on a failure."""
    failures = []
    entities, _, _ = flight.parse_config()
    all_poses = poses()
    for name, mesh in ((STAIRS, STAIRS_MESH), (SIGNPOST, SIGNPOST_MESH), (TABLE, TABLE_MESH)):
        if entities.get(name, (None,))[0] != mesh:
            print("FAIL scene has no AddEntity %s %s" % (name, mesh))
            return 1

    # The table stays at the entrance of the hall and the campaign camera stays where it was.
    if tuple(entities[TABLE][1]) != TABLE_POSITION:
        failures.append("the campaign table moved to %s (stays at %s)" % (tuple(entities[TABLE][1]), TABLE_POSITION))
    if tuple(all_poses.get("campaign", ())) != CAMPAIGN_POSE:
        failures.append("Pose campaign changed to %s (stays %s)" % (all_poses.get("campaign"), CAMPAIGN_POSE))

    stairs = world_triangles(STAIRS_MESH, entities[STAIRS][1])
    sign_parts = submeshes(os.path.join(flight.MODELS, SIGNPOST_MESH))
    signpost = world_triangles(SIGNPOST_MESH, entities[SIGNPOST][1])
    vertices, triangles = sign_parts[BOARD_MATERIAL]
    board = vertices[triangles] + entities[SIGNPOST][1]
    table = world_triangles(entities[TABLE][0], entities[TABLE][1])
    others = {name: world_triangles(mesh, position) for name, (mesh, position) in entities.items()
              if name not in SKY and name not in (STAIRS, SIGNPOST)}
    ground = np.concatenate(list(others.values()))

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
            rows.append((points[:, 2].mean(), points[:, 1].mean(), np.ptp(points[:, 0]), points[:, 1].min(),
                         points[:, 1].max()))
    if len(rows) < MIN_STEP_LEVELS:
        print("FAIL only %d tread levels at least %.1f wide (need %d)" % (len(rows), MIN_WIDTH, MIN_STEP_LEVELS))
        return 1
    if rows[-1][0] > -MIN_DEPTH:
        failures.append("lowest tread at %.2f, not %.1f deep" % (rows[-1][0], MIN_DEPTH))
    along = 1.0 if rows[-1][1] > rows[0][1] else -1.0
    if any((lower[1] - upper[1]) * along <= 0 for upper, lower in zip(rows, rows[1:])):
        failures.append("the tread levels do not drop step by step in one direction")

    # The open part of the stairwell: tread levels with nothing of the stairs above them (no tunnel ceiling).
    open_rows = []
    for row in rows:
        middle = (row[3] + row[4]) / 2
        above = heights_at(stairs, origin[0], middle)
        if not len(above[above > row[0] + 0.3]):
            open_rows.append(row)
    if len(open_rows) < MIN_OPEN_LEVELS:
        failures.append("only %d tread levels lie open to the sky (need %d)" % (len(open_rows), MIN_OPEN_LEVELS))
    # The head is the upper end of the open part, its far end lies where the tunnel begins.
    head_y = open_rows[0][3] if along > 0 else open_rows[0][4]
    end_y = min(row[3] for row in open_rows) if along < 0 else max(row[4] for row in open_rows)
    open_y = (min(row[3] for row in open_rows), max(row[4] for row in open_rows))

    # In the rear yard: behind the hall, before the castle, far behind the table.
    table_back = table[:, :, 1].max()
    hall_back = others[HALL][:, :, 1].max()
    castle_front = others[CASTLE][:, :, 1].min()
    gap = open_y[0] - table_back
    if gap < MIN_GAP:
        failures.append("only %.2f of floor between the table (back edge y %.2f) and the stairwell (y %.2f), need %.1f"
                        % (gap, table_back, open_y[0], MIN_GAP))
    if open_y[0] <= hall_back:
        failures.append("the stairwell starts at y %.2f, inside the campaign hall (back y %.2f)" % (open_y[0], hall_back))
    raised = stairs[stairs[:, :, 2].max(axis=1) > 0.05]
    if raised[:, :, 1].max() >= castle_front or signpost[:, :, 1].max() >= castle_front:
        failures.append("the stair head reaches the abandoned castle (front y %.2f)" % castle_front)

    # Standing on the ground: the rim corners and the signpost foot.
    for x in (origin[0] - 3.3, origin[0] + 3.3):
        for y in (head_y + along * 0.2, end_y - along * 0.2):
            ground_height = floor_height(ground, x, y)
            rim = heights_at(stairs, x, y)
            if ground_height is None or not len(rim) or not rim.min() <= ground_height <= rim.max():
                failures.append("stair rim at (%.1f, %.1f) does not stand on the ground" % (x, y))
    foot = entities[SIGNPOST][1]
    below = [height for height in (floor_height(ground, foot[0], foot[1]), floor_height(stairs, foot[0], foot[1]))
             if height is not None]
    post = heights_at(signpost, foot[0], foot[1])
    if not below or not len(post) or not post.min() <= max(below) <= post.min() + 0.6 or post.max() < 2.0:
        failures.append("signpost post at (%.2f, %.2f) does not stand on the ground" % (foot[0], foot[1]))
    if abs(foot[1] - head_y) > MAX_SIGN_FROM_HEAD or not 3.0 <= abs(foot[0] - origin[0]) <= 3.0 + MAX_SIGN_FROM_HEAD:
        failures.append("signpost at (%.2f, %.2f) does not stand beside the stair head (y %.2f)"
                        % (foot[0], foot[1], head_y))

    # The floor is open over the stairwell and whole around it.
    covering = set()
    for name, part in others.items():
        for row in open_rows:
            for dx in (-2.0, 0.0, 2.0):
                y = (row[3] + row[4]) / 2
                tread = heights_at(stairs, origin[0] + dx, y)
                over = heights_at(part, origin[0] + dx, y)
                if len(tread) and len(over[(over > tread.max() + 0.01) & (over < 8.0)]):
                    covering.add(name)
    if covering:
        failures.append("the stairwell opening is covered by " + ", ".join(sorted(covering)))
    middle_y = sum(open_y) / 2
    for x, y, label in ((origin[0] - 3.9, middle_y, "left"), (origin[0] + 3.9, middle_y, "right"),
                        (origin[0], head_y - along * 0.9, "behind the head"),
                        (origin[0], end_y + along * 0.5, "beyond the tunnel mouth")):
        floor = floor_height(ground, x, y)
        if floor is None or abs(floor) > 0.2:
            failures.append("no floor %s of the stairwell at (%.1f, %.1f)" % (label, x, y))
    for y in np.arange(table_back + 0.5, HALL_FLOOR_END, 0.5):
        floor = floor_height(ground, origin[0], y)
        if floor is None or abs(floor) > 0.2:
            failures.append("the hall floor behind the table has a hole at y %.1f" % y)
            break

    # The campaign flight from gate_exit to campaign sees the board and the steps going down. Every sight line runs
    # between the flight path and the stairs, so only the triangles near the box around both can hide anything.
    occluders = np.concatenate((ground, stairs, signpost))
    path = np.array([flight_pose(all_poses, share)[:3] for share in np.arange(0.0, 1.0001, 0.05)])
    corridor = np.vstack((path, stairs.reshape(-1, 3), signpost.reshape(-1, 3)))
    low, high = corridor.min(axis=0) - 0.5, corridor.max(axis=0) + 0.5
    occluders = occluders[np.all(occluders.max(axis=1) >= low, axis=1) & np.all(occluders.min(axis=1) <= high, axis=1)]
    bounds = (occluders.min(axis=1), occluders.max(axis=1))
    back, tip, direction, normal = arrow(board)
    centre = board.reshape(-1, 3).mean(axis=0)
    for aspect in ASPECTS:
        best = (0, -1.0, None)
        for share in np.arange(0.0, 1.0001, 0.05):
            eye, rotation = camera(flight_pose(all_poses, share))
            if any(not in_view(eye, rotation, point, aspect) for point in board.reshape(-1, 3)):
                continue
            if any(blocked(occluders, eye, point + normal * 0.03, bounds=bounds) for point in (centre, tip)):
                continue
            if normal @ ((eye - centre) / np.linalg.norm(eye - centre)) < MIN_FACING:
                continue
            seen = 0
            for row in open_rows:
                for y in (row[3] + 0.1, (row[3] + row[4]) / 2, row[4] - 0.1):
                    hit = False
                    for dx in (-2.0, 0.0, 2.0):
                        surface = heights_at(steps, origin[0] + dx, y)
                        surface = surface[np.abs(surface - row[0]) < 0.1]
                        if len(surface):
                            point = np.array([origin[0] + dx, y, surface.max() + 0.03])
                            if in_view(eye, rotation, point, aspect) and not blocked(occluders, eye, point,
                                                                                    bounds=bounds):
                                hit = True
                                break
                    if hit:
                        seen += 1
                        break
                if seen >= MIN_FLIGHT_STEPS:
                    break
            if seen > best[0]:
                best = (seen, share, eye)
            if seen >= MIN_FLIGHT_STEPS:
                break
        if best[0] < MIN_FLIGHT_STEPS:
            failures.append("no frame of the campaign flight at aspect %.2f shows the board and %d step levels "
                            "(best %d)" % (aspect, MIN_FLIGHT_STEPS, best[0]))

    # The pointer points down the stairs.
    if direction[2] > -MIN_POINTER_DROP or direction[1] * along <= 0.25:
        failures.append("signpost arrow (%.2f, %.2f, %.2f) does not point down along the stairs" % tuple(direction))
    else:
        reach = tip + direction * ((tip[2] + 1.0) / -direction[2])
        if not (abs(reach[0] - origin[0]) < 3.0 and open_y[0] < reach[1] < open_y[1]):
            failures.append("signpost arrow line meets z -1 at (%.2f, %.2f), outside the stairwell" % tuple(reach[:2]))

    # The board shows "Moreya".
    covered, stray = letters_match()
    if covered < MIN_LETTER_MATCH or stray > 1.0 - MIN_LETTER_MATCH:
        failures.append("board texture does not show the letters of Moreya (%.2f covered, %.2f stray)"
                        % (covered, stray))

    # CREDITS.
    credits = open(os.path.join(ROOT, "CREDITS"), encoding="utf-8").read()
    for name in (STAIRS_MESH, SIGNPOST_MESH, ARCH_MESH, "MenuMoreyaSignpostBoard.png",
                 "MenuMoreyaSignpostBoardNormal.png"):
        if name not in credits:
            failures.append("CREDITS has no entry for " + name)

    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: stairs in the rear yard %.2f behind the table, %d levels down to %.2f (%d open), %.1f wide; "
          "board arrow (%.2f, %.2f, %.2f); letters %.2f"
          % (gap, len(rows), rows[-1][0], len(open_rows), rows[0][2], direction[0], direction[1], direction[2],
             covered))
    return 0

if __name__ == "__main__":
    sys.exit(main())
