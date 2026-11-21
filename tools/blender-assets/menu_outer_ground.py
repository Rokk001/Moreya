"""Build the ground around and inside the menu fortress: paving, wasteland, rubble, ruins and a ring of crags.

The menu scene had no ground outside the courtyard, so camera poses and flights that look past the walls saw the
lower half of the sky dome (clouds and the warm horizon haze) where ground belongs. This model is one entity at the
origin (config/mainmenuscene.cfg, AddEntity OuterGround):
- paving like the courtyard (MenuWetStone) over the whole fortress footprint outside the courtyard: inner bailey,
  the strips beside the courtyard and under the side and back walls (MenuFortressLeft/Right/Rear);
- outside the footprint a wasteland whose ground material steps from the paving brightness near the walls to dark
  far out, with glowing ember veins, larger rocks and remains of an outer wall;
- a ring of fractured crags with spires inside the sky dome, high enough that no view ray below the horizon of any
  menu camera passes over it, and dark against the warm haze above the horizon.

The geometry core (build_geometry) is plain Python, so source/tests can use it without Blender. Run in Blender:
    blender --background --python menu_outer_ground.py -- <repo> <private output folder>
It saves MenuOuterGround.blend and MenuOuterGround.mesh.xml into the private folder.
"""
import math
import random
import sys
from pathlib import Path

#: Centre of the sky dome of MenuBackdrop (ellipsoid radii 190, 190, 115); the ground rings share it.
CENTRE = (0.0, 45.0)
#: Ground level under the courtyard and the paving: below the courtyard's bedding blocks (bottom -0.79).
FOOTPRINT_LEVEL = -0.9
#: Fortress footprint (x min, x max, y min, y max), paved outside the courtyard; the wasteland starts outside it.
FOOTPRINT = (-36.0, 36.0, -32.0, 58.5)
#: Courtyard paving of MenuCourtyard (x min, x max, y min, y max); no new paving there.
COURTYARD = (-26.0, 27.6, -29.9, 19.8)
#: Distance over which the terrain rises from the footprint level to its full relief.
FOOTPRINT_BLEND = 14.0
#: Radii of the ground rings around CENTRE; the crag ring starts at RIM_FOOT.
GROUND_RADII = (0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 78, 84, 90, 96, 103, 111, 120, 129, 138)
RIM_FOOT = 146.0
RIM_CREST = 163.0
RIM_BACK = 171.0
#: Angular segments of the rings (2.5 degrees).
SEGMENTS = 144
#: Lowest crest of the crags; the highest menu camera (settings flight) flies at height 20.5.
RIM_MIN_HEIGHT = 24.0
#: World size of one texture repeat on the ground and on the crags.
TEXTURE_METRES = 4.5
PAVING_MATERIAL = "MenuWetStone"
#: Wasteland ground from near the walls to far out: brightness steps down with the distance to the footprint.
GROUND_BANDS = ((0.0, "MenuWasteGroundNear"), (22.0, "MenuWasteGround"), (60.0, "MenuWasteGroundFar"))
ROCK_MATERIAL = "MenuWasteRock"
CRAG_MATERIAL = "MenuMountain"
VEIN_MATERIAL = "MenuEmberCrack"


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
    # Broad swells grow with the distance; near the fortress the ground stays low beside the walls.
    swell = min(1.0, distance / 60.0) * 3.0 * (0.5 + 0.5 * fbm(x * 0.012, y * 0.012, 11))
    return FOOTPRINT_LEVEL + blend * (relief + swell + 0.6)


def crest_height(angle):
    """Returns the crest height of the crag ring at a polar angle around CENTRE."""
    broad = 0.5 + 0.5 * fbm(math.cos(angle) * 2.6 + 9, math.sin(angle) * 2.6 + 4, 19)
    jagged = 0.5 + 0.5 * fbm(math.cos(angle) * 11 + 3, math.sin(angle) * 11 + 1, 23, 3)
    return RIM_MIN_HEIGHT + 7.0 * broad + 6.0 * jagged


def ground_material(x, y, rng):
    """Returns the wasteland material for a point; band edges are dithered over six metres."""
    distance = footprint_distance(x, y) + rng.uniform(-3.0, 3.0)
    name = GROUND_BANDS[0][1]
    for start, material in GROUND_BANDS:
        if distance >= start:
            name = material
    return name


