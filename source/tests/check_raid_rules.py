#!/usr/bin/env python3
"""Non-compiling check of the rules of the raid (raid plan R2: RA2 countdown, RA3 early opening, RA4 raid groups with
interval, RA5 leader in his group, RA7 plundering with the carry amount of R10, RA8 leader escape, RA9 victory, RA1 gate
unclaimable and indestructible).

Every rule is checked twice: a Python model written from the rule computes fixed scenarios whose expected results are
written in this file, and the C++ source of source/game/RaidRules.cpp and of the engine side (RaidManager, the hero
portal room that shows the gate, the creature) is checked for the statements that implement the same rule. Nothing is
compiled and the game is not started; the integration build compiles and runs the code.

The members that follow their fleeing leader through the gate, the looting and the other rules of raid plan R10 are
checked in check_raid_behaviour.py.

Usage: python -I source/tests/check_raid_rules.py
Exit 0 and "raid rules ok" when every item holds.
"""
import math
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


RULES = read("source/game/RaidRules.cpp")
RULES_H = read("source/game/RaidRules.h")
MANAGER = read("source/game/RaidManager.cpp")
PORTAL = read("source/rooms/RoomPortalWave.cpp")
PORTAL_H = read("source/rooms/RoomPortalWave.h")
CREATURE = read("source/entities/Creature.cpp")
GROUPS = read("source/game/CombatGroupManager.cpp")
RUNNER = read("source/gamemap/LevelScriptRunner.cpp")


# ------------------------------------------------------------------------------------------------ model of RaidRules
class Schedule(object):
    """Model of RaidRules::Schedule."""

    def __init__(self):
        self.next_group = 0
        self.group_count = 0
        self.seconds = -1.0
        self.gate_open = False


def start(s, groups, countdown):
    """Model of RaidRules::start."""
    s.next_group = 0
    s.group_count = groups
    s.gate_open = False
    s.seconds = -1.0 if groups == 0 else max(0.0, countdown)


def advance(s, seconds, interval):
    """Model of RaidRules::advance: True when a group comes now."""
    if s.next_group >= s.group_count or s.seconds < 0.0:
        return False
    s.seconds -= seconds
    if s.seconds > 0.0:
        return False
    s.gate_open = True
    s.next_group += 1
    s.seconds = max(0.0, interval) if s.next_group < s.group_count else -1.0
    return True


def open_early(s):
    """Model of RaidRules::openEarly."""
    if s.gate_open or s.next_group != 0 or s.group_count == 0:
        return False
    s.seconds = 0.0
    return True


def set_seconds(s, seconds):
    """Model of RaidRules::setSecondsToNext."""
    if s.next_group < s.group_count:
        s.seconds = max(0.0, seconds)


def display(s):
    """Model of RaidRules::displaySeconds."""
    if s.next_group >= s.group_count or s.seconds < 0.0:
        return -1
    return int(math.ceil(s.seconds))


def fallen_share(others, fallen):
    """Model of RaidRules::fallenShare."""
    return 0.0 if others == 0 else min(fallen, others) / float(others)


def leader_flees(others, fallen, share):
    """Model of RaidRules::leaderShouldFlee."""
    return others != 0 and fallen_share(others, fallen) >= share


def raid_defeated(all_arrived, spawned, standing, escaped):
    """Model of RaidRules::isRaidDefeated."""
    return all_arrived and spawned > 0 and standing == 0 and not escaped


def plunder_amount(stored, carried, capacity):
    """Model of RaidRules::plunderAmount."""
    return max(0.0, min(stored, capacity - carried))


def run(groups, countdown, interval, seconds, events):
    """Runs the schedule in steps of one second for the given seconds, in the order of a game turn: the raid update
    first, then the level script or the button of the player; events maps a second to such an action ("open" for the
    early opening, a number for raidcountdown). Returns the seconds at which groups came and the countdown shown at
    every second."""
    s = Schedule()
    start(s, groups, countdown)
    arrivals = []
    shown = []
    for second in range(1, seconds + 1):
        if advance(s, 1.0, interval):
            arrivals.append(second)
        action = events.get(second)
        if action == "open":
            if open_early(s) and advance(s, 0.0, interval):
                arrivals.append(second)
        elif action is not None:
            set_seconds(s, action)
        shown.append(display(s))
    return arrivals, shown, s


