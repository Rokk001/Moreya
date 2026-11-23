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

//! \brief The campaign menu: the map of Moreya, carved into stone. Each of its 6 wings has 3 caves, one per story
//! level, and a bonus cave that appears once its hidden stone was found. A cave that can be played (the current level,
//! a defeated level or a found bonus cave) opens its briefing on a click. The current level glows with a golden arrow
//! above it, and a wing that is still locked is greyed out. On a carved stone slab stands the guild that raids the
//! current level with its banner, the portrait of its leader, the raid size and its origin; a trail of embers leads
//! from it to the current level, where its banner stands. A small carved tablet names the cave under the mouse, the
//! wings show how many of their levels are defeated and a panel shows the progress of the campaign. After a win that leaves every guild defeated the map is not shown: the campaign end
//! message appears and closing it shows the main menu; opening the campaign again shows the map for replays.
class MenuModeCampaign: public AbstractApplicationMode
{
public:
    //! \brief Connects the buttons and the map of the campaign sheet to this mode
    MenuModeCampaign(ModeManager*);

    //! \brief Called when the mode is activated
    //! Used to call the corresponding Gui Sheet.
    void activate() final override;

    //! \brief Fits a visible debriefing after screen or UI-scale changes and starts the chosen level once the camera
    //! has flown into the portal
    void onFrameStarted(const Ogre::FrameEvent& evt) override;

    //! \brief Ignores Escape while the camera flies into the portal to start a level; every other key (the
    //! screenshot key too) works as in every menu
    bool keyPressed(const OIS::KeyEvent& arg) override;

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
    //! Text of the hover display, inside its carved stone tablet mTooltipPlaque
    CEGUI::Window* mTooltip;
    //! Carved stone tablet of the hover display; it is shown and hidden with its text
    CEGUI::Window* mTooltipPlaque;
    //! Golden glow under the current level and the golden arrow above it, animated by updateMapAnimation()
    CEGUI::Window* mCurrentGlow;
    CEGUI::Window* mCurrentPointer;
    //! Centre of the current level and the size of its glow in map pixels
    float mCurrentX;
    float mCurrentY;
    float mCurrentGlowSize;
    //! Embers of the trail from the guild panel to the current level, in the order of the raid's way
    std::vector<CEGUI::Window*> mRaidEmbers;
    //! Interface seconds since the map was drawn, the clock of its animation
    float mMapTime;
    //! State of every cave of the map with the current progress, set by fillMap()
    std::vector<CampaignCaveState> mCaveStates;
    //! Level of the open briefing, or the number of levels if none
    size_t mBriefingLevel;
    //! Level started once the camera has flown from the table into the green portal
    size_t mPortalLevel;
    //! True while the camera flies into the green portal to start mPortalLevel
    bool mPortalFlight;
    //! Screen dimensions and GUI scale used by the last debriefing fit.
    CEGUI::Vector2f mDebriefingScreen;
    float mDebriefingScale;
    //! True while the campaign end message is shown in place of the map; closing it shows the main menu
    bool mCampaignEnd;

    //! \brief Reads the map description once. Returns false if it cannot be read or is invalid.
    bool loadWorld();
    //! \brief The image of the world art file, loaded on first use: from the folder of the wing package when it lies
    //! there (the private content packages bring their own previews, banners and portraits), else relative to
    //! gui/campaign. Returns NULL if it cannot be read.
    CEGUI::Image* loadWorldImage(const std::string& file, const std::string& packageDirectory = std::string());
    //! \brief Draws the caves in their states, the wing progress, the guild in front of the gate, the title and
    //! the progress panel on the map
    void fillMap();
    //! \brief Shows the guild of the current level on its carved stone slab, with a trail of embers to the current
    //! level and its banner there; nothing when the campaign is finished
    void fillGuildPanel();
    //! \brief Draws the golden glow under the current level and the golden arrow above it
    void fillCurrentMarker();
    //! \brief Draws the trail of embers from the guild panel to the cave the guild attacks and its banner at the cave
    void fillRaidTrail(size_t cave, const std::string& banner, const std::string& packageDirectory);
    //! \brief Tells whether no cave of the wing can be played yet (its story caves are locked and its bonus cave is
    //! not found), so the wing is greyed out
    bool isWingLocked(uint32_t wing) const;
    //! \brief Lets the current level glow and its arrow bob and the embers of the raid trail run towards it
    void updateMapAnimation(float elapsed);
    //! \brief Shows or hides the hover display with its tablet
    void setTooltipVisible(bool visible);
    //! \brief Writes the defeated levels, wings, shards and cleared bonus caves and the bar in the progress panel
    void fillProgressPanel();
    //! \brief Creates a text window on the map without frame and background
    CEGUI::Window* createMapText(const std::string& name, const CampaignWorldRect& area, const std::string& font,
        const std::string& colour, const std::string& formatting, const std::string& text);
    //! \brief Creates an image window on the map for a campaign art file, looked up first in the folder of the wing
    //! package when one is given; returns NULL if the image cannot be read
    CEGUI::Window* createMapImage(const std::string& name, const std::string& file, float x, float y, float width,
        float height, const std::string& packageDirectory = std::string());
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
    //! \brief Shows or hides the map of Moreya and the controls below it
    void setMapVisible(bool visible);
    //! \brief Tells whether a campaign level can be started (unlocked, its file present and unchanged); otherwise
    //! writes the reason into the status text
    bool canStartLevel(size_t index);
    //! \brief Starts the server and the client for a campaign level; when it fails the map is shown again with the
    //! reason (it may have been hidden for the flight into the portal)
    void startLevel(size_t index);

    //! \brief The mouse moves over the map: the cave below it is highlighted and named in the tooltip
    bool mapMoved(const CEGUI::EventArgs& e);
    //! \brief The mouse leaves the map: the highlight and the tooltip are removed
    bool mapLeft(const CEGUI::EventArgs& e);
    //! \brief A click on the current cave, a defeated cave or a found bonus cave opens its briefing
    bool mapClicked(const CEGUI::EventArgs& e);
    //! \brief Starts the level of the open briefing
    bool briefingStartPressed(const CEGUI::EventArgs&);
    //! \brief Closes the briefing without starting the level; closing the campaign end message shows the main menu
    bool briefingClosePressed(const CEGUI::EventArgs& e);
    //! \brief Chooses the next difficulty while no level is completed
    bool difficultyButtonPressed(const CEGUI::EventArgs&);
    //! \brief Shows the difficulty of the campaign on its button
    void updateDifficultyButton();
    //! \brief Leaves the campaign and shows the main menu
    bool backButtonPressed(const CEGUI::EventArgs&);
};

#endif // MENUMODECAMPAIGN_H
