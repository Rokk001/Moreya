#!/usr/bin/env python3
"""Make the slab of the stone campaign table of the main menu (models/MenuMapTableStone.mesh) one piece of the stone
of the map carved into it.

The map is cut into the table, nothing lies on it: the top slab (its top round the map, its bevels, cut-off corners and
side faces) must be the same stone as the carved map, with no rim of other stone, moss or stains round the map. This
script moves every face of the table body that lies wholly above SLAB_BOTTOM (the slab; the trestles, the stretcher
and the broken pieces on the floor stay below it) from its material to MenuTableStone (the stone of the carved map,
tools/gen_menu_table_stone.py). The map plane (MenuCampaignMap) and the dark cracks (MenuBlack) stay.

    python tools/menu_table_slab_stone.py [<mesh>]

The mesh is converted to XML and back with OgreXMLConverter (OGRE_XML_CONVERTER, else the converter of the build
dependencies) and rewritten in place; a submesh left without faces is removed.
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

#: The material of the slab, the materials that keep their faces, and the lowest point of a slab face (mesh units).
SLAB_MATERIAL = "MenuTableStone"
KEPT_MATERIALS = ("MenuCampaignMap", "MenuBlack")
SLAB_BOTTOM = 1.15


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


def main():
    """Moves the faces of the slab to the stone of the carved map."""
    mesh = sys.argv[1] if len(sys.argv) > 1 else "models/MenuMapTableStone.mesh"
    work = tempfile.mkdtemp()
    xml_path = os.path.join(work, "table.mesh.xml")
    convert(mesh, xml_path)
    tree = ElementTree.parse(xml_path)
    root = tree.getroot()
    geometry = next(buffer for buffer in root.find("sharedgeometry").findall("vertexbuffer")
                    if buffer.get("positions") == "true")
    heights = [float(vertex.find("position").get("z")) for vertex in geometry.findall("vertex")]
    submeshes = root.find("submeshes")
    if any(submesh.get("material") == SLAB_MATERIAL for submesh in submeshes):
        print("the slab already has its own stone")
        return 1
    slab_faces = []
    template = None
    for submesh in list(submeshes):
        if submesh.get("material") in KEPT_MATERIALS:
            continue
        faces = submesh.find("faces")
        for face in list(faces):
            if min(heights[int(face.get(key))] for key in ("v1", "v2", "v3")) > SLAB_BOTTOM:
                faces.remove(face)
                slab_faces.append(face)
        faces.set("count", str(len(faces)))
        template = submesh
        if len(faces) == 0:
            submeshes.remove(submesh)
    slab = ElementTree.SubElement(submeshes, "submesh", dict(template.attrib))
    slab.set("material", SLAB_MATERIAL)
    faces = ElementTree.SubElement(slab, "faces", count=str(len(slab_faces)))
    for face in slab_faces:
        faces.append(face)
    tree.write(xml_path)
    convert(xml_path, mesh)
    print("%s: %d slab faces moved to %s" % (mesh, len(slab_faces), SLAB_MATERIAL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
