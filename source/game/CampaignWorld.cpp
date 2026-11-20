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

#include "game/CampaignWorld.h"

#include "game/Campaign.h"

#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <istream>
#include <sstream>

namespace
{
typedef boost::property_tree::ptree Tree;

//! Most groups or raids a level sends
const uint32_t MAX_GROUPS = 2;

//! Reads a JSON array of integers; returns false if it has fewer than count entries
bool readInts(const Tree& node, size_t count, std::vector<int>& values)
{
    values.clear();
    for(Tree::const_iterator it = node.begin(); it != node.end(); ++it)
        values.push_back(it->second.get_value<int>());
    return values.size() >= count;
}

//! Reads the rectangle (x, y, width, height) with that key; returns false if it is missing, too short or empty
bool readRect(const Tree& parent, const char* key, CampaignWorldRect& rect)
{
    boost::optional<const Tree&> node = parent.get_child_optional(key);
    std::vector<int> values;
    if(!node || !readInts(*node, 4, values))
        return false;

    rect.mX = values[0];
    rect.mY = values[1];
    rect.mWidth = values[2];
    rect.mHeight = values[3];
    return (rect.mWidth > 0) && (rect.mHeight > 0);
}

//! Reads the point (x, y) with that key; returns false if it is missing or too short
bool readPoint(const Tree& parent, const char* key, int& x, int& y)
{
    boost::optional<const Tree&> node = parent.get_child_optional(key);
    std::vector<int> values;
    if(!node || !readInts(*node, 2, values))
        return false;

    x = values[0];
    y = values[1];
    return true;
}

//! \brief Reads the level file and the place of a cave marker, and of its label when withLabel is set; returns false
//! if one is missing or the size is not positive
bool readCavePlace(const Tree& node, bool withLabel, CampaignWorldCave& cave)
{
    cave.mFile = node.get<std::string>("file");
    cave.mSize = node.get<int>("size");
    return !cave.mFile.empty() && (cave.mSize > 0) && readPoint(node, "pos", cave.mX, cave.mY)
        && (!withLabel || readRect(node, "label", cave.mLabel));
}

//! \brief Reads the guild of a story cave; returns false if a name, the leader, the origin, an image or a valid
//! raid size is missing
bool readGuild(const Tree& node, CampaignWorldGuild& guild)
{
    guild.mName = node.get<std::string>("name");
    guild.mLeader = node.get<std::string>("leader");
    guild.mFirstLeader = node.get<std::string>("first_leader", std::string());
    guild.mOrigin = node.get<std::string>("origin");
    guild.mGroups = node.get<uint32_t>("groups");
    guild.mSize = node.get<uint32_t>("size");
    std::string kind = node.get<std::string>("kind");
    guild.mRaid = (kind == "raid");
    guild.mBanner = node.get<std::string>("banner");
    guild.mPortrait = node.get<std::string>("portrait");
    return !guild.mName.empty() && !guild.mLeader.empty() && !guild.mOrigin.empty()
        && !guild.mBanner.empty() && !guild.mPortrait.empty()
        && (guild.mGroups >= 1) && (guild.mGroups <= MAX_GROUPS) && (guild.mSize > 0)
        && ((kind == "raid") || (kind == "group"));
}

//! \brief The number as a word for the counts of groups a level can send, else as digits
std::string countText(uint32_t count)
{
    if(count == 1)
        return "one";
    if(count == 2)
        return "two";

    std::ostringstream os;
    os << count;
    return os.str();
}
} // namespace

const uint32_t CampaignWorld::NUM_WINGS;
const uint32_t CampaignWorld::STORY_CAVES_PER_WING;

//! \brief Creates an empty map: no wing and no cave
CampaignWorld::CampaignWorld():
    mWidth(0),
    mHeight(0)
{
}

//! \brief Forgets the wings, caves, images and panels read before
void CampaignWorld::clear()
{
    mWidth = 0;
    mHeight = 0;
    mBaseImage.clear();
    mWings.clear();
    mCaves.clear();
    mIcons = CampaignWorldIcons();
    mGuildPanel = CampaignWorldGuildPanel();
    mProgressPanel = CampaignWorldRect();
    mTitleCartouche = CampaignWorldRect();
}

