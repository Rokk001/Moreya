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

#include "game/Campaign.h"

#include "ai/KeeperAIType.h"
#include "utils/Translation.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <istream>
#include <ostream>
#include <sstream>

namespace
{
//! Version of the progress file written by exportProgress
const uint32_t PROGRESS_VERSION = 2;

//! Removes the white space at both ends of a text
std::string trim(const std::string& text)
{
    const std::string whitespace = " \t\r\n";
    size_t first = text.find_first_not_of(whitespace);
    if(first == std::string::npos)
        return std::string();

    size_t last = text.find_last_not_of(whitespace);
    return text.substr(first, last - first + 1);
}

//! \brief True for an item quality a bonus level may unlock, spelled as in config/items.cfg
bool isUnlockQuality(const std::string& quality)
{
    return (quality == "Common") || (quality == "Rare") || (quality == "Epic");
}

//! \brief Reads a non negative whole number; false for any other text
bool parseWholeNumber(const std::string& text, uint32_t& value)
{
    if(text.empty() || (text.find_first_not_of("0123456789") != std::string::npos) || (text.size() > 9))
        return false;

    value = static_cast<uint32_t>(std::atoi(text.c_str()));
    return true;
}
} // namespace

//! \brief Initializes metadata without claiming campaign membership.
CampaignSave::CampaignSave():
    mPresent(false), mValid(false), mDifficulty(0), mChampionAvailable(false)
{
}

//! \brief Parses one versioned save record without interpreting missing records as malformed.
//! Version 1 (older saves) also names the creature of the former kept minion; it is read and ignored.
bool CampaignSave::importInfoLine(const std::string& line)
{
    const std::string prefix = "Campaign\t";
    if(line.compare(0, prefix.size(), prefix) != 0)
        return false;
    *this = CampaignSave();
    mPresent = true;
    std::istringstream input(line.substr(prefix.size()));
    uint32_t version = 0;
    uint32_t champion = 0;
    std::string trailing;
    bool fields = static_cast<bool>(input >> version >> mLevelFile >> mDifficulty >> champion);
    if(fields && (version == 1))
    {
        std::string keptClass;
        uint32_t keptLevel = 0;
        fields = static_cast<bool>(input >> keptClass >> keptLevel);
    }
    mValid = fields && ((version == 1) || (version == 2))
        && (mDifficulty < static_cast<uint32_t>(KeeperAIType::nbAI))
        && (champion <= 1) && !(input >> trailing);
    mChampionAvailable = (champion == 1);
    return true;
}

//! \brief Emits the complete, versioned campaign state as an optional Info line.
void CampaignSave::exportInfo(std::ostream& os) const
{
    if(!mPresent || !mValid)
        return;
    os << "Campaign\t2 " << mLevelFile << " " << mDifficulty << " " << (mChampionAvailable ? 1 : 0) << "\n";
}

//! \brief Creates campaign progress and inactive level context.
Campaign::Campaign():
    mActive(false),
    mPlayedLevel(0),
    mPlayedLevelWon(false),
    mDifficulty(getDefaultDifficulty()),
    mLevelDifficulty(getDefaultDifficulty()),
    mLoadedCampaignSave(false),
    mSavedChampionAvailable(false),
    mFromPackages(false)
{
}

//! \brief The end message of the campaign (language key campaign.code.end), in the chosen language.
std::string Campaign::getEndMessage()
{
    return Translation::tr("campaign.code.end");
}

Campaign& Campaign::getSingleton()
{
    static Campaign campaign;
    return campaign;
}

std::string Campaign::unescapeText(const std::string& text)
{
    std::string result;
    for(size_t i = 0; i < text.size(); ++i)
    {
        if((text[i] == '\\') && (i + 1 < text.size()) && (text[i + 1] == 'n'))
        {
            result += '\n';
            ++i;
            continue;
        }
        result += text[i];
    }
    return result;
}

