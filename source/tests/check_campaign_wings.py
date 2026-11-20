"""Static checks of the campaign structure of Moreya; compiles nothing and never starts a game.

Campaign.cfg lists exactly 18 story levels (6 wings x 3) in the fixed order and one bonus level
per wing; the Heartstone has 3 shards in level 2 of wings 1 to 3; Summon champion comes from wing 4
with all shards; the first completion of a bonus level unlocks 1 Epic, 1 Rare and 1 Common item that
the merchant of every later level sells once; every level starts fresh. The runtime rules themselves
are covered by the Boost test 00-Campaign (test_Campaign.cpp); this check pins the data and the wiring.

Campaign texts: every entry has a title, a briefing and a debriefing; no title names an old province or
trial; every story briefing names its guild, leader, origin and raid size and its Warden key names the
leader; bonus briefings and debriefings name the item unlock and no raid; no campaign text and no
scripted message of the 24 levels calls the Ziv a worker or names a removed warden, wave, wagon,
kept minion, Heartstone fragment or reputation.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]

# Fixed expected structure: (file, wing, title, bonus, shard); Summon champion in wings 4 to 6, every bonus level
# unlocks one Epic, one Rare and one Common item
EXPECTED = (
    ("campaign/Brackenford.level", "1", "Mold Pit", False, False),
    ("campaign/Coldwell.level", "1", "Drowned Larder", False, True),
    ("campaign/Ravensledge.level", "1", "Rat Warren", False, False),
    ("campaign/Mossgate.level", "1", "The Forgotten Pit", True, False),
    ("campaign/Tinmoor.level", "2", "Bleeding Seam", False, False),
    ("campaign/Greywater.level", "2", "Chain Gallery", False, True),
    ("campaign/Highcairn.level", "2", "Slag Pit", False, False),
    ("campaign/CrowshotGallery.level", "2", "The Gallery of Crows", True, False),
    ("campaign/Lanternhill.level", "3", "Ossuary", False, False),
    ("campaign/Saltmere.level", "3", "Tomb of Whispers", False, True),
    ("campaign/HollinFen.level", "3", "Bone Chapel", False, False),
    ("campaign/SkittleCavern.level", "3", "The Skull Lanes", True, False),
    ("campaign/Cinderhollow.level", "4", "Rack Hall", False, False),
    ("campaign/Ashcombe.level", "4", "Iron Maw", False, False),
    ("campaign/Ironbridge.level", "4", "Torment Cells", False, False),
    ("campaign/SwarmNight.level", "4", "The Swarming Dark", True, False),
    ("campaign/Bellwick.level", "5", "Charnel Stair", False, False),
    ("campaign/Goldspire.level", "5", "Corpse Gate", False, False),
    ("campaign/Kingsfall.level", "5", "Hall of Skulls", False, False),
    ("campaign/BoulderCourse.level", "5", "The Rolling Tomb", True, False),
    ("campaign/VarnsCrossing.level", "6", "Ember Pit", False, False),
    ("campaign/Wraithwood.level", "6", "Throne of Ash", False, False),
    ("campaign/HollowmarkCitadel.level", "6", "Heart of Moreya", False, False),
    ("campaign/TwistingHalls.level", "6", "The Twisting Abyss", True, False),
)
STORY_LEVELS = 18
BONUS_LEVELS = 6
SHARDS = 3
CHAMPION_WINGS = ("4", "5", "6")
UNLOCK = "Epic Rare Common"
DROPPED = ("Dunmarrow", "Mirewatch", "Wolfscar", "Thornreach", "Stormhaven", "Silverdeep", "Ebonrook")
# Fixed raid of every story level: (file, Warden key, leaders, guild, origin, raid size) as the briefing names them
RAIDS = (
    ("campaign/Brackenford.level", "Elsa Brack", ("Elsa Brack",), "Mud Fists", "Brackenford", "one group of five"),
    ("campaign/Coldwell.level", "Hugo Cole", ("Hugo Cole",), "Iron Latch", "Coldwell", "one group of five"),
    ("campaign/Ravensledge.level", "Rolf Scarrow", ("Rolf Scarrow",), "Grey Fang", "Wolfscar", "one raid of ten"),
    ("campaign/Tinmoor.level", "Merrin Tay", ("Merrin Tay",), "Deep Picks", "Tinmoor", "two groups of five"),
    ("campaign/Greywater.level", "Corwin Gray", ("Corwin Gray",), "Drowned Oath", "Greywater", "two groups of five"),
    ("campaign/Highcairn.level", "Hilde Cairn", ("Hilde Cairn",), "Stone Crown", "Highcairn", "two raids of ten"),
    ("campaign/Lanternhill.level", "Ines Vale", ("Ines Vale",), "Pale Flame", "Lanternhill", "one group of ten"),
    ("campaign/Saltmere.level", "Bram Seward", ("Bram Seward",), "Salt Wolves", "Saltmere", "one group of ten"),
    ("campaign/HollinFen.level", "Agathe Hollin", ("Agathe Hollin",), "Order of the White Thorn", "Hollin Fen",
     "one raid of twenty-five"),
    ("campaign/Cinderhollow.level", "Pell Ashgrove", ("Pell Ashgrove",), "Ember Ram", "Cinderhollow", "two groups of ten"),
    ("campaign/Ashcombe.level", "Liesl Ashby", ("Liesl Ashby",), "Burnt Wheel", "Ashcombe", "two groups of ten"),
    ("campaign/Ironbridge.level", "Gareth Fenn", ("Gareth Fenn",), "Anvil Host", "Ironbridge", "two raids of twenty-five"),
    ("campaign/Bellwick.level", "Lorens Bell", ("Lorens Bell",), "Silent Bell", "Bellwick", "one group of twenty-five"),
    ("campaign/Goldspire.level", "Alaric Penn", ("Alaric Penn",), "Gilded Hand", "Goldspire", "one group of twenty-five"),
    ("campaign/Kingsfall.level", "Prince Aurel", ("Prince Aurel",), "Sun Court", "Kingsfall", "one raid of forty"),
    ("campaign/VarnsCrossing.level", "Marshal Varn", ("Marshal Varn",), "Black Legion", "Varn's Crossing",
     "two groups of twenty-five"),
    ("campaign/Wraithwood.level", "Elowen Ash", ("Elowen Ash",), "Ash Coven", "Wraithwood", "two groups of twenty-five"),
    ("campaign/HollowmarkCitadel.level", "Sabine Rook and High King Castellan", ("Sabine Rook", "High King Castellan"),
     "Crown Eternal", "Hollowmark Citadel", "two raids of forty"),
)
# Names of the old provinces and trials that no level title may carry any more
OLD_TITLE_NAMES = ("Brackenford", "Coldwell", "Ravensledge", "Mossgate", "Tinmoor", "Greywater", "Highcairn", "Lanternhill",
                   "Saltmere", "Hollin Fen", "HollinFen", "Cinderhollow", "Ashcombe", "Ironbridge", "Bellwick", "Goldspire",
                   "Kingsfall", "Varn's Crossing", "VarnsCrossing", "Wraithwood", "Hollowmark", "Dunmarrow", "Mirewatch",
                   "Wolfscar", "Thornreach", "Stormhaven", "Silverdeep", "Ebonrook", "Crowshot Gallery", "Skittle Cavern",
                   "Swarm Night", "Boulder Course", "Twisting Halls")
# Words that no campaign text and no scripted message may use any more: the worker is a Ziv; wardens, waves,
# wagons, the kept minion, Heartstone fragments and reputation are gone from the campaign
WORKER_WORD = re.compile(r"\bworkers?\b", re.I)
REMOVED_WORDS = re.compile(r"\b(wardens?|waves?|wagons?|fragments?|reputation|keepminion|reeve|Osric|Tobin)\b", re.I)
BONUS_UNLOCK_TEXT = "one Epic, one Rare and one Common item"

failures = []


def check(condition, message):
    """Collects a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(path):
    """Reads a repository file as text."""
    return (ROOT / path).read_text(encoding="utf-8")


