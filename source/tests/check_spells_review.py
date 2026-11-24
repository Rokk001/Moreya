#!/usr/bin/env python3
"""Static check of the six keeper spells of the spells review: Curse, Blessing, Invisibility, Plague, Break Wall and
Reveal Enemy (no compiler needed).

    python source/tests/check_spells_review.py

Checks the config values with their documentation lines, the target rule and the effect of every spell, the amounts
of curse and blessing at every research level and their stacking, the end of the invisibility on an attack and on
time, the plague damage, its infection of own, allied and enemy creatures, the cure on admission and the walk of a sick
creature to a free cot, that workers and the champion never get sick, the walls Break Wall takes and refuses, the reveal
of every tile of the clicked keeper, the research nodes and effects, the 24 buttons of the spells tab, the sounds and
looks, the saving and loading of every running effect and the AI rows. Every expected value is written out here.

The spell particle script, config/roomAmbienceSpells.cfg and config/ai.cfg are game data of the content packages
(scripts/content_packages.py): they are read from the public tree or from the content packages, the CREDITS rows from
the CREDITS of the public tree and of the content repository. Without the content these parts are named as not
checked; the code, spells.cfg, skills.cfg and the layouts are checked.
"""

import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

problems = []
#: The game data files the check reads; they lie in the public tree or in a content package
DATA_FILES = ("particles/RoomAmbienceSpells.particle", "config/roomAmbienceSpells.cfg", "config/ai.cfg")


def read(*parts):
    """Returns the text of a file below the repository root (game data from the public tree or a content package)."""
    with open(str(content_packages.resolve(ROOT, "/".join(parts))), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def data_present():
    """True when the game data can be checked: all files are found or the content is present (then a missing one
    fails as before); else names the data part as not checked."""
    missing = [path for path in DATA_FILES if content_packages.data_file(ROOT, path) is None]
    if not missing or content_packages.has_content(ROOT):
        return True
    content_packages.unchecked("check_spells_review", missing + ["the CREDITS rows of the plague look and the recordings"])
    return False


DATA = data_present()
# The CREDITS of the public tree and of the content repository
CREDITS = room_packages.credits_text(ROOT)


def body(text, signature):
    """Returns the body of the function that starts with the signature (braces matched)."""
    start = text.find(signature)
    if start < 0:
        problems.append("missing function %s" % signature)
        return ""
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth and end < len(text):
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def need(condition, message):
    """Records a problem when the condition does not hold."""
    if not condition:
        problems.append(message)


def config_values(text, section):
    """Returns the key/value pairs of a [section] of a config file."""
    start = re.search(r"^\[%s\]\s*$" % section, text, re.M).end()
    block = text[start:re.search(r"^\[/%s\]\s*$" % section, text, re.M).start()]
    values = {}
    for line in block.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) == 2:
            values[fields[0]] = fields[1]
    return values


# ---------------------------------------------------------------------------------------------------------------------
# V1: every value of the section "Values" of the plan is a key of spells.cfg with a documentation line
VALUES = {
    "CursePrice": "7500", "CurseMoodJump": "-200", "CurseMoodFall": "-300", "CurseTurns": "252", "CurseCooldown": "20",
    "BlessingPrice": "7500", "BlessingMoodJump": "200", "BlessingMoodRise": "300", "BlessingTurns": "252",
    "BlessingCooldown": "20",
    "InvisibilityPrice": "6000", "InvisibilityTurns": "84", "InvisibilityCooldown": "30",
    "PlaguePrice": "24000", "PlagueDamagePerTurn": "0.5", "PlagueInfectRadius": "1", "PlagueInfectChancePerTurn": "0.05",
    "PlagueCooldown": "60",
    "BreakWallPrice": "3000", "BreakWallCooldown": "5",
    "RevealEnemyPrice": "100000", "RevealEnemyTurns": "7", "RevealEnemyCooldown": "300",
}
assert len(VALUES) == 23
spells_cfg = read("config", "spells.cfg")
spell_values = config_values(spells_cfg, "Spells")
for key, value in VALUES.items():
    need(spell_values.get(key) == value, "spells.cfg %s is %s, expected %s" % (key, spell_values.get(key), value))
    need(re.search(r"^#\s*%s\s+\(" % key, spells_cfg, re.M) is not None, "spells.cfg has no documentation line for %s" % key)
    if key.endswith("Price"):
        need(int(value) % 50 == 0, "%s is not a whole number of 50 mana steps" % key)
# The chance is a fraction, no percentage
need(0.0 < float(spell_values["PlagueInfectChancePerTurn"]) < 1.0, "the infection chance is a fraction")

# ---------------------------------------------------------------------------------------------------------------------
# The six spells are appended to the spell and skill enums and are built
spell_type = read("source", "spells", "SpellType.h")
spell_enum = re.findall(r"^\s*(\w+)\s*(?:=\s*0)?\s*,?\s*(?://.*)?$",
                        spell_type[spell_type.index("enum class SpellType"):spell_type.index("};")], re.M)
