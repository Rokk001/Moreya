"""Check the alias table that lets savegames, levels and config files with older names keep loading:
every old name (built here from fragments, so the old spelling is never written out) hashes to an entry of
source/utils/NameAliases.cpp that points at the current name, unknown and current names are not in the table,
and the parse points call NameAliases::resolve."""
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[2]
alias_src = (repo / "source/utils/NameAliases.cpp").read_text(encoding="utf-8")


def fnv(name):
    h = 14695981039346656037
    for b in name.lower().encode("ascii"):
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


# The hash function of the code is FNV-1a over the lowercase bytes
assert "14695981039346656037ULL" in alias_src and "1099511628211ULL" in alias_src, "hash constants changed"
assert "std::tolower" in alias_src, "names are not lowercased before hashing"

ENTRY = r'\{\s*0x([0-9a-f]{16})ULL,\s*"([A-Za-z0-9]+)"\s*\}'
# The general table ALIASES and the table of the removed creature classes are read apart
general_src = alias_src.split("const AliasEntry ALIASES[] =", 1)[1].split("};", 1)[0]
creature_src = alias_src.split("const AliasEntry CREATURE_CLASS_ALIASES[] =", 1)[1].split("};", 1)[0]
table = {int(h, 16): n for h, n in re.findall(ENTRY, general_src)}
creature_table = {int(h, 16): n for h, n in re.findall(ENTRY, creature_src)}
assert len(table) >= 29, f"alias table has {len(table)} entries"
assert len(re.findall(ENTRY, alias_src)) == len(table) + len(creature_table), "an alias entry outside the two tables"

# Old names from fragments
a, b, c, d, e = "Turn" + "coat", "Chi" + "cken", "Guard" + "Post", "Bra" + "ced", "Ma" + "gic"
v = "Man" + "aVault"
cases = {a: "Defector", b: "HexenHen"}
for s in ("Price", "NbTurns", "Cooldown"):
    cases[a + s] = "Defector" + s
    cases[b + s] = "HexenHen" + s
for s in ("CostPerTile", "WorkshopPointsPerTile", "AuraTiles"):
    cases[c + s] = "WatchBanner" + s
for s in ("CostPerTile", "PointsPerTile", "HP"):
    cases[d + "Door" + s] = "IronboundDoor" + s
for s in ("CostPerTile", "PointsPerTile", "HP", "ManaToFire", "RegenPerTurn", "ReloadTurns", "Damage"):
    cases[e + "Door" + s] = "RunedDoor" + s
cases["spell" + b] = "spellHexenHen"
cases["spell" + a] = "spellDefector"
cases["trapDoor" + d] = "trapDoorIronbound"
cases["trapDoor" + e] = "trapDoorRuned"
cases["trap" + c] = "trapWatchBanner"
cases[v + "BonusPerTile"] = "ManaWellBonusPerTile"
cases["RoomConvert" + "Refer" + "ence" + "ClaimRate"] = "RoomConvertClaimRate"
cases[v + "Ground"] = "manaWellGround"

for old, new in cases.items():
    # lookup is case-insensitive
    for variant in (old, old.lower(), old.upper()):
        assert table.get(fnv(variant)) == new, f"old name {variant} does not resolve to {new}"
assert len(cases) == len(table), f"{len(cases)} cases but {len(table)} table entries"

# Current names and unknown names are not touched
for name in list(cases.values()) + ["Hatchery", "Wooden", "SteelDoorHP", "spellSummonWorker", "Burn", "Frozen", "", "Defecto"]:
    assert fnv(name) not in table, f"{name!r} would be changed by resolve"

# The new names are really used by the data
spells = (repo / "config/spells.cfg").read_text(encoding="utf-8")
traps = (repo / "config/traps.cfg").read_text(encoding="utf-8")
skills = (repo / "config/skills.cfg").read_text(encoding="utf-8")
glob = (repo / "config/global.cfg").read_text(encoding="utf-8")
for key in ("DefectorPrice", "HexenHenPrice", "HexenHenCooldown"):
    assert re.search(r"^\s+%s\t" % key, spells, re.M), f"spells.cfg lacks {key}"
