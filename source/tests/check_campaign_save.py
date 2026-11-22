"""Pure Python checks of campaign-save wiring; compiles nothing.

Runtime record, progress and difficulty expectations live in the companion
check_campaign_save_probe.py, which is run by FINAL after compilation is allowed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Read the production source without invoking a compiler."""
    return (ROOT / path).read_text(encoding="utf-8")


def body(source, signature):
    """Extract a complete function, retaining nested guards for ordering checks."""
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


campaign = read("source/game/Campaign.cpp")
header = read("source/game/Campaign.h")
handler = read("source/gamemap/MapHandler.cpp")
handler_header = read("source/gamemap/MapHandler.h")
server = read("source/network/ODServer.cpp")
load = read("source/modes/MenuModeLoad.cpp")
game = read("source/modes/GameMode.cpp")
game_map = read("source/gamemap/GameMap.cpp")

# The record is optional, versioned and available to the load-screen classifier.
for field in ("mPresent", "mValid", "mLevelFile", "mDifficulty", "mChampionAvailable"):
    assert field in header, field
# The kept creature of the former campaign is gone: every level starts fresh
for field in ("mKeptClass", "mKeptLevel", "mKeptPendingClass", "mKeptPendingLevel", "mHeartstoneComplete"):
    assert field not in header, field
assert "CampaignSave mCampaignSave" in handler_header
info = body(handler, "bool getMapInfo(")
assert "mCampaignSave.importInfoLine(nextParam)" in info

# Every game save writes campaign metadata, while editor map output does not.
writer = body(handler, "bool writeGameMapToFile(")
assert "gameMap.isServerGameMap() && !gameMap.isInEditorMode()" in writer
save_start = writer.index("if(isGameSave)")
save_block = body(writer[save_start:], "if(isGameSave)")
assert "getSaveState()" in save_block and "exportInfo(levelFile)" in save_block
assert writer.index("getSaveState()") < writer.index('levelFile << "[/Info]"')
snapshot = body(campaign, "CampaignSave Campaign::getSaveState(")
for field in ("mActive", "mLevels", "mPlayedLevel", "mChampionAvailable"):
    assert field in snapshot, field
# Campaign items that still wait for a merchant table are saved and loaded with the game
assert "gameMap.exportCampaignMerchantInfo(levelFile)" in save_block
reader = body(handler, "bool readGameMapFromFile(")
assert "gameMap.importCampaignMerchantInfoLine(nextParam)" in reader

# Eligibility and startup share a single filename/progress rule; both legacy and
# recorded saves go through it, before seat setup can choose campaign effects.
eligibility = body(campaign, "size_t Campaign::findSavedLevelNoLock(")
assert "mLevelFile" in eligibility and "mPresent" in eligibility
assert "isUnlockedNoLock(i)" in eligibility
assert "findSavedLevelNoLock(saved, saveFilename)" in body(campaign, "size_t Campaign::findSavedLevel(")
restore = body(campaign, "bool Campaign::restoreSavedLevel(")
assert "findSavedLevel" in restore
start = body(server, "bool ODServer::startServer(")
assert "mode == ServerMode::ModeGameLoaded" in start
# The second argument of loadLevel is the multiplayer strictness of the shipped level check
assert start.index("gameMap->loadLevel(levelFilename, ") < start.index("restoreSavedLevel(")
assert start.index("restoreSavedLevel(") < start.index("seat->getAiLevel()")
assert "getLevelDifficulty()" in start
assert start.index("if((mode == ServerMode::ModeGameLoaded) && Campaign::getSingleton().isActive())") < start.index("else if(seat->getAiLevel()")
assert "loadCampaignProgress()" in load
assert "bool loadCampaignProgress(" in handler and "loadCampaignProgress()" in handler_header