//! \brief Reads the map of Moreya: size and image, cave icons, title, progress and guild panel, then the 6 wings with
//! their 3 story caves (each with its guild) and their bonus cave. Anything missing makes the whole map invalid.
bool CampaignWorld::importDefinition(std::istream& is)
{
    clear();

    try
    {
        Tree root;
        boost::property_tree::read_json(is, root);
        const Tree& constRoot = root;

        std::vector<int> values;
        if(!readInts(constRoot.get_child("size"), 2, values))
            return false;
        mWidth = values[0];
        mHeight = values[1];
        mBaseImage = constRoot.get<std::string>("base");

        mIcons.mLocked = constRoot.get<std::string>("icons.locked");
        mIcons.mCurrent = constRoot.get<std::string>("icons.current");
        mIcons.mDefeated = constRoot.get<std::string>("icons.defeated");
        mIcons.mBonusFound = constRoot.get<std::string>("icons.bonus_found");
        mIcons.mBonusCleared = constRoot.get<std::string>("icons.bonus_cleared");
        mIcons.mWingDefeated = constRoot.get<std::string>("icons.wing_defeated");
        mIcons.mHover = constRoot.get<std::string>("icons.hover");

        const Tree& panel = constRoot.get_child("guild_panel");
        if(!readRect(constRoot, "progress_panel", mProgressPanel)
            || !readRect(constRoot, "title_cartouche", mTitleCartouche)
            || !readRect(panel, "area", mGuildPanel.mArea)
            || !readRect(panel, "banner", mGuildPanel.mBanner)
            || !readRect(panel, "portrait", mGuildPanel.mPortrait)
            || !readRect(panel, "name", mGuildPanel.mName)
            || !readRect(panel, "details", mGuildPanel.mDetails))
        {
            clear();
            return false;
        }

        const Tree& wings = constRoot.get_child("wings");
        for(Tree::const_iterator it = wings.begin(); it != wings.end(); ++it)
        {
            const Tree& node = it->second;
            CampaignWorldWing wing;
            wing.mNumber = node.get<uint32_t>("wing");
            wing.mName = node.get<std::string>("name");
            wing.mSealSize = node.get<int>("seal_size");
            // The wings come in their order 1 to 6
            if((wing.mNumber != mWings.size() + 1) || wing.mName.empty() || (wing.mSealSize <= 0)
                || !readRect(node, "area", wing.mArea) || !readRect(node, "label", wing.mLabel)
                || !readPoint(node, "seal", wing.mSealX, wing.mSealY))
            {
                clear();
                return false;
            }

            const Tree& levels = node.get_child("levels");
            if(levels.size() != STORY_CAVES_PER_WING)
            {
                clear();
                return false;
            }
            for(Tree::const_iterator level = levels.begin(); level != levels.end(); ++level)
            {
                CampaignWorldCave cave;
                cave.mWing = wing.mNumber;
                if(!readCavePlace(level->second, true, cave) ||!readGuild(level->second.get_child("guild"), cave.mGuild))
                {
                    clear();
                    return false;
                }
                mCaves.push_back(cave);
            }

            CampaignWorldCave bonus;
            bonus.mWing = wing.mNumber;
            bonus.mBonus = true;
            // The name of a bonus cave is only shown in its tooltip
            if(!readCavePlace(node.get_child("bonus"), false, bonus))
            {
                clear();
                return false;
            }
            mCaves.push_back(bonus);
            mWings.push_back(wing);
        }
    }
    catch(const boost::property_tree::ptree_error&)
    {
        clear();
        return false;
    }

    if((mWidth <= 0) || (mHeight <= 0) || mBaseImage.empty() || (mWings.size() != NUM_WINGS))
    {
        clear();
        return false;
    }
    return true;
}