def body(source, signature):
    """Extracts a complete brace-delimited function starting at its signature."""
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


definition = read("levels/campaign/Campaign.cfg").replace("\r", "")
# Comment lines may name the section markers; only the setting lines count
settings_text = "\n".join(line for line in definition.split("\n") if not line.startswith("#"))
check(not settings_text.split("[Level]", 1)[0].strip(), "Campaign.cfg has settings outside of the [Level] entries")
entries = [dict(re.findall(r"^(\w+)=(.*)$", block, re.M)) for block in settings_text.split("[Level]")[1:]]

# CS1: 18 story levels in the order of the structure table and one bonus level per wing
check(len(entries) == len(EXPECTED), "Campaign.cfg must list %d levels, found %d" % (len(EXPECTED), len(entries)))
check(sum(1 for e in entries if e.get("Bonus") != "1") == STORY_LEVELS, "there must be 18 story levels")
check(sum(1 for e in entries if e.get("Bonus") == "1") == BONUS_LEVELS, "there must be 6 bonus levels")
for index, (file, wing, title, bonus, shard) in enumerate(EXPECTED):
    if index >= len(entries):
        break
    entry = entries[index]
    check(entry.get("File") == file, "level %d must be %s, found %s" % (index, file, entry.get("File")))
    check(entry.get("Wing") == wing, file + " must belong to wing " + wing)
    check(entry.get("Title") == title, file + " must be titled " + title)
    check((entry.get("Bonus") == "1") == bonus, file + (" must" if bonus else " must not") + " be a bonus level")
    check((entry.get("Shard") == "1") == shard, file + (" must" if shard else " must not") + " hide a shard")
    champion = wing in CHAMPION_WINGS
    check((entry.get("Champion") == "1") == champion, file + (" must" if champion else " must not") + " offer Summon champion")
    check(entry.get("Unlock") == (UNLOCK if bonus else None), file + (" must unlock " + UNLOCK if bonus else " must unlock nothing"))
    check((ROOT / "levels" / file).is_file(), file + " is missing")
    for key in ("Briefing", "Debriefing", "Preview"):
        check(bool(entry.get(key)), file + " has no " + key)
    for key in ("Province", "Branch", "Heartstone"):
        check(key not in entry, file + " must not have the former key " + key)
