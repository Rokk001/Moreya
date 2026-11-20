/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#define BOOST_TEST_MODULE Campaign
#include "BoostTestTargetConfig.h"

#include "game/Campaign.h"
#include "game/CampaignWorld.h"

#include <map>
#include <sstream>
#include <string>
#include <vector>

static const std::string sample =
    "# comment\n"
    "[Level]\n"
    "File=campaign/One.level\n"
    "Title=First\n"
    "Briefing=Line one\\nLine two\n"
    "Debriefing=Well done\n"
    "[Level]\n"
    "File=campaign/Two.level\n"
    "Title=Second\n"
    "[Level]\n"
    "Title=No file, ignored\n";

//! \brief Levels unlock one after the other, a won level is saved and read again, and a new campaign forgets it
BOOST_AUTO_TEST_CASE(test_sequence_and_progress)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream is(sample);
    BOOST_REQUIRE(campaign.importDefinition(is));
    campaign.resetProgress();
    campaign.stopCampaign();
    BOOST_REQUIRE_EQUAL(campaign.getNumLevels(), 2u);
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mFile, "campaign/One.level");
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mBriefing, "Line one\nLine two");
    BOOST_CHECK_EQUAL(campaign.getLevel(1).mTitle, "Second");

    // New campaign: only level 1 is unlocked.
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 0u);
    BOOST_CHECK(campaign.isUnlocked(0));
    BOOST_CHECK(!campaign.isUnlocked(1));
    BOOST_CHECK(!campaign.hasProgress());

    // Win level 1: level 2 becomes the current one.
    BOOST_CHECK(!campaign.onLevelWon());
    campaign.startLevel(0);
    BOOST_CHECK(campaign.onLevelWon());
    BOOST_CHECK(campaign.getPlayedLevelWon());
    BOOST_CHECK(campaign.isCompleted(0));
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 1u);
    BOOST_CHECK(campaign.isUnlocked(1));

    // Save and load into a fresh state: continue lands on level 2.
    std::ostringstream os;
    campaign.exportProgress(os);
    BOOST_CHECK(os.str().find("Version 2\n") != std::string::npos);
    BOOST_CHECK(os.str().find("Completed campaign/One.level\n") != std::string::npos);
    std::istringstream is2(sample);
    BOOST_REQUIRE(campaign.importDefinition(is2));
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 0u);
    std::istringstream progress(os.str());
    BOOST_REQUIRE(campaign.importProgress(progress));
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 1u);
    BOOST_CHECK(campaign.hasProgress());
    BOOST_CHECK(!campaign.isFinished());

    // A won level can be replayed.
    BOOST_CHECK(campaign.isUnlocked(0));
}

//! Two wings of two story levels each, a bonus level per wing; the shard lies in level 2 of wing 1, Summon champion
//! in every level of wing 2, a bonus level unlocks one Epic, one Rare and one Common item (the Unlock key of a story
//! level and the Shard key of a bonus level are ignored).
static const std::string sampleWings =
    "[Level]\nFile=campaign/W1L1.level\nWing=1\nUnlock=Epic\n"
    "[Level]\nFile=campaign/W1L2.level\nWing=1\nShard=1\n"
    "[Level]\nFile=campaign/W1Bonus.level\nWing=1\nBonus=1\nShard=1\nUnlock=Epic Rare Common\n"
    "[Level]\nFile=campaign/W2L1.level\nWing=2\nChampion=1\n"
    "[Level]\nFile=campaign/W2L2.level\nWing=2\nChampion=1\n"
    "[Level]\nFile=campaign/W2Bonus.level\nWing=2\nBonus=1\nChampion=1\nUnlock=Epic Poor Rare Common\n";

//! \brief Loads sampleWings into the campaign with an empty progress and no level played.
//! \param campaign The campaign to fill.
static void loadWings(Campaign& campaign)
{
    std::istringstream is(sampleWings);
    BOOST_REQUIRE(campaign.importDefinition(is));
    campaign.setProgressPath("");
    campaign.resetProgress();
    campaign.stopCampaign();
}

//! \brief Starts the level with the given index and wins it, so the levels after it unlock.
//! \param campaign The campaign that runs the level.
//! \param index Index of the level in the campaign definition.
static void completeLevel(Campaign& campaign, size_t index)
{
    campaign.startLevel(index);
    BOOST_REQUIRE(campaign.onLevelWon());
}

