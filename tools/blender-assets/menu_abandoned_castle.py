"""Build the abandoned castle of the main menu scene and the fixes that keep every part of the scene on the ground.

INGAME-QS-12 K1: no structure of the menu scene floats, and behind the gate and the campaign hall an abandoned old
castle is built instead of flat stand-in geometry. The models (config/mainmenuscene.cfg):

    MenuAbandonedCastle  entity at the origin: keep with a fallen roof, round and square towers and a tall spire
                         tower behind the campaign hall, in the masonry of the fortress
    MenuCampaignHall     the hall of tools/blender-assets/menu_scene_models.py (hall()) with whole arches and no
                         wall block over a missing one
    MenuOuterGround      the ground of tools/blender-assets/menu_outer_ground.py; every flagstone reaches the ground
    MenuBannerBrackets   entity at the origin: iron wall brackets that carry the rods of the two gate banners
                         (LeftBanner, RightBanner) on the tower faces behind them

The space behind the campaign table (x -4..4, y 23..32) stays free for the staircase into Moreya. Every part stands on
the ground or on another part (source/tests/check_menu_scene_grounded.py). Run in Blender:
    blender --background --python menu_abandoned_castle.py -- <repo> <private output folder> [model names]
It saves <name>.blend and <name>.mesh.xml into the private folder and converts the meshes into <repo>/models
(OgreXMLConverter of BUILD_DEPS_ROOT, else %USERPROFILE%/build-deps). A log is written to <private>/castle.log.
"""
import math
import os
import random
import subprocess
import sys
import traceback
from pathlib import Path

import bpy

LOG = None


def log(text):
    """Appends one line to the log (stdout of a background Blender started by the Store launcher is lost)."""
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(str(text) + "\n")


def whole_arch(b, x, y, spring, radius, thickness, depth, count, material="MenuCarvedStone"):
    """Adds a closed arch of wedge stones whose joints touch (no missing or sagging stone)."""
    for index in range(count):
        a = math.pi * index / count + 0.002
        c = math.pi * (index + 1) / count - 0.002
        polygon = [(x + radius * math.cos(a), spring + radius * math.sin(a)),
                   (x + (radius + thickness) * math.cos(a), spring + (radius + thickness) * math.sin(a)),
                   (x + (radius + thickness) * math.cos(c), spring + (radius + thickness) * math.sin(c)),
                   (x + radius * math.cos(c), spring + radius * math.sin(c))]
        b.prism(polygon, y - depth / 2, y + depth / 2, material)


def keep_wall(b, rng, axis, fixed, start, end, height, thickness, gaps=(), material="MenuStone"):
    """Lays a castle wall of large courses; gaps are (start, end, bottom) openings that stay open up to the top.

    A block that reaches into an opening is cut at its edge, so the masonry beside an opening rises straight and no
    block hangs over it.
    """
    course = 1.05
    rows = int(height / course)
    for row in range(rows):
        z = (row + 0.5) * course
        length = 1.9
        position = start - (length * 0.5 if row % 2 else 0.0)
        while position < end - 0.05:
            pieces = [(max(position, start), min(position + length, end))]
            for gap_low, gap_high, gap_bottom in gaps:
                if z + course / 2 <= gap_bottom:
                    continue
                pieces = [piece for low, high in pieces
                          for piece in ((low, min(high, gap_low)), (max(low, gap_high), high)) if piece[1] > piece[0]]
            for low, high in pieces:
                if high - low <= 0.2:
                    continue
                centre = (low + high) / 2
                if axis == 0:
                    b.box((centre, fixed, z), (high - low - 0.03, thickness, course + 0.02), material)
                else:
                    b.box((fixed, centre, z), (thickness, high - low - 0.03, course + 0.02), material)
            position += length
    return rows * course


def window_slit(b, axis, fixed, along, bottom, height, width, outward):
    """Adds a dark arched window recess painted onto the outer face of a wall (it lies on the wall face)."""
    top = bottom + height
    polygon = [(along - width / 2, bottom), (along + width / 2, bottom), (along + width / 2, top - width / 2),
               (along, top), (along - width / 2, top - width / 2)]
    if axis == 0:
        b.prism(polygon, fixed + outward * 0.001, fixed + outward * 0.012, "MenuBlack")
    else:
        start = len(b.vertices)
        b.prism(polygon, fixed + outward * 0.001, fixed + outward * 0.012, "MenuBlack")
        # The prism runs along y; turn it so the recess lies on a wall that runs along y.
        for index in range(start, len(b.vertices)):
            x, y, z = b.vertices[index]
            b.vertices[index] = (y, x, z)


