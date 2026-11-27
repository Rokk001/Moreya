#!/usr/bin/env python3
"""Raid simulation runner: plays the raid test level or a campaign level headless with the real game and config.

The game binary has a headless raid simulation mode (--raid-sim, source/utils/RaidSimulation.h): it loads a level with
a [Raid] section on a server without window, network or client, runs the real game turns as fast as it can with a
fixed random seed and writes one line per turn (raid and keeper state). This script
  - builds level variants from levels/skirmish/TestRaid.level (raid size, groups, hero level and composition, keeper
    force, countdown, interval, escape share), written to the work folder only,
  - or, with --level <map>, from a story level of levels/campaign (its countdown, interval and escape share, and with
    --member-level a raid composition after the guild's role emphasis, see campaign_members()); the rest of the level
    (map, script, phase-1 enemies) stays as it is,
  - builds a data folder per config variant: links to the game data of the build folder and a copy of config/ in which
    the given [GroupCombat] and [Raid] keys of global.cfg are replaced,
  - runs the seeds in parallel, reads the turn lines and computes the measures of a run (see measures()),
  - writes one JSON line per run to <work>/runs.jsonl (cached: a run with the same level, config and seed is not
    repeated).

Usage (from the repository root, after building the game, e.g. in build/r3):
  python tools/balance/raid_sim.py run --exe build/r3/Release/moreya.exe --work out/raid-sim \
      --size 10 --hero-level 4 --keeper-count 10 --keeper-level 4 --seeds 1-8 --set GroupCombat.GroupFormingDistance=8
  python tools/balance/raid_sim.py run --exe build/r3b/moreya.exe --work out/raid-sim/w --level Brackenford \
      --keeper-ai --countdown 100000 --seconds 2400 --seeds 1-8     (phase 1 of a story level played by the keeper AI)
  python tools/balance/raid_sim.py sweep --exe ... --work ... --level Tinmoor --keeper-ai --countdown 600 \
      --member-level 3 --leader-offset 2 --share 0.6 --axis member_level --values 2,3,4 --report out/raid-sim/x.jsonl
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "levels" / "skirmish" / "TestRaid.level"
TURNS_PER_SECOND = 1.4

# The scouts of the keeper faction's spawn pool that the reference keeper force leaves out.
KEEPER_SCOUTS = ("CaveHornet", "Goblin")


def keeper_pool(repo=REPO):
    """The keeper's fighters of the keeper faction's spawn pool (config/factions.cfg), without the scouts
    (KEEPER_SCOUTS) and the worker, read from the configuration: the reference keeper force cycles through them. The
    tiers of the pool (wage classes by FeeBase of config/creatures.cfg) are interleaved (tier 1, 2, 3, 4, then again),
    so that a small force has every tier as well and only a force of ten or more has every class."""
    factions = (repo / "config" / "factions.cfg").read_text(encoding="utf-8")
    keeper = re.search(r"\[Faction\]\s*Name\s+Keeper\b(.*?)\[/Faction\]", factions, re.S).group(1)
    pool = re.search(r"\[SpawnPool\](.*?)\[/SpawnPool\]", keeper, re.S).group(1)
    names = [line.strip() for line in pool.splitlines()
             if line.strip() and not line.strip().startswith("#") and line.strip() not in KEEPER_SCOUTS]
    creatures = (repo / "config" / "creatures.cfg").read_text(encoding="utf-8")
    fees = {}
    for block in re.findall(r"\[Creature\](.*?)\[/Creature\]", creatures, re.S):
        name = re.search(r"^\s*Name\s+(\S+)", block, re.M)
        fee = re.search(r"^\s*FeeBase\s+(\S+)", block, re.M)
        if name and fee:
            fees.setdefault(name.group(1), float(fee.group(1)))
    tiers = [[name for name in names if fees[name] == fee] for fee in sorted({fees[name] for name in names})]
    result = []
    for index in range(max(len(tier) for tier in tiers)):
        result += [tier[index] for tier in tiers if index < len(tier)]
    return result


KEEPER_POOL = keeper_pool()

# Raid members per role: class and fixed skill template (a template of the class's skill group; the group decides the
# role in group fights). The healer slot is a Wizard with the Sparkcaller template: a mage cannot heal, so in the game
# it fights as a caster; the simulation still counts the slot as its healer (adjust_members()).
ROLE_MEMBER = {
    "tank": ("Knight", "Ironclad"),
    "melee": ("Hunter", "Assassin"),
    "ranged": ("Elf", "Sharpshooter"),
    "healer": ("Wizard", "Sparkcaller"),
    "caster": ("Wizard", "Pyromancer"),
}

# Role cycles of the reference compositions: "all" has every role, the others weight the role emphasis of the guild
# table (the first member is the leader and always a tank).
COMPOSITIONS = {
    "all": ["tank", "melee", "ranged", "healer", "melee", "tank", "ranged", "caster"],
    "melee": ["tank", "melee", "melee", "ranged", "melee", "healer", "melee", "caster"],
    "tank": ["tank", "tank", "melee", "tank", "ranged", "healer", "tank", "caster"],
    "ranged": ["tank", "ranged", "ranged", "melee", "ranged", "healer", "ranged", "caster"],
    "healers": ["tank", "healer", "melee", "healer", "ranged", "healer", "tank", "caster"],
}

# Role emphasis of the guild of every story level (guild table of the raid plan): the primary roles, the secondary
# roles ("tank with ranged") and the tank classes of the guild (heavy tanks: no Monks; many Monks: mostly Monks).
# Roles follow from the skill group of the fixed template (tank, healer, marksman: ranged, mage: caster, every other
# group: melee; TEMPLATE_ROLES).
GUILDS = {
    "Brackenford": (("melee",), (), "tank"),
    "Coldwell": (("melee",), ("tank",), "tank"),
    "Ravensledge": (("ranged",), (), "tank"),
    "Tinmoor": (("tank",), (), "tank"),
    "Greywater": (("tank",), (), "tank"),
    "Highcairn": (("tank",), ("ranged",), "tank"),
    "Lanternhill": (("tank",), ("ranged",), "tank"),
    "Saltmere": (("tank",), (), "tank"),
    "HollinFen": (("healer",), (), "tank"),
    "Cinderhollow": (("tank",), (), "tank"),
    "Ashcombe": (("tank",), (), "tank"),
    "Ironbridge": (("tank",), (), "heavy"),
    "Bellwick": (("tank",), (), "monks"),
    "Goldspire": (("tank",), ("ranged",), "tank"),
    "Kingsfall": (("tank",), ("ranged",), "tank"),
    "VarnsCrossing": (("tank",), (), "tank"),
    "Wraithwood": (("tank",), ("caster",), "tank"),
    "HollowmarkCitadel": (("tank",), (), "tank"),
}

# Class and fixed template of the members of a role, taken in turn (the hero classes of the guild table: Knight, Dwarf
# and Monk tanks, Adventurer melee, Elf ranged, Wizard caster and healer).
ROLE_CLASSES = {
    "tank": [("Knight", "Ironclad"), ("Dwarf2", "Ironclad"), ("Monk", "Mender")],
    "heavy": [("Knight", "Ironclad"), ("Dwarf2", "Ironclad")],
    "monks": [("Monk", "Mender"), ("Monk", "Mender"), ("Knight", "Ironclad")],
    "melee": [("Adventurer", "Assassin"), ("Hunter", "Assassin"), ("Adventurer", "Whirlwind"), ("Knight", "Ironclad")],
    "ranged": [("Elf", "Sharpshooter"), ("Elf", "Poisoner"), ("Elf", "Barrager")],
    "healer": [("Wizard", "Sparkcaller")],
    "caster": [("Wizard", "Pyromancer"), ("Wizard", "Witherer")],
}

# Order in which the members that are neither primary nor secondary are spread over the other roles
OTHER_ROLES = ["melee", "ranged", "healer", "caster", "tank"]

# Role of a fixed template by its skill group (config/creatureSkills.cfg [Template], [GroupCombat] of global.cfg);
# the templates of the other groups (supporter, warrior, skirmisher) fight as melee
TEMPLATE_ROLES = {"Ironclad": "tank", "Evader": "tank", "Regenerator": "tank",
                  "Mender": "healer", "Renewer": "healer", "Warder": "healer",
                  "Sharpshooter": "ranged", "Poisoner": "ranged", "Barrager": "ranged",
                  "Sparkcaller": "caster", "Witherer": "caster", "Pyromancer": "caster"}

GATE = (33, 33)
# Free dirt tiles near the keeper's heart (5..9) where the keeper force starts, row by row
KEEPER_AREA = [(x, y) for y in range(11, 21) for x in range(11, 18)]


def parse_seeds(text):
    """Returns the seeds of '1-8' or '1,3,5'."""
    seeds = []
    for part in text.split(","):
        if "-" in part:
            first, last = part.split("-")
            seeds.extend(range(int(first), int(last) + 1))
        else:
            seeds.append(int(part))
    return seeds


def raid_members(size, hero_level, composition, group_id, leader_name):
    """Member lines of one raid group: the leader first (a tank), then the role cycle of the composition."""
    cycle = COMPOSITIONS[composition]
    lines = []
    for index in range(size):
        role = "tank" if index == 0 else cycle[index % len(cycle)]
        class_name, template = ROLE_MEMBER[role]
        name = leader_name if index == 0 else "-"
        lines.append("Member\t%d\t%s\t%d\t%s\t%s" % (group_id, class_name, hero_level, name, template))
    return lines


def role_counts(size, primary, secondary, share):
    """Members per role of a group of the size: the primary roles get the share of it (rounded), the secondary roles
    half of the rest (rounded), the other members are spread over the remaining roles in the order OTHER_ROLES."""
    counts = {role: 0 for role in ("tank", "melee", "ranged", "healer", "caster")}
    main = int(round(share * size))
    for index in range(main):
        counts[primary[index % len(primary)]] += 1
    rest = size - main
    second = int(round(rest / 2.0)) if secondary else 0
    for index in range(second):
        counts[secondary[index % len(secondary)]] += 1
    others = [role for role in OTHER_ROLES if role not in primary and role not in secondary]
    for index in range(rest - second):
        counts[others[index % len(others)]] += 1
    return counts


def raid_groups(text):
    """The groups of the [Raid] section of a level: [(group id, leader name or None, [member fields])]."""
    block = re.search(r"^\[Raid\]$(.*?)^\[/Raid\]$", text, re.S | re.M).group(1)
    groups = []
    for line in block.splitlines():
        fields = line.split("#")[0].split()
        if fields and fields[0] == "Group":
            groups.append((int(fields[1]), None if fields[2] == "-" else fields[2], []))
        elif fields and fields[0] == "Member":
            for group in groups:
                if group[0] == int(fields[1]):
                    group[2].append(fields)
    return groups


def set_healers(counts, healers):
    """Gives the group exactly that many healers (RA11): added healers replace members of the largest other role in
    turn (never the last tank, so that the leader keeps his role), removed ones become members of the primary role
    order OTHER_ROLES."""
    healers = max(0, min(healers, sum(counts.values()) - 1))
    while counts["healer"] < healers:
        role = max((name for name in counts if name != "healer" and (counts[name] > 1 or name != "tank")),
                   key=lambda name: counts[name])
        counts[role] -= 1
        counts["healer"] += 1
    while counts["healer"] > healers:
        counts["healer"] -= 1
        counts["melee"] += 1


def campaign_members(level_name, text, member_level, leader_offset, share, healers=None):
    """Member lines of the raid of a story level after its guild's role emphasis: every group keeps its size and its
    named leader (class and template as the level has them, level member_level + leader_offset); the other members are
    member_level and get their roles from role_counts() over the whole group (the leader counted in his role), their
    classes and templates in turn from ROLE_CLASSES. With healers, every group has exactly that many healers."""
    primary, secondary, tanks = GUILDS[level_name]
    lines = []
    for group_id, leader, members in raid_groups(text):
        counts = role_counts(len(members), primary, secondary, share)
        if healers is not None:
            set_healers(counts, int(healers))
        if leader is not None:
            fields = next(member for member in members if member[4] == leader)
            lines.append("Member\t%d\t%s\t%d\t%s\t%s" % (group_id, fields[2], member_level + leader_offset, leader,
                                                         fields[5]))
            role = TEMPLATE_ROLES.get(fields[5], "melee")
            if counts[role] > 0:
                counts[role] -= 1
            else:
                largest = max(counts, key=lambda name: counts[name])
                counts[largest] -= 1
        for role in ("tank", "melee", "ranged", "caster", "healer"):
            cycle = ROLE_CLASSES[tanks if role == "tank" else role]
            for index in range(counts[role]):
                class_name, template = cycle[index % len(cycle)]
                lines.append("Member\t%d\t%s\t%d\t-\t%s" % (group_id, class_name, member_level, template))
    return lines


def adjust_members(raid, shift, healers):
    """The level's own raid composition with every member level moved by shift (at least 1) and, with healers, that
    many members of the healer slot (ROLE_MEMBER healer) in every group (RA11): members of the role that has the most members (tanks
    only when no other role is left, never the named leader) become healers at their level, surplus healers become
    melee members (ROLE_CLASSES melee, first class)."""
    lines = raid.split("\n")
    leaders = {}
    for line in lines:
        fields = line.split("\t")
        if fields[0] == "Group":
            leaders[fields[1]] = None if fields[2] == "-" else fields[2]
    members = {}
    for index, line in enumerate(lines):
        fields = line.split("\t")
        if fields[0] != "Member":
            continue
        fields[3] = str(max(1, int(fields[3]) + shift))
        lines[index] = "\t".join(fields)
        if fields[4] != leaders.get(fields[1]):
            members.setdefault(fields[1], []).append(index)

    def role(index):
        """Role of a member line: the healer slot of ROLE_MEMBER, else the role of its template's skill group."""
        fields = lines[index].split("\t")
        if (fields[2], fields[5]) == ROLE_MEMBER["healer"]:
            return "healer"
        return TEMPLATE_ROLES.get(fields[5], "melee")

    if healers is not None:
        for group_id, indexes in members.items():
            have = [index for index in indexes if role(index) == "healer"]
            while len(have) < int(healers):
                counts = {}
                for index in indexes:
                    if role(index) != "healer":
                        counts.setdefault(role(index), []).append(index)
                if not counts:
                    break
                others = [name for name in counts if name != "tank"] or ["tank"]
                chosen = max(others, key=lambda name: len(counts[name]))
                index = counts[chosen][-1]
                fields = lines[index].split("\t")
                fields[2], fields[5] = ROLE_MEMBER["healer"]
                lines[index] = "\t".join(fields)
                have.append(index)
            while len(have) > int(healers):
                index = have.pop()
                fields = lines[index].split("\t")
                fields[2], fields[5] = ROLE_CLASSES["melee"][0]
                lines[index] = "\t".join(fields)
    return "\n".join(lines)


