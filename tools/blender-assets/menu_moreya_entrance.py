"""Build the entrance into Moreya for the start screen: the staircase behind the campaign table and its signpost.

    MenuMoreyaStairs    a wide stone staircase that leads from the floor of the campaign hall down into the ground,
                        under the back wall of the hall and on to an ember-lit doorway; kerb and low parapets
                        frame the opening, iron ember bowls hang on the stairwell walls
    MenuMoreyaSignpost  a smaller signpost of the start screen signpost family (moreya_raid_models.py PartBuilder,
                        same wood, iron and board planks); its arrow board carries the word "Moreya" and its tip
                        points down into the stairwell

Units are menu scene units. The stairs' origin is the middle of the upper edge of the first step on the hall floor
(z 0); the stairs descend along +Y. The opening on the floor is x -3.0..3.0, y 0..5.0 of the mesh; the scene places
the mesh at (0, 24.2, 0), behind the campaign table, so the floor of the campaign hall must be open over
x -3.0..3.0, y 24.2..29.2. The signpost's origin is the foot of its post; the scene places it on the front left kerb
stone. The board front faces the campaign camera and its tip points into the stairwell, down and along +Y.

Run in Blender (5.x):
    blender --background --python menu_moreya_entrance.py -- <repo> <private output folder> [stairs] [signpost]
        [render]
"stairs" and "signpost" write <name>.blend and <name>.mesh.xml into the private folder and convert the meshes with
OgreXMLConverter into <repo>/models. "render" renders the menu scene of config/mainmenuscene.cfg from the campaign
pose and the waypoints of the campaign flight into <private>/renders (see render_poses). The board lettering is
written by tools/gen_menu_signpost_lettering.py (--text Moreya). Progress goes to <private>/menu_moreya_entrance.log.
"""
import math
import os
import subprocess
import sys
import traceback
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

#: Inner half width of the stairwell, tread depth and riser height of a step, number of steps.
HALF, TREAD, RISE, STEPS = 3.0, 0.5, 0.3, 20
#: Length of the open part of the stairwell (the rest runs under the back wall of the hall) and of the landing.
OPEN_LENGTH, LANDING = 5.0, 1.6
#: The stairwell walls: mortar plane behind the blocks and the depth of the wall blocks.
BACKING = HALF + 0.06
#: Ceiling of the tunnel under the hall: underside height at the open end and its slope (parallel to the steps).
CEILING_START, CEILING_SLOPE = -1.05, RISE / TREAD
#: The doorway at the foot of the stairs: half width, height above the landing, depth of the recess.
DOOR_HALF, DOOR_HEIGHT, DOOR_DEPTH = 1.1, 1.75, 1.2
#: Signpost: board outline in its own frame (back end, shoulder, tip, lower and upper edge), thickness planes,
#: the tilt of the board (tip down) and the turn of the whole signpost about Z towards the campaign camera.
SIGN_BACK, SIGN_SHOULDER, SIGN_TIP = -0.30, 1.80, 2.10
SIGN_BOTTOM, SIGN_TOP = 1.75, 2.35
SIGN_FRONT_Y, SIGN_BACK_Y = -0.22, -0.135
SIGN_PIVOT_Z = 2.05
SIGN_TILT, SIGN_TURN = 32.0, 30.0

LOG = None


def log(text):
    """Writes one progress line to the log file of the run."""
    LOG.write(text + "\n")
    LOG.flush()


def tread_height(y):
    """Returns the height of the tread at distance y along the stairs (0 before the first step, flat on the landing)."""
    if y < 0.0:
        return 0.0
    return -(min(int(y / TREAD), STEPS - 1) + 1) * RISE


def ceiling_height(y):
    """Returns the underside height of the tunnel ceiling at distance y along the stairs."""
    end = STEPS * TREAD
    return CEILING_START - CEILING_SLOPE * (min(max(y, OPEN_LENGTH), end) - OPEN_LENGTH)


def box(b, x0, x1, y0, y1, z0, z1, material, grain=(1, 0, 0)):
    """Adds an axis-aligned box between two corners."""
    b.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, z1 - z0), material, grain)


def profile_x(b, profile, x0, x1, material, grain=(1, 0, 0)):
    """Extrudes a convex profile given as (y, z) points from x0 to x1."""
    b.solid([(x0, y, z) for y, z in profile], (x1 - x0, 0, 0), material, grain)