for key in ("WatchBannerCostPerTile", "IronboundDoorHP", "RunedDoorDamage"):
    assert re.search(r"^\s+%s\t" % key, traps, re.M), f"traps.cfg lacks {key}"
for key in ("spellDefector", "spellHexenHen", "trapWatchBanner", "trapDoorIronbound", "trapDoorRuned"):
    assert re.search(r"^\s+%s\t" % key, skills, re.M), f"skills.cfg lacks {key}"
assert re.search(r"^\s+ManaWellBonusPerTile\t", glob, re.M), "global.cfg lacks ManaWellBonusPerTile"
rooms = (repo / "config/rooms.cfg").read_text(encoding="utf-8")
assert re.search(r"^\s+RoomConvertClaimRate\t", rooms, re.M), "rooms.cfg lacks RoomConvertClaimRate"

# Parse points
def count(path, text):
    return (repo / path).read_text(encoding="utf-8").count(text)

assert count("source/creatureeffect/CreatureEffectManager.cpp", "NameAliases::resolve(") == 1
assert count("source/game/SkillType.cpp", "NameAliases::resolve(") == 1
assert count("source/utils/ConfigManager.cpp", "NameAliases::resolve(") == 5
# Seat block of an older savegame: the tile visual tags are read through the alias table, written with the new name
seat_src = (repo / "source/game/Seat.cpp").read_text(encoding="utf-8")
assert seat_src.count("resolveTileVisualTag(") == 3, "Seat tile visual tags are not resolved"
assert 'os << "[" + Tile::tileVisualToString(tileVisual) + "]"' in seat_src, "tags are written with the current name"


def resolve_tag(tag):
    # same rule as resolveTileVisualTag in Seat.cpp
    if len(tag) < 3 or tag[0] != "[" or tag[-1] != "]":
        return tag
    end = tag[1] == "/"
    name = tag[2:-1] if end else tag[1:-1]
    return ("[/" if end else "[") + table.get(fnv(name), name) + "]"


old_seat = " ".join(["[%sGround]", "12", "13", "1", "[/%sGround]", "[dirtGround]", "[/dirtGround]", "[/Seat]"]) % (v[0].lower() + v[1:], v[0].lower() + v[1:])
tags = [resolve_tag(t) for t in old_seat.split()]
assert tags[0] == "[manaWellGround]" and tags[4] == "[/manaWellGround]", tags
assert tags[5:] == ["[dirtGround]", "[/dirtGround]", "[/Seat]"], "other tags must stay unchanged"

# Removed creature classes of older savegames and levels (creature roster CR3): every removed class (built from
# fragments, so the old spelling is never written out) resolves to its successor, counted once: 12 classes
creature_cases = {
    "Ra" + "t": "Banshee", "Spi" + "der": "Ghoul", "Roa" + "ch": "Witch", "Lava" + "Spawn": "Butcher",
    "Sli" + "me": "DarkElf", "Dwarf" + "1": "Hunter", "Nature" + "Monster": "Paladin", "Sca" + "rab": "Priestess",
    "Tentacle" + "Albine": "CrystalGolem", "Tentacle" + "Green": "Cyclops", "Kre" + "atur": "Minotaur",
    "Wy" + "vern": "Werewolf",
}
assert len(creature_cases) == 12 and len(creature_table) == 12, f"{len(creature_table)} creature class entries"
for old, new in creature_cases.items():
    for variant in (old, old.lower(), old.upper()):
        assert creature_table.get(fnv(variant)) == new, f"removed class {variant} does not resolve to {new}"
        assert fnv(variant) not in table, f"removed class {variant} must not be in the general table"
# The classes of the roster keep their names (36 creatures)
ROSTER = ("Knight Dwarf2 Paladin Priestess Monk RunelordDwarf Defender Adventurer Hunter DarkElf Elf Wizard DwarfWorker "
          "Troll Orc PitDemon Vampire Cultist LizardMan Skeleton Goblin Ghoul Butcher CaveHornet Lich Banshee Witch "
          "Kobold CrystalGolem Cyclops Minotaur Werewolf Gnoll Gnome Dragon Champion").split()