def make_campaign_level(params, folder):
    """Writes the variant of a story level (countdown, interval, escape share, composition) and returns its path."""
    # The story level of its wing package (wing 1 public, wings 2 to 6 from the content repository)
    sys.path.insert(0, str(REPO / "scripts"))
    import campaign_packages
    text = campaign_packages.read_level(REPO, params["level"])
    block = re.search(r"^\[Raid\]$.*?^\[/Raid\]$", text, re.S | re.M)
    raid = block.group(0)
    for key, value in (("Countdown", params["countdown"]), ("Interval", params.get("interval_level")),
                       ("EscapeShare", params["escape"])):
        if value is not None:
            raid = re.sub(r"(?m)^%s\t.*$" % key, "%s\t%s" % (key, fmt(value)), raid, count=1)
    if params.get("member_level") is not None:
        members = campaign_members(params["level"], text, int(params["member_level"]), int(params["leader_offset"]),
                                   float(params["share"]), params.get("healers"))
        kept = [line for line in raid.split("\n") if not line.startswith("Member\t")]
        groups = [line for line in kept if line.startswith("Group\t")]
        out = [line for line in kept if not line.startswith("Group\t") and line != "[/Raid]"]
        for group in groups:
            group_id = group.split("\t")[1]
            out.append(group)
            out.extend(line for line in members if line.split("\t")[1] == group_id)
        out.append("[/Raid]")
        raid = "\n".join(out)
    elif params.get("level_shift") is not None or params.get("healers") is not None:
        raid = adjust_members(raid, int(params.get("level_shift") or 0), params.get("healers"))
    text = text[:block.start()] + raid + text[block.end():]
    if params.get("treasury_gold") is not None:
        # The attacked keeper (seat 1 in every story level) starts with that much gold: what the dungeon heart cannot
        # hold goes into his treasuries, so that the raid finds gold to plunder there
        text = add_treasury_gold(text, params["treasury_gold"])
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    path = folder / ("%s-%s.level" % (params["level"], key))
    if not path.exists():
        path.write_text(text, encoding="utf-8", newline="\n")
    return path