# No creature comes along from the last level any more; the unlocked items are queued for the merchant only
# at a fresh start, because a loaded game brings its waiting items in its Info block.
assert "spawnKeptMinion" not in server
queue = server.index("unlockedItems = Campaign::getSingleton().getUnlockedItems();")
assert "if(mServerMode != ServerMode::ModeGameLoaded)" in server[queue - 120:queue]
assert "gameMap->addCampaignMerchantGood(seat->getId(), quality, unlocked.mItemId);" in server
assert "isLevelChampionAvailable()" in server
assert "const bool championAvailable = Campaign::getSingleton().isLevelChampionAvailable();" in server
assert "SkillType::spellSummonChampion, championAvailable, championAvailable" in server
champion = body(campaign, "bool Campaign::isLevelChampionAvailableNoLock(")
assert "if(mLoadedCampaignSave)" in champion and "return mSavedChampionAvailable" in champion
assert "return isChampionAvailableNoLock(mPlayedLevel)" in champion

# Victory still follows the established campaign path, including its message,
# progress write and menu return. Defeat and ordinary quit use the same active flag.
won = body(campaign, "bool Campaign::completePlayedLevel(")
assert "mCompleted[mPlayedLevel] = true" in won
assert "mPlayedLevelWon = true" in won and "saveProgress()" in won
assert "bool firstBonusCompletion = played.mBonus && !mCompleted[mPlayedLevel];" in won
assert won.index("firstBonusCompletion = ") < won.index("mCompleted[mPlayedLevel] = true")
assert "mKeptPendingClass" not in won and "mRestoredLevel" not in won
assert "mSavedChampionAvailable = mLoadedCampaignSave && saved.mChampionAvailable" in restore
assert "mLoadedCampaignSave = false" in body(campaign, "void Campaign::startLevel(")
assert "mDifficulty =" not in won, "loaded victory must preserve menu difficulty"
assert "completePlayedLevel(nullptr, nullptr)" in body(campaign, "bool Campaign::onLevelWon()")
victory = body(game_map, "void GameMap::addWinningSeat(")
assert victory.index("onLevelWon(campaignUnlockCandidates(*this), &drawCampaignUnlock)") < victory.index("ServerNotificationType::campaignVictory")
victory_ui = body(game, "void GameMode::showCampaignVictory(")
assert "Campaign::getSingleton().isActive()" in victory_ui
assert "MENU_CAMPAIGN" in body(game, "bool GameMode::onClickCampaignVictoryConfirm(")
for function in ("bool GameMode::onClickDefeatDebriefingConfirm(",
                 "bool GameMode::onClickYesQuitMenu("):
    route = body(game, function)
    assert "Campaign::getSingleton().isActive()" in route and "MENU_CAMPAIGN" in route

# Ensure FINAL has executable production-code coverage for the cases that static
# wiring cannot prove. Fixed names make accidental loss of a scenario visible.
probe = read("source/tests/check_campaign_save_probe.py")
for expectation in ("all record fields round trip", "recorded file wins over save filename",
                    "recorded difficulty overrides gameplay while menu difficulty stays changed",
                    "champion follows save despite absent current pieces",
                    "victory completes the played level and unlocks the next",
                    "finished difficulty is recorded hard and unlocks Hell",
                    "current complete Heartstone cannot override save without champion",
                    "version 1 record of an older save loads without its kept creature",
                    "champion only from the champion wing with all shards",
                    "recorded locked level loads without active campaign state",
                    "removed recorded level cannot fall back to a matching old filename",
                    "old save of unlocked campaign file is classified as campaign",
                    "old save of locked level stays ordinary",
                    "skirmish save remains ordinary and gets no campaign record",
                    "old campaign save takes current progress difficulty",
                    "old saves use Heartstone and difficulty of current progress",
                    "progress of the former campaign keeps only the difficulty",
                    "campaign list reorder restores by file, never old index"):
    assert expectation in probe, expectation
print("campaign save record, load effects, merchant items, no carry-over and campaign exit wiring: PASS")
print("Runtime campaign save probe is present; execution is deferred to FINAL")
