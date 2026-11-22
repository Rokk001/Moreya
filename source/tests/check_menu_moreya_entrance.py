#!/usr/bin/env python3
"""Checks the campaign scene of the main menu: the forecourt behind the campaign table and its green portal.

No compile needed. Reads config/mainmenuscene.cfg, the menu scene code, the particle and material scripts, the
textures and the binary meshes under models/ and asserts:

- the start screen stays as it was: its entities START_SCENE (hall, wooden table, frame of the old opening,
  staircase, signpost, rear buildings, forge coals, castle) keep their meshes and places, and those meshes keep their
  bytes (START_MESHES, SHA-1);
- the campaign scene ([MenuCampaignScene]) shows exactly CAMPAIGN_SCENE and CAMPAIGN_LIGHTS and hides exactly the
  start entities, and RenderSceneMenu reads that section and switches the scene on the campaign flight; every check
  below looks at the scene as the campaign view shows it (the start entities left out);
- the campaign scene places the forecourt MoreyaForecourt (MenuMoreyaForecourt.mesh), the frame of the opening in the
  hall's back wall ForecourtArch (MenuHallForecourtArch.mesh), the open hall CampaignHallOpen and the portal
  MoreyaPortal (MenuMoreyaPortal.mesh); the stone table stays at the entrance of the hall (TABLE_POSITION) and Pose
  campaign stays as it was (CAMPAIGN_POSE);
- the table is weathered stone, no wood (TABLE_STONE share of its faces, no WOOD_MATERIALS), with moss on it, and it
  carries the map plane (MenuCampaignMap);
- behind the table the hall's back wall is open over OPENING_AREA (at least MIN_OPENING_SHARE of the sight lines
  through it pass) into a large forecourt: its walls stand at least MIN_FORECOURT_WIDTH apart and its rear wall at
  least MIN_FORECOURT_DEPTH behind the hall's back wall (HALL_BACK_WALL); its floor is paved and whole and a clear
  path (PATH_HALF either side of the middle) leads over it to the portal open to the sky (nothing on it higher than
  MAX_CLUTTER);
- the forecourt is old, abandoned and overgrown, not clean: moss covers at least MIN_MOSS_AREA, dead wood stands in
  it (MIN_DEAD_WOOD triangles of MenuAgedWood), rubble lies in it (MIN_RUBBLE triangles of MenuRoughStone), and each
  side wall has fallen somewhere to at most MAX_BREACH_TOP while standing elsewhere at least MIN_WALL_TOP high;
- the portal stands at the far end of the forecourt: centred behind the table (MAX_PORTAL_OFFSET), its fire at least
  MIN_PORTAL_DISTANCE behind the table's back edge and its back at most MAX_PORTAL_FROM_REAR in front of the rear
  wall, its foot on the forecourt floor (MAX_FOOT_GAP);
- it is a stone arch filled with green fire: the fire faces (FIRE_MATERIAL) face the hall, cover at least
  MIN_FIRE_AREA and an opening at least MIN_FIRE_WIDTH wide and MIN_FIRE_HEIGHT high; stone stands on both sides of
  the fire (pillars) and over its top (arch); the fire material ignores the scene lights and lets its texture rise;
  the texture is green (GREEN_SHARE of its bright texels); the green flame particles rise in the opening and the
  orange flames burn over two fire bowls (MenuEmber patches of the portal) left and right in front of the fire;
- the gate_exit frame of the campaign flight to campaign (vertical field of view 45 degrees at 16:9, 16:9 and 4:3,
  path and rotation as RenderSceneMenu::samplePath) shows the middle of the fire and the crown of the arch unhidden;
  it and at least one more frame of the flight show the middle of the fire unhidden;
- no glowing material forms a flat slab in the rear yard behind the forecourt (largest flat connected patch at most
  MAX_FLAT_GLOW);
- the files of the entrance (table, forecourt, frame, portal, fire textures) have CREDITS entries.

Sky and horizon elements (Backdrop, BloodMoon, HorizonCrows, VolcanicRuins) are neither ground nor occluders.
"""
import hashlib
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
TABLE, TABLE_MESH = "CampaignStoneTable", "MenuMapTableStone.mesh"
HALL, HALL_MESH = "CampaignHallOpen", "MenuCampaignHallOpen.mesh"
FORECOURT, FORECOURT_MESH = "MoreyaForecourt", "MenuMoreyaForecourt.mesh"
ARCH, ARCH_MESH = "ForecourtArch", "MenuHallForecourtArch.mesh"
#: The start screen: its entities with mesh and place, and the SHA-1 of their meshes (counted once on this branch).
START_SCENE = {"CampaignHall": ("MenuCampaignHall.mesh", (0.0, 22.0, 0.0)),
               "CampaignTable": ("MenuMapTable.mesh", (0.0, 22.0, 0.0)),
               "HallRearArch": ("MenuHallRearArch.mesh", (0.0, 0.0, 0.0)),
               "MoreyaStairs": ("MenuMoreyaStairs.mesh", (0.0, 31.0, 0.0)),
               "MoreyaSignpost": ("MenuMoreyaSignpost.mesh", (-3.7, 31.2, 0.0)),
               "FortressRear": ("MenuFortressRear.mesh", (0.0, 0.0, 0.0)),
               "ForgeCoals": ("MenuForgeCoals.mesh", (0.0, 0.0, 0.0)),
               "AbandonedCastle": ("MenuAbandonedCastle.mesh", (0.0, 0.0, 0.0))}
