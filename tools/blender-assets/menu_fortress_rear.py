"""Build the rear half of the menu fortress: side walls, back wall, towers and the buildings of the inner bailey.

The menu scene showed only the front of the fortress (courtyard, gate wall, hall, arches, green tower); views that
look past the gate wall saw an empty plain. These three models complete the building in the style of the existing
fortress. The walls and towers are new damage variants made with the same builders as the front
(tools/blender-assets/menu_scene_models.py, new seeds, without the edge bevel that only shows up close); the bailey
buildings are made of the same chipped masonry blocks, slate roofs and timber, with dim window glow.

    MenuFortressLeft   breached left wall (rubble where the multiplayer flight crosses), left wall, tower, long hall
    MenuFortressRight  breached right wall, right wall, armoury beside the campaign hall, storehouse
    MenuFortressRear   back wall in three sections with a postern, corner towers, well and forge behind the hall

The front half of each side wall is a breach of fallen courses and the back wall stays below the gate arch line, so
nothing of the rear half shows above the front wall or through the gate in the main menu overview.

Every model is one entity at the origin (config/mainmenuscene.cfg). Run in Blender:
    blender --background --python menu_fortress_rear.py -- <repo> <private output folder>
It writes <name>.blend and <name>.mesh.xml for each model into the private folder.
"""
import math
import random
import sys
from pathlib import Path

#: x of the side wall centre lines and y of the back wall (the front wall runs from x -30.5 to 30.2).
SIDE_X = 31.5
BACK_Y = 54.0
#: Wall segment centres along the side walls; the left front segment is the breach the multiplayer flight crosses.
SIDE_SEGMENTS = (21.0, 43.0)
#: Buildings sit 0.5 below the bailey paving (top about 0) so no base edge floats above it.
SINK = -0.5


def _part(models, build, name, seed, damage, angle, location):
    """Builds one fortress part with a menu builder variant, without edge bevel, at a place and z rotation."""
    import bpy
    from mathutils import Matrix
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = seed, damage, name
    obj = build()
    for modifier in list(obj.modifiers):
        if modifier.type == "BEVEL":
            obj.modifiers.remove(modifier)
    obj.matrix_world = Matrix.Translation(location) @ Matrix.Rotation(math.radians(angle), 4, "Z")
    bpy.context.view_layer.update()
    return obj


def house(models, name, seed, centre, length, depth, height, roof, collapse, lit=(1,), chimney=False):
    """Builds a gabled stone house along y (ridge along y) with a partly fallen slate roof and exposed rafters.

    centre is the floor centre; length runs along y, depth along x; collapse is the fraction of roof bays missing.
    """
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = seed, 1.0, name
    b = models.MeshBuilder(name)
    rng = random.Random(seed)
    cx, cy, cz = centre
    half_x, half_y = depth / 2, length / 2
    courses = max(2, int(height / 1.1))
    course = height / courses
    # Long walls (x = +-half_x) and gable ends (y = +-half_y) of large chipped courses with gaps for doors.
    for side in (-1, 1):
        for row in range(courses):
            blocks = max(2, int(length / 2.2))
            for column in range(blocks):
                if row < 2 and column == blocks // 2 and side < 0:
                    continue
                if row == courses - 1 and rng.random() < 0.18:
                    continue
                y = cy - half_y + (column + 0.5) * length / blocks + (0.3 if row % 2 else 0)
                y = min(max(y, cy - half_y + 0.6), cy + half_y - 0.6)
                b.box((cx + side * half_x, y + rng.uniform(-0.05, 0.05), cz + (row + 0.5) * course),
                      (0.75, length / blocks + 0.08, course + 0.02))
        for row in range(courses + int(roof / course)):
            z = cz + (row + 0.5) * course
            above = max(0.0, z - cz - height)
            width = depth * (1 - above / roof) if above else depth
            if width < 0.8:
                break
            b.box((cx, cy + side * half_y, z), (width + 0.6, 0.7, course + 0.02))
    for side in (-1, 1):
        for index in range(max(1, int(length / 4.5))):
            y = cy - half_y + (index + 0.5) * length / max(1, int(length / 4.5))
            material = "MenuWindowGlow" if (index in lit and side > 0) else "MenuBlack"
            b.prism([(cx + side * (half_x + 0.39) - 0.03, cz + height * 0.55), (cx + side * (half_x + 0.39) + 0.03, cz + height * 0.55),
                     (cx + side * (half_x + 0.39) + 0.03, cz + height * 0.55 + 1.1),
                     (cx + side * (half_x + 0.39) - 0.03, cz + height * 0.55 + 1.1)], y - 0.3, y + 0.3, material)
    # Roof bays: slate slabs on both slopes, missing bays show the rafters.
    bays = max(3, int(length / 1.6))
    eave = cz + height
    for bay in range(bays):
        y0 = cy - half_y + bay * length / bays
        y1 = y0 + length / bays
        missing = rng.random() < collapse
        for side in (-1, 1):
            if missing and (side > 0 or rng.random() < 0.6):
                continue
            outer = cx + side * (half_x + 0.6)
            sag = rng.uniform(-0.12, 0.05)
            b.prism([(outer, eave - 0.25 + sag), (cx, eave + roof + sag), (cx, eave + roof + 0.22 + sag),
                     (outer, eave - 0.03 + sag)] if side < 0 else
                    [(cx, eave + roof + sag), (outer, eave - 0.25 + sag), (outer, eave - 0.03 + sag),
                     (cx, eave + roof + 0.22 + sag)], y0 + 0.03, y1 - 0.03, "MenuDarkStone")
        # The rafter pair of each bay stays, also where the slates fell.
        for side in (-1, 1):
            b.segment((cx + side * (half_x + 0.3), (y0 + y1) / 2, eave - 0.05), (cx, (y0 + y1) / 2, eave + roof - 0.1),
                      0.11, 0.09, "MenuAgedWood", 6)
    b.segment((cx, cy - half_y, eave + roof - 0.05), (cx, cy + half_y, eave + roof - 0.05), 0.14, 0.14, "MenuAgedWood", 6)
    if chimney:
        b.column((cx + half_x * 0.5, cy + half_y * 0.4, eave), 0.55, roof + 1.8, 0.42, "MenuRoughStone", 8)
        b.column((cx + half_x * 0.5, cy + half_y * 0.4, eave + roof + 1.7), 0.32, 0.18, 0.32, "MenuSoot", 8)
    # Fallen slates and blocks at the foot of the walls.
    for index in range(10):
        b.box((cx + rng.choice((-1, 1)) * (half_x + rng.uniform(0.6, 2.0)), cy + rng.uniform(-half_y, half_y), cz + 0.12),
              (rng.uniform(0.4, 1.0), rng.uniform(0.3, 0.8), rng.uniform(0.15, 0.35)), rng.choice(("MenuDarkStone", "MenuStone")))
    return b.finish()