spell_enum = [name for name in spell_enum if name not in ("enum", "SpellType")]
need(spell_enum[-8:] == ["summonChampion", "curse", "blessing", "invisibility", "plague", "breakWall", "revealEnemy",
                         "nbSpells"], "SpellType ends with the six spells before nbSpells: %s" % spell_enum[-8:])
need(len(spell_enum) == 26, "SpellType holds nullSpellType, 24 spells and nbSpells: %d" % len(spell_enum))
skill_type = read("source", "game", "SkillType.h")
need(re.search(r"roomSpa,\s*(?://[^\n]*\s*)*spellCurse,\s*spellBlessing,\s*spellInvisibility,\s*spellPlague,\s*"
               r"spellBreakWall,\s*spellRevealEnemy,\s*(?://[^\n]*\s*)*countSkill", skill_type) is not None,
     "SkillType appends the six spell skills after roomSpa")
skill_type_cpp = read("source", "game", "SkillType.cpp")
cmake = read("CMakeLists.txt")
SPELLS = {
    # class: (name, display name, cooldown key, price key, skill type, game bar button)
    "SpellCurse": ("curse", "Curse", "CurseCooldown", "CursePrice", "spellCurse", "CurseButton"),
    "SpellBlessing": ("blessing", "Blessing", "BlessingCooldown", "BlessingPrice", "spellBlessing", "BlessingButton"),
    "SpellInvisibility": ("invisibility", "Invisibility", "InvisibilityCooldown", "InvisibilityPrice",
                          "spellInvisibility", "InvisibilityButton"),
    "SpellPlague": ("plague", "Plague", "PlagueCooldown", "PlaguePrice", "spellPlague", "PlagueButton"),
    "SpellBreakWall": ("breakWall", "Break Wall", "BreakWallCooldown", "BreakWallPrice", "spellBreakWall",
                       "BreakWallButton"),
    "SpellRevealEnemy": ("revealEnemy", "Reveal Enemy", "RevealEnemyCooldown", "RevealEnemyPrice", "spellRevealEnemy",
                         "RevealEnemyButton"),
}
sources = {}
for cls, (name, display, cooldown, price, skill, button) in SPELLS.items():
    sources[cls] = read("source", "spells", cls + ".cpp")
    code = sources[cls]
    need('const std::string %sName = "%s";' % (cls, name) in code, "%s saves as %s" % (cls, name))
    need('const std::string %sNameDisplay = "%s";' % (cls, display) in code, "%s is shown as %s" % (cls, display))
    need('const std::string %sCooldownKey = "%s";' % (cls, cooldown) in code, "%s cools down with %s" % (cls, cooldown))
    need("static SpellRegister reg(new %sFactory);" % cls in code, "%s registers its factory" % cls)
    need(('"%s"' % price) in code, "%s reads %s" % (cls, price))
    need("${SRC}/spells/%s.cpp" % cls in cmake, "%s.cpp is in the source list" % cls)
    need('return "%s";' % skill in skill_type_cpp, "SkillType.cpp names %s" % skill)
for extra in ("creatureaction/CreatureActionSearchInfirmary.cpp", "creatureeffect/CreatureEffectSpellInvisible.cpp"):
    need("${SRC}/%s" % extra in cmake, "%s is in the source list" % extra)

# ---------------------------------------------------------------------------------------------------------------------
# N1 Curse: target rule and effect
creature_cpp = read("source", "entities", "Creature.cpp")
curse = sources["SpellCurse"]
rule = body(curse, "bool SpellCurse::isValidTarget(")
for needle in ("!creature.isAlive()", "creature.getSeat()->isAlliedSeat(caster)", "getCreatureMoods().empty()",
               "creature.getSeatPrison() == caster", "creature.isSpellInvisible()", "isTileSeenBy(*pos, caster)"):
    need(needle in rule, "Curse target rule lacks %s" % needle)
need("getPositionTile()" in rule and "isClaimedForSeat" not in rule, "Curse reaches enemies anywhere on the map")
cast = body(curse, "bool SpellCurse::castSpell(")
need('applyMoodEvent(config.getSpellConfigDouble("CurseMoodJump") * factor, false)' in cast, "Curse jump at once")
need('addMoodEffect(MOOD_EFFECT_NAME, config.getSpellConfigDouble("CurseMoodFall") * factor,' in cast and
     'config.getSpellConfigDouble("CurseTurns")' in cast, "Curse fall over CurseTurns as a timed mood effect")
need("SkillType::spellCurse, 1.0,\n        ResearchEffect::MoodLoss" in cast, "the curse amounts follow MoodLoss")
need('const std::string SpellCurse::MOOD_EFFECT_NAME = "Curse";' in curse, 'the mood effect is named "Curse"')
need(cast.index("isValidTarget(") < cast.index("takeMana("), "the target is checked before the mana is taken")

