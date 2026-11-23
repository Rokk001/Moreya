#!/usr/bin/env python3
"""Render the stone campaign table of the main menu standing on the hall floor, seen from above (Blender script).

The clickable campaign map shows the carved map as the top of the stone table in the campaign hall: the map ends at
the table edge and the floor of the hall lies around the table. This script renders that view from the meshes of the
menu scene, so table edge and floor are those of the game: the stone table (models/MenuMapTableStone.mesh, placed
like CampaignStoneTable in config/mainmenuscene.cfg) and the floor it stands on (the floor of the campaign hall,
models/MenuCampaignHallOpen.mesh, up to FLOOR_HEIGHT, and below it the courtyard paving, models/MenuCourtyard.mesh,
and the ground, models/MenuOuterGround.mesh), with the menu textures and the diffuse colours of
materials/scripts/MenuScene.material. The camera is orthographic and tilted towards the front of the table by TILT
degrees (about the pitch of the campaign camera of the menu), so the front face of the top slab and the trestles show
below the table top. So that the table body reads on every side, the render draws the table body (every part but the
map plane) BODY_GROW wider than the map plane: the stone rim of the top slab shows round the map on all four sides.
The dark surface materials (moss, lichen, water stains) are lifted by SURFACE_LIFT of the stone colour, as the lights
of the hall show them in the game. tools/gen_campaign_map_art.py stretches the render back so that the table top is the
exact carved map rectangle of the full screen map and lays the carved map itself over it.

    blender --background --python tools/render_campaign_map_table.py -- [<repo>] [<output png>]

The output (default: moreya_map_table_render.png in $ODP_ASSETS_SRC/gui/campaign-map-carved) is an asset source;
next to it a JSON file of the same name gives the pixel positions of the four corners of the map plane in the render.
The meshes are read through OgreXMLConverter (OGRE_XML_CONVERTER, else the converter of the build dependencies).
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

#: Place of the stone table in the menu scene (CampaignStoneTable) and the floor window rendered around it.
TABLE_OFFSET = (0.0, 22.0, 0.0)
FLOOR_WINDOW = (-7.5, 7.5, 16.0, 28.0)
#: Highest point of a triangle of the campaign hall that still belongs to its floor (walls and roof are left out).
FLOOR_HEIGHT = 0.6
#: Rim of the table body round the map plane in the render (mesh units on every side of x and y).
BODY_GROW = 0.11
#: Share of the stone colour added to the dark surface materials.
SURFACE_LIFT = 0.32
DARK_SURFACES = ("MenuMoss", "MenuLichen", "MenuWaterStain")
#: Tilt of the camera towards the front of the table (degrees from straight down), its pixels per mesh unit (the
#: carved map: 1752 map pixels over the 6.15 units of the map plane) and the render size.
TILT = 29.5
PIXELS_PER_UNIT = 1752.0 / 6.15
RENDER_SIZE = (2600, 1800)
SAMPLES = 96
#: Texture and diffuse colour of every material of the two meshes (MenuScene.material); a material not listed is
#: drawn like MenuStone.
MATERIALS = {
    "MenuStone": ("MenuFortressStone.png", (0.85, 0.85, 0.85)),
    "MenuDarkStone": ("MenuFortressStone.png", (0.48, 0.50, 0.52)),
    "MenuCarvedStone": ("MenuFortressStone.png", (0.80, 0.82, 0.84)),
    "MenuRoughStone": ("MenuFortressStone.png", (0.78, 0.80, 0.82)),
    "MenuChippedStone": ("MenuFortressStone.png", (0.83, 0.83, 0.77)),
    "MenuMoss": ("MenuFortressStone.png", (0.052, 0.052, 0.032)),
    "MenuLichen": ("MenuFortressStone.png", (0.08, 0.07, 0.05)),
    "MenuWaterStain": ("MenuFortressStone.png", (0.050, 0.045, 0.040)),
    "MenuWetStone": ("MenuWetPaving.png", (0.92, 0.92, 0.92)),
    "MenuPuddle": ("MenuWetPaving.png", (0.55, 0.55, 0.52)),
    "MenuParchment": ("MenuFortressStone.png", (0.62, 0.62, 0.62)),
    "MenuWasteGroundNear": ("MenuFortressStone.png", (0.55, 0.50, 0.45)),
    "MenuWasteGround": ("MenuFortressStone.png", (0.38, 0.35, 0.32)),
    "MenuBlack": (None, (0.01, 0.01, 0.01)),
    "MenuCampaignMap": ("MenuCampaignMap.png", (1.0, 1.0, 1.0)),
}
#: Light of the hall as in the menu scene: the point lights over the front of the table (HallFire and GateBacklight of
#: config/mainmenuscene.cfg: name, position, colour) with the power given here, a weak warm light from the top left (as
#: the light of the carved map) and a dim ambient.
FIRES = (
    ("HallFire", (0.0, 20.0, 5.8), (1.0, 0.36 / 1.3, 0.07 / 1.3), 2600.0),
    ("GateBacklight", (0.0, 16.2, 4.2), (1.0, 0.36 / 2.7, 0.024 / 2.7), 1500.0),
)
FIRE_RADIUS = 0.4
SUN_DIRECTION = (-0.5, 0.55, 0.67)
SUN_COLOUR = (1.0, 0.72, 0.52)
SUN_STRENGTH = 0.6
AMBIENT_COLOUR = (0.30, 0.22, 0.18)
AMBIENT_STRENGTH = 0.35


def converter_path():
    """Returns the path of OgreXMLConverter."""
    configured = os.environ.get("OGRE_XML_CONVERTER")
    if configured:
        return configured
    root = os.environ.get("BUILD_DEPS_ROOT", os.path.join(os.path.expanduser("~"), "build-deps"))
    return os.path.join(root, "install", "bin", "OgreXMLConverter.exe")


def vertex_buffers(geometry):
    """Returns (positions, texture coordinates) of a sharedgeometry or geometry element."""
    positions = []
    coordinates = []
    for buffer in geometry.findall("vertexbuffer"):
        if buffer.get("positions") == "true":
            positions = [tuple(float(vertex.find("position").get(axis)) for axis in "xyz")
                         for vertex in buffer.findall("vertex")]
        if buffer.get("texture_coords") not in (None, "0"):
            coordinates = [(float(vertex.find("texcoord").get("u")), float(vertex.find("texcoord").get("v")))
                           for vertex in buffer.findall("vertex")]
    return positions, coordinates


def load_mesh(mesh_path, work):
    """Converts an Ogre mesh to XML and returns [(material, positions, coordinates, triangles)] of its submeshes."""
    target = os.path.join(work, os.path.basename(mesh_path) + ".xml")
    subprocess.run([converter_path(), mesh_path, target], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    root = ElementTree.parse(target).getroot()
    shared = root.find("sharedgeometry")
    shared_buffers = vertex_buffers(shared) if shared is not None else ([], [])
    result = []
    for submesh in root.find("submeshes"):
        geometry = submesh.find("geometry")
        positions, coordinates = vertex_buffers(geometry) if geometry is not None else shared_buffers
        triangles = [tuple(int(face.get(key)) for key in ("v1", "v2", "v3")) for face in submesh.find("faces")]
        result.append((submesh.get("material"), positions, coordinates, triangles))
    return result


def material_for(name, textures):
    """Returns the Blender material of a menu material: its texture times its diffuse colour."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    texture, colour = MATERIALS.get(name, MATERIALS["MenuStone"])
    if name in DARK_SURFACES:
        stone = MATERIALS["MenuStone"][1]
        colour = tuple(colour[channel] + SURFACE_LIFT * stone[channel] for channel in range(3))
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Roughness"].default_value = 0.9
    if texture is None:
        shader.inputs["Base Color"].default_value = colour + (1.0,)
        return material
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = bpy.data.images.load(os.path.join(textures, texture), check_existing=True)
    if texture == "MenuCampaignMap.png":
        image_node.extension = "EXTEND"
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    links = material.node_tree.links
    links.new(image_node.outputs["Color"], tint.inputs[6])
    tint.inputs[7].default_value = colour + (1.0,)
    links.new(tint.outputs[2], shader.inputs["Base Color"])
    return material


