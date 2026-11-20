"""Build the in-game Moreya gate and the start screen signpost, export them and render review previews.

    MoreyaGate            in-game gate: the start screen gate (MenuGate family of menu_scene_models.py, same seed and
                          damage) scaled to the tile grid, with a dark passage behind the arch, without the portcullis
    MoreyaGatePortcullis  the iron grille of the same gate as its own mesh with the same origin, so the game can move
                          or hide it on its own when the gate opens
    MenuSignpost          wooden signpost for the start screen; its arrow board points along +X and its front face
                          (normal -Y, towards the menu camera) carries the material MenuSignpostBoard, whose texture
                          covers the whole board outline (u 0..1 from the back end to the arrow tip, v 0..1 bottom to
                          top); the rectangular lettering area is u 0..0.875

Gate: one tile is one unit; the gate is about 2.7 tiles wide (3.6 with its rubble and chains) and 3.6 high, the
origin is the middle of its footprint on the floor (z 0), the front with the skull crown faces -Y. The passage is
1.8 tiles wide. Opening by sinking the portcullis 2.2 units moves it fully below the floor tile.
Signpost: menu scene units (metres, like the menu gate); origin is the foot of the post, the board is 4 x 1 units
and its lower edge is 3.7 above the ground.

Run in Blender (5.x):
    blender --background --python moreya_raid_models.py -- <repo> <private output folder> [gate] [signpost]
It writes <name>.blend, <name>.mesh.xml and preview PNGs into the private folder, converts the meshes with
OgreXMLConverter (BUILD_DEPS_ROOT, else %USERPROFILE%/build-deps) into <repo>/models and writes the signpost wood
textures into <repo>/materials/textures/menu. Progress goes to <private>/moreya_raid_models.log.
After the signpost textures are rewritten, run tools/gen_menu_signpost_lettering.py again: the menu shows the
lettered copy of the board (MenuSignpostBoardLettered*.png) that it makes from the plain planks.
"""
import math
import os
import random
import re
import subprocess
import sys
import traceback
from pathlib import Path

import bpy
import bmesh
import numpy
from mathutils import Matrix, Vector

#: Scale from menu units to tiles for the in-game gate.
GATE_SCALE = 0.2
#: Ratio of the collapse decimation of the gate frame (the menu gate has about 38 000 triangles).
GATE_DECIMATE = 0.45
#: Board outline of the signpost in the XZ plane: back end, arrow shoulder, tip, lower and upper edge.
BOARD_BACK, BOARD_SHOULDER, BOARD_TIP = -0.5, 3.0, 3.5
BOARD_BOTTOM, BOARD_TOP = 3.7, 4.7
#: Front and back face of the board (the post centre is y 0).
BOARD_FRONT_Y, BOARD_BACK_Y = -0.36, -0.22

LOG = None


def log(text):
    """Writes one progress line to the log file of the run."""
    LOG.write(text + "\n")
    LOG.flush()


def material_block(text, name):
    """Returns the body of one material definition and the name of its parent material."""
    match = re.search(r"\bmaterial\s+" + re.escape(name) + r"\s*(?::\s*([\w/]+))?\s*\{", text)
    if match is None:
        raise ValueError("Missing material: " + name)
    depth = 1
    end = match.end()
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[match.end():end - 1], match.group(1)


def material_values(text, name):
    """Resolves colours, textures and the lighting flag of one material, including its Menu* parents."""
    block, parent = material_block(text, name)
    values = dict(material_values(text, parent)) if parent and not parent.startswith("RTSS") else {}
    for field in ("diffuse", "ambient", "emissive", "specular"):
        found = re.search(r"\b" + field + r"[ \t]+((?:[+-]?[\d.]+[ \t]*){3,5})", block)
        if found:
            values[field] = tuple(float(value) for value in found.group(1).split())
    if re.search(r"\blighting\s+off\b", block):
        values["unlit"] = True
    for filename in re.findall(r"\btexture\s+([\w]+\.png)", block):
        values["normal" if filename.endswith("Normal.png") else "texture"] = filename
    return values


