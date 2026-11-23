"""Build the entrance into Moreya for the start screen: the forecourt behind the campaign table and its green portal.

    MenuMoreyaForecourt a large open forecourt behind the campaign hall (FORECOURT, 24 wide and 30 deep), old,
                        abandoned and overgrown: broken wet flagstones (gone, sunken, tilted, moss in their place),
                        high coursed walls with pilasters whose coping and merlons are partly gone and which have
                        fallen in two places, ivy climbing them and vines hanging down, moss cushions, rubble heaps, a
                        fallen column with its stump and dead trees grown out of the paving; a clear path leads from
                        the hall to the portal; short walls join the hall; the abandoned castle and the rear buildings
                        of the fortress stand behind its rear wall
    MenuHallForecourtArch the stone frame (jambs, lintel, threshold) of the wide opening in the back wall of the
                        campaign scene's hall copy (MenuCampaignHallOpen.mesh) through which one walks from the table
                        into the forecourt
    MenuMoreyaPortal    the other side of the green start gate of the campaign map, at the far end of the forecourt
                        in front of its rear wall: a round arch of grey stone blocks on two coursed pillars with carved
                        capitals, its opening filled with green fire (material MenuMoreyaPortalFire, texture by
                        tools/gen_menu_portal_fire.py), damp moss on the stones and hanging from the arch, two iron fire
                        bowls on stone pedestals in front of the pillars, all on a low stone platform with a front step,
                        built at PORTAL_SCALE; the flames over the bowls and the rising green flames in the arch are
                        particle systems (particles/MenuScene.particle)
    MenuMoreyaSignpost  a smaller signpost of the start screen signpost family (moreya_raid_models.py PartBuilder,
                        same wood, iron and board planks); its upright arrow board carries the word "Moreya"
    MenuForgeCoals      a heap of charred coal lumps with small embers glowing between them on the forge hearth of
                        the rear buildings (MenuFortressRear.mesh), in place of its former flat glowing slab

Units are menu scene units. The forecourt and the frame are built in scene coordinates (the scene places them at the
origin). The portal's origin is the middle of its foot in the plane of the fire; the fire faces -Y, back along the
forecourt towards the hall, the table and the camera of the campaign flight, which sees it through the opening in
the hall's back wall. The signpost's origin is the foot of its post; the scene places it in the forecourt near the
hall, its board upright and facing the hall, its tip pointing along the forecourt towards the portal. MenuForgeCoals
is built in the coordinates of MenuFortressRear.mesh; the scene places both at the same position.

Run in Blender (5.x):
    blender --background --python menu_moreya_entrance.py -- <repo> <private output folder> [forecourt] [arch]
        [portal] [signpost] [coals] [render]
"forecourt", "arch", "portal", "signpost" and "coals" write <name>.blend and <name>.mesh.xml into the private folder
and convert the meshes with OgreXMLConverter into <repo>/models. "render" renders the menu scene of
config/mainmenuscene.cfg from the campaign pose and the waypoints of the campaign flight into <private>/renders (see
render_poses). The board lettering is written by tools/gen_menu_signpost_lettering.py (--text Moreya). Progress goes
to <private>/menu_moreya_entrance.log.
The shipped forecourt, arch and portal meshes use the dark ruin materials MenuRuin* instead of the shared stone named
here: after converting them, run tools/menu_rename_mesh_materials.py as its docstring lists.
"""
import math
import os
import subprocess
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

#: The campaign hall: inner face of its back wall (scene y) and outer half width of its walls.
HALL_BACK_WALL = 29.25
HALL_HALF_OUTER = 6.84
#: The wide opening in the back wall of the campaign hall (scene coordinates): half width, sill and top height, and
#: the wall's inner and outer face (y). tools/menu_cut_moreya_opening.py cuts the same box out of the hall copy of the
#: campaign scene (MenuCampaignHallOpen.mesh).
ARCH_HALF, ARCH_SILL, ARCH_HEIGHT = 5.0, 0.12, 6.6
ARCH_WALL = (29.25, 30.25)
#: The forecourt inside its walls (x min, x max, y min, y max: from the hall's back wall to the rear wall), the
#: thickness of its walls, the height of the side walls and of the rear wall, and the top of the flagstones.
FORECOURT = (-12.0, 12.0, 30.25, 60.25)
FORECOURT_WALL, FORECOURT_WALL_HEIGHT, FORECOURT_REAR_HEIGHT = 1.2, 7.0, 11.0
PAVING_TOP = 0.08
#: The forecourt is an old abandoned ruin: share of decayed flagstones, the half width of the clear path from the
#: hall to the portal (nothing tall stands on it) and the fallen parts of the side walls (start y, end y, lowest top).
FORECOURT_DECAY, PATH_HALF = 0.3, 3.5
LEFT_BREACHES = ((39.0, 45.0, 3.2),)
RIGHT_BREACHES = ((50.5, 54.5, 4.2),)
#: The paved rear yard behind the forecourt's rear wall (x min, x max, y min, y max) and the top of its flagstones.
REAR_YARD, REAR_YARD_TOP = (-15.0, 15.0, 61.45, 77.0), 0.02
#: The portal as designed before it is scaled by PORTAL_SCALE: inner half width of the opening, spring height of the
#: arch (top of the capitals), width of the pillars and of the arch ring, half depth of the pillars, number of arch
#: blocks and the plane of the fire (y).
PORTAL_INNER, PORTAL_SPRING, PILLAR_WIDTH, PILLAR_DEPTH = 1.6, 3.6, 0.85, 0.5
ARCH_BLOCKS, FIRE_Y = 13, 0.0
FIRE_MATERIAL = "MenuMoreyaPortalFire"
PORTAL_SCALE = 1.5
#: The platform under the portal (x min, x max, y min, y max) and its top height.
PLINTH, PLINTH_TOP = (-3.3, 3.3, -2.2, 0.62), 0.22
#: The fire bowls: distance of their centres from the middle, their y and the height of their rims.
BOWL_X, BOWL_Y, BOWL_TOP, BOWL_RIM = 2.3, -1.5, 1.3, 0.45
#: The coal bed on the forge hearth of the rear buildings (x min, x max, y min, y max in the coordinates of
#: MenuFortressRear.mesh) and the hearth top height.
FORGE_BED = (3.05, 4.95, 40.95, 42.05)
FORGE_HEARTH = 0.85
#: Signpost: board outline in its own frame (back end, shoulder, tip, lower and upper edge), thickness planes,
#: the tilt of the board (0: upright), the turn of the whole signpost about Z (tip towards +X and +Y, from the left
#: side of the forecourt along it towards the portal; board front towards the hall and the campaign flight) and its
#: size factor.
SIGN_BACK, SIGN_SHOULDER, SIGN_TIP = -0.30, 1.80, 2.10
SIGN_BOTTOM, SIGN_TOP = 1.75, 2.35
SIGN_FRONT_Y, SIGN_BACK_Y = -0.22, -0.135
SIGN_PIVOT_Z = 2.05
SIGN_TILT, SIGN_TURN, SIGN_SCALE = 0.0, 45.0, 1.6

