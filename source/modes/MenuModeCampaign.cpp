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

#include "modes/MenuModeCampaign.h"

#include "ai/KeeperAIType.h"
#include "game/Campaign.h"
#include "game/CampaignPackages.h"
#include "game/Seat.h"
#include "gamemap/LevelScript.h"
#include "goals/Goal.h"
#include "goals/GoalLoading.h"
#include "gamemap/GameMap.h"
#include "gamemap/MapHandler.h"
#include "modes/ModeManager.h"
#include "network/ODClient.h"
#include "network/ODServer.h"
#include "network/ServerMode.h"
#include "render/Gui.h"
#include "render/ODFrameListener.h"
#include "sound/MusicPlayer.h"
#include "utils/ContentPackages.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LevelText.h"
#include "utils/LogManager.h"
#include "utils/ResourceManager.h"
#include "utils/Translation.h"
#include "utils/RunLevelTest.h"

#include <CEGUI/CEGUI.h>
#include <CEGUI/BasicImage.h>
#include <CEGUI/ImageManager.h>
#include <CEGUI/RendererModules/Ogre/Renderer.h>
#include <CEGUI/widgets/ProgressBar.h>
#include "boost/filesystem.hpp"

#include <Ogre.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iterator>
#include <sstream>

namespace
{
const std::string CAMPAIGN_PROGRESS_FILE = "campaign.progress";

const std::string CMP_FRAME = "CampaignWindowFrame";
const std::string CMP_TEXT_LOADING = "CampaignWindowFrame/LoadingText";
const std::string CMP_BUTTON_DIFFICULTY = "CampaignWindowFrame/DifficultyButton";
const std::string CMP_CHECK_RELATIONSHIPS = "CampaignWindowFrame/RelationshipsCheckbox";
const std::string CMP_BUTTON_BACK = "CampaignWindowFrame/BackButton";
const std::string CMP_MAP = "CampaignWindowFrame/CampaignMap";
//! Backdrop behind the difficulty, relationships and back controls
const std::string CMP_CONTROL_BACKDROP = "CampaignWindowFrame/ControlBackdrop";
const std::string CMP_BRIEFING = "CampaignWindowFrame/BriefingPanel";
const std::string CMP_BRIEFING_TEXT = "CampaignWindowFrame/BriefingPanel/BriefingText";
static const std::string CMP_BRIEFING_IMAGE = "CampaignWindowFrame/BriefingPanel/BriefingImage";
const std::string CMP_BRIEFING_GOALS = "CampaignWindowFrame/BriefingPanel/BriefingGoals";
static const CEGUI::URect BRIEFING_PREVIEW_PANEL_AREA(
    CEGUI::UDim(0.5f, -336), CEGUI::UDim(0.5f, -352),
    CEGUI::UDim(0.5f, 336), CEGUI::UDim(0.5f, 352));
static const CEGUI::URect BRIEFING_TEXT_PANEL_AREA(
    CEGUI::UDim(0.5f, -300), CEGUI::UDim(0.5f, -210),
    CEGUI::UDim(0.5f, 300), CEGUI::UDim(0.5f, 210));
static const CEGUI::URect BRIEFING_PREVIEW_TEXT_AREA(
    CEGUI::UDim(0, 16), CEGUI::UDim(0, 392),
    CEGUI::UDim(1, -16), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_TEXT_AREA(
    CEGUI::UDim(0, 16), CEGUI::UDim(0, 16),
    CEGUI::UDim(1, -16), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_PREVIEW_STORY_AREA(
    CEGUI::UDim(0, 16), CEGUI::UDim(0, 392),
    CEGUI::UDim(0.4f, -8), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_PREVIEW_GOALS_AREA(
    CEGUI::UDim(0.4f, 8), CEGUI::UDim(0, 392),
    CEGUI::UDim(1, -16), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_STORY_AREA(
    CEGUI::UDim(0, 16), CEGUI::UDim(0, 16),
    CEGUI::UDim(0.4f, -8), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_GOALS_AREA(
    CEGUI::UDim(0.4f, 8), CEGUI::UDim(0, 16),
    CEGUI::UDim(1, -16), CEGUI::UDim(1, -72));
static const CEGUI::URect BRIEFING_CLOSE_AREA(
    CEGUI::UDim(0.5f, 8), CEGUI::UDim(1, -56),
    CEGUI::UDim(1, -16), CEGUI::UDim(1, -16));
const std::string CMP_BRIEFING_START = "CampaignWindowFrame/BriefingPanel/BriefingStartButton";
const std::string CMP_BRIEFING_CLOSE = "CampaignWindowFrame/BriefingPanel/BriefingCloseButton";

const std::string WORLD_DIRECTORY = "gui/campaign/";
const std::string WORLD_DEFINITION_FILE = "campaign-world.json";
const std::string WORLD_IMAGE_PREFIX = "CampaignWorld/";
//! Name prefix of every window created on the map
const std::string WORLD_WINDOW_PREFIX = "CampaignWorld_";
const std::string CAMPAIGN_TITLE = "Moreya";
//! Menu places of the camera: the campaign table and the green portal at the far end of the forecourt, into which the
//! camera flies before a campaign level is loaded (config/mainmenuscene.cfg)
const std::string PLACE_CAMPAIGN = "campaign";
const std::string PLACE_PORTAL = "portal";

//! Size of the tooltip window and its distance from the mouse, in design pixels of the 1024 x 768 layout; the
//! window is scaled with the layout (screen size and UI scale) and never larger than the map
const float TOOLTIP_WIDTH = 420.0f;
const float TOOLTIP_HEIGHT = 150.0f;
const float TOOLTIP_OFFSET = 48.0f;
//! Inner margin of the hover display: share of the tablet width left and right and of its height above and below
//! its text (the text stays inside the recess of tooltip_plaque.png)
const float TOOLTIP_INSET_X = 0.09f;
const float TOOLTIP_INSET_Y = 0.17f;
//! Size of the ring around the cave under the mouse, relative to the cave marker
const float HOVER_SCALE = 1.0f;
//! The carved art of the map, relative to the campaign art directory (tools/gen_campaign_map_art.py)
const std::string ART_TOOLTIP_PLAQUE = "moreya/tooltip_plaque.png";
const std::string ART_GUILD_PLAQUE = "moreya/guild_plaque.png";
const std::string ART_CURRENT_GLOW = "moreya/current_glow.png";
const std::string ART_CURRENT_POINTER = "moreya/current_pointer.png";
const std::string ART_RAID_EMBER = "moreya/raid_ember.png";
//! The current level: its marker is drawn larger than the others, its glow is a multiple of the marker, its arrow
//! (map pixels) stands above the marker and bobs by POINTER_BOB; glow and arrow pulse once per PULSE_PERIOD seconds
const float CURRENT_CAVE_SCALE = 1.25f;
const float CURRENT_GLOW_SCALE = 2.8f;
const float POINTER_WIDTH = 64.0f;
const float POINTER_HEIGHT = 80.0f;
const float POINTER_GAP = 6.0f;
const float POINTER_BOB = 12.0f;
const float PULSE_PERIOD = 1.6f;
const float TWO_PI = 6.2831853f;
//! The raid trail: distance of its embers and their number, size of an ember, how fast the glow runs along the trail
//! (trail lengths per second) and the size of the guild banner at the attacked cave (map pixels)
const float RAID_EMBER_SPACING = 70.0f;
const size_t RAID_EMBERS_MIN = 4;
const size_t RAID_EMBERS_MAX = 18;
const float RAID_EMBER_SIZE = 28.0f;
const float RAID_TRAIL_SPEED = 0.45f;
const float RAID_BANNER_WIDTH = 40.0f;
const float RAID_BANNER_HEIGHT = 80.0f;
//! Opacity of the locked caves of a greyed out wing
const float LOCKED_CAVE_ALPHA = 0.6f;
//! Aspect ratio (width to height) of the campaign map art
const float MAP_ASPECT_RATIO = 1.6f;
//! Percent value of a completely finished campaign and its factor to a bar fraction
const int PERCENT_FULL = 100;
const float PERCENT_FULL_FLOAT = 100.0f;
//! Layout of the progress texts and bar inside the progress panel, as fractions of its width and height
const float PROGRESS_LEFT = 0.04f;
const float PROGRESS_TEXT_WIDTH = 0.92f;
const float PROGRESS_TEXT_HEIGHT = 0.70f;
const float PROGRESS_BAR_TOP = 0.74f;
const float PROGRESS_BAR_WIDTH = 0.74f;
const float PROGRESS_BAR_HEIGHT = 0.20f;
const float PROGRESS_PERCENT_LEFT = 0.80f;
const float PROGRESS_PERCENT_TOP = 0.68f;
const float PROGRESS_PERCENT_WIDTH = 0.16f;
const float PROGRESS_PERCENT_HEIGHT = 0.32f;
//! Fonts of the texts on the map
const std::string FONT_TITLE = "MedievalSharp-13";
const std::string FONT_WING = "MedievalSharp-8";
const std::string FONT_CAVE = "MedievalSharp-6";
const std::string FONT_GUILD_NAME = "MedievalSharp-10";
const std::string FONT_GUILD_DETAILS = "MedievalSharp-6";
const std::string FONT_PROGRESS = "MedievalSharp-6";
const std::string FONT_TOOLTIP = "MedievalSharp-8";
//! Colours of the texts on the dark map: parchment, gold for the current level and the guild, grey for what is
//! locked
const std::string COLOUR_TEXT = "FFE6D3A3";
const std::string COLOUR_HIGHLIGHT = "FFF2C46A";
const std::string COLOUR_LOCKED = "FF8C8578";

//! \brief Reads the human seat's initial goal context, without loading entities or modifying a map.
//! \return True when a human seat was found and the seats section is complete.
bool readBriefingSeat(std::istream& level, Seat& player)
{
    std::string token;
    while((level >> token) && token != "[Seats]")
    {}
    bool foundPlayer = false;
    while(level >> token)
    {
        if(token == "[/Seats]")
            return foundPlayer;
        if(token != "[Seat]")
            return false;
        std::string line;
        std::string playerType;
        int seatId = -1;
        int goldMined = 0;
        bool seatClosed = false;
        while(std::getline(level, line))
        {
            std::istringstream fields(line);
            std::string key;
            fields >> key;
            if(key == "[/Seat]")
            {
                seatClosed = true;
                break;
            }
            if(key == "seatId")
                fields >> seatId;
            else if(key == "player")
                fields >> playerType;
            else if(key == "goldMined")
                fields >> goldMined;
        }
        if(!seatClosed)
            return false;
        if(playerType == Seat::PLAYER_TYPE_HUMAN && !foundPlayer)
        {
            player.setId(seatId);
            player.addGoldMined(goldMined);
            foundPlayer = true;
        }
    }
    return false;
}

//! \brief Reads grouped main/optional goals or the legacy list using the gameplay parsers.
//! \return True when level goal metadata was read; no game state or script action is executed. The text holds one
//! text reference or text of the level file per line; the caller shows it with Translation::resolveLines.
bool readBriefingGoals(const std::string& path, std::string& descriptions)
{
    std::stringstream level;
    if(!Helper::readFile(path, level, true))
        return false;
    Seat player(nullptr);
    if(!readBriefingSeat(level, player))
        return false;
    std::string token;
    if(!(level >> token) || token != "[Goals]")
        return false;
    descriptions = Translation::makeReference("goal.heading");
    while(level >> token)
    {
        if(token == "[/Goals]")
            break;
        std::unique_ptr<Goal> goal = Goals::loadGoalFromStream(token, level);
        if(goal == nullptr)
            return false;
        descriptions += "\n[image='GoalStatus/Open'] " + goal->getDescription(player);
    }
    if(token != "[/Goals]")
        return false;
    while(level >> token)
    {
        if(token != "[Triggers]")
            continue;
        LevelScript script;
        if(!script.importFromStream(level))
            return false;
        const std::vector<LevelScriptTrigger>& triggers = script.getTriggers();
        std::vector<std::string> mainObjectives;
        std::vector<std::string> optionalObjectives;
        for(const LevelScriptTrigger& trigger : triggers)
        {
            for(const LevelScriptAction& action : trigger.mActions)
            {
                if(action.mType != LevelScriptActionType::objective ||
                   action.mObjectiveGroup == LevelScriptObjectiveGroup::legacy ||
                   (action.mSeatId >= 0 && action.mSeatId != player.getId()))
                    continue;
                if(action.mObjectiveGroup == LevelScriptObjectiveGroup::optional)
                    optionalObjectives.push_back(LevelText::display(action.mText));
                else
                    mainObjectives.push_back(LevelText::display(action.mText));
            }
        }
        if(!mainObjectives.empty() || !optionalObjectives.empty())
        {
            descriptions = Translation::makeReference("goal.main");
            for(const std::string& objective : mainObjectives)
                descriptions += "\n[image='GoalStatus/Open'] " + objective;
            descriptions += "\n\n" + Translation::makeReference("goal.optional");
            for(const std::string& objective : optionalObjectives)
                descriptions += "\n[image='GoalStatus/Open'] " + objective;
            return true;
        }
        for(const LevelScriptTrigger& trigger : triggers)
        {
            for(const LevelScriptAction& action : trigger.mActions)
            {
                if((action.mType != LevelScriptActionType::objective && action.mType != LevelScriptActionType::hint) ||
                   (action.mSeatId >= 0 && action.mSeatId != player.getId()))
                    continue;
                if(action.mType == LevelScriptActionType::hint)
                {
                    descriptions += "\n" + Translation::makeReference("goal.hint", {{"text", action.mText}});
                    continue;
                }
                descriptions += "\n[image='GoalStatus/Open'] " + LevelText::display(action.mText);
            }
        }
        break;
    }
    return true;
}

//! Reads and decodes a PNG file into RGBA bytes. Returns false if it cannot be read.
bool decodeImage(const std::string& path, int& width, int& height, std::vector<uint8_t>& rgba)
{
    std::ifstream file(path.c_str(), std::ios::binary);
    if(!file.is_open())
        return false;

    std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    if(data.empty())
        return false;

    try
    {
        Ogre::DataStreamPtr stream(new Ogre::MemoryDataStream(&data[0], data.size(), false, true));
        Ogre::Image image;
        image.load(stream, "png");
        width = static_cast<int>(image.getWidth());
        height = static_cast<int>(image.getHeight());
        rgba.assign(static_cast<size_t>(width) * height * 4, 0);
        Ogre::PixelBox target(width, height, 1, Ogre::PF_BYTE_RGBA, &rgba[0]);
        Ogre::PixelUtil::bulkPixelConversion(image.getPixelBox(), target);
    }
    catch(const Ogre::Exception&)
    {
        return false;
    }
    return true;
}

//! \brief The folder of the wing package a level was read from, where its own previews, banners and portraits may
//! lie; empty when the level was not read from a package.
std::string packageDirectoryOf(const CampaignLevel& level)
{
    if(level.mPath.empty())
        return std::string();
    return boost::filesystem::path(level.mPath).parent_path().string();
}
} // namespace

//! \brief Connects campaign controls and initializes map and debriefing layout state.
MenuModeCampaign::MenuModeCampaign(ModeManager* modeManager):
    AbstractApplicationMode(modeManager, ModeManager::MENU_CAMPAIGN),
    mWorldLoaded(false),
    mHoverWindow(nullptr),
    mTooltip(nullptr),
    mTooltipPlaque(nullptr),
    mCurrentGlow(nullptr),
    mCurrentPointer(nullptr),
    mCurrentX(0.0f),
    mCurrentY(0.0f),
    mCurrentGlowSize(0.0f),
    mMapTime(0.0f),
    mBriefingLevel(0),
    mPortalLevel(0),
    mPortalFlight(false),
    mDebriefingScale(0.0f),
    mCampaignEnd(false)
{
    CEGUI::Window* window = modeManager->getGui().getGuiSheet(Gui::guiSheet::campaignMenu);

    addEventConnection(
        window->getChild(CMP_BUTTON_DIFFICULTY)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeCampaign::difficultyButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(CMP_BUTTON_BACK)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeCampaign::backButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(CMP_FRAME)->subscribeEvent(
            CEGUI::FrameWindow::EventCloseClicked,
            CEGUI::Event::Subscriber(&MenuModeCampaign::backButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(CMP_BRIEFING_START)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeCampaign::briefingStartPressed, this)
        )
    );
    addEventConnection(
        window->getChild(CMP_BRIEFING_CLOSE)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeCampaign::briefingClosePressed, this)
        )
    );

    // The map keeps the aspect ratio of the art and is centred on the screen
    CEGUI::Window* map = window->getChild(CMP_MAP);
    map->setHorizontalAlignment(CEGUI::HA_CENTRE);
    map->setVerticalAlignment(CEGUI::VA_CENTRE);
    map->setAspectMode(CEGUI::AM_SHRINK);
    map->setAspectRatio(MAP_ASPECT_RATIO);
    addEventConnection(
        map->subscribeEvent(
            CEGUI::Window::EventMouseMove,
            CEGUI::Event::Subscriber(&MenuModeCampaign::mapMoved, this)
        )
    );
    addEventConnection(
        map->subscribeEvent(
            CEGUI::Window::EventMouseLeavesArea,
            CEGUI::Event::Subscriber(&MenuModeCampaign::mapLeft, this)
        )
    );
    addEventConnection(
        map->subscribeEvent(
            CEGUI::Window::EventMouseClick,
            CEGUI::Event::Subscriber(&MenuModeCampaign::mapClicked, this)
        )
    );
}

bool MenuModeCampaign::loadCampaign()
{
    ResourceManager& resources = ResourceManager::getSingleton();
    Campaign& campaign = Campaign::getSingleton();

    // The campaign comes from the wing packages; a missing package leaves its wing locked on the map
    if(!CampaignPackages::loadCampaign(campaign, resources.getGameDataPath()))
    {
        OD_LOG_ERR("Could not read any campaign package below " + resources.getGameDataPath() + "levels/campaign/");
        return false;
    }

    std::string progressPath = resources.getUserDataPath() + CAMPAIGN_PROGRESS_FILE;
    campaign.setProgressPath(progressPath);
    std::ifstream progress(progressPath.c_str());
    if(progress.is_open())
        campaign.importProgress(progress);

    return true;
}

//! \brief Opens the campaign map and logs when a lost-level message is shown.
void MenuModeCampaign::activate()
{
    // Loads the corresponding Gui sheet.
    getModeManager().getGui().loadGuiSheet(Gui::guiSheet::campaignMenu);

    giveFocus();

    // Play the main menu music
    MusicPlayer::getSingleton().play(ConfigManager::getSingleton().getMainMenuMusic());

    // We may come from a finished game: show the menu scene and clean the map
    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    gameMap->clearAll();
    gameMap->setGamePaused(true);
    ODFrameListener::getSingleton().stopGameRenderer();
    ODFrameListener::getSingleton().createMainMenuScene();

    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    window->getChild(CMP_TEXT_LOADING)->setText("");
    // The sheet was hidden for the flight into the portal before the last level was loaded
    window->setVisible(true);
    mPortalFlight = false;

    // Debriefing of the level that was played last
    mResultText.clear();
    mCampaignEnd = false;
    size_t playedLevel = campaign.getPlayedLevel();
    bool playedLevelWon = false;
    // A win that leaves every guild defeated ends the campaign: the end message and then the main menu, no map
    if(campaign.isPlayedLevelCampaignEnd())
    {
        OD_LOG_INF("Campaign menu shows the campaign end message after level " + Helper::toString(playedLevel));
        mCampaignEnd = true;
        mResultText = Campaign::getEndMessage();
    }
    else if(playedLevel < campaign.getNumLevels())
    {
        const CampaignLevel& level = campaign.getLevel(playedLevel);
        playedLevelWon = campaign.getPlayedLevelWon();
        if(playedLevelWon)
        {
            mResultText = Translation::tr("mode.menu.campaign.debriefing", {{"title", LevelText::display(level.mTitle)}}) + "\n\n" + LevelText::display(level.mDebriefing) + "\n\n";
            if(level.mBonus)
            {
                mResultText += Translation::tr("mode.menu.campaign.bonus_cleared");
            }
            else
                mResultText += Translation::tr("mode.menu.campaign.next_unlocked");

            // The numbers of the level, as sent by the server when it was won
            std::string summary = campaign.getLevelSummary();
            if(!summary.empty())
                mResultText += "\n\n" + summary;
        }
        else
        {
            OD_LOG_INF("Campaign menu shows the lost-level message for level " + Helper::toString(playedLevel));
            mResultText = Translation::tr("mode.menu.campaign.level_failed");
        }
        campaign.clearPlayedLevel();
    }

    clearMap();
    hideBriefing();
    if(mCampaignEnd)
    {
        // The message is shown once without the map; the next opening of the campaign shows the map again
        campaign.clearPlayedLevel();
        setMapVisible(false);
        showDebriefing();
        if(RunLevelTest::isActive())
            RunLevelTest::onCampaignMapShown(true);
        return;
    }
    setMapVisible(true);
    if(campaign.getNumLevels() == 0)
        return;

    if(!loadWorld())
    {
        window->getChild(CMP_TEXT_LOADING)->setText(Gui::trCegui("mode.menu.campaign.map_load_error"));
        return;
    }

    fillMap();
    if(!mResultText.empty())
        showDebriefing();
    updateDifficultyButton();

    // The level load test checks here that the map with the next level appeared after the won level
    if(RunLevelTest::isActive())
        RunLevelTest::onCampaignMapShown(playedLevelWon);
}

//! \brief Displays the campaign difficulty and its unlock hint.
void MenuModeCampaign::updateDifficultyButton()
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    CEGUI::Window* button = window->getChild(CMP_BUTTON_DIFFICULTY);
    KeeperAIType type = static_cast<KeeperAIType>(campaign.getDifficulty());
    std::string name = KeeperAITypes::toString(type);
    std::string displayName = Translation::tr("mode.menu.campaign.difficulty." + name);
    button->setText(Gui::toCeguiText(Translation::tr("mode.menu.campaign.difficulty", {{"name", displayName}})));
    // The difficulty is chosen when a new campaign is begun and then stays
    button->setEnabled(!campaign.hasProgress());
    button->setTooltipText(!campaign.hasProgress() && !campaign.isHellUnlocked() ?
        Gui::trCegui("mode.menu.campaign.hell_hint") : CEGUI::String());
}

//! \brief Selects the next unlocked campaign difficulty.
bool MenuModeCampaign::difficultyButtonPressed(const CEGUI::EventArgs&)
{
    Campaign& campaign = Campaign::getSingleton();
    if(campaign.hasProgress())
        return true;

    size_t index = 0;
    while(index < KeeperAITypes::displayOrder.size() && static_cast<uint32_t>(KeeperAITypes::displayOrder[index]) != campaign.getDifficulty())
        ++index;
    do
    {
        index = (index + 1) % KeeperAITypes::displayOrder.size();
    } while(KeeperAITypes::displayOrder[index] == KeeperAIType::hell && !campaign.isHellUnlocked());
    campaign.setDifficulty(static_cast<uint32_t>(KeeperAITypes::displayOrder[index]));
    updateDifficultyButton();
    return true;
}

//! \brief Reads the map of Moreya once; the caves are found by their round markers, no id map is needed.
bool MenuModeCampaign::loadWorld()
{
    if(mWorldLoaded)
        return true;

    std::string directory = ResourceManager::getSingleton().getGameDataPath() + WORLD_DIRECTORY;
    // The campaign map may lie in a content package (ContentPackages::resolveFile)
    std::ifstream definition(ContentPackages::resolveFile(directory + WORLD_DEFINITION_FILE).c_str());
    if(!definition.is_open() || !mWorld.importDefinition(definition))
    {
        OD_LOG_ERR("Could not read the campaign map of Moreya " + directory + WORLD_DEFINITION_FILE);
        return false;
    }

    mWorldLoaded = true;
    return true;
}

//! \brief Loads a campaign art file once as a CEGUI image named after the file: from the folder of the wing package
//! when the file lies there, else from gui/campaign. Returns NULL if it cannot be read.
CEGUI::Image* MenuModeCampaign::loadWorldImage(const std::string& file, const std::string& packageDirectory)
{
    std::string name = WORLD_IMAGE_PREFIX + file;
    CEGUI::ImageManager& images = CEGUI::ImageManager::getSingleton();
    if(images.isDefined(name))
        return &images.get(name);

    int width = 0;
    int height = 0;
    std::vector<uint8_t> rgba;
    std::string path = ContentPackages::resolveFile(ResourceManager::getSingleton().getGameDataPath() + WORLD_DIRECTORY
        + file);
    if(!packageDirectory.empty())
    {
        boost::filesystem::path packagePath = boost::filesystem::path(packageDirectory) / file;
        if(boost::filesystem::is_regular_file(packagePath))
            path = packagePath.string();
    }
    if(!decodeImage(path, width, height, rgba))
    {
        OD_LOG_ERR("Could not read the campaign world image " + path);
        return nullptr;
    }

    CEGUI::Texture& texture = CEGUI::System::getSingleton().getRenderer()->createTexture(name);
    texture.loadFromMemory(&rgba[0], CEGUI::Sizef(static_cast<float>(width), static_cast<float>(height)),
        CEGUI::Texture::PF_RGBA);
    CEGUI::BasicImage& image = static_cast<CEGUI::BasicImage&>(images.create("BasicImage", name));
    image.setTexture(&texture);
    image.setArea(CEGUI::Rectf(0, 0, static_cast<float>(width), static_cast<float>(height)));
    return &image;
}
//! \brief Removes the map windows of this and of earlier visits, found by their name prefix.
void MenuModeCampaign::clearMap()
{
    CEGUI::WindowManager& windowManager = CEGUI::WindowManager::getSingleton();
    mWorldWindows.clear();
    mCaveStates.clear();

    // The mode is created again on every visit but the gui sheet stays, so windows of an earlier
    // visit are not in the list. Remove them by name or fillMap meets the same names again.
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    if(sheet->isChild(CMP_MAP))
    {
        CEGUI::Window* map = sheet->getChild(CMP_MAP);
        for(size_t i = map->getChildCount(); i > 0; --i)
        {
            CEGUI::Window* child = map->getChildAtIdx(i - 1);
            if(child->getName().compare(0, WORLD_WINDOW_PREFIX.size(), WORLD_WINDOW_PREFIX) == 0)
            {
                map->removeChild(child);
                windowManager.destroyWindow(child);
            }
        }
    }
    windowManager.cleanDeadPool();
    mHoverWindow = nullptr;
    mTooltip = nullptr;
    mTooltipPlaque = nullptr;
    mCurrentGlow = nullptr;
    mCurrentPointer = nullptr;
    mRaidEmbers.clear();
    mMapTime = 0.0f;
}

void MenuModeCampaign::setMapArea(CEGUI::Window* window, float x, float y, float width, float height) const
{
    float mapWidth = static_cast<float>(mWorld.getWidth());
    float mapHeight = static_cast<float>(mWorld.getHeight());
    window->setArea(CEGUI::UDim(x / mapWidth, 0), CEGUI::UDim(y / mapHeight, 0),
        CEGUI::UDim(width / mapWidth, 0), CEGUI::UDim(height / mapHeight, 0));
}

//! \brief Creates a map window whose area is a share of the map, so it scales with the map and stays inside it.
CEGUI::Window* MenuModeCampaign::createMapWindow(const std::string& type, const std::string& name, float x, float y,
    float width, float height)
{
    CEGUI::Window* window = CEGUI::WindowManager::getSingleton().createWindow(type, WORLD_WINDOW_PREFIX + name);
    CEGUI::Window* map = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu)->getChild(CMP_MAP);
    setMapArea(window, x, y, width, height);
    // The map handles the mouse itself, with the cave markers of the map description
    window->setMousePassThroughEnabled(true);
    map->addChild(window);
    mWorldWindows.push_back(window);
    return window;
}

//! \brief Creates a text without frame and background in a rectangle of map pixels.
CEGUI::Window* MenuModeCampaign::createMapText(const std::string& name, const CampaignWorldRect& area,
    const std::string& font, const std::string& colour, const std::string& formatting, const std::string& text)
{
    CEGUI::Window* window = createMapWindow("OD/StaticText", name, static_cast<float>(area.mX),
        static_cast<float>(area.mY), static_cast<float>(area.mWidth), static_cast<float>(area.mHeight));
    window->setProperty("FrameEnabled", "False");
    window->setProperty("BackgroundEnabled", "False");
    window->setProperty("Font", font);
    window->setProperty("HorzFormatting", formatting);
    window->setProperty("VertFormatting", "CentreAligned");
    window->setProperty("TextColours", colour);
    window->setText(reinterpret_cast<const CEGUI::utf8*>(text.c_str()));
    return window;
}

//! \brief Creates an image of the campaign art in a rectangle of map pixels, or nothing when the file is missing.
//! The file is looked up first in the folder of the wing package when one is given.
CEGUI::Window* MenuModeCampaign::createMapImage(const std::string& name, const std::string& file, float x, float y,
    float width, float height, const std::string& packageDirectory)
{
    if(file.empty() || (loadWorldImage(file, packageDirectory) == nullptr))
        return nullptr;

    CEGUI::Window* window = createMapWindow("OD/StaticImage", name, x, y, width, height);
    window->setProperty("FrameEnabled", "False");
    window->setProperty("BackgroundEnabled", "False");
    window->setProperty("Image", WORLD_IMAGE_PREFIX + file);
    return window;
}

//! \brief Draws the map of Moreya with the current progress: wing names with their defeated levels and the seal of
//! a defeated wing, every story cave in its state with its name, the found bonus caves, the guild in front of the
//! gate, the title and the progress panel. The tooltip is created last so it lies above everything.
void MenuModeCampaign::fillMap()
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* map = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu)->getChild(CMP_MAP);

    if(loadWorldImage(mWorld.getBaseImage()) != nullptr)
        map->setProperty("Image", WORLD_IMAGE_PREFIX + mWorld.getBaseImage());

    const std::vector<CampaignWorldCave>& caves = mWorld.getCaves();
    mCaveStates.assign(caves.size(), CampaignCaveState::hidden);
    for(size_t i = 0; i < caves.size(); ++i)
    {
        size_t level = 0;
        mCaveStates[i] = mWorld.getCaveState(campaign, i, level);
    }

    // A wing that cannot be played yet is greyed out, so the open wings stand out
    for(const CampaignWorldWing& wing : mWorld.getWings())
    {
        if(wing.mLockedImage.empty() || !isWingLocked(wing.mNumber))
            continue;
        createMapImage("WingLocked_" + Helper::toString(wing.mNumber), wing.mLockedImage,
            static_cast<float>(wing.mLockedArea.mX), static_cast<float>(wing.mLockedArea.mY),
            static_cast<float>(wing.mLockedArea.mWidth), static_cast<float>(wing.mLockedArea.mHeight));
    }

    // The ring around the cave under the mouse lies below the cave markers
    if(loadWorldImage(mWorld.getIcons().mHover) != nullptr)
    {
        mHoverWindow = createMapWindow("OD/StaticImage", "Hover", 0, 0, 1, 1);
        mHoverWindow->setProperty("FrameEnabled", "False");
        mHoverWindow->setProperty("BackgroundEnabled", "False");
        mHoverWindow->setProperty("Image", WORLD_IMAGE_PREFIX + mWorld.getIcons().mHover);
        mHoverWindow->setVisible(false);
    }

    // The wings: name and defeated levels, and the seal once all of its story levels are defeated
    const std::vector<CampaignWorldWing>& wings = mWorld.getWings();
    for(size_t i = 0; i < wings.size(); ++i)
    {
        const CampaignWorldWing& wing = wings[i];
        uint32_t defeated = mWorld.getDefeatedInWing(campaign, wing.mNumber);
        bool wingDefeated = (defeated >= CampaignWorld::STORY_CAVES_PER_WING);
        std::string wingId = Helper::toString(wing.mNumber);
        if(!campaign.isWingAvailable(wing.mNumber))
        {
            // The package of the wing is missing: the wing name is shown locked, its caves say that the wing is
            // coming in Early Access. A name painted on the map needs no text.
            if(!wing.mNamePainted)
                createMapText("Wing_" + wingId, wing.mLabel, FONT_WING, COLOUR_LOCKED, "WordWrapLeftAligned", wing.mName);
            continue;
        }
        // A name painted on the map gets only the progress beside it
        std::string progress = Helper::toString(defeated) + " / "
            + Helper::toString(CampaignWorld::STORY_CAVES_PER_WING);
        // The progress of a greyed out wing is grey as well
        std::string wingColour = wingDefeated ? COLOUR_HIGHLIGHT : COLOUR_TEXT;
        if(isWingLocked(wing.mNumber))
            wingColour = COLOUR_LOCKED;
        createMapText("Wing_" + wingId, wing.mLabel, FONT_WING, wingColour,
            "WordWrapLeftAligned", wing.mNamePainted ? progress : wing.mName + "   " + progress);
        if(wingDefeated)
        {
            float size = static_cast<float>(wing.mSealSize);
            createMapImage("WingSeal_" + wingId, mWorld.getIcons().mWingDefeated,
                static_cast<float>(wing.mSealX) - size / 2.0f, static_cast<float>(wing.mSealY) - size / 2.0f, size, size);
        }
    }

    // The glow of the current level lies below the cave markers
    fillCurrentMarker();

    // The caves in their states with the names of their levels; a bonus cave only once its stone was found
    const CampaignWorldIcons& icons = mWorld.getIcons();
    for(size_t i = 0; i < caves.size(); ++i)
    {
        const CampaignWorldCave& cave = caves[i];
        const std::string* icon = &icons.mLocked;
        std::string colour = COLOUR_TEXT;
        switch(mCaveStates[i])
        {
            case CampaignCaveState::hidden:
                continue;
            case CampaignCaveState::locked:
                colour = COLOUR_LOCKED;
                break;
            case CampaignCaveState::current:
                icon = &icons.mCurrent;
                colour = COLOUR_HIGHLIGHT;
                break;
            case CampaignCaveState::defeated:
                icon = &icons.mDefeated;
                break;
            case CampaignCaveState::bonusFound:
                icon = &icons.mBonusFound;
                colour = COLOUR_HIGHLIGHT;
                break;
            case CampaignCaveState::bonusCleared:
                icon = &icons.mBonusCleared;
                break;
        }

        std::string caveId = Helper::toString(static_cast<uint32_t>(i));
        float size = static_cast<float>(cave.mSize);
        // The current level is drawn larger than the other caves
        if(mCaveStates[i] == CampaignCaveState::current)
            size *= CURRENT_CAVE_SCALE;
        CEGUI::Window* marker = createMapImage("Cave_" + caveId, *icon, static_cast<float>(cave.mX) - size / 2.0f,
            static_cast<float>(cave.mY) - size / 2.0f, size, size);
        // The locked caves of a greyed out wing recede with it
        if((marker != nullptr) && (mCaveStates[i] == CampaignCaveState::locked) && isWingLocked(cave.mWing))
            marker->setAlpha(LOCKED_CAVE_ALPHA);

        // The name of a level stands under its cave when the map gives it a label; a bonus cave and a level without
        // label name themselves in their tooltip. The caves of a wing without package say that the wing is coming in
        // Early Access.
        size_t level = mWorld.findLevel(campaign, i);
        bool named = !cave.mBonus && (cave.mLabel.mWidth > 0);
        if(named && (level < campaign.getNumLevels()))
        {
            createMapText("CaveName_" + caveId, cave.mLabel, FONT_CAVE, colour, "WordWrapCentreAligned",
                LevelText::display(campaign.getLevel(level).mTitle));
        }
        else if(named && !campaign.isWingAvailable(cave.mWing))
        {
            createMapText("CaveName_" + caveId, cave.mLabel, FONT_CAVE, colour, "WordWrapCentreAligned",
                CampaignPackages::getMissingWingText());
        }
    }

    fillGuildPanel();

    // The title in the cartouche
    createMapText("Title", mWorld.getTitleCartouche(), FONT_TITLE, COLOUR_HIGHLIGHT, "CentreAligned", CAMPAIGN_TITLE);

    fillProgressPanel();

    // The arrow above the current level lies above the cave markers and the guild
    if((mCurrentGlow != nullptr) && (loadWorldImage(ART_CURRENT_POINTER) != nullptr))
    {
        mCurrentPointer = createMapImage("CurrentPointer", ART_CURRENT_POINTER, mCurrentX - POINTER_WIDTH / 2.0f,
            mCurrentY - POINTER_HEIGHT, POINTER_WIDTH, POINTER_HEIGHT);
    }

    // The tooltip is the topmost window of the map: a small carved stone tablet with its text inside its recess
    mTooltipPlaque = createMapWindow("OD/StaticImage", "TooltipPlaque", 0, 0, 1, 1);
    mTooltipPlaque->setProperty("FrameEnabled", "False");
    mTooltipPlaque->setProperty("BackgroundEnabled", "False");
    if(loadWorldImage(ART_TOOLTIP_PLAQUE) != nullptr)
        mTooltipPlaque->setProperty("Image", WORLD_IMAGE_PREFIX + ART_TOOLTIP_PLAQUE);
    mTooltip = CEGUI::WindowManager::getSingleton().createWindow("OD/StaticText", WORLD_WINDOW_PREFIX + "Tooltip");
    mTooltip->setArea(CEGUI::UDim(TOOLTIP_INSET_X, 0), CEGUI::UDim(TOOLTIP_INSET_Y, 0),
        CEGUI::UDim(1.0f - 2.0f * TOOLTIP_INSET_X, 0), CEGUI::UDim(1.0f - 2.0f * TOOLTIP_INSET_Y, 0));
    mTooltip->setMousePassThroughEnabled(true);
    mTooltip->setProperty("FrameEnabled", "False");
    mTooltip->setProperty("BackgroundEnabled", "False");
    mTooltip->setProperty("Font", FONT_TOOLTIP);
    mTooltip->setProperty("HorzFormatting", "WordWrapLeftAligned");
    mTooltip->setProperty("VertFormatting", "CentreAligned");
    mTooltip->setProperty("TextColours", COLOUR_TEXT);
    mTooltipPlaque->addChild(mTooltip);
    setTooltipVisible(false);
}