def load_texture(repo, filename, images):
    """Loads one texture of the game once (menu folder first, then the main texture folder)."""
    if filename not in images:
        for folder in ("materials/textures/menu", "materials/textures"):
            path = Path(repo) / folder / filename
            if path.exists():
                image = bpy.data.images.load(str(path), check_existing=True)
                image.colorspace_settings.name = "Non-Color" if filename.endswith("Normal.png") else "sRGB"
                images[filename] = image
                break
        else:
            raise FileNotFoundError(filename)
    return images[filename]


def configure_preview_material(material, values, repo, images):
    """Gives one material the Eevee nodes of its game definition: texture times diffuse, normal map, emission."""
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    if values.get("unlit") or (values.get("diffuse", (1, 1, 1))[:3] == (0, 0, 0) and "emissive" in values):
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (*values.get("emissive", (0, 0, 0))[:3], 1)
        emission.inputs["Strength"].default_value = 1.5
        links.new(emission.outputs[0], output.inputs["Surface"])
        return
    colour = values.get("diffuse", values.get("ambient", (0.5, 0.5, 0.5)))[:3]
    surface = nodes.new("ShaderNodeBsdfPrincipled")
    rgb = nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = (*colour, 1)
    base = rgb.outputs[0]
    if values.get("texture"):
        image = nodes.new("ShaderNodeTexImage")
        image.image = load_texture(repo, values["texture"], images)
        multiply = nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1
        links.new(image.outputs["Color"], multiply.inputs[1])
        links.new(base, multiply.inputs[2])
        base = multiply.outputs[0]
    links.new(base, surface.inputs["Base Color"])
    specular = values.get("specular", (0, 0, 0, 1, 8))
    surface.inputs["Roughness"].default_value = min(1, math.sqrt(2 / (specular[-1] + 2)))
    if values.get("normal"):
        normal_image = nodes.new("ShaderNodeTexImage")
        normal_image.image = load_texture(repo, values["normal"], images)
        normal = nodes.new("ShaderNodeNormalMap")
        normal.inputs["Strength"].default_value = 0.8
        links.new(normal_image.outputs["Color"], normal.inputs["Color"])
        links.new(normal.outputs["Normal"], surface.inputs["Normal"])
    if max(values.get("emissive", (0, 0, 0))[:3]) > 0:
        surface.inputs["Emission Color"].default_value = (*values["emissive"][:3], 1)
        surface.inputs["Emission Strength"].default_value = 2.0
    links.new(surface.outputs[0], output.inputs["Surface"])


def material_text(repo):
    """Returns the menu material script together with the two material scripts of this tool."""
    folder = Path(repo) / "materials/scripts"
    return "\n".join((folder / name).read_text(encoding="utf-8")
                     for name in ("MenuScene.material", "MoreyaGate.material", "MenuSignpost.material"))


def reset_scene(models):
    """Starts an empty file that holds every menu material name the builders use."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for name, colour in models.COLOURS.items():
        bpy.data.materials.new(name).diffuse_color = (*colour, 1)
    bpy.data.materials.new("MenuWetStone").diffuse_color = (0.30, 0.29, 0.28, 1)
    bpy.context.preferences.filepaths.save_version = 0


def bake_modifiers(obj):
    """Applies every modifier of an object so later steps work on the evaluated surface."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), depsgraph=depsgraph)
    old = obj.data
    obj.modifiers.clear()
    obj.data = mesh
    bpy.data.meshes.remove(old)
    mesh.name = obj.name


def material_index(obj, name):
    """Returns the slot index of a material on an object, adding the slot when it is missing."""
    names = [slot.material.name for slot in obj.material_slots]
    if name not in names:
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        obj.data.materials.append(material)
        names.append(name)
    return names.index(name)