# N2 Blessing
blessing = sources["SpellBlessing"]
rule = body(blessing, "bool SpellBlessing::isValidTarget(")
for needle in ("!creature.isAlive()", "creature.getSeat() != caster", "getCreatureMoods().empty()",
               "!creature.isInContainment()"):
    need(needle in rule, "Blessing target rule lacks %s" % needle)
cast = body(blessing, "bool SpellBlessing::castSpell(")
need('applyMoodEvent(config.getSpellConfigDouble("BlessingMoodJump") * factor, false)' in cast, "Blessing jump at once")
need('addMoodEffect(MOOD_EFFECT_NAME, config.getSpellConfigDouble("BlessingMoodRise") * factor,' in cast and
     'config.getSpellConfigDouble("BlessingTurns")' in cast, "Blessing rise over BlessingTurns")
need("ResearchEffect::MoodGain" in cast, "the blessing amounts follow MoodGain")
need('const std::string SpellBlessing::MOOD_EFFECT_NAME = "Blessing";' in blessing, 'the mood effect is named "Blessing"')

# Curse and blessing amounts at every research level (skills.cfg factors 1, 1.25, 1.5) and stacking
skills_cfg = read("config", "skills.cfg")
effects_block = skills_cfg[re.search(r"^\[ResearchEffects\]\s*$", skills_cfg, re.M).end():
                           re.search(r"^\[/ResearchEffects\]\s*$", skills_cfg, re.M).start()]
EFFECTS = {
    "spellCurse": ("MoodLoss", "mul", "1.0", "1.25", "1.5"),
    "spellBlessing": ("MoodGain", "mul", "1.0", "1.25", "1.5"),
    "spellInvisibility": ("Duration", "mul", "1.0", "1.5", "2.0"),
    "spellPlague": ("Damage", "mul", "1.0", "2.0", "4.0"),
    "spellBreakWall": ("Price", "mul", "1.0", "0.9", "0.8"),
    "spellRevealEnemy": ("Duration", "mul", "1.0", "1.5", "2.0"),
}
factors = {}
for skill, expected in EFFECTS.items():
    lines = [line.split() for line in effects_block.splitlines() if line.split()[:1] == [skill]]
    need(len(lines) == 1 and tuple(lines[0][1:]) == expected, "research effect of %s: %s" % (skill, lines))
    factors[skill] = [1.0] + [float(value) for value in expected[2:]]
AMOUNTS = {  # research level: (jump, spread total) of curse and blessing
    "Curse": [(-200, -300), (-200, -300), (-250, -375), (-300, -450)],
    "Blessing": [(200, 300), (200, 300), (250, 375), (300, 450)],
}
for level in range(4):
    for name, skill, jump_key, total_key in (("Curse", "spellCurse", "CurseMoodJump", "CurseMoodFall"),
                                             ("Blessing", "spellBlessing", "BlessingMoodJump", "BlessingMoodRise")):
        factor = factors[skill][level]
        got = (float(spell_values[jump_key]) * factor, float(spell_values[total_key]) * factor)
        need(all(math.isclose(a, b) for a, b in zip(got, AMOUNTS[name][level])),
             "%s amounts at level %d: %s, expected %s" % (name, level, got, AMOUNTS[name][level]))
add_effect = body(creature_cpp, "void Creature::addMoodEffect(")
need("mMoodEffects.push_back(CreatureMoodEffect(name, totalPoints / turns, turns));" in add_effect and
     "effect.mName == name" not in add_effect, "every curse and blessing adds a mood effect of its own (they stack)")
change = body(creature_cpp, "void Creature::changeStoredMood(")
need("std::min(static_cast<double>(ConfigManager::getSingleton().getCreatureBaseMood())" in change,
     "the stored mood never rises above the maximum")
# Two curses on one creature: two effects of -300 / 252 turns run together
need(math.isclose(2 * (-300.0 / 252.0), -600.0 / 252.0), "stacked curses add their falls")

# ---------------------------------------------------------------------------------------------------------------------
# N3 Invisibility
invisibility = sources["SpellInvisibility"]
rule = body(invisibility, "bool SpellInvisibility::isValidTarget(")
for needle in ("!creature.isAlive()", "creature.getSeat() != caster", "!creature.isKo()", "!creature.isInContainment()"):
    need(needle in rule, "Invisibility target rule lacks %s" % needle)
cast = body(invisibility, "bool SpellInvisibility::castSpell(")
need('SkillType::spellInvisibility,\n        ConfigManager::getSingleton().getSpellConfigDouble("InvisibilityTurns"), ResearchEffect::Duration)'
     in cast and "new CreatureEffectSpellInvisible(turns)" in cast, "Invisibility lasts InvisibilityTurns (Duration)")