//! \brief Always draws the first candidate.
static uint32_t drawFirst(uint32_t)
{
    return 0;
}

//! \brief Always draws the last candidate.
static uint32_t drawLast(uint32_t count)
{
    return count - 1;
}

//! \brief Catalogue of item ids per quality for the unlock tests.
static std::map<std::string, std::vector<std::string> > unlockCandidates()
{
    std::map<std::string, std::vector<std::string> > candidates;
    candidates["Common"].push_back("Sword");
    candidates["Common"].push_back("Shield");
    candidates["Rare"].push_back("Sword");
    candidates["Rare"].push_back("Ring");
    candidates["Epic"].push_back("Crown");
    candidates["Epic"].push_back("Ring");
    candidates["Poor"].push_back("Rag");
    return candidates;
}

//! \brief The wing, shard, bonus, champion and unlock keys are read; a bonus level carries no shard and a story
//! level unlocks no item even when its entry names one, and only Common, Rare and Epic can be unlocked
BOOST_AUTO_TEST_CASE(test_wing_definition)
{
    Campaign& campaign = Campaign::getSingleton();
    loadWings(campaign);
    BOOST_REQUIRE_EQUAL(campaign.getNumLevels(), 6u);
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mWing, 1u);
    BOOST_CHECK_EQUAL(campaign.getLevel(4).mWing, 2u);
    BOOST_CHECK_EQUAL(campaign.getLevel(5).mWing, 2u);
    BOOST_CHECK(campaign.getLevel(1).mShard);
    BOOST_CHECK(!campaign.getLevel(0).mShard);
    BOOST_CHECK(campaign.getLevel(2).mBonus);
    BOOST_CHECK(!campaign.getLevel(2).mShard);
    BOOST_CHECK(!campaign.getLevel(1).mChampion);
    BOOST_CHECK(!campaign.getLevel(2).mChampion);
    BOOST_CHECK(campaign.getLevel(3).mChampion);
    BOOST_CHECK(campaign.getLevel(5).mChampion);
    std::vector<std::string> qualities = campaign.getLevel(2).mUnlockQualities;
    BOOST_REQUIRE_EQUAL(qualities.size(), 3u);
    BOOST_CHECK_EQUAL(qualities[0], "Epic");
    BOOST_CHECK_EQUAL(qualities[1], "Rare");
    BOOST_CHECK_EQUAL(qualities[2], "Common");
    BOOST_CHECK_EQUAL(campaign.getLevel(5).mUnlockQualities.size(), 3u);
    BOOST_CHECK(campaign.getLevel(0).mUnlockQualities.empty());
    BOOST_CHECK_EQUAL(campaign.getHeartstoneTotal(), 1u);
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 0u);

    // A definition without the keys offers the champion nowhere and unlocks no item
    std::istringstream plain(sample);
    BOOST_REQUIRE(campaign.importDefinition(plain));
    BOOST_CHECK(!campaign.getLevel(0).mChampion);
    BOOST_CHECK(campaign.getLevel(0).mUnlockQualities.empty());
    BOOST_CHECK_EQUAL(campaign.getHeartstoneTotal(), 0u);
}

//! \brief A shard counts only in its own story level, once, while that level is played; it is saved and read again
BOOST_AUTO_TEST_CASE(test_shard_counting)
{
    Campaign& campaign = Campaign::getSingleton();
    loadWings(campaign);

    // No level is played: nothing is found
    BOOST_CHECK(!campaign.findShard());
    // A level without a shard and a bonus level find none
    campaign.startLevel(0);
    BOOST_CHECK(!campaign.findShard());
    campaign.startLevel(2);
    BOOST_CHECK(!campaign.findShard());
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 0u);
    BOOST_CHECK(!campaign.isHeartstoneComplete());

    // The shard level finds it once
    campaign.startLevel(1);
    BOOST_CHECK(campaign.findShard());
    BOOST_CHECK(!campaign.findShard());
    BOOST_CHECK(campaign.isShardFound(1));
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 1u);
    BOOST_CHECK(campaign.isHeartstoneComplete());

    // The shard is saved, also when the level is not won
    campaign.stopCampaign();
    std::ostringstream os;
    campaign.exportProgress(os);
    BOOST_CHECK(os.str().find("Shards campaign/W1L2.level\n") != std::string::npos);
    loadWings(campaign);
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 0u);
    std::istringstream progress(os.str());
    BOOST_REQUIRE(campaign.importProgress(progress));
    BOOST_CHECK(campaign.isShardFound(1));
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 1u);
}