for wing in "123456":
    story = [e for e in entries if e.get("Wing") == wing and e.get("Bonus") != "1"]
    bonus = [e for e in entries if e.get("Wing") == wing and e.get("Bonus") == "1"]
    check(len(story) == 3 and len(bonus) == 1, "wing " + wing + " needs 3 story levels and 1 bonus level")

# MAP6: the dropped maps are no longer listed, their files stay
for name in DROPPED:
    check("campaign/" + name + ".level" not in [e.get("File") for e in entries], name + " must be dropped")
    check((ROOT / "levels/campaign" / (name + ".level")).is_file(), name + ".level must stay in the repository")

# CS3, CS6: the champion and unlock keys are documented in the file
for key in ("Wing", "Bonus", "Shard", "Champion", "Unlock"):
    check(re.search(r"^# " + key + " ", definition, re.M) is not None, key + " needs a documentation line")
check(sum(1 for e in entries if e.get("Shard") == "1") == SHARDS, "the Heartstone needs 3 shards")

# Loader and progression: wings, shards, settings; no provinces, branches or bonus Heartstone pieces
campaign = read("source/game/Campaign.cpp")
header = read("source/game/Campaign.h")
for key in ('key == "Wing"', 'key == "Shard"', 'key == "Champion"', 'key == "Unlock"'):
    check(key in campaign, "the loader must read " + key)
