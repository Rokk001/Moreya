#!/usr/bin/env python3
"""Non-compiling check of the rules of the shared group combat (raid plan R1: G2 leader, G3 roles, G4 shared target,
G5 aggro, G6 formation, G7 retreat).

Every rule is checked twice: a Python model written from the rule computes fixed scenarios whose expected results are
written in this file, and the C++ source of source/game/CombatGroupRules.cpp and of the engine side
(CombatGroupManager, the creature actions, the fight action) is checked for the statements that implement the same
rule. Nothing is compiled and the game is not started; the integration build compiles and runs the code.

Usage: python -I source/tests/check_group_combat_rules.py
Exit 0 and "group combat rules ok" when every item holds.

config/creatureSkills.cfg is content (core-config package, found through scripts/content_packages.py); without it the
taunt and aggro skill checks of that table are named as not checked.
"""
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402

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


RULES = read("source/game/CombatGroupRules.cpp")
RULES_H = read("source/game/CombatGroupRules.h")
MANAGER = read("source/game/CombatGroupManager.cpp")
CREATURE = read("source/entities/Creature.cpp")
FIGHT = read("source/creatureaction/CreatureActionFight.cpp")
ATTACK = read("source/creaturebehaviour/CreatureBehaviourAttackEnemy.cpp")
#: True when the content packages are present: config/global.cfg is a mixed table whose own rows come from them
CONTENT = content_packages.has_content(ROOT)
#: config/global.cfg as the game reads it, with its own rows from the content
GLOBAL_CFG = content_packages.read_text(ROOT, "config/global.cfg")
#: The skill templates (core-config package), None without the content
SKILLS_CFG = (content_packages.read_text(ROOT, "config/creatureSkills.cfg")
              if content_packages.data_file(ROOT, "config/creatureSkills.cfg") else None)


def group_block_words(key):
    """Returns the words of a key of the [GroupCombat] block of global.cfg."""
    block = GLOBAL_CFG.split("[GroupCombat]")[1].split("[/GroupCombat]")[0]
    for line in block.splitlines():
        words = line.split("#")[0].split()
        if words and words[0] == key:
            return words[1:]
    raise AssertionError("missing [GroupCombat] key " + key)


# ------------------------------------------------------------------------------------------------ G3 roles
TANK, MELEE, SUPPORTER, RANGED, HEALER = "tank", "melee", "supporter", "ranged", "healer"
# The [GroupCombat] block of global.cfg holds own rows: without the content its values are not there
TANK_GROUPS = group_block_words("GroupTankSkillGroups") if CONTENT else None
HEALER_GROUPS = group_block_words("GroupHealerSkillGroups") if CONTENT else None
SUPPORTER_GROUPS = group_block_words("GroupSupporterSkillGroups") if CONTENT else None
RANGED_GROUPS = group_block_words("GroupRangedSkillGroups") if CONTENT else None


def role_of(skill_group):
    """Model of CombatGroupRules::roleOf: the role follows the skill group alone (tank, healer, supporter, ranged
    groups, every other group melee)."""
    if skill_group in TANK_GROUPS:
        return TANK
    if skill_group in HEALER_GROUPS:
        return HEALER
    if skill_group in SUPPORTER_GROUPS:
        return SUPPORTER
    if skill_group in RANGED_GROUPS:
        return RANGED
    return MELEE


# The group-fight role of every skill group (creature roster plan, CR4 and D26), counted once from the plan: the tank
# group tanks, the healer group healers, the supporter group supporters, warrior and skirmisher melee, marksman and
# mage ranged; the worker group and a creature without a skill group (the Shadow Lord) count as melee.
EXPECTED_GROUP_ROLES = {
    "tank": TANK, "healer": HEALER, "supporter": SUPPORTER, "warrior": MELEE, "skirmisher": MELEE,
    "marksman": RANGED, "mage": RANGED, "worker": MELEE, "none": MELEE, "": MELEE,
}
if CONTENT:
    for group, expected in EXPECTED_GROUP_ROLES.items():
        check(role_of(group) == expected, "G3: group-fight role of skill group " + repr(group))
    check(TANK_GROUPS == ["tank"] and HEALER_GROUPS == ["healer"] and SUPPORTER_GROUPS == ["supporter"] and
          RANGED_GROUPS == ["marksman", "mage"], "G3: role lists of the [GroupCombat] block")