//! \brief Reads the campaign levels, including their optional briefing images, wings, shards, Summon champion
//! and item unlocks. The level list is read; when no campaign level is running, no level counts as played
//! afterwards. Province, Branch and Heartstone keys of the former campaign are ignored. No wing counts as missing.
bool Campaign::importDefinition(std::istream& is)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mLevels.clear();
    mMissingWings.clear();
    mFromPackages = false;
    parseLevels(is, mLevels);
    resetLevelStateNoLock();
    return !mLevels.empty();
}

//! \brief Reads the wing packages in the order of their wings. The level files of a package lie in its folder; a
//! package whose levels do not all name the same wing of 1 to NUM_WINGS, or whose wing was read before, is skipped.
bool Campaign::importPackages(const std::vector<CampaignPackage>& packages)
{
    std::map<uint32_t, std::vector<CampaignLevel> > wings;
    for(const CampaignPackage& package : packages)
    {
        std::vector<CampaignLevel> levels;
        std::istringstream definition(package.mDefinition);
        parseLevels(definition, levels);
        if(levels.empty())
            continue;

        uint32_t wing = levels.front().mWing;
        bool valid = (wing >= 1) && (wing <= NUM_WINGS) && (wings.count(wing) == 0);
        const std::string& directory = package.mDirectory;
        bool slash = !directory.empty() && ((directory[directory.size() - 1] == '/')
            || (directory[directory.size() - 1] == '\\'));
        for(CampaignLevel& level : levels)
        {
            valid = valid && (level.mWing == wing);
            size_t separator = level.mFile.find_last_of("/\\");
            std::string name = level.mFile.substr(separator == std::string::npos ? 0 : separator + 1);
            level.mPath = directory + (slash ? "" : "/") + name;
        }
        if(valid)
            wings[wing] = levels;
    }

    std::lock_guard<std::mutex> lock(mMutex);
    mLevels.clear();
    mMissingWings.clear();
    mFromPackages = true;
    for(uint32_t wing = 1; wing <= NUM_WINGS; ++wing)
    {
        std::map<uint32_t, std::vector<CampaignLevel> >::const_iterator found = wings.find(wing);
        if(found == wings.end())
        {
            mMissingWings.insert(wing);
            continue;
        }
        mLevels.insert(mLevels.end(), found->second.begin(), found->second.end());
    }
    resetLevelStateNoLock();
    return !mLevels.empty();
}

//! \brief A wing is available when one of its levels was read.
bool Campaign::isWingAvailable(uint32_t wing) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    for(const CampaignLevel& level : mLevels)
    {
        if(level.mWing == wing)
            return true;
    }
    return false;
}

//! \brief True while a wing package of 1 to NUM_WINGS is missing.
bool Campaign::hasMissingWings() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return !mMissingWings.empty();
}

//! \brief Finds the bonus level of the wing, or the story level of the wing with that order in the definition.
size_t Campaign::findLevelInWing(uint32_t wing, bool bonus, size_t order) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    size_t story = 0;
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(mLevels[i].mWing != wing)
            continue;
        if(bonus && mLevels[i].mBonus)
            return i;
        if(bonus || mLevels[i].mBonus)
            continue;
        if(story == order)
            return i;
        ++story;
    }
    return mLevels.size();
}

//! \brief Sets up the progress of freshly read levels: nothing completed, found or discovered; when no campaign level
//! is running, no level counts as played.
void Campaign::resetLevelStateNoLock()
{
    mCompleted.assign(mLevels.size(), false);
    mDiscovered.assign(mLevels.size(), false);
    mShardFound.assign(mLevels.size(), false);
    // No level was played yet. The initial value 0 would name the first level as played and make the
    // campaign menu show a lost-level message when the list was empty while the campaign was stopped.
    if(!mActive)
    {
        mPlayedLevel = mLevels.size();
        mPlayedLevelWon = false;
    }
}