//! \brief Tells whether every cave of the wing is locked or a hidden bonus cave; a wing without its package is locked.
bool MenuModeCampaign::isWingLocked(uint32_t wing) const
{
    if(!Campaign::getSingleton().isWingAvailable(wing))
        return true;
    const std::vector<CampaignWorldCave>& caves = mWorld.getCaves();
    for(size_t i = 0; (i < caves.size()) && (i < mCaveStates.size()); ++i)
    {
        if(caves[i].mWing != wing)
            continue;
        if((mCaveStates[i] != CampaignCaveState::locked) && (mCaveStates[i] != CampaignCaveState::hidden))
            return false;
    }
    return true;
}

//! \brief Puts the golden glow below the marker of the current level; the arrow above it is added after the markers.
//! Nothing is drawn when no level is current (the campaign is finished).
void MenuModeCampaign::fillCurrentMarker()
{
    size_t cave = mWorld.findCurrentCave(Campaign::getSingleton());
    if((cave >= mWorld.getCaves().size()) || (cave >= mCaveStates.size())
        || (mCaveStates[cave] != CampaignCaveState::current))
        return;
    const CampaignWorldCave& worldCave = mWorld.getCaves()[cave];
    mCurrentX = static_cast<float>(worldCave.mX);
    mCurrentY = static_cast<float>(worldCave.mY) - static_cast<float>(worldCave.mSize) * CURRENT_CAVE_SCALE / 2.0f
        - POINTER_GAP;
    mCurrentGlowSize = static_cast<float>(worldCave.mSize) * CURRENT_GLOW_SCALE;
    mCurrentGlow = createMapImage("CurrentGlow", ART_CURRENT_GLOW, mCurrentX - mCurrentGlowSize / 2.0f,
        static_cast<float>(worldCave.mY) - mCurrentGlowSize / 2.0f, mCurrentGlowSize, mCurrentGlowSize);
}