//! \brief Summon champion is available only with every shard found and only in the levels with Champion=1 (the
//! champion wings), their bonus levels included
BOOST_AUTO_TEST_CASE(test_champion_by_wing_and_shards)
{
    Campaign& campaign = Campaign::getSingleton();
    loadWings(campaign);

    // Without the shard: no level offers it
    for(size_t i = 0; i < campaign.getNumLevels(); ++i)
        BOOST_CHECK(!campaign.isChampionAvailable(i));
    campaign.startLevel(3);
    BOOST_CHECK(!campaign.isLevelChampionAvailable());

    // With the shard: the levels of wing 2 offer it, the levels of wing 1 do not
    campaign.startLevel(1);
    BOOST_REQUIRE(campaign.findShard());
    BOOST_CHECK(!campaign.isChampionAvailable(0));
    BOOST_CHECK(!campaign.isChampionAvailable(1));
    BOOST_CHECK(!campaign.isChampionAvailable(2));
    BOOST_CHECK(campaign.isChampionAvailable(3));
    BOOST_CHECK(campaign.isChampionAvailable(4));
    BOOST_CHECK(campaign.isChampionAvailable(5));
    BOOST_CHECK(!campaign.isChampionAvailable(campaign.getNumLevels()));
    BOOST_CHECK(!campaign.isLevelChampionAvailable());
    campaign.startLevel(3);
    BOOST_CHECK(campaign.isLevelChampionAvailable());
    BOOST_CHECK(campaign.getSaveState().mChampionAvailable);

    // Not while no campaign level is played
    campaign.stopCampaign();
    BOOST_CHECK(!campaign.isLevelChampionAvailable());
}

//! \brief A bonus level stays hidden until the first story level of its wing finds it, does not block the story
//! levels, has no raid, and its discovery is saved
BOOST_AUTO_TEST_CASE(test_bonus_discovery_by_wing)
{
    Campaign& campaign = Campaign::getSingleton();
    loadWings(campaign);
    BOOST_CHECK(!campaign.isUnlocked(2));

    // Only while a level is played, and only in the first story level of the bonus level's wing
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W1Bonus.level"));
    campaign.startLevel(1);
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W1Bonus.level"));
    campaign.startLevel(3);
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W1Bonus.level"));
    campaign.startLevel(0);
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W2Bonus.level"));
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W1L2.level"));
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/Unknown.level"));
    BOOST_CHECK(campaign.discoverBonusLevel("campaign/W1Bonus.level"));
    BOOST_CHECK(!campaign.discoverBonusLevel("campaign/W1Bonus.level"));
    BOOST_CHECK(campaign.isUnlocked(2));
    BOOST_CHECK(!campaign.isUnlocked(5));
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 0u);
    campaign.startLevel(3);
    BOOST_CHECK(!campaign.isPlayedLevelBonus());
    BOOST_CHECK(campaign.discoverBonusLevel("campaign/W2Bonus.level"));

    // Bonus levels do not block the story levels; a bonus level is played without a raid
    completeLevel(campaign, 0);
    BOOST_CHECK(campaign.isUnlocked(1));
    completeLevel(campaign, 1);
    BOOST_CHECK(campaign.isUnlocked(3));
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 3u);
    campaign.startLevel(2);
    BOOST_CHECK(campaign.isPlayedLevelBonus());

    // The discovery is saved
    campaign.stopCampaign();
    BOOST_CHECK(!campaign.isPlayedLevelBonus());
    std::ostringstream os;
    campaign.exportProgress(os);
    BOOST_CHECK(os.str().find("Discovered campaign/W1Bonus.level campaign/W2Bonus.level\n") != std::string::npos);
    loadWings(campaign);
    BOOST_CHECK(!campaign.isDiscovered(2));
    std::istringstream progress(os.str());
    BOOST_REQUIRE(campaign.importProgress(progress));
    BOOST_CHECK(campaign.isDiscovered(2));
    BOOST_CHECK(campaign.isDiscovered(5));

    // The campaign can be finished without completing a bonus level
    completeLevel(campaign, 3);
    completeLevel(campaign, 4);
    BOOST_CHECK(campaign.isFinished());
    BOOST_CHECK(!campaign.isCompleted(2));
}

