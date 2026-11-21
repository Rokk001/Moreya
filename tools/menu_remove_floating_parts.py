#!/usr/bin/env python3
"""Remove the floating parts of menu scene meshes (INGAME-QS-12 K1).

Some generated menu models carry small parts that hang in the air where the block under them was left out: window
glows and soot marks on missing wall blocks, loose rubble above the ground. source/tests/check_menu_scene_grounded.py
finds every part that no chain of touching parts connects to the ground; this tool deletes the triangles of those parts
from the named entities' meshes and writes the meshes back:

    python tools/menu_remove_floating_parts.py <work folder> <entity> [<entity> ...]

Each mesh is converted to XML with OgreXMLConverter (BUILD_DEPS_ROOT, else %USERPROFILE%/build-deps), the faces of the
floating parts are dropped from its submeshes (a submesh left without faces is dropped), vertices no face uses any more
are removed, and the XML is converted back into models/<mesh>. The XML before and
after is kept in the work folder (outside the repository).
"""
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source" / "tests"))
import check_menu_scene_grounded as grounded  # noqa: E402


def converter():
    """Returns the path of OgreXMLConverter.exe of the dependency root."""
    root = Path(os.environ.get("BUILD_DEPS_ROOT", str(Path.home() / "build-deps")))
    return root / "install" / "bin" / "OgreXMLConverter.exe"


def convert(source, target):
    """Converts between a binary mesh and its XML form, raising on failure."""
    result = subprocess.run([str(converter()), "-q", str(source), str(target)], capture_output=True, text=True)
    if result.returncode != 0 or not Path(target).exists():
        raise RuntimeError("OgreXMLConverter failed for %s: %s %s" % (source, result.stdout, result.stderr))


def compact_geometry(geometry, face_lists):
    """Drops the vertices of a geometry element that no face of face_lists uses and renumbers those faces."""
    used = sorted({int(face.get(key)) for faces in face_lists for face in faces for key in ("v1", "v2", "v3")})
    remap = {old: new for new, old in enumerate(used)}
    for buffer in geometry.findall("vertexbuffer"):
        vertices = buffer.findall("vertex")
        for vertex in vertices:
            buffer.remove(vertex)
        for old in used:
            buffer.append(vertices[old])
    geometry.set("vertexcount", str(len(used)))
    for faces in face_lists:
        for face in faces:
            for key in ("v1", "v2", "v3"):
                face.set(key, str(remap[int(face.get(key))]))


def compact(root):
    """Removes unreferenced vertices from the shared geometry and from every submesh geometry of a mesh XML."""
    submeshes = root.find("submeshes").findall("submesh")
    shared = root.find("sharedgeometry")
    if shared is not None:
        compact_geometry(shared, [submesh.find("faces").findall("face") for submesh in submeshes
                                  if submesh.get("usesharedvertices") == "true"])
    for submesh in submeshes:
        if submesh.get("usesharedvertices") != "true":
            compact_geometry(submesh.find("geometry"), [submesh.find("faces").findall("face")])


def main():
    """Removes the floating parts of the named entities and rewrites their meshes."""
    work = Path(sys.argv[1])
    wanted = sys.argv[2:]
    work.mkdir(parents=True, exist_ok=True)
    scene = grounded.load_scene()
    names, triangles, materials, entity, part = scene
    floating = set(grounded.floating_parts(scene).tolist())
    entities, _ = grounded.parse_config()
    meshes = {name: mesh for name, mesh, _ in entities}
    for name in wanted:
        index = names.index(name)
        own = np.where(entity == index)[0]
        drop = np.array([part[i] in floating for i in own])
        if not drop.any():
            print("%s: no floating part" % name)
            continue
        mesh = meshes[name]
        binary = ROOT / "models" / mesh
        before = work / (mesh + ".before.xml")
        after = work / (mesh + ".xml")
        convert(binary, before)
        tree = ElementTree.parse(before)
        root = tree.getroot()
        face_index = 0
        removed = 0
        submeshes = root.find("submeshes")
        for submesh in list(submeshes.findall("submesh")):
            faces = submesh.find("faces")
            kept = []
            for face in faces.findall("face"):
                if not drop[face_index]:
                    kept.append(face)
                face_index += 1
            removed += len(faces.findall("face")) - len(kept)
            for face in list(faces):
                faces.remove(face)
            for face in kept:
                faces.append(face)
            faces.set("count", str(len(kept)))
            if not kept:
                submeshes.remove(submesh)
        assert face_index == len(own), "face order of %s differs from the binary mesh" % mesh
        assert root.find("submeshnames") is None and root.find("boneassignments") is None, mesh
        compact(root)
        tree.write(after, encoding="utf-8", xml_declaration=False)
        convert(after, binary)
        print("%s: removed %d triangles of %d floating parts from %s"
              % (name, removed, len({part[i] for i in own[drop]}), mesh))


if __name__ == "__main__":
    main()
