#!/usr/bin/env python3
"""Acceptance check CR4 (role groups) of the creature roster plan, config part.

config/creatureSkills.cfg holds the eight skill groups of section 5 (tank, healer, supporter, warrior, skirmisher,
marksman, mage, worker) and no old group; every group has its three paths of section 5c with the tiers 1, 2 and 3;
the members of every group are the creatures of section 5 (creatures.cfg); no path of a group holds a skill of
another role (an ally heal, shield or ally defence buff only in the healer group, an ally aura only in the supporter
group, the taunt only in the tank group, no damage skill in the healer group); no family skill gives an ability of
another role (D3); the tier 4 skills keep the roles (an ally heal only for healers and the two hybrids, D2, D16); no
skill makes a creature invisible (D28); every group has three templates, one per path, named after it, with the next
path of the group as the path of the deviating points (D37, D39). The families are the thirteen of D8 with one path
of three tiers each.

The group-fight role per group and the formation order tanks, melee, supporters, ranged, healers (D26) are asserted
by check_group_combat_rules.py (G3, G6); the preferred merchant potion per group (D40) by
check_merchant_potion_groups.py.

The expected values are the fixed data of source/tests/roster_plan_data.py.

Usage: python -I source/tests/check_roster_cr4_groups.py
Exit 0 and "roster CR4 ok" when every item holds.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster_plan_data as plan  # noqa: E402

START = time.perf_counter()
CHECK = plan.Checker()
check = CHECK.check

SKILLS, TIER_FOURS, TEMPLATES = plan.parse_skill_config(plan.read("config/creatureSkills.cfg"))
CREATURES = plan.parse_creatures(plan.read("config/creatures.cfg"))


def kind_of(entry):
    """Returns the Kind token of a skill entry."""
    return entry.get("Kind", "").split()[0] if entry.get("Kind") else ""


def label(entry):
    """Returns a short name of a skill entry for the messages."""
    return "%s (%s)" % (entry.get("Id", "?"), entry.get("Name", "?"))


def template_index(entry):
    """Returns the Index cell of a template entry (sort key)."""
    return entry.get("Index", "")


group_skills = [entry for entry in SKILLS if "Group" in entry]
family_skills = [entry for entry in SKILLS if "Family" in entry]
check(len(group_skills) + len(family_skills) == len(SKILLS), "CR4: every skill has a Group or a Family line")

# ---------------------------------------------------------------------------------------- groups and paths
groups = sorted(set(entry["Group"] for entry in group_skills))
check(groups == sorted(plan.GROUPS), "CR4: the skill groups are %s (config %s)" % (sorted(plan.GROUPS), groups))
for old in plan.OLD_GROUPS:
    check(all(entry["Group"] != old for entry in group_skills), "CR4: no skill of the old group " + old)
    check(all(entry.get("Group") != old for entry in TEMPLATES), "CR4: no template of the old group " + old)
for group in plan.GROUPS:
    members = [entry for entry in group_skills if entry["Group"] == group]
    check(len(members) == 9, "CR4: group %s has 9 skills, three paths of three tiers (config %d)"
          % (group, len(members)))
    expected_paths = [path for path, _ in plan.PATHS[group]]
    got_paths = []
    for entry in members:
        if entry.get("Path") not in got_paths:
            got_paths.append(entry.get("Path"))
    check(got_paths == expected_paths, "CR4: group %s paths %s in this order (config %s)"
          % (group, expected_paths, got_paths))
    for path in expected_paths:
        tiers = sorted(entry.get("Tier") for entry in members if entry.get("Path") == path)
        check(tiers == ["1", "2", "3"], "CR4: path %s of group %s has the tiers 1, 2, 3 (config %s)"
              % (path, group, tiers))
    expected_members = sorted(name for name, row in plan.ROSTER.items() if row[2] == group)
    got_members = sorted(name for name, entry in CREATURES.items()
                         if (entry.get("SkillGroup") or ["none"])[0] == group)
    check(got_members == expected_members, "CR4: members of group %s %s (config %s)"
          % (group, expected_members, got_members))

# ------------------------------------------------------------------------------- no skill of another role
for entry in group_skills:
    kind = kind_of(entry)
    group = entry["Group"]
    if kind in plan.ALLY_HEAL_KINDS:
        check(group == "healer", "CR4: ally heal %s %s in group %s" % (kind, label(entry), group))
    if kind in plan.SUPPORT_KINDS:
        check(group == "supporter", "CR4: ally aura %s %s in group %s" % (kind, label(entry), group))
    if kind in plan.TAUNT_KINDS:
        check(group == "tank", "CR4: taunt %s in group %s" % (label(entry), group))
    if group == "healer":
        check(kind not in plan.DAMAGE_KINDS, "CR4: damage skill %s %s in the healer group" % (kind, label(entry)))
for entry in family_skills:
    kind = kind_of(entry)
    check(kind not in plan.ALLY_HEAL_KINDS + plan.SUPPORT_KINDS + plan.TAUNT_KINDS,
          "CR4 D3: family skill %s of family %s gives an ability of another role (%s)"
          % (label(entry), entry["Family"], kind))
for entry in SKILLS + TIER_FOURS:
    check(kind_of(entry) not in plan.INVISIBLE_KINDS, "CR4 D28: %s makes a creature invisible" % label(entry))
for entry in TIER_FOURS:
    name = entry.get("Creature", "?")
    kind = kind_of(entry)
    group = plan.ROSTER.get(name, (None, None, "none"))[2]
    if kind in plan.ALLY_HEAL_KINDS:
        check(group == "healer" or name in plan.HYBRID_TIER_FOUR,
              "CR4: tier 4 skill of %s heals allies (%s) although it is no healer and no hybrid" % (name, kind))
    if kind in plan.SUPPORT_KINDS:
        check(group == "supporter", "CR4: tier 4 skill of %s is an ally aura (%s) of another role" % (name, kind))
    if kind in plan.TAUNT_KINDS:
        check(group == "tank", "CR4: tier 4 skill of %s is a taunt of another role" % name)

# -------------------------------------------------------------------------------------------------- families
families = sorted(set(entry["Family"] for entry in family_skills))
check(families == sorted(plan.FAMILIES), "CR4 D8: the families are %s (config %s)" % (sorted(plan.FAMILIES), families))
for family, (path, _names, members) in sorted(plan.FAMILIES.items()):
    entries = [entry for entry in family_skills if entry["Family"] == family]
    check(sorted(entry.get("Tier") for entry in entries) == ["1", "2", "3"] and
          set(entry.get("Path") for entry in entries) == {path},
          "CR4 D8: family %s has one path %s of tiers 1, 2, 3 (config %s)"
          % (family, path, [(entry.get("Path"), entry.get("Tier")) for entry in entries]))
    got_members = sorted(name for name, entry in CREATURES.items()
                         if (entry.get("SkillFamily") or ["none"])[0] == family)
    check(got_members == sorted(members), "CR4 D8: members of family %s %s (config %s)"
          % (family, sorted(members), got_members))

# ------------------------------------------------------------------------------------------------- templates
for group in plan.GROUPS:
    entries = sorted((entry for entry in TEMPLATES if entry.get("Group") == group), key=template_index)
    check([entry.get("Index") for entry in entries] == ["1", "2", "3"],
          "CR4 D37: group %s has the templates 1, 2, 3 (config %s)" % (group, [e.get("Index") for e in entries]))
    paths = [path for path, _ in plan.PATHS[group]]
    for index, entry in enumerate(entries[:3]):
        expected = (plan.TEMPLATE_NAMES[group][index], paths[index], paths[(index + 1) % 3])
        got = (entry.get("Name"), entry.get("Primary"), entry.get("Alternative"))
        check(got == expected, "CR4 D37 D39: template %d of group %s is (name, path, deviation path) %s (config %s)"
              % (index + 1, group, expected, got))
check(sorted(set(entry.get("Group") for entry in TEMPLATES)) == sorted(plan.GROUPS),
      "CR4 D37: templates only of the eight groups (config %s)" % sorted(set(e.get("Group") for e in TEMPLATES)))

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"roster_cr4","seconds":%.3f}' % elapsed)
print("%d items, %d failed" % (CHECK.items, len(CHECK.failures)))
if CHECK.failures:
    for failure in CHECK.failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("roster CR4 ok")
