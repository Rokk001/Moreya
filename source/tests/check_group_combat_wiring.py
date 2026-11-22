#!/usr/bin/env python3
"""Non-compiling check of the wiring of the shared group combat (raid plan R1: G1 forming, workers, AI keepers, no
groups without a raid, fixed templates of raid members, saving and loading, config keys V1/C5).

A Python model written from the rules computes fixed scenarios (forming on approach, the seats that form, the round
trip of a running group fight through the [CombatGroups] section) and the C++ sources are checked for the statements
that implement them: CombatGroupManager, Creature, GameMap, MapHandler, the level script and config/global.cfg.
Nothing is compiled and the game is not started; the integration build compiles and runs the code.

Usage: python -I source/tests/check_group_combat_wiring.py
Exit 0 and "group combat wiring ok" when every item holds.
"""
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


MANAGER = read("source/game/CombatGroupManager.cpp")
CREATURE = read("source/entities/Creature.cpp")
GAME_MAP = read("source/gamemap/GameMap.cpp")
MAP_HANDLER = read("source/gamemap/MapHandler.cpp")
SCRIPT = read("source/gamemap/LevelScript.cpp")
SCRIPT_H = read("source/gamemap/LevelScript.h")
RUNNER = read("source/gamemap/LevelScriptRunner.cpp")
GLOBAL_CFG = read("config/global.cfg")
CONFIG_MANAGER = read("source/utils/ConfigManager.cpp")
CMAKE = read("CMakeLists.txt")

# ------------------------------------------------------------------------------------------------ V1 / C5 config
# The keys of the [GroupCombat] block counted once for this branch: value and whether the simulation still sets it
EXPECTED_KEYS = {
    "GroupFormingDistance": ("20", False),
    "GroupDissolveDistance": ("24", False),
    "GroupRetreatHealthShare": ("0.5", False),
    "GroupRetreatMaxSeconds": ("30", False),
    "GroupRetreatCooldownSeconds": ("30", False),
    "GroupGatherRadius": ("3", False),
    "GroupAggroAdjacentTiles": ("1", False),
    "GroupAggroMemorySeconds": ("3", False),
    "GroupFormationRowSpacing": ("1", False),
    "GroupFormationRowWidth": ("6", False),
    "GroupFormationTolerance": ("2", False),
    "GroupTankPaths": ("Bulwark Protection", False),
    "GroupHealerPaths": ("Healing", False),
    "GroupRangedSkillGroups": ("archer caster", False),
}
PLACEHOLDER = "PLACEHOLDER: set by simulation R3"

block = GLOBAL_CFG.split("[GroupCombat]")[1].split("[/GroupCombat]")[0]
values = {}
for line in block.splitlines():
    words = line.split("#")[0].split()
    if words:
        values[words[0]] = " ".join(words[1:])
check(values == {key: value for key, (value, _) in EXPECTED_KEYS.items()}, "V1: [GroupCombat] keys " + repr(values))
documentation = GLOBAL_CFG.split("[GroupCombat]")[0]
for key, (_, placeholder) in EXPECTED_KEYS.items():
    lines = [line for line in documentation.splitlines() if re.match(r"#\s+" + key + r"\s", line)]
    check(len(lines) == 1, "V1: one documentation line for " + key)
    if lines:
        check((PLACEHOLDER in lines[0]) == placeholder, "V1: placeholder mark of " + key)

read_keys = set(re.findall(r'groupConfig\("(\w+)"\)', MANAGER)) | \
    set(re.findall(r'getGroupCombatConfigWords\("(\w+)"\)', MANAGER))
