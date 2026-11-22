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

#include "modes/MenuModeEditorLoad.h"

#include "utils/Helper.h"
#include "render/Gui.h"
#include "modes/ModeManager.h"
#include "sound/MusicPlayer.h"
#include "gamemap/GameMap.h"
#include "render/ODFrameListener.h"
#include "network/ODServer.h"
#include "network/ODClient.h"
#include "network/ServerMode.h"
#include "utils/LogManager.h"
#include "gamemap/MapHandler.h"
#include "utils/ResourceManager.h"
#include "utils/ConfigManager.h"

#include <CEGUI/CEGUI.h>

#include <boost/filesystem.hpp>

//! \brief Builds the editor load menu; the shipped level types are listed only with the hidden option.
MenuModeEditorLoad::MenuModeEditorLoad(ModeManager* modeManager):
    AbstractApplicationMode(modeManager, ModeManager::MENU_EDITOR_LOAD)
{
    CEGUI::Window* window = modeManager->getGui().getGuiSheet(Gui::guiSheet::editorLoadMenu);
    

    // Fills the Level type combo box with the available level types.
    // The shipped levels are offered only with the hidden option EditOfficialLevels; the item ids stay the same.
    const CEGUI::Image* selImg = &CEGUI::ImageManager::getSingleton().get("OpenDungeonsSkin/SelectionBrush");
    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(window->getChild(Gui::EDM_LIST_LEVEL_TYPES));
    levelTypeCb->resetList();

    CEGUI::ListboxTextItem* item = nullptr;
    if(MapHandler::isEditOfficialLevelsEnabled())
    {
        item = new CEGUI::ListboxTextItem("Official Skirmish Levels", 0);
        item->setSelectionBrushImage(selImg);
        levelTypeCb->addItem(item);

        item = new CEGUI::ListboxTextItem("Official Multiplayer Levels", 1);
        item->setSelectionBrushImage(selImg);
        levelTypeCb->addItem(item);
    }

    item = new CEGUI::ListboxTextItem("Custom Skirmish Levels", 2);
    item->setSelectionBrushImage(selImg);
    levelTypeCb->addItem(item);

    item = new CEGUI::ListboxTextItem("Custom Multiplayer Levels", 3);
    item->setSelectionBrushImage(selImg);
    levelTypeCb->addItem(item);

    addEventConnection(
        window->getChild(Gui::EDM_BUTTON_LAUNCH)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeEditorLoad::launchSelectedButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(Gui::EDM_LIST_LEVELS)->subscribeEvent(
            CEGUI::Listbox::EventMouseDoubleClick,
            CEGUI::Event::Subscriber(&MenuModeEditorLoad::launchSelectedButtonPressed, this)
        )
    );
    addEventConnection(
        window->getChild(Gui::EDM_LIST_LEVELS)->subscribeEvent(
            CEGUI::Listbox::EventMouseClick,
            CEGUI::Event::Subscriber(&MenuModeEditorLoad::updateDescription, this)
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

    addEventConnection(
        window->getChild(Gui::EDM_LIST_LEVEL_TYPES)->subscribeEvent(
            CEGUI::Combobox::EventListSelectionAccepted,
            CEGUI::Event::Subscriber(&MenuModeEditorLoad::updateFilesList, this)
        )
    );
}

void MenuModeEditorLoad::activate()
{
    // Loads the corresponding Gui sheet.
    getModeManager().getGui().loadGuiSheet(Gui::editorLoadMenu);

    giveFocus();

    // Play the main menu music
    MusicPlayer::getSingleton().play(ConfigManager::getSingleton().getMainMenuMusic());

    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    gameMap->clearAll();
    gameMap->setGamePaused(true);

    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(getModeManager().getGui().
                                       getGuiSheet(Gui::editorLoadMenu)->getChild(Gui::EDM_LIST_LEVEL_TYPES));
    levelTypeCb->setItemSelectState(static_cast<size_t>(0), true);
    updateFilesList();
}

static bool findFileStemIn(const std::vector<std::string>& fileList, std::string filename)
{
    for (const std::string& file : fileList)
    {
        if (boost::filesystem::path(file).stem().string() ==
            boost::filesystem::path(filename).stem().string())
            return true;
    }
    return false;
}

//! \brief Lists the levels of the selected level type (both level extensions); shipped levels only with the hidden
//! option.
bool MenuModeEditorLoad::updateFilesList(const CEGUI::EventArgs&)
{
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::editorLoadMenu);
    CEGUI::Listbox* levelSelectList = static_cast<CEGUI::Listbox*>(window->getChild(Gui::EDM_LIST_LEVELS));

    CEGUI::Combobox* levelTypeCb = static_cast<CEGUI::Combobox*>(window->getChild(Gui::EDM_LIST_LEVEL_TYPES));

    CEGUI::Window* loadText = window->getChild(Gui::EDM_TEXT_LOADING);
    loadText->setText("");
    mFilesList.clear();
    mDescriptionList.clear();
    levelSelectList->resetList();

    std::string levelPath;
    // The item id is the level type: without the hidden option the list holds only the custom types (ids 2 and 3)
    CEGUI::ListboxItem* selectedType = levelTypeCb->getSelectedItem();
    unsigned int selection = (selectedType != nullptr) ? selectedType->getID() : 2;
    if(((selection == 0) || (selection == 1)) && !MapHandler::isEditOfficialLevelsEnabled())
        selection = 2;
    bool officialSkirmishMaps = false;
    bool officialMultiplayerMaps = false;
    switch (selection)
    {
        default:
        case 2:
            levelPath = ResourceManager::getSingleton().getUserLevelPathSkirmish();
            break;
        case 0:
            levelPath = ResourceManager::getSingleton().getGameLevelPathSkirmish();
            officialSkirmishMaps = true;
            break;
        case 1:
            levelPath = ResourceManager::getSingleton().getGameLevelPathMultiplayer();
            officialMultiplayerMaps = true;
            break;
        case 3:
            levelPath = ResourceManager::getSingleton().getUserLevelPathMultiplayer();
            break;
    }

    // Both extensions: the .mmap maps of the editor and the older own maps saved as .level
    if(MapHandler::fillLevelFilesList(levelPath, mFilesList))
    {
        std::vector<std::string> officialFileList;
        if (officialSkirmishMaps)
            levelPath = ResourceManager::getSingleton().getUserLevelPathSkirmish();
        if (officialMultiplayerMaps)
            levelPath = ResourceManager::getSingleton().getUserLevelPathMultiplayer();

        if (officialSkirmishMaps || officialMultiplayerMaps)
        {
            if (!MapHandler::fillLevelFilesList(levelPath, officialFileList))
                officialFileList.clear();
        }

        for (uint32_t n = 0; n < mFilesList.size(); ++n)
        {
            std::string filename = mFilesList[n];

            LevelInfo levelInfo;
            std::string mapName;
            std::string mapDescription;
            bool customMapExists = findFileStemIn(officialFileList, filename);
            if(MapHandler::getMapInfo(filename, levelInfo))
            {
                mapName.clear();
                if (customMapExists)
                    mapName = "[image-size='w:16 h:16'][image='OpenDungeonsIcons/CogIcon'][vert-alignment='centre'] ";
                mapName += levelInfo.mLevelName;
                mapDescription = levelInfo.mLevelDescription;
                if (customMapExists)
                    mapDescription += "\n(A custom map exists for this level.)";
            }
            else
            {
                mapName = "invalid map";
                mapDescription = "invalid map";
            }

            mDescriptionList.push_back(mapDescription);
            CEGUI::ListboxTextItem* item = new CEGUI::ListboxTextItem(mapName);
            item->setID(n);
            item->setSelectionBrushImage("OpenDungeonsSkin/SelectionBrush");
            levelSelectList->addItem(item);
        }
    }

    updateDescription();
    return true;
}

//! \brief Opens the selected level in the editor; a shipped level without the hidden option, or a changed one, is
//! refused with a message.
bool MenuModeEditorLoad::launchSelectedButtonPressed(const CEGUI::EventArgs&)
{
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::editorLoadMenu);
    CEGUI::Listbox* levelSelectList = static_cast<CEGUI::Listbox*>(window->getChild(Gui::EDM_LIST_LEVELS));

    if(levelSelectList->getSelectedCount() == 0)
    {
        window->getChild(Gui::EDM_TEXT_LOADING)->setText("Please select a level first.");
        return true;
    }

    window->getChild(Gui::EDM_TEXT_LOADING)->setText("Loading...");

    CEGUI::ListboxItem* selItem = levelSelectList->getFirstSelectedItem();
    int id = selItem->getID();

    const std::string& level = mFilesList[id];

    // A shipped level opens only with the hidden option (the server start checks it again)
    std::string refusal;
    if(!MapHandler::checkEditorMayOpen(level, refusal))
    {
        window->getChild(Gui::EDM_TEXT_LOADING)->setText(refusal);
        return true;
    }

    // In editor mode, we act as a server
    ConfigManager& config = ConfigManager::getSingleton();
    std::string nickname = config.getGameValue(Config::NICKNAME, std::string(), false);
    if(!ODServer::getSingleton().startServer(nickname, level, ServerMode::ModeEditor, false))
    {
        OD_LOG_ERR("Could not start server for editor !!!");
        window->getChild(Gui::EDM_TEXT_LOADING)->setText("ERROR: Could not start server for editor !!!");
        return true;
    }

    int port = ODServer::getSingleton().getNetworkPort();
    uint32_t timeout = ConfigManager::getSingleton().getClientConnectionTimeout();
    std::string replayFilename = ResourceManager::getSingleton().getReplayDataPath()
        + ResourceManager::getSingleton().buildReplayFilename();
    if(!ODClient::getSingleton().connect("localhost", port, timeout, replayFilename))
    {
        OD_LOG_ERR("Could not connect to server for editor !!!");
        window->getChild(Gui::EDM_TEXT_LOADING)->setText("Error: Couldn't connect to local server!");
        return true;
    }
    return true;
}

bool MenuModeEditorLoad::updateDescription(const CEGUI::EventArgs&)
{
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::editorLoadMenu);
    CEGUI::Listbox* levelSelectList = static_cast<CEGUI::Listbox*>(window->getChild(Gui::SKM_LIST_LEVELS));
    CEGUI::Window* descTxt = window->getChild("LevelWindowFrame/MapDescriptionText");

    if(levelSelectList->getSelectedCount() == 0)
    {
        descTxt->setText("");
        return true;
    }

    getModeManager().getGui().playButtonClickSound();

    // Get the level corresponding id
    CEGUI::ListboxItem* selItem = levelSelectList->getFirstSelectedItem();
    int id = selItem->getID();

    std::string description = mDescriptionList[id];
    descTxt->setText(description);
    return true;
}
