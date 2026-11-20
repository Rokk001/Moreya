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

#ifndef CAMPAIGN_H
#define CAMPAIGN_H

#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include <set>

//! \brief One level of the campaign sequence.
//! The level file name is relative to the "levels" directory.
struct CampaignLevel
{
    //! \brief Creates a story level (no bonus level) of no wing that hides no Heartstone shard, offers no Summon
    //! champion and unlocks no item
    CampaignLevel():
        mBonus(false),
        mShard(false),
        mChampion(false),
        mWing(0),
        mDifficulty(1)
    {
    }

    std::string mFile;
    std::string mTitle;
    std::string mBriefing;
    std::string mDebriefing;
    //! \brief Optional briefing image path relative to gui/campaign; empty means text only.
    std::string mPreview;
    //! A bonus (secret) level does not block the story levels. It is found by the hidden stone in the
    //! first story level of its wing, and its first completion unlocks items for the merchant.
    bool mBonus;
    //! True for a story level that hides a shard of the Heartstone. Bonus levels never carry one.
    bool mShard;
    //! True if the level offers Summon champion once every Heartstone shard was found
    bool mChampion;
    //! Qualities (Common, Rare, Epic) of the items the first completion of a bonus level unlocks, one item
    //! each. Story levels unlock nothing.
    std::vector<std::string> mUnlockQualities;
    //! Wing of Moreya (1 to 6) the level belongs to, bonus levels included; 0 when the definition names none.
    uint32_t mWing;
    //! Id of the province (or of the bonus site) of the level on the old world map. The definition no
    //! longer sets it (the campaign is ordered by wings, not provinces), so it stays empty.
    std::string mProvince;
    //! Ruler of the province, shown in its tooltip. Empty if it has none.
    std::string mWarden;
    //! Difficulty of the level from 1 (easy) to 5, shown in the tooltip
    uint32_t mDifficulty;
};

//! \brief One item line that the first completion of a bonus level made available at the merchant for good.
struct CampaignUnlockedItem
{
    //! \brief Level file of the bonus level that unlocked the item
    std::string mBonusFile;
    //! \brief Quality as spelled in config/items.cfg (Common, Rare or Epic)
    std::string mQuality;
    //! \brief Id of the item line in config/items.cfg
    std::string mItemId;
};

//! \brief Draws an index in [0, count - 1] for a count of at least 1. The server passes its random generator.
typedef uint32_t (*CampaignDraw)(uint32_t count);

//! \brief Campaign context stored in a game's Info block, independently of current progress.
struct CampaignSave
{
    //! \brief Creates absent campaign metadata for legacy and ordinary saves.
    CampaignSave();
    //! \brief Reads the versioned Campaign line (version 1 of older saves or version 2); malformed records
    //! never fall back to legacy matching.
    bool importInfoLine(const std::string& line);
    //! \brief Writes a complete version 2 record, or nothing when this is not a campaign game.
    void exportInfo(std::ostream& os) const;

    bool mPresent;
    bool mValid;
    std::string mLevelFile;
    uint32_t mDifficulty;
    //! \brief Whether the saved level gives the keeper the Summon champion spell
    bool mChampionAvailable;
};

//! \brief The campaign: an ordered list of levels plus the saved progress.
//!
//! Definition file (levels/campaign/Campaign.cfg), one setting per line:
//!   # comment
//!   [Level]
//!   File=campaign/Level1.level
//!   Title=Some title
//!   Briefing=Text shown before the level. "\n" starts a new line.
//!   Debriefing=Text shown after the level was won.
//!   Preview=previews/T01.png (optional) briefing image relative to gui/campaign.
//!   Wing=1 the wing of Moreya the level belongs to (bonus levels too).
//!   Bonus=1 (optional) marks a bonus level.
//!   Shard=1 (optional) the story level hides a shard of the Heartstone.
//!   Champion=1 (optional) the level offers Summon champion once every shard was found.
//!   Unlock=Epic Rare Common (optional, bonus levels) the qualities of the items its first
//!   completion unlocks, one item per name.
//!   Warden=Name (optional) shown in the tooltip.
//!   Difficulty=1 to 5 (optional) the difficulty shown on the map.
//! The keys of the former world map campaign (Province, Branch, Heartstone) are ignored.
//!
//! A bonus level is hidden until the level script of the first story level of its wing
//! finds it (action "discover", the level file name as argument). It is not needed to
//! finish the campaign. Its first completion unlocks one item per Unlock quality,
//! drawn from config/items.cfg; a replay unlocks nothing more. Every unlocked item is put
//! up for sale once at the merchant of every level started afterwards.
//!
//! A Heartstone shard counts when the level script of its level finds it (action "shard").
//!
//! Progress file (written by the game):
//!   Version 2
//!   Completed <levelFile> [<levelFile> ...]
//!   Discovered <levelFile> [...]   bonus levels that were found
//!   Shards <levelFile> [...]       levels whose shard was found
//!   Unlocked <bonusLevelFile> <Quality> <itemId>   one line per unlocked item
//!   Difficulty <n>   (index of the AI level for the whole campaign, 0 = easy)
//!   Finished <difficulty name> [...]
//! A progress file without the Version line belongs to the former campaign: only its
//! Difficulty line is read; its level lines, finished difficulties and kept creature are dropped,
//! so every player starts the campaign of Moreya fresh with the difficulty chosen before.
//! A story level is unlocked when all story levels before it are completed; a bonus
//! level is unlocked when it was discovered. The current
//! level is the first story level that is not completed yet. Every level starts fresh:
//! nothing of a level is carried to the next one.
//!
//! The campaign is a process wide singleton because the single player server
//! (which detects the victory) and the menu (which shows the result) live in
//! the same process.
class Campaign
{
public:
    //! \brief The one campaign of the process
    static Campaign& getSingleton();

