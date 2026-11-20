"""Compile and run the real campaign save/progress code. Run only in FINAL.

This probe needs the compiler environment, but no game, assets or third-party
libraries. The companion check_campaign_save.py checks the server/menu wiring.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

PROBE = r'''
#include "game/Campaign.h"
#include "ai/KeeperAIType.h"
#include <iostream>
#include <sstream>
#include <string>

static int failures = 0;
static int checks = 0;

//! \brief Reports each fixed gameplay expectation without stopping the other cases.
static void check(bool condition, const char* message)
{
    ++checks;
    if(!condition)
    {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

//! Three story levels in two wings (the shard in wing 1, Summon champion in wing 2) and the bonus level of wing 1.
static const std::string definition =
    "[Level]\nFile=campaign/One.level\nTitle=First\nWing=1\nShard=1\n"
    "[Level]\nFile=campaign/Two.level\nTitle=Second\nWing=2\nChampion=1\n"
    "[Level]\nFile=campaign/Three.level\nTitle=Third\nWing=2\nChampion=1\n"
    "[Level]\nFile=campaign/Bonus.level\nTitle=Hidden\nWing=1\nBonus=1\nUnlock=Epic Rare Common\n";

//! Index that names no level of the definition
static const size_t NO_LEVEL = 4;

//! \brief Starts every scenario with known progress and no disk writes.
static void fresh(const std::string& progress = "Version 2\nDifficulty 1\n")
{
    Campaign& campaign = Campaign::getSingleton();
    campaign.stopCampaign();
    campaign.setProgressPath("");
    std::istringstream levels(definition);
    check(campaign.importDefinition(levels), "test definition loads");
    std::istringstream saved(progress);
    check(campaign.importProgress(saved), "test progress loads");
}

//! \brief Runs save round trips, eligibility, restored effects and victory progression.
int main()
{
    Campaign& campaign = Campaign::getSingleton();
    const uint32_t hard = static_cast<uint32_t>(KeeperAIType::hard);
    const uint32_t easy = static_cast<uint32_t>(KeeperAIType::easy);
    fresh();
    check(!campaign.getSaveState().mPresent, "inactive skirmish has no campaign record");
    campaign.setDifficulty(hard);
    campaign.startLevel(0);
    check(campaign.findShard(), "the shard of the played level is found");
    check(!campaign.isChampionAvailable(0) && campaign.isChampionAvailable(1) && campaign.isChampionAvailable(2),
        "champion only from the champion wing with all shards");
    campaign.startLevel(1);
    CampaignSave state = campaign.getSaveState();
    check(state.mPresent && state.mValid, "campaign save carries a valid record");
    check(state.mLevelFile == "campaign/Two.level", "record identifies level by file");
    check(state.mDifficulty == hard, "record stores played difficulty");
    check(state.mChampionAvailable, "record stores champion spell entitlement");
    std::ostringstream encoded;
    state.exportInfo(encoded);
    check(encoded.str() == "Campaign\t2 campaign/Two.level 2 1\n",
        "campaign record has stable versioned text format");
    CampaignSave decoded;
    check(decoded.importInfoLine(encoded.str()), "reader recognizes written record");
    check(decoded.mPresent && decoded.mValid && decoded.mLevelFile == "campaign/Two.level" &&
        decoded.mDifficulty == hard && decoded.mChampionAvailable, "all record fields round trip");

    fresh("Version 2\nDifficulty 0\nCompleted campaign/One.level\n");
    check(campaign.findSavedLevel(decoded, "renamed.level") == 1,
        "recorded file wins over save filename");
    check(campaign.findSavedLevel(decoded, "2026-11-09_100000-MP-Two.level") == NO_LEVEL,
        "multiplayer filename is never classified as campaign even with metadata");
    check(campaign.restoreSavedLevel(decoded, "renamed.level"), "unlocked recorded save loads as campaign");
    check(campaign.isActive() && campaign.getPlayedLevel() == 1 && !campaign.getPlayedLevelWon(),
        "restored campaign has the correct active level and unfinished result");
    check(campaign.getLevelDifficulty() == hard && campaign.getDifficulty() == easy,
        "recorded difficulty overrides gameplay while menu difficulty stays changed");
    check(campaign.isLevelChampionAvailable(), "champion follows save despite absent current pieces");
    CampaignSave resaved = campaign.getSaveState();
    check(resaved.mDifficulty == hard && resaved.mChampionAvailable,
        "resaving keeps restored difficulty and champion");
    check(campaign.onLevelWon(), "loaded campaign victory counts");
    check(campaign.isCompleted(1) && campaign.isUnlocked(2) && campaign.getPlayedLevelWon(),
        "victory completes the played level and unlocks the next");

    CampaignSave finalState = decoded;
    finalState.mLevelFile = "campaign/Three.level";
    check(campaign.restoreSavedLevel(finalState, "final.level"), "unlocked final level restores");
    check(campaign.onLevelWon() && campaign.isFinished(), "loaded final victory finishes campaign");
    check(campaign.isHellUnlocked(), "finished difficulty is recorded hard and unlocks Hell");
    check(campaign.getDifficulty() == easy, "finishing loaded campaign preserves menu difficulty");
    std::ostringstream completed;
    campaign.exportProgress(completed);
    check(completed.str().find("Difficulty 0\n") != std::string::npos &&
        completed.str().find("Finished hard\n") != std::string::npos,
        "progress persists recorded completion difficulty and unchanged menu difficulty");

    fresh("Version 2\nCompleted campaign/One.level campaign/Three.level\nDifficulty 0\n");
    check(campaign.restoreSavedLevel(decoded, "first.level") && campaign.onLevelWon() &&
        campaign.isFinished() && campaign.isHellUnlocked() && campaign.getDifficulty() == easy,
        "any loaded level completing campaign records saved difficulty, regardless of list position");

    fresh("Version 2\nDifficulty 1\nCompleted campaign/One.level\nShards campaign/One.level\n");
    CampaignSave withoutChampion = decoded;
    withoutChampion.mChampionAvailable = false;
    check(campaign.restoreSavedLevel(withoutChampion, "first.level") && !campaign.isLevelChampionAvailable(),
        "current complete Heartstone cannot override save without champion");
    check(campaign.getSaveState().mChampionAvailable == false,
        "resave does not acquire champion from current progress");

    fresh();
    CampaignSave locked = decoded;
    locked.mLevelFile = "campaign/Three.level";
    check(campaign.findSavedLevel(locked, "first.level") == NO_LEVEL,
        "recorded locked level is classified as ordinary save");
    campaign.startLevel(0);
    check(!campaign.restoreSavedLevel(locked, "first.level") && !campaign.isActive(),
        "recorded locked level loads without active campaign state");
    check(!campaign.onLevelWon() && !campaign.hasProgress(),
        "ordinary fallback victory cannot change campaign progress");
    CampaignSave missing = decoded;
    missing.mLevelFile = "campaign/Removed.level";
    check(campaign.findSavedLevel(missing, "2026-11-09_100000-SK-One.level") == NO_LEVEL &&
        !campaign.restoreSavedLevel(missing, "2026-11-09_100000-SK-One.level"),
        "removed recorded level cannot fall back to a matching old filename");

    CampaignSave legacy;
    check(!legacy.mPresent, "old save starts with no record");
    check(campaign.findSavedLevel(legacy, "2026-11-09_100000-SK-One.level") == 0,
        "old save of unlocked campaign file is classified as campaign");
    check(campaign.findSavedLevel(legacy, "2026-11-09_100000-SK-Two.level") == NO_LEVEL,
        "old save of locked level stays ordinary");
    check(!campaign.restoreSavedLevel(legacy, "2026-11-09_100000-SK-Two.level"),
        "old locked save loads without campaign");
    check(!campaign.restoreSavedLevel(legacy, "2026-11-09_100000-SK-Arena.level") &&
        !campaign.isActive() && !campaign.getSaveState().mPresent,
        "skirmish save remains ordinary and gets no campaign record");
    check(campaign.restoreSavedLevel(legacy, "2026-11-09_100000-SK-One.level"),
        "old unlocked campaign save restores");
    check(campaign.getLevelDifficulty() == static_cast<uint32_t>(KeeperAIType::normal),
        "old campaign save takes current progress difficulty");
    check(!campaign.isLevelChampionAvailable(), "old campaign save has no champion from stale state");
    std::ostringstream legacyRecord;
    campaign.getSaveState().exportInfo(legacyRecord);
    check(legacyRecord.str() == "Campaign\t2 campaign/One.level 1 0\n",
        "new record for a legacy save is written as version 2");
    campaign.stopCampaign();
    check(!campaign.isActive() && !campaign.hasProgress() && !campaign.getPlayedLevelWon(),
        "quitting or losing before victory does not complete a level");
    fresh("Version 2\nDifficulty 3\nCompleted campaign/One.level\nShards campaign/One.level\n");
    check(campaign.restoreSavedLevel(legacy, "2026-11-09_100000-SK-Two.level") &&
        campaign.isLevelChampionAvailable() && campaign.getLevelDifficulty() == 3,
        "old saves use Heartstone and difficulty of current progress");

    CampaignSave older;
    check(older.importInfoLine("Campaign\t1 campaign/One.level 2 1 Worker 7") && older.mPresent && older.mValid &&
        older.mLevelFile == "campaign/One.level" && older.mDifficulty == hard && older.mChampionAvailable,
        "version 1 record of an older save loads without its kept creature");
    std::ostringstream rewritten;
    older.exportInfo(rewritten);
    check(rewritten.str() == "Campaign\t2 campaign/One.level 2 1\n", "an older record is written back as version 2");

    fresh("Completed 0 1\nDiscovered 3\nDifficulty 0\nFinished hard\nKeptMinion Fighter 11\n");
    std::ostringstream former;
    campaign.exportProgress(former);
    check(!campaign.hasProgress() && !campaign.isDiscovered(3) && campaign.getDifficulty() == easy &&
        !campaign.isHellUnlocked() && former.str().find("KeptMinion") == std::string::npos &&
        former.str().find("Finished\n") != std::string::npos,
        "progress of the former campaign keeps only the difficulty");

    campaign.stopCampaign();
    std::istringstream reordered(
        "[Level]\nFile=campaign/Two.level\n[Level]\nFile=campaign/One.level\n");
    campaign.importDefinition(reordered);
    std::istringstream reorderedProgress("Version 2\nCompleted campaign/One.level\nDifficulty 0\n");
    campaign.importProgress(reorderedProgress);
    check(campaign.isCompleted(1) && !campaign.isCompleted(0), "progress names levels by file, so a reorder keeps them");
    check(campaign.findSavedLevel(decoded, "renamed.level") == 0 &&
        campaign.restoreSavedLevel(decoded, "renamed.level") && campaign.getPlayedLevel() == 0,
        "campaign list reorder restores by file, never old index");

    CampaignSave malformed;
    check(malformed.importInfoLine("Campaign\t2 campaign/One.level 99 1") &&
        malformed.mPresent && !malformed.mValid, "invalid recorded difficulty is not accepted");
    check(!campaign.restoreSavedLevel(malformed, "2026-11-09_100000-SK-One.level"),
        "malformed record cannot masquerade as a legacy save");
    CampaignSave future;
    check(future.importInfoLine("Campaign\t3 campaign/One.level 1 1") &&
        future.mPresent && !future.mValid, "unknown campaign record versions stay in ordinary fallback");
    CampaignSave truncated;
    check(truncated.importInfoLine("Campaign\t2 campaign/One.level 1") && !truncated.mValid,
        "incomplete campaign records cannot activate a campaign");
    CampaignSave trailing;
    check(trailing.importInfoLine("Campaign\t2 campaign/One.level 1 1 Worker 7") && !trailing.mValid,
        "a version 2 record with extra fields is malformed");
    CampaignSave unrelated;
    check(!unrelated.importInfoLine("Name\tFirst level"), "ordinary info line is not a campaign record");
    std::ostringstream empty;
    unrelated.exportInfo(empty);
    check(empty.str().empty(), "ordinary save writes no campaign metadata");
    std::cout << "campaign save probe: checks=" << checks << " failures=" << failures << '\n';
    return failures == 0 ? 0 : 1;
}
'''

with tempfile.TemporaryDirectory(prefix="odp-campaign-save-") as directory:
    work = Path(directory)
    (work / "probe.cpp").write_text(PROBE, encoding="utf-8")
    subprocess.run(["cl", "/nologo", "/EHsc", "/MD", "/std:c++14",
                    f"/I{ROOT / 'source'}", "probe.cpp",
                    str(ROOT / "source/game/Campaign.cpp"), "/Feprobe.exe"],
                   cwd=work, check=True)
    subprocess.run([str(work / "probe.exe")], cwd=work, check=True)
