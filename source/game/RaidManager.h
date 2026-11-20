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

#ifndef RAIDMANAGER_H
#define RAIDMANAGER_H

#include "game/RaidRules.h"

#include <cstdint>
#include <iosfwd>
#include <set>
#include <string>
#include <utility>
#include <vector>

class Creature;
class GameMap;
class Room;
class RoomPortalWave;
class Seat;
class Tile;

//! \brief What a raid leader does about the gate.
enum class RaidLeaderState
{
    //! \brief He leads his raid group (or has not come yet).
    none,
    //! \brief His group has fallen: he runs to the gate.
    fleeing,
    //! \brief He reached the gate and left the level: the level is lost.
    escaped
};

//! \brief One member of a raid group as the level data defines it.
struct RaidMemberSpec
{
    //! \brief Creates a member of no class at level 1 without name and without fixed template.
    RaidMemberSpec() :
        mLevel(1)
    {}

    //! \brief Creature class (Knight, Wizard, ...).
    std::string mClassName;
    //! \brief Level the member comes with.
    uint32_t mLevel;
    //! \brief Name of the creature, empty when the game chooses one.
    std::string mName;
    //! \brief Fixed skill template of the member (its guild's composition), empty when it chooses itself.
    std::string mTemplate;
};

//! \brief One raid group: its composition and named leader from the level data, and what became of it in the game.
struct RaidGroupData
{
    //! \brief Creates a raid group 0 that has not come.
    RaidGroupData() :
        mRaidGroupId(0),
        mArrived(false),
        mLeaderState(RaidLeaderState::none)
    {}

    //! \brief The raid group (1 or more), the same id as in the raid registry of the combat groups.
    uint32_t mRaidGroupId;
    //! \brief Name of the named leader (one of the members), empty when the group has none.
    std::string mLeaderName;
    //! \brief The members in the order they come through the gate.
    std::vector<RaidMemberSpec> mMembers;
    //! \brief True once the group came through the gate.
    bool mArrived;
    //! \brief Names of the creatures that came through the gate (filled at the arrival).
    std::vector<std::string> mSpawned;
    //! \brief Name the named leader got in the game (his spawned creature), empty before the arrival.
    std::string mLeaderSpawned;
    //! \brief Flight of the leader.
    RaidLeaderState mLeaderState;
};

//! \brief Server side. The raid of a level: the Moreya gate (an unclaimable, indestructible hero portal room that shows
//! the gate model), the countdown from the level start until the gate opens, the early opening by the player, the raid
//! groups that come through the gate one after the other, their march to the dungeon heart of the attacked keeper with
//! the plundering of the treasuries on the way, the flight of a raid leader to the gate and the defeat of the whole
//! raid. The level data is the [Raid] section of the level file; a saved game adds the running state. Without a [Raid]
//! section nothing happens, so skirmish and multiplayer games stay as they are. Only the level that is played is
//! attacked: the raid exists only in the level file that is loaded.
class RaidManager
{
public:
    //! \brief Creates the manager of the given map (no raid).
    explicit RaidManager(GameMap& gameMap);

    //! \brief Forgets the raid and its state (a new level is loaded).
    void clear();

    //! \brief True when the level has a raid ([Raid] section with a gate).
    inline bool hasRaid() const
    { return mHasGate; }

    //! \brief Once per turn on the server, before the combat groups: sets the gate up, lets the countdown run, lets
    //! the raid groups come, plunders, starts and ends the flight of the leaders and loses the level when a leader
    //! escaped. Does nothing without a raid and in a campaign bonus level.
    void update();

    //! \brief The keeper of the seat opens the gate before the countdown ends (button of the HUD, script action
    //! raidopen with seat -1): the first raid group comes at once.
    //! \param seatId The seat that asks, -1 for the level script. Only the attacked keeper may open the gate.
    //! \return True when the gate opens now.
    bool openGateEarly(int32_t seatId);

    //! \brief Sets the seconds until the next raid group comes (script action raidcountdown).
    void setSecondsToNextGroup(double seconds);

    //! \brief The whole seconds the HUD countdown shows, -1 when no raid group waits.
    int32_t getCountdownToShow() const;

    //! \brief True while the gate is closed, so that the countdown runs to the first raid group and the player may
    //! open the gate early; false when it shows the time to the next group.
    bool isGateClosed() const;

    //! \brief True when the creature is a raid leader that flees to the gate (it takes part in no fight).
    bool isEscaping(const std::string& creatureName) const;

    //! \brief The standing order of a raid member that has nothing else to do: a fleeing leader runs to the gate, the
    //! leader of a raid group leads it to the dungeon heart of the attacked keeper and turns aside to the treasuries on
    //! the way. Called before the orders of the level script.
    //! \return True when the order takes the turn of the creature.
    bool doCreatureOrder(Creature& creature);