START_MESHES = {"MenuCampaignHall.mesh": "05cb9dd1a241828a", "MenuMapTable.mesh": "9bdb82a4c38aa4cf",
                "MenuHallRearArch.mesh": "01104c3f3df9e01a", "MenuMoreyaStairs.mesh": "c86396a13a29a760",
                "MenuOuterGround.mesh": "cb24fe4aa84dbe8d", "MenuFortressRear.mesh": "d033c9d4f46b553c",
                "MenuForgeCoals.mesh": "e15c0b3c243609ad", "MenuAbandonedCastle.mesh": "d1d4d9922f6f17e1",
                "MenuMoreyaSignpost.mesh": "c2b98c0baac223f4"}
#: The campaign scene: the entities and lights it shows.
CAMPAIGN_SCENE = ("CampaignHallOpen", "CampaignStoneTable", "ForecourtArch", "MoreyaForecourt", "MoreyaPortal",
                  "FortressRearBack", "ForgeCoalsBack", "AbandonedCastleBack")
CAMPAIGN_LIGHTS = ("PortalBowlLeft", "PortalBowlRight")
MENU_CODE = os.path.join(ROOT, "source", "renderscene", "RenderSceneMenu.cpp")
#: The table is stone: at least this share of its faces (by area, the map and parchment left out) is stone, none wood.
TABLE_STONE = 0.8
STONE_LOOK = ("MenuStone", "MenuDarkStone", "MenuCarvedStone", "MenuRoughStone", "MenuChippedStone", "MenuMoss",
              "MenuLichen", "MenuWaterStain", "MenuBlack")