//! \brief Lays embers along the straight way from the bottom of the guild panel below the portrait to the top of the
//! attacked cave and plants the guild's banner beside the cave.
void MenuModeCampaign::fillRaidTrail(size_t cave, const std::string& banner, const std::string& packageDirectory)
{
    if((cave >= mWorld.getCaves().size()) || (loadWorldImage(ART_RAID_EMBER) == nullptr))
        return;
    const CampaignWorldGuildPanel& panel = mWorld.getGuildPanel();
    const CampaignWorldCave& worldCave = mWorld.getCaves()[cave];
    float startX = static_cast<float>(panel.mPortrait.mX) + static_cast<float>(panel.mPortrait.mWidth) / 2.0f;
    float startY = static_cast<float>(panel.mArea.mY + panel.mArea.mHeight);
    float size = static_cast<float>(worldCave.mSize) * CURRENT_CAVE_SCALE;
    float endX = static_cast<float>(worldCave.mX);
    float endY = static_cast<float>(worldCave.mY) - size / 2.0f - POINTER_HEIGHT;
    float length = std::sqrt((endX - startX) * (endX - startX) + (endY - startY) * (endY - startY));
    size_t count = static_cast<size_t>(length / RAID_EMBER_SPACING);
    count = std::max(RAID_EMBERS_MIN, std::min(RAID_EMBERS_MAX, count));
    for(size_t i = 0; i < count; ++i)
    {
        float share = (static_cast<float>(i) + 0.5f) / static_cast<float>(count);
        float x = startX + (endX - startX) * share;
        float y = startY + (endY - startY) * share;
        CEGUI::Window* ember = createMapImage("RaidEmber_" + Helper::toString(static_cast<uint32_t>(i)),
            ART_RAID_EMBER, x - RAID_EMBER_SIZE / 2.0f, y - RAID_EMBER_SIZE / 2.0f, RAID_EMBER_SIZE,
            RAID_EMBER_SIZE);
        if(ember != nullptr)
            mRaidEmbers.push_back(ember);
    }
    // The guild's banner stands at the cave it attacks
    createMapImage("RaidBanner", banner, endX + size / 2.0f, static_cast<float>(worldCave.mY) - RAID_BANNER_HEIGHT,
        RAID_BANNER_WIDTH, RAID_BANNER_HEIGHT, packageDirectory);
}

