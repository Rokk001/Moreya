"""Check that only the faction worker class is created at the dungeon heart.

Source part: the heart spawn in GameMap.cpp takes its class from
Seat::getWorkerClassToSpawn(), which returns the seat default worker class, and
no other GameMap function that touches the heart tile creates a creature.
Level part: Brackenford and the first skirmish level place no non-worker
creature at or next to a heart tile at start and no trigger spawns one there.
Run with python -I.

The levels are content (wing 1 and core-levels packages, found through scripts/campaign_packages.py and
scripts/content_packages.py); the first skirmish level is taken over the public tree and the packages, and a level that
is not present is named as not checked.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402
NEAR = 3  # tiles (Chebyshev distance) counted as "next to the heart"
WORKER_CLASS = "DefaultWorker"


def read(rel):
    return (repo / rel).read_text(encoding="utf-8")


def functions(text):
    """Split a C++ file into top-level function chunks (ends at a line holding only a closing brace)."""
    return re.split(r"\n\}\n", text)


# ---- source ----
game_map = read("source/gamemap/GameMap.cpp")
seat_h = read("source/game/Seat.h")
assert re.search(r"getWorkerClassToSpawn\(\)\s*\{\s*return mDefaultWorkerClass;\s*\}", seat_h), \
    "getWorkerClassToSpawn must return the seat default worker class"

heart_funcs = [f for f in functions(game_map) if "getHeartTile()" in f and "new Creature(" in f]
assert len(heart_funcs) == 1, f"expected exactly one GameMap function creating creatures at a heart tile, got {len(heart_funcs)}"
body = heart_funcs[0]
assert "void GameMap::updateSeatAutoWorkers(" in body, "heart spawn must be the worker spawn function"
assert "classToSpawn = seat->getWorkerClassToSpawn();" in body
creations = re.findall(r"new Creature\(([^)]*)\)", body)
assert creations == ["this, classToSpawn, seat"], creations
assert "getNextFighterClassToSpawn" not in body and "getClassDescription" not in body
assert "setPosition(spawnPosition)" in body and "heartTile->getX()" in body


# ---- levels ----
def section(text, name):
    m = re.search(r"^\[%s\]\n(.*?)^\[/%s\]" % (name, name), text, re.S | re.M)
    return m.group(1) if m else ""


def heart_tiles(text):
    tiles = []
    for block in re.findall(r"^\[Room\]\n(.*?)^\[/Room\]", section(text, "Rooms") or text, re.S | re.M):
        lines = block.splitlines()
        if not lines:
            continue
        head = lines[0].split()
        if len(head) >= 2 and head[1].startswith("DungeonTemple"):
            for ln in lines[1:]:
                p = ln.split()
                if len(p) == 2 and all(x.lstrip("-").isdigit() for x in p):
                    tiles.append((int(p[0]), int(p[1])))
    return tiles


def near(x, y, tiles):
    return any(max(abs(x - tx), abs(y - ty)) <= NEAR for tx, ty in tiles)


def check_level(rel, path):
    """Checks the level file at path (named rel in the messages): no non-worker at or next to a heart."""
    text = path.read_text(encoding="utf-8")
    hearts = heart_tiles(text)
    assert hearts, f"{rel}: no heart room found"
    report = {"hearts": len(hearts), "near_workers": [], "script_spawns": []}
    for line in section(text, "Creatures").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        x, y, cls = float(f[3]), float(f[4]), f[6]
        if near(round(x), round(y), hearts):
            assert cls == WORKER_CLASS, f"{rel}: non-worker {cls} {f[1]} at heart ({x},{y})"
            report["near_workers"].append(f[1])
    for m in re.finditer(r"^Action\tspawn\t(\S+)\t(-?\d+)\t(-?\d+)\t(\S+)\t(.*)$", text, re.M):
        x, y = int(m.group(2)), int(m.group(3))
        classes = [c.split(":")[0] for c in m.group(5).split("\t")]
        report["script_spawns"].append((x, y, classes))
        if near(x, y, hearts):
            assert all(c == WORKER_CLASS for c in classes), f"{rel}: script spawns {classes} at heart ({x},{y})"
    return report


# The first of the skirmish levels of the public tree and of the content packages; without the content packages the
# first level of the whole set is not known, so the skirmish level is named as not checked
levels = ["levels/campaign/wing1/Brackenford.level"]
if content_packages.has_content(repo):
    levels.append("levels/skirmish/" + content_packages.data_glob(repo, "levels/skirmish", "*.level")[0].name)
else:
    content_packages.unchecked("check_heart_spawn_workers_only", ["levels/skirmish (first skirmish level)"])
for rel in levels:
    # A wing level lies in its wing package under its own name, a skirmish level in the public tree or core-levels
    path = campaign_packages.level_file(repo, rel)
    if path is None:
        content_packages.unchecked("check_heart_spawn_workers_only", [rel])
        continue
    print(rel, check_level(rel, path))

print("check_heart_spawn_workers_only: ok")
