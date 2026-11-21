#!/usr/bin/env python3
"""Non-compiling check of the wiring of the raid (raid plan R2: config keys V1/C5, the [Raid] section and its saving
and loading mid-raid C3, the level script vocabulary, the HUD countdown with the early opening C6, the test level,
skirmish and multiplayer unchanged C8, campaign bonus levels without raid CS5, only the loaded level attacked RA10).

A Python model written from the code computes fixed scenarios (the round trip of a running raid through the [Raid]
section, the place of the raid panel at every screen size and UI scale) and the C++ sources, the layout, the config
and the test level are checked for the statements that implement them. Nothing is compiled and the game is not
started; the integration build compiles and runs the code.

Usage: python -I source/tests/check_raid_wiring.py
Exit 0 and "raid wiring ok" when every item holds.
"""
import os
import re
import sys
import time
import xml.etree.ElementTree as ElementTree

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


MANAGER = read("source/game/RaidManager.cpp")
MANAGER_H = read("source/game/RaidManager.h")
GAME_MAP = read("source/gamemap/GameMap.cpp")
MAP_HANDLER = read("source/gamemap/MapHandler.cpp")
SCRIPT = read("source/gamemap/LevelScript.cpp")
SCRIPT_H = read("source/gamemap/LevelScript.h")
RUNNER = read("source/gamemap/LevelScriptRunner.cpp")
GLOBAL_CFG = read("config/global.cfg")
CONFIG_MANAGER = read("source/utils/ConfigManager.cpp")
CMAKE = read("CMakeLists.txt")
LAYOUT = read("gui/ModeGame.layout")
GAME_MODE = read("source/modes/GameMode.cpp")
CLIENT = read("source/network/ODClient.cpp")
SERVER = read("source/network/ODServer.cpp")
CLIENT_NOTIFICATION_H = read("source/network/ClientNotification.h")
GUI = read("source/render/Gui.cpp")
TEST_LEVEL = read("levels/skirmish/TestRaid.level")

# ------------------------------------------------------------------------------------------------ V1 / C5 config
# The keys of the [Raid] block counted once for this branch: value and whether the simulation still sets it
EXPECTED_KEYS = {
    "RaidCountdownSeconds": ("3600", False),
    "RaidWaveIntervalSeconds": ("90", False),
    "RaidLeaderEscapeShare": ("0.25", False),
    "RaidCarryTilesSmall": ("1", False),
    "RaidCarryTilesLarge": ("2", False),
    "RaidLargeMemberClasses": ("NatureMonster Defender Scarab", False),
    "RaidPlunderDetourTiles": ("6", False),
    "RaidGateArrivalTiles": ("1", False),
    "RaidGatePortcullisSink": ("2.2", False),
}
PLACEHOLDER = "PLACEHOLDER: set by simulation R3"
block = re.split(r"(?m)^\[Raid\]\s*$", GLOBAL_CFG)[1].split("[/Raid]")[0]
values = {}
for line in block.splitlines():
    words = line.split("#")[0].split()
    if words:
        values[words[0]] = " ".join(words[1:])
check(values == {key: value for key, (value, _) in EXPECTED_KEYS.items()}, "V1: [Raid] keys " + repr(values))
documentation = re.split(r"(?m)^\[Raid\]\s*$", GLOBAL_CFG)[0].split("[/GroupCombat]")[1]
for key, (_, placeholder) in EXPECTED_KEYS.items():
    lines = [line for line in documentation.splitlines() if re.match(r"#\s+" + key + r"\s", line)]
    check(len(lines) == 1, "V1: one documentation line for " + key)
    if lines:
        check((PLACEHOLDER in lines[0]) == placeholder, "V1: placeholder mark of " + key)