//! \brief The glow of the current level pulses, its arrow bobs over it and a brighter glow runs along the embers of
//! the raid trail towards the current level.
void MenuModeCampaign::updateMapAnimation(float elapsed)
{
    if(std::isfinite(elapsed) && (elapsed > 0.0f))
        mMapTime += elapsed;
    float wave = std::sin(TWO_PI * mMapTime / PULSE_PERIOD);
    if(mCurrentGlow != nullptr)
        mCurrentGlow->setAlpha(0.7f + 0.3f * wave);
    if(mCurrentPointer != nullptr)
    {
        setMapArea(mCurrentPointer, mCurrentX - POINTER_WIDTH / 2.0f,
            mCurrentY - POINTER_HEIGHT - POINTER_BOB * (0.5f + 0.5f * wave), POINTER_WIDTH, POINTER_HEIGHT);
    }
    float head = std::fmod(mMapTime * RAID_TRAIL_SPEED, 1.0f);
    for(size_t i = 0; i < mRaidEmbers.size(); ++i)
    {
        float share = (static_cast<float>(i) + 0.5f) / static_cast<float>(mRaidEmbers.size());
        // Distance behind the running glow, 0 at the glow and growing towards the guild
        float behind = std::fmod(head - share + 1.0f, 1.0f);
        mRaidEmbers[i]->setAlpha(0.3f + 0.7f * std::max(0.0f, 1.0f - behind * 3.0f));
    }
}

