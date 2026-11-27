#!/usr/bin/env python3
"""Static check of the trap and door sounds, the lock glow and the build and sell effects (no compiler needed).

    python source/tests/check_trap_door_polish.py

Checks that every sound family of the config has a sound file, that every synthesized sound file is used by the
config and has a CREDITS line, that the config reader knows the new keys, and that the declarations in the
headers match the definitions in the sources.
The config, sounds, particles, materials, textures and meshes lie in the content packages
(scripts/content_packages.py); without the content the code part is checked and the content part is named as not
checked.
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402


def read(*parts):
    """Returns the text of a file below the repository root."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def content(*parts):
    """Returns the text of a game data file of the public tree or of a content package, or None without the content."""
    path = content_packages.data_file(ROOT, "/".join(parts))
    return None if path is None else path.read_text(encoding="utf-8")


def data_exists(relative):
    """True when a game data file is in the public tree or in a content package."""
    return content_packages.data_file(ROOT, relative) is not None


problems = []
# The public CREDITS and, with the content, the CREDITS of the content repository (rows of moved files)
credits = room_packages.credits_text(ROOT)
config = content("config", "roomAmbienceTraps.cfg")
if config is None:
    content_packages.unchecked("check_trap_door_polish", ["config/roomAmbienceTraps.cfg", "sounds/Spatial"])
    config = ""
families = set(re.findall(r"^\s*Family\s+(\S+)", config, re.M))
for family in sorted(families):
    if not content_packages.data_glob(ROOT, "sounds/Spatial/" + family, "*.ogg"):
        problems.append("no sound file for family %s" % family)

for kind in ("Traps", "Doors"):
    for path in content_packages.data_glob(ROOT, "sounds/Spatial/" + kind, "*/*/Fx*.ogg"):
        relative = content_packages.relative_path(ROOT, path)
        family = "/".join(relative.split("/")[2:5])
        if family not in families:
            problems.append("sound %s is not used by the config" % relative)
        if relative not in credits:
            problems.append("sound %s has no CREDITS line" % relative)

if content_packages.data_file(ROOT, "config/roomAmbienceTraps.cfg") is not None:
    # The cannon fires with a sound of the server, everything else has a Fire sound or is listed here
    for name in ("Spike", "Boulder", "Alarm", "Fear", "Gas", "Lightning", "Fireburst", "Freeze", "Trigger"):
        for role in ("Fire", "Idle", "Reload"):
            if "Traps/%s/%s" % (name, role) not in families:
                problems.append("trap %s has no %s sound in the config" % (name, role))
    if "Traps/Lightning/Crackle" not in families:
        problems.append("the lightning trap has no crackle sound in the config")
    if not re.search(r"Traps/Lightning/Fire.*?Traps/Lightning/Crackle", config, re.S):
        problems.append("the crackle of the lightning trap is not an effect after the spark")
    for name in ("Wooden", "Ironbound", "Steel", "Secret", "Runed"):
        for role in ("Open", "Close", "Hit", "Break"):
            if "Doors/%s/%s" % (name, role) not in families:
                problems.append("door %s has no %s sound in the config" % (name, role))
    for role in ("Hit", "Break"):
        if "Doors/Barricade/%s" % role not in families:
            problems.append("barricade has no %s sound in the config" % role)

reader = read("source", "render", "RoomAmbienceConfig.cpp")
for text in ('"Locked"', '"Sound"', '"Family"', '"Delay"'):
    if text not in reader:
        problems.append("the config reader does not know %s" % text)

ambience_h = read("source", "render", "RoomAmbience.h")
ambience = read("source", "render", "RoomAmbience.cpp")
for text in ("void playSound(", "void updatePendingSounds();", "mPendingSounds;", "mWreckedUntil;"):
    if text not in ambience_h:
        problems.append("RoomAmbience.h lacks %s" % text)
for text in ("void RoomAmbience::playSound(", "void RoomAmbience::updatePendingSounds()", "updatePendingSounds();",
             "AmbienceWhen::locked", "AmbienceKind::sound", '"TrapBuilt"', '"TrapSold"', "getAnimationStateName()"):
    if text not in ambience:
        problems.append("RoomAmbience.cpp lacks %s" % text)
if '#include "sound/SoundEffectsManager.h"' not in ambience:
    problems.append("RoomAmbience.cpp does not include the sound manager")

door_h = read("source", "entities", "DoorEntity.h")
door = read("source", "entities", "DoorEntity.cpp")
if "setAnimationState(const std::string& state" not in door_h or "using MovableGameEntity::setAnimationState;" not in door_h:
    problems.append("DoorEntity.h does not declare the setAnimationState override")
if "void DoorEntity::setAnimationState(" not in door or '"DoorOpen"' not in door or '"DoorClose"' not in door:
    problems.append("DoorEntity.cpp does not raise DoorOpen and DoorClose")
if "getAnimationStateName()" not in read("source", "entities", "MovableGameEntity.h"):
    problems.append("MovableGameEntity.h has no getAnimationStateName")

# Particle systems of the new effects exist
particles = content("particles", "RoomAmbienceTraps.particle")
if particles is None:
    content_packages.unchecked("check_trap_door_polish", ["particles/RoomAmbienceTraps.particle"])
else:
    for system in ("RoomAmbLockGlow", "RoomAmbRevealGlow"):
        if "particle_system %s" % system not in particles:
            problems.append("particle system %s is missing" % system)

# Own meshes of the door types: file, assignment in TrapDoor.cpp, materials and textures
trap_door = read("source", "traps", "TrapDoor.cpp")
material_text = content("materials", "scripts", "DoorTypes.material")
if material_text is None:
    content_packages.unchecked("check_trap_door_polish", ["door meshes", "materials/scripts/DoorTypes.material"])
for mesh in ("DoorIronbound", "DoorSteel", "DoorBarricade", "DoorSecret", "DoorRune"):
    if material_text is not None and not data_exists("models/" + mesh + ".mesh"):
        problems.append("models/%s.mesh is missing" % mesh)
    if ('std::string mesh%s = "%s"' % (mesh[4:], mesh)) not in trap_door:
        problems.append("TrapDoor.cpp does not use the mesh %s" % mesh)
for material in ("DoorIronboundWood", "DoorMetal", "DoorSteel", "DoorBarricade", "DoorSecret", "DoorRune", "DoorRuneGlow"):
    if material_text is not None and "material %s" % material not in material_text:
        problems.append("material %s is not defined" % material)
    # The rows of the moved textures stand in the CREDITS of the content repository
    if material_text is not None and "textures/%s.png" % material not in credits:
        problems.append("texture %s has no CREDITS line" % material)
for texture in re.findall(r"^\s*texture\s+(\S+)", material_text or "", re.M):
    if not data_exists("materials/textures/" + texture):
        problems.append("texture %s is missing" % texture)

if problems:
    for problem in problems:
        print("PROBLEM: " + problem)
    sys.exit(1)
print("fine")
