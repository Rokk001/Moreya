"""Static checks of the sandbox start state: only the starting rooms and the worker summon spell are
researched, the other rooms become available one after the other, every trap and door comes with the workshop,
spells are researched in the library.

Run from any directory. It does not start a game.

The two sandbox levels are game data of the content packages (scripts/content_packages.py): they are read from the
public tree or from the content packages. Without the content the level checks are named as not checked; the code and
config checks run.
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "scripts"))
import content_packages  # noqa: E402

LEVELS = ("levels/skirmish/Sandbox.level", "levels/skirmish/SandboxEverything.level")
# The levels are checked when they are found or the content is present (then a missing one fails as before)
LEVELS_PRESENT = (content_packages.has_content(root)
                  or all(content_packages.data_file(root, level) is not None for level in LEVELS))
if LEVELS_PRESENT:
    sandbox = content_packages.read_text(root, LEVELS[0])
    everything = content_packages.read_text(root, LEVELS[1])
else:
    content_packages.unchecked("check_sandbox_start", LEVELS)
header = (root / "source/gamemap/SandboxMode.h").read_text(encoding="utf-8")
code = (root / "source/gamemap/SandboxMode.cpp").read_text(encoding="utf-8")
rooms_cfg = content_packages.read_text(root, "config/rooms.cfg")
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def skills_done(level):
    seat = level[level.index("[Seat]"):level.index("[/Seat]")]
    block = seat[seat.index("[SkillDone]"):seat.index("[/SkillDone]")]
    return [line.strip() for line in block.splitlines()[1:] if line.strip()]


# The start rooms of Sandbox.level (fixed for this branch; the same list when the level is not present)
start = ["roomTreasury", "roomDormitory", "roomHatchery", "spellSummonWorker"]
if LEVELS_PRESENT:
    start = skills_done(sandbox)
    check(start == ["roomTreasury", "roomDormitory", "roomHatchery", "spellSummonWorker"],
          "Sandbox.level must start with Treasury, Dormitory, Hatchery and the worker summon spell only: %s" % start)

# The unlock order of the code
order_block = code[code.index("ROOM_UNLOCKS["):]
order_block = order_block[order_block.index("{"):order_block.index("};")]
order = re.findall(r"SkillType::(room\w+)", order_block)
check(len(order) == len(set(order)), "the room unlock order has a room twice")
check("NB_UNLOCK_ROOMS = %d;" % len(order) in code, "NB_UNLOCK_ROOMS does not match the unlock order (%d rooms)" % len(order))
check(not set(order) & {"roomDormitory", "roomHatchery"}, "the dormitory and the hatchery are there from the start")
check(set(order) | set(start) >= {"roomLibrary", "roomWorkshop", "roomPrison", "roomTorture", "roomTemple",
                                  "roomCrypt", "roomCasino", "roomArena", "roomBridgeStone", "roomBridgeWooden",
                                  "roomTrainingHall", "roomGuardRoom"},
      "a base room is neither a start room nor in the unlock order")

# The variant with everything available has no room left to unlock and no room timer to wait for
if LEVELS_PRESENT:
    check(set(order) <= set(skills_done(everything)), "SandboxEverything.level must give every room of the unlock order")

# Room i comes after (i + 1) times the interval, a config key with a positive value (an own row of rooms.cfg, present
# only with the content package core-config)
if content_packages.has_content(root):
    match = re.search(r"^\s*SandboxRoomUnlockIntervalSeconds\s+(\d+(?:\.\d+)?)\s*$", rooms_cfg, re.M)
    check(match is not None and float(match.group(1)) > 0, "rooms.cfg needs a positive SandboxRoomUnlockIntervalSeconds")
else:
    content_packages.unchecked("check_sandbox_start", ["SandboxRoomUnlockIntervalSeconds (own row of config/rooms.cfg)"])
check('"SandboxRoomUnlockIntervalSeconds"' in code, "SandboxMode.cpp does not read SandboxRoomUnlockIntervalSeconds")
check("(static_cast<double>(index) + 1.0) * interval" in code, "the unlock time must be (index + 1) times the interval")

check("void updateUnlocks(" in header, "SandboxMode.h does not declare updateUnlocks")

# The unlock goes through the seat, which sends the usual notice, and runs on the server turn
check("seat->addSkill(ROOM_UNLOCKS[" in code, "the unlock must use Seat::addSkill")
check("updateUnlocks(keeperSeats);" in code[code.index("void SandboxMode::doTurn()"):], "doTurn must call updateUnlocks")

# A workshop gives every trap and door in one go (one notice)
check("RoomType::workshop" in code and "seat->addSkill(type, false)" in code,
      "a workshop must unlock every trap and door with a single notice")
check("bool addSkill(SkillType type, bool notify = true);" in (root / "source/game/Seat.h").read_text(encoding="utf-8"),
      "Seat::addSkill needs the notify parameter")

# One message per invasion: the hero portal stays silent when the sandbox spawns a wave (it names the spawned heroes)
portal = (root / "source/rooms/RoomPortalWave.cpp").read_text(encoding="utf-8")
spawn = portal[portal.index("void RoomPortalWave::spawnWave("):portal.index("void RoomPortalWave::warnHeroesComing")]
check("(spawnedNames == nullptr)" in spawn[spawn.index("warnHeroesComing();") - 120:], "the sandbox wave must not also trigger the gate warning")


if failures:
    print("\n".join(failures))
    sys.exit(1)
print("sandbox start checks passed")