def rubble_breach(models, name, seed, x, y0, y1):
    """Builds the collapsed left wall section: a low ridge of fallen courses with a broken stump next to the front wall."""
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = seed, 1.3, name
    b = models.MeshBuilder(name)
    rng = random.Random(seed)
    for index in range(70):
        t = rng.random()
        y = y0 + (y1 - y0) * t
        height = 0.35 + 2.2 * math.sin(math.pi * t) * rng.uniform(0.3, 1.0)
        b.box((x + rng.uniform(-2.2, 2.2), y, rng.uniform(0.1, height)), (rng.uniform(0.8, 1.5), rng.uniform(0.8, 1.6), rng.uniform(0.6, 1.0)),
              rng.choice(("MenuStone", "MenuStone", "MenuDarkStone", "MenuRoughStone")))
    for stump_y, rows in ((y0 + 1.5, 6),):
        for row in range(rows):
            for column in range(2):
                if rng.random() < 0.2 and row > 1:
                    continue
                b.box((x + rng.uniform(-0.06, 0.06), stump_y + (column - 0.5) * 1.34, row * 0.88 + 0.44),
                      (2.8, 1.30, 0.97))
    return b.finish()


def well_and_forge(models, name, seed):
    """Builds the yard behind the campaign hall: a well with a broken winch and a smithy hearth with an anvil."""
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = seed, 1.0, name
    b = models.MeshBuilder(name)
    rng = random.Random(seed)
    for index in range(10):
        angle = index * 2 * math.pi / 10
        b.box((-3.0 + 1.25 * math.cos(angle), 40.0 + 1.25 * math.sin(angle), 0.45), (0.8, 0.55, 0.9))
    b.column((-3.0, 40.0, 0.05), 1.0, 0.1, 1.0, "MenuBlack", 10)
    for side in (-1, 1):
        b.segment((-3.0 + side * 1.3, 40.0, 0.2), (-3.0 + side * 1.3, 40.0, 2.4), 0.1, 0.08, "MenuAgedWood", 6)
    b.segment((-4.4, 40.0, 2.3), (-1.6, 40.0, 2.25), 0.09, 0.09, "MenuAgedWood", 6)
    b.box((4.0, 41.5, 0.55), (2.6, 1.8, 1.1), "MenuRoughStone")
    b.box((4.0, 41.5, 1.13), (2.0, 1.2, 0.08), "MenuEmber")
    b.column((4.0, 42.4, 1.1), 0.6, 4.2, 0.4, "MenuRoughStone", 8)
    b.box((2.2, 39.8, 0.4), (0.5, 0.5, 0.8), "MenuAgedWood")
    b.box((2.2, 39.8, 0.9), (0.9, 0.35, 0.22), "MenuCorrodedIron")
    for index in range(12):
        b.box((rng.uniform(-7, 7), rng.uniform(34, 48), 0.1), (rng.uniform(0.3, 0.9), rng.uniform(0.3, 0.8), rng.uniform(0.15, 0.4)),
              rng.choice(("MenuStone", "MenuDarkStone", "MenuAgedWood")))
    return b.finish()


