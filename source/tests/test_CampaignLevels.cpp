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

#define BOOST_TEST_MODULE CampaignLevels
#include "BoostTestTargetConfig.h"

#include "game/Campaign.h"

#include <sstream>
#include <string>

static const std::string definition =
    "[Level]\n"
    "File=campaign/One.level\n"
    "Title=First\n";

//! \brief Hell stays locked until the campaign was finished on hard; the finished set is saved and read again,
//! a progress file without the Finished line loads with nothing finished, and a new campaign keeps the set.
BOOST_AUTO_TEST_CASE(test_hell_unlock_and_finished_set)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream def(definition);
    BOOST_REQUIRE(campaign.importDefinition(def));

    // A progress file without the Finished line: nothing finished, Hell locked.
    std::istringstream old("Version 2\nCompleted\nDiscovered\nDifficulty 1\n");
    BOOST_REQUIRE(campaign.importProgress(old));
    BOOST_CHECK(!campaign.isHellUnlocked());

    // Finished on normal does not unlock Hell, finished on hard does.
    std::istringstream normalOnly("Version 2\nCompleted\nDiscovered\nDifficulty 1\nFinished normal\n");
    BOOST_REQUIRE(campaign.importProgress(normalOnly));
    BOOST_CHECK(!campaign.isHellUnlocked());
    std::istringstream hard("Version 2\nCompleted\nDiscovered\nDifficulty 2\nFinished normal hard\n");
    BOOST_REQUIRE(campaign.importProgress(hard));
    BOOST_CHECK(campaign.isHellUnlocked());

    // The finished set survives an export and import.
    std::ostringstream out;
    campaign.exportProgress(out);
    std::istringstream again(out.str());
    BOOST_REQUIRE(campaign.importProgress(again));
    BOOST_CHECK(campaign.isHellUnlocked());

    // Starting a new campaign keeps the finished set.
    campaign.resetProgress();
    BOOST_CHECK(campaign.isHellUnlocked());
}

//! Two story levels and a bonus level for the campaign end and the old progress checks
static const std::string twoLevels =
    "[Level]\n"
    "File=campaign/One.level\n"
    "Title=First\n"
    "[Level]\n"
    "File=campaign/Two.level\n"
    "Title=Second\n"
    "[Level]\n"
    "File=campaign/Hidden.level\n"
    "Title=Hidden\n"
    "Bonus=1\n";

//! \brief Old campaign progress (a file without the Version line) is dropped except the chosen difficulty: no
//! level, found bonus level, shard, unlocked item, finished difficulty or kept creature survives, and the next
//! save writes a fresh progress of the current format with that difficulty.
BOOST_AUTO_TEST_CASE(test_old_progress_keeps_only_difficulty)
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream def(twoLevels);
    BOOST_REQUIRE(campaign.importDefinition(def));
    campaign.setProgressPath("");
    campaign.stopCampaign();

    std::istringstream old("Completed campaign/One.level campaign/Two.level 0 1\n"
        "Discovered campaign/Hidden.level 2\nShards campaign/One.level\n"
        "Unlocked campaign/Hidden.level Epic SomeItem\nDifficulty 2\nFinished normal hard\n"
        "KeptMinion Knight 4\n");
    BOOST_REQUIRE(campaign.importProgress(old));
    BOOST_CHECK(!campaign.hasProgress());
    BOOST_CHECK(!campaign.isCompleted(0));
    BOOST_CHECK(!campaign.isCompleted(1));
    BOOST_CHECK(!campaign.isDiscovered(2));
    BOOST_CHECK_EQUAL(campaign.getHeartstonePieces(), 0u);
    BOOST_CHECK(campaign.getUnlockedItems().empty());
    BOOST_CHECK(!campaign.isHellUnlocked());
    BOOST_CHECK(!campaign.isFinished());
    BOOST_CHECK_EQUAL(campaign.getCurrentLevel(), 0u);
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), 2u);

    std::ostringstream fresh;
    campaign.exportProgress(fresh);
    BOOST_CHECK(fresh.str().find("Version 2\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("Completed\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("Discovered\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("Shards\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("Unlocked") == std::string::npos);
    BOOST_CHECK(fresh.str().find("Difficulty 2\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("Finished\n") != std::string::npos);
    BOOST_CHECK(fresh.str().find("KeptMinion") == std::string::npos);

    // The same lines in a progress file of the current format are kept
    std::istringstream current("Version 2\nCompleted campaign/One.level\nDifficulty 2\nFinished hard\n");
    BOOST_REQUIRE(campaign.importProgress(current));
    BOOST_CHECK(campaign.isCompleted(0));
    BOOST_CHECK(campaign.isHellUnlocked());
    BOOST_CHECK_EQUAL(campaign.getDifficulty(), 2u);
}

//! \brief The campaign end message has the decided text and follows exactly the wins that leave every story level
//! defeated: not a win before the last story level, not a lost level, not a second time after it was shown, but
//! every replay won after the end; a new campaign starts without it.
BOOST_AUTO_TEST_CASE(test_campaign_end_message)
{
    BOOST_CHECK_EQUAL(Campaign::CAMPAIGN_END_MESSAGE, "Moreya stands. The campaign is complete.");

    Campaign& campaign = Campaign::getSingleton();
    std::istringstream def(twoLevels);
    BOOST_REQUIRE(campaign.importDefinition(def));
    campaign.setProgressPath("");
    campaign.resetProgress();
    campaign.stopCampaign();
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());

    // The first story level won: the next one is left, the map follows
    campaign.startLevel(0);
    BOOST_REQUIRE(campaign.onLevelWon());
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());
    campaign.clearPlayedLevel();

    // The last story level lost: no end
    campaign.startLevel(1);
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());
    campaign.stopCampaign();
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());

    // The last story level won: every guild is defeated and the end message replaces the map; the bonus level
    // that was not played does not hold it back
    campaign.startLevel(1);
    BOOST_REQUIRE(campaign.onLevelWon());
    BOOST_CHECK(campaign.isFinished());
    BOOST_CHECK(campaign.isPlayedLevelCampaignEnd());
    campaign.clearPlayedLevel();
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());

    // Opening the campaign again: the levels can be replayed; a replay won ends with the message again
    BOOST_CHECK(campaign.isUnlocked(0));
    campaign.startLevel(0);
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());
    BOOST_REQUIRE(campaign.onLevelWon());
    BOOST_CHECK(campaign.isPlayedLevelCampaignEnd());
    campaign.stopCampaign();
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());

    // A new campaign: winning the first level shows the map again
    campaign.resetProgress();
    campaign.startLevel(0);
    BOOST_REQUIRE(campaign.onLevelWon());
    BOOST_CHECK(!campaign.isPlayedLevelCampaignEnd());
    campaign.stopCampaign();
}