class Geometry:
    """Collects triangles with one material and one (u, v) per corner."""

    def __init__(self):
        """Starts an empty triangle list."""
        self.vertices = []
        self.faces = []
        self.materials = []
        self.uvs = []

    def vertex(self, point):
        """Adds a vertex and returns its index."""
        self.vertices.append(tuple(point))
        return len(self.vertices) - 1

    def triangle(self, corners, material, uv_scale=TEXTURE_METRES, projection="top"):
        """Adds a triangle (vertex indices, counter-clockwise seen from its front) with planar texture coordinates."""
        self.faces.append(tuple(corners))
        self.materials.append(material)
        points = [self.vertices[i] for i in corners]
        if projection == "top":
            self.uvs.append(tuple((p[0] / uv_scale, p[1] / uv_scale) for p in points))
        else:
            self.uvs.append(tuple(((p[0] + p[1]) / uv_scale, p[2] / uv_scale) for p in points))

    def block(self, centre, size, turn, material, uv_scale=2.5):
        """Adds a closed box turned about z with its six faces outward."""
        cx, cy, cz = centre
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        cos_t, sin_t = math.cos(turn), math.sin(turn)
        corners = []
        for z in (cz - hz, cz + hz):
            for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
                corners.append(self.vertex((cx + x * cos_t - y * sin_t, cy + x * sin_t + y * cos_t, z)))
        quads = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
        for quad in quads:
            a, b, c, d = (corners[i] for i in quad)
            projection = "top" if quad in ((0, 3, 2, 1), (4, 5, 6, 7)) else "side"
            self.triangle((a, b, c), material, uv_scale, projection)
            self.triangle((a, c, d), material, uv_scale, projection)


def build_geometry(seed=5):
    """Returns (vertices, faces, face materials, face texture coordinates) of the ground.

    Faces are triangles (vertex index triples, counter-clockwise seen from outside); texture coordinates are
    one (u, v) triple per face corner.
    """
    rng = random.Random(seed)
    geometry = Geometry()
    _add_rings(rng, geometry)
    _add_paving(rng, geometry)
    _add_veins(rng, geometry)
    _add_ruins(rng, geometry)
    _add_rubble(rng, geometry)
    _add_spires(rng, geometry)
    return geometry.vertices, geometry.faces, geometry.materials, geometry.uvs


def _add_rings(rng, geometry):
    """Adds the polar ground rings and the crag ring (foot, flank, fractured crest, back)."""
    rings = []
    radii = list(GROUND_RADII) + [RIM_FOOT, (RIM_FOOT + RIM_CREST) * 0.5, RIM_CREST, RIM_BACK]
    for radius in radii:
        row = []
        for segment in range(SEGMENTS if radius > 0 else 1):
            angle = 2 * math.pi * segment / SEGMENTS
            jitter = 0.0 if radius == 0 else rng.uniform(-0.18, 0.18) * (2 * math.pi / SEGMENTS)
            r = radius + (rng.uniform(-1.8, 1.8) if 0 < radius < RIM_FOOT else 0.0)
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
            row.append(geometry.vertex((x, y, z)))
        rings.append(row)
    for ring in range(len(rings) - 1):
        inner, outer = rings[ring], rings[ring + 1]
        crag = radii[ring] >= RIM_FOOT
        for segment in range(SEGMENTS):
            following = (segment + 1) % SEGMENTS
            if len(inner) == 1:
                triangles = [(inner[0], outer[segment], outer[following])]
            else:
                a, b, c, d = inner[segment], outer[segment], outer[following], inner[following]
                # Alternate the diagonal so the ridges do not line up into radial streaks.
                triangles = [(a, b, c), (a, c, d)] if (segment + ring) % 2 else [(a, b, d), (b, c, d)]
            for triangle in triangles:
                if crag:
                    geometry.triangle(triangle, CRAG_MATERIAL, projection="side")
                else:
                    centre = [sum(geometry.vertices[i][k] for i in triangle) / 3 for k in range(2)]
                    geometry.triangle(triangle, ground_material(centre[0], centre[1], rng))


def _paved(x, y):
    """Returns True when a point of the footprint gets new paving (outside the courtyard of MenuCourtyard)."""
    inside = FOOTPRINT[0] <= x <= FOOTPRINT[1] and FOOTPRINT[2] <= y <= FOOTPRINT[3]
    courtyard = COURTYARD[0] < x < COURTYARD[1] and COURTYARD[2] < y < COURTYARD[3]
    return inside and not courtyard