LOG = None


def log(text):
    """Writes one progress line to the log file of the run."""
    LOG.write(text + "\n")
    LOG.flush()


def box(b, x0, x1, y0, y1, z0, z1, material, grain=(1, 0, 0)):
    """Adds an axis-aligned box between two corners."""
    b.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, z1 - z0), material, grain)


def add_plinth(b):
    """Adds the stone platform the portal and its fire bowls stand on: worn slabs on a dark bed and a front step."""
    x0, x1, y0, y1 = PLINTH
    box(b, x0 + 0.03, x1 - 0.03, y0 + 0.03, y1 - 0.03, -0.12, PLINTH_TOP - 0.04, "MenuSoot")
    x = x0
    while x < x1 - 0.05:
        right = min(x + b.rng.uniform(0.9, 1.5), x1)
        if x1 - right < 0.5:
            right = x1
        y = y0
        while y < y1 - 0.05:
            far = min(y + b.rng.uniform(0.7, 1.1), y1)
            if y1 - far < 0.4:
                far = y1
            box(b, x + 0.015, right - 0.015, y + 0.015, far - 0.015, -0.1,
                PLINTH_TOP + b.rng.uniform(-0.025, 0.01), "MenuChippedStone")
            y = far
        x = right
    x = x0 + 0.3
    while x < x1 - 0.35:
        right = min(x + b.rng.uniform(1.0, 1.6), x1 - 0.3)
        if x1 - 0.3 - right < 0.5:
            right = x1 - 0.3
        box(b, x + 0.015, right - 0.015, y0 - 0.45, y0 + 0.02, -0.1, PLINTH_TOP / 2 + b.rng.uniform(-0.02, 0.01),
            "MenuChippedStone")
        x = right


def add_pillars(b):
    """Adds the two pillars of coursed blocks with a wider base block and a carved capital under the arch."""
    for side in (-1, 1):
        inner, outer = sorted((side * PORTAL_INNER, side * (PORTAL_INNER + PILLAR_WIDTH)))
        box(b, inner - 0.1, outer + 0.1, -PILLAR_DEPTH - 0.12, PILLAR_DEPTH + 0.12, PLINTH_TOP - 0.02,
            PLINTH_TOP + 0.55, "MenuCarvedStone", (0, 0, 1))
        bottom = PLINTH_TOP + 0.565
        capital = PORTAL_SPRING - 0.38
        while bottom < capital - 0.05:
            top = min(bottom + b.rng.uniform(0.48, 0.62), capital)
            if capital - top < 0.3:
                top = capital
            jitter = (b.rng.uniform(-0.03, 0.02), b.rng.uniform(-0.02, 0.03))
            box(b, inner + jitter[0], outer + jitter[1], -PILLAR_DEPTH + b.rng.uniform(-0.03, 0.02),
                PILLAR_DEPTH, bottom, top - 0.015, "MenuChippedStone", (0, 0, 1))
            bottom = top
        box(b, inner - 0.14, outer + 0.14, -PILLAR_DEPTH - 0.14, PILLAR_DEPTH + 0.1, capital, capital + 0.14,
            "MenuCarvedStone")
        box(b, inner - 0.06, outer + 0.06, -PILLAR_DEPTH - 0.06, PILLAR_DEPTH + 0.05, capital + 0.14,
            PORTAL_SPRING, "MenuCarvedStone")


def arch_point(radius, angle):
    """Returns the (x, z) of a point on a circle about the arch centre (angle 0 right, pi left)."""
    return radius * math.cos(angle), PORTAL_SPRING + radius * math.sin(angle)


def add_arch(b):
    """Adds the round arch of wedge-shaped blocks over the pillars, with a larger keystone at the crown."""
    inner, outer = PORTAL_INNER, PORTAL_INNER + PILLAR_WIDTH
    gap = 0.012
    for index in range(ARCH_BLOCKS):
        a0 = math.pi * index / ARCH_BLOCKS + gap
        a1 = math.pi * (index + 1) / ARCH_BLOCKS - gap
        key = index == ARCH_BLOCKS // 2
        reach = outer + (0.22 if key else b.rng.uniform(-0.04, 0.05))
        front = -PILLAR_DEPTH - (0.1 if key else b.rng.uniform(-0.02, 0.03))
        corners = [arch_point(inner, a0), arch_point(inner, a1), arch_point(reach, a1), arch_point(reach, a0)]
        b.solid([(x, front, z) for x, z in corners], (0, PILLAR_DEPTH - front, 0), "MenuChippedStone",
                (math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2)))