effect_cpp = read("source", "creatureeffect", "CreatureEffectSpellInvisible.cpp")
need('const std::string CreatureEffectSpellInvisible::EFFECT_NAME = "SpellInvisible";' in effect_cpp and
     "static CreatureEffectRegister reg(new CreatureEffectSpellInvisibleFactory);" in effect_cpp,
     "the invisibility effect is registered by name, so it is saved and loaded with its time left")
attack = body(creature_cpp, "void Creature::useAttack(")
need(re.search(r"if\(\(entityAttack\.getSeat\(\) != nullptr\) && !entityAttack\.getSeat\(\)->isAlliedSeat\(getSeat\(\)\)\)\s*"
               r"endSpellInvisibility\(\);", attack) is not None, "an attack on an enemy ends the invisibility")
end = body(creature_cpp, "void Creature::endSpellInvisibility(")
need("CreatureEffectSpellInvisible::EFFECT_NAME" in end and '"Invisible"' not in end,
     "only the spell ends, the Shadow Veil skill keeps its rules")
need("effect->mEffect->mNbTurnsEffect = 0.0;" in end, "the effect ends at once")
effect_base = read("source", "creatureeffect", "CreatureEffect.cpp")
need("mNbTurnsEffect = std::max(0.0, mNbTurnsEffect - 1.0);" in effect_base, "the effect runs out with its turns")
invisible = body(creature_cpp, "bool Creature::isInvisible(")
need('"Invisible"' in invisible and "CreatureEffectSpellInvisible::EFFECT_NAME" in invisible,
     "enemy creatures do not target a creature hidden by the skill or the spell")
notify = body(creature_cpp, "void Creature::notifySeatsWithVision(")
need("seat->isAlliedSeat(getSeat())" in notify and "isSpellInvisible()" in notify,
     "only allied seats get a creature hidden by the spell (enemies do not see it)")
for trap in ("TrapCannon", "TrapLightning"):
    need("&Trap::isHiddenBySpell" in read("source", "traps", trap + ".cpp"), "%s aims, it skips hidden creatures" % trap)
need("creature->isInvisible()" in read("source", "traps", "TrapWatchBanner.cpp"), "the watch banner skips hidden creatures")
for trap in ("TrapSpike", "TrapGas", "TrapFireburst", "TrapBoulder"):
    need("isSpellInvisible" not in read("source", "traps", trap + ".cpp") and
         "isHiddenBySpell" not in read("source", "traps", trap + ".cpp"), "%s hits everything on its tiles" % trap)
for enemy_spell in ("SpellCreatureSlow", "SpellCreatureWeak", "SpellLightning", "SpellDefector", "SpellHexenHen",
                    "SpellCreatureExplosion", "SpellCurse", "SpellPlague"):
    need("isSpellInvisible()" in read("source", "spells", enemy_spell + ".cpp"),
         "%s cannot target a creature hidden by the spell" % enemy_spell)
need(creature_cpp.count("os << isSpellInvisible();") == 2 and creature_cpp.count("is >> mSpellInvisible") == 2,
     "both creature packets carry the invisibility for the half transparent look")
need("static const float SPELL_INVISIBLE_OPACITY = 0.5f;" in creature_cpp and
     "rrSetCreatureOpacity(this, mSpellInvisible ? SPELL_INVISIBLE_OPACITY : 1.0f)" in creature_cpp,
     "own keeper and allies see the creature half transparent")

# ---------------------------------------------------------------------------------------------------------------------
# N4 Plague
plague = sources["SpellPlague"]
rule = body(plague, "bool SpellPlague::isValidTarget(")
for needle in ("!creature.isAlive()", "creature.getSeat()->isAlliedSeat(caster)", "!creature.canCatchPlague()",
               "creature.isPlagueSick()", "creature.isSpellInvisible()", "isTileSeenBy(*pos, caster)"):
    need(needle in rule, "Plague target rule lacks %s" % needle)
need("creature->catchPlague(player->getSeat()->getId());" in body(plague, "bool SpellPlague::castSpell("),
     "the cast makes the creature sick with the research of the caster")
catch = body(creature_cpp, "bool Creature::canCatchPlague(")
need("!mDefinition->isWorker()" in catch and "!mDefinition->isChampion()" in catch,
     "workers and the champion never get sick")
upkeep = body(creature_cpp, "void Creature::upkeepPlague(")
infection = upkeep[upkeep.index("// The infection"):upkeep.index("// The damage")]
need("PlagueInfectRadius" in infection and "PlagueInfectChancePerTurn" in infection, "the infection reads its keys")
need("getGameMap()->getCreatures()" in infection and "isAlliedSeat" not in infection and "getSeat()" not in infection,
     "the infection reaches own, allied and enemy creatures alike")
need("Random::Double(0.0, 1.0) < chance" in infection and "creature->catchPlague(mPlagueSeatId)" in infection,
     "every creature in the radius is infected with the chance per turn")