check(read_keys == set(EXPECTED_KEYS), "V1: the code reads exactly the configured keys " + repr(sorted(read_keys)))
# No fixed number in the code of the manager: only 0, 1, -1 (no value) and 17 (digits of a saved double)
CODE_ONLY = re.sub(r'"[^"\n]*"', '""', re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", MANAGER, flags=re.S)))
numbers = set(re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", CODE_ONLY))
check(numbers <= {"0", "1", "0.0", "1.0", "17"}, "C5: fixed numbers in CombatGroupManager.cpp " + repr(numbers))
check('nextParam == "[GroupCombat]"' in function(CONFIG_MANAGER, "bool ConfigManager::loadGlobalConfig("),
      "V1: global.cfg reads the [GroupCombat] block")
for source in ("game/CombatGroupManager.cpp", "game/CombatGroupRules.cpp", "creatureaction/CreatureActionGroupFollow.cpp",
               "creatureaction/CreatureActionGroupRetreat.cpp"):
    check("${SRC}/" + source in CMAKE, "the build lists " + source)

# ------------------------------------------------------------------------------------------------ G1 forming
FORMING = float(values["GroupFormingDistance"])


def is_keeper_seat(seat):
    """Model of CombatGroupManager::isKeeperSeat: not the neutral seat 0 and not a hero seat."""
    return seat["id"] != 0 and seat["faction"] != "Hero"


def forms(creature, raider, seats):
    """Model of the forming test of CombatGroupManager::updateKeeperGroups for one keeper creature and one raider."""
    own = seats[creature["seat"]]
    if creature["worker"] or not creature["alive"] or creature["raid"] or not is_keeper_seat(own):
        return False
    if seats[raider["seat"]]["team"] == own["team"]:
        return False
    dx = creature["x"] - raider["x"]
    dy = creature["y"] - raider["y"]
    return dx * dx + dy * dy <= FORMING * FORMING


SEATS = {
    1: {"id": 1, "faction": "Keeper", "team": 1, "player": "Human"},
    2: {"id": 2, "faction": "Keeper", "team": 2, "player": "AI"},
    3: {"id": 3, "faction": "Hero", "team": 3, "player": "AI"},
    4: {"id": 4, "faction": "Hero", "team": 4, "player": "AI"},
}


def creature(seat, x, worker=False, raid=False):
    """A creature of the scenarios at x, 0."""
    return {"seat": seat, "x": x, "y": 0, "worker": worker, "alive": True, "raid": raid}


RAIDER = creature(4, 0, raid=True)
check(forms(creature(1, int(FORMING)), RAIDER, SEATS), "G1: a keeper fighter at the forming distance forms")
check(not forms(creature(1, int(FORMING) + 1), RAIDER, SEATS), "G1: beyond the forming distance nothing forms")
check(forms(creature(2, 1), RAIDER, SEATS), "C4: the fighters of an AI keeper form groups against a raid")
check(not forms(creature(1, 1, worker=True), RAIDER, SEATS), "G1: workers are never group members")
check(not forms(creature(3, 1), RAIDER, SEATS), "G1: phase-1 heroes form no group")


def formed_groups(creatures):
    """Model of the forming of one update: the seats that form a keeper group (only raid members trigger it)."""
    raiders = [c for c in creatures if c["raid"]]
    return sorted({c["seat"] for c in creatures for r in raiders if forms(c, r, SEATS)})


# A skirmish or multiplayer fight: two keepers and a hero wave next to each other, no raid member: no group
SKIRMISH = [creature(1, 0), creature(1, 1, worker=True), creature(2, 1), creature(3, 2)]
check(formed_groups(SKIRMISH) == [], "G1/C8: without a raid no group forms (skirmish and multiplayer unchanged)")
# A raid comes near: the human keeper and the AI keeper form, the phase-1 heroes and the workers do not
RAID_FIGHT = SKIRMISH + [creature(4, 3, raid=True)]
check(formed_groups(RAID_FIGHT) == [1, 2], "G1/C4: keeper groups form against the raid, AI keepers included")

keeper_groups = function(MANAGER, "void CombatGroupManager::updateKeeperGroups(")
check("Pathfinding::squaredDistanceTile(*tile, *raiderTile)) <= formingSquared" in keeper_groups,
      "G1: forming on approach within GroupFormingDistance of a raid member")
check("for(Creature* raider : it->second)" in keeper_groups and "const std::map<uint32_t, std::vector<Creature*> >& raid"
      in keeper_groups, "G1: only members of a raid group make keeper groups form")
check("isKeeperSeat(creature->getSeat())" in keeper_groups and "areEnemies(*creature, *raider)" in keeper_groups,
      "G1: only keeper fighters of enemy seats form")
stay = function(MANAGER, "bool CombatGroupManager::canStayInKeeperGroup(")
check("isWorker()" in stay and "return false;" in stay, "G1: no worker in a keeper group")
active = function(MANAGER, "bool CombatGroupManager::isActiveRaidMember(")
check("isWorker()" in active, "G1: no worker in a raid group")
keeper_seat = function(MANAGER, "bool CombatGroupManager::isKeeperSeat(")
check('getFaction() != "Hero"' in keeper_seat and "isRogueSeat()" in keeper_seat, "G1: keeper seats")
for body, name in ((keeper_groups, "updateKeeperGroups"), (stay, "canStayInKeeperGroup"), (keeper_seat, "isKeeperSeat")):
    check("getIsHuman" not in body and "getPlayer" not in body, "C4: " + name + " treats AI and human keepers alike")
raid_groups = function(MANAGER, "void CombatGroupManager::updateRaidGroups(")
check("newGroup.mIsRaid = true;" in raid_groups and "Distance" not in raid_groups,
      "G1: a raid group is always a group (no distance condition)")
ended = function(MANAGER, "void CombatGroupManager::removeEndedGroups(")
check("GroupDissolveDistance" in ended and "mMembers.empty()" in ended, "G1: groups end with their raid or members")

# ------------------------------------------------------------------------------------------------ no raid, no group
update = function(MANAGER, "void CombatGroupManager::update()")
check(re.search(r"\{\s*if\(isEmpty\(\)\)\s*return;", update) is not None, "C8: without a raid update does nothing")
check("raid[it->second.mRaidGroupId].push_back(creature);" in update, "C8: the raid comes only from the registry")
check("mMemberGroup.empty()" in function(MANAGER, "void CombatGroupManager::notifyAttacked("), "C8: no aggro")
check("mMemberGroup.empty()" in function(MANAGER, "GameEntity* CombatGroupManager::getFightTarget("), "C8: no target")
handle_group = function(CREATURE, "void Creature::handleCombatGroup()")
check(handle_group.index("isGroupMember(getName())") < handle_group.index("clearActionQueue();"),
      "C8: a creature in no group keeps its actions")
check(re.search(r"\{\s*if\(isEmpty\(\)\)\s*return;", function(MANAGER, "void CombatGroupManager::exportToStream("))
      is not None, "C8: a game without raid writes no [CombatGroups] section")
misc = function(GAME_MAP, "unsigned long int GameMap::doMiscUpkeep(")
server = misc[misc.index("if(isServerGameMap())\n    {\n        for(Seat* seat : mSeats)"):]
check("mCombatGroups->update();" in server[:server.index("ge->doUpkeep()")], "the server updates the groups per turn")
for folder in ("levels/skirmish", "levels/multiplayer"):
    directory = os.path.join(ROOT, folder)
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".level"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        check("[CombatGroups]" not in text and "raidmember" not in text and "raidleader" not in text,
              "C8: " + folder + "/" + name + " has no raid, so skirmish and multiplayer stay as they are")

# ------------------------------------------------------------------------------------------------ fixed templates
apply = function(MANAGER, "void CombatGroupManager::applyFixedTemplates(")
check("getSkillTemplateName() == it->second.mTemplate" in apply and "setFixedSkillTemplate(it->second.mTemplate)" in apply,
      "FQ8: raid members get their fixed template")
fixed = function(CREATURE, "bool Creature::setFixedSkillTemplate(")
check("tree.getTemplates(group)" in fixed and "templates[i]->mName == templateName" in fixed and
      "CreatureSkillTree::resetBuild(" in fixed, "FQ8: the fixed template is the named template of the skill group")
respec = function(CREATURE, "void Creature::upkeepSkillTree()")
check("hasFixedSkillTemplate(getName())" in respec, "FQ8: the reset window cannot change a fixed template")
choice = function(CREATURE, "void Creature::updateSkillPoints()")
check("chooseTemplate" in choice and "getCombatGroups" not in choice, "FQ8: keeper creatures keep choosing themselves")
parse = function(SCRIPT, "bool parseAction(")
check('type == "raidmember"' in parse and 'type == "raidleader"' in parse, "the script reads raidmember and raidleader")
check('(t[3] == "-") ? std::string() : t[3]' in parse, "raidmember - means no fixed template")
write = function(SCRIPT, "void writeAction(")
check('os << "raidmember\\t"' in write and 'os << "raidleader\\t"' in write, "the script writes both actions")
run = function(RUNNER, "void runAction(")
check("registerRaidMember(name, static_cast<uint32_t>(action.mNumber), action.mText)" in run and
      "resolveCreatureNames(gameMap, script, action.mCreatureNames)" in run, "raidmember accepts names and parties")
check("setRaidLeader(static_cast<uint32_t>(action.mNumber), action.mText)" in run, "raidleader names the leader")
check("Action  raidmember" in SCRIPT_H and "Action  raidleader" in SCRIPT_H, "the script format documents both")


def resolve_template(group_templates, name):
    """Model of the template lookup of Creature::setFixedSkillTemplate: the position of the name in its group."""
    return group_templates.index(name) if name in group_templates else -1


check(resolve_template(["Berserker", "Guardian", "Warlord"], "Guardian") == 1, "FQ8: Guardian is template 1")
check(resolve_template(["Marksman", "Hunter", "Skirmisher"], "Guardian") == -1, "FQ8: a foreign template is refused")

# ------------------------------------------------------------------------------------------------ C3 save and load
export = function(MANAGER, "void CombatGroupManager::exportToStream(")
load = function(MANAGER, "bool CombatGroupManager::importFromStream(")


def written_fields(statement):
    """The member names a writer statement writes, in order (a mapping keeps the name of the member)."""
    fields = []
    for part in statement.split("<<")[1:]:
        match = re.search(r"\b(?:group|it->second)\.m(\w+)", part)
        if match:
            fields.append(match.group(1))
        elif re.search(r"\bit->first\b", part):
            fields.append("Key")
    return fields


def read_fields(statement, names):
    """The member names a reader statement reads, in order; local variables are mapped with names."""
    fields = []
    for part in statement.split(">>")[1:]:
        token = part.strip().split()[0].rstrip(")")
        match = re.match(r"(?:group|entry)\.m(\w+)", token)
        fields.append(match.group(1) if match else names.get(token, token))
    return fields


group_writer = export[export.index('os << "Group\\t"'):]
group_writer = group_writer[:group_writer.index(";")]
group_reader = load[load.index("line >> group.mId"):]
group_reader = group_reader[:group_reader.index("))")]
written = written_fields(group_writer)
read_back = read_fields(group_reader, {"isRaid": "IsRaid", "leader": "Leader", "target": "Target",
                                       "retreating": "Retreating", "nbMembers": "Members"})
check(written == read_back, "C3: the Group line is read in the order it is written " + repr((written, read_back)))
check(written == ["Id", "IsRaid", "SeatId", "RaidGroupId", "Leader", "Target", "FacingX", "FacingY", "LastLeaderX",
                  "LastLeaderY", "Retreating", "RetreatX", "RetreatY", "RetreatSeconds", "RetreatCooldown", "Members"],
      "C3: every state of a group is saved " + repr(written))
for assignment in ("group.mIsRaid = (isRaid != 0);", "group.mRetreating = (retreating != 0);",
                   "group.mLeader = dashToEmpty(leader);", "group.mTarget = dashToEmpty(target);",
                   "group.mMembers.push_back(member);"):
    check(assignment in load, "C3: the reader restores " + assignment)
for writer, reader in (('os << "RaidGroup\\t" << it->first << "\\t" << nameOrDash(it->second)', "line >> raidGroupId >> leader"),
                       ('os << "RaidMember\\t" << it->first << "\\t" << it->second.mRaidGroupId << "\\t" << nameOrDash(it->second.mTemplate)',
                        "line >> name >> raidGroupId >> templateName"),
                       ('os << "NextGroupId\\t" << mNextGroupId', "line >> nextId"),
                       ('os << "Aggro\\t" << it->first << "\\t" << it->second.mTank << "\\t" << it->second.mTurnsLeft',
                        "line >> name >> entry.mTank >> entry.mTurnsLeft")):
    check(writer in export and reader in load, "C3: line written and read alike: " + reader)
check("if(isGameSave)" in export and export.index("RaidMember") < export.index("if(isGameSave)"),
      "C3: the raid registry is level data, the running state is written in saved games")
check("os.precision(17)" in export, "C3: the numbers are saved with all their digits")
# MapHandler: written last, read last and optional, so that older levels and saves load as before
writer = function(MAP_HANDLER, "bool writeGameMapToFile(")
check(writer.index("[/RelationshipState]") < writer.index("getCombatGroups().exportToStream(levelFile, isGameSave)")
      < writer.index("SafeSave::closeWritten(levelFile)"), "C3: the section is written after the relationship state")
reader = function(MAP_HANDLER, "bool readGameMapFromFile(")
optional = reader[reader.index('if(nextParam == "[RelationshipState]")'):]
check(optional.index("if(!(levelFile >> nextParam))") < optional.index('if(nextParam == "[CombatGroups]")'),
      "C3: the reader looks for the optional section after the relationship state")
check("getCombatGroups().importFromStream(levelFile)" in optional, "C3: the section is read by the manager")
check("mCombatGroups->clear();" in function(GAME_MAP, "bool GameMap::loadLevel("), "C3: a new load starts empty")
check("def read_combat_groups(s):" in read("source/tests/check_save_games_load.py"),
      "C3: the saved game model reads the section")


def export_model(state):
    """Model of exportToStream for a saved game."""
    lines = ["[CombatGroups]"]
    for raid_id, leader in sorted(state["leaders"].items()):
        lines.append("RaidGroup\t%d\t%s" % (raid_id, leader or "-"))
    for name, (raid_id, template) in sorted(state["members"].items()):
        lines.append("RaidMember\t%s\t%d\t%s" % (name, raid_id, template or "-"))
    lines.append("NextGroupId\t%d" % state["next"])
    for g in state["groups"]:
        lines.append("\t".join(["Group", str(g["id"]), "1" if g["raid"] else "0", str(g["seat"]), str(g["raidGroup"]),
                                g["leader"] or "-", g["target"] or "-", repr(g["facing"][0]), repr(g["facing"][1]),
                                str(g["last"][0]), str(g["last"][1]), "1" if g["retreating"] else "0",
                                str(g["retreat"][0]), str(g["retreat"][1]), repr(g["seconds"]), repr(g["cooldown"]),
                                str(len(g["members"]))] + g["members"]))
    for name, (tank, turns) in sorted(state["aggro"].items()):
        lines.append("Aggro\t%s\t%s\t%d" % (name, tank, turns))
    lines.append("[/CombatGroups]")
    return "\n".join(lines) + "\n"


def import_model(text):
    """Model of importFromStream."""
    state = {"leaders": {}, "members": {}, "next": 1, "groups": [], "aggro": {}}
    for line in text.splitlines()[1:]:
        f = line.split()
        if f[0] == "[/CombatGroups]":
            return state
        if f[0] == "RaidGroup":
            if f[2] != "-":
                state["leaders"][int(f[1])] = f[2]
        elif f[0] == "RaidMember":
            state["members"][f[1]] = (int(f[2]), "" if f[3] == "-" else f[3])
        elif f[0] == "NextGroupId":
            state["next"] = max(state["next"], int(f[1]))
        elif f[0] == "Group":
            count = int(f[16])
            state["groups"].append({"id": int(f[1]), "raid": f[2] != "0", "seat": int(f[3]), "raidGroup": int(f[4]),
                                    "leader": "" if f[5] == "-" else f[5], "target": "" if f[6] == "-" else f[6],
                                    "facing": (float(f[7]), float(f[8])), "last": (int(f[9]), int(f[10])),
                                    "retreating": f[11] != "0", "retreat": (int(f[12]), int(f[13])),
                                    "seconds": float(f[14]), "cooldown": float(f[15]), "members": f[17:17 + count]})
        elif f[0] == "Aggro":
            state["aggro"][f[1]] = (f[2], int(f[3]))
    raise AssertionError("no end tag")


# A running group fight: the raid group 1 with its leader and a fixed template, the keeper's group retreating
RUNNING = {
    "leaders": {1: "Castellan"},
    "members": {"Castellan": (1, "Guardian"), "Knight7": (1, ""), "Priest2": (1, "Healer")},
    "next": 3,
    "groups": [
        {"id": 1, "raid": True, "seat": 4, "raidGroup": 1, "leader": "Castellan", "target": "Troll3",
         "facing": (-0.7071067811865476, 0.7071067811865476), "last": (40, 12), "retreating": False, "retreat": (0, 0),
         "seconds": 0.0, "cooldown": 12.857142857142858, "members": ["Castellan", "Knight7", "Priest2"]},
        {"id": 2, "raid": False, "seat": 1, "raidGroup": 1, "leader": "Troll3", "target": "", "facing": (1.0, 0.0),
         "last": (30, 20), "retreating": True, "retreat": (22, 20), "seconds": 3.5714285714285716, "cooldown": 0.0,
         "members": ["Orc4", "Troll3", "Wizard9"]},
    ],
    "aggro": {"Orc4": ("Castellan", 6)},
}
check(import_model(export_model(RUNNING)) == RUNNING, "C3: a running group fight is saved and loaded one to one")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"wiring","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("group combat wiring ok")