def add_fire(b):
    """Adds the green fire face that fills the opening under the arch, facing the hall (-Y)."""
    y, bottom = FIRE_Y, PLINTH_TOP - 0.01
    columns = 6
    for index in range(columns):
        x0 = -PORTAL_INNER + 2 * PORTAL_INNER * index / columns
        x1 = -PORTAL_INNER + 2 * PORTAL_INNER * (index + 1) / columns
        b.face([(x0, y, bottom), (x1, y, bottom), (x1, y, PORTAL_SPRING), (x0, y, PORTAL_SPRING)], FIRE_MATERIAL)
    sides = 16
    for index in range(sides):
        a0, a1 = math.pi * index / sides, math.pi * (index + 1) / sides
        x0, z0 = arch_point(PORTAL_INNER, a0)
        x1, z1 = arch_point(PORTAL_INNER, a1)
        b.face([(0.0, y, PORTAL_SPRING), (x0, y, z0), (x1, y, z1)], FIRE_MATERIAL)


def add_moss(b):
    """Adds damp moss on the capitals, the base blocks and the arch, and strands hanging from the arch."""
    for side in (-1, 1):
        middle = side * (PORTAL_INNER + PILLAR_WIDTH / 2)
        for dx in (-0.3, 0.05, 0.32):
            b.rock((middle + dx, -PILLAR_DEPTH + 0.05, PORTAL_SPRING - 0.22), (0.2, 0.16, 0.05), "MenuMoss")
        for dx in (-0.35, 0.3):
            b.rock((middle + dx, -PILLAR_DEPTH - 0.05, PLINTH_TOP + 0.56), (0.22, 0.14, 0.05), "MenuMoss")
    outer = PORTAL_INNER + PILLAR_WIDTH
    for angle in (0.35, 0.8, 1.25, 1.9, 2.35, 2.8):
        x, z = arch_point(outer + 0.02, angle)
        b.rock((x, -PILLAR_DEPTH + 0.15, z), (0.24, 0.2, 0.07), "MenuMoss")
        for strand in range(b.rng.randint(1, 3)):
            sx, sz = arch_point(b.rng.uniform(PORTAL_INNER + 0.15, outer - 0.1), angle + b.rng.uniform(-0.12, 0.12))
            length = b.rng.uniform(0.35, 1.0)
            b.log_column((sx, -PILLAR_DEPTH - 0.01, sz), (sx + b.rng.uniform(-0.06, 0.06), -PILLAR_DEPTH - 0.05,
                         sz - length), 0.035, 0.012, "MenuMoss", sides=5, rough=0.008)


def fire_bowl(b, centre):
    """Adds one wide iron fire bowl at a centre point (the rim height) filled with glowing coals."""
    sides = 14
    rim, foot, depth = BOWL_RIM, 0.2, 0.3
    upper = [centre + Vector((rim * math.cos(i * 2 * math.pi / sides), rim * math.sin(i * 2 * math.pi / sides), 0.0))
             for i in range(sides)]
    lower = [centre + Vector((foot * math.cos(i * 2 * math.pi / sides), foot * math.sin(i * 2 * math.pi / sides),
                              -depth)) for i in range(sides)]
    b.face(list(reversed(lower)), "MenuCorrodedIron", (0, 0, 1))
    for index in range(sides):
        following = (index + 1) % sides
        b.face((lower[index], lower[following], upper[following], upper[index]), "MenuCorrodedIron", (0, 0, 1))
        b.face((upper[index], upper[following], lower[following], lower[index]), "MenuCorrodedIron", (0, 0, 1))
    coals = [centre + Vector((0.75 * (point - centre).x, 0.75 * (point - centre).y, -0.09)) for point in upper]
    top = centre + Vector((0.0, 0.0, -0.04))
    for index in range(sides):
        b.face((coals[index], coals[(index + 1) % sides], top), "MenuEmber", (1, 0, 0))
    for angle in (0.3, 1.4, 2.5, 3.6, 4.7, 5.6):
        lump = centre + Vector((0.2 * math.cos(angle), 0.2 * math.sin(angle), -0.04))
        b.rock(lump, (0.1, 0.09, 0.06), "MenuSoot")


def add_fire_bowls(b):
    """Adds the two fire bowls on short stone pedestals in front of the pillars."""
    for x in (-BOWL_X, BOWL_X):
        b.log_column((x, BOWL_Y, PLINTH_TOP - 0.02), (x, BOWL_Y, BOWL_TOP - 0.36), 0.3, 0.22, "MenuCarvedStone",
                     sides=8, rough=0.01)
        box(b, x - 0.3, x + 0.3, BOWL_Y - 0.3, BOWL_Y + 0.3, BOWL_TOP - 0.4, BOWL_TOP - 0.3, "MenuCarvedStone")
        fire_bowl(b, Vector((x, BOWL_Y, BOWL_TOP)))


def build_portal(raid):
    """Builds the portal into Moreya: platform, pillars, round arch, green fire face, moss and two fire bowls.

    Every part is designed at the unscaled sizes above and the whole portal is then scaled by PORTAL_SCALE about its
    origin.
    """
    b = raid.PartBuilder("MenuMoreyaPortal", 5821)
    add_plinth(b)
    add_pillars(b)
    add_arch(b)
    add_fire(b)
    add_moss(b)
    add_fire_bowls(b)
    transform_faces(b, 0, Matrix.Scale(PORTAL_SCALE, 4))
    obj = b.finish(["MenuChippedStone", "MenuCarvedStone", "MenuSoot", "MenuMoss", "MenuCorrodedIron", "MenuEmber",
                    FIRE_MATERIAL])
    # The fire face shows its texture once across the opening: u from left to right, v from the crown down in the game
    # (the exporter writes 1 - v, so the Blender v rises from the foot to the crown).
    fire_index = obj.data.materials.find(FIRE_MATERIAL)
    uv = obj.data.uv_layers.active
    crown = (PORTAL_SPRING + PORTAL_INNER) * PORTAL_SCALE
    inner, bottom = PORTAL_INNER * PORTAL_SCALE, PLINTH_TOP * PORTAL_SCALE
    for polygon in obj.data.polygons:
        if polygon.material_index != fire_index:
            continue
        for loop_index in polygon.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = ((point.x + inner) / (2 * inner), (point.z - bottom) / (crown - bottom))
    return obj


