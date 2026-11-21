#!/usr/bin/env python3
"""Turn the start screen "Lords of the Deep" signpost so its board points at the gate, and give it weathered wood.

models/MenuSignpost.mesh is placed by `AddEntity Signpost MenuSignpost.mesh x y z` in config/mainmenuscene.cfg; the
scene cannot rotate an entity, so the turn is baked into the mesh. This script

- converts the mesh to XML with OgreXMLConverter (BUILD_DEPS_ROOT, else %USERPROFILE%/build-deps),
- measures where the board points today: the horizontal main axis of the board front (material MenuSignpostBoard),
  directed from the post (mesh origin) towards the arrow tip,
- turns every vertex position and normal about the vertical axis through the mesh origin (the post foot) so that the
  board points from the configured signpost position into the gate opening, at the point AIM_OFFSET_X beside the
  configured position of the entity Gate (the left half of the opening keeps the board clear of the left brazier and
  its letters left of the menu button column),
- gives the post, brace and board edges the weathered wood MenuSignpostWeatheredWood instead of MenuSignpostWood,
- and converts the result back into models/MenuSignpost.mesh.

The turn is measured from the mesh itself, so running the script again leaves an already turned mesh as it is.

Run from anywhere: python tools/menu_turn_signpost.py [<repo>]

With --wood-only <mesh> it only gives another signpost mesh of the same builder the weathered wood, without turning
it; the Moreya signpost of the staircase uses this:

    python tools/menu_turn_signpost.py [<repo>] --wood-only MenuMoreyaSignpost.mesh
"""
import argparse
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import numpy

#: Material of the board front, whose outline gives the pointing direction.
BOARD_MATERIAL = "MenuSignpostBoard"
#: Aim of the board relative to the Gate entity position along X (the gate opening spans about -4 to 4).
AIM_OFFSET_X = -3.0
#: Plain wood of the signpost and the weathered wood that replaces it on this signpost.
PLAIN_WOOD = "MenuSignpostWood"
WEATHERED_WOOD = "MenuSignpostWeatheredWood"


def converter():
    """Returns the path of OgreXMLConverter.exe of the dependency root."""
    root = os.environ.get("BUILD_DEPS_ROOT") or os.path.join(os.path.expanduser("~"), "build-deps")
    return os.path.join(root, "install", "bin", "OgreXMLConverter.exe")


def scene_position(repo, entity):
    """Returns the (x, y, z) position of an AddEntity line of the menu scene."""
    for line in (repo / "config/mainmenuscene.cfg").read_text(encoding="utf-8").splitlines():
        words = line.split()
        if len(words) >= 6 and words[0] == "AddEntity" and words[1] == entity:
            return numpy.array([float(value) for value in words[3:6]])
    raise RuntimeError("no AddEntity line for " + entity)


def board_direction(positions):
    """Returns the horizontal unit direction from the mesh origin along the board towards its tip."""
    flat = positions[:, :2]
    centre = flat.mean(axis=0)
    _, _, axes = numpy.linalg.svd(flat - centre)
    axis = axes[0]
    if numpy.dot(axis, centre) < 0:
        axis = -axis
    return axis / numpy.linalg.norm(axis)


def turn(root, angle):
    """Turns every position and normal of the shared geometry of a mesh XML tree about +Z by angle (radians)."""
    cosine, sine = math.cos(angle), math.sin(angle)
    for vertex in root.iter("vertex"):
        for tag in ("position", "normal", "tangent"):
            element = vertex.find(tag)
            if element is None:
                continue
            x, y = float(element.get("x")), float(element.get("y"))
            element.set("x", repr(cosine * x - sine * y))
            element.set("y", repr(sine * x + cosine * y))


def board_positions(root):
    """Returns the positions (n, 3) of the shared vertices used by the board front submesh."""
    vertices = [[float(element.get(axis)) for axis in "xyz"]
                for element in root.find("sharedgeometry").iter("position")]
    used = set()
    for submesh in root.iter("submesh"):
        if submesh.get("material") != BOARD_MATERIAL:
            continue
        for face in submesh.iter("face"):
            used.update(int(face.get(key)) for key in ("v1", "v2", "v3"))
    return numpy.array([vertices[index] for index in sorted(used)])


def weather_wood_only(mesh):
    """Gives the plain signpost wood submeshes of a mesh the weathered wood and leaves its geometry as it is."""
    with tempfile.TemporaryDirectory() as folder:
        xml_path = os.path.join(folder, "signpost.mesh.xml")
        subprocess.run([converter(), "-q", str(mesh), xml_path], check=True, cwd=folder)
        tree = ElementTree.parse(xml_path)
        changed = 0
        for submesh in tree.getroot().iter("submesh"):
            if submesh.get("material") == PLAIN_WOOD:
                submesh.set("material", WEATHERED_WOOD)
                changed += 1
        tree.write(xml_path, encoding="utf-8", xml_declaration=False)
        out_path = os.path.join(folder, "signpost.mesh")
        subprocess.run([converter(), "-q", xml_path, out_path], check=True, cwd=folder)
        mesh.write_bytes(Path(out_path).read_bytes())
    print("%s: %d wood submeshes now use %s" % (mesh.name, changed, WEATHERED_WOOD))


def main():
    """Turns models/MenuSignpost.mesh towards the gate and gives it the weathered wood (or, with --wood-only, only
    gives another signpost mesh the weathered wood)."""
    parser = argparse.ArgumentParser(description="Turn the subtitle signpost towards the gate.")
    parser.add_argument("repo", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wood-only", metavar="MESH", help="only give models/MESH the weathered wood")
    arguments = parser.parse_args(sys.argv[1:])
    repo = arguments.repo
    if arguments.wood_only:
        weather_wood_only(repo / "models" / arguments.wood_only)
        return
    mesh = repo / "models/MenuSignpost.mesh"
    signpost = scene_position(repo, "Signpost")
    gate = scene_position(repo, "Gate")
    with tempfile.TemporaryDirectory() as folder:
        xml_path = os.path.join(folder, "MenuSignpost.mesh.xml")
        subprocess.run([converter(), "-q", str(mesh), xml_path], check=True, cwd=folder)
        tree = ElementTree.parse(xml_path)
        root = tree.getroot()
        current = board_direction(board_positions(root))
        target = gate[:2] + numpy.array([AIM_OFFSET_X, 0.0]) - signpost[:2]
        angle = math.atan2(target[1], target[0]) - math.atan2(current[1], current[0])
        angle = math.atan2(math.sin(angle), math.cos(angle))
        if abs(angle) > 1e-5:
            turn(root, angle)
        for submesh in root.iter("submesh"):
            if submesh.get("material") == PLAIN_WOOD:
                submesh.set("material", WEATHERED_WOOD)
        tree.write(xml_path, encoding="utf-8", xml_declaration=False)
        out_path = os.path.join(folder, "MenuSignpost.mesh")
        subprocess.run([converter(), "-q", xml_path, out_path], check=True, cwd=folder)
        mesh.write_bytes(Path(out_path).read_bytes())
    print("turned the signpost by %.2f degrees; board yaw %.2f degrees" % (math.degrees(angle),
                                                                          math.degrees(math.atan2(target[1], target[0]))))


if __name__ == "__main__":
    main()