role_body = function(RULES, "Role roleOf(")
check(role_body.index("mTankSkillGroups") < role_body.index("mHealerSkillGroups") <
      role_body.index("mSupporterSkillGroups") < role_body.index("mRangedSkillGroups"),
      "G3: roleOf tests the tank, healer, supporter and ranged skill groups in this order")
check("return Role::supporter;" in role_body and "return Role::melee;" in role_body, "G3: supporter / melee role")
check("Role roleOf(const RoleSettings& settings, const std::string& skillGroup);" in RULES_H,
      "G3: roleOf takes only the skill group (no template, no primary path)")
get_role = function(MANAGER, "CombatGroupRules::Role CombatGroupManager::getRole(")
check("roleOf(mRoleSettings, definition->getSkillGroup())" in get_role and "mTemplate" not in get_role and
      "mPrimary" not in get_role, "G3: the role is read from the skill group, not from the template")
for key in ("GroupTankSkillGroups", "GroupHealerSkillGroups", "GroupSupporterSkillGroups", "GroupRangedSkillGroups"):
    check('getGroupCombatConfigWords("' + key + '")' in MANAGER, "G3: the manager reads " + key)

# ------------------------------------------------------------------------------------------------ G2 leader


def choose_leader(candidates, named):
    """Model of CombatGroupRules::chooseLeader on (name, level, experience) tuples."""
    for index, candidate in enumerate(candidates):
        if named and candidate[0] == named:
            return index
    best = -1
    for index, candidate in enumerate(candidates):
        if best < 0:
            best = index
            continue
        other = candidates[best]
        if (-candidate[1], -candidate[2], candidate[0]) < (-other[1], -other[2], other[0]):
            best = index
    return best


group = [("Alda", 7, 10.0), ("Bran", 9, 2.0), ("Cora", 9, 30.0), ("Dunn", 3, 99.0)]
check(group[choose_leader(group, "")][0] == "Cora", "G2: highest level leads, more experience breaks the tie")
check(group[choose_leader([group[0], group[1]], "")][0] == "Bran", "G2: highest level leads")
check(choose_leader([("Eric", 5, 1.0), ("Abel", 5, 1.0)], "") == 1, "G2: equal level and experience: first name")
# Succession: the leader falls (he is no longer a present member), the next highest level leads at once
survivors = [member for member in group if member[0] != "Cora"]
check(survivors[choose_leader(survivors, "")][0] == "Bran", "G2: succession to the next highest level")
# The named raid leader leads while he lives, whatever his level
check(group[choose_leader(group, "Dunn")][0] == "Dunn", "G2: the named raid leader leads while alive")
without_named = [member for member in survivors if member[0] != "Dunn"]
check(without_named[choose_leader(without_named, "Dunn")][0] == "Bran",
      "G2: after the named leader falls the highest level leads")

leads = function(RULES, "bool leadsBefore(")
check(leads.index("mLevel") < leads.index("mExperience") < leads.index("mName"),
      "G2: leadsBefore compares level, then experience, then name")
check("first.mLevel > second.mLevel" in leads and "first.mExperience > second.mExperience" in leads,
      "G2: higher level and more experience lead")
choose = function(RULES, "int32_t chooseLeader(")
check(choose.index("namedLeader") < choose.index("leadsBefore"), "G2: the named leader is taken first")
update_group = function(MANAGER, "void CombatGroupManager::updateGroup(")
check("chooseLeader(candidates, namedLeader)" in update_group and "getRaidLeaderName(group.mRaidGroupId)" in update_group,
      "G2: the leader is chosen at every update among the present members (immediate succession)")
check("member->getLevel()" in update_group and "member->getExp()" in update_group, "G2: level and experience")

# ------------------------------------------------------------------------------------------------ G4 shared target


def choose_target(candidates, current):
    """Model of CombatGroupRules::chooseSharedTarget on (name, role, squared distance) tuples."""
    def key(candidate):
        return (0 if candidate[1] == HEALER else 1, candidate[2], candidate[0])
    if not candidates:
        return None
    best = min(candidates, key=key)
    for candidate in candidates:
        if candidate[0] == current and key(candidate)[0] == key(best)[0]:
            return candidate[0]
    return best[0]


enemies = [("Knight1", TANK, 4), ("Wizard1", RANGED, 9), ("Priest1", HEALER, 64), ("Elf1", RANGED, 1)]
check(choose_target(enemies, "") == "Priest1", "G4: the leader chooses the enemy healer first, even far away")
check(choose_target([e for e in enemies if e[1] != HEALER], "") == "Elf1", "G4: without healer the nearest enemy")
check(choose_target([e for e in enemies if e[1] != HEALER], "Wizard1") == "Wizard1",
      "G4: the current target of the same priority is kept")