    //! \brief Level script condition "raid": arrived (every raid group came, or the given one), defeated (the whole
    //! raid with its leaders), escaped (a leader escaped through the gate), fleeing (a leader flees) and open (the gate
    //! is open).
    //! \param state The word of the condition.
    //! \param raidGroupId 0 for the whole raid, else the raid group.
    bool isStateMet(const std::string& state, uint32_t raidGroupId) const;

    //! \brief The raid groups with their state.
    inline const std::vector<RaidGroupData>& getGroups() const
    { return mGroups; }

    //! \brief The arrival schedule.
    inline const RaidRules::Schedule& getSchedule() const
    { return mSchedule; }

    //! \brief Writes the [Raid] section: the level data always, the running state only in a saved game. Writes
    //! nothing without a raid.
    void exportToStream(std::ostream& os, bool isGameSave) const;

    //! \brief Reads the lines of a [Raid] section up to [/Raid] (the opening tag is already read).
    //! \return false on a line that cannot be read.
    bool importFromStream(std::istream& is);

    //! \brief The format of the lines of the [Raid] section, written as a comment above them.
    static std::string getStreamFormat();

    //! \brief The word a leader state is saved as (none, fleeing, escaped).
    static const char* leaderStateName(RaidLeaderState state);

    //! \brief Reads a saved leader state word. False for an unknown word.
    static bool parseLeaderState(const std::string& text, RaidLeaderState& state);

private:
    //! \brief Countdown of the level, else of the config.
    double countdownSeconds() const;
    //! \brief Interval of the level, else of the config.
    double intervalSeconds() const;
    //! \brief Escape share of the level, else of the config.
    double escapeShare() const;

    //! \brief Lets the seconds pass on the schedule: a raid group whose countdown ended comes through the gate, and the
    //! portcullis of the gate model sinks when the gate opens.
    void advanceSchedule(double seconds);

    //! \brief Finds the hero portal room on the gate tile and lets it show the gate with the portcullis down or sunk.
    void setUpGate();

    //! \brief The hero portal room that is the gate, nullptr when there is none.
    RoomPortalWave* getGateRoom() const;

    //! \brief Lets the raid group with the given index come through the gate: creates its members, registers them
    //! with their fixed templates and their leader in the raid registry of the combat groups and tells the players.
    void spawnGroup(uint32_t index);

    //! \brief Every raid member standing on a tile of a treasury (or a dungeon heart) of a keeper that is an enemy of
    //! the raid takes its share of the gold, once per room.
    void plunder();

    //! \brief Starts the flight of the leaders whose groups have fallen and ends it at the gate.
    void updateLeaders();

    //! \brief The leader reached the gate: he leaves the map with what he carries and the level is lost.
    void escape(RaidGroupData& group, Creature& leader);

    //! \brief True while a raid member stands: alive on the map, not imprisoned and not won over by a keeper.
    bool isStanding(const std::string& creatureName) const;

    //! \brief True when the creature stands on the gate (a tile of the gate room or near the gate tile).
    bool isAtGate(const Creature& creature) const;

    //! \brief The raid group a spawned member belongs to, nullptr for any other creature.
    const RaidGroupData* findGroupOfSpawned(const std::string& creatureName) const;

    //! \brief The rooms of keepers hostile to the raid that hold gold: treasuries and dungeon hearts.
    std::vector<Room*> plunderableRooms() const;

    //! \brief Sends a chat message to the attacked keeper (to every human keeper when no seat is attacked).
    void tellKeepers(const std::string& text) const;

    GameMap& mGameMap;
    //! \brief True when the level has a gate (and so a raid).
    bool mHasGate;
    //! \brief The tile in the middle of the gate (the central tile of its hero portal room).
    int32_t mGateX;
    int32_t mGateY;
    //! \brief Rotation of the gate model in degrees (0: its front faces -Y).
    double mGateRotation;
    //! \brief Seat of the raid (a hero seat).
    int32_t mRaidSeatId;
    //! \brief Seat whose dungeon the raid attacks (-1: every human keeper loses on an escape, no heart is attacked).
    int32_t mTargetSeatId;
    //! \brief Seconds from the level start to the first group, negative: config RaidCountdownSeconds.
    double mCountdownSeconds;
    //! \brief Seconds between two groups, negative: config RaidWaveIntervalSeconds.
    double mIntervalSeconds;
    //! \brief Fallen share before a leader flees, negative: config RaidLeaderEscapeShare.
    double mEscapeShare;
    //! \brief The raid groups in the order of their arrival.
    std::vector<RaidGroupData> mGroups;
    //! \brief True once the schedule was started at the level start.
    bool mStarted;
    //! \brief The arrival schedule.
    RaidRules::Schedule mSchedule;
    //! \brief True once a leader escaped and the level was lost.
    bool mLost;
    //! \brief The rooms each raid member already plundered: (creature name, room name).
    std::set<std::pair<std::string, std::string> > mPlundered;
    //! \brief Transient: true once the gate room shows the gate model in this game.
    bool mGateShown;
    //! \brief Transient: true once the bonus level message was logged.
    bool mBonusLogged;
};

#endif // RAIDMANAGER_H