//! \brief The first completion of a bonus level unlocks one item per quality from the candidates, a replay unlocks
//! nothing more, a second bonus level never unlocks an item again at the same quality, and a story level unlocks
//! nothing; the unlocked items are saved, read again and forgotten by a new campaign
BOOST_AUTO_TEST_CASE(test_bonus_unlock_first_completion_only)
{
    Campaign& campaign = Campaign::getSingleton();
    loadWings(campaign);
    std::map<std::string, std::vector<std::string> > candidates = unlockCandidates();

    // Nothing is unlocked before a bonus level is won (the merchant of earlier levels sells none of them)
    BOOST_CHECK(campaign.getUnlockedItems().empty());
    // A story level unlocks nothing
    campaign.startLevel(0);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawFirst));
    BOOST_CHECK(campaign.getUnlockedItems().empty());

    // The first completion of the bonus level unlocks 1 Epic, 1 Rare and 1 Common
    campaign.startLevel(2);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawFirst));
    std::vector<CampaignUnlockedItem> items = campaign.getUnlockedItems();
    BOOST_REQUIRE_EQUAL(items.size(), 3u);
    BOOST_CHECK_EQUAL(items[0].mQuality, "Epic");
    BOOST_CHECK_EQUAL(items[0].mItemId, "Crown");
    BOOST_CHECK_EQUAL(items[1].mQuality, "Rare");
    BOOST_CHECK_EQUAL(items[1].mItemId, "Sword");
    BOOST_CHECK_EQUAL(items[2].mQuality, "Common");
    BOOST_CHECK_EQUAL(items[2].mItemId, "Sword");
    for(const CampaignUnlockedItem& item : items)
        BOOST_CHECK_EQUAL(item.mBonusFile, "campaign/W1Bonus.level");

    // A replay unlocks nothing more
    campaign.startLevel(2);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawLast));
    BOOST_CHECK_EQUAL(campaign.getUnlockedItems().size(), 3u);

    // The second bonus level draws only among the lines not unlocked at that quality yet
    campaign.startLevel(5);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawFirst));
    items = campaign.getUnlockedItems();
    BOOST_REQUIRE_EQUAL(items.size(), 6u);
    BOOST_CHECK_EQUAL(items[3].mItemId, "Ring");
    BOOST_CHECK_EQUAL(items[3].mQuality, "Epic");
    BOOST_CHECK_EQUAL(items[4].mItemId, "Ring");
    BOOST_CHECK_EQUAL(items[4].mQuality, "Rare");
    BOOST_CHECK_EQUAL(items[5].mItemId, "Shield");
    BOOST_CHECK_EQUAL(items[5].mQuality, "Common");
    BOOST_CHECK_EQUAL(items[5].mBonusFile, "campaign/W2Bonus.level");

    // The unlocked items are saved and read again in their order
    campaign.stopCampaign();
    std::ostringstream os;
    campaign.exportProgress(os);
    BOOST_CHECK(os.str().find("Unlocked campaign/W1Bonus.level Epic Crown\n") != std::string::npos);
    BOOST_CHECK(os.str().find("Unlocked campaign/W2Bonus.level Common Shield\n") != std::string::npos);
    loadWings(campaign);
    BOOST_CHECK(campaign.getUnlockedItems().empty());
    std::istringstream progress(os.str() + "Unlocked campaign/W1Bonus.level Poor Rag\nUnlocked broken\n");
    BOOST_REQUIRE(campaign.importProgress(progress));
    items = campaign.getUnlockedItems();
    BOOST_REQUIRE_EQUAL(items.size(), 6u);
    BOOST_CHECK_EQUAL(items[0].mItemId, "Crown");
    BOOST_CHECK_EQUAL(items[5].mItemId, "Shield");
    BOOST_CHECK(campaign.isCompleted(2));
    BOOST_CHECK(campaign.isCompleted(5));

    // A completed bonus level won again after loading unlocks nothing either
    campaign.startLevel(2);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawLast));
    BOOST_CHECK_EQUAL(campaign.getUnlockedItems().size(), 6u);

    // Without candidates a first completion records the level but unlocks nothing
    loadWings(campaign);
    campaign.startLevel(2);
    BOOST_CHECK(campaign.onLevelWon());
    BOOST_CHECK(campaign.isCompleted(2));
    BOOST_CHECK(campaign.getUnlockedItems().empty());

    // A new campaign forgets the unlocked items
    campaign.startLevel(5);
    BOOST_CHECK(campaign.onLevelWon(candidates, &drawFirst));
    BOOST_CHECK_EQUAL(campaign.getUnlockedItems().size(), 3u);
    campaign.resetProgress();
    BOOST_CHECK(campaign.getUnlockedItems().empty());
}

