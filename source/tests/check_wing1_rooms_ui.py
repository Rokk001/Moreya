#!/usr/bin/env python3
"""Non-compiling check of the research tree padlock and the build navigation placeholders of a campaign level
(wing 1 rooms plan, WR4 and WR8; Global Constraint 8 skirmish and multiplayer unchanged; screen sizes and UI scales).

WR4: in a campaign level a research field the level forbids is darkened and grey with the padlock image
SkillLockMarks/Padlock laid over it (in place of the cross), it is disabled and cannot be queued; allowed fields are
unchanged; the question mark is never used in the tree. WR8: in a campaign level the build navigation of rooms, traps
and doors shows an entry from the start or researched with its real icon, an allowed entry not researched yet as the
question mark placeholder SkillLockMarks/QuestionPlaceholder that cannot be built, a forbidden entry not at all, and
traps and doors only with a built Workshop; spells stay as before. Outside a campaign level (skirmish, multiplayer) the
tree keeps its cross and the navigation shows an entry once it has level 1, as before.

The C++ sources, the look of the research field, the scheme and the navigation layouts are checked for the statements
that implement this, with fixed expected values. Nothing is compiled and the game is not started; the compiled probe
of check_research_tree_ui.py plays the same cases against CEGUI in the integration run.

Usage: python -I source/tests/check_wing1_rooms_ui.py
Exit 0 and "wing1 rooms ui ok" when every item holds.
"""
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = time.perf_counter()
FAILURES = []

# Fixed names of the image contract with the icon package (imageset file, imageset name, the two images)
IMAGESET_FILE = "SkillLockMarks.imageset"
IMAGESET_NAME = "SkillLockMarks"
PADLOCK = "SkillLockMarks/Padlock"
PLACEHOLDER = "SkillLockMarks/QuestionPlaceholder"

# Build navigation buttons of rooms (23) and of traps and doors (17) on this branch, counted once from the layouts
ROOM_BUTTONS = ["DormitoryButton", "ToiletButton", "HatcheryButton", "TavernButton", "SpaButton", "LibraryButton",
    "TrainingHallButton", "TreasuryButton", "WorkshopButton", "CasinoButton", "PrisonButton", "WoodenBridgeButton",
    "TortureButton", "StoneBridgeButton", "CryptButton", "GhostRoomButton", "ArenaButton", "GuardRoomButton",
    "InfirmaryButton", "PrayerTempleButton", "MerchantButton", "HerbGardenButton", "AlchemyLabButton"]
TRAP_BUTTONS = ["WoodenDoorTrapButton", "IronboundDoorTrapButton", "SteelDoorTrapButton", "BarricadeTrapButton",
    "SecretDoorTrapButton", "RunedDoorTrapButton", "CannonButton", "SpikeTrapButton", "BoulderTrapButton",
    "AlarmTrapButton", "FearTrapButton", "GasTrapButton", "LightningTrapButton", "FireburstTrapButton",
    "FreezeTrapButton", "WatchBannerTrapButton", "TriggerTrapButton"]

