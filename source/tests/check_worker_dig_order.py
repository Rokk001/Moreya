#!/usr/bin/env python3
"""Non-compiling check that Zivs dig earth walls while marked gold is reachable (INGAME-QS-12 K3, T-W1).

Cause in build 0.7.4.79: a Ziv kept its gold or gem wall reserved through every delivery to the treasury and came back
to it until the wall was empty. A gold wall holds 3000 gold, 120 dig steps of 25 gold and 30 loads of 100; an earth wall
takes 5 dig steps; a gem wall never runs out. A Ziv that once took a gold wall therefore did not choose a wall again for
a very long time, and with the even spread of Automatic the dig job was filled by these Zivs, so no earth wall was dug.

A Python model of the dig job (the same model as the Boost test 00-WorkerDigOrder, with the rules of
source/game/WorkerDigOrder.h) plays fixed scenarios: the observed case with the rules of build 0.7.4.79 (no earth wall
before a gold wall is empty), the same case with the fix and "gold first" off (every earth wall dug while every gold
wall still holds gold), "gold first" on (gold walls before earth walls, as before) and gem walls. The C++ sources and
the build lists are checked for the statements that apply these rules. Nothing is compiled and the game is not
started; the integration build compiles the code and runs the Boost test 00-WorkerDigOrder.

Usage: python -I source/tests/check_worker_dig_order.py
Exit 0 and "worker dig order ok" when every item holds.
"""
import itertools
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = time.perf_counter()
FAILURES = []


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def function(source, signature):
    """Returns the body of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise AssertionError("no end of " + signature)


def check(condition, message):
    """Records a failed item."""
    if not condition:
        FAILURES.append(message)


# ------------------------------------------------------------------------------------------------ model
# Values of creatures.cfg (Ziv dig rate 20, MaxGoldCarryable 100) and global.cfg (GoldPerSeamTile 3000,
# GoldPerDigStep 25, GemGoldPerDigStep 16.67), counted once for this branch
EARTH_DIG_STEPS = 5
GOLD_PER_WALL = 3000.0
GOLD_PER_STEP = 25.0
GEM_GOLD_PER_STEP = 16.67
GOLD_CAPACITY = 100.0
MAX_TURNS = 20000


def group(gold_first, gold_or_gem, occupied, load_taken, after_delivery):
    """Mirror of WorkerDigOrder::group."""
    taken = occupied or ((not gold_first) and after_delivery and load_taken)
    return (2 if gold_first and not gold_or_gem else 0) + (1 if taken else 0)


def ranks_before(have_best, candidate_group, here, distance, best_group, best_here, best_distance):
    """Mirror of WorkerDigOrder::ranksBefore."""
    if not have_best:
        return True
    if candidate_group != best_group:
        return candidate_group < best_group
    if here != best_here:
        return here
    return distance < best_distance


def old_ranks_before(have_best, candidate_group, here, distance, best_group, best_standing, best_distance):
    """The rank of build 0.7.4.79 in CreatureActionSearchTileToDig."""
    return not (have_best and (candidate_group > best_group or
                               (candidate_group == best_group and best_standing and not here) or
                               (candidate_group == best_group and best_standing == here and distance >= best_distance)))


def keeps_wall_for_delivery(gold_first):
    """Mirror of WorkerDigOrder::keepsWallForDelivery."""
    return gold_first


class DigRun:
    """The model run of the dig job: walls, Zivs, the treasury at (0, 0) and the gold mined."""

    def __init__(self, gold_first, fixed):
        self.walls = []
        self.zivs = []
        self.gold_first = gold_first
        # False runs the rules of build 0.7.4.79
        self.fixed = fixed
        self.gold_mined = 0.0

    def add_wall(self, kind, x):
        """Adds a marked wall with its dig place on the corridor at x."""
        left = float(EARTH_DIG_STEPS) if kind == "earth" else (GOLD_PER_WALL if kind == "gold" else 0.0)
        self.walls.append({"kind": kind, "x": x, "left": left, "load_taken": False, "diggers": 0, "dug": -1})

    def add_ziv(self, x):
        """Adds a Ziv with the dig job at x that has not chosen a wall yet."""
        self.zivs.append({"x": x, "state": "choosing", "wall": -1, "walk": 0, "carried": 0.0, "after": False})


def choose_wall(run, ziv):
    """The choice of CreatureActionSearchTileToDig with the rules of WorkerDigOrder."""
    best, best_group, best_here, best_distance = -1, 5, False, 0.0
    for index, wall in enumerate(run.walls):
        if wall["dug"] >= 0:
            continue
        candidate = group(run.gold_first, wall["kind"] != "earth", wall["diggers"] > 0, wall["load_taken"],
                          run.fixed and ziv["after"])
        here = ziv["x"] == wall["x"]
        distance = float((ziv["x"] - wall["x"]) ** 2)
        if not ranks_before(best >= 0, candidate, here, distance, best_group, best_here, best_distance):
            continue
        best, best_group, best_here, best_distance = index, candidate, here, distance
    if best < 0:
        return
    wall = run.walls[best]
    wall["diggers"] += 1
    ziv.update({"wall": best, "after": False, "walk": abs(ziv["x"] - wall["x"]), "state": "to_wall"})


def start_delivery(run, ziv):
    """The full load of CreatureActionDigTile: with the fix and "gold first" off the Ziv leaves its wall."""
    wall = run.walls[ziv["wall"]]
    keeps = (not run.fixed) or keeps_wall_for_delivery(run.gold_first)
    if not keeps or wall["dug"] >= 0:
        if run.fixed and not run.gold_first:
            wall["load_taken"] = True
            ziv["after"] = True
        if wall["dug"] < 0:
            wall["diggers"] -= 1
        ziv["wall"] = -1
    ziv.update({"walk": abs(ziv["x"]), "state": "to_treasury"})


def dig_step(run, ziv, turn):
    """One dig step of the Ziv on its wall."""
    wall = run.walls[ziv["wall"]]
    if wall["dug"] >= 0:
        ziv.update({"wall": -1, "state": "choosing"})
        return
    if wall["kind"] == "earth":
        wall["left"] -= 1.0
    else:
        gold = GOLD_PER_STEP if wall["kind"] == "gold" else GEM_GOLD_PER_STEP
        if wall["kind"] == "gold":
            gold = min(gold, wall["left"])
            wall["left"] -= gold
        ziv["carried"] += gold
        run.gold_mined += gold
    if wall["kind"] != "gem" and wall["left"] <= 0.0:
        wall.update({"dug": turn, "diggers": 0})
        ziv["state"] = "choosing"
    if ziv["carried"] >= GOLD_CAPACITY:
        start_delivery(run, ziv)
        return
    if wall["dug"] >= 0:
        ziv["wall"] = -1


def run_turn(run, turn):
    """One turn of every Ziv; walking takes one turn per tile."""
    for ziv in run.zivs:
        state = ziv["state"]
        if state == "choosing":
            choose_wall(run, ziv)
        elif state in ("to_wall", "back"):
            if ziv["walk"] > 0:
                ziv["walk"] -= 1
                continue
            ziv.update({"x": run.walls[ziv["wall"]]["x"], "state": "digging"})
            dig_step(run, ziv, turn)
        elif state == "digging":
            dig_step(run, ziv, turn)
        elif state == "to_treasury":
            if ziv["walk"] > 0:
                ziv["walk"] -= 1
                continue
            ziv.update({"x": 0, "carried": 0.0})
            if ziv["wall"] >= 0 and run.walls[ziv["wall"]]["dug"] < 0:
                ziv.update({"walk": abs(run.walls[ziv["wall"]]["x"]), "state": "back"})
            else:
                ziv.update({"wall": -1, "state": "choosing"})


def first_dug(run, kind):
    """The turn the first wall of a kind was dug out, -1 when none was."""
    turns = [wall["dug"] for wall in run.walls if wall["kind"] == kind and wall["dug"] >= 0]
    return min(turns) if turns else -1


def last_dug(run, kind):
    """The turn the last wall of a kind was dug out, -1 while one of them stands."""
    turns = [wall["dug"] for wall in run.walls if wall["kind"] == kind]
    return -1 if any(turn < 0 for turn in turns) else max(turns)


def run_until_earth_dug(run, limit=MAX_TURNS):
    """Runs the model until every earth wall is dug out or the limit passed; returns the turns run."""
    turn = 0
    while turn < limit and last_dug(run, "earth") < 0:
        run_turn(run, turn)
        turn += 1
    return turn


def observed_case(gold_first, fixed):
    """Three Zivs at a vein of three marked gold walls, four marked earth walls further down the corridor."""
    run = DigRun(gold_first, fixed)
    for x in (4, 5, 6):
        run.add_wall("gold", x)
    for x in (9, 10, 11, 12):
        run.add_wall("earth", x)
    for _ in range(3):
        run.add_ziv(5)
    return run


run = observed_case(False, False)
turns = run_until_earth_dug(run)
check(turns < MAX_TURNS and first_dug(run, "gold") >= 0 and first_dug(run, "earth") > first_dug(run, "gold"),
      "reproduction: with the rules of build 0.7.4.79 no earth wall is dug before a gold wall is empty")

run = observed_case(False, True)
turns = run_until_earth_dug(run)
check(turns < MAX_TURNS and last_dug(run, "earth") >= 0, "K3: with gold first off every earth wall is dug")
check(first_dug(run, "gold") < 0, "K3: the earth walls are dug before all marked gold is dug out")
check(run.gold_mined > 0.0, "K3: gold is mined while the earth walls are dug")

run = DigRun(True, True)
for x in (5, 6):
    run.add_wall("earth", x)
for x in (9, 10):
    run.add_wall("gold", x)
for _ in range(3):
    run.add_ziv(5)
turns = run_until_earth_dug(run)
check(turns < MAX_TURNS and last_dug(run, "gold") >= 0 and first_dug(run, "earth") > last_dug(run, "gold"),
      "K3: with gold first on gold walls are dug before the nearer earth walls, as before")


def gem_case(gold_first, fixed, zivs):
    """A gem wall at the Zivs and two earth walls behind it."""
    gem = DigRun(gold_first, fixed)
    gem.add_wall("gem", 5)
    gem.add_wall("earth", 7)
    gem.add_wall("earth", 8)
    for _ in range(zivs):
        gem.add_ziv(5)
    return gem


run = gem_case(True, True, 2)
for turn in range(2000):
    run_turn(run, turn)
check(first_dug(run, "earth") < 0 and run.gold_mined > 0.0, "K3: with gold first on the gem wall stays first")
run = gem_case(False, False, 1)
for turn in range(2000):
    run_turn(run, turn)
check(first_dug(run, "earth") < 0, "reproduction: with the rules of build 0.7.4.79 a Ziv stays on a gem wall")
run = gem_case(False, True, 1)
check(run_until_earth_dug(run, 2000) < 2000 and run.gold_mined > 0.0,
      "K3: with gold first off a Ziv at a gem wall digs the earth walls too")

for occupied, load_taken, after in itertools.product((False, True), repeat=3):
    check(group(False, True, occupied, load_taken, after) == group(False, False, occupied, load_taken, after),
          "K3: with gold first off the kind of a wall does not change its group")
for have_best, candidate, best_group, here, best_here, distance, best_distance in itertools.product(
        (False, True), range(4), range(4), (False, True), (False, True), (0.0, 1.0, 4.0), (0.0, 1.0, 4.0)):
    check(ranks_before(have_best, candidate, here, distance, best_group, best_here, best_distance) ==
          old_ranks_before(have_best, candidate, here, distance, best_group, best_here, best_distance),
          "the order inside the groups is unchanged")

# ------------------------------------------------------------------------------------------------ sources
ORDER = read("source/game/WorkerDigOrder.h")
SEARCH = read("source/creatureaction/CreatureActionSearchTileToDig.cpp")
DIG = read("source/creatureaction/CreatureActionDigTile.cpp")
TILE_H = read("source/entities/Tile.h")
CREATURE_H = read("source/entities/Creature.h")
TESTS_CMAKE = read("source/tests/CMakeLists.txt")
BOOST_TEST = read("source/tests/test_WorkerDigOrder.cpp")

check("const bool taken = occupied || (!goldFirst && afterDelivery && loadTaken);" in ORDER and
      "return (goldFirst && !goldOrGem ? 2 : 0) + (taken ? 1 : 0);" in ORDER, "WorkerDigOrder::group as modelled")
check("return goldFirst;" in function(ORDER, "inline bool keepsWallForDelivery("),
      "WorkerDigOrder::keepsWallForDelivery as modelled")
search = function(SEARCH, "bool CreatureActionSearchTileToDig::handleSearchTileToDig(")
check("WorkerDigOrder::group(goldFirst, gold, tile->hasWorkerDigging(), tile->getDigLoadTaken(),\n"
      "            afterDelivery)" in search, "the dig search ranks the walls with WorkerDigOrder::group")
check("WorkerDigOrder::ranksBefore(tileToDig != nullptr, group, here, dist, bestGroup, bestStanding, distBest)"
      in search, "the dig search orders the dig places with WorkerDigOrder::ranksBefore")
check("const bool afterDelivery = creature.isDigAfterDelivery();" in search and
      search.index("creature.setDigAfterDelivery(false);") <
      search.index("CreatureActionDigTile>(creature, *tileToDig, *tilePos, forced)"),
      "the dig search reads and clears the after-delivery state when it takes a wall")
dig = function(DIG, "bool CreatureActionDigTile::handleDigTile(")
release = dig[dig.index("if(isTreasuryAvailable)"):]
check("if(!forced && !WorkerDigOrder::keepsWallForDelivery(goldFirst))" in release and
      "tileDig.setDigLoadTaken();" in release and "creature.setDigAfterDelivery(true);" in release and
      "actions.back()->getType() == CreatureActionType::digTile" in release,
      "a full load with gold first off leaves the wall, marks it and sets the after-delivery state")
check(release.index("creature.popAction();") < release.index("CreatureActionGrabEntity>(creature, *obj, forced, true)"),
      "the wall is left before the delivery starts")
check("bool mDigLoadTaken = false;" in TILE_H and "bool getDigLoadTaken() const" in TILE_H,
      "Tile keeps the wall a load was carried away from")
check("bool mDigAfterDelivery = false;" in CREATURE_H and "void setDigAfterDelivery(bool afterDelivery)" in CREATURE_H,
      "Creature keeps the after-delivery state")
check(re.search(r"add_boost_test\(00-WorkerDigOrder\s+SOURCES\s+test_WorkerDigOrder\.cpp\s+"
                r"\$\{SRC\}/game/WorkerDigOrder\.h\)", TESTS_CMAKE) is not None,
      "the Boost test 00-WorkerDigOrder is built")
cases = re.findall(r"(.*)\n(BOOST_AUTO_TEST_CASE\((\w+)\))", BOOST_TEST)
check(sorted(name for _, _, name in cases) == sorted(["test_observedCaseReproduced", "test_earthDugWithGoldFirstOff",
                                                       "test_goldFirstOnKeepsGoldFirst", "test_gemWall",
                                                       "test_groups", "test_rankUnchanged"]),
      "the Boost test has the six cases of T-W1")
check(all(line.startswith("//!") for line, _, _ in cases), "every Boost test case has a comment")
check(re.search(r"\bauto\b", ORDER + BOOST_TEST) is None, "explicit types, no auto")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"worker-dig-order","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in sorted(set(FAILURES)):
        print("FAIL: " + failure)
    sys.exit(1)
print("worker dig order ok")
