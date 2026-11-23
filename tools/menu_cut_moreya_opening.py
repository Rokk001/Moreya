#!/usr/bin/env python3
"""Open the menu scene for the staircase into Moreya in the rear yard (INGAME-QS-12 K1).

The staircase MoreyaStairs (models/MenuMoreyaStairs.mesh, tools/blender-assets/menu_moreya_entrance.py) lies in the
rear yard behind the campaign hall, in front of the abandoned castle. Two openings are cut (config/mainmenuscene.cfg
coordinates, see CUTS):
- the stairwell: x -3.0..3.0, y 31.0..37.0, z -0.95..0.3 out of the yard paving with its bedding (OuterGround) and
  the loose rubble of the bailey (FortressRear) lying there;
- the back wall of the campaign hall: x -4.0..4.0, y 29.0..30.5, z 0.12..4.2 out of CampaignHall, so the campaign
  flight looks through it into the yard; the stone frame MenuHallRearArch covers the cut edges;
- the flat glowing slab floating over the forge hearth of the yard: x 2.99..5.01, y 40.89..42.11, z 1.08..1.18 out of
  FortressRear; the coal heap MenuForgeCoals takes its place.

The campaign scene (config/mainmenuscene.cfg [MenuCampaignScene]) has its own copy of the campaign hall,
CampaignHallOpen (models/MenuCampaignHallOpen.mesh, a copy of the hall before any cut): a wide opening into the
forecourt behind the hall, x -5.0..5.0, y 29.0..30.5, z 0.12..6.6, is cut out of its back wall; the stone frame
MenuHallForecourtArch covers the cut edges. The start screen keeps the hall, yard and rear buildings above.

    python tools/menu_cut_moreya_opening.py <work folder>

Run it on the meshes as they were before any cut (the tool never adds geometry back). Each mesh is converted to XML
with OgreXMLConverter (BUILD_DEPS_ROOT, else %USERPROFILE%/build-deps). Every triangle that overlaps a box is split
along the box's six planes; the piece inside the box is dropped and the pieces outside replace the triangle in its
place (a box can be limited to some materials; a submesh left without faces is dropped). New vertices on the cut edges interpolate every vertex attribute (normals and tangents renormalised). Triangles
away from the boxes and every vertex still in use stay as they were; vertices no face uses any more (those of the
dropped pieces and of splits that were not needed) are removed. The XML before and
after is kept in the work folder (outside the repository) and converted back into models/<mesh>; the vertex values
are taken bit for bit from the binary mesh, so the XML round trip rounds nothing. Running the tool
again on cut meshes changes nothing.
"""
import os
import struct
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
#: The boxes cut out of the entities' meshes, in scene coordinates (x min, x max, y min, y max, z min, z max).
STAIRWELL = (-3.0, 3.0, 31.0, 37.0, -0.95, 0.3)
HALL_BACK_OPENING = (-4.0, 4.0, 29.0, 30.5, 0.12, 4.2)
FORGE_SLAB = (2.99, 5.01, 40.89, 42.11, 1.08, 1.18)
#: The wide opening of the campaign scene's hall copy into the forecourt.
FORECOURT_OPENING = (-5.0, 5.0, 29.0, 30.5, 0.12, 6.6)
#: Per entity: (box, materials) pairs; materials None cuts every submesh, else only the submeshes of those materials
#: (the forge slab is the glowing material alone; the hearth stone around it stays whole).
CUTS = {"OuterGround": ((STAIRWELL, None),), "FortressRear": ((STAIRWELL, None), (FORGE_SLAB, ("MenuEmber",))),
        "CampaignHall": ((HALL_BACK_OPENING, None),), "CampaignHallOpen": ((FORECOURT_OPENING, None),)}
#: Attributes that are directions and are renormalised after interpolation.
DIRECTIONS = ("normal", "tangent", "binormal")
#: Distance from a cut plane within which a vertex counts as lying on it.
ON_PLANE = 1e-4
#: Ogre vertex element semantics of the XML vertex attributes and the names of their components.
SEMANTICS = {"position": (1, ("x", "y", "z")), "normal": (4, ("x", "y", "z")), "texcoord": (7, ("u", "v", "w", "x")),
             "tangent": (8, ("x", "y", "z", "w")), "binormal": (9, ("x", "y", "z"))}