//! \brief Reads the [Level] entries of a definition with their texts, images, wing, shard, Summon champion, item
//! unlocks, warden and guild. Bonus levels carry no shard and only bonus levels unlock items, whatever the file says.
void Campaign::parseLevels(std::istream& is, std::vector<CampaignLevel>& levels)
{
    CampaignLevel level;
    bool inLevel = false;
    std::string line;
    while(std::getline(is, line))
    {
        line = trim(line);
        if(line.empty() || (line[0] == '#'))
            continue;

        if(line == "[Level]")
        {
            if(inLevel && !level.mFile.empty())
                levels.push_back(level);

            level = CampaignLevel();
            inLevel = true;
            continue;
        }

        size_t pos = line.find('=');
        if(!inLevel || (pos == std::string::npos))
            continue;

        std::string key = trim(line.substr(0, pos));
        std::string value = trim(line.substr(pos + 1));

        if(key == "File")
            level.mFile = value;
        else if(key == "Title")
            level.mTitle = value;
        else if(key == "Briefing")
            level.mBriefing = unescapeText(value);
        else if(key == "Debriefing")
            level.mDebriefing = unescapeText(value);
        else if(key == "Preview")
            level.mPreview = value;
        else if(key == "Bonus")
            level.mBonus = (value == "1");
        else if(key == "Shard")
            level.mShard = (value == "1");
        else if(key == "Champion")
            level.mChampion = (value == "1");
        else if(key == "Unlock")
        {
            level.mUnlockQualities.clear();
            std::istringstream qualities(value);
            std::string quality;
            while(qualities >> quality)
            {
                if(isUnlockQuality(quality))
                    level.mUnlockQualities.push_back(quality);
            }
        }
        else if(key == "Wing")
        {
            uint32_t wing = 0;
            if(parseWholeNumber(value, wing))
                level.mWing = wing;
        }
        else if(key == "Warden")
            level.mWarden = value;
        else if(key == "Guild")
            level.mGuild.mName = value;
        else if(key == "GuildLeader")
            level.mGuild.mLeader = value;
        else if(key == "GuildFirstLeader")
            level.mGuild.mFirstLeader = value;
        else if(key == "GuildOrigin")
            level.mGuild.mOrigin = value;
        else if(key == "GuildGroups")
            parseWholeNumber(value, level.mGuild.mGroups);
        else if(key == "GuildSize")
            parseWholeNumber(value, level.mGuild.mSize);
        else if(key == "GuildKind")
            level.mGuild.mRaid = (value == "raid");
        else if(key == "GuildBanner")
            level.mGuild.mBanner = value;
        else if(key == "GuildPortrait")
            level.mGuild.mPortrait = value;
    }

    if(inLevel && !level.mFile.empty())
        levels.push_back(level);

    // Bonus levels carry no shard and no guild, and only bonus levels unlock items, whatever the file says
    for(CampaignLevel& entry : levels)
    {
        if(entry.mBonus)
        {
            entry.mShard = false;
            entry.mGuild = CampaignGuild();
        }
        else
            entry.mUnlockQualities.clear();
    }
}

