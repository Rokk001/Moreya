#!/usr/bin/env python3
"""Raid simulation runner: plays the raid test level headless with the real game and the real config.

The game binary has a headless raid simulation mode (--raid-sim, source/utils/RaidSimulation.h): it loads a level with
a [Raid] section on a server without window, network or client, runs the real game turns as fast as it can with a
fixed random seed and writes one line per turn (raid and keeper state). This script
  - builds level variants from levels/skirmish/TestRaid.level (raid size, groups, hero level and composition, keeper
    force, countdown, interval, escape share), written to the work folder only,
  - builds a data folder per config variant: links to the game data of the build folder and a copy of config/ in which
    the given [GroupCombat] and [Raid] keys of global.cfg are replaced,
  - runs the seeds in parallel, reads the turn lines and computes the measures of a run (see measures()),
  - writes one JSON line per run to <work>/runs.jsonl (cached: a run with the same level, config and seed is not
    repeated).

Usage (from the repository root, after building the game, e.g. in build/r3):
  python tools/balance/raid_sim.py run --exe build/r3/Release/opendungeons-plus.exe --work out/raid-sim \
      --size 10 --hero-level 4 --keeper-count 10 --keeper-level 4 --seeds 1-8 --set GroupCombat.GroupFormingDistance=8
  python tools/balance/raid_sim.py experiment <name> --exe ... --work ...   (the experiments of the R3 report)
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

# The keeper's fighters of the keeper faction's spawn pool (config/factions.cfg) in pool order, without the scouts
# (CaveHornet, Goblin) and the worker: the reference keeper force cycles through them.
KEEPER_POOL = ["Spider", "Rat", "Roach", "Cultist", "LavaSpawn", "LizardMan", "DarkElf", "Orc", "PitDemon", "Troll"]

# Raid members per role: class and fixed skill template (the role follows from the template, rules G3).
ROLE_MEMBER = {
    "tank": ("Knight", "Guardian"),
    "melee": ("Dwarf1", "Berserker"),
    "ranged": ("Elf", "Marksman"),
    "healer": ("Wizard", "Healer"),
    "caster": ("Wizard", "Destroyer"),
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


def make_level(params, folder):
    """Writes the level variant of the parameters and returns its path."""
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

    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
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


def run_one(exe, data, level, seed, seconds, keeper_ai, out_file):
    """Runs one simulation and returns (exit code, wall seconds, stdout)."""
    app_data = out_file.parent / (out_file.stem + "-appdata")
    app_data.mkdir(parents=True, exist_ok=True)
    args = [str(exe), "--raid-sim", str(level), "--seconds", str(seconds), "--seed", str(seed),
            "--raid-sim-out", str(out_file), "--appData", str(app_data), "--loglevel", "2"]
    if keeper_ai:
        args.append("--raid-sim-keeper-ai")
    start = time.monotonic()
    try:
        done = subprocess.run(args, cwd=str(data), capture_output=True, text=True, timeout=max(120, seconds),
                              env=runtime_environment())
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired as error:
        code, output = -9, "timeout: " + str(error)
    shutil.rmtree(app_data, ignore_errors=True)
    return code, time.monotonic() - start, output


def read_turns(path):
    """The turn lines of a run as dicts and the result line."""
    rows, result = [], {}
    header = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# result="):
            result = dict(item.split("=", 1) for item in line[2:].split())
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
    keeper_start = rows[0]["keeperAlive"]
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


def default_params():
    """The parameters of a level variant before the command line changes them."""
    return {"size": 10, "groups": 1, "hero_level": 4, "composition": "all", "keeper_count": 10, "keeper_level": 4,
            "countdown": 10, "interval": 90, "escape": None, "treasury_gold": None, "treasury_offset": None}


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
        key = hashlib.sha1(json.dumps([params, sorted(overrides.items()), seed, seconds, keeper_ai, exe_stamp],
                                      sort_keys=True).encode()).hexdigest()
        if key in cache:
            results.append(cache[key])
        else:
            todo.append((seed, key))
    (work / "turns").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {}
        for seed, key in todo:
            out_file = work / "turns" / (key[:16] + ".tsv")
            futures[pool.submit(run_one, exe, data, level, seed, seconds, keeper_ai, out_file)] = (seed, key, out_file)
        for future in concurrent.futures.as_completed(futures):
            seed, key, out_file = futures[future]
            code, wall, output = future.result()
            entry = {"key": key, "params": params, "overrides": overrides, "seed": seed, "seconds": seconds,
                     "keeperAi": keeper_ai, "code": code, "wall": round(wall, 2)}
            if code == 0 and out_file.exists():
                rows, result = read_turns(out_file)
                entry["m"] = measures(rows, result)
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
                 "plunderHeart", "treasuryPlundered", "wall"):
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


def sweep(exe, work, params, overrides, axis, values, seeds, seconds, jobs, report):
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
        results = run_batch(exe, work, variant_params, variant_overrides, seeds, seconds, jobs=jobs, quiet=True)
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
                            type=(str if isinstance(value, str) else float if value is None else type(value)))
    args = parser.parse_args()
    params = {name: getattr(args, name) for name in default_params()}
    if args.command == "sweep":
        values = [float(value) if re.match(r"^-?[0-9.]+$", value) else value for value in args.values.split(",")]
        values = [int(value) if isinstance(value, float) and value.is_integer() and "." not in args.axis
                  else value for value in values]
        report = []
        sweep(args.exe.resolve(), args.work.resolve(), params, parse_overrides(args.set), args.axis, values,
              parse_seeds(args.seeds), args.seconds, args.jobs, report)
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
