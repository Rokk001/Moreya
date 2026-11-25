#!/usr/bin/env python3
"""Static check of the cannon recoil clip and the barricade collapse clip (no compiler needed).

    python source/tests/check_trap_clips.py

Checks that the cannon mesh is linked to its skeleton with the clip Triggered, that the shared door
skeleton has the new clip Collapse next to Open, Close and Destroyed, that the cannon plays its clip when
it fires, that the client lets a destroyed barricade collapse, and that the new files are in CREDITS.
The meshes and skeletons lie in the content packages (scripts/content_packages.py); without the content the code
part is checked and the model part is named as not checked.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402


def read(*parts, binary=False):
    """The text or bytes of a file of the public tree."""
    with open(os.path.join(ROOT, *parts), "rb" if binary else "r", **({} if binary else {"encoding": "utf-8"})) as handle:
        return handle.read()


def model(name):
    """The bytes of a model file of the public tree or of a content package, or None without the content."""
    path = content_packages.data_file(ROOT, "models/" + name)
    return None if path is None else path.read_bytes()


problems = []
models = {name: model(name) for name in ("Cannon.mesh", "Cannon.skeleton", "WoodenDoor.skeleton")}
if None in models.values():
    content_packages.unchecked("check_trap_clips", ["models/" + name for name, data in models.items() if data is None])
else:
    if b"Cannon.skeleton" not in models["Cannon.mesh"]:
        problems.append("Cannon.mesh has no link to Cannon.skeleton")
    skeleton = models["Cannon.skeleton"]
    for name in (b"Triggered", b"Barrel", b"Root"):
        if name not in skeleton:
            problems.append("Cannon.skeleton lacks " + name.decode())
    door = models["WoodenDoor.skeleton"]
    for name in (b"Open", b"Close", b"Destroyed", b"Collapse", b"RootBone", b"LeftDoorBone", b"RigthDoorBone"):
        if name not in door:
            problems.append("WoodenDoor.skeleton lacks " + name.decode())

cannon = read("source", "traps", "TrapCannon.cpp")
shoot = cannon[cannon.index("bool TrapCannon::shoot"):cannon.index("TrapEntity* TrapCannon::getTrapEntity")]
if 'setAnimationState("Triggered", false)' not in shoot:
    problems.append("the cannon does not play its clip when it fires")

ambience = read("source", "render", "RoomAmbience.cpp")
if 'startCollapse(tileX, tileY, typeName)' not in ambience or '"Collapse"' not in ambience or "updateCollapses(dt)" not in ambience:
    problems.append("the client does not let a destroyed barricade collapse")
if "destroyCollapse(collapse)" not in ambience[ambience.index("void RoomAmbience::stopAll"):ambience.index("void RoomAmbience::update(")]:
    problems.append("stopAll does not remove the collapsing barricades")

# The public CREDITS and, with the content, the CREDITS of the content repository (rows of moved files)
credits = room_packages.credits_text(ROOT)
for name in ("models/Cannon.skeleton", "models/WoodenDoor.skeleton"):
    # The rows of the moved models stand in the CREDITS of the content repository
    if None not in models.values() and name not in credits:
        problems.append(name + " is not in CREDITS")

if problems:
    for problem in problems:
        print("PROBLEM: " + problem)
    sys.exit(1)
print("fine")