for key in ('key == "Province"', 'key == "Branch"', 'key == "Heartstone"'):
    check(key not in campaign, "the loader must not read " + key)
loader = body(campaign, "bool Campaign::importDefinition(")
check("if(entry.mBonus)\n            entry.mShard = false;\n        else\n            entry.mUnlockQualities.clear();" in loader,
      "bonus levels must never carry a shard and story levels never unlock items")

# CS2: every level starts fresh; nothing is carried over
check("KeptMinion" not in campaign and "mKept" not in header and "mKept" not in campaign,
      "the kept minion must be gone from the campaign")
server = read("source/network/ODServer.cpp")
check("spawnKeptMinion" not in server, "no creature may come along to the next level")

# CS3: shards and the champion wing
shard = body(campaign, "bool Campaign::findShard(")
check("!mLevels[mPlayedLevel].mShard || mShardFound[mPlayedLevel]" in shard and "saveProgress();" in shard,
      "a shard counts once in its own level and is saved")
champion = body(campaign, "bool Campaign::isChampionAvailableNoLock(")
check("getHeartstonePiecesNoLock() != total" in champion and "return mLevels[index].mChampion;" in champion,
      "Summon champion needs all shards and a level with Champion=1")
script_header = read("source/gamemap/LevelScript.h")
check("Action  shard " in script_header and "Heartstone shard brought home" in script_header,
      "the shard action and its recipe must be documented in LevelScript.h")

# CS4, CS5: discovery in the first story level of the wing; bonus levels have no raid
discover = body(campaign, "bool Campaign::discoverBonusLevel(")
check("findFirstStoryLevelOfWingNoLock(wing) != mPlayedLevel" in discover,
      "a bonus level is found only in the first story level of its wing")
check("bool isPlayedLevelBonus() const;" in header and "Bonus levels have no raid." in header,
      "the raid hook for bonus levels must exist")

# CS6: only the first completion of a bonus level unlocks, from the catalogue, never twice at one quality
won = body(campaign, "bool Campaign::completePlayedLevel(")
check("bool firstBonusCompletion = played.mBonus && !mCompleted[mPlayedLevel];" in won,
      "only the first completion of a bonus level unlocks")
check("!isItemUnlockedNoLock(quality, itemId)" in won, "an item line is unlocked once per quality")
check("for(const std::string& quality : played.mUnlockQualities)" in won, "the bonus level's Unlock qualities count")
game_map = read("source/gamemap/GameMap.cpp")
victory = body(game_map, "void GameMap::addWinningSeat(")
check("onLevelWon(campaignUnlockCandidates(*this), &drawCampaignUnlock)" in victory,
      "the victory draws the unlocked items from the item catalogue")
candidates = body(game_map, "std::map<std::string, std::vector<std::string> > campaignUnlockCandidates(")
check("getItemDefinitions()" in candidates and "Quality::common, Quality::rare, Quality::epic" in candidates,
      "candidates are the Common, Rare and Epic lines of config/items.cfg")

# CS7: the merchant of every later level sells each unlocked item once; the queue starts fresh with every map
queue = server.index("unlockedItems = Campaign::getSingleton().getUnlockedItems();")
check("if(mServerMode != ServerMode::ModeGameLoaded)" in server[queue - 120:queue],
      "unlocked items are queued only when a level starts fresh")
check("gameMap->addCampaignMerchantGood(seat->getId(), quality, unlocked.mItemId);" in server,
      "each unlocked item is queued for the human keeper's merchant")
stock = body(game_map, "void GameMap::stockCampaignMerchantGoods(")
check("room.addGoods(item, table)" in stock and "it = mCampaignMerchantGoods.erase(it);" in stock,
      "a sold-in item leaves the queue, so it is offered once per map")
check(stock.index("room.addGoods(item, table)") < stock.rindex("it = mCampaignMerchantGoods.erase(it);"),
      "the item leaves the queue only after it was put on a table")