need("!creature->canCatchPlague()" in infection, "workers and the champion are not infected")
damage = upkeep[upkeep.index("// The damage"):]
need("mKoTurnCounter" not in damage, "the plague damage runs every turn until cured or dead, also while knocked out")
need("infirmaryRest" not in infection, "the infection reaches every creature in the radius, a patient on a cot included")
need("if(isActionInList(CreatureActionType::infirmaryRest))\n    {\n        curePlague();\n        return;\n    }" in upkeep,
     "a sick creature on a cot is cured there, as on its admission")
need('config.getSpellConfigDouble("PlagueDamagePerTurn"), ResearchEffect::Damage)' in damage and
     "takeDamage(nullptr, damage, 0.0, 0.0, 0.0, myTile, false);" in damage, "PlagueDamagePerTurn every turn, normal death")
need(upkeep.index("// The damage") > upkeep.index("// The infection"), "the infection runs before the damage")
DAMAGE = [0.5, 0.5, 1.0, 2.0]  # per turn at research level 0 to 3
for level in range(4):
    need(math.isclose(float(spell_values["PlagueDamagePerTurn"]) * factors["spellPlague"][level], DAMAGE[level]),
         "plague damage at level %d" % level)
# A level-1 rat (35.5 HP) dies in about 51 s at 1.4 turns per second
need(round(35.5 / 0.5 / 1.4) == 51, "the plague time of the plan")
admit = body(read("source", "rooms", "RoomInfirmary.cpp"), "bool RoomInfirmary::admit(")
need("creature.curePlague();" in admit and admit.index("payAdmission") < admit.index("creature.curePlague();"),
     "the admission to a cot cures the plague after the fee is paid")
infirmary = read("source", "rooms", "RoomInfirmary.cpp")
sick = body(infirmary, "bool RoomInfirmary::canAdmitSick(")
for needle in ("creature.isPlagueSick()", "!creature.getDefinition()->isWorker()", "!creature.getDefinition()->isChampion()",
               "!creature.isInContainment()", "findCot(creature,false)!=noCot", "canPayAdmission(creature,false)",
               '"Hero"', "isRogueSeat()"):
    need(needle in sick, "canAdmitSick lacks %s" % needle)
need("getHP" not in sick and "getDischargeThreshold" not in sick, "a sick creature is admitted whatever its HP")
need("return admit(findCot(creature,false),creature,false);" in body(infirmary, "bool RoomInfirmary::admitSick("),
     "the fee of a sick creature is paid as for a carried patient")
rest = body(infirmary, "bool RoomInfirmary::restPatient(")
need("creature.getHP()*100.0<creature.getMaxHp()*getDischargeThreshold()" in rest,
     "after the cure the patient leaves at once when its HP is at or above the threshold")
walk = body(creature_cpp, "void Creature::handlePlagueWalk(")
for needle in ("CreatureActionType::fight", "CreatureActionType::fightFriendly", "CreatureActionType::flee",
               "isInContainment()", "isKo()", "CreatureActionSearchInfirmary::findInfirmaryTile(*this)",
               "pushAction(Utils::make_unique<CreatureActionSearchInfirmary>(*this));"):
    need(needle in walk, "the walk of a sick creature lacks %s" % needle)
need("handlePlagueWalk();" in body(creature_cpp, "void Creature::doUpkeep()"), "the walk is decided every turn")
search = read("source", "creatureaction", "CreatureActionSearchInfirmary.cpp")
need("infirmary->canAdmitSick(creature)" in search and "->admitSick(creature)" in search and
     "findBestPath(" in search, "the sick creature walks to the nearest infirmary with a free cot and is admitted")
need("hasCarryEntitySpot" not in search, "KO sick creatures are carried in by the workers as today")
need('const std::string Creature::PLAGUE_SCRIPT = "SpellCreaturePlague";' in creature_cpp, "the plague look script")
if DATA:
    particles = read("particles", "RoomAmbienceSpells.particle")
    look = particles[particles.index("particle_system SpellCreaturePlague"):]
    look = look[:look.index("\n}") + 2]
    colours = [tuple(float(v) for v in m) for m in re.findall(r"colour\w*\s+([\d.]+) ([\d.]+) ([\d.]+)", look)]
    need(colours and all(g > r and g > b for r, g, b in colours), "the plague look is green")
    need("particles/RoomAmbienceSpells.particle (SpellCreaturePlague)" in CREDITS, "CREDITS names the plague look")

# ---------------------------------------------------------------------------------------------------------------------
# N5 Break Wall
wall = sources["SpellBreakWall"]
rule = body(wall, "bool SpellBreakWall::isValidWall(")
for needle in ("tile.getType() != TileType::dirt", "!tile.isFullTile()", "!tile.isClaimed()",
               "!owner->isAlliedSeat(caster)", "TileVisual::claimedFull"):
    need(needle in rule, "Break Wall wall rule lacks %s" % needle)