//! \brief Finds the cave of a level by the level file of the campaign definition
size_t CampaignWorld::findCave(const std::string& file) const
{
    for(size_t i = 0; i < mCaves.size(); ++i)
    {
        if(mCaves[i].mFile == file)
            return i;
    }
    return mCaves.size();
}

//! \brief Finds the visible cave whose round marker contains the map pixel
size_t CampaignWorld::getCaveAt(float x, float y, const std::vector<CampaignCaveState>& states) const
{
    for(size_t i = 0; (i < mCaves.size()) && (i < states.size()); ++i)
    {
        if(states[i] == CampaignCaveState::hidden)
            continue;

        const CampaignWorldCave& cave = mCaves[i];
        float radius = static_cast<float>(cave.mSize) / 2.0f;
        float dx = x - static_cast<float>(cave.mX);
        float dy = y - static_cast<float>(cave.mY);
        if(dx * dx + dy * dy <= radius * radius)
            return i;
    }
    return mCaves.size();
}

//! \brief A story cave is defeated when its level was won, current when it is the first story level not won, else
//! locked; a bonus cave is hidden until its stone was found, then found or cleared.
CampaignCaveState CampaignWorld::getCaveState(const Campaign& campaign, size_t cave, size_t& level) const
{
    level = campaign.getNumLevels();
    if(cave >= mCaves.size())
        return CampaignCaveState::hidden;

    const CampaignWorldCave& worldCave = mCaves[cave];
    level = campaign.findLevelByFile(worldCave.mFile);
    if(level >= campaign.getNumLevels())
        return worldCave.mBonus ? CampaignCaveState::hidden : CampaignCaveState::locked;

    if(worldCave.mBonus)
    {
        if(!campaign.isUnlocked(level))
            return CampaignCaveState::hidden;

        return campaign.isCompleted(level) ? CampaignCaveState::bonusCleared : CampaignCaveState::bonusFound;
    }

    if(campaign.isCompleted(level))
        return CampaignCaveState::defeated;

    if(level == campaign.getCurrentLevel())
        return CampaignCaveState::current;

    return CampaignCaveState::locked;
}

//! \brief Counts the story caves of the wing that are defeated
uint32_t CampaignWorld::getDefeatedInWing(const Campaign& campaign, uint32_t wing) const
{
    uint32_t defeated = 0;
    for(size_t i = 0; i < mCaves.size(); ++i)
    {
        if((mCaves[i].mWing != wing) || mCaves[i].mBonus)
            continue;

        size_t level = 0;
        if(getCaveState(campaign, i, level) == CampaignCaveState::defeated)
            ++defeated;
    }
    return defeated;
}

//! \brief Finds the cave of the first story level that is not won yet
size_t CampaignWorld::findCurrentCave(const Campaign& campaign) const
{
    size_t current = campaign.getCurrentLevel();
    if(current >= campaign.getNumLevels())
        return mCaves.size();

    size_t cave = findCave(campaign.getLevel(current).mFile);
    if((cave < mCaves.size()) && mCaves[cave].mBonus)
        return mCaves.size();

    return cave;
}

//! \brief Writes the number and kind of the groups or raids and their size, e.g. "two groups of 10"
std::string CampaignWorld::getRaidSizeText(const CampaignWorldGuild& guild)
{
    std::ostringstream os;
    os << countText(guild.mGroups) << " " << (guild.mRaid ? "raid" : "group") << ((guild.mGroups == 1) ? "" : "s")
        << " of " << guild.mSize;
    return os.str();
}

//! \brief Writes one line for the leader (both leaders when the two raids have different ones), the raid size and
//! the origin
std::string CampaignWorld::getGuildDetailsText(const CampaignWorldGuild& guild)
{
    std::string text;
    if(guild.mFirstLeader.empty())
        text = "Leader: " + guild.mLeader;
    else
        text = "Leaders: " + guild.mFirstLeader + " and " + guild.mLeader;

    text += "\nRaid size: " + getRaidSizeText(guild);
    text += "\nOrigin: " + guild.mOrigin;
    return text;
}