def build_object(name, submeshes, offset, textures, window=None, max_height=None):
    """Creates one Blender object of the submeshes, moved by offset; with a window (x0, x1, y0, y1) only the
    triangles that reach into it are kept, with max_height only the triangles that stay below it. Returns the object
    and its materials."""
    vertices = []
    faces = []
    face_materials = []
    face_coordinates = []
    materials = []
    for material_name, positions, coordinates, triangles in submeshes:
        material = material_for(material_name, textures)
        if material not in materials:
            materials.append(material)
        index = materials.index(material)
        for triangle in triangles:
            points = [tuple(positions[i][axis] + offset[axis] for axis in range(3)) for i in triangle]
            if window is not None:
                low_x = min(point[0] for point in points)
                high_x = max(point[0] for point in points)
                low_y = min(point[1] for point in points)
                high_y = max(point[1] for point in points)
                if high_x < window[0] or low_x > window[1] or high_y < window[2] or low_y > window[3]:
                    continue
            if max_height is not None and max(point[2] for point in points) > max_height:
                continue
            base = len(vertices)
            vertices.extend(points)
            faces.append((base, base + 1, base + 2))
            face_materials.append(index)
            face_coordinates.append([coordinates[i] if coordinates else (0.0, 0.0) for i in triangle])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for material in materials:
        mesh.materials.append(material)
    layer = mesh.uv_layers.new(name="UVMap")
    for polygon, index, uvs in zip(mesh.polygons, face_materials, face_coordinates):
        polygon.material_index = index
        polygon.use_smooth = True
        for loop, uv in zip(polygon.loop_indices, uvs):
            layer.data[loop].uv = (uv[0], 1.0 - uv[1])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj, materials