def add_passage(obj):
    """Closes the arch with a dark passage surface just inside the back face of the gate wall."""
    spring, radius = 6.0, 4.5
    outline = [(radius, 0.0)]
    outline.extend((radius * math.cos(i * math.pi / 28), spring + radius * math.sin(i * math.pi / 28)) for i in range(29))
    outline.append((-radius, 0.0))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.active
    index = material_index(obj, "MoreyaGateDepth")
    for y, reverse in ((3.30, False), (3.40, True)):
        points = [bm.verts.new((x, y, z)) for x, z in outline]
        face = bm.faces.new(list(reversed(points)) if reverse else points)
        face.material_index = index
        for loop in face.loops:
            loop[uv].uv = (loop.vert.co.x * 0.5, loop.vert.co.z * 0.5)
    bm.to_mesh(obj.data)
    bm.free()


def split_portcullis(obj):
    """Moves the iron grille inside the arch (bars, spikes and cross bars) into a new object."""
    iron = [slot.material.name for slot in obj.material_slots].index("MenuIron")
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    grille = [face for face in bm.faces if face.material_index == iron
              and 0.15 < face.calc_center_median().y < 0.65 and abs(face.calc_center_median().x) < 4.7
              and face.calc_center_median().z < 11.0]
    keep = [face for face in bm.faces if face not in set(grille)]
    portcullis = obj.copy()
    portcullis.data = obj.data.copy()
    portcullis.name = portcullis.data.name = "MoreyaGatePortcullis"
    bpy.context.scene.collection.objects.link(portcullis)
    bmesh.ops.delete(bm, geom=grille, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    other = bmesh.new()
    other.from_mesh(portcullis.data)
    other.faces.ensure_lookup_table()
    centres = [(face, face.calc_center_median()) for face in other.faces]
    drop = [face for face, centre in centres if not (face.material_index == iron and 0.15 < centre.y < 0.65
            and abs(centre.x) < 4.7 and centre.z < 11.0)]
    bmesh.ops.delete(other, geom=drop, context="FACES")
    other.to_mesh(portcullis.data)
    other.free()
    log("portcullis faces %d, frame faces %d" % (len(portcullis.data.polygons), len(obj.data.polygons)))
    return portcullis


def drop_unused_slots(obj):
    """Removes material slots no face uses, so every exported submesh has triangles."""
    used = {polygon.material_index for polygon in obj.data.polygons}
    for index in reversed(range(len(obj.material_slots))):
        if index not in used:
            obj.active_material_index = index
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.material_slot_remove()


def to_tile_grid(objects, centre):
    """Moves the footprint centre of the gate to the origin and scales it from menu units to tiles."""
    transform = Matrix.Scale(GATE_SCALE, 4) @ Matrix.Translation((-centre.x, -centre.y, 0.0))
    for obj in objects:
        obj.data.transform(transform)
        obj.data.update()


def build_gate(models, repo, private):
    """Builds the in-game gate and its portcullis from the menu gate family and returns both objects."""
    reset_scene(models)
    models.VARIANT_SEED, models.VARIANT_DAMAGE, models.VARIANT_NAME = 1000, 1.15, "MenuGate"
    gate = models.gate()
    gate.name = gate.data.name = "MoreyaGate"
    bake_modifiers(gate)
    portcullis = split_portcullis(gate)
    add_passage(gate)
    decimate = gate.modifiers.new("Tile scale detail", "DECIMATE")
    decimate.ratio = GATE_DECIMATE
    decimate.use_collapse_triangulate = True
    bake_modifiers(gate)
    for obj in (gate, portcullis):
        drop_unused_slots(obj)
    points = [vertex.co for vertex in gate.data.vertices]
    centre = Vector(((min(p.x for p in points) + max(p.x for p in points)) / 2,
                     (min(p.y for p in points) + max(p.y for p in points)) / 2, 0.0))
    to_tile_grid((gate, portcullis), centre)
    return gate, portcullis


def periodic_noise(rng, height, width, scale_u, scale_v):
    """Returns tileable smooth noise in -1..1 made by filtering white noise in frequency space."""
    white = rng.standard_normal((height, width))
    fv = numpy.fft.fftfreq(height)[:, None] * height
    fu = numpy.fft.fftfreq(width)[None, :] * width
    gain = numpy.exp(-((fu / scale_u) ** 2 + (fv / scale_v) ** 2))
    field = numpy.real(numpy.fft.ifft2(numpy.fft.fft2(white) * gain))
    field -= field.mean()
    return field / (numpy.abs(field).max() + 1e-9)


def save_png(path, rgb):
    """Writes an RGB float array (rows from top to bottom, values 0..1) as an 8-bit PNG."""
    height, width = rgb.shape[:2]
    image = bpy.data.images.new(Path(path).stem, width, height, alpha=False)
    rgba = numpy.ones((height, width, 4), dtype=numpy.float32)
    rgba[:, :, :3] = numpy.clip(rgb, 0, 1)
    image.pixels.foreach_set(rgba[::-1].ravel())
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def normal_map(heightfield, strength):
    """Converts a tileable height field into a tangent-space normal map (Y up, wrapped edges)."""
    du = (numpy.roll(heightfield, -1, axis=1) - numpy.roll(heightfield, 1, axis=1)) * strength
    dv = (numpy.roll(heightfield, 1, axis=0) - numpy.roll(heightfield, -1, axis=0)) * strength
    normal = numpy.dstack((-du, -dv, numpy.ones_like(heightfield)))
    normal /= numpy.linalg.norm(normal, axis=2, keepdims=True)
    return normal * 0.5 + 0.5


def wood_surface(rng, height, width, along_u):
    """Returns colour and height of weathered dark wood whose grain runs along u (else along v)."""
    # Frequency cut-offs: few waves along the grain, many across it.
    stretch = (8.0, 140.0) if along_u else (140.0, 8.0)
    streak = periodic_noise(rng, height, width, *stretch)
    fine = periodic_noise(rng, height, width, stretch[0] * 3, stretch[1] * 3)
    warp = periodic_noise(rng, height, width, 4, 4)
    across = (numpy.arange(height)[:, None] / height) if along_u else (numpy.arange(width)[None, :] / width)
    rings = numpy.sin(2 * math.pi * (9 * across + 0.9 * warp + 0.35 * streak)) * 0.5 + 0.5
    weather = periodic_noise(rng, height, width, 5, 5) * 0.5 + 0.5
    crack_noise = periodic_noise(rng, height, width, *[value * 2 for value in stretch])
    cracks = numpy.clip(1 - numpy.abs(crack_noise) * 22, 0, 1) * (weather > 0.55)
    dark = numpy.array((0.075, 0.052, 0.034))
    light = numpy.array((0.235, 0.165, 0.105))
    grey = numpy.array((0.20, 0.19, 0.17))
    tone = 0.30 + 0.42 * rings + 0.18 * fine
    colour = dark + (light - dark) * tone[:, :, None]
    colour = colour + (grey - colour) * (0.45 * numpy.clip(weather - 0.35, 0, 1))[:, :, None]
    colour *= (1 - 0.75 * cracks)[:, :, None]
    heightfield = 0.55 * rings + 0.25 * fine - 1.6 * cracks
    return colour, heightfield


def write_wood_textures(repo, private):
    """Writes the tileable post wood and the board planks (no lettering) with their normal maps."""
    rng = numpy.random.default_rng(7301)
    folder = Path(repo) / "materials/textures/menu"
    colour, heightfield = wood_surface(rng, 512, 512, along_u=False)
    save_png(folder / "MenuSignpostWood.png", colour)
    save_png(folder / "MenuSignpostWoodNormal.png", normal_map(heightfield, 1.6))
    height, width = 512, 2048
    colour, heightfield = wood_surface(rng, height, width, along_u=True)
    rows = numpy.arange(height)[:, None] / height
    columns = numpy.arange(width)[None, :] / width
    # Three planks: dark joints between them and worn, darker borders around the board.
    joint = numpy.zeros((height, width))
    for seam in (1 / 3, 2 / 3):
        joint = numpy.maximum(joint, numpy.clip(1 - numpy.abs(rows - seam) * height / 5.0, 0, 1) * numpy.ones_like(columns))
    border = numpy.clip(1 - numpy.minimum(numpy.minimum(rows, 1 - rows) * 14, 1), 0, 1)
    border = numpy.maximum(border, numpy.clip(1 - columns * 40, 0, 1))
    # Soot from the ember light below darkens the lower edge.
    soot = numpy.clip((0.35 - (1 - rows)) / 0.35, 0, 1) * (0.5 + 0.5 * periodic_noise(rng, height, width, 30, 6))
    colour *= (1 - 0.85 * joint)[:, :, None]
    colour *= (1 - 0.45 * border - 0.35 * soot)[:, :, None]
    heightfield = heightfield - 2.5 * joint - 0.4 * border
    save_png(folder / "MenuSignpostBoard.png", colour)
    save_png(folder / "MenuSignpostBoardNormal.png", normal_map(heightfield, 1.0))
    log("wood textures written")


class PartBuilder:
    """Collects faces with a material and a grain direction for the signpost and makes one mesh of them."""

    def __init__(self, name, seed):
        """Starts an empty part list with its own random sequence."""
        self.name = name
        self.vertices = []
        self.faces = []
        self.rng = random.Random(seed)

    def face(self, points, material, grain=(0, 0, 1), board=False):
        """Adds one polygon given by world points with its material, grain axis and board mapping flag."""
        start = len(self.vertices)
        self.vertices.extend(tuple(point) for point in points)
        self.faces.append((tuple(range(start, start + len(points))), material, Vector(grain), board))

    def solid(self, outline, axis, material, grain, front_board=False):
        """Extrudes a convex outline (list of world points of the back cap) along a vector into a closed solid."""
        back = [Vector(point) for point in outline]
        front = [point + Vector(axis) for point in back]
        count = len(back)
        normal = (back[1] - back[0]).cross(back[2] - back[1])
        if normal.dot(Vector(axis)) > 0:
            back.reverse()
            front.reverse()
        self.face(back, material, grain)
        self.face(list(reversed(front)), "MenuSignpostBoard" if front_board else material, grain, front_board)
        for index in range(count):
            following = (index + 1) % count
            self.face((back[index], back[following], front[following], front[index]), material, grain)

    def log_column(self, base, top, radius, top_radius, material, sides=9, rough=0.018):
        """Adds a slightly irregular many-sided timber or iron column between two points."""
        base, top = Vector(base), Vector(top)
        axis = (top - base).normalized()
        across = axis.cross(Vector((0, 1, 0)))
        if across.length < 0.01:
            across = axis.cross(Vector((1, 0, 0)))
        across.normalize()
        up = axis.cross(across).normalized()
        rings = []
        for centre, width in ((base, radius), (top, top_radius)):
            ring = []
            for index in range(sides):
                angle = index * 2 * math.pi / sides
                wobble = width + self.rng.uniform(-rough, rough)
                ring.append(centre + wobble * (across * math.cos(angle) + up * math.sin(angle)))
            rings.append(ring)
        grain = tuple(axis)
        self.face(list(reversed(rings[0])), material, grain)
        self.face(rings[1], material, grain)
        for index in range(sides):
            following = (index + 1) % sides
            self.face((rings[0][index], rings[0][following], rings[1][following], rings[1][index]), material, grain)

    def rock(self, centre, size, material="MenuRoughStone"):
        """Adds a faceted rough stone (a squashed, jittered icosphere) at the foot of the post."""
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        for vertex in bm.verts:
            vertex.co = Vector((vertex.co.x * size[0], vertex.co.y * size[1], vertex.co.z * size[2]))
            vertex.co += Vector([self.rng.uniform(-0.18, 0.18) * value for value in size])
            vertex.co += Vector(centre)
        for face in bm.faces:
            self.face([vertex.co.copy() for vertex in face.verts], material, (1, 0, 0))
        bm.free()

    def finish(self, materials):
        """Makes the mesh object: planar UVs along each face's grain, and 0..1 over the board outline for its face."""
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], [face[0] for face in self.faces])
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        for name in materials:
            mesh.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
        uv = mesh.uv_layers.new(name="UVMap")
        for polygon, (indices, material, grain, board) in zip(mesh.polygons, self.faces):
            polygon.material_index = materials.index(material)
            normal = polygon.normal
            along = grain - normal * grain.dot(normal)
            if along.length < 0.2:
                along = Vector((0, 0, 1)) if abs(normal.z) < 0.9 else Vector((1, 0, 0))
                along = along - normal * along.dot(normal)
            along.normalize()
            side = normal.cross(along).normalized()
            offset = self.rng.uniform(0, 1)
            for loop_index in polygon.loop_indices:
                point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                if board:
                    uv.data[loop_index].uv = ((point.x - BOARD_BACK) / (BOARD_TIP - BOARD_BACK),
                                              (point.z - BOARD_BOTTOM) / (BOARD_TOP - BOARD_BOTTOM))
                else:
                    uv.data[loop_index].uv = (point.dot(side) * 1.4 + offset, point.dot(along) * 0.7)
        return obj


