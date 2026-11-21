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

//! \brief The warden key of the definition file is read; the Difficulty key and the province keys of the former
//! campaign file are ignored, so no level is found by a province
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
    // A Difficulty key of the former campaign file is ignored: the level is read as usual
    BOOST_CHECK_EQUAL(campaign.getNumLevels(), 3u);
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

//! \brief Writes a map of Moreya in the format of gui/campaign/campaign-world.json: wingCount wings with levelCount
//! story caves each and a bonus cave; the caves name no level and no guild. Cave n of a wing is at
//! x = 100 * wing + 20 * n, y = 50, 10 pixels wide; the bonus cave at y = 80.
static std::string moreyaMap(uint32_t wingCount, uint32_t levelCount)
{
    std::ostringstream os;
    os << "{\"version\":2,\"size\":[800,200],\"base\":\"moreya/map.png\","
        "\"icons\":{\"locked\":\"l.png\",\"current\":\"c.png\",\"defeated\":\"d.png\",\"bonus_found\":\"bf.png\","
        "\"bonus_cleared\":\"bc.png\",\"wing_defeated\":\"w.png\",\"hover\":\"h.png\"},"
        "\"title_cartouche\":[1,2,3,4],\"progress_panel\":[5,6,7,8],"
        "\"guild_panel\":{\"area\":[1,1,9,9],\"banner\":[1,1,2,4],\"portrait\":[3,1,2,2],\"name\":[5,1,4,1],"
        "\"details\":[5,2,4,3]},\"wings\":[";
    for(uint32_t wing = 1; wing <= wingCount; ++wing)
    {
        if(wing > 1)
            os << ",";
        os << "{\"wing\":" << wing << ",\"name\":\"Wing " << wing << "\",\"area\":[" << 100 * wing
            << ",0,90,100],\"label\":[" << 100 * wing << ",0,90,10],\"seal\":[" << 100 * wing + 80
            << ",5],\"seal_size\":8,\"levels\":[";
        for(uint32_t level = 1; level <= levelCount; ++level)
        {
            if(level > 1)
                os << ",";
            os << "{\"pos\":[" << 100 * wing + 20 * level << ",50],\"size\":10,\"label\":["
                << 100 * wing + 20 * level - 5 << ",60,10,5]}";
        }
        os << "],\"bonus\":{\"pos\":[" << 100 * wing + 20
            << ",80],\"size\":10,\"label\":[" << 100 * wing + 30 << ",75,20,10]}}";
    }
    os << "]}";
    return os.str();
}

//! \brief Package definition of one wing for moreyaMap: 3 story levels (campaign/W<wing>L<level>.level, each with
//! its guild; the last of wing 6 with two raids and two leaders), then its bonus level (campaign/W<wing>B.level).
static std::string moreyaWing(uint32_t wing)
{
    std::ostringstream os;
    for(uint32_t level = 1; level <= 3; ++level)
    {
        bool kingsRaid = (wing == 6) && (level == 3);
        os << "[Level]\nFile=campaign/W" << wing << "L" << level << ".level\nWing=" << wing << "\nTitle=Level "
            << wing << level << "\nGuild=Guild " << wing << level << "\nGuildLeader=Leader " << wing << level << "\n"
            << (kingsRaid ? "GuildFirstLeader=First Leader\n" : "") << "GuildOrigin=Origin " << wing << level
            << "\nGuildGroups=" << ((wing % 2 == 0) ? 2 : 1) << "\nGuildSize=" << 5 * wing << "\nGuildKind="
            << ((level == 3) ? "raid" : "group") << "\nGuildBanner=banners/b" << wing << level
            << ".png\nGuildPortrait=portraits/p" << wing << level << ".png\n";
    }
    os << "[Level]\nFile=campaign/W" << wing << "B.level\nWing=" << wing << "\nBonus=1\nTitle=Bonus " << wing << "\n";
    return os.str();
}

//! \brief Campaign definition with the levels of moreyaMap: per wing 3 story levels, then its bonus level.
static std::string moreyaCampaign()
{
    std::ostringstream os;
    for(uint32_t wing = 1; wing <= 6; ++wing)
        os << moreyaWing(wing);
    return os.str();
}

