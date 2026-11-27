#!/usr/bin/env python3
"""Acceptance checks CR12 (clips) and CR13 (portraits, icons, Dungeonbook) of the creature roster plan.

CR12: the model file of each of the 36 creatures (the MeshName of roster_plan_data.MESH) and its skeleton exist in
models/, and the skeleton holds the clips the game plays for every creature (Idle, Walk, Attack1, Die). The clip
names of the role clips (heal, buff, taunt) come from the clip mapping of the content split and are not asserted
here yet. The models of the new creatures come from the content split.

CR13: each of the 36 creatures has its portrait materials/textures/portrait-<MeshName>.png (the population panel,
the profile card and the Dungeonbook; the hand icon is the square crop of the same picture) and a Dungeonbook entry:
a shown class name and a job line in config/social-texts.cfg and a name group of config/social-names.cfg. No removed
creature has a portrait, a portrait prompt record (materials/portraits/<Mesh>.md), a tint entry in
config/portrait-tints.cfg, a job line or a name group; the model Dwarf1.mesh stays as the hero worker's.

An Ogre skeleton stores the name of a clip as plain text after the animation chunk id (0x4000, little endian) and the
chunk length; the check searches for that pattern. The expected values are the fixed data of
source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr12_cr13_assets.py
Exit 0 and "roster CR12 CR13 ok" when every item holds.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

# Clips the game plays for every creature (fixed set of this check); the game also accepts the death clip written
# "die" (CreatureReactions, CreatureCombatReactions)
BASE_CLIPS = ("Idle", "Walk", "Attack1", "Die")
CLIP_SPELLINGS = {"Die": ("Die", "die")}


def has_clip(data, clip):
    """True when the skeleton bytes hold an animation chunk with this clip name (or an accepted spelling of it)."""
    for spelling in CLIP_SPELLINGS.get(clip, (clip,)):
        if re.search(b"\x40[\x00-\xff]{4}" + re.escape(spelling.encode("ascii")) + b"\n", data) is not None:
            return True
    return False


def exists(relative):
    """True when the file exists in the repository."""
    return os.path.isfile(os.path.join(plan.ROOT, relative))


# ---------------------------------------------------------------------------------------------- CR12 clips
for name, mesh in sorted(plan.MESH.items()):
    base = mesh[:-len(".mesh")]
    check(exists("models/" + mesh), "CR12: the model models/%s of %s exists" % (mesh, name))
    skeleton = "models/" + base + ".skeleton"
    if not check(exists(skeleton), "CR12: the skeleton %s of %s exists" % (skeleton, name)):
        continue
    with open(os.path.join(plan.ROOT, skeleton), "rb") as handle:
        data = handle.read()
    missing = [clip for clip in BASE_CLIPS if not has_clip(data, clip)]
    check(not missing, "CR12: the skeleton of %s holds the clips %s (missing %s)" % (name, BASE_CLIPS, missing))

# ------------------------------------------------------------------------------- CR13 portraits, Dungeonbook
texts = plan.read("config/social-texts.cfg").splitlines()
class_names = set(line.split("\t")[1] for line in texts if line.startswith("ClassName\t"))
jobs = set(line.split("\t")[1] for line in texts if line.startswith("Job\t"))
grouped = set()
for line in plan.read("config/social-names.cfg").splitlines():
    cells = line.split("\t")
    if cells[0] == "Classes":
        grouped.update(cell.strip() for cell in cells[1:] if cell.strip())
tints = set(re.findall(r"^Mesh\t(\S+?)(?:-female|-male)?\s*$", plan.read("config/portrait-tints.cfg"), re.M))
for name, mesh in sorted(plan.MESH.items()):
    check(exists("materials/textures/portrait-%s.png" % mesh), "CR13: %s has its portrait portrait-%s.png"
          % (name, mesh))
    check(name in class_names and name in jobs and name in grouped,
          "CR13: %s has a Dungeonbook entry (shown name %s, job %s, name group %s)"
          % (name, name in class_names, name in jobs, name in grouped))
for removed in plan.REMOVED:
    mesh = removed + ".mesh"
    check(removed not in jobs and removed not in grouped, "CR13: the removed %s has no Dungeonbook entry" % removed)
    if mesh in plan.KEPT_MESH_OF_REMOVED:
        continue
    check(not exists("materials/textures/portrait-%s.png" % mesh), "CR13: the removed %s has no portrait" % removed)
    check(not exists("materials/portraits/%s.md" % removed), "CR13: the removed %s has no portrait prompt record"
          % removed)
    check(mesh not in tints, "CR13: the removed %s has no portrait tint entry" % removed)

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr12_cr13","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR12 CR13 ok")
