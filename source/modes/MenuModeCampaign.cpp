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
#include "modes/ModeManager.h"
#include "network/ODClient.h"
#include "network/ODServer.h"
#include "network/ServerMode.h"
#include "render/Gui.h"
#include "render/ODFrameListener.h"
#include "sound/MusicPlayer.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "utils/ResourceManager.h"
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

//! Size of the tooltip window and its distance from the mouse, in design pixels of the 1024 x 768 layout; the
//! window is scaled with the layout (screen size and UI scale) and never larger than the map
const float TOOLTIP_WIDTH = 420.0f;
const float TOOLTIP_HEIGHT = 150.0f;
const float TOOLTIP_OFFSET = 48.0f;
//! Size of the ring around the cave under the mouse, relative to the cave marker
const float HOVER_SCALE = 1.2f;
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
//! \return True when level goal metadata was read; no game state or script action is executed.
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
    descriptions = "Goals:";
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
                    optionalObjectives.push_back(action.mText);
                else
                    mainObjectives.push_back(action.mText);
            }
        }
        if(!mainObjectives.empty() || !optionalObjectives.empty())
        {
            descriptions = "Main goals";
            for(const std::string& objective : mainObjectives)
                descriptions += "\n[image='GoalStatus/Open'] " + objective;
            descriptions += "\n\nOptional goals";
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
                    descriptions += "\nHint: " + action.mText;
                    continue;
                }
                descriptions += "\n[image='GoalStatus/Open'] " + action.mText;
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
} // namespace