check("isEpicRegistered(it->mItemId)" in stock, "an Epic stays unique in the map")
check("mCampaignMerchantGoods.clear();" in body(game_map, "void GameMap::clearItemDefinitions("),
      "a new map starts with an empty merchant queue")
check("getGameMap()->stockCampaignMerchantGoods(*this);" in body(read("source/rooms/RoomMerchant.cpp"),
      "void RoomMerchant::doUpkeep("), "the merchant takes the waiting items on its upkeep")

# CS8: progress and saves keep shards, discoveries and unlocked items; old progress files load
export = body(campaign, "void Campaign::exportProgress(")
for token in ('"Version "', '"Completed"', '"Discovered"', '"Shards"', '"Unlocked "', '"Difficulty "', '"Finished"'):
    check(token in export, "the progress must write " + token)
progress = body(campaign, "bool Campaign::importProgress(")
check('keyword == "Unlocked"' in progress and '(keyword != "Shards")' in progress and "if(!versioned)" in progress,
      "the progress must read shards and unlocked items and keep older files readable")
handler = read("source/gamemap/MapHandler.cpp")
check("gameMap.exportCampaignMerchantInfo(levelFile);" in handler and
      "gameMap.importCampaignMerchantInfoLine(nextParam)" in handler,
      "a saved game keeps the unlocked items that still wait for the merchant")

# TX1-TX4: titles, briefings, debriefings and the scripted messages of the 24 levels
raids = {raid[0]: raid for raid in RAIDS}
check(len(raids) == STORY_LEVELS, "every story level needs its fixed raid")
for entry in entries:
    file = entry.get("File", "")
    texts = [entry.get(key, "") for key in ("Title", "Briefing", "Debriefing")]
    check(all(texts), file + " needs a title, a briefing and a debriefing")
    title, briefing, debriefing = texts
    for name in OLD_TITLE_NAMES:
        check(name.lower() not in title.lower(), file + " must not be titled after the old province or trial " + name)
    for text in texts:
        check(WORKER_WORD.search(text) is None, file + " calls the Ziv a worker: " + text[:60])
        found = REMOVED_WORDS.search(text)
        check(found is None, file + " still names " + (found.group(0) if found else "") + ": " + text[:60])
    if entry.get("Bonus") == "1":
        check("Warden" not in entry, file + " is a bonus level without a raid and needs no Warden key")
        check("No raid" in briefing, file + " must tell that no raid comes")
        check(BONUS_UNLOCK_TEXT in briefing and BONUS_UNLOCK_TEXT in debriefing,
              file + " must name the unlock of " + BONUS_UNLOCK_TEXT)
        check("Heartstone" not in briefing + debriefing, file + " carries no Heartstone shard")
        continue
    raid = raids.get(file)
    if raid is None:
        continue
    _, warden, leaders, guild, origin, size = raid
    check(entry.get("Warden") == warden, file + " must name its raid leader in the Warden key: " + warden)
    for part in leaders + (guild, origin, "Moreya gate"):
        check(part in briefing, file + " briefing must name " + part)
    check(size in briefing.lower(), file + " briefing must name the raid size " + size)
for file, *_ in EXPECTED:
    for number, line in enumerate(read("levels/" + file).replace("\r", "").split("\n"), 1):
        if not line.startswith(("Action\tmessage\t", "Action\thint\t")):
            continue
        check(WORKER_WORD.search(line) is None, "%s:%d calls the Ziv a worker" % (file, number))
        found = REMOVED_WORDS.search(line)
        check(found is None, "%s:%d still names %s" % (file, number, found.group(0) if found else ""))
        if file in raids:
            check("dawn" not in line.lower(), "%s:%d still names the dawn of the old waves" % (file, number))

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign wing structure: %d levels (%d story, %d bonus), %d shards: PASS" % (
    len(entries), STORY_LEVELS, BONUS_LEVELS, SHARDS))