def make_level(params, folder):
    """Writes the level variant of the parameters and returns its path."""
    if params.get("level"):
        return make_campaign_level(params, folder)
    text = TEMPLATE.read_text(encoding="utf-8")
    groups = params["groups"]
    raid = ["[Raid]", "Gate\t%d\t%d\t0" % GATE, "Seats\t2\t1",
            "Countdown\t%s" % fmt(params["countdown"]), "Interval\t%s" % fmt(params["interval"]),
            "EscapeShare\t%s" % ("-" if params["escape"] is None else fmt(params["escape"]))]
    for group_id in range(1, groups + 1):
        leader = "SimLeader%d" % group_id
        raid.append("Group\t%d\t%s" % (group_id, leader))
        raid.extend(raid_members(params["size"], params["hero_level"], params["composition"], group_id, leader))
    raid.append("[/Raid]")
    text = re.sub(r"^\[Raid\]$.*?^\[/Raid\]$", lambda match: "\n".join(raid), text, flags=re.S | re.M)

    creatures = ["[Creatures]",
                 "# SeatId\tName\tMeshName\tPosX\tPosY\tPosZ\tClassName\tLevel\tCurrentXP\tCurrentHP\t"
                 "CurrentWakefulness\tCurrentHunger\tGoldToDeposit\tLeftWeapon\tRightWeapon\tCarriedSkill\t"
                 "CarriedWeapon\tNbCreatureEffects\tN*CreatureEffects"]
    for index in range(params["keeper_count"]):
        class_name = KEEPER_POOL[index % len(KEEPER_POOL)]
        x, y = KEEPER_AREA[index % len(KEEPER_AREA)]
        creatures.append("1\tSimKeeper%d\t%s\t%d\t%d\t0\t%s\t%d\t0\tmax\t100\t0\t0\tnone\tnone\tnullSkillType\tnone\t0"
                         % (index + 1, class_name, x, y, class_name, params["keeper_level"]))
    creatures.append("[/Creatures]")
    text = re.sub(r"^\[Creatures\]$.*?^\[/Creatures\]$", lambda match: "\n".join(creatures), text,
                  flags=re.S | re.M)
    # No script: the countdown, the interval and the escape share come from the [Raid] section or the config
    # (the section is left out: an empty one does not load)
    text = re.sub(r"^\[Triggers\]$.*?^\[/Triggers\]$\n?", "", text, flags=re.S | re.M)
    if params.get("treasury_gold") is not None:
        text = add_treasury_gold(text, params["treasury_gold"])
    if params.get("treasury_offset") is not None:
        text = move_treasury(text, int(params["treasury_offset"]))

    # Named after its content, so that a changed generator never reuses an older level file
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    path = folder / ("sim-%s.level" % key)
    if not path.exists():
        path.write_text(text, encoding="utf-8", newline="\n")
    return path


