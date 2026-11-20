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

#ifndef CAMPAIGNWORLD_H
#define CAMPAIGNWORLD_H

#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <string>
#include <vector>

class Campaign;

//! \brief A rectangle in pixels of the campaign map image.
struct CampaignWorldRect
{
    //! \brief Creates an empty rectangle at the origin
    CampaignWorldRect():
        mX(0), mY(0), mWidth(0), mHeight(0)
    {
    }

    int mX;
    int mY;
    int mWidth;
    int mHeight;
};

//! \brief The guild that raids a story level of Moreya: shown in front of the gate while the level is the
//! current one, and in the tooltip of its cave.
struct CampaignWorldGuild
{
    //! \brief Creates a guild without name that sends one group of no member
    CampaignWorldGuild():
        mGroups(0), mSize(0), mRaid(false)
    {
    }

    //! Name of the guild, shown with its banner
    std::string mName;
    //! The named leader of the raid (with the last group or raid of a level with two)
    std::string mLeader;
    //! Leader of the first raid when the two raids of a level have different leaders; empty otherwise
    std::string mFirstLeader;
    //! Origin of the guild, shown with its banner
    std::string mOrigin;
    //! Number of groups or raids (1 or 2)
    uint32_t mGroups;
    //! Number of members of each group or raid
    uint32_t mSize;
    //! True for raids, false for groups
    bool mRaid;
    //! Banner image, relative to the campaign art directory
    std::string mBanner;
    //! Leader portrait image, relative to the campaign art directory
    std::string mPortrait;
};

//! \brief One cave of the campaign map: a story level (with the guild that raids it) or the bonus cave of a wing.
struct CampaignWorldCave
{
    //! \brief Creates a story cave of no wing at the origin
    CampaignWorldCave():
        mWing(0), mBonus(false), mX(0), mY(0), mSize(0)
    {
    }

    //! Level file as in the campaign definition, relative to the "levels" directory
    std::string mFile;
    //! Wing (1 to 6) the cave belongs to
    uint32_t mWing;
    //! True for the bonus cave of the wing
    bool mBonus;
    //! Centre of the cave marker in map pixels
    int mX;
    int mY;
    //! Width and height of the cave marker in map pixels
    int mSize;
    //! Where the name of the level is written in map pixels; empty for a bonus cave, whose name is in its tooltip
    CampaignWorldRect mLabel;
    //! The guild that raids the level; empty for a bonus cave
    CampaignWorldGuild mGuild;
};

//! \brief One wing of Moreya on the campaign map: its name, its place and where its progress is shown.
struct CampaignWorldWing
{
    //! \brief Creates a wing without number and name
    CampaignWorldWing():
        mNumber(0), mSealX(0), mSealY(0), mSealSize(0)
    {
    }

    //! Number of the wing, 1 to 6
    uint32_t mNumber;
    //! Name of the wing
    std::string mName;
    //! Area of the wing on the map in map pixels
    CampaignWorldRect mArea;
    //! Where the wing name and its progress are written
    CampaignWorldRect mLabel;
    //! Centre of the seal shown once all story levels of the wing are defeated
    int mSealX;
    int mSealY;
    //! Width and height of the seal in map pixels
    int mSealSize;
};

//! \brief Where the guild of the current level stands in front of the gate, in map pixels.
struct CampaignWorldGuildPanel
{
    //! The whole panel
    CampaignWorldRect mArea;
    //! The banner of the guild
    CampaignWorldRect mBanner;
    //! The portrait of the leader
    CampaignWorldRect mPortrait;
    //! The name of the guild
    CampaignWorldRect mName;
    //! Leader, raid size and origin
    CampaignWorldRect mDetails;
};

//! \brief Images of the cave markers in their states, relative to the campaign art directory.
struct CampaignWorldIcons
{
    std::string mLocked;
    std::string mCurrent;
    std::string mDefeated;
    std::string mBonusFound;
    std::string mBonusCleared;
    std::string mWingDefeated;
    std::string mHover;
};