def chunks(data, offset, end):
    """Yields (id, payload start, chunk end) of the Ogre binary chunks between offset and end."""
    while offset + 6 <= end:
        chunk_id, length = struct.unpack_from("<HI", data, offset)
        yield chunk_id, offset + 6, offset + length
        offset += length


def exact_geometry(data, start, end):
    """Returns {(semantic, index): rows of float32 values} of the float elements of one binary geometry chunk."""
    count, = struct.unpack_from("<I", data, start)
    elements = []
    buffers = {}
    for chunk_id, s, e in chunks(data, start + 4, end):
        if chunk_id == 0x5100:
            for _, s3, _ in chunks(data, s, e):
                elements.append(struct.unpack_from("<HHHHH", data, s3))
        elif chunk_id == 0x5200:
            bind, stride = struct.unpack_from("<HH", data, s)
            for kind, s3, _ in chunks(data, s + 4, e):
                if kind == 0x5210:
                    buffers[bind] = (stride, s3)
    result = {}
    for source, kind, semantic, offset, index in elements:
        if kind > 3:
            continue
        stride, base = buffers[source]
        components = kind + 1
        result[(semantic, index)] = [struct.unpack_from("<%df" % components, data, base + vertex * stride + offset)
                                     for vertex in range(count)]
    return result


def exact_geometries(path):
    """Returns the exact float vertex data of a binary mesh: the shared geometry first, then each submesh's own."""
    data = Path(path).read_bytes()
    offset = data.index(b"\n") + 1
    result = []
    for chunk_id, s, e in chunks(data, offset, len(data)):
        if chunk_id != 0x3000:
            continue
        for kind, s2, e2 in chunks(data, s + 1, e):
            if kind == 0x5000:
                result.append(exact_geometry(data, s2, e2))
            elif kind == 0x4000:
                p = data.index(b"\n", s2) + 1
                count, = struct.unpack_from("<I", data, p + 1)
                p += 6 + count * (4 if data[p + 5] else 2)
                for kind3, s3, e3 in chunks(data, p, e2):
                    if kind3 == 0x5000:
                        result.append(exact_geometry(data, s3, e3))
                        break
    return result


def converter():
    """Returns the path of OgreXMLConverter.exe of the dependency root."""
    root = Path(os.environ.get("BUILD_DEPS_ROOT", str(Path.home() / "build-deps")))
    return root / "install" / "bin" / "OgreXMLConverter.exe"


def convert(source, target):
    """Converts between a binary mesh and its XML form, raising on failure."""
    result = subprocess.run([str(converter()), "-q", str(source), str(target)], capture_output=True, text=True)
    if result.returncode != 0 or not Path(target).exists():
        raise RuntimeError("OgreXMLConverter failed for %s: %s %s" % (source, result.stdout, result.stderr))


def entity_positions():
    """Returns {entity: (mesh, (x, y, z))} of the AddEntity lines of config/mainmenuscene.cfg."""
    result = {}
    for line in (ROOT / "config" / "mainmenuscene.cfg").read_text(encoding="utf-8").splitlines():
        words = line.split()
        if len(words) == 6 and words[0] == "AddEntity":
            result[words[1]] = (words[2], tuple(float(value) for value in words[3:6]))
    return result


