#!/usr/bin/env python3
"""Static check that the code fallbacks equal the shipped config values (no compiler needed).

    python source/tests/check_config_fallbacks.py

Checks the ConfigManager constructor defaults, the room config fallbacks of the arena, the hatchery and the
chicken gift, and the hatchery cycle defaults against the shipped config files, and that the new mana and gift box
keys exist with the shipped value as their default.

The data tables are read as the game reads them, with their own rows from the content packages
(scripts/content_packages.py). Without the content a value that is not in the public rows is named as not checked.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
HAS_CONTENT = content_packages.has_content(ROOT)
# The values that could not be checked without the content
unchecked = []


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def cfg_value(text, key):
    match = re.search(r"^\s+" + re.escape(key) + r"\s+(\S+)\s*$", text, re.M)
    return float(match.group(1)) if match else None


def read_table(name):
    """A data table of config/ as the game reads it: with its own rows from the content packages."""
    return content_packages.read_text(ROOT, "config/" + name)


def not_present(shipped, what):
    """True when a shipped value is missing because the content (its own rows) is not present: it is named as not
    checked. With the content present a missing value stays a problem of the check."""
    if shipped is None and not HAS_CONTENT:
        unchecked.append(what)
        return True
    return False


problems = []
global_cfg = read_table("global.cfg")
rooms_cfg = read_table("rooms.cfg")
traps_cfg = read_table("traps.cfg")
manager = read("source", "utils", "ConfigManager.cpp")

# ConfigManager constructor defaults: member -> global.cfg key
DEFAULTS = {
    "mCreatureDeathCounter": "CreatureDeathCounter", "mCreatureBaseMood": "CreatureBaseMood",
    "mSlapEffectDuration": "SlapEffectDuration", "mTimePayDay": "TimePayDay",
    "mClaimingWallPenalty": "ClaimingWallPenalty", "mDigCoefClaimedWall": "DigCoefClaimedWall",
    "mNbTurnsKoCreatureAttacked": "NbTurnsKoCreatureAttacked", "mCorpseLieSeconds": "CorpseLieSeconds",
    "mCorpseDecaySeconds": "CorpseDecaySeconds", "mManaIncomeTilesCap": "ManaIncomeTilesCap",
    "mManaPerClaimedTilePerSecond": "ManaPerClaimedTilePerSecond", "mWorkerManaUpkeepPerSecond": "WorkerManaUpkeepPerSecond",
    "mWorkerManaShortageSeconds": "WorkerManaShortageSeconds", "mWorkerPopCountdownSeconds": "WorkerPopCountdownSeconds",
    "mAutoWorkerIntervalSeconds": "AutoWorkerIntervalSeconds", "mGiftBoxMana": "GiftBoxMana", "mGiftBoxGold": "GiftBoxGold",
    "mGiftBoxLevels": "GiftBoxLevels", "mGiftBoxWorkers": "GiftBoxWorkers", "mGiftBoxStunSeconds": "GiftBoxStunSeconds",
    "mGhostAiGoldPerResearchPoint": "GhostAiGoldPerResearchPoint", "mGhostAiGoldPerXp": "GhostAiGoldPerXp",
    "mSoulCrystalNormalXpPerSecond": "SoulCrystalNormalXpPerSecond", "mCreatureMoodUpset": "CreatureMoodUpset",
    "mCreatureMoodAngry": "CreatureMoodAngry", "mCreatureMoodFurious": "CreatureMoodFurious",
    "mMoodRampageBrawlVictim": "MoodRampageBrawlVictim",
}
for member, key in DEFAULTS.items():
    shipped = cfg_value(global_cfg, key)
    match = re.search(r"^\s+" + member + r"\(([-0-9.]+)\)", manager, re.M)
    if not_present(shipped, "global.cfg " + key):
        continue
    if shipped is None:
        problems.append("global.cfg has no " + key)
    elif match is None:
        problems.append("ConfigManager has no default for " + member)
    elif abs(float(match.group(1)) - shipped) > 1e-9:
        problems.append(member + " defaults to " + match.group(1) + ", global.cfg " + key + " is " + str(shipped))

well = re.search(r"DEFAULT_MANA_WELL_BONUS_PER_TILE = ([-0-9.]+);", manager)
if not_present(cfg_value(global_cfg, "ManaWellBonusPerTile"), "global.cfg ManaWellBonusPerTile"):
    pass
elif well is None or abs(float(well.group(1)) - cfg_value(global_cfg, "ManaWellBonusPerTile")) > 1e-9:
    problems.append("the mana well default must equal global.cfg ManaWellBonusPerTile")

# getRoomConfigDoubleOrDefault fallbacks: file -> keys
for path, keys in (("source/entities/Creature.cpp", ["ArenaDirtPerHit"]),
                   ("source/rooms/RoomArena.cpp", ["PitMoodSolitary", "PitMoodSpectator", "PitMoodVictor"]),
                   ("source/rooms/RoomHatchery.cpp", ["HatcheryDirtPerHenTurn"]),
                   ("source/creatureaction/CreatureActionEatChicken.cpp", ["HatcheryGiftHpRecoveredPerChicken"])):
    text = read(*path.split("/"))
    for key in keys:
        match = re.search(r'getRoomConfigDoubleOrDefault\("' + key + r'",\s*([-0-9.]+)\)', text)
        shipped = cfg_value(rooms_cfg, key)
        if match is None:
            problems.append(path + " has no fallback for " + key)
        elif not_present(shipped, "rooms.cfg " + key):
            continue
        elif abs(float(match.group(1)) - shipped) > 1e-9:
            problems.append(path + " falls back to " + match.group(1) + " for " + key + ", rooms.cfg has " + str(shipped))

for path, constant, key, cfg in (
    ("source/rooms/Room.cpp", "DEFAULT_ROOM_CONVERT_NEUTRAL_SECONDS_PER_TILE", "RoomConvertNeutralSecondsPerTile", rooms_cfg),
    ("source/rooms/Room.cpp", "DEFAULT_ROOM_CONVERT_SECONDS_PER_TILE", "RoomConvertSecondsPerTile", rooms_cfg),
    ("source/rooms/RoomPortal.cpp", "DEFAULT_PORTAL_FIRST_SPAWN_SECONDS", "PortalFirstSpawnSeconds", rooms_cfg),
    ("source/creatureaction/CreatureActionReloadTrap.cpp", "DEFAULT_RELOAD_EXPERIENCE", "TrapReloadExperience", traps_cfg),
):
    match = re.search(r'\b' + constant + r'\s*=\s*([-0-9.]+)', read(*path.split('/')))
    shipped = cfg_value(cfg, key)
    if not_present(shipped, key):
        continue
    if match is None or shipped is None or abs(float(match.group(1)) - shipped) > 1e-9:
        problems.append(path + " default " + constant + " must equal " + key)

# The mood caps and decays of the pit and the casino are gone: the moods are one-time values added to the stored
# mood, so neither the config nor the code keeps a cap key or a default for them.
creature_source = read("source", "entities", "Creature.cpp")
if not HAS_CONTENT:
    unchecked.append("the own rows of rooms.cfg and global.cfg without the removed keys")
for gone in ("PitMoodMax", "PitMoodDecay", "CasinoMoodMax", "CasinoMoodDecay"):
    if cfg_value(rooms_cfg, gone) is not None or gone in creature_source:
        problems.append(gone + " must be gone from rooms.cfg and Creature.cpp")
for gone in ("DEFAULT_PIT_MOOD_MAX", "DEFAULT_PIT_MOOD_DECAY_PER_SECOND"):
    if gone in creature_source:
        problems.append("Creature.cpp must not keep " + gone)

cycle = read("source", "rooms", "HatcheryCycle.h")
for member, key in (("mLayMax", "HatcheryLayMax"), ("mLayFactor", "HatcheryLayFactor")):
    match = re.search(member + r"\(([-0-9.]+)\)", cycle)
    shipped = cfg_value(rooms_cfg, key)
    if not_present(shipped, "rooms.cfg " + key):
        continue
    if match is None or abs(float(match.group(1)) - shipped) > 1e-9:
        problems.append("HatcheryCycle.h default " + member + " must equal rooms.cfg " + key)

trap = read("source", "traps", "Trap.cpp")
gas = re.search(r'getTrapConfigDoubleOrDefault\("GasReloadCost",\s*([-0-9.]+)\)', trap)
gas_shipped = cfg_value(traps_cfg, "GasReloadCost")
if not_present(gas_shipped, "traps.cfg GasReloadCost"):
    pass
elif gas is None or gas_shipped is None or abs(float(gas.group(1)) - gas_shipped) > 1e-9:
    problems.append("GasReloadCost fallback must equal traps.cfg")

# A missing room key is logged
if "Missing room parameter" not in manager:
    problems.append("getRoomConfigDoubleOrDefault must log a missing key")

fallback_keys = manager.split('static const char* const fallbackKeys[]', 1)[-1].split('};', 1)[0]
for key in ('ManaIncomeTilesCap', 'ManaPerClaimedTilePerSecond', 'WorkerManaUpkeepPerSecond',
            'WorkerManaShortageSeconds', 'WorkerPopCountdownSeconds', 'AutoWorkerIntervalSeconds',
            'GiftBoxMana', 'GiftBoxGold', 'GiftBoxLevels', 'GiftBoxWorkers', 'GiftBoxStunSeconds'):
    if f'foundKeys.insert("{key}")' not in manager or f'"{key}"' not in fallback_keys:
        problems.append("missing-key logging is not wired for " + key)
if 'foundKeys.count(key) == 0' not in manager or 'Missing GameConfig key=' not in manager:
    problems.append("missing GameConfig fallbacks must be logged")

# The rampage block of global.cfg: the shipped values equal the defaults of the ConfigManager constructor, and the keys of the
# old wage rules and of the old rogue rule are gone from the code and from the configuration
rampage_block = re.search(r"\[Rampage\](.*?)\[/Rampage\]", global_cfg, re.S)
if not_present(rampage_block, "global.cfg [Rampage] block"):
    pass
elif rampage_block is None:
    problems.append("global.cfg has no [Rampage] block")
else:
    for key in ("RampageTileDamage", "RampageHitTurns", "RampagePileTurns"):
        shipped = cfg_value(rampage_block.group(1), key)
        match = re.search(r'mRampageConfig\["' + key + r'"\] = ([-0-9.]+);', manager)
        if shipped is None or match is None or abs(float(match.group(1)) - shipped) > 1e-9:
            problems.append("the default of " + key + " must equal the [Rampage] block of global.cfg")
for gone in ("UnpaidWagesStopWork", "UnpaidWagesLeave", "NbTurnsFuriousMax"):
    if cfg_value(global_cfg, gone) is not None or gone in manager or ("# " + gone) in global_cfg:
        problems.append(gone + " must be gone from global.cfg and the ConfigManager")

content_packages.unchecked("check_config_fallbacks", unchecked)
if problems:
    print("\n".join("FAIL: " + p for p in problems))
    sys.exit(1)
print("OK: every fallback equals the shipped config value")