//! \brief Connects campaign controls and initializes map and debriefing layout state.
MenuModeCampaign::MenuModeCampaign(ModeManager* modeManager):
    AbstractApplicationMode(modeManager, ModeManager::MENU_CAMPAIGN),
    mWorldLoaded(false),
    mHoverWindow(nullptr),
    mTooltip(nullptr),
    mBriefingLevel(0),
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
        mResultText = Campaign::CAMPAIGN_END_MESSAGE;
    }
    else if(playedLevel < campaign.getNumLevels())
    {
        const CampaignLevel& level = campaign.getLevel(playedLevel);
        playedLevelWon = campaign.getPlayedLevelWon();
        if(playedLevelWon)
        {
            mResultText = "Debriefing - " + level.mTitle + "\n\n" + level.mDebriefing + "\n\n";
            if(level.mBonus)
            {
                mResultText += "You have cleared the hidden chamber.";
            }
            else
                mResultText += "The next level is unlocked.";

            // The numbers of the level, as sent by the server when it was won
            std::string summary = campaign.getLevelSummary();
            if(!summary.empty())
                mResultText += "\n\n" + summary;
        }
        else
        {
            OD_LOG_INF("Campaign menu shows the lost-level message for level " + Helper::toString(playedLevel));
            mResultText = "You did not complete this level. You can try again.";
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
        window->getChild(CMP_TEXT_LOADING)->setText("ERROR: The campaign map of Moreya could not be loaded.");
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
    name[0] = static_cast<char>(std::toupper(static_cast<unsigned char>(name[0])));
    button->setText("Difficulty: " + name);
    // The difficulty is chosen when a new campaign is begun and then stays
    button->setEnabled(!campaign.hasProgress());
    button->setTooltipText(!campaign.hasProgress() && !campaign.isHellUnlocked() ? "Finish the campaign on Hard to unlock Hell." : "");
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
    std::ifstream definition((directory + WORLD_DEFINITION_FILE).c_str());
    if(!definition.is_open() || !mWorld.importDefinition(definition))
    {
        OD_LOG_ERR("Could not read the campaign map of Moreya " + directory + WORLD_DEFINITION_FILE);
        return false;
    }

    mWorldLoaded = true;
    return true;
}

CEGUI::Image* MenuModeCampaign::loadWorldImage(const std::string& file)
{
    std::string name = WORLD_IMAGE_PREFIX + file;
    CEGUI::ImageManager& images = CEGUI::ImageManager::getSingleton();
    if(images.isDefined(name))
        return &images.get(name);

    int width = 0;
    int height = 0;
    std::vector<uint8_t> rgba;
    std::string path = ResourceManager::getSingleton().getGameDataPath() + WORLD_DIRECTORY + file;
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
CEGUI::Window* MenuModeCampaign::createMapImage(const std::string& name, const std::string& file, float x, float y,
    float width, float height)
{
    if(file.empty() || (loadWorldImage(file) == nullptr))
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
            // coming in Early Access
            createMapText("Wing_" + wingId, wing.mLabel, FONT_WING, COLOUR_LOCKED, "WordWrapLeftAligned", wing.mName);
            continue;
        }
        createMapText("Wing_" + wingId, wing.mLabel, FONT_WING, wingDefeated ? COLOUR_HIGHLIGHT : COLOUR_TEXT,
            "WordWrapLeftAligned", wing.mName + "   " + Helper::toString(defeated) + " / "
            + Helper::toString(CampaignWorld::STORY_CAVES_PER_WING));
        if(wingDefeated)
        {
            float size = static_cast<float>(wing.mSealSize);
            createMapImage("WingSeal_" + wingId, mWorld.getIcons().mWingDefeated,
                static_cast<float>(wing.mSealX) - size / 2.0f, static_cast<float>(wing.mSealY) - size / 2.0f, size, size);
        }
    }

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
        createMapImage("Cave_" + caveId, *icon, static_cast<float>(cave.mX) - size / 2.0f,
            static_cast<float>(cave.mY) - size / 2.0f, size, size);

        // The name of a level stands under its cave; a bonus cave names itself in its tooltip. The caves of a wing
        // without package say that the wing is coming in Early Access.
        size_t level = mWorld.findLevel(campaign, i);
        if(!cave.mBonus && (level < campaign.getNumLevels()))
        {
            createMapText("CaveName_" + caveId, cave.mLabel, FONT_CAVE, colour, "WordWrapCentreAligned",
                campaign.getLevel(level).mTitle);
        }
        else if(!cave.mBonus && !campaign.isWingAvailable(cave.mWing))
        {
            createMapText("CaveName_" + caveId, cave.mLabel, FONT_CAVE, colour, "WordWrapCentreAligned",
                CampaignPackages::MISSING_WING_TEXT);
        }
    }

    fillGuildPanel();

    // The title in the cartouche
    createMapText("Title", mWorld.getTitleCartouche(), FONT_TITLE, COLOUR_HIGHLIGHT, "CentreAligned", CAMPAIGN_TITLE);

    fillProgressPanel();

    // The tooltip is the topmost window of the map
    mTooltip = createMapWindow("OD/StaticText", "Tooltip", 0, 0, 1, 1);
    mTooltip->setProperty("Font", FONT_TOOLTIP);
    mTooltip->setProperty("HorzFormatting", "WordWrapLeftAligned");
    mTooltip->setProperty("VertFormatting", "CentreAligned");
    mTooltip->setVisible(false);
}

//! \brief Shows the banner, the leader's portrait, the name, leader, raid size and origin of the guild that raids the
//! current level in front of the gate. Once every story level is defeated no guild comes any more.
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

    const CampaignWorldGuild& guild = campaign.getLevel(level).mGuild;
    if(guild.mName.empty())
        return;
    const CampaignWorldGuildPanel& panel = mWorld.getGuildPanel();
    createMapImage("GuildBanner", guild.mBanner, static_cast<float>(panel.mBanner.mX),
        static_cast<float>(panel.mBanner.mY), static_cast<float>(panel.mBanner.mWidth),
        static_cast<float>(panel.mBanner.mHeight));
    createMapImage("GuildPortrait", guild.mPortrait, static_cast<float>(panel.mPortrait.mX),
        static_cast<float>(panel.mPortrait.mY), static_cast<float>(panel.mPortrait.mWidth),
        static_cast<float>(panel.mPortrait.mHeight));
    createMapText("GuildName", panel.mName, FONT_GUILD_NAME, COLOUR_HIGHLIGHT, "WordWrapLeftAligned", guild.mName);
    createMapText("GuildDetails", panel.mDetails, FONT_GUILD_DETAILS, COLOUR_TEXT, "WordWrapLeftAligned",
        CampaignWorld::getGuildDetailsText(guild));
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
        "Levels defeated: " + Helper::toString(levelsDefeated) + " / " + Helper::toString(levelTotal)
        + "\nWings defeated: " + Helper::toString(wingsDefeated) + " / " + Helper::toString(static_cast<uint32_t>(wings.size()))
        + "\nHeartstone shards: " + Helper::toString(static_cast<uint32_t>(campaign.getHeartstonePieces())) + " / "
        + Helper::toString(static_cast<uint32_t>(campaign.getHeartstoneTotal()))
        + "\nBonus caves cleared: " + Helper::toString(bonusCleared) + " / " + Helper::toString(bonusTotal));

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