read_keys = set(re.findall(r'raidConfig\("(\w+)"\)', MANAGER)) | set(re.findall(r'getRaidConfigWords\("(\w+)"\)', MANAGER))
check(read_keys == set(EXPECTED_KEYS), "V1: the code reads exactly the configured keys " + repr(sorted(read_keys)))
# No fixed number in the code of the manager: only 0, 1, -1 (no value) and 17 (digits of a saved double)
CODE_ONLY = re.sub(r'"[^"\n]*"', '""', re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", MANAGER, flags=re.S)))
numbers = set(re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", CODE_ONLY))
check(numbers <= {"0", "1", "0.0", "1.0", "17"}, "C5: fixed numbers in RaidManager.cpp " + repr(numbers))
check('nextParam == "[Raid]"' in function(CONFIG_MANAGER, "bool ConfigManager::loadGlobalConfig("),
      "V1: global.cfg reads the [Raid] block")
for source in ("game/RaidManager.cpp", "game/RaidRules.cpp"):
    check("${SRC}/" + source in CMAKE, "the build lists " + source)

# ------------------------------------------------------------------------------------------------ C8 / CS5 / RA10 scope
update = function(MANAGER, "void RaidManager::update()")
check(re.search(r"\{\s*if\(!mHasGate \|\| !mGameMap\.isServerGameMap\(\)\)\s*return;", update) is not None,
      "C8: nothing happens without a raid")
check("Campaign::getSingleton().isPlayedLevelBonus()" in update, "CS5: a campaign bonus level has no raid")
check(re.search(r"\{\s*if\(!mHasGate\)\s*return;", function(MANAGER, "void RaidManager::exportToStream(")) is not None,
      "C8: a level without raid writes no [Raid] section")
check("mRaid->clear();" in function(GAME_MAP, "bool GameMap::loadLevel("), "RA10: only the loaded level has a raid")
check("mRaid->clear();" in function(GAME_MAP, "void GameMap::clearAll()"), "RA10: a cleared map has no raid")
misc = function(GAME_MAP, "unsigned long int GameMap::doMiscUpkeep(")
check(misc.index("mRaid->update();") < misc.index("mCombatGroups->update();") < misc.index("ge->doUpkeep()"),
      "the raid runs before the combat groups and the creatures")
for folder in ("levels/skirmish", "levels/multiplayer"):
    for name in sorted(os.listdir(os.path.join(ROOT, folder))):
        if not name.endswith(".level") or name == "TestRaid.level":
            continue
        text = read(folder + "/" + name)
        check("[Raid]" not in text and "raidopen" not in text and "raidcountdown" not in text,
              "C8: " + folder + "/" + name + " has no raid, so skirmish and multiplayer stay as they are")

# ------------------------------------------------------------------------------------------------ level script
for word in ("raidState", "raidOpen", "raidCountdown"):
    check(re.search(r"\b" + word + r"\b", SCRIPT_H) is not None, "the script knows " + word)
for doc in ("Cond    raid <state> [<raidGroupId>]", "Action  raidopen", "Action  raidcountdown <seconds>", "[Raid]",
            "Gate    <x> <y> <rotationDegrees>", "Raid<raidGroupId>"):
    check(doc in SCRIPT_H, "step 4: LevelScript.h documents " + doc)
check('if(type == "raid")' in SCRIPT and 'if(type == "raidopen")' in SCRIPT and 'if(type == "raidcountdown")' in SCRIPT,
      "the parser reads the raid vocabulary")
check('os << "raid\\t" << c.mName;' in SCRIPT and 'os << "raidopen";' in SCRIPT and
      'os << "raidcountdown\\t" << a.mNumber;' in SCRIPT, "the writer writes the raid vocabulary")
check("gameMap.getRaid().isStateMet(cond.mName, static_cast<uint32_t>(cond.mNumber))" in RUNNER and
      "gameMap.getRaid().openGateEarly(-1);" in RUNNER and
      "gameMap.getRaid().setSecondsToNextGroup(static_cast<double>(action.mNumber));" in RUNNER,
      "the runner carries out the raid vocabulary")

# ------------------------------------------------------------------------------------------------ C3 saving
export = function(MANAGER, "void RaidManager::exportToStream(")
load = function(MANAGER, "bool RaidManager::importFromStream(std::istream& is)")
for writer, reader in (('os << "Gate\\t" << mGateX << "\\t" << mGateY << "\\t" << mGateRotation', "line >> mGateX >> mGateY >> mGateRotation"),
                       ('os << "Seats\\t" << mRaidSeatId << "\\t" << mTargetSeatId', "line >> mRaidSeatId >> mTargetSeatId"),
                       ('os << "Group\\t" << group.mRaidGroupId << "\\t" << textOrDash(group.mLeaderName)', "line >> group.mRaidGroupId >> leader"),
                       ('os << "Member\\t" << group.mRaidGroupId << "\\t" << spec.mClassName << "\\t" << spec.mLevel',
                        "line >> raidGroupId >> spec.mClassName >> spec.mLevel >> name >> templateName"),
                       ('os << "State\\t" << (mStarted ? 1 : 0) << "\\t" << (mSchedule.mGateOpen ? 1 : 0)',
                        "line >> started >> gateOpen >> mSchedule.mNextGroup >> mSchedule.mSecondsToNext >> lost"),
                       ('<< "\\t" << (mSchedule.mOpenByKeeper ? 1 : 0)', "line >> openByKeeper"),
                       ('os << "\\t" << optionalNumberText(getLevelCountdownSeconds(COUNTDOWN_DIFFICULTIES[i]));',
                        "setLevelCountdownSeconds(COUNTDOWN_DIFFICULTIES[i], (values.size() == 1) ? values.front() : values[i]);"),
                       ('os << "Arrived\\t" << group.mRaidGroupId << "\\t" << textOrDash(group.mLeaderSpawned)',
                        "line >> raidGroupId >> leader >> stateText >> nbMembers"),
                       ('os << "Plundered\\t" << done.first << "\\t" << done.second', "line >> name >> room")):
    check(writer in export and reader in load, "C3: line written and read alike: " + reader)
check(export.index('"Member\\t"') < export.index("if(isGameSave)") < export.index('"State\\t"'),
      "C3: the raid is level data, the running state is written in saved games")
check("os.precision(17)" in export, "C3: the numbers are saved with all their digits")
check("setRaidMemberDetached(group.mLeaderSpawned, true);" in load and "setRaidMemberDetached(follower, true);" in load,
      "C3: a fleeing leader and his followers leave their group again")
writer = function(MAP_HANDLER, "bool writeGameMapToFile(")
check(writer.index("getCombatGroups().exportToStream(levelFile, isGameSave)") <
      writer.index("getRaid().exportToStream(levelFile, isGameSave)") < writer.rindex("if (!levelFile.good())"),
      "C3: the section is written after the combat groups")
reader = function(MAP_HANDLER, "bool readGameMapFromFile(")
optional = reader[reader.index('if(nextParam == "[CombatGroups]")'):]
check(optional.index("if(!(levelFile >> nextParam))") < optional.index('if(nextParam == "[Raid]")'),
      "C3: the reader looks for the optional section after the combat groups")
check("getRaid().importFromStream(levelFile)" in optional, "C3: the section is read by the raid")
check("def read_raid(s):" in read("source/tests/check_save_games_load.py"),
      "C3: the saved game model reads the section")


def export_model(raid, game_save):
    """Model of RaidManager::exportToStream."""
    def number(value):
        return "-" if value < 0 else repr(value)
    lines = ["[Raid]", "Gate\t%d\t%d\t%s" % (raid["gate"][0], raid["gate"][1], repr(raid["gate"][2])),
             "Seats\t%d\t%d" % raid["seats"], "Countdown\t" + "\t".join(number(v) for v in raid["countdown"]),
             "Interval\t" + number(raid["interval"]), "EscapeShare\t" + number(raid["share"])]
    for group in raid["groups"]:
        lines.append("Group\t%d\t%s" % (group["id"], group["leader"] or "-"))
        for member in group["members"]:
            lines.append("Member\t%d\t%s\t%d\t%s\t%s" % (group["id"], member[0], member[1], member[2] or "-",
                                                        member[3] or "-"))
    if game_save:
        state = raid["state"]
        lines.append("State\t%d\t%d\t%d\t%s\t%d\t%d" % (state["started"], state["open"], state["next"],
                                                       repr(state["seconds"]), state["lost"], state["byKeeper"]))
        for group in raid["groups"]:
            if group["arrived"]:
                lines.append("\t".join(["Arrived", str(group["id"]), group["spawnedLeader"] or "-", group["leaderState"],
                                        str(len(group["spawned"]))] + group["spawned"]))
        for name, room in sorted(raid["plundered"]):
            lines.append("Plundered\t%s\t%s" % (name, room))
    lines.append("[/Raid]")
    return "\n".join(lines) + "\n"


def import_model(text):
    """Model of RaidManager::importFromStream."""
    def number(token):
        return -1.0 if token == "-" else float(token)
    raid = {"groups": [], "plundered": set(), "state": {"started": 0, "open": 0, "next": 0, "seconds": -1.0, "lost": 0,
                                                        "byKeeper": 0}}
    by_id = {}
    for line in text.splitlines()[1:]:
        f = line.split()
        if f[0] == "[/Raid]":
            return raid
        if f[0] == "Gate":
            raid["gate"] = (int(f[1]), int(f[2]), float(f[3]))
        elif f[0] == "Seats":
            raid["seats"] = (int(f[1]), int(f[2]))
        elif f[0] == "Countdown":
            # one value (written before the difficulties) for Normal, Hard and Hell, or one value each
            assert len(f) in (2, 4)
            raid["countdown"] = tuple(number(v) for v in (f[1:] if len(f) == 4 else f[1:] * 3))
        elif f[0] in ("Interval", "EscapeShare"):
            raid[{"Interval": "interval", "EscapeShare": "share"}[f[0]]] = number(f[1])
        elif f[0] == "Group":
            group = {"id": int(f[1]), "leader": "" if f[2] == "-" else f[2], "members": [], "arrived": False,
                     "spawnedLeader": "", "leaderState": "none", "spawned": []}
            raid["groups"].append(group)
            by_id[group["id"]] = group
        elif f[0] == "Member":
            by_id[int(f[1])]["members"].append((f[2], int(f[3]), "" if f[4] == "-" else f[4], "" if f[5] == "-" else f[5]))
        elif f[0] == "State":
            raid["state"] = {"started": int(f[1]), "open": int(f[2]), "next": int(f[3]), "seconds": float(f[4]),
                             "lost": int(f[5]), "byKeeper": int(f[6]) if len(f) > 6 else 0}
        elif f[0] == "Arrived":
            group = by_id[int(f[1])]
            group["arrived"] = True
            group["spawnedLeader"] = "" if f[2] == "-" else f[2]
            group["leaderState"] = f[3]
            group["spawned"] = f[5:5 + int(f[4])]
        elif f[0] == "Plundered":
            raid["plundered"].add((f[1], f[2]))
    raise AssertionError("no end tag")


# Mid-raid: the first group came and its leader flees, the second waits 37.5 s more; one member plundered
RUNNING = {
    "gate": (33, 33, 90.0), "seats": (2, 1), "countdown": (2400.0, 2100.0, -1.0), "interval": -1.0, "share": 0.6,
    "groups": [
        {"id": 1, "leader": "LeaderOne", "members": [("Knight", 4, "LeaderOne", "Guardian"), ("Elf", 3, "", "Marksman")],
         "arrived": True, "spawnedLeader": "LeaderOne", "leaderState": "fleeing", "spawned": ["LeaderOne", "Elf_12"]},
        {"id": 2, "leader": "LeaderTwo", "members": [("Knight", 5, "LeaderTwo", "Guardian"), ("Wizard", 3, "", "Healer")],
         "arrived": False, "spawnedLeader": "", "leaderState": "none", "spawned": []},
    ],
    "state": {"started": 1, "open": 1, "next": 1, "seconds": 37.5, "lost": 0, "byKeeper": 0},
    "plundered": {("Elf_12", "Treasury1")},
}
check(import_model(export_model(RUNNING, True)) == RUNNING, "C3: a running raid is saved and loaded one to one")
# R13: a raid on Easy or Medium whose second group waits behind the closed gate for the player is saved and loaded as it is
WAITING = dict(RUNNING, state={"started": 1, "open": 0, "next": 1, "seconds": -1.0, "lost": 0, "byKeeper": 1})
check(import_model(export_model(WAITING, True)) == WAITING,
      "C3/R13: a raid that waits for the player keeps waiting after loading")
# R13: a level or saved game written before the difficulties (one Countdown value, State without OpenByKeeper) loads
OLD = import_model("[Raid]\nGate\t3\t4\t0\nSeats\t2\t1\nCountdown\t3600\nInterval\t-\nEscapeShare\t-\nGroup\t1\t-\n"
                   "State\t1\t0\t0\t12.5\t0\n[/Raid]\n")
check(OLD["countdown"] == (3600.0, 3600.0, 3600.0) and OLD["state"]["byKeeper"] == 0 and OLD["state"]["seconds"] == 12.5,
      "C3/R13: an old single countdown applies to every difficulty, an old saved countdown keeps running")
LEVEL_ONLY = import_model(export_model(RUNNING, False))
check(LEVEL_ONLY["state"]["started"] == 0 and not LEVEL_ONLY["groups"][0]["arrived"] and not LEVEL_ONLY["plundered"],
      "C3: a level written by the editor starts the raid from the beginning")

# ------------------------------------------------------------------------------------------------ RA2 / RA3 HUD, C6
check("mRaidCountdownToSend = mRaid->getCountdownToShow();" in function(GAME_MAP, "void GameMap::checkGameDuration()"),
      "RA2: the server sends the raid countdown")
send = function(GAME_MAP, "void GameMap::sendTimeLimit(int32_t remainingSeconds)")
check("serverNotification->mPacket << mRaidCountdownToSend;" in send and
      "serverNotification->mPacket << mRaidGateClosedToSend;" in send and
      "serverNotification->mPacket << mRaidWaitsToSend;" in send, "RA2: the countdown travels with the time limit")
check("mRaidWaitsToSend = mRaid->isWaitingForKeeper() ? 1 : 0;" in
      function(GAME_MAP, "void GameMap::checkGameDuration()"), "R13/RA2: the server sends that a group waits for the player")
check("packetReceived >> waits" in CLIENT and "mRaidWaitsForKeeper = (waits != 0);" in CLIENT,
      "R13/RA2: the client reads that a group waits for the player (older recorded packets end before it)")
check("if(!packetReceived.endOfPacket())" in CLIENT and "packetReceived >> mRaidCountdownSeconds >> gateClosed" in CLIENT,
      "RA2: the client reads the countdown (older recorded packets end before it)")
check(re.findall(r"^\s*(\w+)\s*,?\s*(?://.*)?$", CLIENT_NOTIFICATION_H.split("};")[0], re.M)[-1] == "askOpenRaidGate",
      "RA3: the request is appended at the end of the client messages")
server_case = SERVER[SERVER.index("case ClientNotificationType::askOpenRaidGate:"):]
check("getRaid().openGateEarly(clientSocket->getPlayer()->getSeat()->getId());" in server_case[:600],
      "RA3: the server opens the gate for the seat that asks")
panel_update = function(GAME_MODE, "void GameMode::updateRaidPanel()")
check('getChild("RaidPanel")' in panel_update and "button->show();" in panel_update and "button->hide();" in panel_update
      and '"Raid in "' in panel_update and '"Next group in "' in panel_update,
      "RA2/RA3/RA4: the panel shows the countdown, the button only while the gate is closed")
check('"Raid waits at the gate"' in panel_update and "isRaidWaitingForKeeper()" in panel_update and
      panel_update.index("if(waits)") < panel_update.index("button->show();"),
      "R13/RA2: on Easy and Medium the panel shows no countdown but the button while a group waits for the player")
check("ClientNotificationType::askOpenRaidGate" in function(GAME_MODE, "bool GameMode::openRaidGate("),
      "RA3: the button asks the server to open the gate")
check('getChild("RaidPanel/OpenGateButton")' in GAME_MODE and "&GameMode::openRaidGate" in GAME_MODE,
      "RA3: the button is connected")

design_width = float(re.search(r"const float LAYOUT_DESIGN_WIDTH = ([\d.]+)f;", GUI).group(1))
design_height = float(re.search(r"const float LAYOUT_DESIGN_HEIGHT = ([\d.]+)f;", GUI).group(1))
check((design_width, design_height) == (1024.0, 768.0), "C6: the layout is designed for 1024x768")
root = ElementTree.fromstring(LAYOUT.encode("utf-8"))


def area_of(window):
    """The Area property of a layout window as ((sx, ox), (sy, oy), (sx, ox), (sy, oy))."""
    for prop in window.findall("Property"):
        if prop.get("name") == "Area":
            numbers = [float(x) for x in re.findall(r"-?[\d.]+", prop.get("value"))]
            return ((numbers[0], numbers[1]), (numbers[2], numbers[3]), (numbers[4], numbers[5]), (numbers[6], numbers[7]))
    raise AssertionError("no area of " + window.get("name"))


windows = {window.get("name"): window for window in root.iter("Window")}
check("RaidPanel" in windows and "Countdown" in windows and "OpenGateButton" in windows, "C6: the raid panel exists")
raid_root = [w for w in root.find("Window").findall("Window") if w.get("name") == "RaidPanel"]
check(len(raid_root) == 1, "C6: the raid panel is a window of the root sheet")


def rect(area, width, height, scale, parent=None):
    """The screen rectangle (left, top, right, bottom) of an area at the given size and layout scale."""
    px, py, pw, ph = parent if parent else (0.0, 0.0, width, height)
    left = px + area[0][0] * pw + area[0][1] * scale
    top = py + area[1][0] * ph + area[1][1] * scale
    right = px + area[2][0] * pw + area[2][1] * scale
    bottom = py + area[3][0] * ph + area[3][1] * scale
    return left, top, right, bottom


def overlaps(first, second):
    """True when the rectangles share an area."""
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


SCREENS = [(640, 480), (800, 600), (1024, 768), (1280, 720), (1280, 1024), (1366, 768), (1920, 1080), (2560, 1440),
           (3440, 1440), (3840, 2160), (7680, 4320)]
UI_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]
if len(raid_root) == 1:
    panel_area = area_of(windows["RaidPanel"])
    for width, height in SCREENS:
        for user in UI_SCALES:
            scale = min(width / design_width, height / design_height) * user
            panel = rect(panel_area, width, height, scale)
            name = "%dx%d at %d %%" % (width, height, round(user * 100))
            check(panel[0] >= 0 and panel[1] >= 0 and panel[2] <= width and panel[3] <= height,
                  "C6: the raid panel stays on the screen at " + name)
            check(panel[1] >= rect(area_of(windows["HorizontalPipe"]), width, height, scale)[3],
                  "C6: the raid panel is below the top bar at " + name)
            check(not overlaps(panel, rect(area_of(windows["SpecialsPanel"]), width, height, scale)),
                  "C6: the raid panel leaves the specials free at " + name)
            inner = (panel[0], panel[1], panel[2] - panel[0], panel[3] - panel[1])
            text = rect(area_of(windows["Countdown"]), width, height, scale, inner)
            button = rect(area_of(windows["OpenGateButton"]), width, height, scale, inner)
            check(not overlaps(text, button) and text[2] > text[0] and button[2] > button[0],
                  "C6: countdown and button side by side at " + name)

# ------------------------------------------------------------------------------------------------ test level (step 4)
for word in ("Action\traidopen", "Action\traidcountdown\t", "Cond\traid\topen", "Cond\traid\tarrived\t1",
             "Cond\traid\tarrived\n", "Cond\traid\tfleeing", "Cond\traid\tescaped", "Cond\traid\tdefeated",
             "Cond\tevent\tRaid1\tkilled", "Action\tmainobjectiveid\t1\traid\t"):
    check(word in TEST_LEVEL, "step 4: the test level uses " + word.strip())
raid_section = re.split(r"(?m)^\[Raid\]\s*$", TEST_LEVEL)[1].split("[/Raid]")[0]
groups = re.findall(r"^Group\t(\d+)\t(\S+)", raid_section, re.M)
members = re.findall(r"^Member\t(\d+)\t(\w+)\t(\d+)\t(\S+)\t(\S+)", raid_section, re.M)
check([g[0] for g in groups] == ["1", "2"] and groups[0][1] != groups[1][1] and "-" not in (groups[0][1], groups[1][1]),
      "RA5: the test level has two raid groups, each with its own leader")
for group_id, leader in groups:
    check(any(m[0] == group_id and m[3] == leader for m in members), "RA5: leader " + leader + " is a member of his group")
check(all(m[4] != "-" for m in members if m[3] != "-"), "RA5/FQ8: the leaders follow fixed templates")
gate = re.search(r"^Gate\t(\d+)\t(\d+)\t", raid_section, re.M)
seats = re.search(r"^Seats\t(\d+)\t(\d+)", raid_section, re.M)
portal = re.search(r"\[Room\]\n10\t(\w+)\t(\d+)\t9\n((?:\d+\t\d+\n){9})", TEST_LEVEL)
check(gate is not None and seats is not None and portal is not None, "RA1: the test level has a gate room")
if gate and seats and portal:
    tiles = [tuple(int(v) for v in line.split("\t")) for line in portal.group(3).split("\n") if line]
    centre = (sorted(t[0] for t in tiles)[4], sorted(t[1] for t in tiles)[4])
    check(centre == (int(gate.group(1)), int(gate.group(2))), "RA1: the gate tile is the centre of the hero portal room")
    check(portal.group(2) == seats.group(1), "RA1: the gate room belongs to the raid seat")
    raid_seat = re.search(r"seatId\t" + seats.group(1) + r"\nteamId\t\d+\nplayer\t\w+\nfaction\t(\w+)", TEST_LEVEL)
    target_seat = re.search(r"seatId\t" + seats.group(2) + r"\nteamId\t\d+\nplayer\t(\w+)\nfaction\t(\w+)", TEST_LEVEL)
    check(raid_seat is not None and raid_seat.group(1) == "Hero", "the raid seat is a hero seat")
    check(target_seat is not None and target_seat.groups() == ("Human", "Keeper"), "the raid attacks the human keeper")
check(re.search(r"^1\tTreasury\d+\t1\t", TEST_LEVEL, re.M) is None and "\n3\tTreasury1\t1\t9\n" in TEST_LEVEL,
      "RA7: the attacked keeper has a treasury to plunder")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"wiring","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("raid wiring ok")