//! \brief Reads campaign progress (levels by file, shards, unlocked items), finished difficulties and the
//! difficulty. A file without the Version line was written for the former campaign: only its difficulty is
//! kept; its level lines, finished difficulties and kept creature are dropped, so the player starts fresh. Level
//! entries of levels that are not in the campaign (their wing package is missing) are kept to be written again.
bool Campaign::importProgress(std::istream& is)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mCompleted.assign(mLevels.size(), false);
    mDiscovered.assign(mLevels.size(), false);
    mShardFound.assign(mLevels.size(), false);
    mOtherProgress.clear();
    mUnlockedItems.clear();
    mDifficulty = getDefaultDifficulty();
    mFinishedDifficulties.clear();

    std::vector<std::string> lines;
    std::string line;
    bool versioned = false;
    while(std::getline(is, line))
    {
        line = trim(line);
        std::istringstream ss(line);
        std::string keyword;
        uint32_t version = 0;
        if((ss >> keyword) && (keyword == "Version") && (ss >> version) && (version == PROGRESS_VERSION))
            versioned = true;
        lines.push_back(line);
    }

    for(const std::string& entry : lines)
    {
        std::istringstream ss(entry);
        std::string keyword;
        ss >> keyword;
        if(keyword == "Difficulty")
        {
            uint32_t difficulty;
            if((ss >> difficulty) && (difficulty < static_cast<uint32_t>(KeeperAIType::nbAI)))
                mDifficulty = difficulty;
            continue;
        }
        // The level lines and finished difficulties of a file for the former campaign are old progress:
        // they name other levels and are dropped, only the difficulty above stays
        if(!versioned)
            continue;

        if(keyword == "Finished")
        {
            std::string name;
            while(ss >> name)
            {
                for(uint32_t i = 0; i < static_cast<uint32_t>(KeeperAIType::nbAI); ++i)
                {
                    if(name == KeeperAITypes::nameOf(static_cast<KeeperAIType>(i)))
                        mFinishedDifficulties.insert(name);
                }
            }
            continue;
        }
        if(keyword == "Unlocked")
        {
            CampaignUnlockedItem item;
            std::string trailing;
            if((ss >> item.mBonusFile >> item.mQuality >> item.mItemId) && !(ss >> trailing)
                && isUnlockQuality(item.mQuality) && !isItemUnlockedNoLock(item.mQuality, item.mItemId))
            {
                mUnlockedItems.push_back(item);
            }
            continue;
        }
        if((keyword != "Completed") && (keyword != "Discovered") && (keyword != "Shards"))
            continue;

        std::string file;
        while(ss >> file)
        {
            size_t index = findLevelByFileNoLock(file);
            if(index >= mLevels.size())
            {
                // The level of a missing package keeps its progress until the package is there again
                std::pair<std::string, std::string> other(keyword, file);
                if(std::find(mOtherProgress.begin(), mOtherProgress.end(), other) == mOtherProgress.end())
                    mOtherProgress.push_back(other);
                continue;
            }
            if(keyword == "Completed")
                mCompleted[index] = true;
            else if((keyword == "Discovered") && mLevels[index].mBonus)
                mDiscovered[index] = true;
            else if((keyword == "Shards") && mLevels[index].mShard)
                mShardFound[index] = true;
        }
    }
    return true;
}

//! \brief Writes campaign progress (version 2: levels by file, shards, unlocked items) and completed
//! difficulties. The kept entries of levels whose package is missing follow the levels of the campaign.
void Campaign::exportProgress(std::ostream& os) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    os << "# Campaign progress. Do not edit while the game is running.\n";
    os << "Version " << PROGRESS_VERSION << "\n";
    os << "Completed";
    for(size_t i = 0; i < mCompleted.size(); ++i)
    {
        if(mCompleted[i])
            os << " " << mLevels[i].mFile;
    }
    writeOtherProgressNoLock(os, "Completed");
    os << "\n";
    os << "Discovered";
    for(size_t i = 0; i < mDiscovered.size(); ++i)
    {
        if(mDiscovered[i])
            os << " " << mLevels[i].mFile;
    }
    writeOtherProgressNoLock(os, "Discovered");
    os << "\n";
    os << "Shards";
    for(size_t i = 0; i < mShardFound.size(); ++i)
    {
        if(mShardFound[i])
            os << " " << mLevels[i].mFile;
    }
    writeOtherProgressNoLock(os, "Shards");
    os << "\n";
    for(const CampaignUnlockedItem& item : mUnlockedItems)
        os << "Unlocked " << item.mBonusFile << " " << item.mQuality << " " << item.mItemId << "\n";
    os << "Difficulty " << mDifficulty << "\n";
    os << "Finished";
    for(std::set<std::string>::const_iterator it = mFinishedDifficulties.begin(); it != mFinishedDifficulties.end(); ++it)
        os << " " << *it;
    os << "\n";
}

//! \brief Writes the kept levels of missing packages that carry the keyword, each with a leading space.
void Campaign::writeOtherProgressNoLock(std::ostream& os, const std::string& keyword) const
{
    for(const std::pair<std::string, std::string>& other : mOtherProgress)
    {
        if(other.first == keyword)
            os << " " << other.second;
    }
}

void Campaign::setProgressPath(const std::string& path)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mProgressPath = path;
}