def wall_face(b, side, y0, y1, z0, z1, material):
    """Adds one quad of the stairwell wall plane at x = side * BACKING facing the inside of the stairwell."""
    x = side * BACKING
    points = [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
    b.face(points if side < 0 else list(reversed(points)), material, (0, 1, 0))


def add_steps(b):
    """Adds the steps: each step is a row of worn slabs with chipped nosings, slightly uneven."""
    for index in range(STEPS):
        front = index * TREAD
        top = tread_height(front)
        x = -BACKING
        while x < BACKING - 0.05:
            width = b.rng.uniform(0.9, 1.7)
            right = min(x + width, BACKING)
            if BACKING - right < 0.6:
                right = BACKING
            lift = b.rng.uniform(-0.02, 0.015)
            chip = b.rng.uniform(0.03, 0.06) if b.rng.random() < 0.6 else b.rng.uniform(0.08, 0.16)
            shift = b.rng.uniform(-0.03, 0.02)
            # The stairs descend along +Y: the far edge of each tread is the worn nosing over the next, lower step,
            # and the slab reaches back under the step above it.
            edge = front + TREAD + shift
            profile = [(front - 0.08, top - RISE - 0.12), (edge, top - RISE - 0.12), (edge, top + lift - chip * 0.7),
                       (edge - chip, top + lift), (front - 0.08, top + lift)]
            profile_x(b, profile, x + 0.012, right - 0.012, "MenuChippedStone")
            x = right
    # The landing at the foot of the stairs.
    end = STEPS * TREAD
    bottom = tread_height(end)
    x = -BACKING
    while x < BACKING - 0.05:
        right = min(x + b.rng.uniform(1.0, 1.6), BACKING)
        if BACKING - right < 0.6:
            right = BACKING
        y = end
        while y < end + LANDING - 0.05:
            far = min(y + b.rng.uniform(0.6, 0.9), end + LANDING + 0.1)
            box(b, x + 0.012, right - 0.012, y + 0.012, far - 0.012, bottom - 0.4, bottom + b.rng.uniform(-0.02, 0.01),
                "MenuChippedStone")
            y = far
        x = right


def add_walls(b):
    """Adds both stairwell walls: a mortar plane and coursed stone blocks in front of it, under the ceiling."""
    end = STEPS * TREAD + LANDING
    for side in (-1, 1):
        wall_face(b, side, -0.1, end + 0.1, -7.5, 0.0, "MenuSoot")
        top = 0.0
        while top > -7.4:
            height = b.rng.uniform(0.3, 0.42)
            y = -b.rng.uniform(0.0, 0.5)
            while y < end:
                length = b.rng.uniform(0.55, 1.1)
                far = min(y + length, end + 0.1)
                if y < OPEN_LENGTH < far:
                    # No block reaches from the open stairwell into the tunnel: the tunnel blocks end at its ceiling.
                    far = OPEN_LENGTH
                block_top = top
                if far > OPEN_LENGTH:
                    block_top = min(top, ceiling_height(y) + 0.3)
                block_bottom = top - height
                if block_top - block_bottom > 0.06 and block_top > tread_height(far) - RISE:
                    face = side * (HALF + b.rng.uniform(-0.025, 0.03))
                    inner, outer = sorted((face, side * (BACKING + 0.25)))
                    box(b, inner, outer, max(y, -0.1) + 0.02, far - 0.02, block_bottom + 0.02, block_top - 0.02,
                        "MenuDarkStone", (0, 1, 0))
                y = far
            top -= height


def add_ceiling(b):
    """Adds the tunnel under the back wall of the hall: a carved lintel and ceiling slabs following the steps."""
    box(b, -BACKING - 0.3, BACKING + 0.3, OPEN_LENGTH - 0.12, OPEN_LENGTH + 0.3, CEILING_START - 0.08, 0.0,
        "MenuCarvedStone")
    end = STEPS * TREAD + LANDING
    y = OPEN_LENGTH + 0.3
    while y < end + 0.05:
        far = min(y + b.rng.uniform(0.7, 1.0), end + 0.1)
        drop = b.rng.uniform(0.0, 0.04)
        near_z, far_z = ceiling_height(y) - drop, ceiling_height(far) - drop
        profile_x(b, [(y, near_z), (far, far_z), (far, far_z + 0.35), (y, near_z + 0.35)], -BACKING - 0.1,
                  BACKING + 0.1, "MenuDarkStone")
        y = far + 0.015


def add_doorway(b):
    """Adds the end wall at the foot of the stairs with a doorway whose steps lead on into the ember-lit deep."""
    end = STEPS * TREAD + LANDING
    floor = tread_height(STEPS * TREAD)
    ceiling = ceiling_height(end)
    lintel = floor + DOOR_HEIGHT
    box(b, -BACKING, -DOOR_HALF, end, end + 0.5, floor - 0.2, ceiling + 0.3, "MenuDarkStone")
    box(b, DOOR_HALF, BACKING, end, end + 0.5, floor - 0.2, ceiling + 0.3, "MenuDarkStone")
    box(b, -DOOR_HALF - 0.1, DOOR_HALF + 0.1, end - 0.08, end + 0.5, lintel, ceiling + 0.3, "MenuCarvedStone")
    back = end + DOOR_DEPTH
    for side in (-1, 1):
        inner, outer = sorted((side * DOOR_HALF, side * (DOOR_HALF + 0.3)))
        box(b, inner, outer, end + 0.5, back, floor - 1.2, lintel, "MenuDarkStone", (0, 1, 0))
    box(b, -DOOR_HALF - 0.3, DOOR_HALF + 0.3, end + 0.5, back, lintel, lintel + 0.3, "MenuDarkStone")
    box(b, -DOOR_HALF - 0.3, DOOR_HALF + 0.3, back, back + 0.3, floor - 1.2, lintel + 0.3, "MenuDarkStone")
    box(b, -DOOR_HALF, DOOR_HALF, end - 0.05, end + 0.5, floor - 0.4, floor, "MenuChippedStone")
    for index in range(3):
        y = end + 0.5 + index * 0.24
        far = back if index == 2 else y + 0.24
        box(b, -DOOR_HALF, DOOR_HALF, y, far, floor - 1.3, floor - (index + 1) * RISE, "MenuChippedStone")
    # Ember light from the deep: glowing cracks on the back of the recess and in the floor in front of it.
    crack(b, [(-0.8, floor - 0.9), (-0.45, floor - 0.2), (-0.55, floor + 0.5), (-0.2, floor + 1.2)],
          "y", back - 0.005, 0.035)
    crack(b, [(0.7, floor - 0.9), (0.4, floor - 0.1), (0.55, floor + 0.6), (0.25, floor + 1.4)], "y", back - 0.005,
          0.03)
    crack(b, [(-0.25, floor - 0.95), (0.05, floor - 0.4), (-0.05, floor + 0.3)], "y", back - 0.005, 0.025)


def crack(b, points, plane, offset, width):
    """Adds a glowing ember crack: a thin strip along a polyline of (a, b) points on a plane.

    plane "y" lays the strip on the plane y = offset facing -Y with points (x, z); plane "z" lays it on the plane
    z = offset facing up with points (x, y).
    """
    for (a0, b0), (a1, b1) in zip(points, points[1:]):
        length = math.hypot(a1 - a0, b1 - b0)
        na, nb = -(b1 - b0) / length * width, (a1 - a0) / length * width
        quad = [(a0 - na, b0 - nb), (a1 - na, b1 - nb), (a1 + na, b1 + nb), (a0 + na, b0 + nb)]
        if plane == "y":
            points3, wanted = [Vector((qa, offset, qb)) for qa, qb in quad], Vector((0, -1, 0))
        else:
            points3, wanted = [Vector((qa, qb, offset)) for qa, qb in quad], Vector((0, 0, 1))
        if (points3[1] - points3[0]).cross(points3[2] - points3[1]).dot(wanted) < 0:
            points3.reverse()
        b.face(points3, "MenuEmberCrack", (1, 0, 0))


def add_tread_cracks(b):
    """Adds glowing cracks on the lower steps, where the ember light of the deep comes up between the slabs."""
    for index in range(9, STEPS, 2):
        y = index * TREAD + b.rng.uniform(0.12, 0.38)
        x = b.rng.uniform(-2.2, 0.6)
        points = [(x, y)]
        for _ in range(3):
            x += b.rng.uniform(0.25, 0.55)
            points.append((x, y + b.rng.uniform(-0.05, 0.05)))
        crack(b, points, "z", tread_height(index * TREAD + 0.25) + 0.03, 0.018)


def add_kerb_and_parapets(b):
    """Adds the kerb stones in front of the first step and the low, partly broken parapets along both sides."""
    x = -HALF - 0.45
    while x < HALF + 0.45 - 0.05:
        right = min(x + b.rng.uniform(0.7, 1.2), HALF + 0.45)
        if HALF + 0.45 - right < 0.4:
            right = HALF + 0.45
        box(b, x + 0.015, right - 0.015, -0.38, 0.0, -0.35, 0.1 + b.rng.uniform(-0.02, 0.01), "MenuCarvedStone")
        x = right
    for side in (-1, 1):
        inner, outer = sorted((side * HALF, side * (HALF + 0.45)))
        y = 0.0
        while y < OPEN_LENGTH - 0.2:
            far = min(y + b.rng.uniform(0.7, 1.2), OPEN_LENGTH - 0.12)
            if OPEN_LENGTH - 0.12 - far < 0.5:
                far = OPEN_LENGTH - 0.12
            height = 0.45 + b.rng.uniform(-0.04, 0.03)
            if side > 0 and 2.0 < y < 3.4:
                # A broken stretch of the right parapet: the upper course has fallen onto the steps.
                height = 0.12 + b.rng.uniform(0.0, 0.05)
            box(b, inner + 0.01, outer - 0.01, y + 0.015, far - 0.015, -0.45, height, "MenuCarvedStone", (0, 1, 0))
            y = far
    for centre, size in (((HALF - 0.55, 2.65, tread_height(2.65) + 0.12), (0.34, 0.26, 0.17)),
                         ((HALF - 1.15, 3.35, tread_height(3.35) + 0.08), (0.22, 0.2, 0.12)),
                         ((HALF + 0.75, 2.4, 0.08), (0.2, 0.24, 0.12)),
                         ((-HALF + 0.4, 6.7, tread_height(6.7) + 0.08), (0.2, 0.18, 0.11))):
        b.rock(centre, size, "MenuRoughStone")


def add_ember_bowls(b):
    """Adds iron ember bowls on brackets along both walls; their coals glow."""
    for side in (-1, 1):
        for y in (1.6, 4.1, 7.0, 9.6):
            base = tread_height(y) + 1.05
            wall = side * HALF
            centre = Vector((side * (HALF - 0.32), y, base))
            b.log_column((wall + side * 0.02, y, base - 0.32), (centre.x, y, base - 0.06), 0.03, 0.03,
                         "MenuCorrodedIron", sides=6, rough=0.0)
            b.log_column((wall + side * 0.02, y, base + 0.02), (centre.x, y, base + 0.02), 0.025, 0.025,
                         "MenuCorrodedIron", sides=6, rough=0.0)
            bowl(b, centre)


def bowl(b, centre):
    """Adds one open iron bowl filled with glowing coals at a centre point (the rim height)."""
    sides = 10
    rim, foot, depth = 0.22, 0.1, 0.17
    upper = [centre + Vector((rim * math.cos(i * 2 * math.pi / sides), rim * math.sin(i * 2 * math.pi / sides), 0.0))
             for i in range(sides)]
    lower = [centre + Vector((foot * math.cos(i * 2 * math.pi / sides), foot * math.sin(i * 2 * math.pi / sides),
                              -depth)) for i in range(sides)]
    b.face(list(reversed(lower)), "MenuCorrodedIron", (0, 0, 1))
    for index in range(sides):
        following = (index + 1) % sides
        b.face((lower[index], lower[following], upper[following], upper[index]), "MenuCorrodedIron", (0, 0, 1))
        b.face((upper[index], upper[following], lower[following], lower[index]), "MenuCorrodedIron", (0, 0, 1))
    coals = [centre + Vector((0.92 * (point - centre).x, 0.92 * (point - centre).y, -0.03)) for point in upper]
    top = centre + Vector((0.0, 0.0, 0.03))
    for index in range(sides):
        b.face((coals[index], coals[(index + 1) % sides], top), "MenuEmber", (1, 0, 0))


def build_stairs(raid):
    """Builds the staircase with its walls, tunnel, doorway, kerb, parapets, ember bowls and cracks."""
    b = raid.PartBuilder("MenuMoreyaStairs", 2411)
    add_steps(b)
    add_walls(b)
    add_ceiling(b)
    add_doorway(b)
    add_tread_cracks(b)
    add_kerb_and_parapets(b)
    add_ember_bowls(b)
    return b.finish(["MenuChippedStone", "MenuDarkStone", "MenuCarvedStone", "MenuSoot", "MenuRoughStone",
                     "MenuCorrodedIron", "MenuEmber", "MenuEmberCrack"])


def transform_faces(b, first, matrix):
    """Moves the vertices and turns the grain of every face from index first on by a matrix."""
    rotation = matrix.to_3x3()
    for index in range(first, len(b.faces)):
        indices, material, grain, board = b.faces[index]
        for vertex in indices:
            b.vertices[vertex] = tuple(matrix @ Vector(b.vertices[vertex]))
        b.faces[index] = (indices, material, (rotation @ grain).normalized(), board)


def build_signpost(raid):
    """Builds the Moreya signpost: post, tilted arrow board with lettering face, iron rod, straps, nails, stones."""
    b = raid.PartBuilder("MenuMoreyaSignpost", 6607)
    b.board_material = "MenuMoreyaSignpostBoard"
    b.board_box = (SIGN_BACK, SIGN_TIP, SIGN_BOTTOM, SIGN_TOP)
    wood, iron, rust = "MenuSignpostWood", "MenuIron", "MenuCorrodedIron"
    post_top = Vector((-0.03, 0.02, 2.62))
    b.log_column((0, 0, -0.35), post_top, 0.13, 0.11, wood, sides=10, rough=0.015)
    b.log_column(post_top, post_top + Vector((0.0, 0.0, 0.18)), 0.12, 0.0, rust, sides=10, rough=0.0)
    b.solid([(-0.075, SIGN_BACK_Y, 1.62), (0.075, SIGN_BACK_Y, 1.62), (0.075, SIGN_BACK_Y, 2.48),
             (-0.075, SIGN_BACK_Y, 2.48)], (0, 0.085, 0), wood, (0, 0, 1))
    # Everything from here on belongs to the board and is tilted with it about the pivot on the post.
    first_board_face = len(b.faces)
    outline = [(SIGN_BACK, SIGN_BOTTOM), (SIGN_SHOULDER, SIGN_BOTTOM), (SIGN_TIP, (SIGN_BOTTOM + SIGN_TOP) / 2),
               (SIGN_SHOULDER, SIGN_TOP), (SIGN_BACK, SIGN_TOP)]
    b.solid([(x, SIGN_BACK_Y, z) for x, z in outline], (0, SIGN_FRONT_Y - SIGN_BACK_Y, 0), wood, (1, 0, 0),
            front_board=True)
    for x in (-0.145, 0.145):
        b.solid([(x - 0.028, SIGN_FRONT_Y - 0.011, SIGN_BOTTOM - 0.03), (x + 0.028, SIGN_FRONT_Y - 0.011,
                 SIGN_BOTTOM - 0.03), (x + 0.028, SIGN_FRONT_Y - 0.011, SIGN_TOP + 0.03),
                 (x - 0.028, SIGN_FRONT_Y - 0.011, SIGN_TOP + 0.03)], (0, 0.24, 0), rust, (0, 0, 1))
    for x, z in ((-0.22, 1.85), (-0.22, 2.25), (1.69, 1.85), (1.69, 2.25), (0.72, 1.84), (0.72, 2.26)):
        b.log_column((x, SIGN_FRONT_Y + 0.006, z), (x, SIGN_FRONT_Y - 0.021, z), 0.02, 0.016, iron, sides=6, rough=0)
    tilt = (Matrix.Translation((0, 0, SIGN_PIVOT_Z)) @ Matrix.Rotation(math.radians(SIGN_TILT), 4, "Y")
            @ Matrix.Translation((0, 0, -SIGN_PIVOT_Z)))
    transform_faces(b, first_board_face, tilt)
    # An iron rod from the top of the post carries the long arm of the tilted board.
    rod_end = tilt @ Vector((1.6, (SIGN_FRONT_Y + SIGN_BACK_Y) / 2, SIGN_TOP))
    b.log_column((0.06, rod_end.y, 2.5), rod_end, 0.022, 0.02, rust, sides=6, rough=0.0)
    for angle, distance, size in ((0.3, 0.26, (0.18, 0.14, 0.12)), (1.9, 0.27, (0.16, 0.18, 0.11)),
                                  (3.4, 0.25, (0.2, 0.16, 0.13)), (4.9, 0.26, (0.14, 0.13, 0.1))):
        b.rock((distance * math.cos(angle), distance * math.sin(angle), size[2] * 0.35 + 0.1), size)
    turn = Matrix.Rotation(math.radians(SIGN_TURN), 4, "Z")
    transform_faces(b, 0, turn)
    b.to_board = (turn @ tilt).inverted()
    return b.finish([wood, "MenuMoreyaSignpostBoard", rust, iron, "MenuRoughStone"])


def convert(repo, private, name):
    """Converts <private>/<name>.mesh.xml with OgreXMLConverter into <repo>/models/<name>.mesh."""
    root = Path(os.environ.get("BUILD_DEPS_ROOT", str(Path.home() / "build-deps")))
    converter = root / "install" / "bin" / "OgreXMLConverter.exe"
    target = Path(repo) / "models" / (name + ".mesh")
    result = subprocess.run([str(converter), "-q", str(Path(private) / (name + ".mesh.xml")), str(target)],
                            capture_output=True, text=True)
    if result.returncode != 0 or not target.exists():
        raise RuntimeError("OgreXMLConverter failed for %s: %s %s" % (name, result.stdout, result.stderr))
    log("converted %s (%d bytes)" % (target.name, target.stat().st_size))


def export(exporter, repo, private, obj):
    """Saves the editable source of one model privately and writes and converts its Ogre mesh."""
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(private) / (obj.name + ".blend")))
    stats = exporter.export_mesh_xml(obj, None, str(Path(private) / (obj.name + ".mesh.xml")), None, smooth=False)
    log("%s %s" % (obj.name, stats))
    convert(repo, private, obj.name)