//! \brief The map of Moreya is read with its 6 wings, 18 story caves and 6 bonus caves, each cave finds its level by
//! wing and order, the guild of a level comes from its package; a map with another number of wings or caves is
//! rejected
BOOST_AUTO_TEST_CASE(test_world_map)
{
    CampaignWorld world;
    std::istringstream is(moreyaMap(6, 3));
    BOOST_REQUIRE(world.importDefinition(is));
    BOOST_CHECK_EQUAL(world.getWidth(), 800);
    BOOST_CHECK_EQUAL(world.getHeight(), 200);
    BOOST_CHECK_EQUAL(world.getBaseImage(), "moreya/map.png");
    BOOST_REQUIRE_EQUAL(world.getWings().size(), 6u);
    BOOST_REQUIRE_EQUAL(world.getCaves().size(), 24u);
    BOOST_CHECK_EQUAL(world.getWings()[5].mNumber, 6u);
    BOOST_CHECK_EQUAL(world.getWings()[5].mName, "Wing 6");
    BOOST_CHECK_EQUAL(world.getWings()[0].mSealX, 180);
    BOOST_CHECK_EQUAL(world.getIcons().mBonusCleared, "bc.png");
    BOOST_CHECK_EQUAL(world.getGuildPanel().mDetails.mHeight, 3);
    BOOST_CHECK_EQUAL(world.getProgressPanel().mHeight, 8);
    BOOST_CHECK_EQUAL(world.getTitleCartouche().mX, 1);

    // Per wing its 3 story caves, then its bonus cave
    uint32_t storyCaves = 0;
    uint32_t bonusCaves = 0;
    for(size_t i = 0; i < world.getCaves().size(); ++i)
    {
        const CampaignWorldCave& cave = world.getCaves()[i];
        BOOST_CHECK_EQUAL(cave.mWing, static_cast<uint32_t>(i / 4 + 1));
        BOOST_CHECK_EQUAL(cave.mBonus, (i % 4) == 3);
        if(cave.mBonus)
            ++bonusCaves;
        else
        {
            ++storyCaves;
            BOOST_CHECK_EQUAL(cave.mOrder, static_cast<uint32_t>(i % 4));
        }
    }
    BOOST_CHECK_EQUAL(storyCaves, 18u);
    BOOST_CHECK_EQUAL(bonusCaves, 6u);

    // Every cave finds its level by wing and order; the guild of a level comes from the definition
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream definition(moreyaCampaign());
    BOOST_REQUIRE(campaign.importDefinition(definition));
    BOOST_CHECK_EQUAL(campaign.getLevel(world.findLevel(campaign, 6)).mFile, "campaign/W2L3.level");
    BOOST_CHECK_EQUAL(campaign.getLevel(world.findLevel(campaign, 23)).mFile, "campaign/W6B.level");
    BOOST_CHECK_EQUAL(world.findCave(campaign, campaign.findLevelByFile("campaign/W2L3.level")), 6u);
    BOOST_CHECK_EQUAL(world.findCave(campaign, campaign.getNumLevels()), 24u);
    BOOST_CHECK_EQUAL(world.findLevel(campaign, 24), campaign.getNumLevels());
    BOOST_CHECK(campaign.getLevel(world.findLevel(campaign, 3)).mGuild.mName.empty());

    // The guild of a level: banner, portrait, leader, origin and raid size
    const CampaignWorldGuild& guild = campaign.getLevel(campaign.findLevelByFile("campaign/W2L3.level")).mGuild;
    BOOST_CHECK_EQUAL(guild.mName, "Guild 23");
    BOOST_CHECK_EQUAL(guild.mLeader, "Leader 23");
    BOOST_CHECK(guild.mFirstLeader.empty());
    BOOST_CHECK_EQUAL(guild.mOrigin, "Origin 23");
    BOOST_CHECK_EQUAL(guild.mGroups, 2u);
    BOOST_CHECK_EQUAL(guild.mSize, 10u);
    BOOST_CHECK(guild.mRaid);
    BOOST_CHECK_EQUAL(guild.mBanner, "banners/b23.png");
    BOOST_CHECK_EQUAL(guild.mPortrait, "portraits/p23.png");
    BOOST_CHECK_EQUAL(CampaignWorld::getRaidSizeText(guild), "two raids of 10");
    BOOST_CHECK_EQUAL(CampaignWorld::getGuildDetailsText(guild),
        "Leader: Leader 23\nRaid size: two raids of 10\nOrigin: Origin 23");
    const CampaignWorldGuild& group = campaign.getLevel(campaign.findLevelByFile("campaign/W1L1.level")).mGuild;
    BOOST_CHECK_EQUAL(CampaignWorld::getRaidSizeText(group), "one group of 5");
    const CampaignWorldGuild& kingsRaid = campaign.getLevel(campaign.findLevelByFile("campaign/W6L3.level")).mGuild;
    BOOST_CHECK_EQUAL(kingsRaid.mFirstLeader, "First Leader");
    BOOST_CHECK_EQUAL(CampaignWorld::getGuildDetailsText(kingsRaid),
        "Leaders: First Leader and Leader 63\nRaid size: two raids of 30\nOrigin: Origin 63");

    // Another number of wings or story caves or a broken file are rejected and leave the map empty
    std::istringstream fiveWings(moreyaMap(5, 3));
    BOOST_CHECK(!world.importDefinition(fiveWings));
    BOOST_CHECK(world.getCaves().empty());
    BOOST_CHECK(world.getWings().empty());
    std::istringstream sevenWings(moreyaMap(7, 3));
    BOOST_CHECK(!world.importDefinition(sevenWings));
    std::istringstream twoLevels(moreyaMap(6, 2));
    BOOST_CHECK(!world.importDefinition(twoLevels));
    std::istringstream fourLevels(moreyaMap(6, 4));
    BOOST_CHECK(!world.importDefinition(fourLevels));
    std::istringstream broken("{\"size\":[4,2]}");
    BOOST_CHECK(!world.importDefinition(broken));
}