bool Campaign::saveProgress() const
{
    std::string path;
    {
        std::lock_guard<std::mutex> lock(mMutex);
        path = mProgressPath;
    }
    if(path.empty())
        return false;

    std::ofstream file(path.c_str());
    if(!file.is_open())
        return false;

    exportProgress(file);
    return file.good();
}

size_t Campaign::getNumLevels() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mLevels.size();
}

const CampaignLevel& Campaign::getLevel(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mLevels.at(index);
}

size_t Campaign::findLevelByProvince(const std::string& province) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(!province.empty() && (mLevels[i].mProvince == province))
            return i;
    }
    return mLevels.size();
}

//! \brief Finds a level by its file name for callers that do not hold the mutex.
size_t Campaign::findLevelByFile(const std::string& file) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return findLevelByFileNoLock(file);
}

bool Campaign::isCompleted(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return (index < mCompleted.size()) && mCompleted[index];
}

//! \brief Finds a level by its file name, as written in the progress file and level scripts.
size_t Campaign::findLevelByFileNoLock(const std::string& file) const
{
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(mLevels[i].mFile == file)
            return i;
    }
    return mLevels.size();
}

//! \brief Finds the first story level of a wing, the level that hides the stone of the wing's bonus level.
size_t Campaign::findFirstStoryLevelOfWingNoLock(uint32_t wing) const
{
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(!mLevels[i].mBonus && (mLevels[i].mWing == wing))
            return i;
    }
    return mLevels.size();
}

//! \brief The first story level that is not completed; bonus levels never block the sequence. A missing wing blocks
//! it: the story levels of later wings are not reached while a wing before them has no package.
size_t Campaign::getCurrentLevelNoLock() const
{
    for(size_t i = 0; i < mCompleted.size(); ++i)
    {
        if(!mCompleted[i] && !mLevels[i].mBonus)
        {
            if(!mMissingWings.empty() && (*mMissingWings.begin() < mLevels[i].mWing))
                return mCompleted.size();
            return i;
        }
    }
    return mCompleted.size();
}

size_t Campaign::getCurrentLevel() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return getCurrentLevelNoLock();
}

//! \brief A story level is unlocked when every story level before it is completed, a bonus level when it
//! was discovered (or completed before). A story level after a missing wing stays locked.
bool Campaign::isUnlockedNoLock(size_t index) const
{
    if(index >= mLevels.size())
        return false;

    if(mLevels[index].mBonus)
        return mDiscovered[index] || mCompleted[index];

    // The story levels of a missing wing are needed before the levels of later wings
    if(!mMissingWings.empty() && (*mMissingWings.begin() < mLevels[index].mWing))
        return false;

    // All story levels before the level must be completed.
    for(size_t i = 0; i < index; ++i)
    {
        if(mCompleted[i] || mLevels[i].mBonus)
            continue;
        return false;
    }
    return true;
}

bool Campaign::isUnlocked(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return isUnlockedNoLock(index);
}

//! \brief Records a bonus level found by the hidden stone; only the first story level of the bonus
//! level's wing can find it.
bool Campaign::discoverBonusLevel(const std::string& file)
{
    {
        std::lock_guard<std::mutex> lock(mMutex);
        if(!mActive || (mPlayedLevel >= mLevels.size()))
            return false;

        size_t index = findLevelByFileNoLock(file);
        if((index >= mLevels.size()) || !mLevels[index].mBonus || mDiscovered[index])
            return false;

        // The hidden stone of a bonus level lies in the first story level of its wing
        uint32_t wing = mLevels[index].mWing;
        if((wing != 0) && (findFirstStoryLevelOfWingNoLock(wing) != mPlayedLevel))
            return false;

        mDiscovered[index] = true;
    }
    saveProgress();
    return true;
}

bool Campaign::isDiscovered(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return (index < mDiscovered.size()) && mDiscovered[index];
}

//! \brief Records the shard of the played level once; levels without a shard and bonus levels find none.
bool Campaign::findShard()
{
    {
        std::lock_guard<std::mutex> lock(mMutex);
        if(!mActive || (mPlayedLevel >= mLevels.size()))
            return false;

        if(!mLevels[mPlayedLevel].mShard || mShardFound[mPlayedLevel])
            return false;

        mShardFound[mPlayedLevel] = true;
    }
    saveProgress();
    return true;
}