def build_signpost():
    """Builds the signpost: leaning post, arrow board towards +X, brace, iron straps and nails, stones at its foot."""
    b = PartBuilder("MenuSignpost", 5203)
    wood, iron, rust = "MenuSignpostWood", "MenuIron", "MenuCorrodedIron"
    lean = Vector((-0.06, 0.03, 0.0))
    post_top = Vector((0.0, 0.0, 5.25)) + lean
    b.log_column((0, 0, -0.35), post_top, 0.21, 0.18, wood, sides=10, rough=0.022)
    b.log_column(post_top, post_top + Vector((0.0, 0.0, 0.30)), 0.20, 0.0, rust, sides=10, rough=0.0)
    # The arrow board: back end, upper shoulder, tip, lower shoulder; front face towards -Y.
    board = [(BOARD_BACK, BOARD_BOTTOM), (BOARD_SHOULDER, BOARD_BOTTOM), (BOARD_TIP, (BOARD_BOTTOM + BOARD_TOP) / 2),
             (BOARD_SHOULDER, BOARD_TOP), (BOARD_BACK, BOARD_TOP)]
    b.solid([(x, BOARD_BACK_Y, z) for x, z in board], (0, BOARD_FRONT_Y - BOARD_BACK_Y, 0), wood, (1, 0, 0),
            front_board=True)
    # A diagonal brace under the board and a short cleat behind it carry the long arm.
    b.log_column((0.05, -0.12, 2.55), (1.75, -0.28, BOARD_BOTTOM + 0.02), 0.075, 0.065, wood, sides=7)
    b.solid([(-0.12, -0.21, 3.55), (0.12, -0.21, 3.55), (0.12, -0.21, 4.85), (-0.12, -0.21, 4.85)],
            (0, 0.14, 0), wood, (0, 0, 1))
    # Two iron straps wrap the board and the post; nails hold the board ends.
    for x in (-0.24, 0.24):
        b.solid([(x - 0.045, BOARD_FRONT_Y - 0.018, BOARD_BOTTOM - 0.05), (x + 0.045, BOARD_FRONT_Y - 0.018,
                 BOARD_BOTTOM - 0.05), (x + 0.045, BOARD_FRONT_Y - 0.018, BOARD_TOP + 0.05),
                 (x - 0.045, BOARD_FRONT_Y - 0.018, BOARD_TOP + 0.05)], (0, 0.40, 0), rust, (0, 0, 1))
    for x, z in ((-0.36, 3.85), (-0.36, 4.55), (2.82, 3.85), (2.82, 4.55), (1.20, 3.83), (1.20, 4.57)):
        b.log_column((x, BOARD_FRONT_Y + 0.01, z), (x, BOARD_FRONT_Y - 0.035, z), 0.032, 0.026, iron, sides=6, rough=0)
    # Stones piled around the foot of the post.
    for angle, distance, size in ((0.3, 0.42, (0.30, 0.24, 0.20)), (1.6, 0.46, (0.26, 0.30, 0.18)),
                                  (2.9, 0.40, (0.34, 0.26, 0.22)), (4.3, 0.44, (0.24, 0.22, 0.16)),
                                  (5.4, 0.38, (0.22, 0.26, 0.24)), (0.95, 0.70, (0.16, 0.14, 0.10))):
        b.rock((distance * math.cos(angle), distance * math.sin(angle), size[2] * 0.35), size)
    return b.finish([wood, "MenuSignpostBoard", rust, iron, "MenuRoughStone"])


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
    stats = exporter.export_mesh_xml(obj, None, str(Path(private) / (obj.name + ".mesh.xml")), None, smooth=False)
    log("%s %s" % (obj.name, stats))
    convert(repo, private, obj.name)