def add_treasury_gold(text, gold):
    """Gives the keeper's seat the gold to store (the level start puts the seat's gold into its treasuries)."""
    return re.sub(r"(seatId\t1\n(?:.*\n)*?gold\t)\d+", lambda match: match.group(1) + str(int(gold)), text, count=1)


def move_treasury(text, offset):
    """Moves the 3x3 treasury (centre 19,19 on the straight way from the gate to the heart) sideways: its centre goes
    to (19 + offset, 19 - offset), so that its nearest tile lies offset-1 tiles (largest of the x and y distance) off
    the diagonal way the raid takes."""
    centre_x, centre_y = 19 + offset, 19 - offset
    tiles = ["%d\t%d" % (centre_x + dx, centre_y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    return re.sub(r"(3\tTreasury1\t1\t9\n)(?:\d+\t\d+\n){9}", lambda match: match.group(1) + "\n".join(tiles) + "\n",
                  text, count=1)


def fmt(value):
    """A number as the level and config files write it."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def data_folder(build, work, overrides):
    """The data folder of a config variant: links to the build folder's data and a patched copy of config/."""
    key = hashlib.sha1(json.dumps(sorted(overrides.items())).encode()).hexdigest()[:12]
    folder = work / "data" / key
    if (folder / "ready").exists():
        return folder
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for entry in build.iterdir():
        if entry.name in ("config",) or entry.suffix in (".vcxproj", ".filters") or entry.name.startswith("CMake"):
            continue
        if entry.name in ("resources.cfg", "plugins.cfg"):
            shutil.copy2(entry, folder / entry.name)
        elif entry.is_dir() and entry.name in ("levels", "gui", "materials", "models", "music", "particles",
                                                "python", "scripts", "shaders", "sounds", "ogre-includes"):
            link(entry.resolve(), folder / entry.name)
    shutil.copytree((build / "config").resolve(), folder / "config")
    patch_global(folder / "config" / "global.cfg", overrides)
    (folder / "ready").write_text(json.dumps(overrides, sort_keys=True), encoding="utf-8")
    return folder


def link(target, name):
    """A directory junction on Windows, a symbolic link elsewhere."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(name), str(target)], check=True, stdout=subprocess.DEVNULL)
    else:
        os.symlink(target, name)


def patch_global(path, overrides):
    """Replaces the values of the given 'Section.Key' entries in global.cfg; fails on an unknown key."""
    text = path.read_text(encoding="utf-8")
    for full_key, value in overrides.items():
        section, key = full_key.split(".")
        block = re.search(r"\[%s\](.*?)\[/%s\]" % (section, section), text, re.S)
        if block is None:
            raise SystemExit("unknown section " + section)
        new_block, count = re.subn(r"(\n\s*%s\t)[^\n]*" % re.escape(key),
                                   lambda match: match.group(1) + fmt(value), block.group(1))
        if count != 1:
            raise SystemExit("unknown key " + full_key)
        text = text[:block.start(1)] + new_block + text[block.end(1):]
    path.write_text(text, encoding="utf-8", newline="\n")


def runtime_environment():
    """The environment of the game process: the libraries of the dependency folder (BUILD_DEPS_ROOT, else
    build-deps in the user profile) and Python (BUILD_PYTHON_ROOT) come first on PATH, as the build scripts set them."""
    env = dict(os.environ)
    deps = os.environ.get("BUILD_DEPS_ROOT") or os.path.join(os.path.expanduser("~"), "build-deps")
    python = os.environ.get("BUILD_PYTHON_ROOT") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                                                                 "Python", "Python314")
    env["PATH"] = os.pathsep.join([os.path.join(deps, "install", "bin"), python, env.get("PATH", "")])
    return env


def force_classes(count):
    """The classes of a reference keeper force of count creatures: the keeper pool interleaved as KEEPER_POOL says."""
    return [KEEPER_POOL[index % len(KEEPER_POOL)] for index in range(int(count))]


def game_options(params):
    """The game options of the reference keeper force (--force-count, --force-level) and the hand limit."""
    args = []
    if params.get("force_count"):
        args += ["--raid-sim-force", ",".join(force_classes(params["force_count"])),
                 "--raid-sim-force-level", str(int(params.get("force_level") or 1))]
    if params.get("hand_limit"):
        args.append("--raid-sim-hand-limit")
    if params.get("hand_player"):
        args.append("--raid-sim-hand-player")
    if params.get("difficulty"):
        args += ["--raid-sim-difficulty", str(params["difficulty"])]
    if params.get("goal_player"):
        args.append("--raid-sim-goal-player")
    return args


def run_one(exe, data, level, seed, seconds, keeper_ai, out_file, options=()):
    """Runs one simulation and returns (exit code, wall seconds, stdout). A run is stopped after four times its game
    time of wall time (at least 300 s): a fully loaded host runs the large levels slower than the game clock."""
    app_data = out_file.parent / (out_file.stem + "-appdata")
    app_data.mkdir(parents=True, exist_ok=True)
    args = [str(exe), "--raid-sim", str(level), "--seconds", str(seconds), "--seed", str(seed),
            "--raid-sim-out", str(out_file), "--appData", str(app_data), "--loglevel", "2"] + list(options)
    if keeper_ai:
        args.append("--raid-sim-keeper-ai")
    start = time.monotonic()
    try:
        done = subprocess.run(args, cwd=str(data), capture_output=True, text=True, timeout=max(300, 4 * seconds),
                              env=runtime_environment())
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired as error:
        code, output = -9, "timeout: " + str(error)
    if code != 0:
        # The error lines of the game log tell why a run failed
        for log in app_data.rglob("moreya.log"):
            errors = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                      if "ERROR" in line or "CRITICAL" in line]
            output += "\n" + "\n".join(errors[:20])
    shutil.rmtree(app_data, ignore_errors=True)
    return code, time.monotonic() - start, output


def read_turns(path):
    """The turn lines of a run as dicts and the result line."""
    rows, result = [], {}
    header = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# keeper="):
            result["keeper"] = line[len("# keeper="):].strip()
            continue
        if line.startswith("# openGoals="):
            result["openGoals"] = line[len("# openGoals="):].strip()
            continue
        if line.startswith("# result="):
            result.update(dict(item.split("=", 1) for item in line[2:].split()))
            continue
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if header is None:
            header = fields
            continue
        rows.append({name: float(value) for name, value in zip(header, fields)})
    return rows, result


# SIM2 thresholds (seconds): a stretch without any fighting after the first raid group came; the gap that separates
# two fights; a fight that decides within QUICK_FIGHT seconds counts as quickly decided.
FIGHT_GAP = 5.0
QUICK_FIGHT = 10.0
QUICK_DECISION = 60.0


def measures(rows, result):
    """The measures of one run (see the report for their meaning)."""
    out = {"result": result.get("result", "none"), "end": float(result.get("seconds", 0)),
           "openGoals": result.get("openGoals", ""), "keeper": result.get("keeper", ""),
           "wall": float(result.get("wallSeconds", 0))}
    arrival = next((row["seconds"] for row in rows if row["arrived"] >= 1), None)
    out["arrival"] = arrival
    if arrival is None or not rows:
        return out
    phase2 = [row for row in rows if row["seconds"] >= arrival]
    fighting = [row["raidFighting"] + row["keeperFighting"] > 0 for row in phase2]
    contact = next((row["seconds"] for row, fight in zip(phase2, fighting) if fight), None)
    out["contact"] = None if contact is None else contact - arrival
    step = 1.0 / TURNS_PER_SECOND
    out["phase2"] = phase2[-1]["seconds"] - arrival
    out["fightSeconds"] = sum(step for fight in fighting if fight)
    out["idleSeconds"] = sum(step for fight in fighting if not fight)
    # Longest stretch without fighting after the first contact (before it the raid marches)
    longest, current = 0.0, 0.0
    started = False
    for fight in fighting:
        if fight:
            started = True
            current = 0.0
        elif started:
            current += step
            longest = max(longest, current)
    out["longestIdle"] = longest
    # Fights: fighting stretches separated by at least FIGHT_GAP seconds without fighting
    fights = []
    begin, last_fight = None, None
    for row, fight in zip(phase2, fighting):
        if fight:
            if begin is None or row["seconds"] - last_fight > FIGHT_GAP:
                if begin is not None:
                    fights.append((begin, last_fight))
                begin = row
            last_fight = row["seconds"]
    if begin is not None:
        fights.append((begin, last_fight))
    decided = []
    for start_row, end_seconds in fights:
        end_row = next(row for row in phase2 if row["seconds"] >= end_seconds)
        losses = (start_row["raidAlive"] - end_row["raidAlive"]) + (start_row["keeperAlive"] - end_row["keeperAlive"])
        if losses > 0:
            decided.append(end_seconds - start_row["seconds"])
    out["fights"] = len(fights)
    out["decidedFights"] = len(decided)
    out["quickShare"] = (sum(1 for length in decided if length < QUICK_FIGHT) / len(decided)) if decided else None
    out["meanFight"] = statistics.mean(decided) if decided else None
    first = phase2[0]
    raid_peak = max(row["raidAlive"] for row in phase2)
    # The keeper's fighters when the first raid group arrived (a reference force stands at the heart from then on)
    keeper_start = first["keeperAlive"]
    out["raidPeak"] = raid_peak
    out["raidLeft"] = phase2[-1]["raidAlive"]
    out["keeperStart"] = keeper_start
    out["keeperLeft"] = phase2[-1]["keeperAlive"]
    out["keeperLossShare"] = (keeper_start - phase2[-1]["keeperAlive"]) / keeper_start if keeper_start else None
    out["keeperRetreats"] = sum(1 for before, after in zip(phase2, phase2[1:])
                                if after["keeperRetreating"] > before["keeperRetreating"])
    out["raidRetreats"] = sum(1 for before, after in zip(phase2, phase2[1:])
                              if after["raidRetreating"] > before["raidRetreating"])
    out["groupsFormed"] = max(row["maxGroupId"] for row in phase2) if "maxGroupId" in phase2[0] else None
    out["fleeAt"] = next((row["seconds"] - arrival for row in phase2 if row["leadersFleeing"] > 0), None)
    gold_start = rows[0]["keeperGold"]
    out["goldStart"] = gold_start
    out["goldLost"] = gold_start - min(row["keeperGold"] for row in rows)
    out["raidGoldPeak"] = max(row["raidGold"] for row in phase2)
    march = [row for row, fight in zip(phase2, fighting) if not fight and row["raidWithPlace"] > 0]
    out["cohesion"] = (statistics.mean(row["raidInPlace"] / row["raidWithPlace"] for row in march)
                       if march else None)
    joined = [row["keeperGroupMembers"] / row["keeperAlive"] for row, fight in zip(phase2, fighting)
              if fight and row["keeperAlive"] > 0]
    out["participation"] = statistics.mean(joined) if joined else None
    out["placeDistance"] = (statistics.mean(row["raidPlaceDistance"] / row["raidWithPlace"] for row in march)
                            if march and "raidPlaceDistance" in march[0] else None)
    marching = [row for row, fight in zip(phase2, fighting) if not fight and row["raidAlive"] > 1]
    out["marchSpread"] = (statistics.mean(row["raidSpread"] for row in marching)
                          if marching and "raidSpread" in marching[0] else None)
    # From the first contact to the end of the run (a fight that decides the raid within QUICK_DECISION seconds of
    # the first contact counts as decided quickly)
    out["decision"] = None if contact is None else phase2[-1]["seconds"] - (arrival + out["contact"])
    out["quick"] = None if out["decision"] is None or out["result"] == "timeout" else (
        1.0 if out["decision"] < QUICK_DECISION else 0.0)
    out["fled"] = 0.0 if out["fleeAt"] is None else 1.0
    # A flight the keeper caught: a leader fled and did not escape (RA8 and RA8b)
    out["caught"] = 1.0 if out["fled"] and out["result"] != "escaped" else 0.0
    if "handDrops" in rows[-1]:
        out["handDrops"] = rows[-1]["handDrops"]
    # The main fight of the first raid group is over when three quarters of it have fallen (or the keeper has no
    # fighter left), measured from its arrival; before a second group arrives
    later = [row for row in phase2 if row["arrived"] <= 1]
    peak_first = max((row["raidAlive"] for row in later), default=0)
    out["mainFight"] = next((row["seconds"] - arrival for row in later
                             if peak_first and (row["raidAlive"] <= peak_first * 0.25 or row["keeperAlive"] == 0)),
                            None)
    if "treasuryGold" in rows[0]:
        treasury_start = rows[0]["treasuryGold"]
        # Gold the raid took from the treasuries (the lowest stock; workers may carry dropped gold back later)
        out["treasuryTaken"] = treasury_start - min(row["treasuryGold"] for row in rows)
        out["treasuryTakenShare"] = out["treasuryTaken"] / treasury_start if treasury_start else None
        out["treasuryHit"] = 1.0 if out["treasuryTaken"] > 0 else 0.0
        out["treasuryLeft"] = rows[-1]["treasuryGold"]
    if "plunderedTreasury" in rows[0]:
        out["plunderTreasury"] = rows[-1]["plunderedTreasury"]
        out["plunderHeart"] = rows[-1]["plunderedHeart"]
        out["treasuryPlundered"] = 1.0 if out["plunderTreasury"] > 0 else 0.0
    out["fleeSeconds"] = sum(step for row in phase2 if row.get("raidFleeing", 0) > 0)
    out["heartLostShare"] = 1.0 - (phase2[-1]["heartHp"] / rows[0]["heartHp"]) if rows[0]["heartHp"] else None
    return out


def phase1_measures(rows, out):
    """Phase 1 of a story level: when the keeper had reached all phase-1 main goals of the level (all main goals but
    the raid goal) for the first time, the most of them he reached, and his build-up (fighters, claimed tiles, room
    tiles, mined gold) at the raid's arrival or at the end of the run."""
    if not rows or "phase1Total" not in rows[0]:
        return out
    total = rows[0]["phase1Total"]
    out["phase1Total"] = total
    out["phase1Max"] = max(row["phase1Reached"] for row in rows)
    out["phase1Done"] = next((row["seconds"] for row in rows if total > 0 and row["phase1Reached"] >= total), None)
    goals = {}
    for row in rows:
        reached = int(row["phase1Reached"])
        for count in range(1, reached + 1):
            goals.setdefault(count, row["seconds"])
    out["phase1Steps"] = [goals.get(count) for count in range(1, int(total) + 1)]
    at = next((row for row in rows if row["arrived"] >= 1), rows[-1])
    out["fightersAtArrival"] = at["keeperAlive"]
    out["claimedAtArrival"] = at["claimedTiles"]
    out["roomTilesAtArrival"] = at["roomTiles"]
    out["minedAtArrival"] = at["goldMined"]
    if "goalsTotal" in rows[0]:
        # The goal player (R13): every goal of the seat, main and optional, without the raid goal
        out["goalsTotal"] = rows[0]["goalsTotal"]
        out["goalsMax"] = max(row["goalsReached"] for row in rows)
        out["goalsEnd"] = rows[-1]["goalsReached"]
        out["allGoals"] = next((row["seconds"] for row in rows
                                if rows[0]["goalsTotal"] > 0 and row["goalsReached"] >= rows[0]["goalsTotal"]), None)
    return out


def default_params():
    """The parameters of a level variant before the command line changes them."""
    return {"size": 10, "groups": 1, "hero_level": 4, "composition": "all", "keeper_count": 10, "keeper_level": 4,
            "countdown": 10, "interval": 90, "escape": None, "treasury_gold": None, "treasury_offset": None,
            "level": None, "interval_level": None, "member_level": None, "leader_offset": None, "share": None,
            "force_count": None, "force_level": None, "hand_limit": 0, "healers": None, "level_shift": None,
            "hand_player": 0, "difficulty": None, "goal_player": 0}


def run_batch(exe, work, params, overrides, seeds, seconds=900, keeper_ai=False, jobs=6, quiet=False):
    """Runs the seeds of one variant (cached in runs.jsonl) and returns their measures."""
    build = exe.parent.parent if exe.parent.name.lower() in ("release", "debug") else exe.parent
    work.mkdir(parents=True, exist_ok=True)
    data = data_folder(build, work, overrides)
    (work / "levels").mkdir(exist_ok=True)
    level = make_level(params, work / "levels")
    cache_file = work / "runs.jsonl"
    cache = {}
    if cache_file.exists():
        for line in cache_file.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            cache[entry["key"]] = entry
    exe_stamp = str(int(exe.stat().st_mtime))
    todo, results = [], []
    for seed in seeds:
        key = hashlib.sha1(json.dumps([params, sorted(overrides.items()), seed, seconds, keeper_ai, exe_stamp,
                                       level.name], sort_keys=True).encode()).hexdigest()
        if key in cache:
            results.append(cache[key])
        else:
            todo.append((seed, key))
    (work / "turns").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {}
        for seed, key in todo:
            out_file = work / "turns" / (key[:16] + ".tsv")
            futures[pool.submit(run_one, exe, data, level, seed, seconds, keeper_ai, out_file,
                                game_options(params))] = (seed, key, out_file)
        for future in concurrent.futures.as_completed(futures):
            seed, key, out_file = futures[future]
            code, wall, output = future.result()
            entry = {"key": key, "params": params, "overrides": overrides, "seed": seed, "seconds": seconds,
                     "keeperAi": keeper_ai, "code": code, "wall": round(wall, 2)}
            if code == 0 and out_file.exists():
                rows, result = read_turns(out_file)
                entry["m"] = phase1_measures(rows, measures(rows, result))
            else:
                entry["error"] = output[-2000:]
            with cache_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
            results.append(entry)
            if not quiet:
                print("seed %d code %d wall %.1fs %s" % (seed, code, wall, entry.get("m", {}).get("result")),
                      flush=True)
    return results


def summarize(results):
    """Means and shares over the runs of one variant."""
    good = [entry["m"] for entry in results if "m" in entry]
    summary = {"runs": len(results), "errors": len(results) - len(good)}
    if not good:
        return summary
    for outcome in ("defeated", "escaped", "heartlost", "timeout"):
        summary[outcome] = sum(1 for m in good if m["result"] == outcome) / len(good)
    for name in ("phase2", "contact", "fightSeconds", "idleSeconds", "longestIdle", "fights", "decidedFights",
                 "quickShare", "meanFight", "keeperLossShare", "raidLeft", "keeperLeft", "keeperRetreats",
                 "raidRetreats", "groupsFormed", "fleeAt", "goldLost", "raidGoldPeak", "cohesion", "participation",
                 "heartLostShare", "fleeSeconds", "placeDistance", "marchSpread", "decision", "quick", "fled",
                 "mainFight", "treasuryTaken", "treasuryTakenShare", "treasuryHit", "treasuryLeft", "plunderTreasury",
                 "plunderHeart", "treasuryPlundered", "wall", "caught", "handDrops", "phase1Max", "phase1Done", "fightersAtArrival",
                 "claimedAtArrival", "roomTilesAtArrival", "minedAtArrival"):
        values = [m[name] for m in good if m.get(name) is not None]
        summary[name] = round(statistics.mean(values), 3) if values else None
    return summary


def parse_overrides(items):
    """'Section.Key=Value' items as a dict with numbers."""
    overrides = {}
    for item in items or []:
        key, value = item.split("=", 1)
        overrides[key] = float(value) if re.match(r"^-?[0-9.]+$", value) else value
    return overrides


def sweep(exe, work, params, overrides, axis, values, seeds, seconds, jobs, report, keeper_ai=False):
    """Runs one variant per value of the axis (a level parameter or a 'Section.Key' of global.cfg) and writes one
    summary line per value to the report list."""
    for value in values:
        variant_params = dict(params)
        variant_overrides = dict(overrides)
        if "." in axis:
            variant_overrides[axis] = value
        else:
            variant_params[axis] = value
        started = time.monotonic()
        results = run_batch(exe, work, variant_params, variant_overrides, seeds, seconds, keeper_ai, jobs=jobs,
                            quiet=True)
        summary = summarize(results)
        line = {"axis": axis, "value": value, "params": variant_params, "overrides": variant_overrides,
                "seeds": "%d-%d" % (seeds[0], seeds[-1]), "summary": summary,
                "batchWall": round(time.monotonic() - started, 1)}
        report.append(line)
        print(json.dumps({"axis": axis, "value": value, "size": variant_params["size"],
                          "groups": variant_params["groups"], "hero": variant_params["hero_level"],
                          "keeper": "%dx%d" % (variant_params["keeper_count"], variant_params["keeper_level"]),
                          "won": summary.get("defeated"), "esc": summary.get("escaped"),
                          "heart": summary.get("heartlost"), "tout": summary.get("timeout"),
                          "p2": summary.get("phase2"), "idleMax": summary.get("longestIdle"),
                          "quick": summary.get("quickShare"), "kLoss": summary.get("keeperLossShare"),
                          "part": summary.get("participation"), "coh": summary.get("cohesion"),
                          "kRet": summary.get("keeperRetreats"), "groups": summary.get("groupsFormed"),
                          "gold": summary.get("goldLost"), "contact": summary.get("contact"),
                          "flee": summary.get("fleeSeconds"), "wall": summary.get("wall")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["run", "sweep"])
    parser.add_argument("--axis", help="sweep: level parameter or Section.Key of global.cfg")
    parser.add_argument("--values", help="sweep: comma-separated values of the axis")
    parser.add_argument("--report", type=Path, help="sweep: JSON lines file the summaries are appended to")
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--seeds", default="1-8")
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--keeper-ai", action="store_true")
    parser.add_argument("--set", action="append", help="Section.Key=Value of global.cfg")
    for name, value in default_params().items():
        parser.add_argument("--" + name.replace("_", "-"), default=value,
                            type=(str if isinstance(value, str) or name in ("level", "difficulty")
                                  else float if value is None else type(value)))
    args = parser.parse_args()
    params = {name: getattr(args, name) for name in default_params()}
    if args.command == "sweep":
        values = [float(value) if re.match(r"^-?[0-9.]+$", value) else value for value in args.values.split(",")]
        values = [int(value) if isinstance(value, float) and value.is_integer() and "." not in args.axis
                  else value for value in values]
        report = []
        sweep(args.exe.resolve(), args.work.resolve(), params, parse_overrides(args.set), args.axis, values,
              parse_seeds(args.seeds), args.seconds, args.jobs, report, args.keeper_ai)
        if args.report:
            with args.report.open("a", encoding="utf-8") as handle:
                for line in report:
                    handle.write(json.dumps(line) + "\n")
        return 0
    results = run_batch(args.exe.resolve(), args.work.resolve(), params, parse_overrides(args.set),
                        parse_seeds(args.seeds), args.seconds, args.keeper_ai, args.jobs)
    print(json.dumps(summarize(results), indent=1))


if __name__ == "__main__":
    sys.exit(main())
