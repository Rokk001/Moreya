/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#define BOOST_TEST_MODULE CreatureSkillTreeView
#include "BoostTestTargetConfig.h"
#include "creatureskill/CreatureSkillTreeView.h"

#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

using namespace CreatureSkillTree;

namespace
{
//! \brief Loads config/creatureSkills.cfg: from OD_TEST_CREATURE_SKILLS_FILE, else from the working folder or one of
//! its parent folders.
bool loadConfig(SkillTreeConfig& config)
{
    std::vector<std::string> candidates;
    const char* variable = std::getenv("OD_TEST_CREATURE_SKILLS_FILE");
    if(variable != nullptr)
        candidates.push_back(variable);
    std::string prefix;
    for(int i = 0; i < 5; ++i)
    {
        candidates.push_back(prefix + "config/creatureSkills.cfg");
        prefix += "../";
    }
    for(std::vector<std::string>::const_iterator it = candidates.begin(); it != candidates.end(); ++it)
    {
        std::ifstream file(it->c_str());
        if(!file)
            continue;
        std::string error;
        return config.load(file, error);
    }
    return false;
}

//! \brief The skill keys of the Orc in config/creatures.cfg.
TypeInfo orcType()
{
    TypeInfo orc;
    orc.mGroup = "blocker";
    orc.mFamily = "greenskin";
    orc.mTierFour = "T4_Orc";
    return orc;
}
}

//! \brief Checks the skill id at every column and row of the Orc's tree and the column titles.
BOOST_AUTO_TEST_CASE(orc_layout)
{
    SkillTreeConfig config;
    BOOST_REQUIRE(loadConfig(config));
    SkillBuild build;
    const TreeView view = buildTreeView(config, orcType(), build, ViewRules());
    BOOST_REQUIRE_EQUAL(view.mColumns.size(), 4u);
    const char* const paths[4] = {"Arms", "Bulwark", "War Cries", "Greenskin"};
    const char* const ids[4][3] = {{"BLK_A1", "BLK_A2", "BLK_A3"}, {"BLK_B1", "BLK_B2", "BLK_B3"},
        {"BLK_C1", "BLK_C2", "BLK_C3"}, {"GRN_1", "GRN_2", "GRN_3"}};
    for(std::size_t column = 0; column < 4; ++column)
    {
        BOOST_CHECK_EQUAL(view.mColumns[column].mPath, std::string(paths[column]));
        BOOST_REQUIRE_EQUAL(view.mColumns[column].mTiers.size(), 3u);
        for(std::size_t tier = 0; tier < 3; ++tier)
            BOOST_CHECK_EQUAL(view.mColumns[column].mTiers[tier].mId, std::string(ids[column][tier]));
    }
    BOOST_CHECK(view.mHasTierFour);
    BOOST_CHECK_EQUAL(view.mTierFour.mId, std::string("T4_Orc"));
}

//! \brief Checks the unlock state and bar text for a given set of ranks, including the tier 4 limit of 20 points.
BOOST_AUTO_TEST_CASE(orc_unlock_and_bars)
{
    SkillTreeConfig config;
    BOOST_REQUIRE(loadConfig(config));
    SkillBuild build;
    build.mRanks["BLK_A1"] = 5;
    build.mRanks["BLK_A2"] = 1;
    build.mRanks["BLK_B1"] = 3;
    TreeView view = buildTreeView(config, orcType(), build, ViewRules());
    // Arms: tier 2 unlocked by 5 ranks in tier 1, tier 3 locked with only 1 rank in tier 2
    BOOST_CHECK(view.mColumns[0].mTiers[0].mUnlocked);
    BOOST_CHECK(view.mColumns[0].mTiers[1].mUnlocked);
    BOOST_CHECK(!view.mColumns[0].mTiers[2].mUnlocked);
    BOOST_CHECK_EQUAL(view.mColumns[0].mTiers[0].mBarText, std::string("5/5"));
    BOOST_CHECK_EQUAL(view.mColumns[0].mTiers[1].mBarText, std::string("1/5"));
    BOOST_CHECK_EQUAL(view.mColumns[0].mTiers[2].mBarText, std::string("0/5"));
    // Bulwark: tier 2 unlocked by 3 ranks in tier 1; War Cries: only tier 1 unlocked
    BOOST_CHECK(view.mColumns[1].mTiers[1].mUnlocked);
    BOOST_CHECK(!view.mColumns[1].mTiers[2].mUnlocked);
    BOOST_CHECK(view.mColumns[2].mTiers[0].mUnlocked);
    BOOST_CHECK(!view.mColumns[2].mTiers[1].mUnlocked);
    BOOST_CHECK_EQUAL(view.mColumns[1].mTiers[0].mBarText, std::string("3/5"));
    // 9 points spent: tier 4 locked with bar 0/1
    BOOST_CHECK(!view.mTierFour.mUnlocked);
    BOOST_CHECK_EQUAL(view.mTierFour.mBarText, std::string("0/1"));

    build.mRanks["BLK_A2"] = 2;
    build.mRanks["BLK_A3"] = 5;
    build.mRanks["BLK_B1"] = 5;
    build.mRanks["GRN_1"] = 3;
    view = buildTreeView(config, orcType(), build, ViewRules());
    // 20 points spent: tier 3 of Arms and tier 4 unlocked
    BOOST_CHECK(view.mColumns[0].mTiers[2].mUnlocked);
    BOOST_CHECK(view.mTierFour.mUnlocked);
    build.mRanks["T4_Orc"] = 1;
    view = buildTreeView(config, orcType(), build, ViewRules());
    BOOST_CHECK_EQUAL(view.mTierFour.mBarText, std::string("1/1"));
}

