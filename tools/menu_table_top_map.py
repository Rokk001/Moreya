#!/usr/bin/env python3
"""Carve the campaign map into the top of the stone table of the main menu (models/MenuMapTableStone.mesh) itself.

The map is not a sheet on the table: the table top is the map. The table used to carry the map on a separate thin plane
(material MenuCampaignMap) a little above its slab, whose own top was a patchwork of the slab, a worn sheet once laid on
it and chipped edges, so a second edge ran round the top and the plane stuck out over the slab where the slab was
lower. This script

- removes that map plane (its corners at +-half-width x +-half-depth, cut off by tools/menu_table_map_chamfer.py) and
  remembers its octagon,
- moves every vertex of the slab (above MIN_HEIGHT) that lies outside +-half-width x +-half-depth onto that edge and
  every vertex of the table above TOP_BAND up to the top height (the highest point of the slab), so the side faces of
  the slab run up to one flat top,
- removes every face that now lies wholly in that top (the old top surface, the sheet, collapsed edge faces),
- closes the top with one octagon at the top height, the outline of the slab top, in the material MenuCampaignMap with
  planar texture coordinates over +-half-width x +-half-depth: the carved map is the slab's own top surface with
  exactly one edge.

    python tools/menu_table_top_map.py [<mesh>]

The mesh is converted to XML and back with OgreXMLConverter (OGRE_XML_CONVERTER, else the converter of the build
dependencies) and rewritten in place; vertices no face uses any more are removed. It runs after
tools/menu_table_map_chamfer.py and tools/menu_table_slab_stone.py.
"""
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

#: The material of the map.
MAP_MATERIAL = "MenuCampaignMap"
#: Vertices of the table above MIN_HEIGHT belong to the slab; those above TOP_BAND are raised to the top.
MIN_HEIGHT = 1.0
TOP_BAND = 1.6


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


def octagon_outline(points):
    """Returns the corners of the octagon map plane (x, y), counter-clockwise seen from above."""
    centre_x = sum(point[0] for point in points) / len(points)
    centre_y = sum(point[1] for point in points) / len(points)

    def angle(point):
        """Returns the angle of a corner round the centre of the plane."""
        return math.atan2(point[1] - centre_y, point[0] - centre_x)

    return sorted(points, key=angle)


def main():
    """Replaces the map plane and the top of the slab by one flat top carrying the carved map."""
    mesh = sys.argv[1] if len(sys.argv) > 1 else "models/MenuMapTableStone.mesh"
    work = tempfile.mkdtemp()
    xml_path = os.path.join(work, "table.mesh.xml")
    convert(mesh, xml_path)
    tree = ElementTree.parse(xml_path)
    root = tree.getroot()
    shared = root.find("sharedgeometry")
    buffers = shared.findall("vertexbuffer")
    geometry = next(buffer for buffer in buffers if buffer.get("positions") == "true")
    coordinates = next(buffer for buffer in buffers if buffer.get("texture_coords") not in (None, "0"))
    vertices = geometry.findall("vertex")
    texcoords = coordinates.findall("vertex")
    positions = [[float(vertex.find("position").get(axis)) for axis in "xyz"] for vertex in vertices]
    submeshes = root.find("submeshes")
    plane = next((submesh for submesh in submeshes if submesh.get("material") == MAP_MATERIAL), None)
    if plane is None:
        print("the table has no map plane")
        return 1
    plane_vertices = sorted(set(int(face.get(key)) for face in plane.find("faces") for key in ("v1", "v2", "v3")))
    outline = octagon_outline([(positions[index][0], positions[index][1]) for index in plane_vertices])
    half_width = max(abs(point[0]) for point in outline)
    half_depth = max(abs(point[1]) for point in outline)
    attributes = dict(plane.attrib)
    submeshes.remove(plane)
    # The slab ends where the map ends and runs up to one flat top
    top_height = max(position[2] for index, position in enumerate(positions) if index not in plane_vertices)
    raised = set()
    for index, position in enumerate(positions):
        if index in plane_vertices or position[2] < MIN_HEIGHT:
            continue
        position[0] = max(-half_width, min(half_width, position[0]))
        position[1] = max(-half_depth, min(half_depth, position[1]))
        if position[2] > TOP_BAND:
            position[2] = top_height
            raised.add(index)
    removed = 0
    for submesh in list(submeshes):
        faces = submesh.find("faces")
        for face in list(faces):
            if all(int(face.get(key)) in raised for key in ("v1", "v2", "v3")):
                faces.remove(face)
                removed += 1
        faces.set("count", str(len(faces)))
        if len(faces) == 0:
            submeshes.remove(submesh)
    # Rebuild the vertex buffers with only the used vertices, then add the octagon top
    order = []
    new_index = {}
    for submesh in submeshes:
        for face in submesh.find("faces"):
            for key in ("v1", "v2", "v3"):
                old = int(face.get(key))
                if old not in new_index:
                    new_index[old] = len(order)
                    order.append(old)
                face.set(key, str(new_index[old]))
    for vertex in list(geometry):
        geometry.remove(vertex)
    for vertex in list(coordinates):
        coordinates.remove(vertex)
    for old in order:
        x, y, z = positions[old]
        vertex = ElementTree.SubElement(geometry, "vertex")
        ElementTree.SubElement(vertex, "position", x="%.6g" % x, y="%.6g" % y, z="%.6g" % z)
        normal = vertices[old].find("normal")
        if normal is not None:
            vertex.append(normal)
        texcoord_vertex = ElementTree.SubElement(coordinates, "vertex")
        texcoord_vertex.append(texcoords[old].find("texcoord"))
    first = len(order)
    for x, y in outline:
        vertex = ElementTree.SubElement(geometry, "vertex")
        ElementTree.SubElement(vertex, "position", x="%.6g" % x, y="%.6g" % y, z="%.6g" % top_height)
        ElementTree.SubElement(vertex, "normal", x="0", y="0", z="1")
        texcoord_vertex = ElementTree.SubElement(coordinates, "vertex")
        ElementTree.SubElement(texcoord_vertex, "texcoord", u="%.6g" % ((x + half_width) / (2.0 * half_width)),
                               v="%.6g" % ((half_depth - y) / (2.0 * half_depth)))
    shared.set("vertexcount", str(first + len(outline)))
    top = ElementTree.SubElement(submeshes, "submesh", attributes)
    faces = ElementTree.SubElement(top, "faces", count=str(len(outline) - 2))
    for corner in range(1, len(outline) - 1):
        ElementTree.SubElement(faces, "face", v1=str(first), v2=str(first + corner), v3=str(first + corner + 1))
    tree.write(xml_path)
    convert(xml_path, mesh)
    print("%s: one flat top at %.3f carries the map, %d faces in the old top removed, %d vertices"
          % (mesh, top_height, removed, first + len(outline)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
