"""Check catalogue row comments in their owning functions and configuration.

config/ai.cfg lies in the content package core-config; without the content the configuration part is named as not
checked and the code part runs."""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "scripts"))
import content_packages
ANCHORS = {
    "A01": ("source/ai/AiEconomy.cpp", "ECON::digQueueWatch"),
    "A02": ("source/ai/AiEconomy.cpp", "ECON::claimWatch"),
    "A03": ("source/ai/AiEconomy.cpp", "ECON::summonWatch"),
    "A04": ("source/ai/AiEconomy.cpp", "ECON::walletGate"),
    "A05": ("source/ai/AiEconomy.cpp", "ECON::castCreateGold"),
    "A06": ("source/ai/AiEconomy.cpp", "ECON::goldCapacityWatch"),
    "A07": ("source/ai/AiEconomy.cpp", "ECON::manaCapWatch"),
    "A08": ("source/ai/AiEconomy.cpp", "ECON::sellObsolete"),
    "A09": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B01": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B02": ("source/ai/AiRooms.cpp", "ROOMS::bedWatch"),
    "B03": ("source/ai/AiRooms.cpp", "ROOMS::hatcheryWatch"),
    "B04": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B05": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B06": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B07": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B08": ("source/ai/AiRooms.cpp", "ROOMS::auditTavern"),
    "B09": ("source/ai/AiRooms.cpp", "ROOMS::auditCasino"),
    "B10": ("source/ai/AiRooms.cpp", "ROOMS::toiletWatch"),
    "B11": ("source/ai/AiRooms.cpp", "ROOMS::auditMerchant"),
    "B12": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B13": ("source/ai/AiRooms.cpp", "ROOMS::auditLab"),
    "B14": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B15": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B16": ("source/ai/AiRooms.cpp", "ROOMS::auditInfirmary"),
    "B17": ("source/ai/AiRooms.cpp", "ROOMS::ghostProduct"),
    "B18": ("source/ai/AiRooms.cpp", "ROOMS::auditSpa"),
    "B19": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "B20": ("source/ai/AiRooms.cpp", "ROOMS::templeSacrifice"),
    "B21": ("source/ai/AiRooms.cpp", "ROOMS::bridgeWatch"),
    "B22": ("source/ai/AiRooms.cpp", "ROOMS::rebuildLost"),
    "B23": ("source/ai/AiRooms.cpp", "ROOMS::placeRoom"),
    "B24": ("source/ai/AiRooms.cpp", "ROOMS::auditSettings"),
    "C01": ("source/ai/AiResearch.cpp", "RES::chooseResearch"),
    "C02": ("source/ai/AiResearch.cpp", "RES::refillQueue"),
    "C03": ("source/ai/AiResearch.cpp", "RES::chooseResearch"),
    "C04": ("source/ai/AiResearch.cpp", "RES::chooseResearch"),
    "C05": ("source/ai/AiResearch.cpp", "RES::chooseResearch"),
    "C06": ("source/ai/AiResearch.cpp", "RES::chooseResearch"),
    "D01": ("source/ai/AiEconomy.cpp", "ECON::walletGate"),
    "D02": ("source/ai/AiRooms.cpp", "ROOMS::bedWatch"),
    "D03": ("source/ai/AiRooms.cpp", "ROOMS::hatcheryWatch"),
    "D04": ("source/ai/AiCare.cpp", "CARE::slapWatch"),
    "D05": ("source/ai/AiCare.cpp", "CARE::possessDefender"),
    "D06": ("source/ai/AiCare.cpp", "CARE::idleToHall"),
    "D07": ("source/ai/AiCare.cpp", "CARE::moodPatrol"),
    "D08": ("source/ai/AiCare.cpp", "CARE::levelWatch"),
    "D09": ("source/ai/AiCare.cpp", "CARE::moodRelief"),
    "D10": ("source/ai/AiPrison.cpp", "PRIS::tortureStep"),
    "D11": ("source/ai/AiItems.cpp", "ITEMS::classNRows"),
    "E01": ("source/ai/AiEconomy.cpp", "ECON::summonWatch"),
    "E02": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "E03": ("source/ai/AiSpells.cpp", "SPELL::castHaste"),
    "E04": ("source/ai/AiSpells.cpp", "SPELL::castEye"),
    "E05": ("source/ai/AiSpells.cpp", "SPELL::castDefense"),
    "E06": ("source/ai/AiSpells.cpp", "SPELL::castStrength"),
    "E07": ("source/ai/AiSpells.cpp", "SPELL::castCallToWar"),
    "E08": ("source/ai/AiSpells.cpp", "SPELL::castSlow"),
    "E09": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "E10": ("source/ai/AiSpells.cpp", "SPELL::castWeak"),
    "E11": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "E12": ("source/ai/AiCare.cpp", "CARE::possessDefender"),
    "E13": ("source/ai/AiEconomy.cpp", "ECON::castCreateGold"),
    "E14": ("source/ai/AiItems.cpp", "ITEMS::classNRows"),
    "E15": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "E16": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "E17": ("source/ai/AiSpells.cpp", "SPELL::castDefector"),
    "E18": ("source/ai/AiSpells.cpp", "SPELL::castHexenHen"),
    "E19": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "F01": ("source/ai/AiTraps.cpp", "TRAP::trapLook"),
    "F02": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F03": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F04": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F05": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F06": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F07": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F08": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F09": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F10": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F11": ("source/ai/AiTraps.cpp", "TRAP::placeTrap"),
    "F12": ("source/ai/AiTraps.cpp", "TRAP::reloadGate"),
    "F13": ("source/ai/AiTraps.cpp", "TRAP::placeDoor"),
    "F14": ("source/ai/AiTraps.cpp", "TRAP::placeDoor"),
    "F15": ("source/ai/AiTraps.cpp", "TRAP::fortifyTunnel"),
    "G01": ("source/ai/AiRooms.cpp", "ROOMS::buildNext"),
    "G02": ("source/ai/AiPrison.cpp", "PRIS::tortureStep"),
    "G03": ("source/ai/AiItems.cpp", "ITEMS::classNRows"),
    "G04": ("source/ai/AiPrison.cpp", "PRIS::tortureStep"),
    "H01": ("source/ai/AiItems.cpp", "ITEMS::classNRows"),
    "H02": ("source/ai/AiRooms.cpp", "ROOMS::auditLab"),
    "H03": ("source/ai/AiItems.cpp", "ITEMS::useStoredSpecial"),
    "I01": ("source/ai/AiWar.cpp", "WAR::planDig"),
    "I02": ("source/ai/AiKnowledge.cpp", "AiKnowledge::planRoute"),
    "I03": ("source/ai/AiKnowledge.cpp", "AiKnowledge::scout"),
    "I04": ("source/ai/AiKnowledge.cpp", "AiKnowledge::estimateEnemy"),
    "I05": ("source/ai/AiKnowledge.cpp", "AiKnowledge::exploreTunnels"),
    "I06": ("source/ai/AiMind.cpp", "Mind::enqueue"),
    "J01": ("source/ai/AiWar.cpp", "WAR::defend"),
    "J02": ("source/ai/AiWar.cpp", "WAR::defend"),
    "J03": ("source/ai/AiWar.cpp", "WAR::defend"),
    "J04": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "J05": ("source/ai/AiWar.cpp", "WAR::heartGuard"),
    "J06": ("source/ai/AiWar.cpp", "WAR::defend"),
    "J07": ("source/ai/AiWar.cpp", "WAR::planAttack"),
    "J08": ("source/ai/AiWar.cpp", "WAR::restAfterFight"),
    "K01": ("source/ai/AiWar.cpp", "WAR::planAttack"),
    "K02": ("source/ai/AiWar.cpp", "WAR::planAttack"),
    "K03": ("source/ai/AiWar.cpp", "WAR::launch"),
    "K04": ("source/ai/AiWar.cpp", "WAR::launch"),
    "K05": ("source/ai/AiWar.cpp", "WAR::launch"),
    "K06": ("source/ai/AiSpells.cpp", "SPELL::chooseSpell"),
    "K07": ("source/ai/AiWar.cpp", "WAR::assaultStep"),
    "K08": ("source/ai/AiWar.cpp", "WAR::secondWave"),
    "K09": ("source/ai/AiWar.cpp", "WAR::assaultStep"),
    "K10": ("source/ai/AiWar.cpp", "WAR::endAssault"),
    "L01": ("source/ai/AiMind.cpp", "Mind::exec"),
    "L02": ("source/ai/AiMind.cpp", "Mind::rowClassAudit"),
    "L03": ("source/ai/AiKnowledge.cpp", "AiKnowledge::isKnown"),
    "L04": ("source/ai/AiActions.cpp", "ACTS::buildRoom"),
    "E20": ("source/ai/AiSpells.cpp", "SPELL::castChampion"),
    "H04": ("source/ai/AiItems.cpp", "ITEMS::buyForStrongest"),
    # The six spells of the spells review, each decision with its own row
    "E21": ("source/ai/AiSpells.cpp", "SPELL::castCurse"),
    "E22": ("source/ai/AiSpells.cpp", "SPELL::castBlessing"),
    "E23": ("source/ai/AiSpells.cpp", "SPELL::castInvisibility"),
    "E24": ("source/ai/AiSpells.cpp", "SPELL::castPlague"),
    "E25": ("source/ai/AiSpells.cpp", "SPELL::castBreakWall"),
    "E26": ("source/ai/AiSpells.cpp", "SPELL::castRevealEnemy"),
}