for refused in ("gold", "gem", "rock", "lava", "water"):
    need("TileType::%s" % refused not in rule, "Break Wall refuses %s by taking earth only" % refused)
cast = body(wall, "bool SpellBreakWall::castSpell(")
need("isTileSeenBy(*tile, player->getSeat())" in cast, "the caster sees the wall")
need("tile->getSeat()->notifyTileClaimedByEnemy(tile);\n    tile->unclaimTile();" in cast,
     "the wall turns back into earth like the walls of Tremor")
tremor = read("source", "spells", "SpellTremor.cpp")
need("tile->unclaimTile();" in tremor, "Tremor unclaims its walls the same way")
PRICES = [3000, 3000, 2700, 2400]
for level in range(4):
    need(round(float(spell_values["BreakWallPrice"]) * factors["spellBreakWall"][level]) == PRICES[level],
         "Break Wall price at level %d" % level)
need("std::lround(SkillManager::getResearchValue(seat, SkillType::spellBreakWall," in wall, "the price follows Price")

# N6 Reveal Enemy
reveal = sources["SpellRevealEnemy"]
claimed = body(reveal, "std::vector<Tile*> SpellRevealEnemy::getClaimedTiles(")
need("gameMap->getMapSizeX()" in claimed and "gameMap->getMapSizeY()" in claimed and
     "tile->isClaimed() && (tile->getSeat() == owner)" in claimed, "every tile claimed by the keeper is revealed")
rule = body(reveal, "bool SpellRevealEnemy::isValidTile(")
need("tile.isClaimed()" in rule and "!owner->isAlliedSeat(caster)" in rule, "the clicked tile is claimed by an enemy")
cast = body(reveal, "bool SpellRevealEnemy::castSpell(")
need("isTileSeenBy(*tile, player->getSeat())" in cast, "the clicked tile is visible to the caster")
need("getClaimedTiles(gameMap, tile->getSeat());" in cast and "player->getSeat()->revealTiles(tiles, revealTurns);" in cast,
     "the claimed tiles of the clicked keeper are shown to the caster")
need('getSpellConfigDouble("RevealEnemyTurns"), ResearchEffect::Duration)' in cast, "RevealEnemyTurns follows Duration")
TURNS = [7, 7, 11, 14]  # rounded half away from zero, as std::lround
for level in range(4):
    turns = float(spell_values["RevealEnemyTurns"]) * factors["spellRevealEnemy"][level]
    need(int(math.floor(turns + 0.5)) == TURNS[level], "reveal turns at level %d" % level)

# ---------------------------------------------------------------------------------------------------------------------
# N7 Research nodes, effects, buttons, icons and tooltips
manager = read("source", "game", "SkillManager.cpp")
NODES = [
    ("spellBlessing", "spellCreatureHeal", "BlessingButton", 2, "blessing", 250),
    ("spellBreakWall", "spellEyeEvil", "BreakWallButton", 2, "breakWall", 250),
    ("spellCurse", "spellCreatureSlow", "CurseButton", 3, "curse", 600),
    ("spellInvisibility", "spellCreatureHaste", "InvisibilityButton", 3, "invisibility", 600),
    ("spellPlague", "spellCreatureWeak", "PlagueButton", 4, "plague", 1500),
    ("spellRevealEnemy", "spellEyeEvil", "RevealEnemyButton", 4, "revealEnemy", 1500),
]
skill_points = config_values(skills_cfg, "Skills")
for skill, parent, button, tier, spell, points in NODES:
    need(("createSkill(mSkills, SkillType::%s, std::vector<SkillType>{SkillType::%s});\n"
          "    def = new SkillDefSpell(TREE_PREFIX_SPELLS, \"%s\", skill, %d, SpellType::%s);") %
         (skill, parent, button, tier, spell) in manager, "research node %s" % skill)
    need(skill_points.get(skill) == str(points), "%s costs %d points" % (skill, points))
    need(re.search(r"^#\s*%s\s+\(int\)" % skill, skills_cfg, re.M) is not None, "skills.cfg documents %s" % skill)
    need('{SkillType::%s, "%s", ResearchBaseSource::spells,' % (skill, EFFECTS[skill][0]) in manager,
         "the tooltip has a base value for %s" % skill)
# Every one of the six spells shows its own painted icon of gui/ODIcons.png, named like its button
ICONS = {"CurseButton": "CurseButton", "BlessingButton": "BlessingButton",
         "InvisibilityButton": "InvisibilityButton", "PlagueButton": "PlagueButton",
         "BreakWallButton": "BreakWallButton", "RevealEnemyButton": "RevealEnemyButton"}
icon_names = [i.get("name") for i in ET.parse(os.path.join(ROOT, "gui", "ODIcons.imageset")).getroot().findall("Image")]
for icon in ICONS.values():
    need(icon_names.count(icon) == 1, "gui/ODIcons.imageset has the icon %s once" % icon)
