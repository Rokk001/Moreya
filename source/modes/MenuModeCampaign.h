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

#ifndef MENUMODECAMPAIGN_H
#define MENUMODECAMPAIGN_H

#include "AbstractApplicationMode.h"

#include "game/CampaignWorld.h"

#include <CEGUI/Vector.h>

#include <cstdint>
#include <string>
#include <vector>

namespace CEGUI
{
class Image;
}

//! \brief The campaign menu: the map of Moreya. Each of its 6 wings has 3 caves, one per story level, and a
//! bonus cave that appears once its hidden stone was found. A cave that can be played (the current level, a
//! defeated level or a found bonus cave) opens its briefing on a click. In front of the gate stands the guild that
//! raids the current level with its banner, the portrait of its leader, the raid size and its origin. A tooltip
//! names the cave under the mouse, the wings show how many of their levels are defeated and a panel shows the
//! progress of the campaign.
class MenuModeCampaign: public AbstractApplicationMode
{
public:
    //! \brief Connects the buttons and the map of the campaign sheet to this mode
    MenuModeCampaign(ModeManager*);

    //! \brief Called when the mode is activated
    //! Used to call the corresponding Gui Sheet.
    void activate() final override;

    //! \brief Fits a visible debriefing after screen or UI-scale changes
    void onFrameStarted(const Ogre::FrameEvent& evt) override;

    //! \brief Reads the campaign definition and the saved progress from disk.
    //! Returns false if there is no campaign definition.
    static bool loadCampaign();

private:
    //! \brief Debriefing text of the level that was played last (empty if none)
    std::string mResultText;
    //! The map of Moreya: wings, caves, guilds and panels
    CampaignWorld mWorld;
    bool mWorldLoaded;
    //! Windows on the map (markers, texts, guild panel), destroyed with clearMap()
    std::vector<CEGUI::Window*> mWorldWindows;
    //! Ring drawn around the cave under the mouse
    CEGUI::Window* mHoverWindow;
    CEGUI::Window* mTooltip;
    //! State of every cave of the map with the current progress, set by fillMap()
    std::vector<CampaignCaveState> mCaveStates;
    //! Level of the open briefing, or the number of levels if none
    size_t mBriefingLevel;
    //! Screen dimensions and GUI scale used by the last debriefing fit.
    CEGUI::Vector2f mDebriefingScreen;
    float mDebriefingScale;

    //! \brief Reads the map description once. Returns false if it cannot be read or is invalid.
    bool loadWorld();
    //! \brief The image of the world art file (relative to gui/campaign), loaded on first use.
    //! Returns NULL if it cannot be read.
    CEGUI::Image* loadWorldImage(const std::string& file);
    //! \brief Draws the caves in their states, the wing progress, the guild in front of the gate, the title and
    //! the progress panel on the map
    void fillMap();
    //! \brief Shows the guild of the current level in front of the gate; nothing when the campaign is finished
    void fillGuildPanel();
    //! \brief Writes the defeated levels, wings, shards and cleared bonus caves and the bar in the progress panel
    void fillProgressPanel();
    //! \brief Creates a text window on the map without frame and background
    CEGUI::Window* createMapText(const std::string& name, const CampaignWorldRect& area, const std::string& font,
        const std::string& colour, const std::string& formatting, const std::string& text);
    //! \brief Creates an image window on the map for a campaign art file; returns NULL if the image cannot be read
    CEGUI::Window* createMapImage(const std::string& name, const std::string& file, float x, float y, float width,
        float height);
    //! \brief Removes everything fillMap drew
    void clearMap();
    //! \brief Places a window on the map. The values are map pixels, the window gets the share of the map they cover.
    void setMapArea(CEGUI::Window* window, float x, float y, float width, float height) const;
    //! \brief Creates a window of that type on the map at the area in map pixels; the map handles the mouse itself
    CEGUI::Window* createMapWindow(const std::string& type, const std::string& name, float x, float y,
        float width, float height);
    //! \brief The cave under the screen position on the map window, or the number of caves if there is none
    size_t findCaveAt(const CEGUI::Vector2f& position, const CEGUI::Window* map) const;
    //! \brief Shows the ring around the cave under the mouse, or hides it when there is none
    void updateHover(size_t cave);
    //! \brief Shows the tooltip of the cave under the mouse, or hides it when there is none
    void updateTooltip(const CEGUI::Vector2f& position, size_t cave);
    //! \brief Shows the unchanged story beside the level goals and its preview when available.
    void showBriefing(size_t level);
    //! \brief Shows the last level result fitted to its text without a preview or goal list.
    void showDebriefing();
    //! \brief Fits a visible debriefing to rendered text and existing margins, limited to the screen.
    void fitDebriefingPanel();
    //! \brief Shows or hides the preview and registers scaled panel and text areas.
    void setBriefingPreviewVisible(bool visible);
    //! \brief Closes the briefing or debriefing panel
    void hideBriefing();
    //! \brief Starts the server and the client for a campaign level
    void startLevel(size_t index);

    //! \brief The mouse moves over the map: the cave below it is highlighted and named in the tooltip
    bool mapMoved(const CEGUI::EventArgs& e);
    //! \brief The mouse leaves the map: the highlight and the tooltip are removed
    bool mapLeft(const CEGUI::EventArgs& e);
    //! \brief A click on the current cave, a defeated cave or a found bonus cave opens its briefing
    bool mapClicked(const CEGUI::EventArgs& e);
    //! \brief Starts the level of the open briefing
    bool briefingStartPressed(const CEGUI::EventArgs&);
    //! \brief Closes the briefing without starting the level
    bool briefingClosePressed(const CEGUI::EventArgs&);
    //! \brief Chooses the next difficulty while no level is completed
    bool difficultyButtonPressed(const CEGUI::EventArgs&);
    //! \brief Shows the difficulty of the campaign on its button
    void updateDifficultyButton();
    //! \brief Leaves the campaign and shows the main menu
    bool backButtonPressed(const CEGUI::EventArgs&);
};

#endif // MENUMODECAMPAIGN_H