def _add_paving(rng, geometry):
    """Adds wet flagstones like the courtyard over the footprint outside the courtyard: worn, tilted, some missing."""
    rows = int((FOOTPRINT[3] - FOOTPRINT[2]) / 1.75)
    for row in range(rows):
        y = FOOTPRINT[2] + 0.9 + row * 1.75
        columns = int((FOOTPRINT[1] - FOOTPRINT[0]) / 1.85)
        for column in range(columns):
            x = FOOTPRINT[0] + 0.95 + column * 1.85 + (0.9 if row % 2 else 0.0) + rng.uniform(-0.12, 0.12)
            if not _paved(x, y) or x > FOOTPRINT[1] - 0.9:
                continue
            if rng.random() < 0.07:
                continue
            top = -0.03 + rng.uniform(-0.09, 0.05)
            size = (1.66 + rng.uniform(-0.2, 0.05), 1.58 + rng.uniform(-0.2, 0.05), top + 0.55)
            turn = rng.uniform(-0.05, 0.05)
            # Every flagstone reaches down to the ground level, so none hangs above it where its neighbours are missing.
            size = (size[0], size[1], top - FOOTPRINT_LEVEL)
            geometry.block((x, y, top - size[2] / 2), size, turn, PAVING_MATERIAL, 3.3)


def _add_veins(rng, geometry):
    """Adds thin glowing ember veins on the wasteland near the fortress, following the ground."""
    for vein in range(26):
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(55, 95)
        x = CENTRE[0] + distance * math.cos(angle)
        y = CENTRE[1] + distance * math.sin(angle) * 0.85
        if footprint_distance(x, y) < 3.0:
            continue
        heading = rng.uniform(0, 2 * math.pi)
        for step in range(rng.randint(5, 10)):
            heading += rng.uniform(-0.6, 0.6)
            length = rng.uniform(1.2, 2.6)
            nx, ny = x + length * math.cos(heading), y + length * math.sin(heading)
            if footprint_distance(nx, ny) < 2.0:
                break
            width = rng.uniform(0.05, 0.13)
            ox, oy = -math.sin(heading) * width, math.cos(heading) * width
            quad = [geometry.vertex((px, py, ground_height(px, py) + 0.04))
                    for px, py in ((x - ox, y - oy), (nx - ox, ny - oy), (nx + ox, ny + oy), (x + ox, y + oy))]
            geometry.triangle((quad[0], quad[1], quad[2]), VEIN_MATERIAL)
            geometry.triangle((quad[0], quad[2], quad[3]), VEIN_MATERIAL)
            x, y = nx, ny


def _add_ruins(rng, geometry):
    """Adds the stumps of a fallen outer wall: short rows of squared blocks one to three courses high."""
    placed = 0
    attempts = 0
    while placed < 22 and attempts < 600:
        attempts += 1
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(50, 100)
        x = CENTRE[0] + distance * math.cos(angle)
        y = CENTRE[1] + distance * math.sin(angle)
        if footprint_distance(x, y) < 6.0:
            continue
        turn = angle + math.pi / 2 + rng.uniform(-0.25, 0.25)
        length = rng.randint(3, 6)
        for index in range(length):
            courses = rng.randint(1, 3) if index not in (0, length - 1) else 1
            for course in range(courses):
                along = (index - length / 2) * 1.35
                bx = x + along * math.cos(turn)
                by = y + along * math.sin(turn)
                base = ground_height(bx, by) - 0.25
                geometry.block((bx + rng.uniform(-0.08, 0.08), by + rng.uniform(-0.08, 0.08), base + 0.45 + course * 0.88),
                               (1.28, 1.6, 0.9), turn + rng.uniform(-0.06, 0.06), ROCK_MATERIAL)
        placed += 1


def _add_rubble(rng, geometry):
    """Adds fractured boulders and toppled blocks on the wasteland, dense near the walls and larger further out."""
    placed = 0
    attempts = 0
    while placed < 200 and attempts < 12000:
        attempts += 1
        near = placed < 160
        if placed < 80:
            # Close to the walls: a band up to 25 beyond the footprint.
            x = rng.uniform(FOOTPRINT[0] - 25, FOOTPRINT[1] + 25)
            y = rng.uniform(FOOTPRINT[2] - 25, FOOTPRINT[3] + 25)
            if footprint_distance(x, y) > 25:
                continue
        else:
            angle = rng.uniform(0, 2 * math.pi)
            distance = rng.uniform(40, 100) if near else rng.uniform(95, 130)
            x = CENTRE[0] + distance * math.cos(angle)
            y = CENTRE[1] + distance * math.sin(angle)
        size = rng.uniform(0.6, 2.4) if near else rng.uniform(2.5, 6.0)
        if footprint_distance(x, y) < size * 1.5 + 1.0:
            continue
        if math.hypot(x - CENTRE[0], y - CENTRE[1]) > RIM_FOOT - size * 2:
            continue
        _boulder(rng, geometry, x, y, size, block=placed % 5 == 0)
        placed += 1


