#!/usr/bin/env python3
"""Static check of the decorations and the production rooms of the room ambience (no compiler needed).

    python source/tests/check_room_decor.py

Checks that the kind Model and the key WallSide are read from the config, that the code creates, moves and
removes decorations, that a decoration mesh has a CREDITS line, and that the config of the production rooms
(workshop, library, training hall, treasury and the hatchery coop) only names meshes, rooms and particle systems that
exist. The generic checks of the config files are in tools/check_room_ambience.py.

The config, the decoration meshes and the texture are game data of the content packages (scripts/content_packages.py):
they are read from the public tree or from the content packages. Without the content the check checks the code and
names the data part as not checked. The CREDITS rows of the moved files stand in the CREDITS of the content repository and
are checked with the content.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

CHECK = "check_room_decor"


def read(*parts):
    """Returns the text of a file below the repository root (game data from the public tree or a content package)."""
    with open(str(content_packages.resolve(ROOT, "/".join(parts))), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def present(*paths):
    """True when the game data files can be checked: all are found or the content is present (then a missing one fails
    as before); else names the missing ones as not checked."""
    missing = [path for path in paths if content_packages.data_file(ROOT, path) is None]
    if not missing or content_packages.has_content(ROOT):
        return True
    content_packages.unchecked(CHECK, missing)
    return False


problems = []

# The config format
config_h = read("source", "render", "RoomAmbienceConfig.h")
config_cpp = read("source", "render", "RoomAmbienceConfig.cpp")
kinds = re.search(r"enum class AmbienceKind\s*\{(.*?)\};", config_h, re.S).group(1)
order = re.findall(r"^\s*(\w+),?\s*$", re.sub(r"//.*", "", kinds), re.M)
if order[:3] != ["particle", "motion", "clip"] or "model" not in order:
    problems.append("AmbienceKind values changed: %s" % order)
if 'words[1] == "Model"' not in config_cpp or "AmbienceKind::model" not in config_cpp:
    problems.append("kind Model is not read from the config")
if 'key == "WallSide"' not in config_cpp or "mWallSide" not in config_h:
    problems.append("WallSide is not read from the config")

# The code
ambience = read("source", "render", "RoomAmbience.cpp")
for needle in ("bool RoomAmbience::createModel", "void RoomAmbience::moveModel", "AmbienceKind::model",
               "effect.mWallSide", "destroyEntity(emitter.mEntity)"):
    if needle not in ambience:
        problems.append("RoomAmbience.cpp lacks %s" % needle)
reconcile = ambience[ambience.index("void RoomAmbience::reconcile"):ambience.index("void RoomAmbience::playClips")]
if "it->second.mSystem != nullptr" not in reconcile:
    problems.append("reconcile does not cope with an emitter without a particle system (a decoration)")
if "createModel(effect.mMesh" not in reconcile:
    problems.append("reconcile does not create the decoration of a model effect")

# The config of the production rooms; the CREDITS of the public tree and of the content repository
credits = room_packages.credits_text(ROOT)
PRODUCTION_DATA = present("config/roomAmbienceProduction.cfg", "config/roomAmbience.cfg",
                          "materials/textures/RoomDecorSurface.png")
if PRODUCTION_DATA:
    text = read("config", "roomAmbienceProduction.cfg")
    if "Include roomAmbienceProduction.cfg" not in read("config", "roomAmbience.cfg"):
        problems.append("roomAmbience.cfg does not include roomAmbienceProduction.cfg")
    rooms = {"workshopRoom", "libraryRoom", "trainingHallRoom", "treasuryRoom"}
    found_rooms = set()
    for block in re.findall(r"\[Effect\](.*?)\[/Effect\]", text, re.S):
        name = re.search(r"^\s*Name\s+(\S+)", block, re.M).group(1)
        for match in re.findall(r"^\s*Match\s+(.*)$", block, re.M):
            found_rooms.update(rooms.intersection(match.split()))
        if re.search(r"^\s*Kind\s+Model\s*$", block, re.M):
            mesh = re.search(r"^\s*Mesh\s+(\S+)", block, re.M)
            if mesh is None or content_packages.data_file(ROOT, "models/" + mesh.group(1)) is None:
                problems.append("%s: the mesh of the decoration does not exist" % name)
            elif mesh.group(1).replace(".mesh", "") + ".mesh" not in credits:
                problems.append("%s: no CREDITS line for %s" % (name, mesh.group(1)))
    if found_rooms != rooms:
        problems.append("the production config has no effect for %s" % sorted(rooms - found_rooms))
    if "ChickenCoop" not in text:
        problems.append("the production config has no effect for the hatchery coop")
    if content_packages.data_file(ROOT, "materials/textures/RoomDecorSurface.png") is None:
        problems.append("the texture of the decorations is missing")
if PRODUCTION_DATA and ("RoomDecorSurface.png" not in credits or "gen_room_decor_texture.py" not in credits):
    problems.append("CREDITS lacks the decoration texture or its generator")

if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("fine")
