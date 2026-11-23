#!/usr/bin/env python3
"""Render the stone campaign table of the main menu standing on the hall floor, seen from above (Blender script).

The clickable campaign map shows the stone table of the campaign hall, the map carved into its top: the map ends at
the table edge and the floor of the hall lies around the table. This script renders that view from the meshes of the
menu scene: the stone table (models/MenuMapTableStone.mesh, placed like CampaignStoneTable in
config/mainmenuscene.cfg) and the floor of the campaign hall (the MenuHallFloor faces of
models/MenuCampaignHallOpen.mesh), continued by a floor plane of the same flagstones (FLOOR_PLANE, the same planar
texture coordinates) where the hall floor ends, so the floor is one dungeon floor all round; walls, wall tops and the
courtyard are left out. Textures and diffuse colours are those of materials/scripts/MenuScene.material.

The camera is a perspective camera CAMERA_DISTANCE in front of and above the centre of the map plane, tilted towards
the front of the table by TILT degrees, so the table shows as a solid stone table with length, width and height (the
front side of the thick top slab, the trestles standing on the floor, the shadow of the slab) and the floor recedes:
its flagstones get smaller towards the back and the light of the fires falls off into the distance. The dark surface materials (moss, lichen, water stains) are
lifted by SURFACE_LIFT of the stone colour. The slab is the stone of the carved map (MenuTableStone) and its own top
faces carry the carved map texture (materials/textures/menu/MenuCampaignMap.png, tools/menu_table_top_map.py, as in the
game), whose carving runs out into the slab along the cut-off corners: one top surface with one edge, nothing laid over
it. Table and floor share the light of
the hall: the fires over the front of the table, a weak light from the top left and the ambient of the hall.
The render is the full screen map at RENDER_SCALE times its size; the shift of the camera puts the map plane where the
carved map frame of the full screen map lies (SHIFT_Y), and tools/gen_campaign_map_art.py maps the places of the map
description onto the map plane seen in perspective.

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
FLOOR_WINDOW = (-12.0, 12.0, 14.0, 34.0)
#: Height above which a triangle of the campaign hall belongs to its roof, which lies above the camera and is left out.
ROOF_HEIGHT = 7.0
#: The camera: tilt towards the front of the table (degrees from straight down), distance from the centre of the map
#: plane, vertical field of view (degrees), vertical shift of the picture (share of its width, the map plane below the
#: middle as the carved map frame of the full screen map), the size of the full screen map and how many times larger
#: the render is (so the map stays sharp when it is scaled down).
TILT = 45.0
CAMERA_DISTANCE = 8.0
FOV_Y = 35.0
SHIFT_Y = 0.042
MAP_SIZE = (2560, 1600)
RENDER_SCALE = 1.5
RENDER_SIZE = (int(MAP_SIZE[0] * RENDER_SCALE), int(MAP_SIZE[1] * RENDER_SCALE))
#: Share of the stone colour added to the dark surface materials.
SURFACE_LIFT = 0.32
DARK_SURFACES = ("MenuMoss", "MenuLichen", "MenuWaterStain")
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
    "MenuHallFloor": ("MenuHallFloor.png", (0.80, 0.80, 0.80)),
    "MenuHallWall": ("MenuHallWall.png", (0.80, 0.80, 0.80)),
    "MenuTableStone": ("MenuTableStone.png", (1.0, 1.0, 1.0)),
    "MenuBlack": (None, (0.01, 0.01, 0.01)),
    "MenuCampaignMap": ("MenuCampaignMap.png", (1.0, 1.0, 1.0)),
}
#: Normal maps of the textures (the relief the menu materials show with RTSS normal mapping).
NORMAL_MAPS = {
    "MenuFortressStone.png": "MenuFortressStoneNormal.png",
    "MenuTableStone.png": "MenuFortressStoneNormal.png",
    "MenuWetPaving.png": "MenuWetPavingNormal.png",
    "MenuHallFloor.png": "MenuHallFloorNormal.png",
    "MenuHallWall.png": "MenuHallWallNormal.png",
}
NORMAL_STRENGTH = 1.0
#: The floor plane under the hall floor: its height, half its size (mesh units) and the size of one tile of its
#: flagstones (tools/menu_hall_floor_walls.py: FLOOR_TILE).
FLOOR_PLANE = (-0.12, 30.0, 4.0)
#: Light of the hall: the point lights over the front of the table at the places of HallFire and GateBacklight of
#: config/mainmenuscene.cfg (name, position, colour, power), in a milder warm colour than in the game so the carved
#: stone of the map keeps its colour, a weak warm light from the top left (as the light of the carved map) and a dim
#: ambient.
FIRES = (
    ("HallFire", (0.0, 20.0, 5.8), (1.0, 0.72, 0.52), 1400.0),
    ("GateBacklight", (0.0, 16.2, 4.2), (1.0, 0.62, 0.42), 700.0),
)
FIRE_RADIUS = 0.4
SUN_DIRECTION = (-0.5, 0.55, 0.67)
SUN_COLOUR = (1.0, 0.72, 0.52)
SUN_STRENGTH = 0.9
AMBIENT_COLOUR = (0.30, 0.22, 0.18)
AMBIENT_STRENGTH = 0.18


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
    links = material.node_tree.links
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    links.new(image_node.outputs["Color"], tint.inputs[6])
    tint.inputs[7].default_value = colour + (1.0,)
    links.new(tint.outputs[2], shader.inputs["Base Color"])
    if texture in NORMAL_MAPS:
        normal_image = nodes.new("ShaderNodeTexImage")
        normal_image.image = bpy.data.images.load(os.path.join(textures, NORMAL_MAPS[texture]), check_existing=True)
        normal_image.image.colorspace_settings.is_data = True
        normal_node = nodes.new("ShaderNodeNormalMap")
        normal_node.inputs["Strength"].default_value = NORMAL_STRENGTH
        links.new(normal_image.outputs["Color"], normal_node.inputs["Color"])
        links.new(normal_node.outputs["Normal"], shader.inputs["Normal"])
    return material


def build_object(name, submeshes, offset, textures, window=None, roof_height=None):
    """Creates one Blender object of the submeshes, moved by offset; with a window (x0, x1, y0, y1) only the
    triangles that reach into it are kept, with roof_height the triangles lying wholly above it are left out. Returns the object
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
            if roof_height is not None and min(point[2] for point in points) > roof_height:
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


