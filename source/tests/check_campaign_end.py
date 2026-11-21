#!/usr/bin/env python3
"""Static check of the campaign end and of old campaign progress; compiles nothing and starts no game.

Campaign end: after a win that leaves every story level defeated the campaign menu does not draw the map of Moreya;
it shows the message "Moreya stands. The campaign is complete." alone, and closing it (Close, Back or the frame's close
button) shows the main menu. Opening the campaign again shows the map, so played levels can be replayed; the guild
panel stays empty for a finished campaign; the main menu offers a new campaign. The decision itself
(Campaign::isPlayedLevelCampaignEnd) is covered by the Boost test test_campaign_end_message (test_CampaignLevels.cpp).

Old progress: a progress file without the Version line keeps only its difficulty; the Boost test
test_old_progress_keeps_only_difficulty covers it at run time.
"""
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: The end message decided by the owner, word for word.
END_MESSAGE = "Moreya stands. The campaign is complete."


def read(path):
    """Returns the text of a file of the repository."""
    return (ROOT / path).read_text(encoding="utf-8")


def body(source, signature):
    """Returns the complete function that starts with signature (braces counted)."""
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    """Runs every assertion and reports each failure."""
    started = time.monotonic()
    failures = []

    def check(condition, text):
        """Records text as a failure when condition is false."""
        if not condition:
            failures.append(text)

    campaign = read("source/game/Campaign.cpp")
    header = read("source/game/Campaign.h")
    menu = read("source/modes/MenuModeCampaign.cpp")
    menu_header = read("source/modes/MenuModeCampaign.h")
    main_menu = read("source/modes/MenuModeMain.cpp")
    tests = read("source/tests/test_CampaignLevels.cpp")

    # The message text, once, in the campaign
    check(campaign.count('"' + END_MESSAGE + '"') == 1, "Campaign.cpp must define the end message word for word once")
    check("static const std::string CAMPAIGN_END_MESSAGE;" in header, "Campaign.h must declare CAMPAIGN_END_MESSAGE")
    check("bool isPlayedLevelCampaignEnd() const;" in header, "Campaign.h must declare isPlayedLevelCampaignEnd")
    end = body(campaign, "bool Campaign::isPlayedLevelCampaignEnd(")
    complete = body(campaign, "bool Campaign::isCampaignCompleteNoLock(")
    check("mPlayedLevelWon" in end and "isCampaignCompleteNoLock()" in end
          and "getCurrentLevelNoLock() == mLevels.size()" in complete,
          "the campaign ends only after a won level that leaves no story level undefeated")
    # A missing wing package keeps the campaign open: the map shows the wing locked instead of the end message
    check("mMissingWings.empty()" in complete, "the campaign ends only while no wing package is missing")

    # The menu: the end replaces the map and the debriefing, then the main menu follows
    activate = body(menu, "void MenuModeCampaign::activate(")
    check("campaign.isPlayedLevelCampaignEnd()" in activate, "activate must ask whether the campaign ended")
    end_start = activate.index("if(campaign.isPlayedLevelCampaignEnd())")
    end_block = body(activate[end_start:], "if(campaign.isPlayedLevelCampaignEnd())")
    for token in ("mCampaignEnd = true;", "mResultText = Campaign::CAMPAIGN_END_MESSAGE;"):
        check(token in end_block, "the campaign end decision must contain " + token)
    check(re.search(r"\}\s*else if\(playedLevel < campaign\.getNumLevels\(\)\)", activate[end_start:]) is not None,
          "the end message must replace the debriefing of the last level")
    show_start = activate.index("if(mCampaignEnd)")
    show_block = body(activate[show_start:], "if(mCampaignEnd)")
    for token in ("campaign.clearPlayedLevel();", "setMapVisible(false);", "showDebriefing();", "return;"):
        check(token in show_block, "the campaign end block must contain " + token)
    for block in (end_block, show_block):
        for token in ("fillMap()", "loadWorld()", "Debriefing - ", "fillGuildPanel"):
            check(token not in block, "the campaign end must not draw the map or a debriefing: " + token)
    check(end_start < show_start < activate.index("loadWorld()") < activate.index("fillMap();"),
          "the end must be decided and shown before the map is loaded and drawn")
    check("setMapVisible(true);" in activate, "a normal opening of the campaign must show the map again")
    check("You have completed the campaign." not in menu, "no second campaign end text after a won level")
    visible = body(menu, "void MenuModeCampaign::setMapVisible(")
    for name in ("CMP_MAP", "CMP_CONTROL_BACKDROP", "CMP_BUTTON_DIFFICULTY", "CMP_CHECK_RELATIONSHIPS", "CMP_BUTTON_BACK"):
        check("getChild(%s)->setVisible(visible)" % name in visible, "setMapVisible must switch " + name)
    close = body(menu, "bool MenuModeCampaign::briefingClosePressed(")
    check(re.search(r"if\(mCampaignEnd\)\s*return backButtonPressed\(e\);", close) is not None,
          "closing the end message must lead to the main menu")
    back = body(menu, "bool MenuModeCampaign::backButtonPressed(")
    check("mCampaignEnd = false;" in back and "requestMode(AbstractModeManager::MENU_MAIN)" in back,
          "the back path must end the message and show the main menu")
    check("bool mCampaignEnd;" in menu_header and "mCampaignEnd(false)" in menu,
          "the menu must keep and initialise the end state")
    guild = body(menu, "void MenuModeCampaign::fillGuildPanel(")
    # findCurrentCave returns the number of caves for a finished campaign (Boost test_world_map_progress pins it)
    check("mWorld.findCurrentCave(" in guild and
          re.search(r"if\(cave >= mWorld\.getCaves\(\)\.size\(\)\)\s*return;", guild) is not None,
          "the guild panel must stay empty for a finished campaign (nobody in front of the gate)")
    check("newCampaignPressed" in main_menu and "resetProgress()" in main_menu,
          "the main menu must still offer a new campaign")

    # Old progress keeps only the difficulty
    progress = body(campaign, "bool Campaign::importProgress(")
    difficulty_at = progress.index('keyword == "Difficulty"')
    versioned_at = progress.index("if(!versioned)")
    finished_at = progress.index('keyword == "Finished"')
    check(difficulty_at < versioned_at < finished_at,
          "an unversioned progress file must keep the difficulty and drop the finished difficulties")
    check(progress.count("if(!versioned)") == 1, "one guard drops every other line of an old progress file")

    # The Boost cases exist with their comments
    for case in ("test_old_progress_keeps_only_difficulty", "test_campaign_end_message"):
        match = re.search(r"//! \\brief [^\n]+\n(?://![^\n]*\n)*BOOST_AUTO_TEST_CASE\(%s\)" % case, tests)
        check(match is not None, "test_CampaignLevels.cpp must have the commented Boost case " + case)
    check('"Moreya stands. The campaign is complete."' in tests, "the Boost test must pin the message word for word")

    print('ODP_TEST_PHASE {"name":"campaign end","seconds":%.2f}' % (time.monotonic() - started))
    for failure in failures:
        print("FAIL " + failure)
    if failures:
        return 1
    print("campaign end message instead of the map, then main menu; old progress keeps only the difficulty: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