# RA2 / RA4: two groups, countdown 240 s from the level start, interval 90 s; the countdown then shows the next group
arrivals, shown, schedule = run(2, 240.0, 90.0, 400, {})
check(arrivals == [240, 330], "RA2/RA4: the groups come at 240 s and 330 s, not " + str(arrivals))
check(shown[0] == 239 and shown[238] == 1, "RA2: the countdown runs down from the level start")
check(shown[239] == 90 and shown[328] == 1, "RA4: after the first group the countdown shows the next group")
check(shown[329] == -1 and schedule.gate_open, "RA4: after the last group no countdown is shown")

# RA3: the player opens the gate at 10 s: the first group comes at once, the second after the interval
arrivals, shown, schedule = run(2, 240.0, 90.0, 200, {10: "open"})
check(arrivals == [10, 100], "RA3: early opening brings the first group at once, not " + str(arrivals))
s = Schedule()
start(s, 2, 240.0)
check(open_early(s) and advance(s, 0.0, 90.0) and not open_early(s), "RA3: the gate opens early only once")
s = Schedule()
start(s, 0, 240.0)
check(not open_early(s) and display(s) == -1, "RA3: without raid groups there is nothing to open")

# Script action raidcountdown 150 at 5 s
arrivals, shown, schedule = run(1, 240.0, 90.0, 200, {5: 150})
check(arrivals == [155], "raidcountdown: the group comes 150 s after the action, not " + str(arrivals))

# Fractional turns: the countdown is shown rounded up
s = Schedule()
start(s, 1, 2.0)
advance(s, 0.5, 90.0)
check(display(s) == 2, "RA2: 1.5 s left are shown as 2 s")

# RA8: the leader flees once the fallen share of the others reached the share (0.75 in this scenario)
check(fallen_share(4, 3) == 0.75 and leader_flees(4, 3, 0.75), "RA8: 3 of 4 fallen reach the share 0.75")
check(not leader_flees(4, 2, 0.75), "RA8: 2 of 4 fallen do not reach the share 0.75")
check(not leader_flees(0, 0, 0.0), "RA8: a leader without other members never flees")

# RA9: the whole raid is defeated only when every group came, nobody stands and no leader escaped
check(raid_defeated(True, 8, 0, False), "RA9: every member fallen and every group come is a victory")
check(not raid_defeated(True, 8, 1, False), "RA9: a leader still standing blocks the victory")
check(not raid_defeated(False, 4, 0, False), "RA9: a group that did not come yet blocks the victory")
check(not raid_defeated(True, 8, 0, True), "RA9: an escaped leader is no victory")
check(not raid_defeated(True, 0, 0, False), "RA9: a raid that never came is no victory")

# RA7: one member takes what it can still carry, at most what the room holds (capacity 1000 in these scenarios)
check(plunder_amount(150.0, 0.0, 1000.0) == 150.0 and plunder_amount(5000.0, 0.0, 1000.0) == 1000.0 and
      plunder_amount(0.0, 0.0, 1000.0) == 0.0, "RA7: the plundered amount")
check(plunder_amount(5000.0, 600.0, 1000.0) == 400.0 and plunder_amount(5000.0, 1000.0, 1000.0) == 0.0,
      "RA7: a member that carries gold takes only the rest of what it can carry")

# ------------------------------------------------------------------------------------------------ C++ statements
advance_cpp = function(RULES, "bool advance(Schedule& schedule, double seconds, double intervalSeconds)")
check("schedule.mSecondsToNext -= seconds;" in advance_cpp and "if(schedule.mSecondsToNext > 0.0)" in advance_cpp,
      "RA2: advance counts the countdown down")
check("schedule.mGateOpen = true;" in advance_cpp and "++schedule.mNextGroup;" in advance_cpp and
      "schedule.mSecondsToNext = std::max(0.0, intervalSeconds);" in advance_cpp and
      "schedule.mSecondsToNext = -1.0;" in advance_cpp, "RA4: advance opens the gate and starts the interval")
