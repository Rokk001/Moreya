#!/usr/bin/env python3
"""Give the floor and the walls of the campaign hall of the main menu (models/MenuCampaignHallOpen.mesh) their own
materials.

The hall used one stone material (MenuStone) for its floor, its walls and its roof, the same stone as the table in it,
so floor, walls and table melted into one brown mass. This script splits the faces of that material into

- MenuHallFloor: the faces that look up (face normal z above FLOOR_NORMAL_Z) and lie low (all corners below
  FLOOR_HEIGHT): worn, dirty flagstones;
- MenuHallWall: every other face of it (walls, pillars, roof): rough masonry with damp stains and soot.

Positions and normals stay; the faces move to the two new submeshes. The floor gets planar texture coordinates (one
tile of the flagstones every FLOOR_TILE mesh units along x and y, so the stones lie square to the hall and no longer
diagonal; the floor vertices are its own); the other texture coordinates stay. The overlay materials (moss, lichen,
water stains, chipped stone, black) stay as they are.

    python tools/menu_hall_floor_walls.py [<mesh>]

The mesh is converted to XML and back with OgreXMLConverter (OGRE_XML_CONVERTER, else the converter of the build
dependencies) and rewritten in place.
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

#: The material that is split and the two materials it is split into.
SOURCE_MATERIAL = "MenuStone"
FLOOR_MATERIAL = "MenuHallFloor"
WALL_MATERIAL = "MenuHallWall"
#: A floor face looks up at least this much and lies below this height (mesh units).
FLOOR_NORMAL_Z = 0.7
FLOOR_HEIGHT = 1.0
#: Size of one tile of the floor texture (mesh units along x and y).
FLOOR_TILE = 4.0


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


def is_floor(points):
    """True if a triangle (three (x, y, z) points) belongs to the floor: it looks up and lies low."""
    ax, ay, az = (points[1][axis] - points[0][axis] for axis in range(3))
    bx, by, bz = (points[2][axis] - points[0][axis] for axis in range(3))
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length == 0.0:
        return False
    return nz / length > FLOOR_NORMAL_Z and max(point[2] for point in points) < FLOOR_HEIGHT


def main():
    """Splits the stone submesh of the hall into a floor and a wall submesh."""
    mesh = sys.argv[1] if len(sys.argv) > 1 else "models/MenuCampaignHallOpen.mesh"
    work = tempfile.mkdtemp()
    xml_path = os.path.join(work, "hall.mesh.xml")
    convert(mesh, xml_path)
    tree = ElementTree.parse(xml_path)
    root = tree.getroot()
    geometry = next(buffer for buffer in root.find("sharedgeometry").findall("vertexbuffer")
                    if buffer.get("positions") == "true")
    positions = [tuple(float(vertex.find("position").get(axis)) for axis in "xyz")
                 for vertex in geometry.findall("vertex")]
    submeshes = root.find("submeshes")
    source = next((submesh for submesh in submeshes if submesh.get("material") == SOURCE_MATERIAL), None)
    if source is None or source.get("usesharedvertices") != "true":
        print("the hall has no %s submesh on shared vertices" % SOURCE_MATERIAL)
        return 1
    floor_faces = []
    wall_faces = []
    for face in source.find("faces"):
        corners = [positions[int(face.get(key))] for key in ("v1", "v2", "v3")]
        (floor_faces if is_floor(corners) else wall_faces).append(face)
    # Planar texture coordinates of the floor; its vertices are used by no other face
    coordinates = next(buffer for buffer in root.find("sharedgeometry").findall("vertexbuffer")
                       if buffer.get("texture_coords") not in (None, "0")).findall("vertex")
    floor_vertices = set(int(face.get(key)) for face in floor_faces for key in ("v1", "v2", "v3"))
    other_vertices = set(int(face.get(key)) for submesh in submeshes for face in submesh.find("faces")
                         for key in ("v1", "v2", "v3") if face not in floor_faces)
    if floor_vertices & other_vertices:
        print("the floor shares vertices with other faces; its texture coordinates cannot be set alone")
        return 1
    for vertex in floor_vertices:
        texcoord = coordinates[vertex].find("texcoord")
        texcoord.set("u", "%.6g" % (positions[vertex][0] / FLOOR_TILE))
        texcoord.set("v", "%.6g" % (-positions[vertex][1] / FLOOR_TILE))
    index = list(submeshes).index(source)
    submeshes.remove(source)
    for offset, (material, faces) in enumerate(((FLOOR_MATERIAL, floor_faces), (WALL_MATERIAL, wall_faces))):
        submesh = ElementTree.Element("submesh", dict(source.attrib))
        submesh.set("material", material)
        faces_element = ElementTree.SubElement(submesh, "faces", count=str(len(faces)))
        for face in faces:
            faces_element.append(face)
        submeshes.insert(index + offset, submesh)
    tree.write(xml_path)
    convert(xml_path, mesh)
    print("%s: %d floor faces (%s), %d wall faces (%s)" % (mesh, len(floor_faces), FLOOR_MATERIAL, len(wall_faces),
                                                          WALL_MATERIAL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