def scene_definitions(repo):
    """Returns the words of every command line of config/mainmenuscene.cfg."""
    text = (Path(repo) / "config/mainmenuscene.cfg").read_text(encoding="utf-8")
    return [line.split() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def menu_material_text(repo):
    """Returns the text of every menu material script (MenuScene with the stone, MenuSignpost with the wood and boards)."""
    folder = Path(repo) / "materials/scripts"
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(folder.glob("Menu*.material")))


def import_scene(repo, private, raid, exporter, with_entrance, open_floor):
    """Imports every AddEntity mesh of the menu scene at its position and gives each material its preview nodes.

    with_entrance False leaves the staircase and the Moreya signpost out (the scene before this change);
    open_floor True removes the floor faces over the stairwell opening from the hall and the outer ground.
    """
    root = Path(os.environ.get("BUILD_DEPS_ROOT", str(Path.home() / "build-deps")))
    converter = root / "install" / "bin" / "OgreXMLConverter.exe"
    xml_folder = Path(private) / "scene-xml"
    xml_folder.mkdir(parents=True, exist_ok=True)
    collection = bpy.data.collections.new("Menu scene")
    bpy.context.scene.collection.children.link(collection)
    entrance = {"MenuMoreyaStairs.mesh", "MenuMoreyaSignpost.mesh"}
    for words in scene_definitions(repo):
        if words[0] != "AddEntity" or (not with_entrance and words[2] in entrance):
            continue
        xml = xml_folder / (words[2] + ".xml")
        if not xml.exists() or xml.stat().st_mtime < (Path(repo) / "models" / words[2]).stat().st_mtime:
            subprocess.run([str(converter), "-q", str(Path(repo) / "models" / words[2]), str(xml)], check=True,
                           capture_output=True)
        obj = exporter.import_mesh(str(xml), None, words[1], collection=collection)
        obj.location = [float(value) for value in words[3:6]]
        if open_floor and words[1] in ("CampaignHall", "OuterGround"):
            cut_opening(obj)
    text = menu_material_text(repo)
    images = {}
    for material in bpy.data.materials:
        if material.users:
            try:
                values = raid.material_values(text, material.name.split(".")[0])
            except ValueError:
                values = {"diffuse": (0.3, 0.3, 0.3)}
            raid.configure_preview_material(material, values, repo, images)


