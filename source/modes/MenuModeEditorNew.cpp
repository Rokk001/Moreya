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

#include "modes/MenuModeEditorNew.h"

#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/MapHandler.h"
#include "modes/ModeManager.h"
#include "network/ODServer.h"
#include "network/ODClient.h"
#include "network/ServerMode.h"
#include "render/Gui.h"
#include "render/ODFrameListener.h"
#include "render/LoadingScreen.h"
#include "sound/MusicPlayer.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/Translation.h"
#include "utils/LevelFileNameInput.h"
#include "utils/LogManager.h"
#include "utils/MapSizeInput.h"
#include "utils/ResourceManager.h"

#include <CEGUI/CEGUI.h>
#include <boost/filesystem.hpp>

const std::string TEXT_LOADING = "LoadingText";
const std::string BUTTON_LAUNCH = "LevelWindowFrame/LaunchEditorButton";
const std::string BUTTON_BACK = "LevelWindowFrame/BackButton";
const std::string LIST_LEVEL_TYPES = "LevelWindowFrame/LevelTypeSelect";

namespace
{
    //! \brief Writes the texts of the items of the Level type combo box in the chosen language. The items are found
    //! by their id (0 and 1), so that the selection stays when the language changes.
    void translateLevelTypeItems(CEGUI::Combobox* levelTypeCb)
    {
        static const char* const KEYS[2] = {"editor.leveltype.skirmish", "editor.leveltype.multiplayer"};
        for(size_t i = 0; i < levelTypeCb->getItemCount(); ++i)
        {
            CEGUI::ListboxItem* item = levelTypeCb->getListboxItemFromIndex(i);
            if(item->getID() >= 2)
                continue;
            item->setText(Gui::trCegui(KEYS[item->getID()]));
            if(item->isSelected())
                levelTypeCb->setText(item->getText());
        }
        levelTypeCb->invalidate();
    }
}

MenuModeEditorNew::MenuModeEditorNew(ModeManager* modeManager):
    AbstractApplicationMode(modeManager, ModeManager::MENU_EDITOR_NEW)
{
    CEGUI::Window* window = modeManager->getGui().getGuiSheet(Gui::guiSheet::editorNewMenu);

    // Fills the Level type combo box with the available level types.
    const CEGUI::Image* selImg = &CEGUI::ImageManager::getSingleton().get("OpenDungeonsSkin/SelectionBrush");
    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(window->getChild(LIST_LEVEL_TYPES));
    levelTypeCb->resetList();

    CEGUI::ListboxTextItem* item = new CEGUI::ListboxTextItem(Gui::trCegui("editor.leveltype.skirmish"), 0);
    item->setSelectionBrushImage(selImg);
    levelTypeCb->addItem(item);

    item = new CEGUI::ListboxTextItem(Gui::trCegui("editor.leveltype.multiplayer"), 1);
    item->setSelectionBrushImage(selImg);
    levelTypeCb->addItem(item);

    translateLevelTypeItems(levelTypeCb);

    addEventConnection(
        window->getChild(Gui::EDM_BUTTON_LAUNCH)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeEditorNew::launchSelectedButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(Gui::EDM_BUTTON_BACK)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&AbstractApplicationMode::goBack,
                                     static_cast<AbstractApplicationMode*>(this))
        )
    );
    addEventConnection(
        window->getChild("LevelWindowFrame")->subscribeEvent(
            CEGUI::FrameWindow::EventCloseClicked,
            CEGUI::Event::Subscriber(&AbstractApplicationMode::goBack,
                                     static_cast<AbstractApplicationMode*>(this))
        )
    );
}

void MenuModeEditorNew::activate()
{
    // Loads the corresponding Gui sheet.
    getModeManager().getGui().loadGuiSheet(Gui::editorNewMenu);

    giveFocus();

    // Play the main menu music
    MusicPlayer::getSingleton().play(ConfigManager::getSingleton().getMainMenuMusic());

    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    gameMap->clearAll();
    gameMap->setGamePaused(true);

    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::editorNewMenu);
    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(window->getChild(LIST_LEVEL_TYPES));
    levelTypeCb->setItemSelectState(static_cast<size_t>(0), true);

    window->getChild(TEXT_LOADING)->setText("");
}