early_cpp = function(RULES, "bool openEarly(Schedule& schedule)")
check("if(schedule.mGateOpen || (schedule.mNextGroup != 0) || (schedule.mGroupCount == 0))" in early_cpp and
      "schedule.mSecondsToNext = 0.0;" in early_cpp, "RA3: openEarly ends the countdown of the first group")
check("std::ceil(schedule.mSecondsToNext)" in function(RULES, "int32_t displaySeconds(const Schedule& schedule)"),
      "RA2: the countdown is rounded up")
check("return fallenShare(others, fallen) >= escapeShare;" in function(RULES, "bool leaderShouldFlee("),
      "RA8: the escape share")
check("return allGroupsArrived && (spawned > 0) && (standing == 0) && !leaderEscaped;" in
      function(RULES, "bool isRaidDefeated("), "RA9: the defeat of the whole raid")
check("return std::max(0.0, std::min(stored, capacity - carried));" in function(RULES, "double plunderAmount("),
      "RA7: the plundered amount")
check("#include <" in RULES_H and "Ogre" not in RULES_H and "GameMap" not in RULES_H,
      "the rules depend only on the standard library")

# RA2 / RA3 engine: the countdown runs every turn, the early opening brings the group at once
update = function(MANAGER, "void RaidManager::update()")
check("RaidRules::start(mSchedule, static_cast<uint32_t>(mGroups.size()), countdownSeconds());" in update and
      "advanceSchedule(1.0 / ODApplication::turnsPerSecond);" in update, "RA2: the countdown starts with the level")
advance_engine = function(MANAGER, "void RaidManager::advanceSchedule(double seconds)")
check("spawnGroup(mSchedule.mNextGroup - 1);" in advance_engine and "setMoreyaGateOpen(true," in advance_engine,
      "RA4: an arrival lets the group come and sinks the portcullis")
early = function(MANAGER, "bool RaidManager::openGateEarly(int32_t seatId)")
check("(seatId != mTargetSeatId)" in early and "RaidRules::openEarly(mSchedule)" in early and
      "advanceSchedule(0.0);" in early, "RA3: only the attacked keeper opens early, the raid comes at once")

# RA5: the named leader is registered as the leader of his raid group, the members with their fixed templates
spawn = function(MANAGER, "void RaidManager::spawnGroup(uint32_t index)")
check("combatGroups.registerRaidMember(name, group.mRaidGroupId, spec.mTemplate);" in spawn,
      "RA5: every member joins its raid group with its fixed template")
check("(spec.mName == group.mLeaderName)" in spawn and "combatGroups.setRaidLeader(group.mRaidGroupId, name);" in spawn,
      "RA5: the named leader leads his own raid group")
check('mGameMap.getLevelScript().addPartyMember(party, name);' in spawn and '"Raid" + Helper::toString(' in spawn,
      "the members belong to the party Raid<id>")

# RA6: the leader leads the group to the heart as the killplayer order does and turns aside to the treasuries
order = function(MANAGER, "bool RaidManager::doCreatureOrder(Creature& creature)")
check("shouldKeepFormation(creature)" in order and "LevelScriptRunner::walkToDungeonHeart(creature, mTargetSeatId)"
      in order and 'raidConfig("RaidPlunderDetourTiles")' in order, "RA6: the leader leads, plunders, attacks the heart")
heart = function(RUNNER, "bool LevelScriptRunner::walkToDungeonHeart(Creature& creature, int32_t seatId)")
check("isNear(myTile, tile, NEAR_HEART_DISTANCE)" in heart and "RoomType::dungeonTemple" in heart,
      "RA6: the heart attack is the rule of the killplayer order")

# RA7: the gold leaves the keeper at once and the member carries it; a killed member drops it as every creature does
plunder = function(MANAGER, "void RaidManager::plunder()")
check("RaidRules::plunderAmount(room->getTotalGoldStored(), creature->getGoldCarried()," in plunder and
      "carryCapacity(*creature));" in plunder and "room->withdrawGold(amount);" in plunder and
      "creature->addGoldStolen(taken);" in plunder, "RA7: the plundered gold leaves the treasury of the keeper")
check(plunder.index("mPlundered.insert(std::make_pair(name, room->getName()));") < plunder.index("if(amount <= 0.0)"),
      "RA7: a room the member entered is remembered, also when it can carry nothing more")