//! \brief Fits a visible debriefing after display or UI-scale changes.
void MenuModeCampaign::onFrameStarted(const Ogre::FrameEvent&)
{
    fitDebriefingPanel();
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

//! \brief Puts the ring around a cave that can be played; locked caves and empty map get no ring.
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
    setMapArea(mHoverWindow, static_cast<float>(worldCave.mX) - size / 2.0f,
        static_cast<float>(worldCave.mY) - size / 2.0f, size, size);
    mHoverWindow->setVisible(true);
}

//! \brief Names the cave under the mouse: level title, wing, guild and state (a level has no difficulty of its
//! own). The tooltip is scaled with the layout and kept inside the map.
void MenuModeCampaign::updateTooltip(const CEGUI::Vector2f& position, size_t cave)
{
    if(mTooltip == nullptr)
        return;

    const std::vector<CampaignWorldCave>& caves = mWorld.getCaves();
    if((cave >= caves.size()) || (cave >= mCaveStates.size()))
    {
        mTooltip->setVisible(false);
        return;
    }

    Campaign& campaign = Campaign::getSingleton();
    const CampaignWorldCave& worldCave = caves[cave];
    size_t level = mWorld.findLevel(campaign, cave);
    bool known = (level < campaign.getNumLevels());
    std::string text = known ? campaign.getLevel(level).mTitle : CampaignPackages::MISSING_WING_TEXT;
    std::string wingName;
    if((worldCave.mWing >= 1) && (worldCave.mWing <= mWorld.getWings().size()))
        wingName = mWorld.getWings()[worldCave.mWing - 1].mName;
    if(worldCave.mBonus)
        text += "\nBonus cave of " + wingName;
    else if(known && !campaign.getLevel(level).mGuild.mName.empty())
        text += "\n" + wingName + "\nGuild: " + campaign.getLevel(level).mGuild.mName;
    else
        text += "\n" + wingName;

    switch(mCaveStates[cave])
    {
        case CampaignCaveState::locked:
            text += "\nState: Locked";
            break;
        case CampaignCaveState::current:
            text += "\nState: Current level";
            break;
        case CampaignCaveState::defeated:
            text += "\nState: Defeated, can be played again";
            break;
        case CampaignCaveState::bonusFound:
            text += "\nState: Found";
            break;
        case CampaignCaveState::bonusCleared:
            text += "\nState: Cleared, can be played again";
            break;
        case CampaignCaveState::hidden:
            mTooltip->setVisible(false);
            return;
    }
    const float scale = getModeManager().getGui().getLayoutScale();
    const CEGUI::Rectf& mapRect = mTooltip->getParent()->getUnclippedOuterRect().get();
    float width = std::min(TOOLTIP_WIDTH * scale, mapRect.getWidth());
    float height = std::min(TOOLTIP_HEIGHT * scale, mapRect.getHeight());
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
    mTooltip->setArea(CEGUI::UDim(0, x), CEGUI::UDim(0, y), CEGUI::UDim(0, width), CEGUI::UDim(0, height));
    mTooltip->setText(reinterpret_cast<const CEGUI::utf8*>(text.c_str()));
    mTooltip->setVisible(true);
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
    if(mTooltip != nullptr)
        mTooltip->setVisible(false);
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
            statusText->setText("This cave is locked. Defeat the levels before it first.");
        else if(!campaign.isWingAvailable(mWorld.getCaves()[cave].mWing))
            statusText->setText("This wing is locked: " + CampaignPackages::MISSING_WING_TEXT + ".");
        else
            statusText->setText("This cave cannot be played yet.");
        return true;
    }

    if(level < campaign.getNumLevels())
        showBriefing(level);
    return true;
}