check(choose_target(enemies, "Wizard1") == "Priest1", "G4: a healer in sight replaces a non-healer target")
check(choose_target([], "Wizard1") is None, "G4: no enemy, no target")

target_body = function(RULES, "int32_t chooseSharedTarget(")
check("isBetterTarget" in target_body and "targetPriority" in target_body, "G4: priority and distance decide")
check("return (role == Role::healer) ? 0 : 1;" in RULES, "G4: healers have the first priority")
check("visibleEnemyCreatures(*leader)" in update_group, "G4: the leader chooses among the enemies he sees")

# ------------------------------------------------------------------------------------------------ G5 aggro


def choose_aggro(attacking, near, adjacent):
    """Model of CombatGroupRules::chooseAggroTank on (name, distance) tuples."""
    if attacking:
        return attacking
    close = sorted((d, n) for n, d in near if d <= adjacent)
    return close[0][1] if close else ""


if CONTENT:
    ADJACENT = int(float(group_block_words("GroupAggroAdjacentTiles")[0]))
    check(ADJACENT == 1, "G5: next to a tank means the eight neighbour tiles (GroupAggroAdjacentTiles 1)")
    check(choose_aggro("Guard1", [("Guard2", 1)], ADJACENT) == "Guard1", "G5: the tank that hit the member wins")
    check(choose_aggro("", [("Guard2", 1), ("Guard3", 1)], ADJACENT) == "Guard2", "G5: next to a tank: that tank")
    check(choose_aggro("", [("Guard2", 2)], ADJACENT) == "", "G5: a tank two tiles away draws no aggro")


def fight_target(aggro, shared):
    """Model of CombatGroupManager::getFightTarget: the aggro tank, else the shared target."""
    return aggro if aggro else shared


check(fight_target("Guard2", "Priest1") == "Guard2", "G5: a member with aggro attacks the tank")
check(fight_target("", "Priest1") == "Priest1", "G5: all other members follow the shared target")

aggro_body = function(RULES, "std::string chooseAggroTank(")
check(aggro_body.index("attackingTank") < aggro_body.index("adjacentTiles"), "G5: hit first, then next to")
fight_target_body = function(MANAGER, "GameEntity* CombatGroupManager::getFightTarget(")
check(fight_target_body.index("group->mTarget") < fight_target_body.index("mAggroTargets.find"),
      "G5: the aggro tank replaces the shared target")
notify = function(MANAGER, "void CombatGroupManager::notifyAttacked(")
check("CombatGroupRules::Role::tank" in notify and "GroupAggroMemorySeconds" in notify,
      "G5: only a hit of an enemy tank gives aggro, for GroupAggroMemorySeconds")
take_damage = function(CREATURE, "double Creature::takeDamage(")
check("getCombatGroups().notifyAttacked(*this, *creatureAttacking)" in take_damage, "G5: hits are reported")
handle_fight = function(FIGHT, "bool CreatureActionFight::handleFight(")
check("getCombatGroups().getFightTarget(creature)" in handle_fight and "enemyPrioritaryTargets = groupTargets;" in
      handle_fight, "G4/G5: a member attacks the group target in its fight")
# The aggro is a rule of target choice: no new skill
for path in ("source/game/CombatGroupRules.cpp", "source/game/CombatGroupManager.cpp"):
    check("CreatureSkill" not in read(path).replace("CreatureSkillTree", ""), "G5: no skill in " + path)
# The roster plan (D11, D25) adds one taunt skill: tier 1 of the tank path Ironclad, the pre-skill of every tank. It is
# the only taunt and lives in the tank group; there is no other aggro skill kind.
if SKILLS_CFG is not None:
    taunt_blocks = [block for block in re.findall(r"^\[Skill\]\s*$(.*?)^\[/Skill\]", SKILLS_CFG, re.M | re.S)
                    if re.search(r"^Kind\s+TAUNT\s*$", block, re.M)]
    check(len(taunt_blocks) == 1 and re.search(r"^Id\s+TNK_A1\s*$", taunt_blocks[0], re.M) and
          re.search(r"^Group\s+tank\s*$", taunt_blocks[0], re.M) and re.search(r"^Path\s+Ironclad\s*$", taunt_blocks[0], re.M)
          and re.search(r"^Tier\s+1\s*$", taunt_blocks[0], re.M),
          "G5: the only taunt skill is TNK_A1, tier 1 of the tank path Ironclad")
    check(not re.search(r"^Kind\s+TAUNT", "\n".join(re.findall(r"^\[TierFour\]\s*$(.*?)^\[/TierFour\]", SKILLS_CFG,
                                                                  re.M | re.S)), re.M), "G5: no tier 4 taunt")
    check(not re.search(r"^Kind\s+AGGRO", SKILLS_CFG, re.M), "G5: no aggro skill kind in creatureSkills.cfg")