//! \brief Shows or hides the tablet of the hover display together with its text.
void MenuModeCampaign::setTooltipVisible(bool visible)
{
    if(mTooltipPlaque != nullptr)
        mTooltipPlaque->setVisible(visible);
    if(mTooltip != nullptr)
        mTooltip->setVisible(visible);
}

//! \brief Shows the banner, the leader's portrait, the name, leader, raid size and origin of the guild that raids the
//! current level on a carved stone slab, with a trail of embers from it to the current level and its banner there.
//! Once every story level is defeated no guild comes any more. The names come from the chosen language.
void MenuModeCampaign::fillGuildPanel()
{
    Campaign& campaign = Campaign::getSingleton();
    size_t cave = mWorld.findCurrentCave(campaign);
    if(cave >= mWorld.getCaves().size())
        return;

    // The guild comes with the level from its wing package
    size_t level = mWorld.findLevel(campaign, cave);
    if(level >= campaign.getNumLevels())
        return;

    const CampaignLevel& campaignLevel = campaign.getLevel(level);
    const CampaignWorldGuild& guild = campaignLevel.mGuild;
    if(guild.mName.empty())
        return;
    // Banner and portrait of a private wing package lie in its own folder
    const std::string packageDirectory = packageDirectoryOf(campaignLevel);
    const CampaignWorldGuildPanel& panel = mWorld.getGuildPanel();
    // The guild stands on a carved stone slab with a niche for its banner and a frame round the portrait, and its
    // embers lead to the level it attacks, where its banner stands
    createMapImage("GuildPlaque", ART_GUILD_PLAQUE, static_cast<float>(panel.mArea.mX),
        static_cast<float>(panel.mArea.mY), static_cast<float>(panel.mArea.mWidth),
        static_cast<float>(panel.mArea.mHeight));
    fillRaidTrail(cave, guild.mBanner, packageDirectory);
    createMapImage("GuildBanner", guild.mBanner, static_cast<float>(panel.mBanner.mX),
        static_cast<float>(panel.mBanner.mY), static_cast<float>(panel.mBanner.mWidth),
        static_cast<float>(panel.mBanner.mHeight), packageDirectory);
    createMapImage("GuildPortrait", guild.mPortrait, static_cast<float>(panel.mPortrait.mX),
        static_cast<float>(panel.mPortrait.mY), static_cast<float>(panel.mPortrait.mWidth),
        static_cast<float>(panel.mPortrait.mHeight), packageDirectory);
    // The names of the guild and its leaders come from the language files
    CampaignWorldGuild shownGuild = guild;
    shownGuild.mName = LevelText::display(guild.mName);
    shownGuild.mLeader = LevelText::display(guild.mLeader);
    shownGuild.mFirstLeader = LevelText::display(guild.mFirstLeader);
    shownGuild.mOrigin = LevelText::display(guild.mOrigin);
    createMapText("GuildName", panel.mName, FONT_GUILD_NAME, COLOUR_HIGHLIGHT, "WordWrapLeftAligned",
        shownGuild.mName);
    createMapText("GuildDetails", panel.mDetails, FONT_GUILD_DETAILS, COLOUR_TEXT, "WordWrapLeftAligned",
        CampaignWorld::getGuildDetailsText(shownGuild));
}

