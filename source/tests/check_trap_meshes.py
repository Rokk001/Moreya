#!/usr/bin/env python3
"""Static check that every trap type has its own mesh (no compiler needed).

    python source/tests/check_trap_meshes.py

Reads the mesh name of every trap in source/traps/Trap*.cpp (and of every door type in TrapDoor.cpp), checks that no
two types share a mesh, that the .mesh file exists, that all its materials are defined in a material script and that
the own meshes are listed in CREDITS. The guard banner keeps its banner mesh.
The meshes and material scripts lie in the content packages (scripts/content_packages.py); without the content the
mesh names of the code are checked and the mesh files are named as not checked.
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402
problems = []
#: True when the content packages are present: the mesh files are checked only then
CONTENT = content_packages.has_content(ROOT)

TRAPS = {
    "Cannon": "Cannon",
    "Spike": "Spiketrap",
    "Boulder": "Boulder",
    "Alarm": "AlarmTrap",
    "Fear": "FearTrap",
    "Gas": "GasTrap",
    "Lightning": "LightningTrap",
    "Fireburst": "FireburstTrap",
    "Freeze": "FrostTrap",
    "WatchBanner": "WarBanner",
    "Trigger": "TriggerTrap",
}
DOORS = ("WoodenDoor", "DoorIronbound", "DoorSteel", "DoorBarricade", "DoorSecret", "DoorRune")


def read(*parts, binary=False):
    """Returns the text or bytes of a file below the repository root."""
    with open(os.path.join(ROOT, *parts), "rb" if binary else "r", **({} if binary else {"encoding": "utf-8"})) as handle:
        return handle.read()


def mesh_file(mesh):
    """The .mesh file of the public tree or of a content package, or None when it is not there."""
    return content_packages.data_file(ROOT, "models/" + mesh + ".mesh")


def mesh_missing(mesh):
    """True when a .mesh file is missing although the content is present (without the content it is not checked)."""
    return CONTENT and mesh_file(mesh) is None


# The public CREDITS and, with the content, the CREDITS of the content repository (rows of moved files)
credits = room_packages.credits_text(ROOT)
material_text = "".join(p.read_text(encoding="utf-8")
                        for p in content_packages.data_glob(ROOT, "materials/scripts", "*.material"))
defined = set(re.findall(r"^\s*material\s+(\S+)", material_text, re.M))

seen = {}
for trap, expected in TRAPS.items():
    source = read("source", "traps", "Trap%s.cpp" % trap)
    match = re.search(r'getMeshName\(\) const override\s*\{(?:\s*//[^\n]*)*\s*static const std::string \w+ = "([^"]+)";', source)
    if not match:
        problems.append("Trap%s.cpp: no mesh name found" % trap)
        continue
    mesh = match.group(1)
    if mesh != expected:
        problems.append("Trap%s uses mesh %s, expected %s" % (trap, mesh, expected))
    if mesh in seen:
        problems.append("Trap%s shares the mesh %s with Trap%s" % (trap, mesh, seen[mesh]))
    seen[mesh] = trap
    if not CONTENT:
        continue
    path = mesh_file(mesh)
    if path is None:
        problems.append("models/%s.mesh is missing" % mesh)
        continue
    data = path.read_bytes()
    # own static meshes (the ones made by trap_meshes.py) use materials of TrapTypes.material
    if mesh.endswith("Trap") and mesh != "Spiketrap":
        used = [m for m in defined if m.startswith("Trap") and m.encode() in data]
        if not used:
            problems.append("models/%s.mesh uses none of the TrapTypes materials" % mesh)
        if b".skeleton" in data:
            problems.append("models/%s.mesh links a skeleton, it should be static" % mesh)
        if ("models/%s.mesh" % mesh) not in credits:
            problems.append("models/%s.mesh has no CREDITS entry" % mesh)

door_source = read("source", "traps", "TrapDoor.cpp")
door_meshes = re.findall(r'static const std::string mesh\w+ = "([^"]+)";', door_source)
if sorted(door_meshes) != sorted(DOORS):
    problems.append("TrapDoor.cpp mesh names %s differ from %s" % (sorted(door_meshes), sorted(DOORS)))
for mesh in DOORS:
    if mesh_missing(mesh):
        problems.append("models/%s.mesh is missing" % mesh)

for name in ("AlarmTrap", "FearTrap", "GasTrap", "LightningTrap", "FireburstTrap", "FrostTrap", "TriggerTrap"):
    if mesh_missing(name):
        problems.append("models/%s.mesh is missing" % name)

if not CONTENT:
    content_packages.unchecked("check_trap_meshes", ["trap and door mesh files", "materials/scripts", "their CREDITS rows"])
if problems:
    print("check_trap_meshes: %d problem(s)" % len(problems))
    for line in problems:
        print("  " + line)
    sys.exit(1)
print("check_trap_meshes: ok (%d trap types and %d door types, every type has its own mesh)" % (len(TRAPS), len(DOORS)))