# Return a function body, tracking nested braces.
def function_body(text, signature):
    match = re.search(r"\b" + re.escape(signature) + r"\s*\([^;]*?\)\s*(?:const\s*)?\{", text, re.S)
    if not match and "::" in signature:
        # A definition inside "namespace X { ... }" carries the bare name; only a definition line (return type first) counts
        bare = signature.split("::", 1)[1]
        match = re.search(r"^[A-Za-z_][\w:<>,\s\*&]*?\b" + re.escape(bare) + r"\s*\([^;]*?\)\s*(?:const\s*)?\{", text, re.S | re.M)
    assert match, f"missing function {signature}"
    start = match.end() - 1
    depth = 1
    end = start + 1
    while depth and end < len(text):
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    assert depth == 0, f"unclosed function {signature}"
    return text[start:end]

PROBABILITY_KEYS = ['Pi', 'FocusFire', 'MistakeBaseRoutine', 'MistakeBaseRule', 'MistakeBaseComplex', 'MistakeBaseUnfamiliar', 'MistakeBaseRare', 'MistakeMin', 'MistakeMax', 'HealCastChance', 'PoorDefenceShuffleChance', 'RawHitFactor']

# The AI configuration of the content, None when the content is not present.
config_file = content_packages.data_file(repo, "config/ai.cfg")
if config_file is None:
    content_packages.unchecked("check_ai_rows", ["config/ai.cfg probabilities and row classes"])