//! \brief Progress: defeated story levels and wings, Heartstone shards, cleared bonus caves, and a bar of the defeated
//! story levels in percent.
void MenuModeCampaign::fillProgressPanel()
{
    Campaign& campaign = Campaign::getSingleton();
    uint32_t levelsDefeated = 0;
    uint32_t levelTotal = 0;
    uint32_t bonusCleared = 0;
    uint32_t bonusTotal = 0;
    for(size_t i = 0; i < mCaveStates.size(); ++i)
    {
        if(mWorld.getCaves()[i].mBonus)
        {
            ++bonusTotal;
            if(mCaveStates[i] == CampaignCaveState::bonusCleared)
                ++bonusCleared;
        }
        else
        {
            ++levelTotal;
            if(mCaveStates[i] == CampaignCaveState::defeated)
                ++levelsDefeated;
        }
    }
    uint32_t wingsDefeated = 0;
    const std::vector<CampaignWorldWing>& wings = mWorld.getWings();
    for(size_t i = 0; i < wings.size(); ++i)
    {
        if(mWorld.getDefeatedInWing(campaign, wings[i].mNumber) >= CampaignWorld::STORY_CAVES_PER_WING)
            ++wingsDefeated;
    }
    int percent = (levelTotal > 0) ? static_cast<int>(levelsDefeated * PERCENT_FULL / levelTotal) : 0;

    const CampaignWorldRect& panel = mWorld.getProgressPanel();
    float panelX = static_cast<float>(panel.mX);
    float panelY = static_cast<float>(panel.mY);
    float panelWidth = static_cast<float>(panel.mWidth);
    float panelHeight = static_cast<float>(panel.mHeight);
    CampaignWorldRect textArea;
    textArea.mX = static_cast<int>(panelX + panelWidth * PROGRESS_LEFT);
    textArea.mY = panel.mY;
    textArea.mWidth = static_cast<int>(panelWidth * PROGRESS_TEXT_WIDTH);
    textArea.mHeight = static_cast<int>(panelHeight * PROGRESS_TEXT_HEIGHT);
    createMapText("ProgressText", textArea, FONT_PROGRESS, COLOUR_TEXT, "LeftAligned",
        Translation::tr("mode.menu.campaign.progress", {
            {"levels", Helper::toString(levelsDefeated)}, {"levelTotal", Helper::toString(levelTotal)},
            {"wings", Helper::toString(wingsDefeated)}, {"wingTotal", Helper::toString(static_cast<uint32_t>(wings.size()))},
            {"shards", Helper::toString(static_cast<uint32_t>(campaign.getHeartstonePieces()))},
            {"shardTotal", Helper::toString(static_cast<uint32_t>(campaign.getHeartstoneTotal()))},
            {"bonus", Helper::toString(bonusCleared)}, {"bonusTotal", Helper::toString(bonusTotal)}}));

    CEGUI::Window* bar = createMapWindow("OD/ProgressBar", "ProgressBar", panelX + panelWidth * PROGRESS_LEFT,
        panelY + panelHeight * PROGRESS_BAR_TOP, panelWidth * PROGRESS_BAR_WIDTH, panelHeight * PROGRESS_BAR_HEIGHT);
    static_cast<CEGUI::ProgressBar*>(bar)->setProgress(static_cast<float>(percent) / PERCENT_FULL_FLOAT);

    CampaignWorldRect percentArea;
    percentArea.mX = static_cast<int>(panelX + panelWidth * PROGRESS_PERCENT_LEFT);
    percentArea.mY = static_cast<int>(panelY + panelHeight * PROGRESS_PERCENT_TOP);
    percentArea.mWidth = static_cast<int>(panelWidth * PROGRESS_PERCENT_WIDTH);
    percentArea.mHeight = static_cast<int>(panelHeight * PROGRESS_PERCENT_HEIGHT);
    createMapText("ProgressPercent", percentArea, FONT_PROGRESS, COLOUR_TEXT, "RightAligned",
        Helper::toString(percent) + "%");
}

//! \brief Fits a visible debriefing after display or UI-scale changes and animates the current level and the raid
//! trail. Once the camera has arrived in the green
//! portal the chosen level is loaded, so its loading screen comes only then; if it cannot be started the map comes
//! back with the reason.
void MenuModeCampaign::onFrameStarted(const Ogre::FrameEvent& evt)
{
    fitDebriefingPanel();
    updateMapAnimation(evt.timeSinceLastFrame);
    if(!mPortalFlight || ODFrameListener::getSingleton().isMainMenuFlightActive())
        return;
    mPortalFlight = false;
    startLevel(mPortalLevel);
}

//! \brief Escape would leave the campaign while the level is about to be loaded, so it waits for the portal.
bool MenuModeCampaign::keyPressed(const OIS::KeyEvent& arg)
{
    if(mPortalFlight && (arg.key == OIS::KC_ESCAPE))
        return true;
    return AbstractApplicationMode::keyPressed(arg);
}

//! \brief Converts the screen position into map pixels and finds the visible cave whose marker is there.
size_t MenuModeCampaign::findCaveAt(const CEGUI::Vector2f& position, const CEGUI::Window* map) const
{
    size_t count = mWorld.getCaves().size();
    if(!mWorldLoaded || (map == nullptr))
        return count;

    const CEGUI::Rectf& mapRect = map->getUnclippedOuterRect().get();
    if((mapRect.getWidth() <= 0.0f) || (mapRect.getHeight() <= 0.0f))
        return count;

    float x = (position.d_x - mapRect.left()) * static_cast<float>(mWorld.getWidth()) / mapRect.getWidth();
    float y = (position.d_y - mapRect.top()) * static_cast<float>(mWorld.getHeight()) / mapRect.getHeight();
    return mWorld.getCaveAt(x, y, mCaveStates);
}

//! \brief Puts the ring around a cave that can be played, as large as its marker; locked caves and empty map get no
//! ring.
void MenuModeCampaign::updateHover(size_t cave)
{
    if(mHoverWindow == nullptr)
        return;

    if((cave >= mWorld.getCaves().size()) || (cave >= mCaveStates.size())
        || (mCaveStates[cave] == CampaignCaveState::locked) || (mCaveStates[cave] == CampaignCaveState::hidden))
    {
        mHoverWindow->setVisible(false);
        return;
    }

    const CampaignWorldCave& worldCave = mWorld.getCaves()[cave];
    float size = static_cast<float>(worldCave.mSize) * HOVER_SCALE;
    // The marker of the current level is drawn larger, its ring too
    if(mCaveStates[cave] == CampaignCaveState::current)
        size *= CURRENT_CAVE_SCALE;
    setMapArea(mHoverWindow, static_cast<float>(worldCave.mX) - size / 2.0f,
        static_cast<float>(worldCave.mY) - size / 2.0f, size, size);
    mHoverWindow->setVisible(true);
}

