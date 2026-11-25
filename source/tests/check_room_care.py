#!/usr/bin/env python3
"""Static check of the room ambience data of the care rooms (dormitory, temple, prison, torture room, crypt, arena) (no compiler needed).

    python source/tests/check_room_care.py

Checks that config/roomAmbienceCare.cfg is included by config/roomAmbience.cfg, that it has the effects the group is
meant to have, that no effect name is used twice in the room ambience files, that the files and textures
named below exist and (for meshes) have a CREDITS line. The generic checks of every config
file (keys, meshes, particle systems, textures) are in tools/check_room_ambience.py.

The ambience files, particles, materials, textures and meshes live in content packages (found through
scripts/content_packages.py); their CREDITS lines stand in the CREDITS of the content repository
(room_packages.credits_text). Without the content the check names those parts as not checked; with the content present
a missing file or line is a problem as before.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402
# Effects the config file must contain
EXPECTED = ("DormitoryLanternPool", "DormitoryMotes", "DormitoryBedCreak", "DormitorySleepZ", "DormitoryBreathing", "TempleIncense", "TempleLightShaft", "TempleFloorRune", "TemplePrayerMotes", "PrisonDrip", "PrisonFlies", "PrisonSkullGlint", "PrisonBarsDust", "PrisonDoorOpen", "TortureCoals", "TortureCreak", "TortureChains", "TortureFrameTurns", "TortureSteam", "TortureSparks", "CryptMist", "CryptGraveLight", "CryptStatueGlimmer", "CryptWisp", "ArenaShieldsSway", "ArenaShieldGlint", "ArenaSand", "ArenaFightDust", "ArenaShieldsRattle", "ArenaBanners", "CryptRevivalLight")
# Files below the repository root that the group brings
FILES = ("particles/RoomAmbienceCare.particle", "materials/scripts/RoomAmbienceCare.material", "materials/textures/RoomAmbZ.png", "models/ArenaBanner.mesh", "models/PrisonDoor.mesh", "models/PrisonDoor.skeleton")
# Meshes that need a CREDITS line
MESHES = ("models/ArenaBanner.mesh", "models/PrisonDoor.mesh")


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
care_cfg = read_data("config", "roomAmbienceCare.cfg")
if (ambience_cfg is None or care_cfg is None) and not with_content:
    not_checked.append("config/roomAmbience.cfg and config/roomAmbienceCare.cfg")
    care_cfg = ""
else:
    # With the content present a missing file fails here as before (read() of the public path)
    ambience_cfg = ambience_cfg if ambience_cfg is not None else read("config", "roomAmbience.cfg")
    care_cfg = care_cfg if care_cfg is not None else read("config", "roomAmbienceCare.cfg")
    if "Include roomAmbienceCare.cfg" not in ambience_cfg:
        problems.append("roomAmbience.cfg does not include roomAmbienceCare.cfg")

names = []
for block in re.findall(r"\[Effect\](.*?)\[/Effect\]", care_cfg, re.S):
    found = re.search(r"^\s*Name\s+(\S+)", block, re.M)
    if found is None:
        problems.append("an effect without a name in roomAmbienceCare.cfg")
    else:
        names.append(found.group(1))
for name in EXPECTED if not not_checked else ():
    if name not in names:
        problems.append("roomAmbienceCare.cfg lacks the effect %s" % name)

# An effect name is used once in all room ambience files (the log and the check use it to tell effects apart); the
# files of the public tree and of the content packages
seen = {}
for path in content_packages.data_glob(ROOT, "config", "roomAmbience*.cfg"):
    for found in re.finditer(r"^\s*Name\s+(\S+)", open(str(path), encoding="utf-8", errors="replace").read(), re.M):
        other = seen.setdefault(found.group(1), os.path.basename(str(path)))
        if other != os.path.basename(str(path)):
            problems.append("effect %s is in %s and in %s" % (found.group(1), other, os.path.basename(str(path))))

for path in FILES:
    if content_packages.data_file(ROOT, path) is None:
        if with_content:
            problems.append("missing file %s" % path)
        else:
            not_checked.append(path)

# the public CREDITS and, with the content, the CREDITS of the content repository
credits = room_packages.credits_text(ROOT)
for mesh in MESHES:
    if not with_content and content_packages.data_file(ROOT, mesh) is None:
        not_checked.append("CREDITS line of " + mesh)
    elif mesh not in credits:
        problems.append("no CREDITS line for %s" % mesh)

content_packages.unchecked("check_room_care", not_checked)
if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("fine (%d effects)" % len(names))
