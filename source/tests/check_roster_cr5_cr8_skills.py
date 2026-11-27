#!/usr/bin/env python3
"""Acceptance checks CR5 (pre-skills) and CR8 (tier 4 skills) of the creature roster plan, config and source part.

CR5: every creature with a pre-skill (tanks the Taunt, Monk and Cultist the Mend, Priestess and Vampire the Circle of
Renewal, the supporters the Aura of Might, Dark Elf and Goblin the Weak Spot, Gnome and Elf the Blast Shot, the
Wizard the Lightning, Lich, Cave Hornet and Dragon their family skill, the workers theirs) names a skill of
config/creatureSkills.cfg that is the tier 1 skill of the expected path of its group or family; the tank pre-skill is
a TAUNT. The skill tree source gives the pre-skill rank 1 when a build starts (level 1) and again after a reset, so
it cannot be removed. Spawning a level-1 creature in the game and the game tests (a tank drawing an enemy, a healer
healing an ally) need the integration build.

CR8: every creature but the Shadow Lord has exactly one [TierFour] block with the name of D16, D34 and section 5c and
a kind that fits its role; the removed creatures have none.

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr5_cr8_skills.py
Exit 0 and "roster CR5 CR8 ok" when every item holds.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

SKILLS, TIER_FOURS, _TEMPLATES = plan.parse_skill_config(plan.read("config/creatureSkills.cfg"))
CREATURES = plan.parse_creatures(plan.read("config/creatures.cfg"))
TREE = plan.read("source/creatureskill/CreatureSkillTree.cpp")
CREATURE_CPP = plan.read("source/entities/Creature.cpp")


def function(source, signature):
    """Returns the function that starts with the signature (up to its closing brace)."""
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


# ------------------------------------------------------------------------------------------- CR5 pre-skills
by_id = {}
for entry in SKILLS:
    check(entry.get("Id") not in by_id, "CR5: skill id %s is unique" % entry.get("Id"))
    by_id[entry.get("Id")] = entry
for name, pre in sorted(plan.PRE_SKILL.items()):
    if pre is None:
        continue
    skill_id, owner, path, skill_name = pre
    entry = by_id.get(skill_id)
    if not check(entry is not None, "CR5: pre-skill %s of %s exists in creatureSkills.cfg" % (skill_id, name)):
        continue
    if owner.startswith("family:"):
        got_owner = "family:" + entry.get("Family", "")
    else:
        got_owner = entry.get("Group", "")
    got = (got_owner, entry.get("Path"), entry.get("Tier"), entry.get("Name"))
    check(got == (owner, path, "1", skill_name), "CR5: pre-skill %s of %s is tier 1 %s of path %s of %s (config %s)"
          % (skill_id, name, skill_name, path, owner, got))
    if plan.ROSTER[name][2] == "tank":
        check(entry.get("Kind", "").split()[:1] == ["TAUNT"], "CR5: the tank pre-skill of %s is a TAUNT (config %s)"
              % (name, entry.get("Kind")))
start = function(TREE, "void startBuild(SkillBuild& build, const TypeInfo& type, uint32_t seed)")
check("build.mRanks[type.mPreSkill] = 1;" in start, "CR5: a new build has the pre-skill at rank 1")
reset = function(TREE, "void resetBuild(")
check(reset.index("build.mRanks.clear();") < reset.index("build.mRanks[type.mPreSkill] = 1;"),
      "CR5: a reset gives the pre-skill rank 1 again (it cannot be removed)")
check("type.mPreSkill = skillTextOrEmpty(mDefinition->getPreSkill());" in CREATURE_CPP,
      "CR5: the creature passes the PreSkill of its type to the skill tree")

# ----------------------------------------------------------------------------------------- CR8 tier 4 skills
creatures_with_tier4 = [entry.get("Creature") for entry in TIER_FOURS]
check(sorted(creatures_with_tier4) == sorted(plan.TIER_FOUR),
      "CR8: [TierFour] blocks for exactly the 35 creatures but the Shadow Lord; extra %s, missing %s"
      % (sorted(set(creatures_with_tier4) - set(plan.TIER_FOUR)), sorted(set(plan.TIER_FOUR) - set(creatures_with_tier4))))
check(len(creatures_with_tier4) == len(set(creatures_with_tier4)), "CR8: one tier 4 skill per creature")
for removed in plan.REMOVED:
    check(removed not in creatures_with_tier4, "CR8: the removed %s has no tier 4 skill" % removed)
check("Champion" not in creatures_with_tier4, "CR8: the Shadow Lord has no tier 4 skill")
for entry in TIER_FOURS:
    name = entry.get("Creature")
    if name not in plan.TIER_FOUR:
        continue
    expected_name, kinds = plan.TIER_FOUR[name]
    kind = entry.get("Kind", "").split()[:1]
    check(entry.get("Name") == expected_name, "CR8: tier 4 skill of %s is named %s (config %s)"
          % (name, expected_name, entry.get("Name")))
    check(kind and kind[0] in kinds, "CR8: tier 4 skill of %s has a kind of %s (config %s)"
          % (name, kinds, entry.get("Kind")))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr5_cr8","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR5 CR8 ok")