def cut_opening(obj):
    """Deletes the faces of a ground mesh that lie over the stairwell opening (x -3..3, y 24.2..29.2, z -1..0.3)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    origin = obj.location
    doomed = []
    for face in bm.faces:
        centre = face.calc_center_median() + origin
        if -HALF < centre.x < HALF and 24.2 < centre.y < 24.2 + OPEN_LENGTH and -1.0 < centre.z < 0.3:
            doomed.append(face)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    log("opened %d faces of %s" % (len(doomed), obj.name))


def render_poses(repo, private, raid, exporter):
    """Renders the menu scene from the campaign pose and the campaign flight waypoints, before and after.

    Writes <private>/renders/<state>_<pose>_<width>x<height>.png for the states "before" (scene without the
    entrance), "after_closed" (entrance with today's floor) and "after_open" (entrance with the floor opened over
    the stairwell). Lights come from the AddPointLight lines, the ambient from [MenuLighting] FlightAmbient, the
    camera from the [MenuCamera] poses with the vertical field of view of 45 degrees of the game camera.
    """
    sys.path.insert(0, str(Path(repo) / "tools/blender-assets"))
    import menu_scene_assembly as assembly
    definitions = scene_definitions(repo)
    text = (Path(repo) / "config/mainmenuscene.cfg").read_text(encoding="utf-8")
    poses = {}
    ambient = (0.15, 0.18, 0.22)
    for line in text.splitlines():
        words = line.split()
        if len(words) == 8 and words[0] == "Pose":
            poses[words[1]] = [float(value) for value in words[2:]]
        if len(words) == 4 and words[0] == "FlightAmbient":
            ambient = tuple(float(value) for value in words[1:])
    output = Path(private) / "renders"
    output.mkdir(parents=True, exist_ok=True)
    for state, with_entrance, open_floor in (("before", False, False), ("after_closed", True, False),
                                             ("after_open", True, True)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.image_settings.file_format = "PNG"
        scene.view_settings.view_transform = "Standard"
        scene.eevee.taa_render_samples = 32
        world = bpy.data.worlds.new("Menu ambient")
        world.use_nodes = True
        world.node_tree.nodes["Background"].inputs["Color"].default_value = (*ambient, 1)
        world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
        scene.world = world
        import_scene(repo, private, raid, exporter, with_entrance, open_floor)
        lights = bpy.data.collections.new("Lights")
        scene.collection.children.link(lights)
        for words in definitions:
            if words[0] == "AddPointLight":
                assembly.add_light(words, lights)
        camera_data = bpy.data.cameras.new("Menu camera")
        camera_data.sensor_fit = "VERTICAL"
        camera_data.sensor_height = 24
        camera_data.lens = camera_data.sensor_height / (2 * math.tan(math.radians(45) / 2))
        camera_data.clip_start = 0.05
        camera_data.clip_end = 400
        camera = bpy.data.objects.new("Menu camera", camera_data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        camera.rotation_mode = "QUATERNION"
        for pose, sizes in (("campaign", ((1920, 1080), (1440, 1080))), ("gate_entry", ((1920, 1080),)),
                            ("gate_exit", ((1920, 1080),))):
            values = poses[pose]
            camera.location = values[:3]
            camera.rotation_quaternion = (Quaternion((1, 0, 0), math.radians(values[3]))
                                          @ Quaternion((0, 1, 0), math.radians(values[4]))
                                          @ Quaternion((0, 0, 1), math.radians(values[5])))
            for width, height in sizes:
                scene.render.resolution_x, scene.render.resolution_y = width, height
                scene.render.filepath = str(output / ("%s_%s_%dx%d.png" % (state, pose, width, height)))
                bpy.ops.render.render(write_still=True)
                log("rendered " + scene.render.filepath)


def main():
    """Runs the requested builds and renders (stairs and signpost when none is named) and logs the result."""
    global LOG
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    wanted = set(arguments[2:]) or {"stairs", "signpost"}
    private.mkdir(parents=True, exist_ok=True)
    LOG = open(private / "menu_moreya_entrance.log", "w", encoding="utf-8")
    try:
        sys.path.insert(0, str(repo / "tools/blender-assets"))
        import moreya_raid_models as raid
        import odp_ogre_io as exporter
        bpy.context.preferences.filepaths.save_version = 0
        if "stairs" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_stairs(raid))
        if "signpost" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_signpost(raid))
        if "render" in wanted:
            render_poses(repo, private, raid, exporter)
        log("finished")
    except Exception:
        LOG.write(traceback.format_exc())
        log("failed")
    finally:
        LOG.close()


if __name__ == "__main__":
    main()