def setup_render(scene, resolution):
    """Sets Eevee, a near-black world and the filmic view used by the review previews."""
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Night")
    scene.world.use_nodes = True
    background = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (0.006, 0.006, 0.008, 1)
    background.inputs["Strength"].default_value = 1.0
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        pass
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 48


def add_light(scene, name, kind, location, colour, energy, size=0.5):
    """Adds one coloured light to the preview scene."""
    data = bpy.data.lights.new(name, kind)
    data.color = colour
    data.energy = energy
    if hasattr(data, "shadow_soft_size"):
        data.shadow_soft_size = size
    light = bpy.data.objects.new(name, data)
    light.location = location
    scene.collection.objects.link(light)
    return light


def add_floor(scene, size, material):
    """Adds a square ground plane with a stone material under the previewed model."""
    mesh = bpy.data.meshes.new("Floor")
    half = size / 2
    mesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        point = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (point.x * 0.5, point.y * 0.5)
    mesh.materials.append(bpy.data.materials.get(material) or bpy.data.materials.new(material))
    floor = bpy.data.objects.new("Floor", mesh)
    scene.collection.objects.link(floor)
    return floor


def shoot(scene, camera, target, elevation, azimuth, distance, lens, path):
    """Points the camera at a target from an elevation, azimuth and distance and renders one PNG."""
    e, a = math.radians(elevation), math.radians(azimuth)
    camera.location = Vector(target) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * distance
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = lens
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log("rendered " + str(path))