WOOD_MATERIALS = ("MenuWood", "MenuAgedWood")
MAP_MATERIAL = "MenuCampaignMap"
#: The table stays at the entrance of the campaign hall and the campaign camera pose stays as it was.
TABLE_POSITION = (0.0, 22.0, 0.0)
CAMPAIGN_POSE = (0.0, 19.0, 7.0, 29.5, 0.0, 0.0)
#: The inner face of the hall's back wall (scene y); the opening in it is sampled over OPENING_AREA (x min, x max,
#: z min, z max, step) and at least MIN_OPENING_SHARE of the sight lines through it must pass.
HALL_BACK_WALL = 29.25
OPENING_AREA = (-4.5, 4.5, 0.5, 5.5, 0.25)
MIN_OPENING_SHARE = 0.95
#: The forecourt: its walls stand at least this far apart and its rear wall at least this far behind the hall's back
#: wall; on the path (PATH_HALF either side of the middle) nothing stands higher than MAX_CLUTTER (sampled every
#: CLUTTER_STEP).
MIN_FORECOURT_WIDTH = 23.0
MIN_FORECOURT_DEPTH = 28.0
PATH_HALF = 3.0
MAX_CLUTTER = 0.5
CLUTTER_STEP = 1.0
#: The forecourt is an overgrown ruin: least moss area (square units), dead wood and rubble (triangles), and the side
#: walls (sampled every WALL_STEP) fall somewhere to at most MAX_BREACH_TOP while standing elsewhere MIN_WALL_TOP high.
MIN_MOSS_AREA = 120.0
MIN_DEAD_WOOD = 200
MIN_RUBBLE = 800
MAX_BREACH_TOP = 4.5
MIN_WALL_TOP = 6.5
WALL_STEP = 0.5
#: The portal is centred behind the table (x offset at most), its fire at least this far behind the table's back edge,
#: its back at most this far in front of the forecourt's rear wall, and its foot at most this far from the floor.
MAX_PORTAL_OFFSET = 0.3
MIN_PORTAL_DISTANCE = 30.0
MAX_PORTAL_FROM_REAR = 1.5
MAX_FOOT_GAP = 0.15
#: The green fire: its material, the least area of its faces and the least width and top height of the opening.
FIRE_MATERIAL = "MenuMoreyaPortalFire"
MIN_FIRE_AREA = 25.0
MIN_FIRE_WIDTH = 4.5
MIN_FIRE_HEIGHT = 7.0
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
#: Glowing materials that must not form a flat slab in the rear yard (YARD: x min, x max, y min, y max), and the
#: largest flat connected patch of them allowed there in square units.
GLOW_SLAB_MATERIALS = ("MenuEmber", "MenuFlame", "MenuFlameCore")
YARD = (-9.0, 9.0, 61.5, 72.0)
MAX_FLAT_GLOW = 0.1
SKY = ("Backdrop", "BloodMoon", "HorizonCrows", "VolcanicRuins")

#: Vertical field of view of the menu camera at 16:9 (REFERENCE_ASPECT) and the checked aspect ratios.
FOV_Y = 45.0
ASPECTS = (16.0 / 9.0, 4.0 / 3.0)
REFERENCE_ASPECT = 16.0 / 9.0



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


def campaign_section():
    """Returns {kind: [names]} of the [MenuCampaignScene] section of config/mainmenuscene.cfg."""
    text = open(flight.CONFIG, encoding="utf-8").read()
    if "[MenuCampaignScene]" not in text:
        return {}
    body = text.split("[MenuCampaignScene]", 1)[1].split("[/MenuCampaignScene]", 1)[0]
    result = {}
    for line in body.splitlines():
        words = line.split()
        if len(words) == 2 and not words[0].startswith("#"):
            result.setdefault(words[0], []).append(words[1])
    return result


