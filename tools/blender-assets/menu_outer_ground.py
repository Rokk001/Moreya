"""Build the wasteland around the menu fortress: ground, rubble and a ring of crags that closes the horizon.

The menu scene had no ground outside the courtyard, so camera poses and flights that look past the walls saw
the lower half of the sky dome (clouds and the warm horizon haze) where ground belongs. This model is one
entity at the origin (config/mainmenuscene.cfg, AddEntity OuterGround). It lies below the courtyard paving and
the buildings, undulates outside the fortress footprint and rises to fractured crags inside the sky dome, high
enough that no view ray below the horizon of any menu camera passes over them.

The geometry core (build_geometry) is plain Python, so source/tests can use it without Blender. Run in Blender:
    blender --background --python menu_outer_ground.py -- <repo> <private output folder>
It saves MenuOuterGround.blend and MenuOuterGround.mesh.xml into the private folder (convert the XML with
OgreXMLConverter into models/MenuOuterGround.mesh).
"""
import math
import random
import sys
from pathlib import Path

#: Centre of the sky dome of MenuBackdrop (ellipsoid radii 190, 190, 115); the ground rings share it.
CENTRE = (0.0, 45.0)
#: Ground level under the courtyard paving, the walls and the buildings (paving tops start at -0.27).
FOOTPRINT_LEVEL = -0.42
#: Fortress footprint (x min, x max, y min, y max) that stays at FOOTPRINT_LEVEL; the terrain starts outside it.
FOOTPRINT = (-31.0, 31.0, -33.0, 32.0)
#: Distance over which the terrain rises from the footprint level to its full relief.
FOOTPRINT_BLEND = 14.0
#: Radii of the ground rings around CENTRE; the crag ring starts at RIM_FOOT.
GROUND_RADII = (0, 4, 9, 15, 22, 30, 39, 49, 60, 72, 85, 99, 113, 126, 137)
RIM_FOOT = 146.0
RIM_CREST = 163.0
RIM_BACK = 171.0
#: Angular segments of the rings (2.5 degrees).
SEGMENTS = 144
#: Lowest crest of the crags; the highest menu camera (settings flight) flies at height 20.5.
RIM_MIN_HEIGHT = 24.0
#: World size of one texture repeat on the ground and on the crags.
TEXTURE_METRES = 4.5
GROUND_MATERIAL = "MenuWasteGround"
CRAG_MATERIAL = "MenuMountain"


def _hash(ix, iy, seed):
    """Returns a repeatable value in [0, 1) for one lattice point."""
    value = math.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return value - math.floor(value)