class Geometry:
    """The vertices of one Ogre XML geometry element, readable as numbers and extendable by interpolation."""

    def __init__(self, element, exact=None):
        """Reads every vertex of every vertex buffer of a geometry element.

        exact, the float data of the same geometry read from the binary mesh, replaces the six-digit numbers of the
        XML form, so the vertices that stay keep their values bit for bit when the XML is converted back.
        """
        self.element = element
        self.buffers = element.findall("vertexbuffer")
        if exact:
            self.restore(exact)
        self.records = [[self.parse(vertex) for vertex in buffer.findall("vertex")] for buffer in self.buffers]
        self.count = int(element.get("vertexcount"))

    def restore(self, exact):
        """Writes the exact binary values into every float attribute of the XML vertices."""
        vertex_lists = [buffer.findall("vertex") for buffer in self.buffers]
        for index in range(len(vertex_lists[0])):
            texcoords = 0
            for vertices in vertex_lists:
                for child in vertices[index]:
                    if child.tag not in SEMANTICS:
                        continue
                    semantic, names = SEMANTICS[child.tag]
                    slot = texcoords if child.tag == "texcoord" else 0
                    texcoords += child.tag == "texcoord"
                    values = exact.get((semantic, slot))
                    if values is None:
                        continue
                    for name, value in zip(names, values[index]):
                        if name in child.attrib:
                            child.set(name, "%.9g" % value)

    @staticmethod
    def parse(vertex):
        """Returns [(tag, [(attribute, [numbers])])] of one vertex element."""
        return [(child.tag, [(name, [float(value) for value in text.split()]) for name, text in child.attrib.items()])
                for child in vertex]

    def position(self, index):
        """Returns the position (x, y, z) of a vertex."""
        for records in self.records:
            for tag, attributes in records[index]:
                if tag == "position":
                    values = dict(attributes)
                    return values["x"][0], values["y"][0], values["z"][0]
        raise ValueError("vertex without position")

    def interpolate(self, first, second, share):
        """Appends the vertex at share (0..1) between two vertices and returns its index."""
        for buffer, records in zip(self.buffers, self.records):
            mixed = []
            for (tag, one), (_, two) in zip(records[first], records[second]):
                attributes = [(name, [a + (b - a) * share for a, b in zip(values, other)])
                              for (name, values), (_, other) in zip(one, two)]
                if tag in DIRECTIONS:
                    axes = [name for name, _ in attributes if name in ("x", "y", "z")]
                    length = sum(dict(attributes)[name][0] ** 2 for name in axes) ** 0.5 or 1.0
                    attributes = [(name, [value / length for value in values] if name in axes else values)
                                  for name, values in attributes]
                mixed.append((tag, attributes))
            records.append(mixed)
            vertex = ElementTree.SubElement(buffer, "vertex")
            for tag, attributes in mixed:
                ElementTree.SubElement(vertex, tag, {name: " ".join("%.9g" % value for value in values)
                                                     for name, values in attributes})
        self.count += 1
        self.element.set("vertexcount", str(self.count))
        return self.count - 1


def split(geometry, polygon, axis, value, cache):
    """Splits a polygon of vertex indices at a plane (axis 0, 1 or 2 equals value): returns (below, above)."""
    below, above = [], []
    for index, vertex in enumerate(polygon):
        following = polygon[(index + 1) % len(polygon)]
        a = geometry.position(vertex)[axis] - value
        b = geometry.position(following)[axis] - value
        # A vertex within ON_PLANE of the plane lies on it and belongs to both sides (no sliver on a second run).
        if a <= ON_PLANE:
            below.append(vertex)
        if a >= -ON_PLANE:
            above.append(vertex)
        if (a < -ON_PLANE and b > ON_PLANE) or (a > ON_PLANE and b < -ON_PLANE):
            key = (min(vertex, following), max(vertex, following), axis, value)
            if key not in cache:
                share = a / (a - b)
                cache[key] = geometry.interpolate(vertex, following, share)
            below.append(cache[key])
            above.append(cache[key])
    return below, above