bar = ET.parse(os.path.join(ROOT, "gui", "WindowTabSpells.layout")).getroot().find("Window")
bar_buttons = [w for w in bar.findall("Window") if w.get("type") == "OD/GameTabButton"]
need(len(bar_buttons) == 24, "the spells tab holds 24 buttons: %d" % len(bar_buttons))
tree = ET.parse(os.path.join(ROOT, "gui", "WindowSkillTree.layout")).getroot()
spells_page = next(w for w in tree.iter("Window") if w.get("name") == "Spells")
for button, icon in ICONS.items():
    node = next((w for w in bar_buttons if w.get("name") == button), None)
    need(node is not None and node.find('Property[@name="NormalImage"]').get("value") == "OpenDungeonsIcons/" + icon,
         "the game bar button %s shows the icon of %s" % (button, icon))
    need(node is not None and node.find('Window[@name="%sProgressBar"]' % button) is not None,
         "the button %s has its cooldown bar" % button)
    research = next((w for w in spells_page.findall("Window") if w.get("name") == button), None)
    need(research is not None and research.get("type") == "OD/ResearchButton" and
         research.find('Property[@name="ButtonImage"]').get("value") == "OpenDungeonsIcons/" + icon,
         "the research node %s shows the icon of %s" % (button, icon))
gui = read("source", "render", "Gui.cpp")
arrange = body(gui, "void Gui::arrangeSpellButtons(")
names = re.findall(r'"(\w+Button)"', arrange)
need(len(names) == 24 and len(set(names)) == 24, "the spells tab arranges 24 buttons: %d" % len(names))
need(sorted(names) == sorted(w.get("name") for w in bar_buttons), "every button of the layout is arranged")
rooms = re.findall(r'"(\w+Button)"', body(gui, "void Gui::arrangeRoomButtons("))
# Two rows of small buttons: 24 spells need the 12 columns the 23 rooms already use at every resolution and UI scale
need(math.ceil(24 / 2.0) == math.ceil(len([n for n in rooms if n != "DestroyRoomButton"]) / 2.0) == 12,
     "the spells tab is no wider than the rooms tab")
cost = body(manager, "std::string getCostText(GameMap* gameMap) const override\n    {\n        if(mSpellType")
for cls, (name, display, cooldown, price, skill, button) in SPELLS.items():
    need('case SpellType::%s: key = "%s"; break;' % (name, price) in cost, "the tooltip shows the price of %s" % display)
need("mSpellType == SpellType::revealEnemy) ?\n            \" mana\"" in cost, "the six spells cost mana per cast")

# ---------------------------------------------------------------------------------------------------------------------
# N8 Sounds and looks: spell source, effect name, sound family
LOOKS = {"SpellCurse": ("Weak", "Curse"), "SpellBlessing": ("Strength", "Boost"), "SpellInvisibility": ("", "Dark"),
         "SpellPlague": ("", "Curse"), "SpellBreakWall": ("Tremor", "TremorImpact"),
         "SpellRevealEnemy": ("", "EyeEvilCast")}
credits = CREDITS
for cls, (effect, family) in LOOKS.items():
    need('"%s", "%s", gameMap, player->getSeat())' % (effect, family) in sources[cls], "%s plays %s" % (cls, family))
    if DATA:
        need("sounds/Spatial/Spells/%s/Fx%s01.ogg" % (family, family) in credits, "the recording %s is credited" % family)
spell_cpp = read("source", "spells", "Spell.cpp")
need("if(effectName.empty())\n            continue;" in body(spell_cpp, "void Spell::fireSpellEffect("),
     "a spell without a look of its own plays only its sound")
if DATA:
    ambience = read("config", "roomAmbienceSpells.cfg")
    for event in ("SpellFxWeak", "SpellFxStrength", "SpellFxTremor"):
        need(re.search(r"Event\s+%s\b" % event, ambience) is not None, "the reused look %s exists" % event)

# ---------------------------------------------------------------------------------------------------------------------
# N9 AI rows and decisions
ai_cfg = read("config", "ai.cfg") if DATA else None
rows = ai_cfg[ai_cfg.index("[RowClasses]"):ai_cfg.index("[/RowClasses]")] if DATA else None
ai_spells = read("source", "ai", "AiSpells.cpp")
ROWS = {"E21": "castCurse", "E22": "castBlessing", "E23": "castInvisibility", "E24": "castPlague",
        "E25": "castBreakWall", "E26": "castRevealEnemy"}
for row, function in ROWS.items():
    if DATA:
        need(re.search(r"^\s*%s\s+complex\s+1\s*$" % row, rows, re.M) is not None, "row %s is complex" % row)
    need("// AI row %s" % row in body(ai_spells, "bool SPELL::%s(" % function), "SPELL::%s carries row %s" % (function, row))
    need('{"%s", "complex", "1"}' % row in read("source", "utils", "ConfigManager.cpp"), "compiled default of %s" % row)