def map_plane_corners(submeshes, offset):
    """Returns the vertices of the carved map (material MenuCampaignMap, the faces of the slab top) in scene
    coordinates."""
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
    build_object("StoneTable", table, TABLE_OFFSET, textures)
    hall = load_mesh(os.path.join(repo, "models", "MenuCampaignHallOpen.mesh"), work)
    hall_floor = [submesh for submesh in hall if submesh[0] == "MenuHallFloor"]
    build_object("HallFloor", hall_floor, TABLE_OFFSET, textures, FLOOR_WINDOW, ROOF_HEIGHT)
    height, half, tile = FLOOR_PLANE
    plane_points = [(-half, -half, height), (half, -half, height), (half, half, height), (-half, half, height)]
    plane_coordinates = [(x / tile, -y / tile) for x, y, _ in plane_points]
    build_object("FloorPlane", [("MenuHallFloor", plane_points, plane_coordinates, [(0, 1, 2), (0, 2, 3)])],
                 TABLE_OFFSET, textures)
    corners = map_plane_corners(table, TABLE_OFFSET)
    # Camera: perspective, tilted about x towards the front of the table, aimed at the centre of the map plane
    centre = Vector(tuple((min(corner[axis] for corner in corners) + max(corner[axis] for corner in corners)) / 2.0
                          for axis in range(3)))
    camera_data = bpy.data.cameras.new("MapCamera")
    camera_data.type = "PERSP"
    camera_data.sensor_fit = "VERTICAL"
    camera_data.angle_y = math.radians(FOV_Y)
    camera_data.shift_y = SHIFT_Y
    camera_data.clip_start = 0.1
    camera_data.clip_end = 200.0
    camera = bpy.data.objects.new("MapCamera", camera_data)
    scene.collection.objects.link(camera)
    tilt = math.radians(TILT)
    camera.rotation_euler = (tilt, 0.0, 0.0)
    camera.location = centre - Vector((0.0, math.sin(tilt), -math.cos(tilt))) * CAMERA_DISTANCE
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
        json.dump({"render_scale": RENDER_SCALE, "map_plane_corners": pixels}, target, indent=2)


main()
