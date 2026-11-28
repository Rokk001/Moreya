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

#include "modes/MenuModeMultiplayerClient.h"

#include "gamemap/GameMap.h"
#include "modes/ModeManager.h"
#include "network/MultiplayerClientRules.h"
#include "network/ODServer.h"
#include "network/ODClient.h"
#include "render/Gui.h"
#include "render/ODFrameListener.h"
#include "sound/MusicPlayer.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/Translation.h"
#include "utils/LogManager.h"
#include "utils/ResourceManager.h"

#include <CEGUI/CEGUI.h>
#include <boost/locale.hpp>

MenuModeMultiplayerClient::MenuModeMultiplayerClient(ModeManager *modeManager):
    AbstractApplicationMode(modeManager, ModeManager::MENU_MULTIPLAYER_CLIENT)
{
    CEGUI::Window* window = getModeManager().getGui().getGuiSheet(Gui::guiSheet::multiplayerClientMenu);

    addEventConnection(
        window->getChild(Gui::MPM_BUTTON_CLIENT)->subscribeEvent(
            CEGUI::PushButton::EventClicked,
            CEGUI::Event::Subscriber(&MenuModeMultiplayerClient::clientButtonPressed,
                                     this)
        )
    );
    addEventConnection(
        window->getChild(Gui::MPM_BUTTON_BACK)->subscribeEvent(
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

//! \brief Shows the join menu with the saved nickname; an empty port field gets the configured network port.
void MenuModeMultiplayerClient::activate()
{
    // Loads the corresponding Gui sheet.
    Gui& gui = getModeManager().getGui();
    gui.loadGuiSheet(Gui::guiSheet::multiplayerClientMenu);

    giveFocus();

    // Play the main menu music
    MusicPlayer::getSingleton().play(ConfigManager::getSingleton().getMainMenuMusic());

    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    gameMap->clearAll();
    gameMap->setGamePaused(true);

    CEGUI::Window* mainWin = gui.getGuiSheet(Gui::guiSheet::multiplayerClientMenu);
    mainWin->getChild(Gui::MPM_TEXT_LOADING)->setText("");

    CEGUI::Editbox* editNick = static_cast<CEGUI::Editbox*>(mainWin->getChild(Gui::MPM_EDIT_NICK));
    ConfigManager& config = ConfigManager::getSingleton();
    std::string nickname = config.getGameValue(Config::NICKNAME, std::string(), false);
    if (!nickname.empty())
        editNick->setText(reinterpret_cast<const CEGUI::utf8*>(nickname.c_str()));

    // The port typed last is kept; a host with another port than this configuration can be joined by changing it
    CEGUI::Editbox* editPort = static_cast<CEGUI::Editbox*>(mainWin->getChild(Gui::MPM_EDIT_PORT));
    if(editPort->getText().empty())
        editPort->setText(Helper::toString(ODServer::getSingleton().getNetworkPort()));
}

//! \brief Checks the server IP, the nickname and the optional port (empty: the configured network port), then
//! displays the existing loading text before a blocking server connection.
bool MenuModeMultiplayerClient::clientButtonPressed(const CEGUI::EventArgs&)
{
    CEGUI::Window* mainWin = getModeManager().getGui().getGuiSheet(Gui::guiSheet::multiplayerClientMenu);
    CEGUI::Editbox* editIp = static_cast<CEGUI::Editbox*>(mainWin->getChild(Gui::MPM_EDIT_IP));
    const std::string ip = editIp->getText().c_str();

    CEGUI::Window* infoText = mainWin->getChild(Gui::MPM_TEXT_LOADING);

    if (ip.empty())
    {
        infoText->setText(Gui::trCegui("mode.menu.multiplayer.enter_ip"));
        return true;
    }

    CEGUI::Editbox* editNick = static_cast<CEGUI::Editbox*>(mainWin->getChild(Gui::MPM_EDIT_NICK));
    std::string nick = editNick->getText().c_str();
    CEGUI::String nickCeguiStr = reinterpret_cast<const CEGUI::utf8*>(nick.c_str());
    if (nickCeguiStr.empty())
    {
        infoText->setText(Gui::trCegui("mode.menu.enter_nickname"));
        return true;
    }
    else if (nickCeguiStr.length() > 20)
    {
        infoText->setText(Gui::trCegui("mode.menu.nickname_too_long"));
        return true;
    }

    CEGUI::Editbox* editPort = static_cast<CEGUI::Editbox*>(mainWin->getChild(Gui::MPM_EDIT_PORT));
    const std::string portText = editPort->getText().c_str();
    uint32_t port = 0;
    if(!MultiplayerClientRules::parsePort(portText, static_cast<uint32_t>(ODServer::getSingleton().getNetworkPort()), port))
    {
        infoText->setText(MultiplayerClientRules::INVALID_PORT_MESSAGE);
        return true;
    }

    ODFrameListener::getSingleton().getClientGameMap()->setLocalPlayerNick(nick);

    uint32_t timeout = ConfigManager::getSingleton().getClientConnectionTimeout();
    std::string replayFilename = ResourceManager::getSingleton().getReplayDataPath()
        + ResourceManager::getSingleton().buildReplayFilename();
    infoText->setText(Gui::trCegui("mode.menu.loading"));
    if(!ODClient::getSingleton().connect(ip, static_cast<int>(port), timeout, replayFilename))
    {
        // Error while connecting
        infoText->setText(Gui::toCeguiText(Translation::tr("mode.menu.multiplayer.connect_failed",
        {{"ip", ip}, {"port", Helper::toString(port)}})));
        return true;
    }

    return true;
}