//! \brief The caves of the map show the progress: the current level is marked, defeated levels stay playable, the
//! levels after the current one are locked, a bonus cave is hidden until its stone was found, then found and
//! cleared, and a wing counts its defeated levels; only visible caves can be hit with the mouse
BOOST_AUTO_TEST_CASE(test_world_map_progress)
{
    CampaignWorld world;
    std::istringstream map(moreyaMap(6, 3));
    BOOST_REQUIRE(world.importDefinition(map));
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream definition(moreyaCampaign());
    BOOST_REQUIRE(campaign.importDefinition(definition));
    campaign.setProgressPath("");
    campaign.resetProgress();
    campaign.stopCampaign();
    BOOST_REQUIRE_EQUAL(campaign.getNumLevels(), 24u);

    // A new campaign: the first cave is the current one, the other story caves are locked, the bonus caves hidden
    size_t level = 0;
    BOOST_CHECK(world.getCaveState(campaign, 0, level) == CampaignCaveState::current);
    BOOST_CHECK_EQUAL(level, 0u);
    BOOST_CHECK(world.getCaveState(campaign, 1, level) == CampaignCaveState::locked);
    BOOST_CHECK(world.getCaveState(campaign, 3, level) == CampaignCaveState::hidden);
    BOOST_CHECK_EQUAL(level, 3u);
    BOOST_CHECK(world.getCaveState(campaign, 23, level) == CampaignCaveState::hidden);
    BOOST_CHECK(world.getCaveState(campaign, 24, level) == CampaignCaveState::hidden);
    BOOST_CHECK_EQUAL(level, 24u);
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 0u);
    BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, 1), 0u);

    // The stone of wing 1 is found in its first level, then that level is won
    campaign.startLevel(0);
    BOOST_CHECK(campaign.discoverBonusLevel("campaign/W1B.level"));
    BOOST_CHECK(campaign.onLevelWon());
    BOOST_CHECK(world.getCaveState(campaign, 0, level) == CampaignCaveState::defeated);
    BOOST_CHECK(world.getCaveState(campaign, 1, level) == CampaignCaveState::current);
    BOOST_CHECK(world.getCaveState(campaign, 2, level) == CampaignCaveState::locked);
    BOOST_CHECK(world.getCaveState(campaign, 3, level) == CampaignCaveState::bonusFound);
    BOOST_CHECK(world.getCaveState(campaign, 7, level) == CampaignCaveState::hidden);
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 1u);
    BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, 1), 1u);
    // A defeated level can be played again
    BOOST_CHECK(campaign.isUnlocked(0));

    // The bonus cave is cleared; it does not count for the wing and does not move the current level
    campaign.startLevel(3);
    BOOST_CHECK(campaign.onLevelWon());
    BOOST_CHECK(world.getCaveState(campaign, 3, level) == CampaignCaveState::bonusCleared);
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 1u);
    BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, 1), 1u);

    // The whole wing is defeated, the first cave of wing 2 is the current one
    campaign.startLevel(1);
    BOOST_CHECK(campaign.onLevelWon());
    campaign.startLevel(2);
    BOOST_CHECK(campaign.onLevelWon());
    BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, 1), 3u);
    BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, 2), 0u);
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 4u);
    BOOST_CHECK(world.getCaveState(campaign, 4, level) == CampaignCaveState::current);

    // Hit test with the states: a visible cave is hit within its marker, a hidden bonus cave never
    std::vector<CampaignCaveState> states;
    for(size_t i = 0; i < world.getCaves().size(); ++i)
        states.push_back(world.getCaveState(campaign, i, level));
    BOOST_CHECK_EQUAL(world.getCaveAt(120.0f, 50.0f, states), 0u);
    BOOST_CHECK_EQUAL(world.getCaveAt(124.0f, 53.0f, states), 0u);
    BOOST_CHECK_EQUAL(world.getCaveAt(127.0f, 50.0f, states), 24u);
    BOOST_CHECK_EQUAL(world.getCaveAt(120.0f, 80.0f, states), 3u);
    BOOST_CHECK_EQUAL(world.getCaveAt(220.0f, 80.0f, states), 24u);
    BOOST_CHECK_EQUAL(world.getCaveAt(260.0f, 50.0f, states), 6u);

    // Every story level won: no current cave and no guild in front of the gate
    for(size_t i = 4; i < campaign.getNumLevels(); ++i)
    {
        if(campaign.getLevel(i).mBonus)
            continue;
        campaign.startLevel(i);
        BOOST_CHECK(campaign.onLevelWon());
    }
    BOOST_CHECK(campaign.isFinished());
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 24u);
    for(uint32_t wing = 1; wing <= 6; ++wing)
        BOOST_CHECK_EQUAL(world.getDefeatedInWing(campaign, wing), 3u);
    campaign.stopCampaign();
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