//! \brief Presents loading before creating, writing and opening the new editor map. The file name must be a plain
//! name in the user level folder.
bool MenuModeEditorNew::launchSelectedButtonPressed(const CEGUI::EventArgs&)
{
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::editorNewMenu);

    window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.creating"));

    // Creating the filename
    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(getModeManager().getGui().
                                       getGuiSheet(Gui::editorNewMenu)->getChild(LIST_LEVEL_TYPES));
    std::string levelPath;
    size_t selection = levelTypeCb->getItemIndex(levelTypeCb->getSelectedItem());
    switch (selection)
    {
        default:
        case 0:
            levelPath = ResourceManager::getSingleton().getUserLevelPathSkirmish();
            break;
        case 1:
            levelPath = ResourceManager::getSingleton().getUserLevelPathMultiplayer();
            break;
    }
    CEGUI::Editbox* editWin = static_cast<CEGUI::Editbox*>(window->getChild("LevelWindowFrame/LevelFilenameEdit"));
    std::string level = editWin->getText().c_str();
    Helper::trim(level);
    if (level.empty()) {
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.filename_missing"));
        return true;
    }
    // The map is made in the user level folder: a name with a folder or ".." could put it anywhere else
    if(!LevelFileNameInput::isPlainFileName(level))
    {
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.filename_plain"));
        return true;
    }

    level = levelPath + "/" + level;
    // Maps made in the editor carry the .mmap extension (a typed .level becomes .mmap, so that the map never
    // looks like a shipped level). It is added before the test, so that the file that would be written is tested.
    boost::filesystem::path pp (level);
    if (pp.extension() == MapHandler::LEVEL_EXTENSION) {
        level = pp.replace_extension(MapHandler::USER_MAP_EXTENSION).string();
    }
    else if (pp.extension() != MapHandler::USER_MAP_EXTENSION) {
        level.append(MapHandler::USER_MAP_EXTENSION);
    }
    if (boost::filesystem::exists(level)) {
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.filename_exists"));
        return true;
    }

    // Get the map size.
    editWin = static_cast<CEGUI::Editbox*>(window->getChild("LevelWindowFrame/LevelWidthEdit"));
    std::string widthStr = editWin->getText().c_str();
    editWin = static_cast<CEGUI::Editbox*>(window->getChild("LevelWindowFrame/LevelHeightEdit"));
    std::string heightStr = editWin->getText().c_str();
    int32_t width = 0;
    int32_t height = 0;
    if (!MapSizeInput::parse(widthStr, width) || !MapSizeInput::parse(heightStr, height)) {
        window->getChild(TEXT_LOADING)->setText(Gui::toCeguiText(Translation::tr("editor.new.size_invalid",
            {{"max", Helper::toString(MapSizeInput::MAX_SIZE)}})));
        return true;
    }

    window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.loading"));
    LoadingScreen loading;

    // Create the level before opening it.
    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    gameMap->clearAll();
    gameMap->setGamePaused(true);
    if(!gameMap->createNewMap(width, height))
    {
        OD_LOG_WRN("Couldn't create a new map of size " + Helper::toString(width) + "x" + Helper::toString(height));
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.create_failed"));
        return true;
    }
    gameMap->setLevelFileName(level);
    editWin = static_cast<CEGUI::Editbox*>(window->getChild("LevelWindowFrame/LevelTitleEdit"));
    std::string levelTitle = editWin->getText().c_str();
    if (levelTitle.empty()) {
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.title_missing"));
        return true;
    }
    gameMap->setLevelName(levelTitle);
    CEGUI::MultiLineEditbox* meditWin = static_cast<CEGUI::MultiLineEditbox*>(
        window->getChild("LevelWindowFrame/LevelDescriptionEdit"));
    gameMap->setLevelDescription(meditWin->getText().c_str());

    // We create some basic map at first. The map maker will be able to add/edit map properties
    // once the map editor has run.
    gameMap->setTileSetName(std::string()); // default one.
    gameMap->setLevelMusicFile("Searching_yd.ogg");
    gameMap->setLevelFightMusicFile("TheDarkAmulet_MP.ogg");
    Seat* seat = new Seat(gameMap);
    seat->setId(1);
    seat->setTeamId(1);
    seat->setPlayerType("Human");
    seat->setFaction("Keeper");
    seat->setColorId("1");
    if(!gameMap->addSeat(seat))
    {
        OD_LOG_WRN("Couldn't add seat id=" + Helper::toString(seat->getId()));
        delete seat;
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.seat_invalid"));
        return true;
    }

    if (!MapHandler::writeGameMapToFile(level, *gameMap)) {
        OD_LOG_WRN("Couldn't write new map before loading: " + level);
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.write_failed"));
        return true;
    }

    // In editor mode, we act as a server
    ConfigManager& config = ConfigManager::getSingleton();
    std::string nickname = config.getGameValue(Config::NICKNAME, std::string(), false);
    if(!ODServer::getSingleton().startServer(nickname, level, ServerMode::ModeEditor, false))
    {
        OD_LOG_ERR("Could not start server for editor!");
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.server_failed"));
        return true;
    }

    int port = ODServer::getSingleton().getNetworkPort();
    uint32_t timeout = ConfigManager::getSingleton().getClientConnectionTimeout();
    std::string replayFilename = ResourceManager::getSingleton().getReplayDataPath()
        + ResourceManager::getSingleton().buildReplayFilename();
    if(!ODClient::getSingleton().connect("localhost", port, timeout, replayFilename))
    {
        OD_LOG_ERR("Could not connect to server for editor!");
        window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.connect_failed"));
        return true;
    }
    window->getChild(TEXT_LOADING)->setText(Gui::trCegui("editor.new.created"));
    loading.continueLoading();
    return true;
}
