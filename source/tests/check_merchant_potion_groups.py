#!/usr/bin/env python3
"""Non-compiling check of the preferred merchant potion per skill group (creature roster plan, CR4 / D40).

A creature that buys at the merchant prefers, after the healing potions, the stat potion of its skill group: the tank
and warrior groups strength, the skirmisher and marksman groups dexterity, the mage, healer and supporter groups mana,
every other group (the workers and a creature without a skill group) life as before. The expected kinds are written in
this file; the check reads the function preferredPotionKind of source/game/CreatureMerchantAI.cpp and compares the
groups it names with them. Nothing is compiled and the game is not started.

Usage: python -I source/tests/check_merchant_potion_groups.py
Exit 0 and "merchant potion groups ok" when every item holds.
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


# The preferred potion kind of every skill group, counted once from the plan (D40): 8 skill groups, 3 stat kinds
EXPECTED = {
    "tank": "StrengthChange", "warrior": "StrengthChange",
    "skirmisher": "DexterityChange", "marksman": "DexterityChange",
    "mage": "MaxManaChange", "healer": "MaxManaChange", "supporter": "MaxManaChange",
}
# Groups that keep today's preference (life): the workers and a creature without a skill group
EXPECTED_DEFAULT = "MaxHPChange"
DEFAULT_GROUPS = ("worker", "none", "")

AI = read("source/game/CreatureMerchantAI.cpp")
body = function(AI, "std::string preferredPotionKind(const std::string& group)")

# Every "if(...) return "Kind";" line: the groups compared in the condition get that kind
named = {}
for condition, kind in re.findall(r"if\((.*?)\)\s*return\s+\"(\w+)\";", body):
    for group in re.findall(r"group == \"(\w+)\"", condition):
        check(group not in named, "D40: group named twice: " + group)
        named[group] = kind
check(named == EXPECTED, "D40: preferred potion per skill group " + repr(named))
default = re.findall(r"\n\s*return\s+\"(\w+)\";\s*\n\}", body)
check(default == [EXPECTED_DEFAULT], "D40: other groups keep the life potion " + repr(default))
for group in DEFAULT_GROUPS:
    check(group not in named, "D40: " + repr(group) + " keeps the default")
# The old skill group ids are gone from the preference
for old in ("blocker", "blitzer", "flanker", "archer", "caster"):
    check('"' + old + '"' not in body, "D40: old skill group id " + old + " no longer used")

# The preference is what potionPriority compares against
priority = function(AI, "PotionPriority potionPriority(")
check("preferredPotionKind(creature.getDefinition()->getSkillGroup())" in priority and
      "return PotionPriority::groupBuff;" in priority, "D40: potionPriority uses the group preference")

# Every preferred kind is a potion kind of config/potions.cfg
POTION_KINDS = set(re.findall(r"^\s*Kind\s+(\w+)", read("config/potions.cfg"), re.M))
for kind in set(EXPECTED.values()) | {EXPECTED_DEFAULT}:
    check(kind in POTION_KINDS, "D40: potions.cfg has potions of kind " + kind)

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"merchant_potion_groups","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("merchant potion groups ok")
