#!/usr/bin/env python3
"""Static check of the room ambience data of the unmade beds, altar fire, rats and turning gears (no compiler needed).

    python source/tests/check_room_deferred_looks.py

Checks that config/roomAmbienceDeferred.cfg is included by config/roomAmbience.cfg, that it has the effects the group is
meant to have, that no effect name is used twice in the room ambience files, that the files and textures
named below exist and (for meshes) have a CREDITS line. The generic checks of every config
file (keys, meshes, particle systems, textures) are in tools/check_room_ambience.py.

The config, particle, material, texture and sound files are game data of the content packages
(scripts/content_packages.py): they are read from the public tree or from the content packages, their CREDITS rows
from the CREDITS of the public tree and of the content repository. Without the content the check checks the code and
names the data part as not checked.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

CHECK = "check_room_deferred_looks"
# Effects the config file must contain
EXPECTED = ("DormitoryUnmadeBed", "TempleAltarFlame", "TempleAltarGlow", "TempleAltarEmbers", "PrisonRatRight", "PrisonRatLeft", "WorkshopGearBig", "WorkshopGearSmall")
# Files below the repository root that the group brings
FILES = ("particles/RoomAmbienceDeferred.particle", "materials/scripts/RoomAmbienceDeferred.material", "tools/gen_room_effects_art.py")
# Meshes that need a CREDITS line
MESHES = ()
# Folders of game data that may lie in a content package instead of the public tree
DATA_FOLDERS = ("config/", "gui/", "levels/", "materials/", "models/", "particles/", "sounds/")


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


def file_missing(path):
    """True when a file is missing; a game data file is looked up in the content packages too and, when the content is
    not present, named as not checked instead."""
    if content_packages.data_file(ROOT, path) is not None:
        return False
    if path.startswith(DATA_FOLDERS) and not content_packages.has_content(ROOT):
        content_packages.unchecked(CHECK, [path])
        return False
    return True


def row_unchecked(path):
    """True when the CREDITS row of a game data file cannot be checked: the content is not present (the rows of the
    moved files stand in the CREDITS of the content repository); names it as not checked."""
    if path.startswith(DATA_FOLDERS) and not content_packages.has_content(ROOT):
        content_packages.unchecked(CHECK, ["the CREDITS row of " + path])
        return True
    return False


problems = []

names = []
if present("config/roomAmbience.cfg", "config/roomAmbienceDeferred.cfg"):
    if "Include roomAmbienceDeferred.cfg" not in read("config", "roomAmbience.cfg"):
        problems.append("roomAmbience.cfg does not include roomAmbienceDeferred.cfg")

    for block in re.findall(r"\[Effect\](.*?)\[/Effect\]", read("config", "roomAmbienceDeferred.cfg"), re.S):
        found = re.search(r"^\s*Name\s+(\S+)", block, re.M)
        if found is None:
            problems.append("an effect without a name in roomAmbienceDeferred.cfg")
        else:
            names.append(found.group(1))
    for name in EXPECTED:
        if name not in names:
            problems.append("roomAmbienceDeferred.cfg lacks the effect %s" % name)

    # An effect name is used once in all room ambience files (the log and the check use it to tell effects apart)
    seen = {}
    for path in content_packages.data_glob(ROOT, "config", "roomAmbience*.cfg"):
        for found in re.finditer(r"^\s*Name\s+(\S+)", open(str(path), encoding="utf-8", errors="replace").read(), re.M):
            other = seen.setdefault(found.group(1), os.path.basename(str(path)))
            if other != os.path.basename(str(path)):
                problems.append("effect %s is in %s and in %s" % (found.group(1), other, os.path.basename(str(path))))

for path in FILES:
    if file_missing(path):
        problems.append("missing file %s" % path)

# The CREDITS of the public tree and of the content repository (the rows of the moved game data stand there)
credits = room_packages.credits_text(ROOT)
for mesh in MESHES:
    if mesh not in credits and not row_unchecked(mesh):
        problems.append("no CREDITS line for %s" % mesh)

# The condition Vacated is read from the config and needs that the target was used while it was watched
config_cpp = read("source", "render", "RoomAmbienceConfig.cpp")
if 'text == "Vacated"' not in config_cpp or "AmbienceWhen::vacated" not in config_cpp:
    problems.append("RoomAmbienceConfig.cpp does not read When Vacated")
ambience = read("source", "render", "RoomAmbience.cpp")
for needle in ("bool RoomAmbience::isIdleState", "it->second.mEverBusy = true;", "idle && (it != mBusy.end()) && it->second.mEverBusy",
               "isIdleState(effect, "):
    if needle not in ambience:
        problems.append("RoomAmbience.cpp lacks %s" % needle)
if 'isIdleLongEnough("o"' in ambience or "isIdleLongEnough(key, busy == 1, effect.mAfter)" in ambience:
    problems.append("a scan still asks isIdleLongEnough instead of isIdleState")
# The textures of the sprites and their generator
for name in ("RoomAmbFlame", "RoomAmbGear", "RoomAmbRat", "RoomAmbRatL", "RoomAmbRumple"):
    if file_missing("materials/textures/" + name + ".png"):
        problems.append("missing texture %s" % name)
if "tools/gen_room_effects_art.py" not in credits:
    problems.append("CREDITS lacks the generator of the sprites")

if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("fine (%d effects)" % len(names))