def grown_table(submeshes):
    """Returns the submeshes of the table with every part but the map plane widened by BODY_GROW on every side
    (positions scaled in x and y about the centre of the map plane), so the table body shows round the map."""
    corners = map_plane_corners(submeshes, (0.0, 0.0, 0.0))
    half_x = max(abs(corner.x) for corner in corners)
    half_y = max(abs(corner.y) for corner in corners)
    scale_x = (half_x + BODY_GROW) / half_x
    scale_y = (half_y + BODY_GROW) / half_y
    result = []
    for material_name, positions, coordinates, triangles in submeshes:
        if material_name != "MenuCampaignMap":
            positions = [(point[0] * scale_x, point[1] * scale_y, point[2]) for point in positions]
        result.append((material_name, positions, coordinates, triangles))
    return result


def map_plane_corners(submeshes, offset):
    """Returns the four corners of the map plane (material MenuCampaignMap) in scene coordinates."""
    for material_name, positions, _, triangles in submeshes:
        if material_name == "MenuCampaignMap":
            used = sorted(set(i for triangle in triangles for i in triangle))
            return [Vector(tuple(positions[i][axis] + offset[axis] for axis in range(3))) for i in used]
    raise ValueError("the table has no map plane")


def main():
    """Builds the scene, renders it and writes the render and the corners of the map plane."""
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(arguments[0] if arguments else os.path.join(here, ".."))
    sources = os.environ.get("ODP_ASSETS_SRC", os.path.join(repo, "assets-src"))
    output = arguments[1] if len(arguments) > 1 else os.path.join(sources, "gui", "campaign-map-carved",
                                                                   "moreya_map_table_render.png")
    textures = os.path.join(repo, "materials", "textures", "menu")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    work = tempfile.mkdtemp()
    table = load_mesh(os.path.join(repo, "models", "MenuMapTableStone.mesh"), work)
    build_object("StoneTable", grown_table(table), TABLE_OFFSET, textures)
    hall = load_mesh(os.path.join(repo, "models", "MenuCampaignHallOpen.mesh"), work)
    build_object("HallFloor", hall, TABLE_OFFSET, textures, FLOOR_WINDOW, FLOOR_HEIGHT)
    for floor_mesh in ("MenuCourtyard.mesh", "MenuOuterGround.mesh"):
        floor = load_mesh(os.path.join(repo, "models", floor_mesh), work)
        build_object(floor_mesh, floor, (0.0, 0.0, 0.0), textures, FLOOR_WINDOW)
    corners = map_plane_corners(table, TABLE_OFFSET)
    centre = sum(corners, Vector()) / len(corners)
    # Camera: orthographic, tilted about x towards the front of the table, aimed at the centre of the map plane
    camera_data = bpy.data.cameras.new("MapCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = RENDER_SIZE[0] / PIXELS_PER_UNIT
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("MapCamera", camera_data)
    scene.collection.objects.link(camera)
    tilt = math.radians(TILT)
    camera.rotation_euler = (tilt, 0.0, 0.0)
    camera.location = centre - Vector((0.0, math.sin(tilt), -math.cos(tilt))) * 30.0
    scene.camera = camera
    # Light: the fires over the front of the table, the weak light from the top left and the ambient of the hall
    for name, position, colour, power in FIRES:
        fire_data = bpy.data.lights.new(name, "POINT")
        fire_data.color = colour
        fire_data.energy = power
        fire_data.shadow_soft_size = FIRE_RADIUS
        fire = bpy.data.objects.new(name, fire_data)
        scene.collection.objects.link(fire)
        fire.location = position
    sun_data = bpy.data.lights.new("TopLeft", "SUN")
    sun_data.color = SUN_COLOUR
    sun_data.energy = SUN_STRENGTH
    sun_data.angle = math.radians(12.0)
    sun = bpy.data.objects.new("TopLeft", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(SUN_DIRECTION).to_track_quat("Z", "Y").to_euler()
    world = bpy.data.worlds.new("Hall")
    world.use_nodes = True
    background = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = AMBIENT_COLOUR + (1.0,)
    background.inputs["Strength"].default_value = AMBIENT_STRENGTH
    scene.world = world
    # Render
    try:
        scene.render.engine = "CYCLES"
    except TypeError:
        pass
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.seed = 1
    scene.render.resolution_x = RENDER_SIZE[0]
    scene.render.resolution_y = RENDER_SIZE[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = output
    os.makedirs(os.path.dirname(output), exist_ok=True)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)
    pixels = []
    for corner in corners:
        projected = world_to_camera_view(scene, camera, corner)
        pixels.append([projected.x * RENDER_SIZE[0], (1.0 - projected.y) * RENDER_SIZE[1], corner.x, corner.y])
    with open(os.path.splitext(output)[0] + ".json", "w", encoding="utf-8") as target:
        json.dump({"tilt": TILT, "map_plane_corners": pixels}, target, indent=2)


main()