def build_hall_arch(raid):
    """Builds the stone frame of the wide opening in the back wall of the campaign hall that leads into the forecourt.

    Scene coordinates (the scene places it at the origin): tools/menu_cut_moreya_opening.py cuts the wall over
    x -ARCH_HALF..ARCH_HALF, z ARCH_SILL..ARCH_HEIGHT out of MenuCampaignHallOpen.mesh; the jambs, the lintel and the
    threshold of this frame cover the cut edges and stand on the floor.
    """
    b = raid.PartBuilder("MenuHallForecourtArch", 3307)
    front, back = ARCH_WALL[0] - 0.12, ARCH_WALL[1] + 0.12
    for side in (-1, 1):
        inner, outer = sorted((side * (ARCH_HALF - 0.15), side * (ARCH_HALF + 0.38)))
        bottom = -0.05
        for top in (1.4, 2.9, 4.4, ARCH_HEIGHT + 0.08):
            lift = b.rng.uniform(-0.02, 0.02)
            box(b, inner + b.rng.uniform(-0.02, 0.01), outer, front + b.rng.uniform(-0.03, 0.0), back, bottom,
                top + lift, "MenuCarvedStone", (0, 0, 1))
            bottom = top + lift + 0.015
    box(b, -ARCH_HALF - 0.5, ARCH_HALF + 0.5, front - 0.04, back + 0.04, ARCH_HEIGHT - 0.05, ARCH_HEIGHT + 0.7,
        "MenuCarvedStone")
    box(b, -ARCH_HALF - 0.15, ARCH_HALF + 0.15, front, back, -0.12, ARCH_SILL + 0.04, "MenuChippedStone")
    return b.finish(["MenuCarvedStone", "MenuChippedStone"])


def add_forecourt_paving(b, area, top, decay=0.0):
    """Paves an area (x min, x max, y min, y max) with worn wet flagstones of uneven size on a dark bed.

    decay is the share of flagstones that are gone (moss or bare bed in their place) or sunken and tilted; the
    flagstones of the clear path (|x| < PATH_HALF) are only sunken or tilted, never gone.
    """
    x0, x1, y0, y1 = area
    box(b, x0, x1, y0, y1, top - 0.38, top - 0.12, "MenuSoot")
    y = y0
    while y < y1 - 0.05:
        far = min(y + b.rng.uniform(1.3, 2.2), y1)
        if y1 - far < 0.8:
            far = y1
        x = x0 + b.rng.uniform(-0.6, 0.0)
        while x < x1 - 0.05:
            right = min(x + b.rng.uniform(1.3, 2.4), x1)
            if x1 - right < 0.8:
                right = x1
            left = max(x, x0)
            chance = b.rng.random()
            on_path = abs((left + right) / 2) < PATH_HALF
            if chance < decay * 0.45 and not on_path:
                # A flagstone is gone: its bed shows, often grown over with moss.
                if b.rng.random() < 0.7:
                    moss_patch(b, ((left + right) / 2, (y + far) / 2), ((right - left) * 0.45, (far - y) * 0.45),
                               top - 0.12, 0.06)
            else:
                first = len(b.faces)
                box(b, left + 0.02, right - 0.02, y + 0.02, far - 0.02, top - 0.33,
                    top + b.rng.uniform(-0.03, 0.015), "MenuWetStone")
                if chance < decay:
                    # A sunken, tilted flagstone.
                    centre = Vector(((left + right) / 2, (y + far) / 2, top))
                    tilt = (Matrix.Translation(centre) @ Matrix.Rotation(b.rng.uniform(-0.06, 0.06), 4, "X")
                            @ Matrix.Rotation(b.rng.uniform(-0.06, 0.06), 4, "Y")
                            @ Matrix.Translation(-centre + Vector((0.0, 0.0, -b.rng.uniform(0.02, 0.07)))))
                    transform_faces(b, first, tilt)
            x = right
        y = far


def moss_patch(b, centre, radius, z, thickness):
    """Adds a flat, irregular cushion of moss (centre and radii in x and y) lying on a surface at height z."""
    points = []
    for index in range(9):
        angle = index * 2 * math.pi / 9
        scale = b.rng.uniform(0.75, 1.0)
        points.append((centre[0] + radius[0] * scale * math.cos(angle), centre[1] + radius[1] * scale * math.sin(angle),
                       z - 0.02))
    b.solid(points, (0, 0, thickness + 0.02), "MenuMoss", (1, 0, 0))