def preview(repo, private, prefix, views, lights, floor_size, floor_material):
    """Configures every material from the game scripts, lights the model as the style guide asks and renders views."""
    scene = bpy.context.scene
    setup_render(scene, (1280, 720))
    text = material_text(repo)
    images = {}
    add_floor(scene, floor_size, floor_material)
    for material in bpy.data.materials:
        if material.users:
            configure_preview_material(material, material_values(text, material.name), repo, images)
    for light in lights:
        add_light(scene, *light)
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    for suffix, target, elevation, azimuth, distance, lens in views:
        shoot(scene, camera, target, elevation, azimuth, distance, lens, Path(private) / ("%s_%s.png" % (prefix, suffix)))


def run_gate(models, exporter, repo, private):
    """Builds, saves, exports and previews the in-game gate and its portcullis."""
    gate, portcullis = build_gate(models, repo, private)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(private) / "MoreyaGate.blend"))
    export(exporter, repo, private, gate)
    export(exporter, repo, private, portcullis)
    # Ember light from below in front, a weak green glow of Moreya's power from inside the passage, dim fill.
    lights = (("EmberLeft", "POINT", (-1.2, -1.6, 0.25), (1.0, 0.36, 0.08), 60.0, 0.3),
              ("EmberRight", "POINT", (1.3, -1.4, 0.25), (1.0, 0.32, 0.06), 55.0, 0.3),
              ("MoreyaGreen", "POINT", (0.0, 0.2, 1.0), (0.15, 1.0, 0.25), 12.0, 0.4),
              ("Fill", "SUN", (0, 0, 10), (0.55, 0.6, 0.75), 0.35, 1.0))
    views = (("game", (0, 0, 1.3), 52.0, 30.0, 9.5, 40), ("front", (0, 0, 1.7), 12.0, 0.0, 9.0, 42),
             ("open", (0, 0, 1.3), 52.0, -30.0, 9.5, 40))
    preview_gate(repo, private, lights, views[:2])
    portcullis.location.z = -2.2
    preview_gate(repo, private, lights, views[2:], prepared=True)