//! \brief True if the shard of that level was found.
bool Campaign::isShardFound(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return (index < mShardFound.size()) && mShardFound[index];
}

//! \brief Counts the found shards while the caller holds the mutex.
//! The shards found in levels whose package is missing count as well (kept progress entries).
size_t Campaign::getHeartstonePiecesNoLock() const
{
    size_t count = 0;
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(mLevels[i].mShard && mShardFound[i])
            ++count;
    }
    for(const std::pair<std::string, std::string>& other : mOtherProgress)
    {
        if(other.first == "Shards")
            ++count;
    }
    return std::min(count, getHeartstoneTotalNoLock());
}

//! \brief Counts the levels with a shard while the caller holds the mutex.
//! A campaign read from packages has at least HEARTSTONE_SHARDS shards, so the total does not shrink while a wing is
//! missing.
size_t Campaign::getHeartstoneTotalNoLock() const
{
    size_t count = 0;
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        if(mLevels[i].mShard)
            ++count;
    }
    return mFromPackages ? std::max(count, static_cast<size_t>(HEARTSTONE_SHARDS)) : count;
}

//! \brief Number of found Heartstone shards.
size_t Campaign::getHeartstonePieces() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return getHeartstonePiecesNoLock();
}

//! \brief Number of Heartstone shards of the campaign.
size_t Campaign::getHeartstoneTotal() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return getHeartstoneTotalNoLock();
}

//! \brief True if the campaign has shards and every one was found.
bool Campaign::isHeartstoneComplete() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    size_t total = getHeartstoneTotalNoLock();
    return (total > 0) && (getHeartstonePiecesNoLock() == total);
}

//! \brief Summon champion needs every shard and a level with Champion=1.
bool Campaign::isChampionAvailableNoLock(size_t index) const
{
    if(index >= mLevels.size())
        return false;

    size_t total = getHeartstoneTotalNoLock();
    if((total == 0) || (getHeartstonePiecesNoLock() != total))
        return false;

    return mLevels[index].mChampion;
}

bool Campaign::isChampionAvailable(size_t index) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return isChampionAvailableNoLock(index);
}

//! \brief True while a campaign bonus level is played.
bool Campaign::isPlayedLevelBonus() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mActive && (mPlayedLevel < mLevels.size()) && mLevels[mPlayedLevel].mBonus;
}

//! \brief The items unlocked by bonus levels so far.
std::vector<CampaignUnlockedItem> Campaign::getUnlockedItems() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mUnlockedItems;
}

//! \brief True if the item line is unlocked at that quality.
bool Campaign::isItemUnlockedNoLock(const std::string& quality, const std::string& itemId) const
{
    for(const CampaignUnlockedItem& item : mUnlockedItems)
    {
        if((item.mQuality == quality) && (item.mItemId == itemId))
            return true;
    }
    return false;
}

bool Campaign::isFinished() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return isCampaignCompleteNoLock();
}

//! \brief The campaign is complete when every story level was won and no wing package is missing.
bool Campaign::isCampaignCompleteNoLock() const
{
    return !mLevels.empty() && mMissingWings.empty() && (getCurrentLevelNoLock() == mLevels.size());
}

bool Campaign::hasProgress() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    for(size_t i = 0; i < mCompleted.size(); ++i)
    {
        if(mCompleted[i])
            return true;
    }
    return false;
}

//! \brief Returns whether Hard has been completed.
bool Campaign::isHellUnlocked() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mFinishedDifficulties.count("hard") != 0;
}

//! \brief Forgets levels, shards and unlocked items of the campaign; the finished difficulties stay.
void Campaign::resetProgress()
{
    {
        std::lock_guard<std::mutex> lock(mMutex);
        mCompleted.assign(mLevels.size(), false);
        mDiscovered.assign(mLevels.size(), false);
        mShardFound.assign(mLevels.size(), false);
        mUnlockedItems.clear();
        mOtherProgress.clear();
        mPlayedLevel = mLevels.size();
        mPlayedLevelWon = false;
        mDifficulty = getDefaultDifficulty();
    }
    saveProgress();
}