# ------------------------------------------------------------------------------------------------ G6 formation


def formation_places(members, width):
    """Model of CombatGroupRules::formationPlaces: roles in order, each role in rows of width places."""
    places = {}
    row = 1
    for role in (TANK, MELEE, SUPPORTER, RANGED, HEALER):
        of_role = sorted(name for name, member_role in members if member_role == role)
        for start in range(0, len(of_role), width):
            in_row = of_role[start:start + width]
            for index, name in enumerate(in_row):
                places[name] = (row, index - (len(in_row) - 1) / 2.0)
            row += 1
    return places


def place_position(leader, facing, place, spacing):
    """Model of CombatGroupRules::placePosition: rows behind the leader, places to the side."""
    length = math.hypot(facing[0], facing[1]) or 1.0
    forward = (facing[0] / length, facing[1] / length) if math.hypot(*facing) else (1.0, 0.0)
    side = (-forward[1], forward[0])
    back = place[0] * spacing
    return (leader[0] - forward[0] * back + side[0] * place[1] * spacing,
            leader[1] - forward[1] * back + side[1] * place[1] * spacing)


members = [("Tank1", TANK), ("Tank2", TANK), ("Melee1", MELEE), ("Support1", SUPPORTER), ("Support2", SUPPORTER),
           ("Range1", RANGED), ("Range2", RANGED), ("Range3", RANGED), ("Range4", RANGED), ("Heal1", HEALER)]
places = formation_places(members, 3)
check(places == {"Tank1": (1, -0.5), "Tank2": (1, 0.5), "Melee1": (2, 0.0), "Support1": (3, -0.5),
                  "Support2": (3, 0.5), "Range1": (4, -1.0), "Range2": (4, 0.0), "Range3": (4, 1.0), "Range4": (5, 0.0),
                  "Heal1": (6, 0.0)}, "G6: formation rows " + repr(places))
rows = {role: max(places[n][0] for n, r in members if r == role) for role in (TANK, MELEE, SUPPORTER, RANGED, HEALER)}
check(rows[TANK] < rows[MELEE] < rows[SUPPORTER] < rows[RANGED] < rows[HEALER],
      "G6: tanks, melee, supporters, ranged, healers from the front (D26)")
# Without supporters the rows close up: no empty supporter row between melee and ranged
places = formation_places([("Melee1", MELEE), ("Range1", RANGED)], 3)
check(places == {"Melee1": (1, 0.0), "Range1": (2, 0.0)}, "G6: no empty row for a missing role " + repr(places))
places = formation_places(members, 3)
# The group faces +x: every place lies behind (smaller x than) the leader at 10,10
for name, place in places.items():
    position = place_position((10.0, 10.0), (1.0, 0.0), place, 1.0)
    check(position[0] < 10.0, "G6: " + name + " stands behind the leader")
check(place_position((10.0, 10.0), (0.0, 1.0), (2, 0.0), 1.0) == (10.0, 8.0), "G6: rows follow the facing")

order_body = function(RULES, "std::vector<Role> formationOrder(")
pushes = re.findall(r"order\.push_back\(Role::(\w+)\);", order_body)
check(pushes == ["tank", "melee", "supporter", "ranged", "healer"], "G6: formation order in the source " + repr(pushes))
check(re.search(r"tank = 0,\s*melee = 1,\s*supporter = 2,\s*ranged = 3,\s*healer = 4", RULES_H) is not None,
      "G6: role order")
check('case Role::supporter:\n            return "supporter";' in function(RULES, "const char* roleName("),
      "G6: the supporter role has its own name")
check("leaderX - forwardX * back" in RULES and "leaderY - forwardY * back" in RULES, "G6: places behind the leader")
check("formationPlaces(formationMembers" in update_group and "member == leader" in update_group,
      "G6: every member but the leader gets a place")
follow = read("source/creatureaction/CreatureActionGroupFollow.cpp")
check("getFormationTile(creature)" in follow and "isAtFormationPlace(creature, *place)" in follow,
      "G6: a member walks to its place and holds it")