rooms = function(MANAGER, "std::vector<Room*> RaidManager::plunderableRooms() const")
check("RoomType::treasury, RoomType::dungeonTemple" in rooms and "owner->isAlliedSeat(raidSeat)" in rooms,
      "RA7: the treasuries and heart treasuries of the enemy keepers")
die = CREATURE[CREATURE.index("// We drop what we are carrying"):]
check(re.search(r"if\(mGoldCarried > 0\)\s*\{\s*TreasuryObject\* obj = new TreasuryObject\(getGameMap\(\), mGoldCarried\);",
                die) is not None, "RA7/FQ5: a killed member drops the gold it carries, as before")

# RA8: flight and escape of a leader
leaders = function(MANAGER, "void RaidManager::updateLeaders()")
check("RaidRules::leaderShouldFlee(others, fallen, share)" in leaders and
      "group.mLeaderState = RaidLeaderState::fleeing;" in leaders and
      "setRaidMemberDetached(name, true);" in leaders and
      "setMoveSpeedModifier(LevelScriptRunner::getRunSpeedFactor());" in leaders,
      "RA8: the leader leaves his group and runs to the gate")
check("if(isAtGate(*leader))" in leaders and "escape(group, *leader);" in leaders, "RA8: at the gate he escapes")
escape = function(MANAGER, "void RaidManager::escape(RaidGroupData& group, Creature& leader)")
check("group.mLeaderState = RaidLeaderState::escaped;" in escape and "leader.removeFromGameMap();" in escape and
      "player->notifyNoMoreDungeonTemple();" in escape, "RA8: an escape loses the level")
check("!isRaidMemberDetached(it->first)" in function(GROUPS, "void CombatGroupManager::update()"),
      "RA8: the fleeing leader is no longer in his raid group")
check("getRaid().isEscaping(getName())" in function(CREATURE, "void Creature::decidePrioritaryAction()") and
      "getRaid().isEscaping(getName())" in function(CREATURE, "void Creature::handleRaidEscape()"),
      "RA8: the fleeing leader neither fights nor flees elsewhere")
check(CREATURE.index("getGameMap()->getRaid().doCreatureOrder(*this)") <
      CREATURE.index("LevelScriptRunner::doCreatureOrder(*this)"), "RA8: the raid order comes first")

# RA9: the condition counts every arrived member, leaders included
state = function(MANAGER, "bool RaidManager::isStateMet(const std::string& state, uint32_t raidGroupId) const")
check("RaidRules::isRaidDefeated(arrived, spawned, standing, leaderEscaped)" in state and
      "for(const std::string& member : group.mSpawned)" in state, "RA9: defeated needs every member, leaders too")
standing = function(MANAGER, "bool RaidManager::isStanding(const std::string& creatureName) const")
check("creature->isAlive() && (creature->getIsOnMap() || creature->isInHand()) && !creature->isInPrison()" in standing and
      "!CombatGroupManager::isKeeperSeat(creature->getSeat())" in standing,
      "RA9: dead, imprisoned or won over members no longer stand")

# RA1: the gate is a hero portal room: unclaimable and indestructible, without waves of its own
check(re.search(r"bool RoomPortalWave::isClaimable\(Seat\* seat\) const\s*\{[^}]*return false;", PORTAL) is not None,
      "RA1: the gate cannot be claimed")
check(re.search(r"virtual bool isAttackable\(Tile\* tile, Seat\* seat\) const override\s*\{ return false; \}",
                PORTAL_H) is not None, "RA1: the gate cannot be destroyed")
upkeep = function(PORTAL, "void RoomPortalWave::doUpkeep()")
check(upkeep.index("if(mIsMoreyaGate)") < upkeep.index("handleFirstUpkeep();"), "RA1: the gate spawns no waves")
position = function(PORTAL, "void RoomPortalWave::updatePortalPosition()")
check('"MoreyaGate"' in position and '"MoreyaGatePortcullis"' in function(PORTAL, "void RoomPortalWave::setMoreyaGateOpen("),
      "RA1: the gate shows the gate model with its portcullis")
check("-portcullisSink" in function(PORTAL, "void RoomPortalWave::setMoreyaGateOpen("),
      "RA3: the portcullis sinks into the floor when the gate opens")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"rules","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("raid rules ok")