else:
    config = config_file.read_text(encoding="utf-8")
    seen_probabilities = set()
    for section in ("KeeperAILevels", "KeeperAI"):
        contents = config.split("[" + section + "]", 1)[1].split("[/" + section + "]", 1)[0]
        for line in contents.splitlines():
            fields = line.split("#", 1)[0].split()
            if fields and fields[0] in PROBABILITY_KEYS:
                assert fields[0] not in seen_probabilities, fields[0]
                seen_probabilities.add(fields[0])
                assert len(fields) == (6 if section == "KeeperAILevels" else 2), fields[0]
                assert all(0 < float(value) < 1 for value in fields[1:]), fields[0]
    assert seen_probabilities == set(PROBABILITY_KEYS), "missing probability key"
    row_section = config.split("[RowClasses]", 1)[1].split("[/RowClasses]", 1)[0]
    row_ids = [line.split()[0] for line in row_section.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert len(row_ids) == len(set(row_ids)), "duplicate row class"
    assert set(row_ids) == set(ANCHORS), "row classes differ from catalogue"
for row, (path, signature) in ANCHORS.items():
    text = (repo / path).read_text(encoding="utf-8")
    assert re.search(r"// AI row " + row + r"\b", function_body(text, signature)), f"{row}: missing in {signature}"

# Behaviour of the rows whose row-by-row comparison with the specification found a difference and fixed it.
# Remove C++ comments and keep the code, so a comment cannot satisfy a behaviour assertion.
def code_only(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)

# Return the comment-free body of a function defined in a file, by qualified or bare name.
def body(path, name):
    text = code_only((repo / path).read_text(encoding="utf-8"))
    match = None
    # A definition inside "namespace X { ... }" carries the bare name.
    for candidate in (name, name.split("::")[-1]):
        match = match or re.search(r"^[A-Za-z_][\w:<>,\s\*&]*?(?<![\w:])" + re.escape(candidate) + r"\s*\([^;{]*?\)\s*(?:const\s*)?\{",
                                   text, re.M | re.S)
    assert match, f"missing function {name} in {path}"
    end = match.end()
    depth = 1
    while depth and end < len(text):
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[match.end():end]

ai = "source/ai/"
# A07: the mana-cap spend summons a worker on the worker limit and the price alone (specification 3.7.1); the summon
# factor and income test belong to A03 only.
summon = body(ai + "AiEconomy.cpp", "summonWorker")
assert re.search(r"surplus\s*\?\s*seat->getMana\(\)\s*>=\s*price\s*:[^;]*SummonManaFactor[^;]*SummonIncomeMin", summon), "A07 surplus test"
assert re.search(r"summonWorker\(ai,\s*true\)", body(ai + "AiEconomy.cpp", "ECON::manaCapWatch")), "A07 surplus summon"
assert re.search(r"summonWorker\(ai,\s*false\)", body(ai + "AiEconomy.cpp", "ECON::summonWatch")), "A03 regular summon"
# C01: the research pick draws its mistake from its row class, once per firing.
research = body(ai + "AiResearch.cpp", "RES::chooseResearch")
assert re.search(r'refire\("C01"\);\s*if\(ai\.getMind\(\)\.slip\("C01"\)\)\s*return\s+candidates\[Random::', research), "C01 slip"
assert not re.search(r"MistakeBaseRule|mistakeProbability", research), "C01 own mistake draw"
# B22 (decision 335): rebuilding a lost room draws no mistake of its own.
assert re.search(r"buildNext\(ai\)", body(ai + "AiRooms.cpp", "ROOMS::rebuildLost"))
for path in sorted((repo / "source/ai").glob("*.cpp")):
    assert 'slip("B22")' not in code_only(path.read_text(encoding="utf-8")), f"B22 draw in {path.name}"
# B02/D02 (decision 336): the shortage is the game's bed search finding no place, not the count of placed beds.
beds = body(ai + "AiRooms.cpp", "ROOMS::bedWatch")
assert re.search(r"if\(!bedsExhausted\(ai\)\)\s*return;", beds) and "getNbBeds" not in beds, "B02 bed shortage"
assert beds.index("bedsExhausted") < beds.index('slip("B02")'), "B02 shortage before the draw"
assert re.search(r"getLocationForBed\(creature\)\s*!=\s*nullptr", body(ai + "AiRooms.cpp", "hasBedPlace")), "B02 bed search"
assert re.search(r'getHomeTile\(\)\s*==\s*nullptr\s*&&\s*!hasBedPlace.*BedsSpare', body(ai + "AiRooms.cpp", "bedsExhausted"), re.S)
# D03: the hatchery row also reacts to every creature arrival.
assert re.search(r'onEvent\("B03",\s*\{[^}]*FirstPortalArrival[^}]*CreatureArrived[^}]*NoFood', body(ai + "AiRooms.cpp", "ROOMS::bind")), "D03 trigger"
# D04: the production-slap check runs on its own timer at the poll, slaps fighters only, at most SlapMistakeMaxClicks per episode.
care = ai + "AiCare.cpp"
assert re.search(r"slapCheck\(mAi, mSlap\);\s*slapEpisodeStep\(mAi, mSlap\);", body(care, "CARE::Controller::poll")), "D04 poll"
check = body(care, "CARE::slapCheck")
assert re.search(r"if\(now < state\.nextCheck\)\s*return;", check), "D04 timer"
assert re.search(r'ownFighters\(ai\)\.empty\(\)\s*\|\|\s*!ai\.getMind\(\)\.slip\("D04"\)', check), "D04 fighters"
assert re.search(r'slapsLeft\s*=\s*static_cast<int>\(config\.getAiConfigDouble\("SlapMistakeMaxClicks"\)\)', check), "D04 click cap"
episode = body(care, "CARE::slapEpisodeStep")
assert re.search(r"for\(Creature\* creature : ownFighters\(ai\)\)\s*\{\s*if\(state\.slapsLeft <= 0\)\s*break;\s*ACTS::slap\(ai, creature\);\s*--state\.slapsLeft;", episode), "D04 episode"
assert "slip(" not in body(care, "CARE::slapWatch"), "D04 brawl look draws no episode"
# D05/E12 (owner answer 80): only fighters near the fight place or in the attacked room take part.
assert re.search(r"squaredDistanceTile\(\*tile, \*event\.tile\)\s*<\s*Player::getMinDistEventSquared\(\)", body(care, "CARE::possessDefender"))
assert "isActionInList(CreatureActionType::fight)" not in body(care, "CARE::possessDefender"), "D05 distant fights"
# D08 (owner answer 82): only a creature with an empty action list is without work.
assert re.search(r"destination == nullptr && creature->getActions\(\)\.empty\(\)", body(care, "CARE::levelWatch")), "D08 idle"
# H03 (owner answer 110): the kill gift never targets a creature held in a hand.
kill_gift = code_only((repo / "source/giftboxes/GiftBoxBonus.cpp").read_text(encoding="utf-8"))
# The last switch of the file applies the effect; its kill case chooses the victim.
kill_gift = kill_gift.rsplit("case GiftBoxType::killCreatures", 1)[1].split("case GiftBoxType::", 1)[0]
assert re.search(r"if\(!creature->isAlive\(\) \|\| !creature->getIsOnMap\(\)", kill_gift), "H03 held victim"
# H04 (owner answers 92 and 94): the gift waits in the hand while the recipient shares its tile or an arena fight runs.
hand_over = body(ai + "AiItems.cpp", "canHandOver")
assert re.search(r"entity != recipient && entity->getObjectType\(\) == GameEntityType::creature && entity->getSeat\(\) == seat\)\s*return false;", hand_over)
assert re.search(r"hasRunningFight\(\)", hand_over) and re.search(r"isClaimedForSeat\(seat\)", hand_over), "H04 hand-over"
actions = code_only((repo / ai / "AiActions.cpp").read_text(encoding="utf-8"))
drop_item = actions.split('action == "dropItem"', 1)[1].split('action == "drop"', 1)[0]
assert re.search(r"if\(!ITEMS::canHandOver\(ai, fighter\)\)\s*\{\s*ITEMS::holdGift\(", drop_item), "H04 hold"
assert drop_item.index("canHandOver") < drop_item.index("dropHand("), "H04 hold before the drop"
assert "ITEMS::retryGift(mAi);" in body(care, "CARE::Controller::poll"), "H04 retry"
# Reaction kinds per row (owner answers 107 and 108, decision 354): each row reacts after its own kind of delay.
mind = body(ai + "AiMind.cpp", "rowKind")
for event, rows, kind in (("CreatureMood", ("D07", "D09"), "symptom"), ("NoBed", ("D06",), "alert"),
                          ("NoFood", ("D06",), "alert"), ("FightOver", ("J08", "G01"), "alert")):
    clause = re.search(r"if\(([^{};]*AiEventType::" + event + r"[^{};]*)\)\s*return AiMath::ReactionKind::(\w+);", mind)
    assert clause and clause.group(2) == kind and all('"' + r + '"' in clause.group(1) for r in rows), f"{event} row kind"
enqueue = body(ai + "AiMind.cpp", "Mind::enqueue")
assert re.search(r"rowKind\(event\.type, entry\.first, kind\)", enqueue) and "copy.rowId = entry.first;" in enqueue, "per-row reaction"
assert re.search(r'reaction\.rowId == "-"\s*\?\s*rowKind\(event\.type, entry\.first, reaction\.kind\) == reaction\.kind',
                 body(ai + "AiMind.cpp", "Mind::doTurn")), "shared reaction skips own-kind rows"
# E15 (decision 334): Tremor needs no minimum group.
spells = body(ai + "AiSpells.cpp", "SPELL::chooseSpell")
assert "TremorMinTargets" not in spells, "E15 minimum group"
# E19 (decision 332), with J04, K06, E02, E09, E11: a mistaken spell goes to the least useful valid target, never to an own fighter.
assert re.search(r'bool\s+slipped\s*=\s*ai\.getMind\(\)\.slip\("E19"\)', spells), "E19 draw"
assert re.search(r"if\(slipped\)\s*\{.*?wastedAreaTile\(ai, chosen\).*?wastedCreatureTarget\(ai, chosen, enemies\)", spells, re.S), "E19 waste"
assert not re.search(r"anyOf\(\s*ownFighters", spells), "E19 own fighter as waste target"
assert re.search(r"creaturesAround\(enemies, tile, radius\) == 0", body(ai + "AiSpells.cpp", "wastedAreaTile")), "E19 area waste"
# F01: traps start after TrapPlanMinRooms built room plan entries, and the plan counts the basic traps only.
traps = ai + "AiTraps.cpp"
trap_look = body(traps, "TRAP::trapLook")
assert re.search(r'builtPlanEntries\(ai\)\)\s*<\s*aiKey\("TrapPlanMinRooms"\)', trap_look), "F01 room plan entries"
assert re.search(r"if\(isBasicTrap\(trap->getType\(\)\)\)\s*trapTiles\s*\+=", trap_look), "F01 basic traps"
# F07 (decision 352), F08 (decision 329), F11 (decision 337), F15: placement fixes.
place = body(traps, "TRAP::placeTrap")
assert "RoomType::treasury" in place and "nearestEntrance(entrances, treasuries" not in place, "F07 treasury door"
assert re.search(r'slip\("F08"\)\s*\?\s*farHalfEntrance\(entrances, heart\)\s*:\s*nearestEntrance\(entrances, heart, false\)', place), "F08 far half"
assert re.search(r"effectReach\(target->getType\(\)\)", code_only((repo / traps).read_text(encoding="utf-8"))), "F11 effect reach"
# F02 mistake, F04, F09 (coordinator 2026-11-17): a tile outside the door is never own ground, so no trap spot lies on the
# outer part of an entrance line; gas and the spike mistake take the first free own tile behind the door, the alarm the
# farthest free own tile up to AlarmDistanceTiles behind it.
assert not re.search(r"lineTile\(gameMap, entrance, (?:-|slipped\s*\?\s*-)", place), "trap spot outside the door"
assert re.search(r'int first = slipped \? 1 : spikeFirst \+ index;', place), "F02 mistake behind the door"
gas_branch = place.split('slip("F04")', 1)[1].split("buildOne(", 1)[0]
assert re.search(r"for\(int k = 1; \(spot == nullptr\) && \(k <= lineEnd\); \+\+k\)\s*\{\s*Tile\* tile = lineTile\(gameMap, entrance, k\);", gas_branch), "F04 gas behind the door"
alarm = place.split('if(SkillManager::isTrapAvailable(TrapType::alarm, seat))', 1)[1].split('slip("F09")', 1)[0]
assert re.search(r'for\(int k = static_cast<int>\(aiKey\("AlarmDistanceTiles"\)\); k >= 1; --k\)', alarm), "F09 farthest own tile"
assert re.search(r"lineTile\(gameMap, entrance, k\)", alarm), "F09 on the entrance line"
# A basic tile without a free spot never stalls the plan: the special traps of F05-F11 are reached after it.
basic = place.split("if(trapTiles < want)", 1)[1].split("Tile* heart = heartTile(ai);", 1)[0]
assert re.search(r"if\(spot != nullptr\)\s*return buildOne\(ai, kind, spot\);\s*\}\s*$", basic.rstrip()), "basic mix falls through"
assert not re.search(r"isTrapAvailable\(kind, seat\)\)\s*return false;", basic), "unresearched basic kind stalls the plan"
assert re.search(r"TrapDoor::canDoorBeOnTile\(&gameMap, tunnel\)", body(traps, "TRAP::findEntrances")), "F15 own tunnel entrance"
# I01, K01 (decision 353): the target is the nearest known enemy tile, never a wild seat and never an unseen heart.
knowledge = code_only((repo / ai / "AiKnowledge.cpp").read_text(encoding="utf-8"))
knowledge = knowledge.split("AiKnowledge::nearestKnownEnemyTile(const SightingState& sighting, int& ownerSeatId)", 1)[1]
assert re.search(r"owner->isAlliedSeat\(mSeat\) \|\| owner->isRogueSeat\(\)", knowledge), "I01 wild seat tiles"
assert re.search(r"recordSeat->isRogueSeat\(\)\)\s*continue;", knowledge), "I01 wild seat sightings"
war = ai + "AiWar.cpp"
enemy = body(war, "enemySeat")
assert "nearestKnownEnemyTile(" in enemy and "RoomType::dungeonTemple" not in enemy, "K01 known target"
# I04, K08 (decisions 357 and 358): the enemy trap state is the last one the seat saw.
assert re.search(r"WAR::seenTrapExhausted\(war, seat, trap, tile\)", body(ai + "AiEvents.cpp", "AiEvents::pollWar")), "K08 seen state"
assert "isTileExhausted" not in body(ai + "AiEvents.cpp", "AiEvents::pollWar"), "K08 true state"
# J08: the defence banner ends with its lifetime, not with a slap.
rest = body(war, "WAR::restAfterFight")
assert "removeBanner" not in rest and "defenceBanner = nullptr;" in rest, "J08 banner"
# K05: one Launch event, after the last drop.
assert len(re.findall(r"AiEventType::Launch\b", body(war, "launch"))) == 0, "K05 early launch"
assert len(re.findall(r"AiEventType::Launch\b", body(war, "launchDropsDone"))) == 1, "K05 launch after drops"
print("OK")