//! \brief Wing packages: the levels come in wing order with their files in the package folders; a package with mixed
//! wings, a wing out of range or a second package of a wing is skipped. Without the packages of wings 2 to 6 those
//! wings are missing: their caves are locked, the campaign is not finished after wing 1, no difficulty is finished,
//! and the progress of their levels is kept and written again unchanged
BOOST_AUTO_TEST_CASE(test_wing_packages)
{
    Campaign& campaign = Campaign::getSingleton();
    campaign.setProgressPath("");
    campaign.stopCampaign();

    // Every wing in its own package, given out of order, plus packages that must be skipped
    std::vector<CampaignPackage> packages;
    for(uint32_t wing = 6; wing >= 1; --wing)
    {
        CampaignPackage package;
        package.mDirectory = "packs/wing" + std::to_string(wing);
        package.mDefinition = moreyaWing(wing);
        packages.push_back(package);
    }
    CampaignPackage twice;
    twice.mDirectory = "other/wing2/";
    twice.mDefinition = "[Level]\nFile=campaign/Twice.level\nWing=2\n";
    packages.push_back(twice);
    CampaignPackage mixed;
    mixed.mDirectory = "other/mixed";
    mixed.mDefinition = "[Level]\nFile=campaign/M1.level\nWing=1\n[Level]\nFile=campaign/M2.level\nWing=2\n";
    packages.push_back(mixed);
    CampaignPackage outside;
    outside.mDirectory = "other/wing7";
    outside.mDefinition = "[Level]\nFile=campaign/Seven.level\nWing=7\n";
    packages.push_back(outside);
    BOOST_REQUIRE(campaign.importPackages(packages));
    BOOST_REQUIRE_EQUAL(campaign.getNumLevels(), 24u);
    BOOST_CHECK(!campaign.hasMissingWings());
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mFile, "campaign/W1L1.level");
    BOOST_CHECK_EQUAL(campaign.getLevel(0).mPath, "packs/wing1/W1L1.level");
    BOOST_CHECK_EQUAL(campaign.getLevel(23).mFile, "campaign/W6B.level");
    BOOST_CHECK_EQUAL(campaign.getLevel(23).mPath, "packs/wing6/W6B.level");
    BOOST_CHECK_EQUAL(campaign.findLevelByFile("campaign/Twice.level"), campaign.getNumLevels());
    BOOST_CHECK_EQUAL(campaign.findLevelInWing(2, false, 1), 5u);
    BOOST_CHECK_EQUAL(campaign.findLevelInWing(2, true, 0), 7u);
    BOOST_CHECK_EQUAL(campaign.findLevelInWing(2, false, 3), campaign.getNumLevels());

    // Only the package of wing 1: wings 2 to 6 are missing
    std::vector<CampaignPackage> first(1, packages[5]);
    BOOST_REQUIRE(campaign.importPackages(first));
    BOOST_REQUIRE_EQUAL(campaign.getNumLevels(), 4u);
    BOOST_CHECK(campaign.hasMissingWings());
    BOOST_CHECK(campaign.isWingAvailable(1));
    for(uint32_t wing = 2; wing <= Campaign::NUM_WINGS; ++wing)
        BOOST_CHECK(!campaign.isWingAvailable(wing));

    // Progress of the missing wings stays and is written again; the levels of wing 1 are read
    std::istringstream progress("Version 2\nCompleted campaign/W1L1.level campaign/W2L1.level\n"
        "Discovered campaign/W2B.level\nShards campaign/W2L2.level\nDifficulty 1\nFinished\n");
    BOOST_REQUIRE(campaign.importProgress(progress));
    BOOST_CHECK(campaign.isCompleted(0));
    std::ostringstream written;
    campaign.exportProgress(written);
    BOOST_CHECK(written.str().find("Completed campaign/W1L1.level campaign/W2L1.level\n") != std::string::npos);
    BOOST_CHECK(written.str().find("Discovered campaign/W2B.level\n") != std::string::npos);
    BOOST_CHECK(written.str().find("Shards campaign/W2L2.level\n") != std::string::npos);
    // The Heartstone keeps its 3 shards while wings are missing; the shard found in a missing wing still counts
    BOOST_CHECK_EQUAL(campaign.getHeartstoneTotal(), static_cast<size_t>(Campaign::HEARTSTONE_SHARDS));
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 1u);
    BOOST_CHECK(!campaign.isHeartstoneComplete());

    // The map shows the caves of the missing wings locked and their bonus caves hidden
    CampaignWorld world;
    std::istringstream map(moreyaMap(6, 3));
    BOOST_REQUIRE(world.importDefinition(map));
    size_t level = 0;
    BOOST_CHECK(world.getCaveState(campaign, 4, level) == CampaignCaveState::locked);
    BOOST_CHECK_EQUAL(level, campaign.getNumLevels());
    BOOST_CHECK(world.getCaveState(campaign, 7, level) == CampaignCaveState::hidden);

    // Winning all of wing 1 does not finish the campaign: wing 2 is coming, Hell stays locked
    // Hard: a finished campaign on Hard would unlock Hell
    campaign.setDifficulty(2);
    for(size_t i = 1; i < 3; ++i)
    {
        campaign.startLevel(i);
        BOOST_CHECK(campaign.onLevelWon());
    }
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), campaign.getNumLevels());
    BOOST_CHECK(!campaign.isFinished());
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());
    BOOST_CHECK(!campaign.isHellUnlocked());
    BOOST_CHECK_EQUAL(world.findCurrentCave(campaign), 24u);
    campaign.stopCampaign();

    // A package of wing 3 without wing 2 keeps the story levels of wing 3 locked
    std::vector<CampaignPackage> gap;
    gap.push_back(packages[5]);
    gap.push_back(packages[3]);
    BOOST_REQUIRE(campaign.importPackages(gap));
    std::istringstream wingOneDone("Version 2\nCompleted campaign/W1L1.level campaign/W1L2.level campaign/W1L3.level\n");
    BOOST_REQUIRE(campaign.importProgress(wingOneDone));
    BOOST_CHECK(!campaign.isUnlocked(campaign.findLevelByFile("campaign/W3L1.level")));
    // The missing wing 2 also keeps wing 3 from becoming the current level, and the campaign is not finished
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), campaign.getNumLevels());
    BOOST_CHECK(!campaign.isFinished());
    campaign.resetProgress();
}