    //! \brief Reads the campaign settings and the level sequence. Returns false if no level was found.
    bool importDefinition(std::istream& is);
    //! \brief Reads the saved progress. Unknown level files are ignored; a file without a Version line keeps
    //! only its difficulty.
    bool importProgress(std::istream& is);
    //! \brief Writes the progress (version 2: levels, shards, unlocked items, difficulty) in the format
    //! importProgress reads
    void exportProgress(std::ostream& os) const;

    //! \brief Sets the file the progress is written to by saveProgress() and
    //! onLevelWon(). Without a path nothing is written.
    void setProgressPath(const std::string& path);
    //! \brief Writes the progress to the progress file. Returns false if there is no path or it cannot be written.
    bool saveProgress() const;

    //! \brief Number of levels of the campaign, bonus levels included
    size_t getNumLevels() const;
    //! \brief The level with that index in the order of the definition file
    const CampaignLevel& getLevel(size_t index) const;
    //! \brief Index of the level on the province or bonus site with that id,
    //! or getNumLevels() if there is none. The definition sets no province any more.
    size_t findLevelByProvince(const std::string& province) const;
    //! \brief Index of the level with that file (relative to the "levels" directory), or getNumLevels() if there
    //! is none. The campaign map finds the level of each of its caves with it.
    size_t findLevelByFile(const std::string& file) const;
    //! \brief True if the level was won
    bool isCompleted(size_t index) const;
    //! \brief True if the level can be played: its story levels before it are done, or the bonus level was found
    bool isUnlocked(size_t index) const;
    //! \brief First story (non bonus) level not completed. Equals the number of levels if all are done.
    size_t getCurrentLevel() const;
    //! \brief True if every story level was won
    bool isFinished() const;
    //! \brief A level script found the bonus level with that file name. Only
    //! counts while the first story level of the bonus level's wing is played (any campaign level
    //! for a bonus level without a wing). Returns true if it is newly discovered (progress is saved).
    bool discoverBonusLevel(const std::string& file);
    //! \brief True if the bonus level was found by a level script
    bool isDiscovered(size_t index) const;
    //! \brief A level script found the Heartstone shard of the level that is played. Returns true if
    //! the level hides a shard that was not found before (progress is saved).
    bool findShard();
    //! \brief True if the shard of the level was found
    bool isShardFound(size_t index) const;
    //! \brief Number of Heartstone shards found.
    size_t getHeartstonePieces() const;
    //! \brief Number of Heartstone shards (story levels with Shard=1).
    size_t getHeartstoneTotal() const;
    //! \brief True if the campaign has shards and all were found.
    bool isHeartstoneComplete() const;
    //! \brief True if the level offers Summon champion with the current progress: every shard was found
    //! and the level has Champion=1.
    bool isChampionAvailable(size_t index) const;
    //! \brief True while a bonus level is played. Bonus levels have no raid.
    bool isPlayedLevelBonus() const;
    //! \brief Every item unlocked so far, in the order of unlocking.
    std::vector<CampaignUnlockedItem> getUnlockedItems() const;
    //! \brief True if any level was completed (a campaign can be continued).
    bool hasProgress() const;
    //! \brief Starts a new campaign while retaining completed difficulties.
    void resetProgress();

    //! \brief Returns whether completing Hard unlocked Hell.
    bool isHellUnlocked() const;

    //! \brief AI difficulty of the whole campaign, chosen when a new campaign
    //! is begun. The value is an index into KeeperAIType.
    uint32_t getDifficulty() const;
    //! \brief Difficulty of the running level, including the immutable saved difficulty.
    uint32_t getLevelDifficulty() const;
    //! \brief Summon champion availability of the running level, following its save when present.
    bool isLevelChampionAvailable() const;
    //! \brief Captures campaign membership, file identity, difficulty and Summon champion availability.
    CampaignSave getSaveState() const;
    //! \brief Resolves eligible recorded or legacy saves by file name and current unlocks, without mutation.
    size_t findSavedLevel(const CampaignSave& saved, const std::string& saveFilename) const;
    //! \brief Restores eligible saves as campaign levels; other saves clear campaign activity.
    bool restoreSavedLevel(const CampaignSave& saved, const std::string& saveFilename);
    //! \brief Sets the difficulty and saves the progress. Values above the
    //! highest AI level are ignored.
    void setDifficulty(uint32_t difficulty);
    //! \brief Default difficulty (normal).
    static uint32_t getDefaultDifficulty();