def round_tower(b, rng, centre, radius, height, roof, broken):
    """Adds a round tower of stacked ring courses with a conical slate roof (broken: roof partly fallen)."""
    cx, cy = centre
    course = 1.05
    rows = int(height / course)
    for row in range(rows):
        z = (row + 0.5) * course
        stones = max(8, int(2 * math.pi * radius / 1.6))
        for stone in range(stones):
            if broken and row >= rows - 2 and stone % 3 == 0:
                continue
            angle = (stone + (0.5 if row % 2 else 0.0)) * 2 * math.pi / stones
            length = 2 * math.pi * radius / stones
            # A block of the ring: a box along x moved out to the radius and turned to its angle.
            start = len(b.vertices)
            b.box((0.0, 0.0, z), (length + 0.02, 0.9, course + 0.02))
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            for index in range(start, len(b.vertices)):
                x, y, zz = b.vertices[index]
                y += radius
                b.vertices[index] = (cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a, zz)
    wall_top = rows * course
    # A floor slab closes the top of the ring, the roof cone stands on it.
    b.column((cx, cy, wall_top), radius + 0.45, 0.3, radius + 0.45, "MenuDarkStone", 14)
    if broken:
        b.column((cx, cy, wall_top + 0.3), radius + 0.2, roof * 0.55, radius * 0.45, "MenuDarkStone", 12)
        for index in range(5):
            angle = index * 2 * math.pi / 5 + 0.4
            b.segment((cx + radius * 0.45 * math.cos(angle), cy + radius * 0.45 * math.sin(angle), wall_top + 0.3 + roof * 0.55),
                      (cx + radius * 0.15 * math.cos(angle), cy + radius * 0.15 * math.sin(angle), wall_top + 0.3 + roof * 0.85),
                      0.09, 0.06, "MenuAgedWood", 6)
    else:
        b.column((cx, cy, wall_top + 0.3), radius + 0.2, roof, 0, "MenuDarkStone", 12)
    return wall_top