assert len(ROSTER) == 36
for name in ROSTER + ["DefaultWorker", ""]:
    assert fnv(name) not in creature_table and fnv(name) not in table, f"{name!r} would be changed"
assert "lookUp(CREATURE_CLASS_ALIASES" in alias_src, "resolveCreatureClass reads the creature class table"
assert 'SIDE_MOVED_CLASS = "DarkElf"' in alias_src and 'SIDE_SUCCESSOR_CLASS = "Banshee"' in alias_src


def side_class(name, hero_side):
    # same rule as NameAliases::resolveOldCreatureClassForSide
    return "Banshee" if (not hero_side and name == "DarkElf") else name


assert side_class("DarkElf", False) == "Banshee" and side_class("DarkElf", True) == "DarkElf"
assert side_class("Elf", False) == "Elf"
side_body = alias_src.split("std::string resolveOldCreatureClassForSide(", 1)[1].split("\n}", 1)[0]
assert "if(!heroSide && (className == SIDE_MOVED_CLASS))" in side_body, "side rule changed"

# Parse points of the creature classes: the class lookup of the map and the creature loader
game_map_src = (repo / "source/gamemap/GameMap.cpp").read_text(encoding="utf-8")
lookup = game_map_src.split("const CreatureDefinition* GameMap::getClassDescription(const string &className)", 1)[1]
lookup = lookup.split("\n}", 1)[0]
assert "NameAliases::resolveCreatureClass(className)" in lookup, "the class lookup does not resolve removed classes"
assert lookup.index("findClassDescriptionByName(mClassDescriptions, className)") < lookup.index("resolveCreatureClass"), \
    "a class of the map must be found before the alias table is asked"
tuning = game_map_src.split("CreatureDefinition* GameMap::getClassDescriptionForTuning(", 1)[1].split("\n}", 1)[0]
assert tuning.index("resolveClassName(name)") < tuning.index("new CreatureDefinition(name)"), \
    "the tuning of a removed class must go to its successor"
creature_src_cpp = (repo / "source/entities/Creature.cpp").read_text(encoding="utf-8")
loader = creature_src_cpp.split("bool Creature::importFromStream(std::istream& is)", 1)[1].split("if(!(is >> mLevel))", 1)[0]
assert "getGameMap()->resolveClassName(mDefinitionString)" in loader
assert "isLoadingOldRosterCreatures()" in loader and 'getSeat()->getFaction() == "Hero"' in loader
assert "NameAliases::resolveOldCreatureClassForSide(mDefinitionString, heroSide)" in loader
assert "setMeshName(successor->getMeshName())" in loader, "a replaced creature takes the mesh of its new class"
map_handler = (repo / "source/gamemap/MapHandler.cpp").read_text(encoding="utf-8")
assert 'CREATURE_ROSTER_INFO_KEY = "CreatureRoster\\t"' in map_handler and "CREATURE_ROSTER_VERSION = 1;" in map_handler
assert "levelFile << CREATURE_ROSTER_INFO_KEY << CREATURE_ROSTER_VERSION" in map_handler, "files carry the roster"
creatures_block = map_handler.split("gameMap.setLoadingOldRosterCreatures(oldRosterFile);", 1)
assert len(creatures_block) == 2 and "Creature::getCreatureFromStream(&gameMap, ss)" in creatures_block[1].split(
    "gameMap.setLoadingOldRosterCreatures(false);\n    OD_LOG_INF", 1)[0], "the side rule is on only for [Creatures]"
assert map_handler.count("gameMap.setLoadingOldRosterCreatures(false);") == 4, "the side rule is switched off again"

assert "utils/NameAliases.cpp" in (repo / "CMakeLists.txt").read_text(encoding="utf-8")
assert (repo / "docs/development/NAME-ALIASES.md").is_file()

print("CHECKS OK")
