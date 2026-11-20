#!/usr/bin/env python3
"""Non-compiling check of the raid behaviour of raid plan R10: the members follow their fleeing leader to the gate and
escape through it (RA8, FQ 10), the followers of a fleeing leader who is killed or captured before the gate stop
fleeing and fight again (RA8b, Q20.33), escaped members count as defeated and their gold and items are lost (RA7, RA9), no
individual flight inside a combat group but outside it (G10), the raid group retreats towards the gate (G7),
unconscious is not fallen and a leader without further members never flees (RA8, Q20.12), the carry amount of a small
member is 1 treasury tile and of a large one 2 tiles (RA7), the raid loots the items fallen keeper creatures drop and a
fallen member drops its own (RA12), the saving and loading of the new state (C3), and the dissolving (G8) and the
holding leader (G9) of the keeper groups.

Every rule is checked twice: a Python model written from the rule computes fixed scenarios whose expected results are
written in this file, and the C++ sources are checked for the statements that implement the same rule. Nothing is
compiled and the game is not started; the integration build compiles and runs the code.

Usage: python -I source/tests/check_raid_behaviour.py
Exit 0 and "raid behaviour ok" when every item holds.
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


def block(text, tag):
    """The key -> words of a [tag] block of a config file."""
    body = re.split(r"(?m)^\[" + tag + r"\]\s*$", text)[1].split("[/" + tag + "]")[0]
    values = {}
    for line in body.splitlines():
        words = line.split("#")[0].split()
        if words:
            values[words[0]] = words[1:]
    return values


MANAGER = read("source/game/RaidManager.cpp")
MANAGER_H = read("source/game/RaidManager.h")
RULES = read("source/game/RaidRules.cpp")
GROUPS = read("source/game/CombatGroupManager.cpp")
CREATURE = read("source/entities/Creature.cpp")
EQUIPMENT = read("source/entities/CreatureEquipmentAI.cpp")
ATTACK = read("source/creaturebehaviour/CreatureBehaviourAttackEnemy.cpp")
FLEE_H = read("source/creatureaction/CreatureActionFlee.h")
FOLLOW = read("source/creatureaction/CreatureActionGroupFollow.cpp")
CONFIG_MANAGER = read("source/utils/ConfigManager.cpp")
GLOBAL_CFG = read("config/global.cfg")
ROOMS_CFG = read("config/rooms.cfg")


# ------------------------------------------------------------------------------------------------ model of the raid
class Member(object):
    """A raid member as the raid sees it."""

    def __init__(self, name, alive=True, on_map=True, in_hand=False, prison=False, converted=False, ko=False):
        self.name = name
        self.alive = alive
        self.on_map = on_map
        self.in_hand = in_hand
        self.prison = prison
        self.converted = converted
        self.ko = ko
        self.at_gate = False
        self.escaped = False


def standing(m):
    """Model of RaidManager::isStanding (an unconscious member stays alive with 1 hit point)."""
    if m.escaped:
        return False  # removed from the map and deleted
    return m.alive and (m.on_map or m.in_hand) and not m.prison and not m.converted


def flees(others, fallen, share):
    """Model of RaidRules::leaderShouldFlee."""
    return others != 0 and min(fallen, others) / float(others) >= share


class Group(object):
    """Model of RaidGroupData with the part of updateLeaders that R10 changed."""

    def __init__(self, leader, members):
        self.leader = leader
        self.members = members
        self.state = "none"
        self.followers = []
        self.escaped_members = []
        self.lost = False

    def escaping(self, name):
        """Model of RaidManager::isEscaping."""
        if self.state == "fleeing" and name == self.leader.name:
            return True
        return name in self.followers and name not in self.escaped_members

    def update(self, share):
        """Model of RaidManager::updateLeaders for one group."""
        by_name = {m.name: m for m in self.members}
        for name in list(self.followers):
            m = by_name[name]
            if self.escaping(name) and standing(m) and m.at_gate:
                m.escaped = True
                self.escaped_members.append(name)
        if self.state == "escaped":
            return
        if not standing(self.leader):
            # RA8b [Q20.33]: a leader killed or captured during his flight releases the followers that did not escape
            if self.state == "fleeing":
                self.followers = [name for name in self.followers if name in self.escaped_members]
                self.state = "none"
            return
        if self.state == "fleeing":
            if self.leader.at_gate:
                self.state = "escaped"
                self.leader.escaped = True
                self.lost = True
            return
        others = [m for m in self.members if m is not self.leader]
        fallen = len([m for m in others if not standing(m)])
        if not flees(len(others), fallen, share):
            return
        self.state = "fleeing"
        self.followers = [m.name for m in others if standing(m)]

    def defeated(self):
        """Model of RaidRules::isRaidDefeated for an arrived group."""
        return len([m for m in self.members if standing(m)]) == 0 and self.state != "escaped"


def make_group():
    """A leader with four members (escape share 0.25 in these scenarios)."""
    leader = Member("Leader")
    return Group(leader, [leader, Member("A"), Member("B"), Member("C"), Member("D")])


# RA8 / FQ 10: one of four fallen reaches 0.25: the leader flees and the three standing members follow him
g = make_group()
g.members[1].alive = False
g.update(0.25)
check(g.state == "fleeing" and g.followers == ["B", "C", "D"], "RA8: the standing members follow the fleeing leader")
check(not g.escaping("A") and g.escaping("B") and g.escaping("Leader"), "RA8: the dead member does not flee")
# A follower reaches the gate first: it escapes, counts as defeated, the level is not lost
g.members[2].at_gate = True
g.update(0.25)
check(g.escaped_members == ["B"] and not standing(g.members[2]) and not g.lost,
      "RA8/FQ 6: a follower escapes through the gate and the level is not lost by it")
# The keeper kills the leader and the last two followers: the raid is defeated although B escaped
g.leader.alive = False
g.members[3].alive = False
g.members[4].alive = False
g.update(0.25)
check(g.defeated(), "RA9/FQ 6: an escaped member counts as defeated")
# Another run: the leader reaches the gate: the level is lost
g = make_group()
g.members[1].prison = True
g.update(0.25)
g.leader.at_gate = True
g.update(0.25)
check(g.state == "escaped" and g.lost and not g.defeated(), "RA8: the leader's escape loses the level")
# A follower still escapes after its leader escaped
g.members[2].at_gate = True
g.update(0.25)
check(g.escaped_members == ["B"], "RA8: a follower escapes also after its leader")

# RA8b [Q20.33]: the keeper kills the fleeing leader before the gate: his followers stop fleeing and fight again; a
# follower that escaped before stays escaped
for fall in ("dead", "prison", "converted"):
    g = make_group()
    g.members[1].alive = False
    g.update(0.25)
    g.members[2].at_gate = True
    g.update(0.25)
    if fall == "dead":
        g.leader.alive = False
    elif fall == "prison":
        g.leader.prison = True
    else:
        g.leader.converted = True
    g.update(0.25)
    check(g.state == "none" and g.followers == ["B"] and g.escaped_members == ["B"],
          "RA8b: the flight ends when the fleeing leader falls (%s), the escaped follower stays escaped" % fall)
    check(not g.escaping("C") and not g.escaping("D") and standing(g.members[3]) and standing(g.members[4]),
          "RA8b: the followers of a fallen leader (%s) stop fleeing and stand" % fall)
    g.members[3].at_gate = True
    g.update(0.25)
    check(g.escaped_members == ["B"] and standing(g.members[3]) and not g.lost,
          "RA8b: a released follower at the gate does not escape any more (%s)" % fall)
# An unconscious fleeing leader has not fallen: his followers keep fleeing
g = make_group()
g.members[1].alive = False
g.update(0.25)
g.leader.ko = True
g.update(0.25)
check(g.state == "fleeing" and g.escaping("C"), "RA8b: an unconscious leader keeps his followers fleeing")

# Q20.12: unconscious and in a keeper's hand are not fallen; dead, imprisoned, converted are
g = make_group()
g.members[1].ko = True
g.members[2].in_hand = True
g.members[2].on_map = False
g.update(0.25)
check(g.state == "none", "Q20.12: unconscious members and a member in the hand have not fallen")
check(not standing(Member("x", alive=False)) and not standing(Member("x", prison=True)) and
      not standing(Member("x", converted=True)), "Q20.12: dead, imprisoned and converted have fallen")
# A leader without further members never flees
alone = Member("Alone")
g = Group(alone, [alone])
g.update(0.0)
check(g.state == "none", "RA8: a leader without further members never flees")

# ------------------------------------------------------------------------------------------------ RA8 statements
leaders = function(MANAGER, "void RaidManager::updateLeaders()")
check(leaders.index("const std::vector<std::string> followers = group.mFollowers;") <
      leaders.index("if(!group.mArrived || group.mLeaderSpawned.empty())"),
      "RA8: the followers are handled also when the leader is gone")
check("if(isAtGate(*member))" in leaders and "escapeMember(group, *member);" in leaders,
      "RA8: a follower at the gate escapes")
check("if((member == group.mLeaderSpawned) || !isStanding(member))" in leaders and
      "group.mFollowers.push_back(member);" in leaders, "RA8: the standing members become followers")
check("setRaidMemberDetached(name, true);" in leaders and
      "creature->setMoveSpeedModifier(LevelScriptRunner::getRunSpeedFactor());" in leaders,
      "RA8: the followers leave the raid group and run at the leader's speed")
escape_member = function(MANAGER, "void RaidManager::escapeMember(RaidGroupData& group, Creature& member)")
check("group.mEscapedMembers.push_back(name);" in escape_member and "member.removeFromGameMap();" in escape_member and
      "member.deleteYourself();" in escape_member, "RA7/RA9: an escaped member leaves the map with what it carries")
check("notifyNoMoreDungeonTemple" not in escape_member and "mLost" not in escape_member,
      "FQ 6: a follower's escape does not lose the level")
check("dropItems" not in escape_member and "TreasuryObject" not in escape_member,
      "RA7: the gold and items of an escaped member are lost for the keeper")
# RA8b [Q20.33]: a leader who fell during his flight ends it; his followers rejoin the raid group and fight again
check("if(!isStanding(group.mLeaderSpawned))\n        {\n" in leaders and
      "if(group.mLeaderState == RaidLeaderState::fleeing)\n                endFlight(group);" in leaders,
      "RA8b: updateLeaders ends the flight of a fleeing leader who fell")
end_flight = function(MANAGER, "void RaidManager::endFlight(RaidGroupData& group)")
check("setRaidMemberDetached(follower, false);" in end_flight and "creature->clearMoveSpeedModifier();" in end_flight
      and "creature->clearActionQueue();" in end_flight,
      "RA8b: a released follower rejoins its raid group at its normal speed and takes up the fight again")
check("escapedFollowers.push_back(follower);" in end_flight and "group.mFollowers = escapedFollowers;" in end_flight,
      "RA8b: only the escaped followers stay in the follower list")
check("group.mLeaderState = RaidLeaderState::none;" in end_flight,
      "RA8b: the fallen leader no longer counts as fleeing")
check("void endFlight(RaidGroupData& group);" in MANAGER_H, "RA8b: endFlight is declared")
escaping = function(MANAGER, "bool RaidManager::isEscaping(const std::string& creatureName) const")
check("group.mFollowers" in escaping and "group.mEscapedMembers" in escaping, "RA8: a follower runs to the gate")
standing_cpp = function(MANAGER, "bool RaidManager::isStanding(const std::string& creatureName) const")
check("(creature->getIsOnMap() || creature->isInHand())" in standing_cpp and "!creature->isInPrison()" in standing_cpp
      and "!CombatGroupManager::isKeeperSeat(creature->getSeat())" in standing_cpp,
      "Q20.12: fallen = dead, imprisoned or converted")
check("mHp = 1.0;" in CREATURE[CREATURE.index("else if(ko && !getDefinition()->isWorker()"):][:200],
      "Q20.12: an unconscious creature keeps 1 hit point and stays alive")
check("if(others == 0)\n        return false;" in function(RULES, "bool leaderShouldFlee("),
      "RA8: a leader without further members never flees")

# ------------------------------------------------------------------------------------------------ G10


def runs_flee_rules(in_group, fear_flight=False):
    """Model of Creature::decidePrioritaryAction and handleCombatGroup: (individual flight rules run, flight kept)."""
    may_flee = not in_group
    kept = (not in_group) or fear_flight
    return may_flee, kept


check(runs_flee_rules(True) == (False, False), "G10: a group member does not flee on its own")
check(runs_flee_rules(False) == (True, True), "G10: outside a group the flight rules stay")
check(runs_flee_rules(True, True)[1], "G10: a flight from fear goes on in a group")
may = function(CREATURE, "bool Creature::mayFleeOnItsOwn() const")
check("return !getGameMap()->getCombatGroups().isGroupMember(getName());" in may and
      "if(!getIsOnServerMap())\n        return true;" in may, "G10: only a group member may not flee on its own")
decide = function(CREATURE, "void Creature::decidePrioritaryAction()")
check("const bool mayFlee = mayFleeOnItsOwn();" in decide and
      "if(!mayFlee && (behaviour->getName() == CreatureBehaviourFleeWhenWeak::mNameCreatureBehaviourFleeWhenWeak ||"
      in decide and "CreatureBehaviourFleeWhenOutmatched::mNameCreatureBehaviourFleeWhenOutmatched))\n            continue;"
      in decide, "G10: the individual flight rules are skipped inside a group")
check("if(creature.mayFleeOnItsOwn() &&" in function(ATTACK, "bool CreatureBehaviourAttackEnemy::processBehaviour("),
      "G10: no flight out of anger inside a group")
handle_group = function(CREATURE, "void Creature::handleCombatGroup()")
check(handle_group.index("isGroupMember(getName())") < handle_group.index("bool ownFlight = false;") <
      handle_group.index("groups.isRetreating(*this)"), "G10: a flight of its own ends before the group rules")
check("!static_cast<const CreatureActionFlee*>(action.get())->isFearFlight()" in handle_group,
      "G10: a flight from fear is kept")
check("{ return mFearTile != nullptr; }" in FLEE_H, "G10: a fear flight is one with a fear tile")

# ------------------------------------------------------------------------------------------------ G7 raid retreat
update_group = function(GROUPS, "void CombatGroupManager::updateGroup(")
check("(group.mIsRaid && mGameMap.getRaid().hasRaid()) ?" in update_group and
      "findRaidRetreatTile(*leader, retreatX, retreatY)" in update_group,
      "G7/Q20.3: a raid group retreats towards the gate, a keeper group as before")
raid_retreat = function(GROUPS, "bool CombatGroupManager::findRaidRetreatTile(")
check("mGameMap.getRaid().getGateTile()" in raid_retreat and "pathExists(&leader, leaderTile, gathering)" in raid_retreat,
      "G7: the gathering tile is the gate, reachable by the leader")
check("return mGameMap.getTile(mGateX, mGateY);" in function(MANAGER, "Tile* RaidManager::getGateTile() const"),
      "G7: the gate tile")

# ------------------------------------------------------------------------------------------------ RA7 carry amount
raid_cfg = block(GLOBAL_CFG, "Raid")
gold_per_tile = float(block(ROOMS_CFG, "Rooms")["TreasuryGoldPerTile"][0]) if "[Rooms]" in ROOMS_CFG else None
if gold_per_tile is None:
    gold_per_tile = float(re.search(r"^\s+TreasuryGoldPerTile\s+(\d+)", ROOMS_CFG, re.M).group(1))
check(gold_per_tile == 1000.0, "RA7: one treasury tile stores 1000 gold")
check(raid_cfg.get("RaidCarryTilesSmall") == ["1"] and raid_cfg.get("RaidCarryTilesLarge") == ["2"],
      "RA7/Q20.28: small 1 tile, large 2 tiles")
check(raid_cfg.get("RaidLargeMemberClasses") == ["NatureMonster", "Defender", "Scarab"],
      "Q20.28b: the large classes are NatureMonster, Defender and Scarab")
check("RaidPlunderGoldPerMember" not in GLOBAL_CFG and "RaidPlunderGoldPerMember" not in MANAGER,
      "RA7: the carry amount replaces RaidPlunderGoldPerMember")


def capacity(class_name):
    """Model of RaidManager::carryCapacity with the config of this branch."""
    large = class_name in raid_cfg["RaidLargeMemberClasses"]
    tiles = float(raid_cfg["RaidCarryTilesLarge"][0] if large else raid_cfg["RaidCarryTilesSmall"][0])
    return max(0.0, tiles * gold_per_tile)


def plunder(stored, carried, cap):
    """Model of RaidRules::plunderAmount."""
    return max(0.0, min(stored, cap - carried))


EXPECTED_CAPACITY = {"Knight": 1000.0, "Wizard": 1000.0, "Elf": 1000.0, "Monk": 1000.0, "NatureMonster": 2000.0,
                     "Defender": 2000.0, "Scarab": 2000.0}
for name, expected in sorted(EXPECTED_CAPACITY.items()):
    check(capacity(name) == expected, "RA7: " + name + " carries " + str(expected))
# A small member at a full 3x3 treasury takes 1000, a large one 2000; a second treasury adds nothing when full
check(plunder(9000.0, 0.0, capacity("Knight")) == 1000.0 and plunder(9000.0, 0.0, capacity("Scarab")) == 2000.0,
      "RA7: the first treasury")
check(plunder(9000.0, 1000.0, capacity("Knight")) == 0.0 and plunder(9000.0, 1000.0, capacity("Scarab")) == 1000.0,
      "RA7: a member takes only what it can still carry")
check("std::find(largeClasses.begin(), largeClasses.end(), className) != largeClasses.end()" in
      function(RULES, "bool isLargeMember(") and "const double tiles = large ? largeTiles : smallTiles;" in
      function(RULES, "double carryCapacity(") and "return std::max(0.0, tiles * goldPerTile);" in
      function(RULES, "double carryCapacity("), "RA7: the rules of the carry amount")
cap_cpp = function(MANAGER, "double RaidManager::carryCapacity(const Creature& creature)")
check('getRaidConfigWords("RaidLargeMemberClasses")' in cap_cpp and 'getRoomConfigDouble("TreasuryGoldPerTile")' in cap_cpp
      and 'raidConfig("RaidCarryTilesSmall")' in cap_cpp and 'raidConfig("RaidCarryTilesLarge")' in cap_cpp,
      "RA7: the carry amount reads the config")
loader = function(CONFIG_MANAGER, "bool ConfigManager::loadGlobalRaidConfig(")
check("std::getline(configFile, value);" in loader and "mRaidConfigWords[nextParam] = value;" in loader,
      "RA7: the [Raid] block keeps word lists")
docs = re.split(r"(?m)^\[Raid\]\s*$", GLOBAL_CFG)[0].split("[/GroupCombat]")[1]
for key in ("RaidCarryTilesSmall", "RaidCarryTilesLarge", "RaidLargeMemberClasses"):
    lines = [line for line in docs.splitlines() if re.match(r"#\s+" + key + r"\s", line)]
    check(len(lines) == 1 and "PLACEHOLDER" not in lines[0], "V1: " + key + " is documented as a rule value")

# ------------------------------------------------------------------------------------------------ RA12 looting


def lootable(bag_from_fallen_keeper, merchant_goods, ghost, allied, free_slot, fighting, escaping):
    """Model of the conditions of RaidManager::doLoot."""
    return (bag_from_fallen_keeper and not merchant_goods and not ghost and not allied and free_slot and
            not fighting and not escaping)


check(lootable(True, False, False, False, True, False, False), "RA12: a member loots an item of a fallen keeper creature")
check(not lootable(False, False, False, False, True, False, False), "RA12: only items fallen keeper creatures dropped")
check(not lootable(True, False, False, False, False, False, False), "RA12: only into a free inventory slot")
check(not lootable(True, False, False, False, True, True, False), "RA12: not during a fight")
check(not lootable(True, False, False, False, True, False, True), "RA12: not while it flees to the gate")
death = function(EQUIPMENT, "void Creature::dropItems(bool dead)")
dead_part = death[death.index("else"):]
check(dead_part.count("dropDeathItem(*this,") == 3 and "dropDeathItem" not in death[:death.index("else")],
      "RA12: only what a creature drops at its death is registered as loot")
check("getRaid().registerFallenDrop(creature, *bag);" in function(EQUIPMENT, "void dropDeathItem("),
      "RA12: the death drop is told to the raid")
register = function(MANAGER, "void RaidManager::registerFallenDrop(")
check("!CombatGroupManager::isKeeperSeat(fallen.getSeat())" in register and "mLoot.insert(bag.getName());" in register,
      "RA12: only the drops of keeper creatures")
loot = function(MANAGER, "bool RaidManager::doLoot(Creature& creature)")
check("isEscaping(name)" in loot and "CreatureActionType::fight" in loot and "freeSlot" in loot and
      "mLoot.count(entity->getName()) == 0" in loot and "creature.getSeat()->isAlliedSeat(bag->getSeat())" in loot,
      "RA12: the conditions of the looting")
check("creature.acceptItem(std::move(item));" in loot and "bagHere->deleteYourself();" in loot and
      "mLoot.erase(bagName);" in loot, "RA12: the item goes into the member's inventory like a creature's")
check("LevelScriptRunner::walkToNearestTile(creature, lootTiles)" in loot, "RA12: the member walks to the item")
check("goldCarried" not in loot.replace("getGoldCarried", "") and "plunderAmount" not in loot,
      "RA12: looted items do not count against the gold")
check("getRaid().doLoot(creature)" in function(FOLLOW, "bool CreatureActionGroupFollow::handleGroupFollow("),
      "RA12: the members in the formation loot")
order = function(MANAGER, "bool RaidManager::doCreatureOrder(Creature& creature)")
check(order.index("if(doLoot(creature))") < order.index("LevelScriptRunner::walkToDungeonHeart"),
      "RA12: the leader loots on his way")
check("if(!isAlive())\n        dropItems(true);" in CREATURE, "RA12/Q20.28c: a fallen member drops its items as today")

# ------------------------------------------------------------------------------------------------ C3 saving


def export_state(groups, loot):
    """Model of the R10 lines of RaidManager::exportToStream in a saved game."""
    lines = []
    for gid, followers, escaped in groups:
        lines += ["Follower\t%d\t%s" % (gid, name) for name in followers]
        lines += ["Escaped\t%d\t%s" % (gid, name) for name in escaped]
    lines += ["Loot\t" + name for name in sorted(loot)]
    return lines


def import_state(lines, group_ids):
    """Model of the R10 lines of RaidManager::importFromStream; None when a line is refused."""
    followers = {gid: [] for gid in group_ids}
    escaped = {gid: [] for gid in group_ids}
    loot = set()
    for line in lines:
        f = line.split("\t")
        if f[0] in ("Follower", "Escaped"):
            if len(f) < 3 or int(f[1]) not in followers:
                return None
            (followers if f[0] == "Follower" else escaped)[int(f[1])].append(f[2])
        elif f[0] == "Loot":
            loot.add(f[1])
    detached = sorted(n for gid in group_ids for n in followers[gid] if n not in escaped[gid])
    return followers, escaped, loot, detached


STATE = [(1, ["Elf_3", "Wizard_4", "Knight_5"], ["Elf_3"]), (2, [], [])]
LOOT = {"ItemBag_17", "ItemBag_18"}
loaded = import_state(export_state(STATE, LOOT), [1, 2])
check(loaded is not None and loaded[0] == {1: ["Elf_3", "Wizard_4", "Knight_5"], 2: []} and
      loaded[1] == {1: ["Elf_3"], 2: []} and loaded[2] == LOOT, "C3: followers, escaped members and loot round trip")
check(loaded is not None and loaded[3] == ["Knight_5", "Wizard_4"],
      "C3: the followers that did not escape leave their raid group again")
check(import_state([], [1]) == ({1: []}, {1: []}, set(), []), "C3: an old saved game without the lines loads as before")
check(import_state(["Follower\t9\tX"], [1]) is None, "C3: a follower of an unknown raid group is refused")
export = function(MANAGER, "void RaidManager::exportToStream(")
load = function(MANAGER, "bool RaidManager::importFromStream(std::istream& is)")
check(export.index("if(isGameSave)") < export.index('os << "Follower\\t" << group.mRaidGroupId << "\\t" << follower')
      and 'os << "Escaped\\t" << group.mRaidGroupId << "\\t" << escaped' in export and
      'os << "Loot\\t" << bag' in export, "C3: the new state is written in saved games")
check('if((token == "Follower") || (token == "Escaped"))' in load and "line >> raidGroupId >> name" in load and
      'if(token == "Loot")' in load and "mLoot.insert(bag);" in load, "C3: the new state is read")
check("setRaidMemberDetached(follower, true);" in load, "C3: the followers leave their group again on a load")
check("Follower RaidGroupId CreatureName" in function(MANAGER, "std::string RaidManager::getStreamFormat()"),
      "C3: the format comment names the new lines")
check("mLoot.clear();" in function(MANAGER, "void RaidManager::clear()"), "C3: a new level forgets the loot")

# ------------------------------------------------------------------------------------------------ G8 / G9


def dissolves(members, raiders, distance):
    """Model of CombatGroupManager::removeEndedGroups for a keeper group: tiles (x, y), squared distance."""
    if not members:
        return True
    if raiders is None:
        return True
    return not any((mx - rx) ** 2 + (my - ry) ** 2 <= distance * distance for mx, my in members for rx, ry in raiders)


DISSOLVE = float(block(GLOBAL_CFG, "GroupCombat")["GroupDissolveDistance"][0])
check(DISSOLVE == 24.0, "G8: the dissolving distance of this branch is 24")
check(dissolves([(0, 0)], None, DISSOLVE), "G8: the group dissolves when its raid group is gone")
check(dissolves([(0, 0)], [(25, 0)], DISSOLVE), "G8: ... or no raid member is within the distance")
check(not dissolves([(0, 0)], [(24, 0)], DISSOLVE), "G8: a raid member at the distance keeps the group")
ended = function(GROUPS, "void CombatGroupManager::removeEndedGroups(")
check('groupConfig("GroupDissolveDistance")' in ended and "raidIt != raid.end()" in ended and
      "ended = !raidNear;" in ended and "it = mGroups.erase(it);" in ended, "G8: the dissolving in the source")
check("return !(group->mIsRaid && (group->mLeader == creature.getName()));" in
      function(GROUPS, "bool CombatGroupManager::shouldKeepFormation("),
      "G9: the keeper group leader keeps the formation action")
check("if(place == nullptr)\n        return false; // the leader of a keeper's group holds his position" in FOLLOW,
      "G9: a keeper group leader without a place holds his position")
check("if(member == leader)\n                continue;" in update_group and
      "CombatGroupRules::placePosition(static_cast<double>(leaderTile->getX())" in update_group,
      "G9: the members gather behind their leader")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"behaviour","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("raid behaviour ok")