def _boulder(rng, geometry, x, y, size, block):
    """Adds one closed fractured rock (or a squared fallen block) sunk into the ground."""
    if block:
        geometry.block((x, y, ground_height(x, y) + size * 0.2), (size * 1.3, size * 0.9, size * 0.8),
                       rng.uniform(0, math.pi), ROCK_MATERIAL)
        return
    sides = 7
    base = ground_height(x, y) - 0.25 * size
    rows = ((0.0, 1.0), (0.45, 1.08), (0.85, 0.72), (1.0, 0.35))
    height = size * rng.uniform(0.6, 1.0)
    stretch = rng.uniform(0.7, 1.3)
    turn = rng.uniform(0, math.pi)
    first = len(geometry.vertices)
    for level, spread in rows:
        for side in range(sides):
            angle = turn + 2 * math.pi * side / sides
            radius = size * spread * rng.uniform(0.78, 1.18)
            geometry.vertex((x + radius * math.cos(angle) * stretch, y + radius * math.sin(angle) / stretch,
                             base + height * level + rng.uniform(-0.08, 0.08) * size))
    top = geometry.vertex((x + rng.uniform(-0.2, 0.2) * size, y + rng.uniform(-0.2, 0.2) * size, base + height * 1.05))
    for row in range(len(rows) - 1):
        for side in range(sides):
            a = first + row * sides + side
            b = first + row * sides + (side + 1) % sides
            c = first + (row + 1) * sides + (side + 1) % sides
            d = first + (row + 1) * sides + side
            geometry.triangle((a, b, c), ROCK_MATERIAL, 2.5, "side")
            geometry.triangle((a, c, d), ROCK_MATERIAL, 2.5, "side")
    last = first + (len(rows) - 1) * sides
    for side in range(sides):
        geometry.triangle((last + side, last + (side + 1) % sides, top), ROCK_MATERIAL, 2.5, "side")
    for side in range(1, sides - 1):
        geometry.triangle((first, first + side + 1, first + side), ROCK_MATERIAL, 2.5, "side")


def _add_spires(rng, geometry):
    """Adds leaning rock spires on the crag crest so the ring reads as a jagged silhouette against the sky."""
    for index in range(46):
        angle = 2 * math.pi * (index + rng.uniform(-0.3, 0.3)) / 46
        radius = RIM_CREST + rng.uniform(-4.0, 2.0)
        x = CENTRE[0] + radius * math.cos(angle)
        y = CENTRE[1] + radius * math.sin(angle)
        base = crest_height(angle) * 0.8
        height = rng.uniform(7.0, 15.0)
        width = rng.uniform(2.0, 4.2)
        lean = (rng.uniform(-2.0, 2.0), rng.uniform(-2.0, 2.0))
        sides = 5
        first = len(geometry.vertices)
        for level, spread in ((0.0, 1.0), (0.55, 0.6)):
            for side in range(sides):
                a = 2 * math.pi * side / sides + rng.uniform(-0.25, 0.25)
                geometry.vertex((x + width * spread * math.cos(a) + lean[0] * level, y + width * spread * math.sin(a) + lean[1] * level,
                                 base + height * level))
        top = geometry.vertex((x + lean[0], y + lean[1], base + height))
        for side in range(sides):
            a, b = first + side, first + (side + 1) % sides
            c, d = first + sides + (side + 1) % sides, first + sides + side
            geometry.triangle((a, b, c), CRAG_MATERIAL, projection="side")
            geometry.triangle((a, c, d), CRAG_MATERIAL, projection="side")
            geometry.triangle((d, c, top), CRAG_MATERIAL, projection="side")


def main():
    """Builds the Blender source and the Ogre XML of the ground (run inside Blender in background mode)."""
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
    names = list(dict.fromkeys(face_materials))
    material_text = (repo / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
    images = {}
    for name in names:
        material = bpy.data.materials.new(name)
        configure_material(material, material_values(material_text, name), repo, images)
        mesh.materials.append(material)
    layer = mesh.uv_layers.new(name="UVMap")
    smooth = set(name for _, name in GROUND_BANDS)
    for polygon, material, corners in zip(mesh.polygons, face_materials, face_uvs):
        polygon.material_index = names.index(material)
        polygon.use_smooth = material in smooth
        for loop, uv in zip(polygon.loop_indices, corners):
            layer.data[loop].uv = uv
    obj = bpy.data.objects.new("MenuOuterGround", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["menu_source_family"] = "MenuBackdrop"
    bpy.ops.wm.save_as_mainfile(filepath=str(private / "MenuOuterGround.blend"))
    stats = exporter.export_mesh_xml(obj, None, str(private / "MenuOuterGround.mesh.xml"), None, smooth=False)
    print("OUTER_GROUND_DONE", len(vertices), len(faces), stats, flush=True)


if __name__ == "__main__":
    main()