def preview_gate(repo, private, lights, views, prepared=False):
    """Renders gate views; the first call sets up the scene, later calls only render with the current poses."""
    if not prepared:
        preview(repo, private, "MoreyaGate_preview", views, lights, 12, "MenuDarkStone")
        return
    scene = bpy.context.scene
    for suffix, target, elevation, azimuth, distance, lens in views:
        shoot(scene, scene.camera, target, elevation, azimuth, distance, lens,
              Path(private) / ("MoreyaGate_preview_%s.png" % suffix))


def run_signpost(models, exporter, repo, private):
    """Writes the wood textures, builds, saves, exports and previews the signpost."""
    reset_scene(models)
    write_wood_textures(repo, private)
    signpost = build_signpost()
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(private) / "MenuSignpost.blend"))
    export(exporter, repo, private, signpost)
    lights = (("EmberLow", "POINT", (1.2, -2.6, 0.4), (1.0, 0.35, 0.07), 900.0, 0.4),
              ("EmberSide", "POINT", (-2.0, -1.5, 1.0), (1.0, 0.30, 0.05), 300.0, 0.4),
              ("MoreyaGreen", "POINT", (3.5, 2.0, 5.5), (0.15, 1.0, 0.25), 250.0, 0.6),
              ("Fill", "SUN", (0, 0, 10), (0.55, 0.6, 0.75), 0.4, 1.0))
    views = (("front", (1.4, 0, 3.0), 8.0, 0.0, 14.0, 45), ("side", (1.4, 0, 3.0), 18.0, 35.0, 14.0, 45))
    preview(repo, private, "MenuSignpost_preview", views, lights, 14, "MenuStone")


def main():
    """Runs the requested builds (both when none is named) and records the result in the log."""
    global LOG
    arguments = sys.argv[sys.argv.index("--") + 1:]
    repo, private = Path(arguments[0]), Path(arguments[1])
    wanted = set(arguments[2:]) or {"gate", "signpost"}
    private.mkdir(parents=True, exist_ok=True)
    LOG = open(private / "moreya_raid_models.log", "w", encoding="utf-8")
    try:
        sys.path.insert(0, str(repo / "tools/blender-assets"))
        import menu_scene_models as models
        import odp_ogre_io as exporter
        if "gate" in wanted:
            run_gate(models, exporter, repo, private)
        if "signpost" in wanted:
            run_signpost(models, exporter, repo, private)
        log("finished")
    except Exception:
        LOG.write(traceback.format_exc())
        log("failed")
    finally:
        LOG.close()


if __name__ == "__main__":
    main()