def value_noise(x, y, seed=0):
    """Returns smooth lattice noise in [0, 1)."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash(ix, iy, seed)
    b = _hash(ix + 1, iy, seed)
    c = _hash(ix, iy + 1, seed)
    d = _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def fbm(x, y, seed=0, octaves=4):
    """Returns fractal noise in about [-1, 1]."""
    total = 0.0
    weight = 1.0
    norm = 0.0
    for octave in range(octaves):
        total += (value_noise(x, y, seed + octave * 13) * 2 - 1) * weight
        norm += weight
        weight *= 0.5
        x *= 2.03
        y *= 2.03
    return total / norm


def footprint_distance(x, y):
    """Returns the distance of a point outside the fortress footprint to it (0 inside)."""
    dx = max(FOOTPRINT[0] - x, 0.0, x - FOOTPRINT[1])
    dy = max(FOOTPRINT[2] - y, 0.0, y - FOOTPRINT[3])
    return math.hypot(dx, dy)


def ground_height(x, y):
    """Returns the terrain height at a point of the ground rings (not the crags)."""
    distance = footprint_distance(x, y)
    if distance <= 0.0:
        return FOOTPRINT_LEVEL
    blend = min(1.0, distance / FOOTPRINT_BLEND)
    blend = blend * blend * (3 - 2 * blend)
    relief = 1.4 * fbm(x * 0.045, y * 0.045, 3) + 0.5 * fbm(x * 0.17, y * 0.17, 7)
    # Broad swells grow with the distance; near the fortress the ground stays low beside the flights.
    swell = min(1.0, distance / 60.0) * 3.0 * (0.5 + 0.5 * fbm(x * 0.012, y * 0.012, 11))
    return FOOTPRINT_LEVEL + blend * (relief + swell + 0.6)


def crest_height(angle):
    """Returns the crest height of the crag ring at a polar angle around CENTRE."""
    broad = 0.5 + 0.5 * fbm(math.cos(angle) * 2.6 + 9, math.sin(angle) * 2.6 + 4, 19)
    jagged = 0.5 + 0.5 * fbm(math.cos(angle) * 11 + 3, math.sin(angle) * 11 + 1, 23, 3)
    return RIM_MIN_HEIGHT + 7.0 * broad + 6.0 * jagged


def _uv_ground(x, y):
    """Returns the planar texture coordinates of a ground point."""
    return (x / TEXTURE_METRES, y / TEXTURE_METRES)


def build_geometry(seed=5):
    """Returns (vertices, faces, face materials, face texture coordinates) of the wasteland.

    Faces are triangles (vertex index triples, counter-clockwise seen from outside); texture coordinates are
    one (u, v) triple per face corner so the crag faces can use their own projection.
    """
    rng = random.Random(seed)
    vertices = []
    faces = []
    materials = []
    uvs = []
    rings = []
    # Ground rings, then the crag foot, crest and back; the crest is fractured radially and in height.
    radii = list(GROUND_RADII) + [RIM_FOOT, (RIM_FOOT + RIM_CREST) * 0.5, RIM_CREST, RIM_BACK]
    for ring, radius in enumerate(radii):
        row = []
        for segment in range(SEGMENTS if radius > 0 else 1):
            angle = 2 * math.pi * segment / SEGMENTS
            jitter = 0.0 if radius == 0 else rng.uniform(-0.18, 0.18) * (2 * math.pi / SEGMENTS)
            r = radius + (rng.uniform(-2.5, 2.5) if 0 < radius < RIM_FOOT else 0.0)
            if radius == RIM_CREST:
                r += rng.uniform(-3.0, 3.0)
            x = CENTRE[0] + r * math.cos(angle + jitter)
            y = CENTRE[1] + r * math.sin(angle + jitter)
            if radius < RIM_FOOT:
                z = ground_height(x, y)
            elif radius == RIM_FOOT:
                z = ground_height(x, y) + 1.5
            elif radius < RIM_CREST:
                z = crest_height(angle) * rng.uniform(0.42, 0.6)
            elif radius == RIM_CREST:
                z = crest_height(angle) * rng.uniform(0.94, 1.06)
            else:
                z = crest_height(angle) * 0.55
            row.append(len(vertices))
            vertices.append((x, y, z))
        rings.append(row)
    for ring in range(len(rings) - 1):
        inner, outer = rings[ring], rings[ring + 1]
        crag = radii[ring] >= RIM_FOOT
        material = CRAG_MATERIAL if crag else GROUND_MATERIAL
        for segment in range(SEGMENTS):
            following = (segment + 1) % SEGMENTS
            quads = []
            if len(inner) == 1:
                quads.append((inner[0], outer[segment], outer[following]))
            else:
                a, b, c, d = inner[segment], outer[segment], outer[following], inner[following]
                # Alternate the diagonal so the ridges do not line up into radial streaks.
                if (segment + ring) % 2:
                    quads.extend(((a, b, c), (a, c, d)))
                else:
                    quads.extend(((a, b, d), (b, c, d)))
            for triangle in quads:
                faces.append(triangle)
                materials.append(material)
                if crag:
                    uvs.append(tuple(((vertices[i][0] + vertices[i][1]) / TEXTURE_METRES, vertices[i][2] / TEXTURE_METRES)
                                     for i in triangle))
                else:
                    uvs.append(tuple(_uv_ground(vertices[i][0], vertices[i][1]) for i in triangle))
    _add_rubble(rng, vertices, faces, materials, uvs)
    return vertices, faces, materials, uvs


#: Areas the rubble keeps clear: buildings, the courtyard and the flight corridors (x min, x max, y min, y max).
RUBBLE_CLEAR = (
    (-27.0, 28.0, -31.0, 20.5),     # courtyard paving and everything on it
    (-31.0, 31.0, 3.5, 11.0),       # walls, towers and the side cave front
    (-7.5, 7.5, 13.5, 31.0),        # campaign hall, table and gate beast
    (-29.0, -11.0, 20.0, 26.0),     # gathering arches and the arcade
    (16.5, 27.5, 5.0, 30.5),        # green tower and side cave
)


def _clear(x, y, radius):
    """Returns True when a rubble rock of the radius at (x, y) keeps every RUBBLE_CLEAR area free."""
    return not any(x0 - radius < x < x1 + radius and y0 - radius < y < y1 + radius for x0, x1, y0, y1 in RUBBLE_CLEAR)


def _add_rubble(rng, vertices, faces, materials, uvs):
    """Adds fractured boulders and toppled wall blocks that rest on the ground around the fortress."""
    placed = 0
    attempts = 0
    # Dense rubble where the poses look past the walls, sparser larger rocks further out.
    while placed < 150 and attempts < 6000:
        attempts += 1
        near = placed < 115
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(60, 125)
        x = rng.uniform(-62, 62) if near else CENTRE[0] + distance * math.cos(angle)
        y = rng.uniform(-48, 72) if near else CENTRE[1] + distance * math.sin(angle)
        size = rng.uniform(0.35, 1.5) if near else rng.uniform(2.0, 5.5)
        if not _clear(x, y, size * 1.4):
            continue
        if math.hypot(x - CENTRE[0], y - CENTRE[1]) > RIM_FOOT - size * 2:
            continue
        _boulder(rng, vertices, faces, materials, uvs, x, y, size, block=placed % 5 == 0)
        placed += 1


def _boulder(rng, vertices, faces, materials, uvs, x, y, size, block):
    """Adds one closed fractured rock (or a squared fallen wall block) sunk into the ground."""
    sides = 6 if block else 7
    base = ground_height(x, y) - 0.25 * size
    rows = ((0.0, 1.0), (0.45, 1.08), (0.85, 0.72), (1.0, 0.35)) if not block else ((0.0, 1.0), (0.9, 0.98), (1.0, 0.86))
    height = size * (rng.uniform(0.6, 1.0) if not block else rng.uniform(0.5, 0.7))
    stretch = rng.uniform(0.7, 1.3)
    turn = rng.uniform(0, math.pi)
    first = len(vertices)
    for level, spread in rows:
        for side in range(sides):
            angle = turn + 2 * math.pi * side / sides
            radius = size * spread * (rng.uniform(0.78, 1.18) if not block else 1.0)
            vx = radius * math.cos(angle) * stretch
            vy = radius * math.sin(angle) / stretch
            vertices.append((x + vx, y + vy, base + height * level + rng.uniform(-0.08, 0.08) * size))
    top = len(vertices)
    vertices.append((x + rng.uniform(-0.2, 0.2) * size, y + rng.uniform(-0.2, 0.2) * size, base + height * 1.05))
    for row in range(len(rows) - 1):
        for side in range(sides):
            a = first + row * sides + side
            b = first + row * sides + (side + 1) % sides
            c = first + (row + 1) * sides + (side + 1) % sides
            d = first + (row + 1) * sides + side
            for triangle in ((a, b, c), (a, c, d)):
                faces.append(triangle)
    for side in range(sides):
        faces.append((first + (len(rows) - 1) * sides + side, first + (len(rows) - 1) * sides + (side + 1) % sides, top))
    for side in range(1, sides - 1):
        faces.append((first, first + side + 1, first + side))
    count = (len(rows) - 1) * sides * 2 + sides + sides - 2
    for triangle in faces[-count:]:
        materials.append(CRAG_MATERIAL)
        uvs.append(tuple(((vertices[i][0] - vertices[i][1]) / 2.5, vertices[i][2] / 2.5) for i in triangle))


def main():
    """Builds the Blender source and the Ogre XML of the wasteland (run inside Blender in background mode)."""
    import bpy
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    sys.path.insert(0, str(repo / "tools/blender-assets"))
    import odp_ogre_io as exporter
    from menu_scene_assembly import configure_material, material_values
    private.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    vertices, faces, face_materials, face_uvs = build_geometry()
    mesh = bpy.data.meshes.new("MenuOuterGround")
    mesh.from_pydata(vertices, [], faces)
    names = [GROUND_MATERIAL, CRAG_MATERIAL]
    material_text = (repo / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
    images = {}
    for name in names:
        material = bpy.data.materials.new(name)
        configure_material(material, material_values(material_text, name), repo, images)
        mesh.materials.append(material)
    layer = mesh.uv_layers.new(name="UVMap")
    for polygon, material, corners in zip(mesh.polygons, face_materials, face_uvs):
        polygon.material_index = names.index(material)
        polygon.use_smooth = material == GROUND_MATERIAL
        for loop, uv in zip(polygon.loop_indices, corners):
            layer.data[loop].uv = uv
    mesh.validate()
    obj = bpy.data.objects.new("MenuOuterGround", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["menu_source_family"] = "MenuBackdrop"
    blend = private / "MenuOuterGround.blend"
    xml = private / "MenuOuterGround.mesh.xml"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    stats = exporter.export_mesh_xml(obj, None, str(xml), None, smooth=False)
    print("OUTER_GROUND_DONE", len(vertices), len(faces), stats, flush=True)


if __name__ == "__main__":
    main()