def _bake(objects, name):
    """Joins the evaluated objects into one mesh object with world-space vertices and shared material slots."""
    import bpy
    import bmesh
    depsgraph = bpy.context.evaluated_depsgraph_get()
    names = []
    combined = bmesh.new()
    for obj in objects:
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), depsgraph=depsgraph)
        mesh.transform(obj.matrix_world)
        remap = []
        for material in mesh.materials:
            base = material.name.split(".")[0]
            if base not in names:
                names.append(base)
            remap.append(names.index(base))
        for polygon in mesh.polygons:
            polygon.material_index = remap[polygon.material_index] if remap else 0
        combined.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    result = bpy.data.meshes.new(name)
    combined.to_mesh(result)
    combined.free()
    for material_name in names:
        result.materials.append(bpy.data.materials[material_name])
    obj = bpy.data.objects.new(name, result)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def main():
    """Builds the three fortress models and writes their Blender sources and Ogre XML meshes."""
    import bpy
    from mathutils import Vector
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    sys.path.insert(0, str(repo / "tools/blender-assets"))
    import menu_scene_models as models
    import odp_ogre_io as exporter
    from menu_scene_assembly import configure_material, material_values
    material_text = (repo / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
    private.mkdir(parents=True, exist_ok=True)
    parts = {
        "MenuFortressLeft": lambda: [
            rubble_breach(models, "MenuFortressBreach", 5101, -SIDE_X, 9.5, 31.0),
            _part(models, models.tower, "MenuTowerBreach", 5111, 1.8, 90, Vector((-SIDE_X, 32.0, SINK))),
            _part(models, models.wall, "MenuWallLeftBack", 5121, 1.15, 90, Vector((-SIDE_X, SIDE_SEGMENTS[1], SINK))),
            house(models, "MenuLongHall", 5131, (-22.0, 33.5, SINK), 11.0, 7.0, 5.5, 3.6, 0.35, lit=(1,)),
            house(models, "MenuBarracksLeft", 5141, (-21.0, 45.0, SINK), 9.0, 6.0, 5.0, 3.2, 0.2, lit=(0,), chimney=True),
        ],
        "MenuFortressRight": lambda: [
            rubble_breach(models, "MenuFortressBreachRight", 5201, SIDE_X, 9.5, 31.0),
            _part(models, models.wall, "MenuWallRightBack", 5241, 1.25, -90, Vector((SIDE_X, SIDE_SEGMENTS[1], SINK))),
            house(models, "MenuArmoury", 5251, (12.2, 20.5, SINK), 13.0, 6.2, 6.5, 3.8, 0.4, lit=(0, 2), chimney=True),
            house(models, "MenuStorehouse", 5261, (21.0, 42.0, SINK), 10.0, 7.5, 5.0, 3.4, 0.25, lit=(1,)),
        ],
        "MenuFortressRear": lambda: [
            _part(models, models.wall, "MenuWallBackLeft", 5311, 1.2, 0, Vector((-19.3, BACK_Y + 0.1, SINK))),
            _part(models, models.wall, "MenuWallBackRight", 5321, 1.05, 0, Vector((19.2, BACK_Y, SINK))),
            # The middle section stands 1.6 behind the two outer ones so their overlapping ends never share a face.
            _part(models, models.wall, "MenuWallBackMiddle", 5331, 1.3, 0, Vector((0.0, BACK_Y + 1.6, SINK))),
            _part(models, models.tower, "MenuTowerCornerLeft", 5361, 1.0, 45, Vector((-SIDE_X, BACK_Y, SINK))),
            _part(models, models.tower, "MenuTowerCornerRight", 5371, 1.1, -45, Vector((SIDE_X, BACK_Y, SINK))),
            well_and_forge(models, "MenuBaileyYard", 5381),
        ],
    }
    for name, build in parts.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.preferences.filepaths.save_version = 0
        for material_name, colour in models.COLOURS.items():
            bpy.data.materials.new(material_name).diffuse_color = (*colour, 1)
        bpy.data.materials.new("MenuWetStone").diffuse_color = (0.30, 0.29, 0.28, 1)
        objects = build()
        obj = _bake(objects, name)
        for part in objects:
            bpy.data.objects.remove(part, do_unlink=True)
        images = {}
        for material in obj.data.materials:
            configure_material(material, material_values(material_text, material.name), repo, images)
        obj["menu_source_family"] = "MenuWallSegment"
        bpy.ops.wm.save_as_mainfile(filepath=str(private / (name + ".blend")))
        stats = exporter.export_mesh_xml(obj, None, str(private / (name + ".mesh.xml")), None, smooth=False)
        print("FORTRESS_PART", name, len(obj.data.polygons), stats, flush=True)


if __name__ == "__main__":
    main()