//! \brief Names the cave under the mouse: level title, wing, guild and state (a level has no difficulty of its
//! own), on a small carved stone tablet that is just large enough for its text: the title in gold, the state in the
//! colour of the cave. The tooltip is scaled with the layout, never wider than TOOLTIP_WIDTH and kept inside the map.
void MenuModeCampaign::updateTooltip(const CEGUI::Vector2f& position, size_t cave)
{
    if((mTooltip == nullptr) || (mTooltipPlaque == nullptr))
        return;

    const std::vector<CampaignWorldCave>& caves = mWorld.getCaves();
    if((cave >= caves.size()) || (cave >= mCaveStates.size()))
    {
        setTooltipVisible(false);
        return;
    }

    Campaign& campaign = Campaign::getSingleton();
    const CampaignWorldCave& worldCave = caves[cave];
    size_t level = mWorld.findLevel(campaign, cave);
    bool known = (level < campaign.getNumLevels());
    std::string text = known ? LevelText::display(campaign.getLevel(level).mTitle) : CampaignPackages::getMissingWingText();
    std::string wingName;
    if((worldCave.mWing >= 1) && (worldCave.mWing <= mWorld.getWings().size()))
        wingName = mWorld.getWings()[worldCave.mWing - 1].mName;
    if(worldCave.mBonus)
        text += "\n" + Translation::tr("mode.menu.campaign.bonus_cave", {{"wing", wingName}});
    else if(known && !campaign.getLevel(level).mGuild.mName.empty())
        text += "\n" + wingName + "\n" + Translation::tr("mode.menu.campaign.guild", {{"name", LevelText::display(campaign.getLevel(level).mGuild.mName)}});
    else
        text += "\n" + wingName;

    std::string state;
    std::string stateColour = COLOUR_TEXT;
    switch(mCaveStates[cave])
    {
        case CampaignCaveState::locked:
            state = Translation::tr("mode.menu.campaign.state_locked");
            stateColour = COLOUR_LOCKED;
            break;
        case CampaignCaveState::current:
            state = Translation::tr("mode.menu.campaign.state_current");
            stateColour = COLOUR_HIGHLIGHT;
            break;
        case CampaignCaveState::defeated:
            state = Translation::tr("mode.menu.campaign.state_defeated");
            break;
        case CampaignCaveState::bonusFound:
            state = Translation::tr("mode.menu.campaign.state_found");
            stateColour = COLOUR_HIGHLIGHT;
            break;
        case CampaignCaveState::bonusCleared:
            state = Translation::tr("mode.menu.campaign.state_cleared");
            break;
        case CampaignCaveState::hidden:
            setTooltipVisible(false);
            return;
    }
    text += "\n" + state;
    const float scale = getModeManager().getGui().getLayoutScale();
    const CEGUI::Rectf& mapRect = mTooltipPlaque->getParent()->getUnclippedOuterRect().get();
    // The tablet is as wide as the longest line needs, at most TOOLTIP_WIDTH, and as high as the wrapped text
    const CEGUI::Font* font = mTooltip->getFont();
    float textWidth = 0.0f;
    std::istringstream lines(text);
    std::string line;
    while(std::getline(lines, line))
    {
        textWidth = std::max(textWidth,
            font->getTextExtent(CEGUI::String(reinterpret_cast<const CEGUI::utf8*>(line.c_str()))));
    }
    float width = std::min(std::min(TOOLTIP_WIDTH * scale, mapRect.getWidth()),
        std::ceil(textWidth + 2.0f) / (1.0f - 2.0f * TOOLTIP_INSET_X));
    mTooltipPlaque->setArea(CEGUI::UDim(0, 0), CEGUI::UDim(0, 0), CEGUI::UDim(0, width),
        CEGUI::UDim(0, std::min(TOOLTIP_HEIGHT * scale, mapRect.getHeight())));
    // The title in gold, the state in the colour of the cave; the text is measured without the colour tags
    std::string title = text.substr(0, text.find('\n'));
    std::string middle = text.substr(title.size(), text.size() - title.size() - state.size());
    std::string shown = "[colour='" + COLOUR_HIGHLIGHT + "']" + title + "[colour='" + COLOUR_TEXT + "']" + middle
        + "[colour='" + stateColour + "']" + state;
    mTooltip->setText(reinterpret_cast<const CEGUI::utf8*>(shown.c_str()));
    float textHeight = CEGUI::PropertyHelper<float>::fromString(mTooltip->getProperty("VertExtent"));
    float height = std::min(std::min(TOOLTIP_HEIGHT * scale, mapRect.getHeight()),
        std::ceil(textHeight + 2.0f) / (1.0f - 2.0f * TOOLTIP_INSET_Y));
    float offset = TOOLTIP_OFFSET * scale;
    float x = position.d_x - mapRect.left() + offset;
    float y = position.d_y - mapRect.top() + offset;
    // Keep it inside of the map
    if(x + width > mapRect.getWidth())
        x = position.d_x - mapRect.left() - offset - width;
    if(y + height > mapRect.getHeight())
        y = position.d_y - mapRect.top() - offset - height;
    x = std::max(0.0f, std::min(x, mapRect.getWidth() - width));
    y = std::max(0.0f, std::min(y, mapRect.getHeight() - height));
    mTooltipPlaque->setArea(CEGUI::UDim(0, x), CEGUI::UDim(0, y), CEGUI::UDim(0, width), CEGUI::UDim(0, height));
    setTooltipVisible(true);
}

//! \brief Highlights the cave under the mouse and shows its tooltip.
bool MenuModeCampaign::mapMoved(const CEGUI::EventArgs& e)
{
    const CEGUI::MouseEventArgs& args = static_cast<const CEGUI::MouseEventArgs&>(e);
    size_t cave = findCaveAt(args.position, args.window);
    updateHover(cave);
    updateTooltip(args.position, cave);
    return true;
}

//! \brief Removes the highlight and the tooltip when the mouse leaves the map.
bool MenuModeCampaign::mapLeft(const CEGUI::EventArgs&)
{
    updateHover(mWorld.getCaves().size());
    setTooltipVisible(false);
    return true;
}

//! \brief Opens the briefing of the clicked cave when it can be played: the current level, a defeated level (played
//! again as today) or a found bonus cave. A locked cave only gets a message; nothing starts on the click itself.
bool MenuModeCampaign::mapClicked(const CEGUI::EventArgs& e)
{
    const CEGUI::MouseEventArgs& args = static_cast<const CEGUI::MouseEventArgs&>(e);
    if(!mWorldLoaded || (args.button != CEGUI::LeftButton))
        return true;

    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    if(sheet->getChild(CMP_BRIEFING)->isVisible())
        return true;

    CEGUI::Window* statusText = sheet->getChild(CMP_TEXT_LOADING);
    statusText->setText("");
    size_t cave = findCaveAt(args.position, args.window);
    if(cave >= mWorld.getCaves().size())
        return true;

    size_t level = campaign.getNumLevels();
    CampaignCaveState state = mWorld.getCaveState(campaign, cave, level);
    if((state == CampaignCaveState::locked) || (state == CampaignCaveState::hidden))
    {
        if(level < campaign.getNumLevels())
            statusText->setText(Gui::trCegui("mode.menu.campaign.cave_locked"));
        else if(!campaign.isWingAvailable(mWorld.getCaves()[cave].mWing))
            statusText->setText(Gui::toCeguiText(Translation::tr("mode.menu.campaign.wing_locked",
                {{"text", CampaignPackages::getMissingWingText()}})));
        else
            statusText->setText(Gui::trCegui("mode.menu.campaign.cave_unplayable"));
        return true;
    }

    if(level < campaign.getNumLevels())
        showBriefing(level);
    return true;
}

//! \brief Shows the unchanged story beside the actual goals and optional preview of the selected level. Title and
//! story are shown in the chosen language.
void MenuModeCampaign::showBriefing(size_t level)
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    const CampaignLevel& campaignLevel = campaign.getLevel(level);
    CEGUI::Image* image = nullptr;
    if(!campaignLevel.mPreview.empty())
        image = loadWorldImage(campaignLevel.mPreview, packageDirectoryOf(campaignLevel));
    setBriefingPreviewVisible(image != nullptr);
    if(image != nullptr)
        sheet->getChild(CMP_BRIEFING_IMAGE)->setProperty("Image", WORLD_IMAGE_PREFIX + campaignLevel.mPreview);
    std::string text = Translation::tr("mode.menu.campaign.briefing", {{"title", LevelText::display(campaignLevel.mTitle)}}) + "\n\n" + LevelText::display(campaignLevel.mBriefing);
    sheet->getChild(CMP_BRIEFING_TEXT)->setText(reinterpret_cast<const CEGUI::utf8*>(text.c_str()));
    std::string goals;
    const std::string path = CampaignPackages::getLevelFile(campaignLevel,
        ResourceManager::getSingleton().getGameDataPath());
    if(!readBriefingGoals(path, goals))
    {
        OD_LOG_ERR("Could not read campaign briefing goals from " + path);
        goals = Translation::tr("mode.menu.campaign.goals_unreadable");
    }
    Gui& gui = getModeManager().getGui();
    gui.setScaledArea(sheet->getChild(CMP_BRIEFING_TEXT), image != nullptr ?
        BRIEFING_PREVIEW_STORY_AREA : BRIEFING_STORY_AREA);
    gui.setScaledArea(sheet->getChild(CMP_BRIEFING_GOALS), image != nullptr ?
        BRIEFING_PREVIEW_GOALS_AREA : BRIEFING_GOALS_AREA);
    // The goals are text references of the goals and of the level file (one per line), shown in the chosen language
    goals = Translation::resolveLines(goals);
    sheet->getChild(CMP_BRIEFING_GOALS)->setText(reinterpret_cast<const CEGUI::utf8*>(goals.c_str()));
    sheet->getChild(CMP_BRIEFING_GOALS)->setVisible(true);
    sheet->getChild(CMP_BRIEFING_START)->setVisible(true);
    sheet->getChild(CMP_BRIEFING)->setVisible(true);
    mBriefingLevel = level;
}

//! \brief Shows the last level result in a fitted full-width text-only panel without a goal preview.
void MenuModeCampaign::showDebriefing()
{
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    setBriefingPreviewVisible(false);
    sheet->getChild(CMP_BRIEFING_GOALS)->setVisible(false);
    sheet->getChild(CMP_BRIEFING_TEXT)->setText(reinterpret_cast<const CEGUI::utf8*>(mResultText.c_str()));
    sheet->getChild(CMP_BRIEFING_START)->setVisible(false);
    sheet->getChild(CMP_BRIEFING)->setVisible(true);
    mBriefingLevel = Campaign::getSingleton().getNumLevels();
    mDebriefingScale = 0.0f;
    fitDebriefingPanel();
}