def add_wall(b, x0, x1, y0, y1, top, breaches=()):
    """Adds a coursed stone wall over a rectangle (along its longer side) with a dark core, coping and merlons.

    The wall is old: some merlons and pieces of the coping are gone. breaches lists (start, end, low) ranges along
    the wall where it has partly fallen: there the courses end at a ragged line that sinks to the height low.
    """
    along_x = x1 - x0 >= y1 - y0
    start, end = (x0, x1) if along_x else (y0, y1)

    def ruined_top(position):
        """Returns the height the wall still reaches at a position along it."""
        height = top
        for first, last, low in breaches:
            if first <= position <= last:
                middle, half = (first + last) / 2, (last - first) / 2
                height = min(height, low + (top - low) * (abs(position - middle) / half) ** 2)
        return height

    # The dark core follows the ruined top in short pieces.
    position = start
    while position < end - 0.01:
        following = min(position + 0.5, end)
        height = min(ruined_top(position), ruined_top(following)) - 0.05
        if along_x:
            box(b, position + 0.01, following - 0.01, y0 + 0.06, y1 - 0.06, -0.2, height, "MenuSoot")
        else:
            box(b, x0 + 0.06, x1 - 0.06, position + 0.01, following - 0.01, -0.2, height, "MenuSoot")
        position = following
    bottom, row = -0.15, 0
    while bottom < top - 0.4:
        height = min(b.rng.uniform(0.6, 0.78), top - 0.4 - bottom)
        position = start - (0.5 if row % 2 else 0.0)
        while position < end - 0.05:
            length = b.rng.uniform(1.0, 1.9)
            following = min(position + length, end)
            if end - following < 0.5:
                following = end
            low, high = max(position, start) + 0.012, following - 0.012
            if bottom + height > min(ruined_top(low), ruined_top(high)) - b.rng.uniform(0.0, 0.3):
                position = following
                continue
            out = b.rng.uniform(-0.03, 0.03)
            material = "MenuChippedStone" if b.rng.random() < 0.3 else "MenuStone"
            if along_x:
                box(b, low, high, y0 - out, y1 + out, bottom, bottom + height - 0.015, material, (1, 0, 0))
            else:
                box(b, x0 - out, x1 + out, low, high, bottom, bottom + height - 0.015, material, (0, 1, 0))
            position = following
        bottom += height
        row += 1
    # The coping in pieces, some of them gone, and the merlons on it, many of them gone.
    position = start
    while position < end - 0.05:
        following = min(position + b.rng.uniform(1.5, 3.0), end)
        if b.rng.random() > 0.18 and ruined_top(position) >= top and ruined_top(following) >= top:
            if along_x:
                box(b, position, following, y0 - 0.1, y1 + 0.1, top - 0.4, top, "MenuCarvedStone")
            else:
                box(b, x0 - 0.1, x1 + 0.1, position, following, top - 0.4, top, "MenuCarvedStone")
            merlon = position + 0.2
            while merlon < following - 0.9:
                if b.rng.random() > 0.35:
                    lean = b.rng.uniform(0.45, 0.75)
                    if along_x:
                        box(b, merlon, merlon + 0.8, y0, y1, top - 0.02, top + lean, "MenuStone")
                    else:
                        box(b, x0, x1, merlon, merlon + 0.8, top - 0.02, top + lean, "MenuStone")
                merlon += 1.6
        position = following


def ivy(b, base, normal, height):
    """Adds a strand of ivy that climbs a wall face from base (on the floor) up to a height, with leaf clumps.

    normal points out of the wall face into the forecourt; the strand winds sideways along the face as it climbs.
    """
    normal = Vector(normal)
    side = Vector((-normal.y, normal.x, 0.0))
    point = Vector(base) + normal * 0.06
    while point.z < height:
        following = point + side * b.rng.uniform(-0.35, 0.35) + Vector((0.0, 0.0, b.rng.uniform(0.35, 0.6)))
        b.log_column(point, following, 0.045, 0.04, "MenuMoss", sides=5, rough=0.008)
        for _ in range(2):
            leaf = following + side * b.rng.uniform(-0.25, 0.25) + Vector((0.0, 0.0, b.rng.uniform(-0.25, 0.05)))
            b.rock(leaf + normal * 0.05, (0.16 + 0.1 * abs(normal.y), 0.16 + 0.1 * abs(normal.x), 0.14), "MenuMoss")
        point = following


def add_overgrowth(b):
    """Grows the forecourt over: moss cushions along the walls, ivy climbing them, vines hanging from the coping."""
    x0, x1, y0, y1 = FORECOURT
    for side in (-1, 1):
        face = side * x1
        normal = (-side, 0.0, 0.0)
        y = y0 + 0.8
        while y < y1 - 0.5:
            moss_patch(b, (face - side * b.rng.uniform(0.7, 1.5), y + b.rng.uniform(-0.5, 0.5)),
                       (b.rng.uniform(0.6, 1.3), b.rng.uniform(0.8, 1.8)), PAVING_TOP, 0.05)
            if b.rng.random() < 0.75:
                ivy(b, (face, y + b.rng.uniform(-0.8, 0.8), PAVING_TOP), normal,
                    b.rng.uniform(1.8, FORECOURT_WALL_HEIGHT - 0.6))
            if b.rng.random() < 0.55:
                hang = Vector((face - side * 0.12, y + b.rng.uniform(-1.0, 1.0), FORECOURT_WALL_HEIGHT - 0.42))
                b.log_column(hang, hang + Vector((-side * 0.05, 0.0, -b.rng.uniform(1.0, 3.2))), 0.04, 0.015,
                             "MenuMoss", sides=5, rough=0.008)
            y += b.rng.uniform(1.6, 2.8)
    x = x0 + 0.8
    while x < x1 - 0.5:
        if abs(x) > PORTAL_SCALE * (PORTAL_INNER + PILLAR_WIDTH) + 1.5:
            moss_patch(b, (x, y1 - b.rng.uniform(0.6, 1.3)), (b.rng.uniform(0.8, 1.6), b.rng.uniform(0.5, 1.0)),
                       PAVING_TOP, 0.05)
            if b.rng.random() < 0.8:
                ivy(b, (x, y1, PAVING_TOP), (0.0, -1.0, 0.0), b.rng.uniform(2.5, FORECOURT_REAR_HEIGHT - 1.5))
        x += b.rng.uniform(1.5, 2.6)
    # Moss and weeds in the joints all over the floor, low enough to walk over.
    for _ in range(140):
        centre = (b.rng.uniform(x0 + 0.5, x1 - 0.5), b.rng.uniform(y0 + 0.5, y1 - 4.5))
        moss_patch(b, centre, (b.rng.uniform(0.2, 0.7), b.rng.uniform(0.2, 0.7)), PAVING_TOP, 0.04)


