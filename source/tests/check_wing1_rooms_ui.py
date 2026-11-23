#!/usr/bin/env python3
"""Non-compiling check of the campaign level marks in the research tree and the build navigation (wing 1 rooms plan,
WR4, WR8 and WR10; Global Constraint 8 skirmish and multiplayer unchanged; screen sizes and UI scales).

In a campaign level, in the research tree of rooms, spells, traps and doors:
- an entry available from the start or researched shows its real icon, as before;
- an entry the level allows but the keeper has not researched yet shows its real icon darkened with the padlock image
  SkillLockMarks/Padlock on it; it can still be queued and researched;
- an entry the level forbids shows the question mark SkillLockMarks/QuestionPlaceholder in place of its icon and
  cannot be clicked.
The build navigation of a campaign level shows only researched entries the level allows, with their real icon and no
mark (owner decision of 2026-11-23: padlock and question mark only in the research window); traps and doors are not
shown there while the keeper has no built Workshop. WR10: the tree padlock sits in the icon area inside the tile frame.
Outside a campaign level (skirmish, multiplayer) the tree keeps its cross and the navigation shows an entry once it has
level 1, as before.

The C++ sources, the looks, the scheme and the layouts are checked for the statements that implement this, with fixed
expected values. Nothing is compiled and the game is not started; the compiled probe of check_research_tree_ui.py
plays the same cases against CEGUI in the integration run.

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

# Build navigation buttons of rooms (23), of traps and doors (17) and of spells (24) on this branch, counted once from
# the layouts
ROOM_BUTTONS = ["DormitoryButton", "ToiletButton", "HatcheryButton", "TavernButton", "SpaButton", "LibraryButton",
    "TrainingHallButton", "TreasuryButton", "WorkshopButton", "CasinoButton", "PrisonButton", "WoodenBridgeButton",
    "TortureButton", "StoneBridgeButton", "CryptButton", "GhostRoomButton", "ArenaButton", "GuardRoomButton",
    "InfirmaryButton", "PrayerTempleButton", "MerchantButton", "HerbGardenButton", "AlchemyLabButton"]
TRAP_BUTTONS = ["WoodenDoorTrapButton", "IronboundDoorTrapButton", "SteelDoorTrapButton", "BarricadeTrapButton",
    "SecretDoorTrapButton", "RunedDoorTrapButton", "CannonButton", "SpikeTrapButton", "BoulderTrapButton",
    "AlarmTrapButton", "FearTrapButton", "GasTrapButton", "LightningTrapButton", "FireburstTrapButton",
    "FreezeTrapButton", "WatchBannerTrapButton", "TriggerTrapButton"]
SPELL_BUTTONS = ["SummonWorkerButton", "CallToWarButton", "CreatureHealButton", "CreatureExplosionButton",
    "CreatureHasteButton", "CreatureDefenseButton", "CreatureSlowButton", "CreatureStrengthButton", "CreatureWeakButton",
    "SpellEyeEvilButton", "CreateGoldButton", "LightningButton", "TremorButton", "HexenHenButton", "DefectorButton",
    "InfernoButton", "PossessButton", "CurseButton", "BlessingButton", "InvisibilityButton", "PlagueButton",
    "BreakWallButton", "RevealEnemyButton", "SummonChampionButton"]

# Number of campaign and skirmish cases the compiled research tree probe plays (counted once on this branch)
PROBE_CAMPAIGN_CASES = 16
PROBE_SKIRMISH_CASES = 4


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
          "question mark image name")
    check('static const std::string MARK_LOCKED_ICON_COLOUR = "FF666666";' in game, "colour of a darkened icon")
    check('static const std::string RESEARCH_LOCK_PROPERTY = "LockImage";' in game and
          'static const std::string NAVIGATION_MARK_PROPERTY = "MarkImage";' in game and
          'static const std::string NAVIGATION_ICON_COLOUR_PROPERTY = "IconColour";' in game,
          "properties that draw the marks")
    check('static const std::string NAVIGATION_LOCKED = "NavigationLocked";' in game, "user string of a marked button")
    check('static const std::string NAVIGATION_PATH_TRAPS = "MainTabControl/Traps/";' in game,
          "build navigation page of traps and doors")
    check("NAVIGATION_PATH_ROOMS" not in game and "MainTabControl/Spells/" not in game,
          "WR8: rooms and spells follow the rules without a page test")

    refresh = function(game, "void GameMode::refreshSkillButtonState(")
    # WR4: tree marks of a campaign level, cross elsewhere
    check("const bool isCampaignForbidden = mIsCampaignLevelShown && !isAllowed;" in refresh,
          "WR4: the question mark is tied to a forbidden field of a campaign level")
    check("const bool isCampaignLocked = mIsCampaignLevelShown && isAllowed && (level == 0);" in refresh,
          "WR4: the padlock is tied to an allowed field of a campaign level that is not researched yet")
    check("if(isCampaignForbidden)\n        skillButton->setProperty(\"StateImage\", \"\");" in refresh,
          "WR4: the cross gives way to the question mark in a campaign level")
    check("skillButton->setProperty(RESEARCH_LOCK_PROPERTY, isCampaignLocked ? RESEARCH_LOCK_IMAGE : \"\");" in refresh,
          "WR4: the padlock is set on an unresearched allowed field and cleared on every other field")
    check("skillButton->setUserString(RESEARCH_REAL_IMAGE, skillButton->getProperty(\"ButtonImage\"));" in refresh and
          "skillButton->setProperty(\"ButtonImage\", isCampaignForbidden ? CEGUI::String(NAVIGATION_PLACEHOLDER_IMAGE) :\n"
          "        skillButton->getUserString(RESEARCH_REAL_IMAGE));" in refresh,
          "WR4: a forbidden field shows the question mark in place of its icon, every other field its real icon")
    check('skillButton->setProperty("StateImage", abortIcon);' in refresh and "skillButton->setEnabled(false);" in refresh,
          "WR4 and skirmish: a forbidden field keeps the cross outside a campaign level and is disabled")
    check('skillButton->setProperty("ButtonImageColour", !isAllowed ? (isCampaignForbidden ? "FFFFFFFF" : "FF808080") :\n'
          '        (level == 0 ? MARK_LOCKED_ICON_COLOUR : "FFFFFFFF"));' in refresh,
          "WR4: the padlocked icon is darkened, the question mark keeps its colours, skirmish as before")
    clicked = function(game, "bool GameMode::skillButtonTreeClicked(")
    check("if(std::find(skillNotAllowed.begin(), skillNotAllowed.end(), type) != skillNotAllowed.end())\n        return false;"
          in clicked, "WR4: a forbidden field cannot be queued")
    check("isCampaignLocked" not in clicked and "LockImage" not in clicked and "RESEARCH_LOCK" not in clicked,
          "WR4: a padlocked field can still be queued")

    # WR8: navigation states of a campaign level for rooms, spells, traps and doors, skirmish unchanged
    check("bool isVisible = level > 0;" in refresh, "skirmish: an entry is shown once it has level 1")
    check("const bool isTrapEntry = castButtonName.compare(0, NAVIGATION_PATH_TRAPS.size(), NAVIGATION_PATH_TRAPS) == 0;"
          in refresh, "WR8: traps and doors are told by their navigation page")
    check("isBuildEntry" not in refresh, "WR8: spells follow the same rules as rooms, traps and doors")
    check("if(mIsCampaignLevelShown)\n        {" in refresh, "WR8: the navigation rule applies only in a campaign level")
    check("isVisible = isAllowed && (level > 0) && !(isTrapEntry && !mHasWorkshopShown);" in refresh,
          "the navigation shows only researched allowed entries, traps and doors only with a built Workshop")
    check("castButton->setUserString(NAVIGATION_REAL_IMAGE, castButton->getProperty(\"NormalImage\"));" in refresh and
          "castButton->setProperty(\"NormalImage\", castButton->getUserString(NAVIGATION_REAL_IMAGE));" in refresh,
          "every shown navigation entry has its real icon")
    check("castButton->setProperty(NAVIGATION_MARK_PROPERTY, \"\");" in refresh and
          "castButton->setProperty(NAVIGATION_ICON_COLOUR_PROPERTY, \"FFFFFFFF\");" in refresh and
          "castButton->setUserString(NAVIGATION_LOCKED, \"false\");" in refresh,
          "the navigation never carries a padlock or a question mark")
    check("castButton->setEnabled(!isLockedByLibrary);" in refresh,
          "the library lock stays as before")
    check("castButton->setVisible(isVisible && isContentAvailable);" in refresh,
          "WR8: the visibility is set for every cast button, hidden while its room package is missing")
    check(refresh.count("RESEARCH_LOCK_IMAGE") == 1 and refresh.count("NAVIGATION_PLACEHOLDER_IMAGE") == 1,
          "the padlock and the question mark appear in the tree only")

    # WR8: the selectors build or cast nothing for a marked button
    base = read("source/modes/GameEditorModeBase.cpp")
    check("bool isNavigationMarked(const CEGUI::EventArgs& e)" in base and
          "const CEGUI::Window* button = static_cast<const CEGUI::WindowEventArgs&>(e).window;" in base and
          'return (button != nullptr) && button->isUserStringDefined("NavigationLocked") &&\n'
          '            (button->getUserString("NavigationLocked") == "true");' in base,
          "WR8: a marked button is recognised by its user string")
    for selector in ("RoomSelector", "TrapSelector", "SpellSelector"):
        selector_body = function(base, "bool " + selector + "::operator()(")
        guard = "if(isNavigationMarked(e))\n        return true;"
        check(guard in selector_body and selector_body.index(guard) < selector_body.index("mPlayerSelection"),
              "WR8: " + selector + " selects nothing for a marked button")

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

    # WR10, tree: the padlock in the icon area (inside the tile frame), right after the icon and under the state badge,
    # relative size (640x480 to 8K, UI scale 80-120 %)
    look = read("gui/OD.looknfeel").replace("\r\n", "\n")
    research = look[look.index('<WidgetLook name="OD/ResearchButton"'):]
    research = research[:research.index("</WidgetLook>")]
    check('<PropertyDefinition name="LockImage" initialValue="" redrawOnWrite="true" />' in research,
          "OD/ResearchButton defines the padlock property, empty by default")
    components = re.findall(r'<ImageryComponent>(?:(?!</ImageryComponent>).)*</ImageryComponent>', research)
    icon_area = ('<Area><Dim type="LeftEdge"><UnifiedDim scale="0.1" type="Width" /></Dim><Dim type="TopEdge">'
                 '<UnifiedDim scale="0.1" type="Height" /></Dim><Dim type="Width"><UnifiedDim scale="0.8" type="Width" />'
                 '</Dim><Dim type="Height"><UnifiedDim scale="0.8" type="Height" /></Dim></Area>')
    lock_positions = [i for i, component in enumerate(components) if '<ImageProperty name="LockImage" />' in component]
    check(len(lock_positions) == 3, "the padlock is drawn in the normal, pushed and disabled look of the field")
    for position in lock_positions:
        component = components[position]
        check(position > 0 and '<ImageProperty name="ButtonImage" />' in components[position - 1],
              "the padlock is drawn right over the icon")
        check(icon_area in component and position > 0 and icon_area in components[position - 1],
              "the padlock covers exactly the icon area inside the tile frame")
        check("AbsoluteDim" not in component and '<VertFormat type="Stretched" />' in component and
              '<HorzFormat type="Stretched" />' in component,
              "the padlock scales with the field at every screen size and UI scale")
    sections = re.findall(r'<ImagerySection name="research(?:_pushed|_disabled)?">.*?</ImagerySection>', research,
                          re.S)
    check(len(sections) == 3, "the field has its normal, pushed and disabled look")
    for section in sections:
        check('name="LockImage"' in section and 'name="StateImage"' in section and
              section.index('name="LockImage"') < section.index('name="StateImage"'),
              "the queue and research badges stay visible over the padlock")

    # WR10, navigation: the mark between the icon and the frame in every state, relative size
    tab_button = look[look.index('<WidgetLook name="OD/GameTabButton">'):]
    tab_button = tab_button[:tab_button.index("</WidgetLook>")]
    check('<PropertyDefinition initialValue="" name="MarkImage" redrawOnWrite="true" />' in tab_button and
          '<PropertyDefinition initialValue="FFFFFFFF" name="IconColour" redrawOnWrite="true" />' in tab_button,
          "OD/GameTabButton defines the mark, empty by default, and the icon colour, white by default")
    normal = re.search(r'<ImagerySection name="normal">.*?</ImagerySection>', tab_button, re.S).group(0)
    check('<ImageProperty name="NormalImage" />' in normal and '<ColourRectProperty name="IconColour" />' in normal,
          "the icon is drawn in the icon colour")
    mark = re.search(r'<ImagerySection name="mark">.*?</ImagerySection>', tab_button, re.S)
    check(mark is not None and '<ImageProperty name="MarkImage" />' in mark.group(0) and
          '<Dim type="Width"><UnifiedDim scale="1" type="Width" /></Dim>' in mark.group(0) and
          '<Dim type="Height"><UnifiedDim scale="1" type="Height" /></Dim>' in mark.group(0) and
          '<VertFormatProperty name="VertImageFormatting" />' in mark.group(0) and
          '<HorzFormatProperty name="HorzImageFormatting" />' in mark.group(0),
          "the mark covers the icon area and scales with the button")
    states = re.findall(r'<StateImagery name="(\w+)">(.*?)</StateImagery>', tab_button, re.S)
    check(sorted(name for name, _ in states) == ["Disabled", "Hover", "Normal", "Pushed", "PushedOff"],
          "the navigation button has its five states")
    for name, state in states:
        check('<Layer priority="1">\n                <Section section="normal" />\n'
              '                <Section section="mark" />\n            </Layer>' in state,
              "WR10: the mark is drawn over the icon in the " + name + " state")
        check('<Layer priority="2">' in state and state.index('section="mark"') < state.index('<Layer priority="2">'),
              "WR10: the frame of the " + name + " state is drawn over the mark")
    check('<PropertyDefinition initialValue="Stretched" name="VertImageFormatting" redrawOnWrite="true" />' in tab_button
          and '<PropertyDefinition initialValue="Stretched" name="HorzImageFormatting" redrawOnWrite="true" />'
          in tab_button, "the marks fill the navigation button at every screen size and UI scale")

    # Navigation buttons: each room, spell, trap and door button has its real icon in the layout
    for layout, names in (("gui/WindowTabRooms.layout", ROOM_BUTTONS), ("gui/WindowTabTraps.layout", TRAP_BUTTONS),
                          ("gui/WindowTabSpells.layout", SPELL_BUTTONS)):
        tree = ET.fromstring(read(layout))
        for name in names:
            button = tree.find(".//Window[@name='" + name + "']")
            image = None if button is None else button.find("Property[@name='NormalImage']")
            check(button is not None and button.get("type") == "OD/GameTabButton" and image is not None and
                  image.get("value"), layout + ": " + name + " has its real icon")

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