//! \brief Checks that the primary path of the chosen template is highlighted and nothing while no template is chosen.
BOOST_AUTO_TEST_CASE(orc_template_highlight)
{
    SkillTreeConfig config;
    BOOST_REQUIRE(loadConfig(config));
    SkillBuild build;
    TreeView view = buildTreeView(config, orcType(), build, ViewRules());
    for(std::size_t column = 0; column < view.mColumns.size(); ++column)
        BOOST_CHECK(!view.mColumns[column].mHighlighted);
    // Template index 1 of the blocker group is "Guardian" with the primary path Bulwark
    build.mTemplate = 1;
    view = buildTreeView(config, orcType(), build, ViewRules());
    BOOST_CHECK(!view.mColumns[0].mHighlighted);
    BOOST_CHECK(view.mColumns[1].mHighlighted);
    BOOST_CHECK(!view.mColumns[2].mHighlighted);
    BOOST_CHECK(!view.mColumns[3].mHighlighted);
}

//! \brief Checks the four tooltip lines of a passive skill, an active skill with mana and cooldown, a WHIRLWIND
//! skill and the tier 4 skill.
BOOST_AUTO_TEST_CASE(orc_tooltips)
{
    SkillTreeConfig config;
    BOOST_REQUIRE(loadConfig(config));
    SkillBuild build;
    build.mRanks["BLK_A1"] = 3;
    build.mRanks["BLK_A2"] = 2;
    build.mRanks["BLK_A3"] = 2;
    build.mRanks["BLK_C1"] = 1;
    build.mRanks["BLK_C2"] = 2;
    const TreeView view = buildTreeView(config, orcType(), build, ViewRules());

    const std::vector<std::string>& passive = view.mColumns[0].mTiers[0].mTooltip;
    BOOST_REQUIRE_EQUAL(passive.size(), 4u);
    BOOST_CHECK_EQUAL(passive[0], std::string("Weapon Training"));
    BOOST_CHECK_EQUAL(passive[1], std::string("Effect: Damage 0.939%"));
    BOOST_CHECK_EQUAL(passive[2], std::string("Mana: none"));
    BOOST_CHECK_EQUAL(passive[3], std::string("Cooldown: none"));

    const std::vector<std::string>& active = view.mColumns[0].mTiers[2].mTooltip;
    BOOST_REQUIRE_EQUAL(active.size(), 4u);
    BOOST_CHECK_EQUAL(active[0], std::string("Heavy Blow"));
    BOOST_CHECK_EQUAL(active[1], std::string("Effect: Strike 1.146"));
    BOOST_CHECK_EQUAL(active[2], std::string("Mana: 5"));
    BOOST_CHECK_EQUAL(active[3], std::string("Cooldown: 30 turns"));

    // Rank 0 shows the values of rank 1
    const std::vector<std::string>& whirlwind = view.mColumns[2].mTiers[2].mTooltip;
    BOOST_REQUIRE_EQUAL(whirlwind.size(), 4u);
    BOOST_CHECK_EQUAL(whirlwind[0], std::string("Cleaving Spin"));
    BOOST_CHECK_EQUAL(whirlwind[1], std::string("Effect: Whirlwind push 1, stun 1"));
    BOOST_CHECK_EQUAL(whirlwind[2], std::string("Mana: 12.5"));
    BOOST_CHECK_EQUAL(whirlwind[3], std::string("Cooldown: 14 turns"));

    const std::vector<std::string>& tierFour = view.mTierFour.mTooltip;
    BOOST_REQUIRE_EQUAL(tierFour.size(), 4u);
    BOOST_CHECK_EQUAL(tierFour[0], std::string("Blood Frenzy"));
    BOOST_CHECK_EQUAL(tierFour[1], std::string("Effect: Strength (self) 1.201"));
    BOOST_CHECK_EQUAL(tierFour[2], std::string("Mana: 30"));
    BOOST_CHECK_EQUAL(tierFour[3], std::string("Cooldown: 140 turns"));
}

//! \brief Checks that a type without skill group (the Champion) has no tree.
BOOST_AUTO_TEST_CASE(type_without_group_has_no_tree)
{
    SkillTreeConfig config;
    BOOST_REQUIRE(loadConfig(config));
    TypeInfo champion;
    const TreeView view = buildTreeView(config, champion, SkillBuild(), ViewRules());
    BOOST_CHECK(view.mColumns.empty());
    BOOST_CHECK(!view.mHasTierFour);
}