//! \brief Shows the unchanged story beside the actual goals and optional preview of the selected level.
void MenuModeCampaign::showBriefing(size_t level)
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* sheet = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    const CampaignLevel& campaignLevel = campaign.getLevel(level);
    CEGUI::Image* image = nullptr;
    if(!campaignLevel.mPreview.empty())
        image = loadWorldImage(campaignLevel.mPreview);
    setBriefingPreviewVisible(image != nullptr);
    if(image != nullptr)
        sheet->getChild(CMP_BRIEFING_IMAGE)->setProperty("Image", WORLD_IMAGE_PREFIX + campaignLevel.mPreview);
    std::string text = "Briefing - " + campaignLevel.mTitle + "\n\n" + campaignLevel.mBriefing;
    sheet->getChild(CMP_BRIEFING_TEXT)->setText(reinterpret_cast<const CEGUI::utf8*>(text.c_str()));
    std::string goals;
    const std::string path = CampaignPackages::getLevelFile(campaignLevel,
        ResourceManager::getSingleton().getGameDataPath());
    if(!readBriefingGoals(path, goals))
    {
        OD_LOG_ERR("Could not read campaign briefing goals from " + path);
        goals = "Goals: Could not read level goals.";
    }
    Gui& gui = getModeManager().getGui();
    gui.setScaledArea(sheet->getChild(CMP_BRIEFING_TEXT), image != nullptr ?
        BRIEFING_PREVIEW_STORY_AREA : BRIEFING_STORY_AREA);
    gui.setScaledArea(sheet->getChild(CMP_BRIEFING_GOALS), image != nullptr ?
        BRIEFING_PREVIEW_GOALS_AREA : BRIEFING_GOALS_AREA);
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

bool MenuModeCampaign::briefingStartPressed(const CEGUI::EventArgs&)
{
    size_t level = mBriefingLevel;
    if(level < Campaign::getSingleton().getNumLevels())
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

void MenuModeCampaign::startLevel(size_t index)
{
    Campaign& campaign = Campaign::getSingleton();
    CEGUI::Window* mainWin = getModeManager().getGui().getGuiSheet(Gui::guiSheet::campaignMenu);
    CEGUI::Window* statusText = mainWin->getChild(CMP_TEXT_LOADING);

    if(!campaign.isUnlocked(index))
    {
        statusText->setText("This level is locked. Complete the previous levels first.");
        return;
    }

    std::string level = CampaignPackages::getLevelFile(campaign.getLevel(index),
        ResourceManager::getSingleton().getGameDataPath());
    if(!boost::filesystem::exists(boost::filesystem::path(level)))
    {
        OD_LOG_ERR("Campaign level not found: " + level);
        statusText->setText("ERROR: Campaign level file not found.");
        return;
    }

    hideBriefing();
    statusText->setText("Loading...");

    // In single player mode, we act as a server
    campaign.startLevel(index);
    const std::string& nickname = ODFrameListener::getSingleton().getClientGameMap()->getLocalPlayerNick();
    CEGUI::ToggleButton* relationshipsCheckbox = static_cast<CEGUI::ToggleButton*>(
        mainWin->getChild(CMP_CHECK_RELATIONSHIPS));
    if(!ODServer::getSingleton().startServer(nickname, level, ServerMode::ModeGameSinglePlayer, false,
        relationshipsCheckbox->isSelected()))
    {
        OD_LOG_ERR("Could not start server for campaign game !!!");
        statusText->setText("ERROR: Could not start server for campaign game !!!");
        campaign.stopCampaign();
        return;
    }

    int port = ODServer::getSingleton().getNetworkPort();
    uint32_t timeout = ConfigManager::getSingleton().getClientConnectionTimeout();
    std::string replayFilename = ResourceManager::getSingleton().getReplayDataPath()
        + ResourceManager::getSingleton().buildReplayFilename();
    if(!ODClient::getSingleton().connect("localhost", port, timeout, replayFilename))
    {
        OD_LOG_ERR("Could not connect to server for campaign game !!!");
        statusText->setText("Error: Couldn't connect to local server!");
        campaign.stopCampaign();
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