# Healers heal the members with the existing heal skills: the heal skills heal own creatures in range
heal_ally = read("source/creatureskill/CreatureSkillHealAlly.cpp")
check("getOwnCreaturesWithin(mRange)" in heal_ally, "G6: the existing heal skill heals own creatures in range")

# ------------------------------------------------------------------------------------------------ G7 retreat


def order_options(options, group_to_enemy):
    """Model of CombatGroupRules::orderRetreatOptions on (x, y, to group, to enemy) tuples."""
    kept = [o for o in options if o[3] > group_to_enemy]
    return [options.index(o) for o in sorted(kept, key=lambda o: (o[2], o[0], o[1]))]


def choose_retreat(doors, rooms, group_to_enemy):
    """Model of CombatGroupManager::findRetreatTile with every option reachable: doors first, then rooms."""
    for options, kind in ((doors, "door"), (rooms, "room")):
        order = order_options(options, group_to_enemy)
        if order:
            return kind, options[order[0]][:2]
    return None, None


# The group stands at 10,10, the enemy at 20,10 (squared distance 100)
door_behind = (5, 10, 25, 225)     # behind the group, away from the enemy
door_ahead = (16, 10, 36, 16)      # between the group and the enemy: not away from it
room_behind = (2, 10, 64, 324)
room_ahead = (25, 10, 225, 25)
check(choose_retreat([door_ahead, door_behind], [room_behind], 100) == ("door", (5, 10)),
      "G7: the group retreats behind the next door away from the enemy")
check(choose_retreat([door_ahead], [room_ahead, room_behind], 100) == ("room", (2, 10)),
      "G7: without such a door the nearest own room away from the enemy")
check(choose_retreat([door_ahead], [room_ahead], 100) == (None, None), "G7: no door and no room: no retreat")


def should_retreat(hp, max_hp, enemy, share):
    """Model of CombatGroupRules::shouldRetreat."""
    return enemy and max_hp > 0 and hp / max_hp < share


if CONTENT:
    SHARE = float(group_block_words("GroupRetreatHealthShare")[0])
    check(should_retreat(SHARE * 100 - 1, 100, True, SHARE), "G7: below the share with an enemy in sight: retreat")
    check(not should_retreat(SHARE * 100 + 1, 100, True, SHARE), "G7: above the share: no retreat")
    check(not should_retreat(0, 100, False, SHARE), "G7: no enemy in sight: no retreat")

find_retreat = function(MANAGER, "bool CombatGroupManager::findRetreatTile(")
check(find_retreat.index("doorOptions") < find_retreat.index("roomOptions"), "G7: doors before rooms")
check("trap->isDoor()" in find_retreat and "group.mSeatId" in find_retreat, "G7: only own doors and rooms")
check(find_retreat.count("pathExists(&leader") == 2, "G7: the gathering tile must be reachable")
check("mSquaredDistanceToEnemy <= groupToEnemySquared" in function(RULES, "std::vector<size_t> orderRetreatOptions("),
      "G7: only options away from the enemy")
check("shouldRetreat(groupHp, groupMaxHp, !enemies.empty(), groupConfig(\"GroupRetreatHealthShare\"))" in update_group,
      "G7: the leader decides from the configured retreat condition")
handle_group = function(CREATURE, "void Creature::handleCombatGroup()")
check(handle_group.index("groups.isRetreating(*this)") < handle_group.index("shouldKeepFormation(*this)"),
      "G7: the retreat comes before the formation")
check("CreatureActionGroupRetreat" in handle_group and "clearActionQueue();" in handle_group,
      "G7: a retreating member drops what it does")
check("CreatureActionType::groupRetreat" in function(ATTACK, "bool CreatureBehaviourAttackEnemy::processBehaviour("),
      "G7: a retreating member starts no fight")
retreat = read("source/creatureaction/CreatureActionGroupRetreat.cpp")
check("getRetreatTile(creature)" in retreat and "isAtGatheringTile(creature, *gathering)" in retreat,
      "G7: members walk to the gathering tile and gather there")
check("retreatFinished(arrived" in update_group and "GroupRetreatCooldownSeconds" in update_group,
      "G7: the group gathers again and the next retreat waits for the cooldown")

if SKILLS_CFG is None:
    content_packages.unchecked("check_group_combat_rules", ["config/creatureSkills.cfg"])
if not CONTENT:
    content_packages.unchecked("check_group_combat_rules", ["G3 roles of the skill groups, G5 aggro distance and G7 "
                                                            "retreat share of the [GroupCombat] block of config/global.cfg"])
elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"rules","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("group combat rules ok")