    //! \brief A campaign level was started from the campaign menu.
    void startLevel(size_t index);
    //! \brief Leaving the campaign (the main menu is shown).
    void stopCampaign();
    //! \brief True while a campaign level is played
    bool isActive() const;
    //! \brief The level that was started last, or getNumLevels() if none.
    size_t getPlayedLevel() const;
    //! \brief True if the level that was played last was won
    bool getPlayedLevelWon() const;
    //! \brief Clears the "last played" result once the menu has shown it.
    void clearPlayedLevel();
    //! \brief True if the level played last was won and every story level is defeated now: the campaign ends with
    //! the end message and the main menu instead of the campaign map. Holds for every such win, replays included.
    bool isPlayedLevelCampaignEnd() const;

    //! \brief Message shown in place of the campaign map after a win that leaves every story level defeated
    static const std::string CAMPAIGN_END_MESSAGE;

    //! \brief The statistics of the level that was just won, as text lines. Set by the client when the
    //! server sends them at the victory, shown by the campaign menu. Empty if there are none.
    void setLevelSummary(const std::string& summary);
    //! \brief The statistics text of the level that was just won, empty if there is none
    std::string getLevelSummary() const;

    //! \brief Called by the server when a human seat completed all its goals.
    //! Marks the played level as completed and saves the progress; it unlocks no item.
    //! Returns true if a campaign level was won.
    bool onLevelWon();
    //! \brief Called by the server when a human seat completed all its goals. Like onLevelWon(); the first
    //! completion of a bonus level also unlocks one item per Unlock quality of the level, drawn with draw among the
    //! candidate item ids of that quality (candidates maps a quality name to item ids) that are not unlocked
    //! at that quality yet. Returns true if a campaign level was won.
    bool onLevelWon(const std::map<std::string, std::vector<std::string> >& candidates, CampaignDraw draw);

    //! \brief Replaces "\n" (backslash, n) by a line feed.
    static std::string unescapeText(const std::string& text);

private:
    //! \brief The campaign is created by getSingleton only
    Campaign();

    mutable std::mutex mMutex;
    std::vector<CampaignLevel> mLevels;
    std::vector<bool> mCompleted;
    std::vector<bool> mDiscovered;
    //! Levels whose Heartstone shard was found
    std::vector<bool> mShardFound;
    //! Items unlocked by first completions of bonus levels, saved with the progress
    std::vector<CampaignUnlockedItem> mUnlockedItems;
    std::string mProgressPath;
    bool mActive;
    size_t mPlayedLevel;
    bool mPlayedLevelWon;
    std::string mLevelSummary;
    uint32_t mDifficulty;
    uint32_t mLevelDifficulty;
    bool mLoadedCampaignSave;
    bool mSavedChampionAvailable;
    std::set<std::string> mFinishedDifficulties;

    //! \brief getCurrentLevel for callers that hold the mutex already
    size_t getCurrentLevelNoLock() const;
    //! \brief isUnlocked for callers that hold the mutex already
    bool isUnlockedNoLock(size_t index) const;
    //! \brief Resolves a save while the caller holds the campaign mutex.
    size_t findSavedLevelNoLock(const CampaignSave& saved, const std::string& saveFilename) const;
    //! \brief Index of the level with that file, or the number of levels. The mutex is held by the caller.
    size_t findLevelByFileNoLock(const std::string& file) const;
    //! \brief Index of the first story level of the wing, or the number of levels. The mutex is held by the caller.
    size_t findFirstStoryLevelOfWingNoLock(uint32_t wing) const;
    //! \brief Number of found shards. The mutex is held by the caller.
    size_t getHeartstonePiecesNoLock() const;
    //! \brief Number of shard levels. The mutex is held by the caller.
    size_t getHeartstoneTotalNoLock() const;
    //! \brief isChampionAvailable for callers that hold the mutex already
    bool isChampionAvailableNoLock(size_t index) const;
    //! \brief isLevelChampionAvailable for callers that hold the mutex already
    bool isLevelChampionAvailableNoLock() const;
    //! \brief True if the item line is unlocked at that quality. The mutex is held by the caller.
    bool isItemUnlockedNoLock(const std::string& quality, const std::string& itemId) const;
    //! \brief Marks the played level as won and saves the progress; with candidates and draw set, the first
    //! completion of a bonus level also unlocks its items. Returns true if a campaign level was won.
    bool completePlayedLevel(const std::map<std::string, std::vector<std::string> >* candidates, CampaignDraw draw);
};

#endif // CAMPAIGN_H