def area(geometry, polygon):
    """Returns the doubled area of a planar polygon of vertex indices."""
    points = [geometry.position(index) for index in polygon]
    total = [0.0, 0.0, 0.0]
    for index in range(1, len(points) - 1):
        u = [points[index][k] - points[0][k] for k in range(3)]
        v = [points[index + 1][k] - points[0][k] for k in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        total = [total[k] + cross[k] for k in range(3)]
    return sum(value * value for value in total) ** 0.5


def cut_faces(geometry, faces, box, cache):
    """Cuts a box (mesh coordinates) out of the triangles of one faces element; returns the triangles cut."""
    planes = ((0, box[0], True), (0, box[1], False), (1, box[2], True), (1, box[3], False), (2, box[4], True),
              (2, box[5], False))
    result = []
    changed = 0
    for face in faces.findall("face"):
        triangle = [int(face.get(name)) for name in ("v1", "v2", "v3")]
        points = [geometry.position(index) for index in triangle]
        overlaps = all(max(p[axis] for p in points) > box[2 * axis] and min(p[axis] for p in points) < box[2 * axis + 1]
                       for axis in range(3))
        if not overlaps:
            result.append(triangle)
            continue
        outside = []
        rest = triangle
        for axis, value, keep_below in planes:
            below, above = split(geometry, rest, axis, value, cache)
            outside.append(below if keep_below else above)
            rest = above if keep_below else below
            if len(rest) < 3:
                break
        if len(rest) < 3 or area(geometry, rest) < 1e-10:
            result.append(triangle)
            continue
        changed += 1
        for piece in outside:
            if len(piece) >= 3 and area(geometry, piece) > 1e-10:
                for index in range(1, len(piece) - 1):
                    result.append([piece[0], piece[index], piece[index + 1]])
    for face in list(faces):
        faces.remove(face)
    for triangle in result:
        ElementTree.SubElement(faces, "face", {"v1": str(triangle[0]), "v2": str(triangle[1]),
                                               "v3": str(triangle[2])})
    faces.set("count", str(len(result)))
    return changed


def compact(geometry, face_lists):
    """Removes the vertices of a geometry that no face uses any more and renumbers the faces, keeping the order."""
    used = sorted({int(face.get(name)) for faces in face_lists for face in faces.findall("face")
                   for name in ("v1", "v2", "v3")})
    if len(used) == geometry.count:
        return 0
    remap = {old: new for new, old in enumerate(used)}
    for buffer in geometry.buffers:
        vertices = buffer.findall("vertex")
        for index, vertex in enumerate(vertices):
            if index not in remap:
                buffer.remove(vertex)
    for faces in face_lists:
        for face in faces.findall("face"):
            for name in ("v1", "v2", "v3"):
                face.set(name, str(remap[int(face.get(name))]))
    removed = geometry.count - len(used)
    geometry.element.set("vertexcount", str(len(used)))
    return removed


def cut_mesh(path, boxes, binary):
    """Cuts (box, materials) pairs (mesh coordinates) out of one Ogre XML mesh file in place; returns the triangles cut.

    binary is the mesh file the XML was made from; its exact vertex values replace the rounded ones of the XML.
    """
    tree = ElementTree.parse(path)
    root = tree.getroot()
    exact = iter(exact_geometries(binary))
    shared = root.find("sharedgeometry")
    shared_geometry = Geometry(shared, next(exact)) if shared is not None else None
    shared_cache = {}
    total = 0
    shared_faces = []
    for submesh in root.find("submeshes").findall("submesh"):
        if submesh.get("usesharedvertices") == "true":
            geometry, cache = shared_geometry, shared_cache
            shared_faces.append(submesh.find("faces"))
        else:
            geometry, cache = Geometry(submesh.find("geometry"), next(exact)), {}
        if submesh.get("operationtype", "triangle_list") != "triangle_list":
            continue
        for box, materials in boxes:
            if materials is None or submesh.get("material") in materials:
                total += cut_faces(geometry, submesh.find("faces"), box, cache)
        if geometry is not shared_geometry:
            compact(geometry, [submesh.find("faces")])
    if shared_geometry is not None:
        compact(shared_geometry, shared_faces)
    # A submesh left without faces is dropped together with its name entry.
    submeshes = root.find("submeshes")
    names = root.find("submeshnames")
    for index, submesh in reversed(list(enumerate(submeshes.findall("submesh")))):
        if int(submesh.find("faces").get("count")) == 0:
            submeshes.remove(submesh)
            if names is not None:
                for entry in names.findall("submeshname"):
                    position = int(entry.get("index"))
                    if position == index:
                        names.remove(entry)
                    elif position > index:
                        entry.set("index", str(position - 1))
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return total


def main():
    """Cuts the boxes of CUTS out of the named entities' meshes and writes the meshes back."""
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    work.mkdir(parents=True, exist_ok=True)
    entities = entity_positions()
    for name, scene_boxes in CUTS.items():
        mesh, offset = entities[name]
        boxes = [((box[0] - offset[0], box[1] - offset[0], box[2] - offset[1], box[3] - offset[1], box[4] - offset[2],
                   box[5] - offset[2]), materials) for box, materials in scene_boxes]
        before = work / (mesh + ".before.xml")
        after = work / (mesh + ".xml")
        binary = work / (Path(mesh).stem + ".before.mesh")
        binary.write_bytes((ROOT / "models" / mesh).read_bytes())
        convert(binary, before)
        after.write_bytes(before.read_bytes())
        total = cut_mesh(after, boxes, binary)
        convert(after, ROOT / "models" / mesh)
        print("%s: %d triangles cut" % (mesh, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
