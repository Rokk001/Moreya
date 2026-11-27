#!/usr/bin/env python3
"""Static check of the sounds of the spells (no compiler needed).

    python source/tests/check_spell_sounds.py

Checks that every spell has an own cast sound family that the server plays, that the end sounds of the defector
and hen spells and the impact and end sounds that the config plays exist, that every sound file is a real Ogg
file with a CREDITS entry, that no two sounds are the same file, and that the config plays every impact sound.

The spell sounds and config/roomAmbienceSpellsFx.cfg are game data of the content packages
(scripts/content_packages.py): they are read from the public tree or from the content packages, their CREDITS rows from
the CREDITS of the public tree and of the content repository. Without the content the sounds and the config are named
as not checked; the code is checked.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402


def read(*parts):
    """Returns the text of a file below the repository root (game data from the public tree or a content package)."""
    with open(str(content_packages.resolve(ROOT, "/".join(parts))), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def sound_file(family):
    """The path of the sound of a spell family from the public tree or a content package (below the repository when
    it is not found)."""
    return str(content_packages.resolve(ROOT, "sounds/Spatial/Spells/%s/Fx%s01.ogg" % (family, family)))


problems = []
# The CREDITS of the public tree and of the content repository
credits = room_packages.credits_text(ROOT)
# The sounds and the config are checked when the config is found or the content is present (then a missing file fails
# as before)
DATA = (content_packages.has_content(ROOT)
        or content_packages.data_file(ROOT, "config/roomAmbienceSpellsFx.cfg") is not None)
if not DATA:
    content_packages.unchecked("check_spell_sounds", ["the spell sounds and their CREDITS rows",
                                                      "config/roomAmbienceSpellsFx.cfg"])

spell_dir = os.path.join(ROOT, "source", "spells")
server_code = "".join(read("source", "spells", name) for name in sorted(os.listdir(spell_dir)) if name.endswith(".cpp"))
server_code += read("source", "creatureeffect", "CreatureEffectHexenHen.cpp") + \
    read("source", "creatureeffect", "CreatureEffectDefector.cpp") + \
    "".join(read("source", "creatureskill", name) for name in ("CreatureSkillHasteSelf.cpp", "CreatureSkillHealSelf.cpp",
                                                                "CreatureSkillDefenseSelf.cpp"))
casts = ("SummonWorkerCast", "CallToWarCast", "HealCast", "ExplosionCast", "HasteCast", "DefenseCast", "SlowCast",
         "StrengthCast", "WeakCast", "EyeEvilCast", "GoldCast", "LightningCast", "TremorCast", "DefectorCast",
         "HexenHenCast", "InfernoCast", "PossessCast", "ChampionCast")
if len(casts) != 18:
    problems.append("expected 18 spells with an own cast sound")
# The six spells of the spells review reuse existing recordings (no new sound file): spell source, effect name, family
REVIEW_SOUNDS = (("SpellCurse.cpp", "Weak", "Curse"), ("SpellBlessing.cpp", "Strength", "Boost"),
                 ("SpellInvisibility.cpp", "", "Dark"), ("SpellPlague.cpp", "", "Curse"),
                 ("SpellBreakWall.cpp", "Tremor", "TremorImpact"), ("SpellRevealEnemy.cpp", "", "EyeEvilCast"))
if len(casts) + len(REVIEW_SOUNDS) != 24:
    problems.append("expected 24 spells")
for source, effect, family in REVIEW_SOUNDS:
    path = sound_file(family)
    if DATA and (not os.path.exists(path) or os.path.getsize(path) < 1000):
        problems.append("sound %s of %s is missing or too small" % (family, source))
    if DATA and ("sounds/Spatial/Spells/%s/Fx%s01.ogg" % (family, family)) not in credits:
        problems.append("CREDITS has no entry for sound %s of %s" % (family, source))
    if ('fireSpellEffect(' not in read("source", "spells", source) or
            ('"%s", "%s", gameMap, player->getSeat())' % (effect, family)) not in read("source", "spells", source)):
        problems.append("%s does not play %s with the effect %s" % (source, family, effect or "(none)"))
others = ("ExplosionImpact", "LightningImpact", "TremorImpact", "InfernoImpact", "GoldImpact", "HealImpact",
          "HasteImpact", "PossessEnd", "DefectorEnd", "HexenHenEnd")
digests = {}
for family in casts + others if DATA else ():
    path = sound_file(family)
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        problems.append("sound %s is missing or too small" % family)
        continue
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"OggS":
        problems.append("sound %s is not an Ogg file" % family)
    if ("sounds/Spatial/Spells/%s/Fx%s01.ogg" % (family, family)) not in credits:
        problems.append("CREDITS has no entry for sound %s" % family)
    if data in digests:
        problems.append("sounds %s and %s are identical" % (family, digests[data]))
    digests[data] = family

for family in casts + ("DefectorEnd", "HexenHenEnd"):
    if '"%s"' % family not in server_code:
        problems.append("the server does not play the sound %s" % family)

if DATA:
    fx_cfg = read("config", "roomAmbienceSpellsFx.cfg")
    for family in others:
        if family in ("DefectorEnd", "HexenHenEnd"):
            continue
        if ("Spells/%s" % family) not in fx_cfg:
            problems.append("config has no effect that plays %s" % family)
    for block in re.findall(r"\[Effect\](.*?)\[/Effect\]", fx_cfg, re.S):
        family = re.search(r"^\s*Family\s+Spells/(\S+)", block, re.M)
        if family is not None and family.group(1) not in casts + others:
            problems.append("the config plays the unknown sound family %s" % family.group(1))

if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("fine")
