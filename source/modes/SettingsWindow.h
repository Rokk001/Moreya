/*!
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

#ifndef SETTINGSWINDOW_H
#define SETTINGSWINDOW_H


#include <CEGUI/Event.h>
#include <CEGUI/Window.h>


#include <functional>
#include <vector>
#include <string>

class Gui;

//! \brief This class is creating a setting window gui child to the current gui context
//! and populates its widgets with the current game, video, audio values.
//! It also permits to change them.
class SettingsWindow
{
public:
    //! \brief Settings window constructor
    //! \param rootWindow The main CEGUI window used as background to the current mode.
    //! Used to load and later show the settings window.
    SettingsWindow(CEGUI::Window* rootWindow, Gui& gui, bool menuPages = false, bool gamePage = false);

    ~SettingsWindow();

    void show();

    //! \brief Shows the window with the settings tab of the given name (Video, Audio, Input or Game).
    void showPage(const std::string& name);

    void hide();

    bool isVisible() const
    {
        if (mSettingsWindow)
            return mSettingsWindow->isVisible();
        return false;
    }

    //! \brief Called when pushing the cancel button on the settings window.
    bool onCancelSettings(const CEGUI::EventArgs& e = {});

    //! \brief Shows the setting "KO enemy creatures instead of killing" of the local keeper's seat on the Game page
    //! (only in a running game; the menu and the editor do not call it, so the check box stays hidden there).
    //! \param current Returns the setting of the seat; the check box shows it whenever the window is opened.
    //! \param apply Called with the check box state when the settings are applied.
    void setKoCreaturesSetting(const std::function<bool()>& current, const std::function<void(bool)>& apply);

    //! \brief Shows the current KO setting of the seat in the check box (when the setting is shown).
    void syncKoCreaturesSetting();

private:
    //! \brief Returns the KO setting of the local keeper's seat; empty outside a running game.
    std::function<bool()> mKoCreaturesCurrent;

    //! \brief Sends the KO setting chosen in the check box to the server; empty outside a running game.
    std::function<void(bool)> mKoCreaturesApply;

    //! \brief Vector of cegui event bindings to be cleared on exiting the mode
    std::vector<CEGUI::Event::Connection> mEventConnections;

    //! \brief The Settings window.
    CEGUI::Window* mSettingsWindow;

    //! \brief The apply change pop-up
    CEGUI::Window* mApplyWindow;

    //! \brief The root window.
    CEGUI::Window* mRootWindow;

    //! \brief Used to apply the UI scale and to register the generated windows for scaling
    Gui& mGui;

    //! \brief The temporary video comboboxes and texts created depending on the video settings.
    std::vector<CEGUI::Window*> mCustomVideoComboBoxes;
    std::vector<CEGUI::Window*> mCustomVideoTexts;

    //! \brief Updates the page title when another settings tab is selected (in game window).
    bool onSelectedTabChanged(const CEGUI::EventArgs&);

    //! \brief Set the different widget values according to current config.
    void initConfig();

    //! \brief Save and apply the config. Returns false if a selected value could not be applied.
    bool saveConfig();

    //! \brief Adds an event binding to be cleared on exiting the mode.
    inline void addEventConnection(CEGUI::Event::Connection conn)
    {
        mEventConnections.emplace_back(conn);
    }

    //! \brief Called when pushing the apply button on the settings window.
    bool onApplySettings(const CEGUI::EventArgs&);

    //! \brief Called when pushing the cancel button on the change appliance popup.
    bool onPopupCancelApplySettings(const CEGUI::EventArgs&);

    //! \brief Called when pushing the apply button on the change appliance popup.
    bool onPopupApplySettings(const CEGUI::EventArgs&);

    //! \brief Called when changing the music volume value.
    bool onMusicVolumeChanged(const CEGUI::EventArgs&);

    //! \brief Set the volume value in the volume setting text and slider.
    void setMusicVolumeValue(float volume);

    //! \brief Called when changing the ambient light factor value.
    bool onLightFactorChanged(const CEGUI::EventArgs&);
    bool onPanSpeedChanged(const CEGUI::EventArgs&);

    //! \brief Applies the selected UI scale immediately.
    bool onUiScaleChanged(const CEGUI::EventArgs&);

    //! \brief Set the volume value in the ambient light factor setting text and slider.
    void setLightFactorValue(float lightFactor);
    void setPanSpeedValue(float panSpeedPercent);

};

#endif // SETTINGSWINDOW_H
