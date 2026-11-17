"""Static check that the running possession of an AI keeper is saved and loaded completely (no build needed).

Checks against the sources of this branch:
- the possessed creature writes a [Possession] block (seat of the AI keeper, turns of the possession, follow group)
  and every follower a [PossessionGroup] block with the name of its leader; a human keeper's possession is never
  written (a human cannot save while possessing)
- the reader takes both blocks back in the same order; old saves without them load as before
- after loading, the server binds the keeper again before the first upkeep: possessor, possessed name of the player,
  possessed action, aura and the followers that still follow the leader; the turns go on, so the free period and the
  drain continue where they stopped; the AI keeps its saved control timer (row D05)
A saved line is built from the field order of the writer and read back with the field order of the reader: the
values of the fixed example must come back unchanged.
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
game_map = read("source/gamemap/GameMap.cpp")
care = read("source/ai/AiCare.cpp")

check('POSSESSION_SAVE_OPEN = "[Possession]";' in creature and 'POSSESSION_SAVE_CLOSE = "[/Possession]";' in creature,
      "the possession block has no fixed tags")
check('POSSESSION_GROUP_SAVE_OPEN = "[PossessionGroup]";' in creature
      and 'POSSESSION_GROUP_SAVE_CLOSE = "[/PossessionGroup]";' in creature, "the follow group block has no fixed tags")

# ---- the writer
export = creature[creature.index("void Creature::exportToStream(std::ostream& os) const"):]
export = export[:export.index("\n}\n")]
block = export[export.index("os << \"\\t\" << POSSESSION_SAVE_OPEN"):]
block = block[:block.index("os << \" \" << POSSESSION_SAVE_CLOSE;")]
guard = export[:export.index("os << \"\\t\" << POSSESSION_SAVE_OPEN")]
check("(mPossessor != nullptr) && !mPossessor->getIsHuman()" in guard[guard.rindex("if("):],
      "only the possession of an AI keeper is written")
writer_fields = re.findall(r"<< (mPossessor->getSeat\(\)->getId\(\)|mPossessionTurns|mGroupMemberNames\.size\(\)|memberName)",
                           block)
check(writer_fields == ["mPossessor->getSeat()->getId()", "mPossessionTurns", "mGroupMemberNames.size()", "memberName"],
      "the possession block writes %s" % writer_fields)
group = export[export.index("POSSESSION_GROUP_SAVE_OPEN"):]
check("<< mGroupLeaderName <<" in group[:group.index(";")], "a follower must write its leader")
group_guard = export[export.index("if(!mGroupLeaderName.empty())"):export.index("POSSESSION_GROUP_SAVE_OPEN")]
check("!leader->mPossessor->getIsHuman()" in group_guard, "a follower is written only for the leader of an AI keeper")

# ---- the reader
reader = creature[creature.index("bool Creature::importFromStream(std::istream& is)"):]
reader = reader[:reader.index("\n}\n")]
possession = reader[reader.index("if(appearanceToken == POSSESSION_SAVE_OPEN)"):]
possession = possession[:possession.index("continue;")]
check("is >> possessorSeatId >> possessionTurns >> nbMembers" in possession and "is >> memberName" in possession
      and "close != POSSESSION_SAVE_CLOSE" in possession, "the possession block is not read in the written order")
for target in ("mSavedPossessorSeatId = possessorSeatId;", "mPossessionTurns = possessionTurns;",
               "mGroupMemberNames = memberNames;"):
    check(target in possession, "the reader does not keep " + target)
group_reader = reader[reader.index("if(appearanceToken == POSSESSION_GROUP_SAVE_OPEN)"):]
group_reader = group_reader[:group_reader.index("continue;")]
check("is >> leaderName >> close" in group_reader and "mGroupLeaderName = leaderName;" in group_reader,
      "the follower block is not read")
check("int32_t                         mSavedPossessorSeatId = -1;" in header,
      "an old save without the block must keep 'no possession'")

# ---- a fixed example line goes through the writer order and the reader order unchanged
EXAMPLE = {"seat": 3, "turns": 517, "members": ["Grunt12", "Archer4"], "leader": "Wizard7"}
line = "[Possession] %d %d %d %s [/Possession] [PossessionGroup] %s [/PossessionGroup]" % (
    EXAMPLE["seat"], EXAMPLE["turns"], len(EXAMPLE["members"]), " ".join(EXAMPLE["members"]), EXAMPLE["leader"])
tokens = line.split()
loaded = {}
while tokens:
    token = tokens.pop(0)
    if token == "[Possession]":
        loaded["seat"] = int(tokens.pop(0))
        loaded["turns"] = int(tokens.pop(0))
        count = int(tokens.pop(0))
        loaded["members"] = [tokens.pop(0) for _ in range(count)]
        check(tokens.pop(0) == "[/Possession]", "the example possession block does not close")
    elif token == "[PossessionGroup]":
        loaded["leader"] = tokens.pop(0)
        check(tokens.pop(0) == "[/PossessionGroup]", "the example group block does not close")
check(loaded == EXAMPLE, "the example came back as %s" % loaded)

# ---- the restore after loading, before the first upkeep
create = function(game_map, "void GameMap::createAllEntities()")
server_part = create[create.index("for(Creature* creature : mCreatures) creature->restoreGhostHunt();"):]
check("creature->restoreSavedPossession();" in server_part[:server_part.index("}")],
      "the server must restore the saved possessions with the other loaded states")
restore = function(creature, "void Creature::restoreSavedPossession()")
check("player->getIsHuman()" in restore and "(seat != getSeat())" in restore,
      "only an AI keeper of the creature's seat gets its possession back")
check("mSavedPossessorSeatId = -1;" in restore, "the restore must run once")
for needle, message in (("mPossessor = player;", "the possessor"),
                        ("player->setPossessedCreatureName(getName());", "the possessed name of the keeper"),
                        ("pushAction(Utils::make_unique<CreatureActionPossessed>(*this));", "the possessed action"),
                        ("addParticleEffect(POSSESSION_AURA_SCRIPT, -1);", "the aura"),
                        ("member->mGroupLeaderName == getName()", "the follow group")):
    check(needle in restore, "the restore does not give back " + message)
check("mPossessionTurns = 0;" not in restore[restore.index("mPossessor = player;"):],
      "the turns (free period and drain) must go on after loading")
check('lines.push_back({"draw", {"D05", "nextControl", careNumber(mNextControl - now)}});' in care,
      "the AI must keep its saved possession control timer")

print('ODP_TEST_PHASE {"name":"test","seconds":%.3f}' % (time.monotonic() - START))
if problems:
    for problem in problems:
        print("FAIL: " + problem)
    raise SystemExit(1)
print("AI keeper possession saved and restored with turns and follow group: PASS (static only)")