//! \brief The difficulty of the campaign is chosen once, saved with the progress and reset by a new campaign
BOOST_AUTO_TEST_CASE(test_difficulty_is_saved)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream is(sample);
    BOOST_REQUIRE(campaign.importDefinition(is));
    campaign.resetProgress();
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), Campaign::getDefaultDifficulty());

    campaign.setDifficulty(0);
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), 0u);
    // Values beyond the highest AI level are ignored
    campaign.setDifficulty(99);
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), 0u);

    std::ostringstream os;
    campaign.exportProgress(os);
    campaign.setDifficulty(Campaign::getDefaultDifficulty());
    std::istringstream progress(os.str());
    BOOST_REQUIRE(campaign.importProgress(progress));
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), 0u);

    // A new campaign returns to the default
    campaign.resetProgress();
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), Campaign::getDefaultDifficulty());
}

//! \brief The warden and difficulty keys of the definition file are read; the province keys of the former world
//! map are ignored, so no level is found by a province
BOOST_AUTO_TEST_CASE(test_province_keys)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream is(
        "[Level]\n"
        "File=a.level\n"
        "Province=T01\n"
        "Warden=Reeve Test\n"
        "Difficulty=9\n"
        "[Level]\n"
        "File=b.level\n"
        "Province=B01\n"
        "[Level]\n"
        "File=c.level\n");
    BOOST_REQUIRE(campaign.importDefinition(is));

    BOOST_CHECK(campaign.getLevel(0).mProvince.empty());
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mWarden, "Reeve Test");
    // The difficulty is limited to 1..5, without the setting it is 1
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mDifficulty, 5u);
    BOOST_CHECK_EQUAL(campaign.getLevel(1).mDifficulty, 1u);
    BOOST_CHECK_EQUAL(campaign.findLevelByProvince("B01"), campaign.getNumLevels());
    BOOST_CHECK_EQUAL(campaign.findLevelByProvince("T01"), campaign.getNumLevels());
    BOOST_CHECK_EQUAL(campaign.findLevelByProvince(""), campaign.getNumLevels());
}

static const std::string sampleBranch =
    "[Level]\nFile=p.level\nProvince=T08\n"
    "[Level]\nFile=a.level\nProvince=T09A\nBranch=T09B\n"
    "[Level]\nFile=b.level\nProvince=T09B\nBranch=T09A\n"
    "[Level]\nFile=n.level\nProvince=T10\n";

//! \brief Branch keys of an older definition are ignored: the former sisters are two story levels of one straight
//! sequence, so each of them is needed to unlock the levels after them
BOOST_AUTO_TEST_CASE(test_branch_levels)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream is(sampleBranch);
    BOOST_REQUIRE(campaign.importDefinition(is));
    campaign.setProgressPath("");
    campaign.resetProgress();

    // Only the first level is open
    BOOST_CHECK(!campaign.isUnlocked(1));
    BOOST_CHECK(!campaign.isUnlocked(2));
    BOOST_CHECK(!campaign.isUnlocked(3));
    completeLevel(campaign, 0);
    // The former first sister opens, the former second one does not
    BOOST_CHECK(campaign.isUnlocked(1));
    BOOST_CHECK(!campaign.isUnlocked(2));
    BOOST_CHECK(!campaign.isUnlocked(3));

    // One former sister is not enough for the next level any more
    completeLevel(campaign, 1);
    BOOST_CHECK(campaign.isUnlocked(2));
    BOOST_CHECK(!campaign.isUnlocked(3));
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 2u);
    completeLevel(campaign, 2);
    BOOST_CHECK(campaign.isUnlocked(3));
    BOOST_CHECK(!campaign.isFinished());
    completeLevel(campaign, 3);
    BOOST_CHECK(campaign.isFinished());
}