//! \brief Fits the visible text-only result to its rendered text, existing margins and Close button.
void MenuModeCampaign::fitDebriefingPanel()
{
    Gui& gui = getModeManager().getGui();
    CEGUI::Window* sheet = gui.getGuiSheet(Gui::guiSheet::campaignMenu);
    CEGUI::Window* panel = sheet->getChild(CMP_BRIEFING);
    if(!panel->isVisible() || sheet->getChild(CMP_BRIEFING_IMAGE)->isVisible() ||
       sheet->getChild(CMP_BRIEFING_START)->isVisible())
        return;

    const float scale = gui.getLayoutScale();
    const CEGUI::Sizef screen = panel->getRootContainerSize();
    if(mDebriefingScale == scale && mDebriefingScreen.d_x == screen.d_width &&
       mDebriefingScreen.d_y == screen.d_height)
        return;
    mDebriefingScale = scale;
    mDebriefingScreen = CEGUI::Vector2f(screen.d_width, screen.d_height);
    const float halfWidth = std::min(300.0f, screen.d_width / (2.0f * scale));
    const float maxHeight = screen.d_height / scale;
    // Measure at the available height so a previous scrollbar cannot add needless wrapped lines.
    gui.setScaledArea(panel, CEGUI::URect(CEGUI::UDim(0.5f, -halfWidth),
        CEGUI::UDim(0.5f, -maxHeight * 0.5f), CEGUI::UDim(0.5f, halfWidth),
        CEGUI::UDim(0.5f, maxHeight * 0.5f)));
    CEGUI::Window* text = sheet->getChild(CMP_BRIEFING_TEXT);
    gui.setScaledArea(text, BRIEFING_TEXT_AREA);
    gui.setScaledArea(sheet->getChild(CMP_BRIEFING_CLOSE), BRIEFING_CLOSE_AREA);
    const float textHeight = CEGUI::PropertyHelper<float>::fromString(text->getProperty("VertExtent"));
    const float margins = BRIEFING_TEXT_AREA.d_min.d_y.d_offset - BRIEFING_TEXT_AREA.d_max.d_y.d_offset;
    const float height = std::min(maxHeight, margins + (std::ceil(textHeight) + 1.0f) / scale);
    gui.setScaledArea(panel, CEGUI::URect(CEGUI::UDim(0.5f, -halfWidth),
        CEGUI::UDim(0.5f, -height * 0.5f), CEGUI::UDim(0.5f, halfWidth),
        CEGUI::UDim(0.5f, height * 0.5f)));
}

//! \brief Registers scaled panel and text areas around the preview, or restores the text-only layout.
void MenuModeCampaign::setBriefingPreviewVisible(bool visible)
{
    Gui& gui = getModeManager().getGui();
    CEGUI::Window* sheet = gui.getGuiSheet(Gui::guiSheet::campaignMenu);
    sheet->getChild(CMP_BRIEFING_IMAGE)->setVisible(visible);
    if(visible)
    {
        gui.setScaledArea(sheet->getChild(CMP_BRIEFING), BRIEFING_PREVIEW_PANEL_AREA);
        gui.setScaledArea(sheet->getChild(CMP_BRIEFING_TEXT), BRIEFING_PREVIEW_TEXT_AREA);
    }
    else
    {
        gui.setScaledArea(sheet->getChild(CMP_BRIEFING), BRIEFING_TEXT_PANEL_AREA);
        gui.setScaledArea(sheet->getChild(CMP_BRIEFING_TEXT), BRIEFING_TEXT_AREA);
    }
}

void MenuModeCampaign::hideBriefing()
{
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    sheet->getChild(CMP_BRIEFING)->setVisible(false);
    mBriefingLevel = Campaign::getSingleton().getNumLevels();
}

//! \brief Shows or hides the map of Moreya with its controls; the campaign end message is shown without them.
void MenuModeCampaign::setMapVisible(bool visible)
{
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    sheet->getChild(CMP_MAP)->setVisible(visible);
    sheet->getChild(CMP_CONTROL_BACKDROP)->setVisible(visible);
    sheet->getChild(CMP_BUTTON_DIFFICULTY)->setVisible(visible);
    sheet->getChild(CMP_CHECK_RELATIONSHIPS)->setVisible(visible);
    sheet->getChild(CMP_BUTTON_BACK)->setVisible(visible);
}

//! \brief Starts the level of the open briefing: the map is hidden and the camera turns from the table and flies
//! across the forecourt into the green portal; onFrameStarted loads the level once it is there. Without the menu scene
//! at the table the level is started at once.
bool MenuModeCampaign::briefingStartPressed(const CEGUI::EventArgs&)
{
    size_t level = mBriefingLevel;
    Campaign& campaign = Campaign::getSingleton();
    if((level >= campaign.getNumLevels()) || mPortalFlight)
        return true;
    if(!canStartLevel(level))
        return true;
    ODFrameListener& listener = ODFrameListener::getSingleton();
    if((listener.getMainMenuPlace() == PLACE_CAMPAIGN) && listener.flyMainMenuTo(PLACE_PORTAL))
    {
        hideBriefing();
        getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu)->setVisible(false);
        mPortalLevel = level;
        mPortalFlight = true;
        return true;
    }
    startLevel(level);
    return true;
}

//! \brief Closes the briefing; closing the campaign end message leaves for the main menu.
bool MenuModeCampaign::briefingClosePressed(const CEGUI::EventArgs& e)
{
    hideBriefing();
    if(mCampaignEnd)
        return backButtonPressed(e);
    return true;
}

//! \brief Refuses a locked, missing or changed shipped level with a message in the status text before the flight
//! into the portal; startLevel checks the same again when the level is started.
bool MenuModeCampaign::canStartLevel(size_t index)
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* mainWin = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    CEGUI::Window* statusText = mainWin->getChild(CMP_TEXT_LOADING);

    if(!campaign.isUnlocked(index))
    {
        statusText->setText(Gui::trCegui("mode.menu.campaign.level_locked"));
        return false;
    }

    std::string level = CampaignPackages::getLevelFile(campaign.getLevel(index),
        ResourceManager::getSingleton().getGameDataPath());
    if(!boost::filesystem::exists(boost::filesystem::path(level)))
    {
        OD_LOG_ERR("Campaign level not found: " + level);
        statusText->setText(Gui::trCegui("mode.menu.campaign.level_missing"));
        return false;
    }

    // A changed shipped level is rejected with its reason (the server start checks it again)
    std::string rejection;
    if(!MapHandler::checkOfficialLevel(level, false, rejection))
    {
        statusText->setText(rejection);
        return false;
    }
    return true;
}

//! \brief Starts a campaign level; a locked, missing or changed shipped level is refused with a message. Every refusal
//! shows the map again, which the flight into the portal hid.
void MenuModeCampaign::startLevel(size_t index)
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* mainWin = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    CEGUI::Window* statusText = mainWin->getChild(CMP_TEXT_LOADING);

    if(!campaign.isUnlocked(index))
    {
        statusText->setText(Gui::trCegui("mode.menu.campaign.level_locked"));
        mainWin->setVisible(true);
        return;
    }

    std::string level = CampaignPackages::getLevelFile(campaign.getLevel(index),
        ResourceManager::getSingleton().getGameDataPath());
    if(!boost::filesystem::exists(boost::filesystem::path(level)))
    {
        OD_LOG_ERR("Campaign level not found: " + level);
        statusText->setText(Gui::trCegui("mode.menu.campaign.level_missing"));
        mainWin->setVisible(true);
        return;
    }

    // A changed shipped level is rejected with its reason (the server start checks it again)
    std::string rejection;
    if(!MapHandler::checkOfficialLevel(level, false, rejection))
    {
        statusText->setText(rejection);
        mainWin->setVisible(true);
        return;
    }

    hideBriefing();
    statusText->setText(Gui::trCegui("mode.menu.loading"));

    // In single player mode, we act as a server
    campaign.startLevel(index);
    const std::string& nickname = ODFrameListener::getSingleton().getClientGameMap()->getLocalPlayerNick();
    CEGUI::ToggleButton* relationshipsCheckbox = static_cast<CEGUI::ToggleButton*>(
        mainWin->getChild(CMP_CHECK_RELATIONSHIPS));
    if(!ODServer::getSingleton().startServer(nickname, level, ServerMode::ModeGameSinglePlayer, false,
        relationshipsCheckbox->isSelected()))
    {
        OD_LOG_ERR("Could not start server for campaign game !!!");
        statusText->setText(Gui::trCegui("mode.menu.campaign.server_failed"));
        campaign.stopCampaign();
        mainWin->setVisible(true);
        return;
    }

    int port = ODServer::getSingleton().getNetworkPort();
    uint32_t timeout = ConfigManager::getSingleton().getClientConnectionTimeout();
    std::string replayFilename = ResourceManager::getSingleton().getReplayDataPath()
        + ResourceManager::getSingleton().buildReplayFilename();
    if(!ODClient::getSingleton().connect("localhost", port, timeout, replayFilename))
    {
        OD_LOG_ERR("Could not connect to server for campaign game !!!");
        statusText->setText(Gui::trCegui("mode.menu.connect_failed"));
        campaign.stopCampaign();
        mainWin->setVisible(true);
        return;
    }
}

//! \brief Leaves the campaign for the main menu; the campaign end message is closed with it.
bool MenuModeCampaign::backButtonPressed(const CEGUI::EventArgs&)
{
    mCampaignEnd = false;
    Campaign::getSingleton().stopCampaign();
    getModeManager().requestMode(AbstractModeManager::MENU_MAIN);
    return true;
}