uint32_t Campaign::getDifficulty() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mDifficulty;
}

//! \brief Returns the saved level difficulty without changing the menu's selection.
uint32_t Campaign::getLevelDifficulty() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mActive ? mLevelDifficulty : mDifficulty;
}

//! \brief Uses the saved champion state for recorded saves and live progress of the played level otherwise.
bool Campaign::isLevelChampionAvailableNoLock() const
{
    if(!mActive)
        return false;
    if(mLoadedCampaignSave)
        return mSavedChampionAvailable;
    return isChampionAvailableNoLock(mPlayedLevel);
}

//! \brief Uses the saved champion state for recorded saves and live progress for other starts.
bool Campaign::isLevelChampionAvailable() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return isLevelChampionAvailableNoLock();
}

//! \brief Captures only running campaign games.
CampaignSave Campaign::getSaveState() const
{
    CampaignSave saved;
    std::lock_guard<std::mutex> lock(mMutex);
    if(!mActive || (mPlayedLevel >= mLevels.size()))
        return saved;
    saved.mPresent = true;
    saved.mValid = true;
    saved.mLevelFile = mLevels[mPlayedLevel].mFile;
    saved.mDifficulty = mLevelDifficulty;
    saved.mChampionAvailable = isLevelChampionAvailableNoLock();
    return saved;
}

//! \brief Finds a recorded file exactly, or the original basename retained in legacy SK save names.
size_t Campaign::findSavedLevelNoLock(const CampaignSave& saved, const std::string& saveFilename) const
{
    size_t slash = saveFilename.find_last_of("/\\");
    std::string filename = saveFilename.substr(slash == std::string::npos ? 0 : slash + 1);
    size_t skirmish = filename.find("SK-");
    size_t multiplayer = filename.find("MP-");
    if((multiplayer != std::string::npos) && ((skirmish == std::string::npos) || (multiplayer < skirmish)))
        return mLevels.size();
    if(saved.mPresent && !saved.mValid)
        return mLevels.size();
    if(!saved.mPresent && (skirmish != std::string::npos))
        filename = filename.substr(skirmish + 3);
    for(size_t i = 0; i < mLevels.size(); ++i)
    {
        const std::string& file = mLevels[i].mFile;
        size_t separator = file.find_last_of("/\\");
        std::string basename = file.substr(separator == std::string::npos ? 0 : separator + 1);
        bool matches = saved.mPresent ? (saved.mLevelFile == file) : (filename == basename);
        if(matches && isUnlockedNoLock(i))
            return i;
    }
    return mLevels.size();
}

//! \brief Shares the exact load eligibility decision with save-list classification.
size_t Campaign::findSavedLevel(const CampaignSave& saved, const std::string& saveFilename) const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return findSavedLevelNoLock(saved, saveFilename);
}

//! \brief Restores the running level without importing or overwriting campaign progress.
bool Campaign::restoreSavedLevel(const CampaignSave& saved, const std::string& saveFilename)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mPlayedLevel = findSavedLevelNoLock(saved, saveFilename);
    mActive = (mPlayedLevel < mLevels.size());
    mPlayedLevelWon = false;
    mLevelSummary.clear();
    mLoadedCampaignSave = mActive && saved.mPresent;
    mLevelDifficulty = mLoadedCampaignSave ? saved.mDifficulty : mDifficulty;
    mSavedChampionAvailable = mLoadedCampaignSave && saved.mChampionAvailable;
    return mActive;
}

void Campaign::setDifficulty(uint32_t difficulty)
{
    if(difficulty >= static_cast<uint32_t>(KeeperAIType::nbAI))
        return;

    {
        std::lock_guard<std::mutex> lock(mMutex);
        mDifficulty = difficulty;
    }
    saveProgress();
}

uint32_t Campaign::getDefaultDifficulty()
{
    return static_cast<uint32_t>(KeeperAIType::normal);
}