def main():
    """Runs every assertion and prints each failure; returns 1 on a failure."""
    failures = []
    entities, _, _ = flight.parse_config()
    all_poses = poses()

    # The start screen stays as it was.
    for name, (mesh, position) in START_SCENE.items():
        if name not in entities or entities[name][0] != mesh or tuple(entities[name][1]) != position:
            failures.append("the start screen entity %s is not %s at %s" % (name, mesh, position))
    for mesh, digest in START_MESHES.items():
        found = hashlib.sha1(open(os.path.join(flight.MODELS, mesh), "rb").read()).hexdigest()[:16]
        if found != digest:
            failures.append("the start screen mesh %s changed (SHA-1 %s, was %s)" % (mesh, found, digest))
    # The campaign scene shows its own entities and lights instead of the start screen's ones.
    section = campaign_section()
    if (sorted(section.get("Show", [])) != sorted(CAMPAIGN_SCENE)
            or sorted(section.get("ShowLight", [])) != sorted(CAMPAIGN_LIGHTS)
            or sorted(section.get("Hide", [])) != sorted(START_SCENE)):
        failures.append("[MenuCampaignScene] must show %s and %s and hide %s, has %s"
                        % (sorted(CAMPAIGN_SCENE), sorted(CAMPAIGN_LIGHTS), sorted(START_SCENE), section))
    code = open(MENU_CODE, encoding="utf-8").read()
    for needle in ('"[MenuCampaignScene]"', "showCampaignScene(renderManager, false);", "updateCampaignScene(renderManager);",
                   'CAMPAIGN_PLACE = "campaign"'):
        if needle not in code:
            failures.append("RenderSceneMenu.cpp does not switch the campaign scene (%s)" % needle)
    entities = {name: value for name, value in entities.items() if name not in section.get("Hide", [])}
    for name, mesh in ((PORTAL, PORTAL_MESH), (TABLE, TABLE_MESH), (HALL, HALL_MESH), (FORECOURT, FORECOURT_MESH),
                       (ARCH, ARCH_MESH)):
        if entities.get(name, (None,))[0] != mesh:
            print("FAIL scene has no AddEntity %s %s" % (name, mesh))
            return 1

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
    table = world_triangles(TABLE_MESH, entities[TABLE][1])
    others = {name: world_triangles(mesh, position) for name, (mesh, position) in entities.items()
              if name not in SKY and name != PORTAL}
    ground = np.concatenate(list(others.values()))

    # The table is weathered stone with moss, no wood, and carries the map.
    table_parts = submeshes(os.path.join(flight.MODELS, TABLE_MESH))
    areas_by_material = {}
    for material, (vertices, triangles) in table_parts.items():
        corners = vertices[triangles]
        areas_by_material[material] = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0],
                                                              corners[:, 2] - corners[:, 0]), axis=1).sum() / 2
    body = sum(area for material, area in areas_by_material.items() if material not in (MAP_MATERIAL, "MenuParchment"))
    stone_share = sum(areas_by_material.get(material, 0.0) for material in STONE_LOOK) / max(body, 1e-9)
    if stone_share < TABLE_STONE or any(material in table_parts for material in WOOD_MATERIALS):
        failures.append("the table is not weathered stone: %.2f of it is stone, wood materials %s"
                        % (stone_share, sorted(set(table_parts) & set(WOOD_MATERIALS))))
    if "MenuMoss" not in table_parts or MAP_MATERIAL not in table_parts:
        failures.append("the stone table has no moss or no map plane")

    # The forecourt behind the hall: the opening in the back wall, the walls round it, its open, paved floor.
    table_back = table[:, :, 1].max()
    low, high = portal.reshape(-1, 3).min(axis=0), portal.reshape(-1, 3).max(axis=0)
    hall = others[HALL]
    hall_bounds = (hall.min(axis=1), hall.max(axis=1))
    x_min, x_max, z_min, z_max, step = OPENING_AREA
    passing = [not blocked(hall, np.array([x, HALL_BACK_WALL - 1.0, z]), np.array([x, HALL_BACK_WALL + 2.0, z]),
                           bounds=hall_bounds)
               for x in np.arange(x_min, x_max + 1e-6, step) for z in np.arange(z_min, z_max + 1e-6, step)]
    if np.mean(passing) < MIN_OPENING_SHARE:
        failures.append("the hall's back wall is closed: only %.2f of the sight lines through its opening pass (need "
                        "%.2f)" % (np.mean(passing), MIN_OPENING_SHARE))
    court = others[FORECOURT]
    court_bounds = (court.min(axis=1), court.max(axis=1))
    middle_y = (HALL_BACK_WALL + low[1]) / 2
    walls = []
    for side in (-1.0, 1.0):
        reach = 0.0
        for distance in np.arange(1.0, 30.0, 0.25):
            if blocked(court, np.array([0.0, middle_y, 3.0]), np.array([side * distance, middle_y, 3.0]),
                       bounds=court_bounds, margin=0.0):
                reach = distance
                break
        walls.append(reach)
    rear = 0.0
    for distance in np.arange(HALL_BACK_WALL + 1.0, HALL_BACK_WALL + 60.0, 0.25):
        if blocked(court, np.array([0.0, HALL_BACK_WALL + 0.5, high[2] + 0.5]), np.array([0.0, distance, high[2] + 0.5]),
                   bounds=court_bounds, margin=0.0):
            rear = distance
            break
    width, depth = sum(walls), rear - HALL_BACK_WALL
    if min(walls) == 0.0 or width < MIN_FORECOURT_WIDTH or rear == 0.0 or depth < MIN_FORECOURT_DEPTH:
        failures.append("the forecourt is %.2f wide and %.2f deep (need %.1f and %.1f)"
                        % (width, depth, MIN_FORECOURT_WIDTH, MIN_FORECOURT_DEPTH))
    # Only the triangles over the forecourt matter for its floor and for what stands on it.
    area_low = np.array([-walls[0] - 1.0, HALL_BACK_WALL, -5.0])
    area_high = np.array([walls[1] + 1.0, low[1], 40.0])

    def over_forecourt(triangles):
        """Returns the triangles whose bounding boxes reach into the box over the forecourt."""
        return triangles[np.all(triangles.max(axis=1) >= area_low, axis=1)
                         & np.all(triangles.min(axis=1) <= area_high, axis=1)]

    clutter = over_forecourt(np.concatenate([part for name, part in others.items() if name != HALL]))
    court_ground = over_forecourt(ground)
    for x in np.arange(-PATH_HALF, PATH_HALF + 1e-6, CLUTTER_STEP):
        for y in np.arange(HALL_BACK_WALL + 1.5, low[1] - 0.5, CLUTTER_STEP):
            floor = floor_height(court_ground, x, y)
            if floor is None or abs(floor) > MAX_FLOOR_STEP:
                failures.append("the forecourt floor has a hole at (%.1f, %.1f)" % (x, y))
                continue
            standing = heights_at(clutter, x, y)
            if len(standing[(standing > floor + MAX_CLUTTER) & (standing < 40.0)]):
                failures.append("something stands or hangs over the path to the portal at (%.1f, %.1f)" % (x, y))

    # An overgrown ruin: moss, dead wood, rubble and fallen parts of both side walls.
    court_parts = submeshes(os.path.join(flight.MODELS, FORECOURT_MESH))

    def total_area(material):
        """Returns the area of the forecourt faces of one material."""
        if material not in court_parts:
            return 0.0
        vertices, triangles = court_parts[material]
        corners = vertices[triangles]
        return np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1).sum() / 2

    moss = total_area("MenuMoss")
    dead_wood = len(court_parts.get("MenuAgedWood", (None, ()))[1])
    rubble = len(court_parts.get("MenuRoughStone", (None, ()))[1])
    if moss < MIN_MOSS_AREA or dead_wood < MIN_DEAD_WOOD or rubble < MIN_RUBBLE:
        failures.append("the forecourt is too clean: %.1f m2 moss, %d dead wood and %d rubble triangles (need %.0f, "
                        "%d, %d)" % (moss, dead_wood, rubble, MIN_MOSS_AREA, MIN_DEAD_WOOD, MIN_RUBBLE))
    wall_tops = []
    for side, reach in ((-1.0, walls[0]), (1.0, walls[1])):
        x = side * (reach + 0.6)
        tops = [heights_at(court, x, y) for y in np.arange(HALL_BACK_WALL + 2.0, rear - 1.0, WALL_STEP)]
        tops = [values.max() for values in tops if len(values)]
        wall_tops.append((min(tops), max(tops)) if tops else (0.0, 0.0))
        if not tops or min(tops) > MAX_BREACH_TOP or max(tops) < MIN_WALL_TOP:
            failures.append("the %s wall has not partly fallen (tops %.2f..%.2f, need one below %.1f and one above %.1f)"
                            % ("left" if side < 0 else "right", wall_tops[-1][0], wall_tops[-1][1], MAX_BREACH_TOP,
                               MIN_WALL_TOP))

    # The portal at the far end of the forecourt: centred behind the table, its back at the rear wall, on the floor.
    middle_x = (low[0] + high[0]) / 2
    table_x = (table[:, :, 0].min() + table[:, :, 0].max()) / 2
    if abs(middle_x - table_x) > MAX_PORTAL_OFFSET:
        failures.append("the portal (middle x %.2f) is not centred behind the table (x %.2f)" % (middle_x, table_x))
    if rear and not 0.0 <= rear - high[1] <= MAX_PORTAL_FROM_REAR:
        failures.append("the portal (back y %.2f) does not stand at the forecourt's rear wall (y %.2f)"
                        % (high[1], rear))
    for x, y in ((low[0] + 0.6, low[1] + 0.6), (high[0] - 0.6, low[1] + 0.6), (low[0] + 0.6, high[1] - 0.6),
                 (high[0] - 0.6, high[1] - 0.6)):
        floor = floor_height(ground, x, y)
        foot = heights_at(portal, x, y)
        if floor is None or not len(foot) or abs(foot.min() - floor) > MAX_FOOT_GAP + 0.25:
            failures.append("the portal foot at (%.1f, %.1f) does not stand on the forecourt floor" % (x, y))

    # A stone arch filled with green fire that faces the hall and stands far behind the table.
    normals = np.cross(fire[:, 1] - fire[:, 0], fire[:, 2] - fire[:, 0])
    areas = np.linalg.norm(normals, axis=1) / 2
    facing = normals[:, 1] / (2 * areas + 1e-12)
    fire_area = areas.sum()
    fire_low, fire_high = fire.reshape(-1, 3).min(axis=0), fire.reshape(-1, 3).max(axis=0)
    fire_centre = (fire_low + fire_high) / 2
    if fire_centre[1] - table_back < MIN_PORTAL_DISTANCE:
        failures.append("the fire is only %.2f behind the table's back edge (need %.1f)"
                        % (fire_centre[1] - table_back, MIN_PORTAL_DISTANCE))
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

    # The floor where the stairwell was is whole again.
    for x, y in OLD_STAIRWELL:
        floor = floor_height(ground, x, y)
        if floor is None or abs(floor) > MAX_FLOOR_STEP:
            failures.append("the yard floor where the stairwell was has a hole at (%.1f, %.1f)" % (x, y))

    # The campaign flight shows the fire and the arch crown in the gate_exit frame and the fire in at least one later
    # frame; only triangles near the box around the flight path and the portal can hide them.
    path = np.array([flight_pose(all_poses, share)[:3] for share in np.arange(0.0, 1.0001, 0.05)])
    corridor = np.vstack((path, portal.reshape(-1, 3)))
    box_low, box_high = corridor.min(axis=0) - 0.5, corridor.max(axis=0) + 0.5
    occluders = np.concatenate((ground, portal))
    occluders = occluders[np.all(occluders.max(axis=1) >= box_low, axis=1)
                          & np.all(occluders.min(axis=1) <= box_high, axis=1)]
    bounds = (occluders.min(axis=1), occluders.max(axis=1))
    # A point just above the front edge of the crown (the front of the stones within half a unit of its top).
    top_stones = stone[stone[:, :, 2].max(axis=1) > crown.max() - 0.5] if len(crown) else stone
    crown_top = (np.array([fire_centre[0], top_stones[:, :, 1].min() - 0.05, crown.max() + 0.02]) if len(crown)
                 else fire_high)
    fire_middle = fire_centre - np.array([0.0, 0.03, 0.0])
    for aspect in ASPECTS:
        showing = visible_frames(all_poses, aspect, [fire_middle], occluders, bounds)
        if 0.0 not in showing or len(showing) < 2:
            failures.append("at aspect %.2f the middle of the fire shows in flight frames %s, need gate_exit and one "
                            "more" % (aspect, showing))
        if 0.0 not in visible_frames(all_poses, aspect, [fire_middle, crown_top], occluders, bounds):
            failures.append("at aspect %.2f the gate_exit frame does not show the crown of the arch" % aspect)
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
    # CREDITS.
    credits = open(os.path.join(ROOT, "CREDITS"), encoding="utf-8").read()
    for name in (TABLE_MESH, FORECOURT_MESH, ARCH_MESH, PORTAL_MESH, "MenuMoreyaPortalFire.png",
                 "MenuMoreyaPortalFireShade.png"):
        if name not in credits:
            failures.append("CREDITS has no entry for " + name)

    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: start screen unchanged (%d entities, %d meshes); campaign scene of %d entities and %d lights; stone table (%.2f stone); forecourt %.2f wide, %.2f deep, opening %.2f open, %.1f m2 moss, %d dead wood "
          "and %d rubble triangles, walls fallen to %.2f and %.2f; fire %.2f behind the table, %.2f m2 (%.2f x %.2f), "
          "arch crown at %.2f, %.2f of the fire texels green"
          % (len(START_SCENE), len(START_MESHES), len(CAMPAIGN_SCENE), len(CAMPAIGN_LIGHTS), stone_share, width, depth, np.mean(passing), moss, dead_wood, rubble, wall_tops[0][0], wall_tops[1][0],
             fire_centre[1] - table_back, fire_area, fire_high[0] - fire_low[0], fire_high[2] - fire_low[2],
             crown.max(), green))
    return 0


if __name__ == "__main__":
    sys.exit(main())