//! \brief The world map description and the id map give the province under a map pixel
BOOST_AUTO_TEST_CASE(test_world_map)
{
    CampaignWorld world;
    std::istringstream is(
        "{\"version\":1,\"size\":[4,2],\"provinces\":["
        "{\"id\":\"T01\",\"name\":\"One\",\"mask_rgb\":[10,20,30],\"layer_origin\":[1,2],\"lift_origin\":[0,1],"
        "\"layers\":{\"locked\":\"l.png\",\"available\":\"a.png\",\"conquered\":\"c.png\",\"lift\":\"f.png\"}},"
        "{\"id\":\"T02\",\"name\":\"Two\",\"mask_rgb\":[40,50,60],\"layer_origin\":[3,4],\"lift_origin\":[2,3],"
        "\"layers\":{\"locked\":\"l.png\",\"available\":\"a.png\",\"conquered\":\"c.png\",\"lift\":\"f.png\"}}],"
        "\"sites\":[{\"id\":\"B01\",\"name\":\"Cave\",\"host\":\"T01\",\"pos\":[5,6],"
        "\"icons\":{\"hidden\":\"h.png\",\"found\":\"f.png\",\"done\":\"d.png\"}}],"
        "\"progress_panel\":[1,2,3,4],\"title_cartouche\":[5,6,7,8]}");
    BOOST_REQUIRE(world.importDefinition(is));
    BOOST_CHECK_EQUAL(world.getProvinces().size(), 2u);
    BOOST_CHECK_EQUAL(world.getWidth(), 4);
    BOOST_CHECK_EQUAL(world.getProvinces()[1].mLayerY, 4);
    BOOST_CHECK_EQUAL(world.getSites()[0].mX, 5);
    BOOST_CHECK_EQUAL(world.getProgressPanel().mHeight, 4);
    BOOST_CHECK_EQUAL(world.findProvince("T02"), 1u);
    BOOST_CHECK_EQUAL(world.findProvince("T99"), 2u);

    // Id map 4x2: pixel 0 is province one, pixel 5 province two, the rest is outside of all provinces
    std::vector<uint8_t> rgb(4 * 2 * 3, 0);
    rgb[0] = 10; rgb[1] = 20; rgb[2] = 30;
    rgb[15] = 40; rgb[16] = 50; rgb[17] = 60;
    world.setIdMap(4, 2, rgb);
    BOOST_CHECK_EQUAL(world.getProvinceAt(0, 0), 0u);
    BOOST_CHECK_EQUAL(world.getProvinceAt(1, 1), 1u);
    BOOST_CHECK_EQUAL(world.getProvinceAt(2, 0), 2u);
    BOOST_CHECK_EQUAL(world.getProvinceAt(-1, 0), 2u);
    BOOST_CHECK_EQUAL(world.getProvinceAt(4, 0), 2u);

    std::istringstream broken("{\"size\":[4,2]}");
    BOOST_CHECK(!world.importDefinition(broken));
}

//! \brief Every level starts fresh: no creature comes along any more. A kept creature of an older progress file is
//! ignored and never written again, and winning a level records nothing that a later level would receive
BOOST_AUTO_TEST_CASE(test_kept_minion)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream is(sample);
    BOOST_REQUIRE(campaign.importDefinition(is));
    campaign.resetProgress();

    // An older progress file with a kept creature loads; the creature is dropped
    std::istringstream older("Completed 0\nDiscovered\nDifficulty 1\nKeptMinion Knight 4\n");
    BOOST_REQUIRE(campaign.importProgress(older));
    std::ostringstream afterOlder;
    campaign.exportProgress(afterOlder);
    BOOST_CHECK(afterOlder.str().find("KeptMinion") == std::string::npos);

    // A won level writes the same progress as before apart from its completion: nothing is carried over
    campaign.startLevel(0);
    BOOST_CHECK(campaign.onLevelWon());
    std::ostringstream os;
    campaign.exportProgress(os);
    BOOST_CHECK(os.str().find("KeptMinion") == std::string::npos);
    BOOST_CHECK(os.str().find("Unlocked") == std::string::npos);
    BOOST_CHECK(os.str().find("Completed campaign/One.level\n") != std::string::npos);

    // A save of the next level records only file, difficulty and champion availability
    campaign.startLevel(1);
    std::ostringstream record;
    campaign.getSaveState().exportInfo(record);
    BOOST_CHECK_EQUAL(record.str(), "Campaign\t2 campaign/Two.level 1 0\n");
}