def rubble_heap(b, centre, radius, count):
    """Adds a heap of fallen wall blocks and broken stones around a centre on the forecourt floor."""
    for _ in range(count):
        angle, distance = b.rng.uniform(0, 2 * math.pi), radius * math.sqrt(b.rng.random())
        x, y = centre[0] + distance * math.cos(angle), centre[1] + distance * math.sin(angle)
        height = 0.2 + 0.9 * (1.0 - distance / radius) * b.rng.random()
        if b.rng.random() < 0.45:
            size = (b.rng.uniform(0.5, 1.2), b.rng.uniform(0.4, 0.8), b.rng.uniform(0.35, 0.6))
            first = len(b.faces)
            box(b, x - size[0] / 2, x + size[0] / 2, y - size[1] / 2, y + size[1] / 2, PAVING_TOP - 0.1,
                PAVING_TOP - 0.1 + size[2], "MenuChippedStone")
            pivot = Vector((x, y, PAVING_TOP))
            transform_faces(b, first, Matrix.Translation(pivot) @ Matrix.Rotation(b.rng.uniform(0, 2 * math.pi), 4, "Z")
                            @ Matrix.Rotation(b.rng.uniform(-0.3, 0.3), 4, "X") @ Matrix.Translation(-pivot))
        else:
            size = (b.rng.uniform(0.2, 0.5), b.rng.uniform(0.2, 0.45), b.rng.uniform(0.15, 0.35))
            b.rock((x, y, PAVING_TOP + min(height, size[2] * 0.6)), size, "MenuRoughStone")


def dead_tree(b, root, height, lean):
    """Adds a dead gnarled tree that has grown out of the broken paving: roots, trunk and bare branches."""
    root = Vector(root)
    top = root + Vector((lean[0], lean[1], height))
    b.log_column(root + Vector((0, 0, -0.3)), root + (top - root) * 0.55, 0.32, 0.2, "MenuAgedWood", sides=8,
                 rough=0.04)
    middle = root + (top - root) * 0.55
    b.log_column(middle, top, 0.2, 0.06, "MenuAgedWood", sides=7, rough=0.03)
    for index in range(5):
        angle = index * 2 * math.pi / 5 + b.rng.uniform(-0.3, 0.3)
        b.log_column(root + Vector((0, 0, 0.1)), root + Vector((1.1 * math.cos(angle), 1.1 * math.sin(angle), -0.1)),
                     0.14, 0.04, "MenuAgedWood", sides=6, rough=0.02)
    for index in range(6):
        start = root + (top - root) * b.rng.uniform(0.45, 0.95)
        angle = b.rng.uniform(0, 2 * math.pi)
        reach = b.rng.uniform(0.9, 2.0)
        end = start + Vector((reach * math.cos(angle), reach * math.sin(angle), b.rng.uniform(0.4, 1.3)))
        b.log_column(start, end, 0.09, 0.02, "MenuAgedWood", sides=5, rough=0.015)
        twig = end + Vector((b.rng.uniform(-0.5, 0.5), b.rng.uniform(-0.5, 0.5), b.rng.uniform(0.2, 0.6)))
        b.log_column(end, twig, 0.03, 0.008, "MenuAgedWood", sides=4, rough=0.0)


def add_decay(b):
    """Adds the ruin of the forecourt: rubble under the breaches and along the walls, a fallen column with its
    broken stump, and dead trees grown out of the paving."""
    x0, x1, y0, y1 = FORECOURT
    for first, last, low in LEFT_BREACHES:
        rubble_heap(b, (x0 + 1.4, (first + last) / 2), (last - first) / 2 + 0.4, 34)
    for first, last, low in RIGHT_BREACHES:
        rubble_heap(b, (x1 - 1.4, (first + last) / 2), (last - first) / 2 + 0.4, 30)
    for centre in ((x0 + 1.6, 35.5), (x1 - 1.7, 49.5), (x0 + 2.2, 55.5), (x1 - 2.0, 33.0)):
        rubble_heap(b, centre, 1.3, 12)
    # A fallen column lies broken across the right half; its stump still stands.
    b.log_column((8.0, 41.0, PAVING_TOP - 0.05), (8.0, 41.0, 1.4), 0.5, 0.46, "MenuCarvedStone", sides=10, rough=0.03)
    b.log_column((7.4, 42.0, 0.5), (5.0, 45.6, 0.48), 0.46, 0.45, "MenuCarvedStone", sides=10, rough=0.03)
    b.log_column((4.8, 46.1, 0.44), (4.5, 47.4, 0.42), 0.45, 0.44, "MenuCarvedStone", sides=10, rough=0.03)
    rubble_heap(b, (6.4, 43.9), 1.0, 8)
    dead_tree(b, (-7.6, 46.5, PAVING_TOP), 5.2, (-0.4, 0.3))
    dead_tree(b, (8.6, 54.0, PAVING_TOP), 4.0, (0.3, -0.2))
    dead_tree(b, (-9.4, 33.8, PAVING_TOP), 3.4, (0.2, 0.3))