//! \brief State of a cave on the campaign map.
enum class CampaignCaveState
{
    //! A bonus cave whose hidden stone was not found yet: not on the map
    hidden,
    //! A story level that is not reached yet
    locked,
    //! The story level the keeper defends now
    current,
    //! A story level that was won; it can be played again
    defeated,
    //! A bonus cave that was found and not cleared yet
    bonusFound,
    //! A bonus cave that was cleared; it can be played again
    bonusCleared
};

//! \brief The campaign map of Moreya (gui/campaign/campaign-world.json): 6 wings with 3 story level caves and one
//! bonus cave each, the gate with the guild of the current level in front of it, the title and the progress panel.
//! There are no surface regions on the map any more.
class CampaignWorld
{
public:
    //! Number of wings the map must have
    static const uint32_t NUM_WINGS = 6;
    //! Number of story level caves of every wing
    static const uint32_t STORY_CAVES_PER_WING = 3;

    //! \brief Creates an empty map: no wing and no cave
    CampaignWorld();

    //! \brief Reads the JSON description. Returns false if it is invalid or does not have exactly 6 wings in
    //! order, each with 3 story caves with a guild and one bonus cave.
    bool importDefinition(std::istream& is);

    //! \brief Width of the map image in pixels
    int getWidth() const
    { return mWidth; }
    //! \brief Height of the map image in pixels
    int getHeight() const
    { return mHeight; }
    //! \brief The map image, relative to the campaign art directory
    const std::string& getBaseImage() const
    { return mBaseImage; }
    //! \brief The wings in the order 1 to 6
    const std::vector<CampaignWorldWing>& getWings() const
    { return mWings; }
    //! \brief The caves: per wing its 3 story caves, then its bonus cave
    const std::vector<CampaignWorldCave>& getCaves() const
    { return mCaves; }
    //! \brief Images of the cave markers
    const CampaignWorldIcons& getIcons() const
    { return mIcons; }
    //! \brief Where the guild of the current level is shown in front of the gate
    const CampaignWorldGuildPanel& getGuildPanel() const
    { return mGuildPanel; }
    //! \brief Where the progress panel is drawn in map pixels
    const CampaignWorldRect& getProgressPanel() const
    { return mProgressPanel; }
    //! \brief Where the title cartouche is drawn in map pixels
    const CampaignWorldRect& getTitleCartouche() const
    { return mTitleCartouche; }

    //! \brief Index of the cave of that level file, or the number of caves if none.
    size_t findCave(const std::string& file) const;
    //! \brief Index of the cave whose marker is at the map pixel, or the number of caves if there is none.
    //! Hidden bonus caves are not on the map, so the caller passes the states of the caves (one per cave).
    size_t getCaveAt(float x, float y, const std::vector<CampaignCaveState>& states) const;

    //! \brief State of the cave with the campaign's progress. level is set to the campaign level of the cave, or
    //! to the number of levels if the campaign has no level with its file (such a cave is locked or hidden).
    CampaignCaveState getCaveState(const Campaign& campaign, size_t cave, size_t& level) const;
    //! \brief Number of story caves of the wing whose level was won
    uint32_t getDefeatedInWing(const Campaign& campaign, uint32_t wing) const;
    //! \brief Index of the cave of the current story level, or the number of caves when the campaign is finished
    //! or its current level has no cave.
    size_t findCurrentCave(const Campaign& campaign) const;

    //! \brief The raid size as shown to the player, e.g. "one group of 5" or "two raids of 40"
    static std::string getRaidSizeText(const CampaignWorldGuild& guild);
    //! \brief The lines shown under the guild name: leader (or both leaders), raid size and origin
    static std::string getGuildDetailsText(const CampaignWorldGuild& guild);

private:
    int mWidth;
    int mHeight;
    std::string mBaseImage;
    std::vector<CampaignWorldWing> mWings;
    std::vector<CampaignWorldCave> mCaves;
    CampaignWorldIcons mIcons;
    CampaignWorldGuildPanel mGuildPanel;
    CampaignWorldRect mProgressPanel;
    CampaignWorldRect mTitleCartouche;

    //! \brief Forgets everything read before
    void clear();
};

#endif // CAMPAIGNWORLD_H