if DATA:
    ai_values = config_values(ai_cfg, "KeeperAI")
    for key, value in (("PlagueMinEnemies", "3"), ("PlagueEnemyRadius", "2"), ("PlagueOwnClearRadius", "3")):
        need(ai_values.get(key) == value, "ai.cfg %s is %s" % (key, value))
need("creature->getLevel() > target->getLevel()" in body(ai_spells, "bool SPELL::castCurse(") and
     "hasMoodEffect(creature, SpellCurse::MOOD_EFFECT_NAME)" in body(ai_spells, "bool SPELL::castCurse("),
     "Curse: the visible enemy of the highest level that is not cursed")
blessing_ai = body(ai_spells, "bool SPELL::castBlessing(")
need("CreatureMoodLevel::Upset" in blessing_ai and "hasMoodEffect(creature, SpellBlessing::MOOD_EFFECT_NAME)" in blessing_ai,
     "Blessing: an own creature Upset or worse that is not blessed")
invisibility_ai = body(ai_spells, "bool SPELL::castInvisibility(")
need("CreatureActionType::flee" in invisibility_ai and 'aiKey("HealBelow")' in invisibility_ai,
     "Invisibility: an own creature that flees with low HP")
plague_ai = body(ai_spells, "bool SPELL::castPlague(")
for key in ("PlagueEnemyRadius", "PlagueOwnClearRadius", "PlagueMinEnemies"):
    need('aiKey("%s")' % key in plague_ai, "Plague reads %s" % key)
wall_ai = body(ai_spells, "bool SPELL::castBreakWall(")
need("WAR::WarState::tunnelDigging" in wall_ai and "SpellBreakWall::isValidWall(*tile, seat)" in wall_ai and
     "ACTS::markDig(ai, dig, true);" in wall_ai, "Break Wall: the enemy wall on the dig path of the tunnel")
reveal_ai = body(ai_spells, "bool SPELL::castRevealEnemy(")
need("knowledge.isKnown(enemyHeart)" in reveal_ai, "Reveal Enemy only for a keeper whose heart was not seen")
plan = body(read("source", "ai", "AiWar.cpp"), "void planAttack(Env& env, bool bypassRest)")
need("SPELL::castRevealEnemy(env.ai, enemy);" in plan and
     plan.index("SPELL::castRevealEnemy(env.ai, enemy);") < plan.index("launch(env, tactic, ready, estimate);"),
     "Reveal Enemy is cast once before the attack starts")
need('mind.onLook("E21", aiKey("LookFactorScan"), std::bind(&SPELL::spellLook, std::ref(ai)));' in ai_spells,
     "the spell rows run on their own look")
actions = read("source", "ai", "AiActions.cpp")
need("spell == SpellType::breakWall" in actions and "spell == SpellType::revealEnemy" in actions,
     "the AI sends the tile spells as tiles")
for cls, (name, display, cooldown, price, skill, button) in SPELLS.items():
    need('case SpellType::%s: return "%s";' % (name, price) in ai_spells, "the AI knows the price of %s" % display)

# ---------------------------------------------------------------------------------------------------------------------
# N10 Saving and loading of every running effect
export = body(creature_cpp, "void Creature::exportToStream(")
need('if(mPlagueSick)\n        os << "\\t[Plague] " << mPlagueSeatId << " [/Plague]";' in export, "the sickness is saved")
load = body(creature_cpp, "bool Creature::importFromStream(")
need('if(appearanceToken == "[Plague]")' in load and "mPlagueSick = true;" in load, "the sickness is loaded")
need('os << " " << effect.mName << " " << effect.mStrength << " " << effect.mTurnsLeft;' in export,
     "curse and blessing are saved with the mood effects")
need("CreatureEffectManager::write(*creatureParticleEffect->mEffect, os);" in export,
     "the invisibility is saved with its time left like every creature effect")
seat = read("source", "game", "Seat.cpp")
seat_export = body(seat, "bool Seat::exportSeatToStream(")
need('os << "[RevealedTiles]\\n" << mRevealedTiles.size() << "\\n";' in seat_export and
     'revealed.first->getX() << "\\t" << revealed.first->getY() << "\\t" << revealed.second' in seat_export,
     "a running reveal is saved with its tiles and turns left")
seat_import = body(seat, "bool Seat::importSeatFromStream(")
need('if(str == "[RevealedTiles]")' in seat_import and "mRevealedTilesLoaded.push_back(" in seat_import,
     "a running reveal is loaded")
need("mRevealedTiles.push_back(std::pair<Tile*, uint32_t>(tile, entry.second));" in body(seat, "void Seat::initSeat("),
     "the loaded reveal goes on with its turns left")
need("for(uint32_t i = 1; i < static_cast<uint32_t>(SpellType::nbSpells); ++i)" in seat_export,
     "the cooldowns of all 24 spells are saved")

if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1)
print("spells review checks passed")