def castle(models):
    """Builds the abandoned castle behind the campaign hall: keep, fallen roof, towers and the spire tower."""
    b = models.MeshBuilder("MenuAbandonedCastle")
    rng = random.Random(7301)
    x0, x1, y0, y1 = -9.0, 9.0, 44.5, 51.5
    thickness = 1.2
    height = 13.65
    # Front wall with a gate and a breach on the right, back wall, two side walls.
    keep_wall(b, rng, 0, y0, x0, x1, height, thickness, gaps=((-1.4, 1.4, 0.0), (4.2, 6.6, 8.0)))
    keep_wall(b, rng, 0, y1, x0, x1, height, thickness)
    for side in (-1, 1):
        keep_wall(b, rng, 1, side * 9.0, y0 + thickness / 2, y1 - thickness / 2, height, thickness)
    # Gate arch on the gate opening and a door leaf fallen inwards onto the floor.
    whole_arch(b, 0.0, y0, 4.2, 1.4, 0.7, thickness + 0.1, 11)
    for side in (-1, 1):
        b.box((side * 1.75, y0, 2.1), (0.7, thickness + 0.1, 4.2), "MenuCarvedStone")
    b.box((0.3, y0 + 2.2, 0.12), (2.4, 3.8, 0.24), "MenuAgedWood")
    # Window slits on the front wall.
    for along in (-6.5, -3.5, 3.5):
        window_slit(b, 0, y0 - thickness / 2, along, 6.0, 2.2, 0.8, -1)
    for along in (-6.5, -3.0, 2.8):
        window_slit(b, 0, y0 - thickness / 2, along, 10.2, 1.6, 0.6, -1)
    # Battlements on the wall tops, some fallen.
    for x in [x0 + 0.6 + k * 1.5 for k in range(12)]:
        if rng.random() < 0.3 or 4.0 < x < 6.9:
            continue
        b.box((x, y0, height + 0.55), (0.9, thickness, 1.1))
    for x in [x0 + 0.6 + k * 1.5 for k in range(12)]:
        if rng.random() < 0.25:
            continue
        b.box((x, y1, height + 0.55), (0.9, thickness, 1.1))
    # Gable roof along x: slate slabs on the walls, most of the front slope fallen, rafters left standing.
    eave, ridge = height, height + 5.0
    bays = 9
    for bay in range(bays):
        xa = x0 + 0.6 + bay * (x1 - x0 - 1.2) / bays
        xb = xa + (x1 - x0 - 1.2) / bays
        for side in (-1, 1):
            if side < 0 and bay not in (0, 7, 8):
                continue
            if side > 0 and bay in (3, 4):
                continue
            outer = y0 if side < 0 else y1
            middle = (y0 + y1) / 2
            plate = [(xa + 0.02, outer), (xb - 0.02, outer), (xb - 0.02, middle), (xa + 0.02, middle)]
            start = len(b.vertices)
            b.slab(plate, 0.0, 0.22, "MenuDarkStone")
            for index in range(start, len(b.vertices)):
                x, y, z = b.vertices[index]
                share = abs(y - outer) / abs(middle - outer)
                b.vertices[index] = (x, y, eave + share * (ridge - eave) + z)
        for side in (-1, 1):
            outer = y0 if side < 0 else y1
            b.segment(((xa + xb) / 2, outer, eave + 0.1), ((xa + xb) / 2, (y0 + y1) / 2, ridge + 0.05), 0.12, 0.1,
                      "MenuAgedWood", 6)
    for side in (-1, 1):
        # Gable walls over the side walls carry the ridge beam.
        for row in range(5):
            share = (row + 0.5) / 5
            width = (y1 - y0) * (1 - share)
            b.box((side * 9.0, (y0 + y1) / 2, eave + row * 1.0 + 0.5), (thickness, max(width, 0.8), 1.02))
    b.segment((x0 + 0.6, (y0 + y1) / 2, ridge + 0.1), (x1 - 0.6, (y0 + y1) / 2, ridge + 0.1), 0.16, 0.16, "MenuAgedWood", 6)
    # Fallen slates and blocks at the foot of the breach and in front of the keep.
    for index in range(16):
        b.box((rng.uniform(3.6, 7.4), rng.uniform(y0 - 2.6, y0 - 0.8), 0.15 + rng.uniform(0, 0.1)),
              (rng.uniform(0.5, 1.1), rng.uniform(0.4, 0.9), rng.uniform(0.25, 0.45)), rng.choice(("MenuStone", "MenuDarkStone")))
    # Round tower at the front left corner, square tower at the front right corner.
    round_tower(b, rng, (x0 - 1.2, y0 + 0.3), 2.6, 19.0, 6.5, broken=False)
    square_top = 17.85
    for side_x in (x1 - 0.6, x1 + 4.0):
        keep_wall(b, rng, 1, side_x, y0 - 2.2, y0 + 2.8, square_top, 1.0)
    for side_y in (y0 - 2.2, y0 + 2.8):
        keep_wall(b, rng, 0, side_y, x1 - 0.1, x1 + 3.5, square_top, 1.0)
    for x in (x1 - 0.6, x1 + 1.1, x1 + 2.6, x1 + 4.0):
        if x > x1 + 2.0 and rng.random() < 0.6:
            continue
        b.box((x, y0 - 2.2, square_top + 0.55), (0.9, 1.0, 1.1))
    # The spire tower rises from the back of the keep, left of the middle.
    spire_wall = round_tower(b, rng, (-3.5, y1 + 1.6), 2.2, 26.0, 9.0, broken=True)
    window_slit(b, 0, y1 + 1.6 - 2.2 - 0.46, -3.5, spire_wall - 6.0, 2.4, 0.7, -1)
    return b.finish()


#: Banner rods of LeftBanner and RightBanner (world centre y and z) and the x of their wall brackets, where the tower
#: face stands behind the rod (the left tower is broken off left of x -9.3).
BANNER_RODS = ((3.705, 11.6, (-9.15, -7.6)), (3.5, 11.29, (8.0, 10.4)))
#: The brackets reach into the tower faces (y 4.45 to 4.65 behind the rods) up to this y.
BRACKET_WALL_Y = 4.75


