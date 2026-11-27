#!/usr/bin/env python3
"""Static check of the room ambience data of the temple bell, the converted flash and the hurt heart (no compiler needed).

    python source/tests/check_room_client_moments.py

Checks that config/roomAmbienceDeferred.cfg is included by config/roomAmbience.cfg, that it has the effects the group is
meant to have, that no effect name is used twice in the room ambience files, that the files and textures
named below exist and (for meshes) have a CREDITS line. The generic checks of every config
file (keys, meshes, particle systems, textures) are in tools/check_room_ambience.py.

The ambience files and the texture live in content packages, the gong in the temple room package (found through
scripts/content_packages.py). Without the content the check names those parts as not checked and checks the source
wiring; with the content present a missing file is a problem as before.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import room_packages  # noqa: E402
import content_packages  # noqa: E402
# Effects the config file must contain
EXPECTED = ("TempleGongRing", "TempleBellSparks", "ConvertedFlash", "ConvertedRing", "ConvertedSparks", "HeartHurtPulse", "HeartHurtDrops", "HeartLowBeatSound")
# Files below the repository root that the group brings
FILES = ("sounds/Spatial/Rooms/Temple/Gong/Gong01.ogg", "materials/textures/RoomAmbSoftRing.png")
# Files that need a CREDITS line (the CREDITS file lists the sounds by their folder below sounds/)
MESHES = ("Spatial/Rooms/Temple/Gong/",)


def read(*parts):
    """Returns the text of a file below the repository root."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def read_data(*parts):
    """Returns the text of a game data file (public tree or content package), or None when it is not there."""
    path = content_packages.data_file(ROOT, "/".join(parts))
    if path is None:
        return None
    with open(str(path), encoding="utf-8", errors="replace") as handle:
        return handle.read()


problems = []
# Parts that need the content and are not checked because it is not present
not_checked = []
with_content = content_packages.has_content(ROOT)

ambience_cfg = read_data("config", "roomAmbience.cfg")
deferred_cfg = read_data("config", "roomAmbienceDeferred.cfg")
if (ambience_cfg is None or deferred_cfg is None) and not with_content:
    not_checked.append("config/roomAmbience.cfg and config/roomAmbienceDeferred.cfg")
    deferred_cfg = None
else:
    # With the content present a missing file fails here as before (read() of the public path)
    ambience_cfg = ambience_cfg if ambience_cfg is not None else read("config", "roomAmbience.cfg")
    deferred_cfg = deferred_cfg if deferred_cfg is not None else read("config", "roomAmbienceDeferred.cfg")
    if "Include roomAmbienceDeferred.cfg" not in ambience_cfg:
        problems.append("roomAmbience.cfg does not include roomAmbienceDeferred.cfg")

names = []
for block in re.findall(r"\[Effect\](.*?)\[/Effect\]", deferred_cfg or "", re.S):
    found = re.search(r"^\s*Name\s+(\S+)", block, re.M)
    if found is None:
        problems.append("an effect without a name in roomAmbienceDeferred.cfg")
    else:
        names.append(found.group(1))
for name in EXPECTED if deferred_cfg is not None else ():
    if name not in names:
        problems.append("roomAmbienceDeferred.cfg lacks the effect %s" % name)

# An effect name is used once in all room ambience files (the log and the check use it to tell effects apart); the
# files of the public tree and of the content packages
seen = {}
for path in content_packages.data_glob(ROOT, "config", "roomAmbience*.cfg"):
    for found in re.finditer(r"^\s*Name\s+(\S+)", open(str(path), encoding="utf-8", errors="replace").read(), re.M):
        other = seen.setdefault(found.group(1), os.path.basename(str(path)))
        if other != os.path.basename(str(path)):
            problems.append("effect %s is in %s and in %s" % (found.group(1), other, os.path.basename(str(path))))

# The gong comes from the temple room package: read there when the package is present, not checked without it; the
# texture comes from a content package
for path in FILES:
    if room_packages.is_missing_packaged(ROOT, path):
        not_checked.append(path)
        continue
    if content_packages.data_file(ROOT, path) is None:
        if with_content:
            problems.append("missing file %s" % path)
        else:
            not_checked.append(path)

credits = room_packages.credits_text(ROOT) if room_packages.has_room(ROOT, "Temple") else read("CREDITS")
MESHES = tuple(mesh for mesh in MESHES if room_packages.has_room(ROOT, "Temple") or "Temple/Gong" not in mesh)
for mesh in MESHES:
    if mesh not in credits:
        problems.append("no CREDITS line for %s" % mesh)

# The key Sound is read and played with the particles of an event
config_cpp = read("source", "render", "RoomAmbienceConfig.cpp")
if 'key == "Sound"' not in config_cpp or "mSound" not in read("source", "render", "RoomAmbienceConfig.h"):
    problems.append("the key Sound is not read from the config")
ambience = read("source", "render", "RoomAmbience.cpp")
if "playSpatialSound(effect.mSound," not in ambience or "mExtras.reset();" not in ambience:
    problems.append("RoomAmbience.cpp does not play the sound of an event effect or does not reset the extras")
# The moments are started by the watcher, from what the client already knows
extras = read("source", "render", "RoomAmbienceExtras.cpp")
for needle in ('"TempleHealed"', '"ConvertedFlash"', '"HeartHurt"', '"HeartLowBeat"', "getOverlayHealthValue()", "getSeatPrison()",
               "mInitialized && ((clock - snapshot.mLastEvent) >= CREATURE_EVENT_COOLDOWN)", "fraction < HEART_HURT_FRACTION"):
    if needle not in extras:
        problems.append("RoomAmbienceExtras.cpp lacks %s" % needle)
# The low beat is a sound of the heart hit
if deferred_cfg is not None and "Family      Rooms/Heart/Hit" not in deferred_cfg:
    problems.append("the low beat does not use the sound of the heart hit")

content_packages.unchecked("check_room_client_moments", not_checked)
if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("fine (%d effects)" % len(names))