# Number of campaign and skirmish cases the compiled research tree probe plays (counted once on this branch)
PROBE_CAMPAIGN_CASES = 10
PROBE_SKIRMISH_CASES = 3


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def function(source, signature):
    """Returns the body of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise ValueError("unterminated function " + signature)


def check(condition, message):
    """Records a failed item."""
    if not condition:
        FAILURES.append(message)


def main():
    """Runs every item and prints the result."""
    game = read("source/modes/GameMode.cpp")
    header = read("source/modes/GameMode.h")

    # Image contract and its loading: the scheme loads the imageset with the other imagesets of the game
    scheme = ET.fromstring(read("gui/ODSkin.scheme"))
    imagesets = [(node.get("filename"), node.get("name")) for node in scheme.iter("Imageset")]
    check(imagesets.count((IMAGESET_FILE, IMAGESET_NAME)) == 1, "ODSkin.scheme loads SkillLockMarks.imageset once")
    check('static const std::string RESEARCH_LOCK_IMAGE = "' + PADLOCK + '";' in game, "padlock image name")
    check('static const std::string NAVIGATION_PLACEHOLDER_IMAGE = "' + PLACEHOLDER + '";' in game,
          "question mark placeholder image name")
    check('static const std::string RESEARCH_LOCK_PROPERTY = "LockImage";' in game, "padlock property name")
    check('static const std::string NAVIGATION_PATH_ROOMS = "MainTabControl/Rooms/";' in game and
          'static const std::string NAVIGATION_PATH_TRAPS = "MainTabControl/Traps/";' in game,
          "build navigation pages of rooms and of traps and doors")
    check("MainTabControl/Spells/" not in game, "the spells page is not part of the campaign navigation rules")

    refresh = function(game, "void GameMode::refreshSkillButtonState(")
    # WR4: padlock on a forbidden field of a campaign level, cross elsewhere, darkened grey, disabled
    check("const bool isCampaignLocked = mIsCampaignLevelShown && !isAllowed;" in refresh,
          "WR4: the padlock is tied to a forbidden field of a campaign level")
    check("if(isCampaignLocked)\n        skillButton->setProperty(\"StateImage\", \"\");" in refresh,
          "WR4: the cross gives way to the padlock in a campaign level")
    check("skillButton->setProperty(RESEARCH_LOCK_PROPERTY, isCampaignLocked ? RESEARCH_LOCK_IMAGE : \"\");" in refresh,
          "WR4: the padlock is set on the forbidden field and cleared on every other field")
    check('skillButton->setProperty("StateImage", abortIcon);' in refresh and "skillButton->setEnabled(false);" in refresh,
          "WR4 and skirmish: a forbidden field keeps the cross outside a campaign level and is disabled")
    check('skillButton->setProperty("ButtonImageColour", !isAllowed ? "FF808080"' in refresh,
          "WR4: a forbidden field stays darkened and grey")
    check(refresh.count("RESEARCH_LOCK_IMAGE") == 1 and refresh.count("NAVIGATION_PLACEHOLDER_IMAGE") == 1,
          "WR4: the padlock appears once (tree field), the question mark once (navigation button)")
    placeholder_line = [line for line in refresh.splitlines() if "NAVIGATION_PLACEHOLDER_IMAGE" in line]
    check(len(placeholder_line) == 1 and "castButton->setProperty(\"NormalImage\"" in placeholder_line[0],
          "WR4: the question mark is only set on a navigation button, never on a tree field")
    clicked = function(game, "bool GameMode::skillButtonTreeClicked(")
    check("if(std::find(skillNotAllowed.begin(), skillNotAllowed.end(), type) != skillNotAllowed.end())\n        return false;"
          in clicked, "WR4: a forbidden field cannot be queued")

    # WR8: navigation states of a campaign level, skirmish unchanged
    check("bool isVisible = level > 0;" in refresh, "skirmish: an entry is shown once it has level 1")
    check("const bool isTrapEntry = castButtonName.compare(0, NAVIGATION_PATH_TRAPS.size(), NAVIGATION_PATH_TRAPS) == 0;"
          in refresh, "WR8: traps and doors are told by their navigation page")
    check("castButtonName.compare(0, NAVIGATION_PATH_ROOMS.size(), NAVIGATION_PATH_ROOMS) == 0;" in refresh,
          "WR8: rooms are told by their navigation page")
    check("if(!isAllowed || (isTrapEntry && !mHasWorkshopShown))\n                    isVisible = false;" in refresh,
          "WR8: forbidden entries and traps and doors without a built Workshop are not shown")
    check("isVisible = true;\n                    isPlaceholder = (level == 0);" in refresh,
          "WR8: an allowed entry is shown, as a question mark until it is researched")
    check("if(mIsCampaignLevelShown)\n            {" in refresh, "WR8: the navigation states apply only in a campaign level")
    check("castButton->setUserString(NAVIGATION_REAL_IMAGE, castButton->getProperty(\"NormalImage\"));" in refresh and
          "castButton->getUserString(NAVIGATION_REAL_IMAGE));" in refresh,
          "WR8: the real icon of the layout comes back once the entry is researched")
    check("castButton->setEnabled(!isLockedByLibrary && !isPlaceholder);" in refresh,
          "WR8: a question mark cannot be built; the library lock stays as before")
    check("castButton->setVisible(isVisible);" in refresh, "WR8: the visibility is set for every cast button")

    gui_refresh = function(game, "void GameMode::refreshGuiSkill(")
    check("const bool isCampaignLevel = Campaign::getSingleton().isActive() && "
          "!ODClient::getSingleton().isMultiplayerSession();" in gui_refresh,
          "C8: only a campaign level, never skirmish or multiplayer, uses the new rules")
    check("const bool hasWorkshop = localPlayerSeat->getNbRooms(RoomType::workshop) > 0;" in gui_refresh,
          "WR8: a built Workshop of the keeper is read from the seat the server keeps up to date")
    check("if((mIsCampaignLevelShown != isCampaignLevel) || (mHasWorkshopShown != hasWorkshop))" in gui_refresh and
          gui_refresh.count("forceRefresh = true;") >= 4,
          "WR8: building or losing the Workshop and starting a campaign level refresh the navigation")
    check("bool mIsCampaignLevelShown = false;" in header and "bool mHasWorkshopShown = false;" in header,
          "a new game starts with the skirmish rules until the campaign is read")

    # Look of the research field: padlock over the whole field, relative size (640x480 to 8K, UI scale 80-120 %)
    look = read("gui/OD.looknfeel")
    research = look[look.index('<WidgetLook name="OD/ResearchButton"'):]
    research = research[:research.index("</WidgetLook>")]
    check('<PropertyDefinition name="LockImage" initialValue="" redrawOnWrite="true" />' in research,
          "OD/ResearchButton defines the padlock property, empty by default")
    lock_components = re.findall(r'<ImageryComponent>(?:(?!</ImageryComponent>).)*<ImageProperty name="LockImage" />'
                                 r'(?:(?!</ImageryComponent>).)*</ImageryComponent>', research)
    check(len(lock_components) == 3, "the padlock is drawn in the normal, pushed and disabled look of the field")
    for component in lock_components:
        check('<Dim type="LeftEdge"><UnifiedDim scale="0" type="Width" /></Dim>' in component and
              '<Dim type="TopEdge"><UnifiedDim scale="0" type="Height" /></Dim>' in component and
              '<Dim type="Width"><UnifiedDim scale="1" type="Width" /></Dim>' in component and
              '<Dim type="Height"><UnifiedDim scale="1" type="Height" /></Dim>' in component,
              "the padlock image (drawn for the whole field) covers the whole field")
        check("AbsoluteDim" not in component and '<VertFormat type="Stretched" />' in component and
              '<HorzFormat type="Stretched" />' in component,
              "the padlock scales with the field at every screen size and UI scale")

    # Navigation buttons: each room, trap and door button has its real icon in the layout and a stretched icon look
    for layout, names in (("gui/WindowTabRooms.layout", ROOM_BUTTONS), ("gui/WindowTabTraps.layout", TRAP_BUTTONS)):
        tree = ET.fromstring(read(layout))
        for name in names:
            button = tree.find(".//Window[@name='" + name + "']")
            image = None if button is None else button.find("Property[@name='NormalImage']")
            check(button is not None and button.get("type") == "OD/GameTabButton" and image is not None and
                  image.get("value"), layout + ": " + name + " has its real icon")
    tab_button = look[look.index('<WidgetLook name="OD/GameTabButton">'):]
    tab_button = tab_button[:tab_button.index("</WidgetLook>")]
    check('<PropertyDefinition initialValue="Stretched" name="VertImageFormatting" redrawOnWrite="true" />' in tab_button
          and '<PropertyDefinition initialValue="Stretched" name="HorzImageFormatting" redrawOnWrite="true" />'
          in tab_button, "the question mark fills the navigation button at every screen size and UI scale")

    # The compiled probe of the research tree plays the campaign and skirmish cases
    probe = read("source/tests/check_research_tree_ui.py")
    check(probe.count('"campaign: ') == PROBE_CAMPAIGN_CASES, "the research tree probe plays the campaign cases")
    check(probe.count('"skirmish: ') == PROBE_SKIRMISH_CASES, "the research tree probe plays the skirmish cases")
    check("bool mIsCampaignLevelShown=false;bool mHasWorkshopShown=false;" in probe,
          "the probe starts with the skirmish rules")

    elapsed = time.perf_counter() - START
    print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % elapsed)
    if FAILURES:
        for failure in FAILURES:
            print("FAIL " + failure)
        return 1
    print("wing1 rooms ui ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