def banner_brackets(models):
    """Builds iron wall brackets that carry the rods of the two gate banners on the tower faces behind them."""
    b = models.MeshBuilder("MenuBannerBrackets")
    for rod_y, rod_z, xs in BANNER_RODS:
        for x in xs:
            b.segment((x, rod_y, rod_z), (x, BRACKET_WALL_Y, rod_z), 0.055, 0.05, "MenuCorrodedIron", 8)
            b.segment((x, rod_y + 0.05, rod_z - 0.02), (x, BRACKET_WALL_Y, rod_z - 0.65), 0.04, 0.04, "MenuCorrodedIron", 8)
            b.slab([(x - 0.14, BRACKET_WALL_Y - 0.25), (x + 0.14, BRACKET_WALL_Y - 0.25), (x + 0.14, BRACKET_WALL_Y),
                    (x - 0.14, BRACKET_WALL_Y)], rod_z - 0.8, rod_z + 0.15, "MenuIron")
            # A ring around the rod.
            b.segment((x - 0.06, rod_y, rod_z), (x + 0.06, rod_y, rod_z), 0.12, 0.12, "MenuCorrodedIron", 10)
    return b.finish()


def hall(models):
    """Builds the campaign hall with whole arches and no wall block over a missing one (menu_scene_models.hall)."""
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = 1100, 1.15, "MenuCampaignHall"
    return models.hall()


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


def outer_ground(repo, private):
    """Builds the ground of menu_outer_ground.py as a Blender object with its materials and texture coordinates."""
    import menu_outer_ground as ground
    from menu_scene_assembly import configure_material, material_values
    vertices, faces, face_materials, face_uvs = ground.build_geometry()
    mesh = bpy.data.meshes.new("MenuOuterGround")
    mesh.from_pydata(vertices, [], faces)
    names = list(dict.fromkeys(face_materials))
    material_text = (repo / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
    images = {}
    for name in names:
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        try:
            configure_material(material, material_values(material_text, name), repo, images)
        except Exception as error:
            log("preview material %s: %r" % (name, error))
        mesh.materials.append(material)
    layer = mesh.uv_layers.new(name="UVMap")
    smooth = set(name for _, name in ground.GROUND_BANDS)
    for polygon, material, corners in zip(mesh.polygons, face_materials, face_uvs):
        polygon.material_index = names.index(material)
        polygon.use_smooth = material in smooth
        for loop, uv in zip(polygon.loop_indices, corners):
            layer.data[loop].uv = uv
    obj = bpy.data.objects.new("MenuOuterGround", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["menu_source_family"] = "MenuBackdrop"
    return obj


def main():
    """Builds the requested models (all by default), saves their sources and converts their meshes."""
    global LOG
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    wanted = set(arguments[2:])
    private.mkdir(parents=True, exist_ok=True)
    LOG = private / "castle.log"
    sys.path.insert(0, str(repo / "tools/blender-assets"))
    import menu_scene_models as models
    import odp_ogre_io as exporter
    from menu_scene_assembly import configure_material, material_values
    material_text = "\n".join((repo / "materials/scripts" / name).read_text(encoding="utf-8")
                              for name in ("MenuScene.material", "MenuSignpost.material"))
    builders = {
        "MenuAbandonedCastle": lambda: castle(models),
        "MenuCampaignHall": lambda: hall(models),
        "MenuOuterGround": lambda: outer_ground(repo, private),
        "MenuBannerBrackets": lambda: banner_brackets(models),
    }
    for name, build in builders.items():
        if wanted and name not in wanted:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.preferences.filepaths.save_version = 0
        for material_name, colour in models.COLOURS.items():
            bpy.data.materials.new(material_name).diffuse_color = (*colour, 1)
        bpy.data.materials.new("MenuWetStone").diffuse_color = (0.30, 0.29, 0.28, 1)
        models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = 7000, 0.8, name
        obj = build()
        obj.name = name
        # The edge bevel only shows up close; the castle and the brackets are seen from afar (as the fortress parts).
        if name in ("MenuAbandonedCastle", "MenuBannerBrackets"):
            for modifier in list(obj.modifiers):
                if modifier.type == "BEVEL":
                    obj.modifiers.remove(modifier)
        images = {}
        if name != "MenuOuterGround":
            for material in obj.data.materials:
                try:
                    configure_material(material, material_values(material_text, material.name), repo, images)
                except Exception as error:
                    log("preview material %s: %r" % (material.name, error))
            obj["menu_source_family"] = {"MenuAbandonedCastle": "MenuWallSegment",
                                         "MenuBannerBrackets": "MenuBanner"}.get(name, "MenuCampaignHall")
        bpy.ops.wm.save_as_mainfile(filepath=str(private / (name + ".blend")))
        stats = exporter.export_mesh_xml(obj, None, str(private / (name + ".mesh.xml")), None, smooth=False)
        log("%s %d faces %s" % (name, len(obj.data.polygons), stats))
        convert(repo, private, name)
    log("done")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