def add_forecourt_walls(b):
    """Adds the walls round the forecourt, partly fallen, the pilasters on their inner faces and stones at their feet."""
    x0, x1, y0, y1 = FORECOURT
    thick = FORECOURT_WALL
    add_wall(b, x0 - thick, x0, y0 - 1.0, y1 + thick, FORECOURT_WALL_HEIGHT, LEFT_BREACHES)
    add_wall(b, x1, x1 + thick, y0 - 1.0, y1 + thick, FORECOURT_WALL_HEIGHT, RIGHT_BREACHES)
    add_wall(b, x0 - thick, x1 + thick, y1, y1 + thick, FORECOURT_REAR_HEIGHT)
    # Short walls close the forecourt between the campaign hall and the side walls.
    for side in (-1, 1):
        inner, outer = sorted((side * HALL_HALF_OUTER, side * x1))
        add_wall(b, inner, outer, y0 - 1.0, y0, FORECOURT_WALL_HEIGHT)
    for side, breaches in ((-1, LEFT_BREACHES), (1, RIGHT_BREACHES)):
        face = side * x1
        y = y0 + 3.0
        while y < y1 - 2.0:
            if not any(first - 0.6 <= y <= last + 0.6 for first, last, low in breaches):
                inner, outer = sorted((face - side * 0.45, face))
                box(b, inner, outer, y - 0.5, y + 0.5, -0.1, FORECOURT_WALL_HEIGHT + 0.3, "MenuCarvedStone", (0, 0, 1))
            y += 6.0
    x = x0 + 2.0
    while x < x1 - 2.0:
        box(b, x - 0.5, x + 0.5, y1 - 0.45, y1, -0.1, FORECOURT_REAR_HEIGHT + 0.3, "MenuCarvedStone", (0, 0, 1))
        x += 4.0


def build_forecourt(raid):
    """Builds the forecourt behind the campaign hall as an old, abandoned and overgrown ruin: broken paving, partly
    fallen walls with pilasters, ivy, moss, rubble, a fallen column and dead trees, and the paving of the rear yard
    behind it."""
    b = raid.PartBuilder("MenuMoreyaForecourt", 7717)
    add_forecourt_paving(b, FORECOURT, PAVING_TOP, FORECOURT_DECAY)
    # The rear yard behind the forecourt keeps its paving: the rubble and the forge of the rear buildings
    # (MenuFortressRear.mesh, moved back with them) lie on it.
    add_forecourt_paving(b, REAR_YARD, REAR_YARD_TOP)
    add_forecourt_walls(b)
    add_overgrowth(b)
    add_decay(b)
    return b.finish(["MenuWetStone", "MenuSoot", "MenuStone", "MenuChippedStone", "MenuCarvedStone", "MenuMoss",
                     "MenuRoughStone", "MenuAgedWood"])


def build_forge_coals(raid):
    """Builds the coal heap on the forge hearth of the rear yard: dark charred lumps with small embers between them.

    Scene coordinates (the scene places it at the origin). The lumps rest on the hearth top (about z 0.86) over
    FORGE_BED (x and y range); tools/menu_cut_moreya_opening.py removes the flat glowing slab that floated there.
    """
    b = raid.PartBuilder("MenuForgeCoals", 4409)
    x0, x1, y0, y1 = FORGE_BED
    rows, columns = 6, 10
    for row in range(rows):
        for column in range(columns):
            x = x0 + (column + 0.5 + b.rng.uniform(-0.25, 0.25)) * (x1 - x0) / columns
            y = y0 + (row + 0.5 + b.rng.uniform(-0.25, 0.25)) * (y1 - y0) / rows
            size = (b.rng.uniform(0.1, 0.16), b.rng.uniform(0.09, 0.14), b.rng.uniform(0.06, 0.1))
            b.rock((x, y, FORGE_HEARTH + size[2] * 0.55), size, "MenuSoot")
            if b.rng.random() < 0.45:
                ember = (b.rng.uniform(0.04, 0.07), b.rng.uniform(0.04, 0.07), b.rng.uniform(0.03, 0.05))
                b.rock((x + (x1 - x0) / columns * 0.5, y + (y1 - y0) / rows * 0.5, FORGE_HEARTH + ember[2] * 0.6),
                       ember, "MenuEmber")
    return b.finish(["MenuSoot", "MenuEmber"])


def transform_faces(b, first, matrix):
    """Moves the vertices and turns the grain of every face from index first on by a matrix."""
    rotation = matrix.to_3x3()
    for index in range(first, len(b.faces)):
        indices, material, grain, board = b.faces[index]
        for vertex in indices:
            b.vertices[vertex] = tuple(matrix @ Vector(b.vertices[vertex]))
        b.faces[index] = (indices, material, (rotation @ grain).normalized(), board)


def build_signpost(raid):
    """Builds the Moreya signpost: post, arrow board with lettering face, iron rod, straps, nails, stones."""
    b = raid.PartBuilder("MenuMoreyaSignpost", 6607)
    b.board_material = "MenuMoreyaSignpostBoard"
    b.board_box = (SIGN_BACK, SIGN_TIP, SIGN_BOTTOM, SIGN_TOP)
    # The post wears the weathered signpost wood like the subtitle signpost (tools/menu_turn_signpost.py --wood-only
    # gave the committed mesh this material without rebuilding it).
    wood, iron, rust = "MenuSignpostWeatheredWood", "MenuIron", "MenuCorrodedIron"
    post_top = Vector((-0.03, 0.02, 2.62))
    b.log_column((0, 0, -0.35), post_top, 0.13, 0.11, wood, sides=10, rough=0.015)
    b.log_column(post_top, post_top + Vector((0.0, 0.0, 0.18)), 0.12, 0.0, rust, sides=10, rough=0.0)
    b.solid([(-0.075, SIGN_BACK_Y, 1.62), (0.075, SIGN_BACK_Y, 1.62), (0.075, SIGN_BACK_Y, 2.48),
             (-0.075, SIGN_BACK_Y, 2.48)], (0, 0.085, 0), wood, (0, 0, 1))
    # Everything from here on belongs to the board and is tilted with it about the pivot on the post (SIGN_TILT).
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
    # An iron rod from the top of the post carries the long arm of the board.
    rod_end = tilt @ Vector((1.6, (SIGN_FRONT_Y + SIGN_BACK_Y) / 2, SIGN_TOP))
    b.log_column((0.06, rod_end.y, 2.5), rod_end, 0.022, 0.02, rust, sides=6, rough=0.0)
    for angle, distance, size in ((0.3, 0.26, (0.18, 0.14, 0.12)), (1.9, 0.27, (0.16, 0.18, 0.11)),
                                  (3.4, 0.25, (0.2, 0.16, 0.13)), (4.9, 0.26, (0.14, 0.13, 0.1))):
        b.rock((distance * math.cos(angle), distance * math.sin(angle), size[2] * 0.35 + 0.1), size)
    turn = Matrix.Rotation(math.radians(SIGN_TURN), 4, "Z") @ Matrix.Scale(SIGN_SCALE, 4)
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


