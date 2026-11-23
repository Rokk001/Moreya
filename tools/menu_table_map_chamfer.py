#!/usr/bin/env python3
"""Cut off the corners of the stone campaign table of the main menu (models/MenuMapTableStone.mesh) and of the map
carved into its top.

The table top has no square corners: its four corners are cut off (chamfered), and the carved map on it follows that
outline, so no square map corner shows anywhere (menu UX plan M2, Mario 2026-11-23). This script

- replaces the rectangular map plane (material MenuCampaignMap, corners at +-half-width x +-half-depth) by an octagon:
  the rectangle with every corner cut off CHAMFER mesh units along both edges; its texture coordinates are those of the
  rectangle at the same place, so the carved map is cut along the chamfers and stays where it was everywhere else;
- moves every vertex of the table body above MIN_HEIGHT (the top slab with its moss and stains) that lies beyond the
  same chamfer lines onto them, so the slab gets flat cut-off corners under the cut-off map; the normals of the side
  faces moved there face out of the chamfer.

    python tools/menu_table_map_chamfer.py [<mesh>] [--chamfer 0.6]

The mesh is converted to XML and back with OgreXMLConverter (OGRE_XML_CONVERTER, else the converter of the build
dependencies) and rewritten in place. It must run after tools/menu_table_map_plane.py, which moves every map plane
vertex to a corner of the rectangle. The shipped table was made with --chamfer 0.6 from the table of 2026-11-23.
"""
import argparse
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

#: Material of the map plane.
MAP_MATERIAL = "MenuCampaignMap"
#: Vertices of the table body below this height (trestles, stretcher, broken pieces on the floor) are left as they are.
MIN_HEIGHT = 1.0
#: A moved vertex whose normal has less upward share than this belongs to a side face and gets the chamfer normal.
SIDE_NORMAL_Z = 0.7


def converter_path():
    """Returns the path of OgreXMLConverter."""
    configured = os.environ.get("OGRE_XML_CONVERTER")
    if configured:
        return configured
    root = os.environ.get("BUILD_DEPS_ROOT", os.path.join(os.path.expanduser("~"), "build-deps"))
    return os.path.join(root, "install", "bin", "OgreXMLConverter.exe")


def convert(source, target):
    """Converts between the binary and the XML mesh format with OgreXMLConverter."""
    subprocess.run([converter_path(), "-q", source, target], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def chamfer_outline(half_width, half_depth, chamfer):
    """Returns the octagon of the map plane, counter-clockwise seen from above: the rectangle +-half_width x
    +-half_depth with every corner cut off chamfer along both edges."""
    return [(half_width - chamfer, -half_depth), (half_width, -half_depth + chamfer),
            (half_width, half_depth - chamfer), (half_width - chamfer, half_depth),
            (-half_width + chamfer, half_depth), (-half_width, half_depth - chamfer),
            (-half_width, -half_depth + chamfer), (-half_width + chamfer, -half_depth)]


def main():
    """Cuts the corners of the map plane and of the top slab of the table."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesh", nargs="?", default="models/MenuMapTableStone.mesh")
    parser.add_argument("--chamfer", type=float, default=0.6)
    args = parser.parse_args()
    work = tempfile.mkdtemp()
    xml_path = os.path.join(work, "table.mesh.xml")
    convert(args.mesh, xml_path)
    tree = ElementTree.parse(xml_path)
    root = tree.getroot()
    shared = root.find("sharedgeometry")
    buffers = shared.findall("vertexbuffer")
    geometry = next(buffer for buffer in buffers if buffer.get("positions") == "true")
    coordinates = next(buffer for buffer in buffers if buffer.get("texture_coords") not in (None, "0"))
    vertices = geometry.findall("vertex")
    texcoords = coordinates.findall("vertex")
    map_submesh = None
    map_indices = set()
    body_indices = set()
    for submesh in root.find("submeshes"):
        indices = set(int(face.get(key)) for face in submesh.find("faces") for key in ("v1", "v2", "v3"))
        if submesh.get("material") == MAP_MATERIAL:
            map_submesh = submesh
            map_indices = indices
        else:
            body_indices.update(indices)
    if map_submesh is None or len(map_indices) != 4:
        print("the table has no rectangular map plane (run tools/menu_table_map_plane.py first)")
        return 1
    corners = [tuple(float(vertices[index].find("position").get(axis)) for axis in "xyz") for index in map_indices]
    half_width = max(abs(corner[0]) for corner in corners)
    half_depth = max(abs(corner[1]) for corner in corners)
    height = corners[0][2]
    # Chamfer line of every corner: sign_x * x + sign_y * y <= limit
    limit = half_width + half_depth - args.chamfer
    moved = 0
    for index in sorted(body_indices):
        position = vertices[index].find("position")
        x, y, z = (float(position.get(axis)) for axis in "xyz")
        if z < MIN_HEIGHT:
            continue
        sign_x = 1.0 if x >= 0.0 else -1.0
        sign_y = 1.0 if y >= 0.0 else -1.0
        excess = sign_x * x + sign_y * y - limit
        if excess <= 0.0:
            continue
        x -= sign_x * excess / 2.0
        y -= sign_y * excess / 2.0
        position.set("x", "%.6g" % x)
        position.set("y", "%.6g" % y)
        normal = vertices[index].find("normal")
        if normal is not None and abs(float(normal.get("z"))) < SIDE_NORMAL_Z:
            normal.set("x", "%.6g" % (sign_x / math.sqrt(2.0)))
            normal.set("y", "%.6g" % (sign_y / math.sqrt(2.0)))
            normal.set("z", "0")
        moved += 1
    # The octagon of the map plane: the four vertices of the rectangle take four of its points (so no vertex is left
    # unused), four new shared vertices the others; texture coordinates are those of the rectangle at the same place
    octagon = []
    reused = sorted(map_indices)
    first = len(vertices)
    for number, (x, y) in enumerate(chamfer_outline(half_width, half_depth, args.chamfer)):
        if number < len(reused):
            index = reused[number]
            vertex = vertices[index]
            texcoord = texcoords[index].find("texcoord")
        else:
            index = first + number - len(reused)
            vertex = ElementTree.SubElement(geometry, "vertex")
            ElementTree.SubElement(vertex, "position")
            ElementTree.SubElement(vertex, "normal")
            texcoord = ElementTree.SubElement(ElementTree.SubElement(coordinates, "vertex"), "texcoord")
        vertex.find("position").attrib.update({"x": "%.6g" % x, "y": "%.6g" % y, "z": "%.6g" % height})
        vertex.find("normal").attrib.update({"x": "0", "y": "0", "z": "1"})
        texcoord.attrib.update({"u": "%.6g" % ((x + half_width) / (2.0 * half_width)),
                                "v": "%.6g" % ((half_depth - y) / (2.0 * half_depth))})
        octagon.append(index)
    shared.set("vertexcount", str(first + 8 - len(reused)))
    faces = map_submesh.find("faces")
    for face in list(faces):
        faces.remove(face)
    for corner in range(1, 7):
        ElementTree.SubElement(faces, "face", v1=str(octagon[0]), v2=str(octagon[corner]),
                               v3=str(octagon[corner + 1]))
    faces.set("count", "6")
    tree.write(xml_path)
    convert(xml_path, args.mesh)
    print("%s: map plane cut to an octagon (chamfer %.2f), %d slab vertices moved onto the chamfers"
          % (args.mesh, args.chamfer, moved))
    return 0


if __name__ == "__main__":
    sys.exit(main())
