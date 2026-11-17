"""Static check of a possessed worker's work, its gold and the skills of a possessed creature (no build needed).

Checks against the sources of this branch:
- the left mouse button attacks an enemy the creature can attack in front of it and waits while that attack is not
  ready; with no such enemy a worker works (digging, claiming the wall in front, claiming the floor, in this order)
- a dig step of a possessed worker digs the tile in front whether it is marked or not, with the rate, critical roll,
  gold and experience of the dig action, one work step per turn
- the gold: every turn of a possession the worker stores what it carries on an own treasury or heart ring tile and
  picks up the gold lying on its tile up to its normal capacity; dug gold above the capacity falls to the floor
- no skill fires by itself while possessed: the possessed branch of the upkeep returns before the support skills and
  the fights, so a skill is used only by its key or the left mouse button
The expected values are fixed: the order of the three work steps, the 45 degree front (cosine 0.7) and the one step
per turn.
"""
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[2]
START = time.monotonic()


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def function(source, signature):
    """Return the source of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


creature = read("source/entities/Creature.cpp")
header = read("source/entities/Creature.h")
possessed_action = read("source/creatureaction/CreatureActionPossessed.cpp")

# ---- the left mouse button: attack as today when an attackable enemy is in front, else the work of a worker
attack = function(creature, "void Creature::possessedAttack(const Ogre::Vector2& aim)")
check("enemyInFront = true;" in attack, "possessedAttack does not remember an enemy in front")
check(attack.index("possessedFindTarget(aim, skillData, entity, tile)") < attack.index("enemyInFront = true;")
      < attack.index("isPossessedSkillReady(*this, skillData)"),
      "an enemy in front must count even while the attack is not ready")
check(attack.index("useAttack(*bestSkill, *bestEntity, *bestTile, false, true);") < attack.index("if(enemyInFront)")
      < attack.index("possessedWork(aim);"), "the work must come only without an attack and without an enemy in front")
check(attack.count("possessedWork(") == 1, "possessedAttack must call the work once")

# ---- the work: one step per turn, in the order of the possession rules
work = function(creature, "bool Creature::possessedWork(const Ogre::Vector2& aim)")
check("if(!mDefinition->isWorker())" in work, "only a worker works")
check("if(turn == mPossessionWorkTurn)" in work and work.count("mPossessionWorkTurn = turn;") == 3,
      "one work step per turn (dig, wall claim and floor claim each set the turn)")
check("int64_t                         mPossessionWorkTurn = -1;" in header, "mPossessionWorkTurn is not declared")
dig = work.index("tileFront->isDiggable(getSeat())")
wall = work.index("myTile->isClaimedForSeat(getSeat()) && tileFront->isWallClaimable(getSeat())")
floor = work.index("myTile->isGroundClaimable(getSeat())")
check(dig < wall < floor, "the work order must be: dig the tile in front, claim the wall in front, claim the floor")
check("tileFront->isFullTile()" in work[:dig], "only a wall in front is dug or claimed")
check("getMarkedForDigging" not in work, "a possessed worker digs a tile whether it is marked or not")
check("possessedDigStep(*tileFront)" in work[dig:wall], "the dig step is not used")
check("dropExcessGold();" in work[dig:wall], "gold dug above the capacity must fall to the floor")
check("tileFront->claimForSeat(getSeat(), getClaimRate());" in work[wall:floor], "the wall in front is not claimed")
check("myTile->claimForSeat(getSeat(), getClaimRate());" in work[floor:], "the floor is not claimed")
check(work.count("CreatureActionClaimGroundTile::getClaimExperience(*this)") == 2,
      "claiming gives the experience of a claim step")

front = function(creature, "Tile* getPossessedTileInFront(Tile& myTile, const Ogre::Vector2& aimDir)")
check("const Ogre::Real POSSESSION_WORK_FRONT_MIN_COS = 0.7f;" in creature, "the front is 45 degrees to each side")
check("myTile.getAllNeighbors()" in front and "cosAngle < bestCos" in front, "the tile in front is the best neighbour")

# ---- the dig step: the same rules as a dig step of the dig action
step = function(creature, "double Creature::possessedDigStep(Tile& tileDig)")
check(step.count("rollCritical()") == 1, "one critical roll per dig step")
check("tileDig.digOutGold(digFactor * criticalFactor)" in step, "gold walls are mined by gold per step")
check("tileDig.digOut(getDigRate() * digFactor * criticalFactor)" in step, "other walls are dug by the dig rate")
check("addGoldCarriedFraction(gold)" in step and "addGoldMined(wholeGold)" in step
      and "observeGoldMined(" in step, "dug gold goes to the worker, the statistics and the level script")
check("getGemGoldPerDigStep()" in step, "a gem wall pays the gem gold per step")
check(re.search(r"receiveExp\(config\.getDigXpFactor\(\) \* getDigRate\(\) / config\.getWorkXpRateDivisor\(\)\)", step),
      "the dig experience is not the one of the dig action")
check("receiveExp(config.getTileDugXp());" in step, "a dug out tile gives its experience")
check("fireCreatureSound(CreatureSound::Dig);" in step, "the dig sound is missing")
check("getMaxGoldCarryable()" not in creature.replace("const int32_t baseCapacity = mDefinition->getMaxGoldCarryable();", ""),
      "only getGoldCapacity reads the definition capacity")

# ---- the gold of a possessed worker
gold = function(creature, "void Creature::possessedHandleGold()")
check("!mDefinition->isWorker()" in gold, "only a possessed worker handles gold")
store = gold.index("room->depositGold(mGoldCarried, myTile)")
pick = gold.index("pile->stealGold(*this, capacity - mGoldCarried)")
check(store < pick, "the gold is stored before new gold is picked up")
check("(room->getSeat() == getSeat())" in gold[:store], "gold is stored only in an own room")
check("addGoldCarried(-deposited);" in gold, "stored gold is not taken from the worker")
check("static_cast<double>(getGoldCapacity())" in gold, "the limit is the normal gold capacity")
check("if(mGoldCarried >= capacity)" in gold and gold.count("mGoldCarried >= capacity") == 2,
      "a full worker picks up no more gold")
check("GameEntityType::treasuryObject" in gold, "only gold piles are picked up")
handle = function(possessed_action, "bool CreatureActionPossessed::handlePossessed(Creature& creature)")
check(handle.index("creature.endPossession();") < handle.index("creature.possessedHandleGold();")
      < handle.index("isFreePossession()"), "the gold is handled every turn, also in the free period")

# ---- no skill fires by itself while possessed
upkeep = creature[creature.index("void Creature::doUpkeep()"):]
upkeep = upkeep[:upkeep.index("\n}\n")]
branch_start = upkeep.index("if(isPossessed())\n    {")
branch = upkeep[branch_start:upkeep.index("possessedFunc();", branch_start)]
check("tryUseSupport" not in branch and "useAttack" not in branch, "the possessed branch must not use a skill")
check(upkeep.index("possessedFunc();", branch_start) < upkeep.index("// We use creature skills if we can"),
      "the possessed branch must come before the support skills")
check("return;" in upkeep[upkeep.index("possessedFunc();", branch_start):upkeep.index("// We use creature skills if we can")],
      "the possessed branch must return before the support skills and the fights")
use_skill = function(creature, "void Creature::possessedUseSkill(uint32_t slot, const Ogre::Vector2& aim)")
check("if(isPossessedBasicAttack(*skillData.mSkill))" in use_skill and "if(index != slot)" in use_skill,
      "the skill keys must count the usable skills other than the basic attack in the skill order")

print('ODP_TEST_PHASE {"name":"test","seconds":%.3f}' % (time.monotonic() - START))
if problems:
    for problem in problems:
        print("FAIL: " + problem)
    raise SystemExit(1)
print("Possessed worker work, gold limit and no automatic skills: PASS (static only)")