def import_scene(repo, private, raid, exporter):
    """Imports every AddEntity mesh of the menu scene at its position and gives each material its preview nodes."""
    root = Path(os.environ.get("BUILD_DEPS_ROOT", str(Path.home() / "build-deps")))
    converter = root / "install" / "bin" / "OgreXMLConverter.exe"
    xml_folder = Path(private) / "scene-xml"
    xml_folder.mkdir(parents=True, exist_ok=True)
    collection = bpy.data.collections.new("Menu scene")
    bpy.context.scene.collection.children.link(collection)
    for words in scene_definitions(repo):
        if words[0] != "AddEntity":
            continue
        xml = xml_folder / (words[2] + ".xml")
        if not xml.exists() or xml.stat().st_mtime < (Path(repo) / "models" / words[2]).stat().st_mtime:
            subprocess.run([str(converter), "-q", str(Path(repo) / "models" / words[2]), str(xml)], check=True,
                           capture_output=True)
        obj = exporter.import_mesh(str(xml), None, words[1], collection=collection)
        obj.location = [float(value) for value in words[3:6]]
    text = menu_material_text(repo)
    images = {}
    for material in bpy.data.materials:
        if material.users:
            try:
                values = raid.material_values(text, material.name.split(".")[0])
            except ValueError:
                values = {"diffuse": (0.3, 0.3, 0.3)}
            raid.configure_preview_material(material, values, repo, images)


def flight_sample(poses, share):
    """Returns the camera [x, y, z, rx, ry, rz] at a share (0..1) of the campaign flight from gate_exit to campaign.

    Positions follow the Catmull-Rom curve of RenderSceneMenu::samplePath through gate_entry, gate_exit and campaign;
    both poses only turn about X, so the slerp of their rotations is the linear blend of the X angles.
    """
    before, first, second = (Vector(poses[name][:3]) for name in ("gate_entry", "gate_exit", "campaign"))
    after = second
    t, t2, t3 = share, share * share, share * share * share
    position = 0.5 * ((2 * first) + (-before + second) * t + (2 * before - 5 * first + 4 * second - after) * t2
                      + (-before + 3 * first - 3 * second + after) * t3)
    angles = [poses["gate_exit"][3 + k] + (poses["campaign"][3 + k] - poses["gate_exit"][3 + k]) * share
              for k in range(3)]
    return [position.x, position.y, position.z] + angles


def render_poses(repo, private, raid, exporter):
    """Renders the menu scene from the campaign pose and the campaign flight waypoints.

    Writes <private>/renders/scene_<pose>_<width>x<height>.png (poses campaign, gate_entry, gate_exit and two
    frames of the flight from gate_exit to campaign) with the meshes as they are. Particle effects are not rendered.
    Lights come from the AddPointLight lines, the ambient from [MenuLighting] FlightAmbient, the
    camera from the [MenuCamera] poses with the field of view of the menu camera (45 degrees vertical at 16:9, the same
    horizontal field of view for narrower windows).
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
    for state in ("scene",):
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
        import_scene(repo, private, raid, exporter)
        lights = bpy.data.collections.new("Lights")
        scene.collection.children.link(lights)
        for words in definitions:
            if words[0] == "AddPointLight":
                assembly.add_light(words, lights)
        camera_data = bpy.data.cameras.new("Menu camera")
        # The menu keeps the horizontal field of view of 16:9 (vertical 45 degrees) and widens the vertical one for
        # narrower windows (CameraManager::setViewportSize).
        camera_data.sensor_fit = "HORIZONTAL"
        camera_data.sensor_width = 36
        camera_data.lens = camera_data.sensor_width / (2 * math.tan(math.radians(45) / 2) * 16 / 9)
        camera_data.clip_start = 0.05
        camera_data.clip_end = 400
        camera = bpy.data.objects.new("Menu camera", camera_data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        camera.rotation_mode = "QUATERNION"
        views = [("campaign", poses["campaign"], ((1920, 1080), (1440, 1080))),
                 ("gate_entry", poses["gate_entry"], ((1920, 1080),)),
                 ("gate_exit", poses["gate_exit"], ((1920, 1080), (1440, 1080)))]
        for share in (0.25, 0.5):
            views.append(("flight_exit_to_campaign_%02d" % int(share * 100), flight_sample(poses, share),
                          ((1920, 1080), (1440, 1080))))
        for pose, values, sizes in views:
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
    """Runs the requested builds and renders (every model when none is named) and logs the result."""
    global LOG
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    wanted = set(arguments[2:]) or {"forecourt", "arch", "portal", "signpost", "coals"}
    private.mkdir(parents=True, exist_ok=True)
    LOG = open(private / "menu_moreya_entrance.log", "w", encoding="utf-8")
    try:
        sys.path.insert(0, str(repo / "tools/blender-assets"))
        import moreya_raid_models as raid
        import odp_ogre_io as exporter
        bpy.context.preferences.filepaths.save_version = 0
        if "forecourt" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_forecourt(raid))
        if "arch" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_hall_arch(raid))
        if "portal" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_portal(raid))
        if "signpost" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_signpost(raid))
        if "coals" in wanted:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            export(exporter, repo, private, build_forge_coals(raid))
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
