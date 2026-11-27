#!/usr/bin/env python3
"""Compiled check that an old savegame loads a removed creature class as its successor (creature roster CR3, D20,
D35).

The probe compiles the real alias table (source/utils/NameAliases.cpp), the real class lookup of the map
(findClassDescriptionByName, GameMap::getClassDescription and GameMap::resolveClassName, cut out of
source/gamemap/GameMap.cpp) and the real class mapping of the creature loader (the lines of Creature::importFromStream
from "loadedClass" to its log line) against small stand-ins for the map, the seat and the creature. It then loads the
creatures of an old savegame written into a temporary folder: one creature of every removed class on a keeper seat,
a keeper-owned, a rogue and a hero-owned DarkElf, and, as a file written with the current roster, a keeper-owned
DarkElf again. The removed class names are built from fragments, so they are never written out in the repository.

The real class mapping of the ghost loader (GhostEntity::importFromStream) and GameMap::resolveLoadedClassName, which
both loaders share, are cut out as well; the old file also holds ghosts of keeper, rogue and hero seats, and the
current file a keeper and a rogue DarkElf ghost. Crypt and prison save only the names of their corpses and
prisoners, which are creatures of [Creatures] with their own seat; the probe has one of each.

Expected (fixed, counted once from the contract of the roster): 19 creatures and 6 ghosts in the old file, 2 of each in
the current file; the 12 removed classes load as their successors, the
keeper-owned and the rogue DarkElf of the old file as Banshee, the hero-owned DarkElf stays, the keeper-owned DarkElf
of a current file stays, and a replaced creature takes the mesh of its new class.

Usage: python -I source/tests/check_old_save_successors.py  (needs cl on the PATH, for example after vcvars64.bat)
Exit 0 and "old save successors ok" when every item holds.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = time.perf_counter()


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def function(source, signature):
    """Returns the function that starts with the signature (up to its closing brace)."""
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


def phase(name, started):
    """Prints a phase measurement of this check."""
    print("ODP_TEST_PHASE " + json.dumps({"name": name, "seconds": round(time.perf_counter() - started, 3)}),
          flush=True)


# Removed class -> successor, from fragments (contract of the creature roster): 12 classes
SUCCESSORS = [
    ("Ra" + "t", "Banshee"), ("Spi" + "der", "Ghoul"), ("Roa" + "ch", "Witch"), ("Lava" + "Spawn", "Butcher"),
    ("Sli" + "me", "DarkElf"), ("Dwarf" + "1", "Hunter"), ("Nature" + "Monster", "Paladin"),
    ("Sca" + "rab", "Priestess"), ("Tentacle" + "Albine", "CrystalGolem"), ("Tentacle" + "Green", "Cyclops"),
    ("Kre" + "atur", "Minotaur"), ("Wy" + "vern", "Werewolf"),
]
# The classes of the map the probe loads into: the successors and the DarkElf, as the creature config will name them
MAP_CLASSES = ["Banshee", "Ghoul", "Witch", "Butcher", "DarkElf", "Hunter", "Paladin", "Priestess", "CrystalGolem",
               "Cyclops", "Minotaur", "Werewolf", "Knight", "Orc"]
# Seats of the old savegame: 0 rogue, 1 keeper, 2 hero
SEATS = {0: "Rogue", 1: "Keeper", 2: "Hero"}

# The creatures of the old savegame: (seat, name, class, expected class after loading)
OLD_FILE = []
for index, (old, new) in enumerate(SUCCESSORS):
    expected = new
    # A keeper-side creature whose successor is the DarkElf is a keeper-side DarkElf: Banshee (D20)
    if new == "DarkElf":
        expected = "Banshee"
    OLD_FILE.append((1, "Old%02d" % index, old, expected))
OLD_FILE.append((1, "KeeperElf", "DarkElf", "Banshee"))
OLD_FILE.append((0, "RogueElf", "DarkElf", "Banshee"))
OLD_FILE.append((2, "HeroElf", "DarkElf", "DarkElf"))
OLD_FILE.append((2, "HeroSuccessor", SUCCESSORS[4][0], "DarkElf"))
OLD_FILE.append((1, "KeeperKnight", "Knight", "Knight"))
# Crypt and prison save only the names of their corpses and prisoners; these are creatures of [Creatures] with their
# own seat: a keeper's corpse in a crypt becomes Banshee, a hero prisoner stays DarkElf
OLD_FILE.append((1, "CryptKeeperElf", "DarkElf", "Banshee"))
OLD_FILE.append((2, "PrisonerHeroElf", "DarkElf", "DarkElf"))
# A file written with the current roster keeps a keeper-owned DarkElf
CURRENT_FILE = [(1, "KeeperElfNow", "DarkElf", "DarkElf"), (0, "RogueElfNow", "DarkElf", "DarkElf")]
assert len(OLD_FILE) == 19 and len(CURRENT_FILE) == 2
# The ghosts of the files ([Ghosts], seat of the dead creature): (seat, name, class, expected class after loading)
OLD_GHOSTS = [
    (1, "GhostKeeperElf", "DarkElf", "Banshee"), (0, "GhostRogueElf", "DarkElf", "Banshee"),
    (2, "GhostHeroElf", "DarkElf", "DarkElf"), (1, "GhostKeeperRemoved", SUCCESSORS[1][0], "Ghoul"),
    (1, "GhostKeeperSuccessorElf", SUCCESSORS[4][0], "Banshee"), (2, "GhostHeroSuccessorElf", SUCCESSORS[4][0], "DarkElf"),
]
CURRENT_GHOSTS = [(1, "GhostKeeperElfNow", "DarkElf", "DarkElf"), (0, "GhostRogueElfNow", "DarkElf", "DarkElf")]
assert len(OLD_GHOSTS) == 6 and len(CURRENT_GHOSTS) == 2

GAME_MAP = read("source/gamemap/GameMap.cpp")
CREATURE = read("source/entities/Creature.cpp")
find_function = function(GAME_MAP, "static const CreatureDefinition* findClassDescriptionByName(")
lookup_function = function(GAME_MAP, "const CreatureDefinition* GameMap::getClassDescription(const string &className)")
resolve_function = function(GAME_MAP, "std::string GameMap::resolveClassName(const std::string& className)")
loaded_function = function(GAME_MAP, "std::string GameMap::resolveLoadedClassName(const std::string& className, "
                                     "const Seat* seat)")
loader = function(CREATURE, "bool Creature::importFromStream(std::istream& is)")
start = loader.index("    const std::string loadedClass = mDefinitionString;")
end = loader.index("is loaded as \" + mDefinitionString);", start)
end = loader.index("}", end) + 1
class_mapping = loader[start:end]
GHOST = read("source/entities/GhostEntity.cpp")
ghost_loader = function(GHOST, "bool GhostEntity::importFromStream(std::istream& stream)")
start = ghost_loader.index("    const std::string loadedClass = mClassName;")
end = ghost_loader.index("is kept as \" + mClassName);", start) + len("is kept as \" + mClassName);")
ghost_mapping = ghost_loader[start:end]

PROBE = r'''
#include "utils/NameAliases.h"
#include <cstdio>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using std::string;
#define OD_LOG_INF(message) do { std::string logged = (message); (void)logged; } while(false)

// Stand-in of the creature definition: the class name and the mesh of the class
class CreatureDefinition
{
public:
    CreatureDefinition(const std::string& name) : mClassName(name), mMeshName(name + ".mesh") {}
    const std::string& getClassName() const { return mClassName; }
    const std::string& getMeshName() const { return mMeshName; }
private:
    std::string mClassName;
    std::string mMeshName;
};

// Stand-in of the seat: its faction
class Seat
{
public:
    explicit Seat(const std::string& faction) : mFaction(faction) {}
    const std::string& getFaction() const { return mFaction; }
private:
    std::string mFaction;
};

// Stand-in of the map with the class descriptions and the loading flag of the level loader
class GameMap
{
public:
    const CreatureDefinition* getClassDescription(const std::string& className);
    std::string resolveClassName(const std::string& className);
    std::string resolveLoadedClassName(const std::string& className, const Seat* seat);
    bool isLoadingOldRosterCreatures() const { return mLoadingOldRosterCreatures; }
    std::vector<std::pair<const CreatureDefinition*,CreatureDefinition*> > mClassDescriptions;
    bool mLoadingOldRosterCreatures = false;
};

@FIND@

@LOOKUP@

@RESOLVE@

@LOADED@

// Stand-in of the ghost with the fields the class mapping of the ghost loader uses
class GhostEntity
{
public:
    GhostEntity(GameMap* gameMap, Seat* seat, const std::string& name, const std::string& className) :
        mGameMap(gameMap), mSeat(seat), mName(name), mClassName(className) {}
    GameMap* getGameMap() const { return mGameMap; }
    Seat* getSeat() const { return mSeat; }
    // The class mapping of GhostEntity::importFromStream, cut out of the source
    void mapClass()
    {
@GHOST@
    }
    GameMap* mGameMap;
    Seat* mSeat;
    std::string mName;
    std::string mClassName;
};

// Stand-in of the creature with the fields the class mapping of the loader uses
class Creature
{
public:
    Creature(GameMap* gameMap, Seat* seat, const std::string& name, const std::string& definition) :
        mGameMap(gameMap), mSeat(seat), mName(name), mDefinitionString(definition), mMeshName(definition + ".mesh") {}
    GameMap* getGameMap() const { return mGameMap; }
    Seat* getSeat() const { return mSeat; }
    const std::string& getName() const { return mName; }
    void setMeshName(const std::string& meshName) { mMeshName = meshName; }
    // The class mapping of Creature::importFromStream, cut out of the source
    void mapClass()
    {
@MAPPING@
    }
    GameMap* mGameMap;
    Seat* mSeat;
    std::string mName;
    std::string mDefinitionString;
    std::string mMeshName;
};

// Reads "classes" lines and "file old|current" blocks of "seat name class" lines, prints "name class mesh"
int main(int argc, char** argv)
{
    if(argc < 2)
        return 2;
    std::ifstream input(argv[1]);
    GameMap gameMap;
    std::map<int, Seat*> seats;
    seats[0] = new Seat("Rogue");
    seats[1] = new Seat("Keeper");
    seats[2] = new Seat("Hero");
    std::string word;
    while(input >> word)
    {
        if(word == "class")
        {
            std::string name;
            input >> name;
            gameMap.mClassDescriptions.push_back(std::pair<const CreatureDefinition*,CreatureDefinition*>(
                new CreatureDefinition(name), nullptr));
        }
        else if(word == "file")
        {
            std::string kind;
            input >> kind;
            gameMap.mLoadingOldRosterCreatures = (kind == "old");
        }
        else if(word == "creature")
        {
            int seat = 0;
            std::string name;
            std::string definition;
            input >> seat >> name >> definition;
            Creature creature(&gameMap, seats[seat], name, definition);
            creature.mapClass();
            std::cout << creature.mName << " " << creature.mDefinitionString << " " << creature.mMeshName << "\n";
        }
        else if(word == "ghost")
        {
            int seat = 0;
            std::string name;
            std::string className;
            input >> seat >> name >> className;
            GhostEntity ghost(&gameMap, seats[seat], name, className);
            ghost.mapClass();
            std::cout << ghost.mName << " " << ghost.mClassName << " Ghost\n";
        }
    }
    return 0;
}
'''
PROBE = (PROBE.replace("@FIND@", find_function).replace("@LOOKUP@", lookup_function)
         .replace("@RESOLVE@", resolve_function).replace("@LOADED@", loaded_function)
         .replace("@MAPPING@", class_mapping).replace("@GHOST@", ghost_mapping))


def main():
    """Builds and runs the probe and compares the loaded classes with the fixed expectation."""
    if shutil.which("cl") is None:
        print("FAIL: cl (MSVC) is needed for the compiled probe; run from a Developer prompt (vcvars64)")
        return 1
    failures = []
    folder = tempfile.mkdtemp(prefix="odp_old_save_")
    try:
        lines = ["class " + name for name in MAP_CLASSES]
        lines.append("file old")
        lines += ["creature %d %s %s" % entry[:3] for entry in OLD_FILE]
        lines += ["ghost %d %s %s" % entry[:3] for entry in OLD_GHOSTS]
        lines.append("file current")
        lines += ["creature %d %s %s" % entry[:3] for entry in CURRENT_FILE]
        lines += ["ghost %d %s %s" % entry[:3] for entry in CURRENT_GHOSTS]
        save = os.path.join(folder, "oldsave.txt")
        with open(save, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        code = os.path.join(folder, "probe.cpp")
        with open(code, "w", encoding="utf-8") as handle:
            handle.write(PROBE)
        started = time.perf_counter()
        subprocess.run(["cl", "/nologo", "/EHsc", "/std:c++14", "/I" + os.path.join(ROOT, "source"), code,
                        os.path.join(ROOT, "source", "utils", "NameAliases.cpp"), "/Fe:" + os.path.join(folder,
                        "probe.exe")], cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True,
                       timeout=300)
        phase("old_save_successors:compile", started)
        started = time.perf_counter()
        result = subprocess.run([os.path.join(folder, "probe.exe"), save], cwd=folder, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, universal_newlines=True, check=True, timeout=60)
        phase("old_save_successors:execute", started)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    loaded = {}
    for line in result.stdout.splitlines():
        name, definition, mesh = line.split()
        loaded[name] = (definition, mesh)
    for seat, name, old, expected in OLD_FILE + CURRENT_FILE:
        if name not in loaded:
            failures.append("creature " + name + " was not loaded")
            continue
        definition, mesh = loaded[name]
        if definition != expected:
            failures.append("%s (%s, seat %s) loads as %s, expected %s" % (name, "removed class" if old not in
                            MAP_CLASSES else old, SEATS[seat], definition, expected))
        expected_mesh = expected + ".mesh"
        if mesh != expected_mesh:
            failures.append("%s has mesh %s, expected %s" % (name, mesh, expected_mesh))
    # Every removed class of the keeper seat has its successor (counted: 12 classes, 11 successors on the keeper side
    # plus the Banshee in place of the DarkElf)
    found = set(loaded[name][0] for seat, name, old, _ in OLD_FILE if old not in MAP_CLASSES and seat == 1)
    if found != set(new if new != "DarkElf" else "Banshee" for _, new in SUCCESSORS):
        failures.append("successors found " + repr(sorted(found)))
    for seat, name, old, expected in OLD_GHOSTS + CURRENT_GHOSTS:
        if name not in loaded:
            failures.append("ghost " + name + " was not loaded")
        elif loaded[name] != (expected, "Ghost"):
            failures.append("ghost %s (%s, seat %s) is kept as %s, expected %s" % (name, "removed class" if old not in
                            MAP_CLASSES else old, SEATS[seat], loaded[name][0], expected))
    if not re.search(r"getClassDescription\(sideClass\) != nullptr", loaded_function):
        failures.append("the side successor is taken only when the map has its class")

    phase("old_save_successors", START)
    for failure in failures:
        print("FAIL: " + failure)
    if failures:
        return 1
    print("old save successors ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