//! \brief Starts a menu level using current progress and clears any loaded snapshot.
void Campaign::startLevel(size_t index)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mActive = true;
    mLevelDifficulty = mDifficulty;
    mLoadedCampaignSave = false;
    mSavedChampionAvailable = false;
    mPlayedLevel = index;
    mPlayedLevelWon = false;
    mLevelSummary.clear();
}

void Campaign::stopCampaign()
{
    std::lock_guard<std::mutex> lock(mMutex);
    mActive = false;
    mPlayedLevel = mLevels.size();
    mPlayedLevelWon = false;
    mLevelSummary.clear();
}

bool Campaign::isActive() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mActive;
}

size_t Campaign::getPlayedLevel() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mPlayedLevel;
}

bool Campaign::getPlayedLevelWon() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mPlayedLevelWon;
}

void Campaign::clearPlayedLevel()
{
    std::lock_guard<std::mutex> lock(mMutex);
    mPlayedLevel = mLevels.size();
    mPlayedLevelWon = false;
    mLevelSummary.clear();
}

//! \brief A won level ends the campaign when no story level is left undefeated afterwards and no wing is missing.
bool Campaign::isPlayedLevelCampaignEnd() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return (mPlayedLevel < mLevels.size()) && mPlayedLevelWon && isCampaignCompleteNoLock();
}

void Campaign::setLevelSummary(const std::string& summary)
{
    std::lock_guard<std::mutex> lock(mMutex);
    // Only a campaign level that is played keeps the numbers
    if(mActive)
        mLevelSummary = summary;
}

std::string Campaign::getLevelSummary() const
{
    std::lock_guard<std::mutex> lock(mMutex);
    return mLevelSummary;
}

//! \brief Records the won level, any completed campaign difficulty and, for the first completion of a
//! bonus level, one unlocked item per Unlock quality of the level.
bool Campaign::completePlayedLevel(const std::map<std::string, std::vector<std::string> >* candidates,
    CampaignDraw draw)
{
    {
        std::lock_guard<std::mutex> lock(mMutex);
        if(!mActive || (mPlayedLevel >= mLevels.size()))
            return false;

        const CampaignLevel& played = mLevels[mPlayedLevel];
        // Only the first completion of a bonus level unlocks items; a replay unlocks nothing more
        bool firstBonusCompletion = played.mBonus && !mCompleted[mPlayedLevel];
        mCompleted[mPlayedLevel] = true;
        if(firstBonusCompletion && (candidates != nullptr) && (draw != nullptr))
        {
            for(const std::string& quality : played.mUnlockQualities)
            {
                std::map<std::string, std::vector<std::string> >::const_iterator found = candidates->find(quality);
                if(found == candidates->end())
                    continue;

                std::vector<std::string> available;
                for(const std::string& itemId : found->second)
                {
                    if(!itemId.empty() && !isItemUnlockedNoLock(quality, itemId)
                        && (std::find(available.begin(), available.end(), itemId) == available.end()))
                    {
                        available.push_back(itemId);
                    }
                }
                if(available.empty())
                    continue;

                uint32_t pick = draw(static_cast<uint32_t>(available.size()));
                if(pick >= available.size())
                    pick = static_cast<uint32_t>(available.size() - 1);

                CampaignUnlockedItem item;
                item.mBonusFile = played.mFile;
                item.mQuality = quality;
                item.mItemId = available[pick];
                mUnlockedItems.push_back(item);
            }
        }
        if(isCampaignCompleteNoLock())
            mFinishedDifficulties.insert(KeeperAITypes::nameOf(static_cast<KeeperAIType>(mLevelDifficulty)));
        mPlayedLevelWon = true;
    }
    saveProgress();
    return true;
}

//! \brief Records the won level and any completed campaign difficulty; it unlocks no item.
bool Campaign::onLevelWon()
{
    return completePlayedLevel(nullptr, nullptr);
}

//! \brief Records the won level and any completed campaign difficulty; the first completion of a bonus level
//! unlocks its items from the candidates.
bool Campaign::onLevelWon(const std::map<std::string, std::vector<std::string> >& candidates, CampaignDraw draw)
{
    return completePlayedLevel(&candidates, draw);
}
