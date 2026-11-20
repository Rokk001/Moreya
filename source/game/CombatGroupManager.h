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

#ifndef COMBATGROUPMANAGER_H
#define COMBATGROUPMANAGER_H

#include "game/CombatGroupRules.h"

#include <cstdint>
#include <iosfwd>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

class Creature;
class GameEntity;
class GameMap;
class Seat;
class Tile;

//! \brief One combat group: a raid group (always a group while it has living members) or the group that the fighters
//! of one keeper form against one raid group. Members are kept by creature name so that the group can be saved and
//! loaded one to one.
struct CombatGroup
{
    //! \brief Creates an empty keeper group that faces +x and does not retreat.
    CombatGroup();

    //! \brief Unique id of the group on this map.
    uint32_t mId;
    //! \brief True for a raid group, false for a keeper's group.
    bool mIsRaid;
    //! \brief The seat of the members.
    int32_t mSeatId;
    //! \brief The raid group: the group itself (raid) or the raid group it formed against (keeper).
    uint32_t mRaidGroupId;
    //! \brief Names of the members (the leader included).
    std::vector<std::string> mMembers;
    //! \brief Name of the leader, empty while there is none.
    std::string mLeader;
    //! \brief Name of the shared target chosen by the leader, empty while there is none.
    std::string mTarget;
    //! \brief Direction the group faces (towards the enemy or the way the leader walks).
    double mFacingX;
    double mFacingY;
    //! \brief Tile of the leader at the last update (-1 before the first one).
    int32_t mLastLeaderX;
    int32_t mLastLeaderY;
    //! \brief True while the group retreats to its gathering tile.
    bool mRetreating;
    //! \brief The gathering tile of the retreat.
    int32_t mRetreatX;
    int32_t mRetreatY;
    //! \brief Seconds the current retreat lasts so far.
    double mRetreatSeconds;
    //! \brief Seconds left before the leader can order the next retreat.
    double mRetreatCooldown;
};

//! \brief The registered raid member: its raid group and the fixed skill template it follows.
struct RaidMemberEntry
{
    //! \brief Creates a member of no raid group without a fixed template.
    RaidMemberEntry() :
        mRaidGroupId(0)
    {}

    //! \brief The raid group (1 or more).
    uint32_t mRaidGroupId;
    //! \brief Name of the fixed skill template, empty when the member chooses its template itself.
    std::string mTemplate;
};

//! \brief The aggro a member got from an enemy tank that hit it.
struct GroupAggroEntry
{
    //! \brief Creates an entry without tank.
    GroupAggroEntry() :
        mTurnsLeft(0)
    {}

    //! \brief Name of the enemy tank.
    std::string mTank;
    //! \brief Turns the member keeps attacking that tank.
    int64_t mTurnsLeft;
};

//! \brief Server side. The shared group combat of the raid and of the keepers' creatures: the raid registry (which
//! creature belongs to which raid group, its named leader and fixed skill templates, set by the level data and the
//! level script), the forming of the keeper groups against a raid, the leader, the shared target, the aggro of the
//! enemy tanks, the formation and the retreat. Without a raid nothing happens, so skirmish and multiplayer games stay
//! as they are.
class CombatGroupManager
{
public:
    //! \brief Creates the manager of the given map.
    explicit CombatGroupManager(GameMap& gameMap);

    //! \brief Forgets the raid registry and every group (a new level is loaded).
    void clear();

    //! \brief Registers a creature as a member of a raid group. A raid group is always a combat group. The member
    //! follows the fixed skill template when one is given (raid members get the template of their guild's
    //! composition), otherwise it chooses its template itself.
    //! \param creatureName The name of the creature (it may be spawned later).
    //! \param raidGroupId The raid group, 1 or more.
    //! \param templateName The name of a template of the creature's skill group, empty for none.
    void registerRaidMember(const std::string& creatureName, uint32_t raidGroupId, const std::string& templateName);

    //! \brief Names the leader of a raid group. He leads his group as long as he lives.
    void setRaidLeader(uint32_t raidGroupId, const std::string& leaderName);

    //! \brief Takes a raid member out of its raid group or lets it take part again (a raid leader who flees to the gate
    //! leaves his group, which goes on under the next leader). Set again by the raid when a game is loaded.
    void setRaidMemberDetached(const std::string& creatureName, bool detached);

    //! \brief True when the raid member was taken out of its raid group.
    bool isRaidMemberDetached(const std::string& creatureName) const;

    //! \brief True when the creature is registered as a raid member.
    bool isRaidMember(const std::string& creatureName) const;

    //! \brief Returns the raid group of a registered raid member, 0 for any other creature.
    uint32_t getRaidGroupId(const std::string& creatureName) const;

    //! \brief Returns the named leader of a raid group, empty when it has none.
    std::string getRaidLeaderName(uint32_t raidGroupId) const;

    //! \brief True when the creature is a raid member with a fixed skill template.
    bool hasFixedSkillTemplate(const std::string& creatureName) const;

    //! \brief Returns the registered raid members by creature name.
    inline const std::map<std::string, RaidMemberEntry>& getRaidMembers() const
    { return mRaidMembers; }

    //! \brief Returns the named leaders by raid group.
    inline const std::map<uint32_t, std::string>& getRaidLeaders() const
    { return mRaidLeaders; }

    //! \brief Returns the current groups.
    inline const std::vector<CombatGroup>& getGroups() const
    { return mGroups; }

    //! \brief Returns the group of the creature, nullptr when it is in none.
    const CombatGroup* getGroupOf(const std::string& creatureName) const;

    //! \brief True when the creature is a member of a group.
    bool isGroupMember(const std::string& creatureName) const;

    //! \brief True when there is neither a raid member nor a group (the manager has nothing to do and saves nothing).
    bool isEmpty() const;

    //! \brief Once per turn on the server: fixed templates, raid groups, forming and breaking up of the keeper
    //! groups, then per group the leader, the facing, the shared target, the retreat, the formation places and the
    //! aggro of every member. Does nothing while there is no raid member and no group.
    void update();

    //! \brief Called when a creature takes damage from another creature: a member hit by an enemy tank remembers
    //! that tank for GroupAggroMemorySeconds.
    void notifyAttacked(Creature& victim, Creature& attacker);

    //! \brief The creature a member of a group attacks in a fight: the enemy tank of its aggro, else the shared
    //! target of its group. nullptr when the creature is in no group or neither exists, then it chooses its target
    //! itself.
    GameEntity* getFightTarget(Creature& creature) const;

    //! \brief True when the group of the creature retreats.
    bool isRetreating(const Creature& creature) const;

    //! \brief True when the creature keeps its place in the formation instead of doing its own jobs: every member of
    //! a group that does not retreat, except the leader of a raid group, who walks where his orders lead him.
    bool shouldKeepFormation(const Creature& creature) const;

    //! \brief The tile of the creature's place in the formation, nullptr when it has none (the leader stands where
    //! he is).
    Tile* getFormationTile(const Creature& creature) const;

    //! \brief The gathering tile of the retreat of the creature's group, nullptr when it does not retreat.
    Tile* getRetreatTile(const Creature& creature) const;

    //! \brief True when the creature stands near enough to its place in the formation (GroupFormationTolerance).
    bool isAtFormationPlace(const Creature& creature, const Tile& place) const;

    //! \brief True when the creature has arrived at the gathering tile of a retreat (GroupGatherRadius).
    bool isAtGatheringTile(const Creature& creature, const Tile& gathering) const;

    //! \brief The role of a creature from the template it follows (rules of CombatGroupRules::roleOf with the
    //! lists of the [GroupCombat] block of global.cfg, read at every update).
    CombatGroupRules::Role getRole(const Creature& creature) const;

    //! \brief True when the seat is a keeper's seat (not the neutral seat and not a hero seat).
    static bool isKeeperSeat(const Seat* seat);

    //! \brief Writes the [CombatGroups] section: the raid registry always, the running groups and aggro only in a
    //! saved game. Writes nothing while the manager is empty.
    void exportToStream(std::ostream& os, bool isGameSave) const;

    //! \brief Reads the lines of a [CombatGroups] section up to [/CombatGroups] (the opening tag is already read).
    //! \return false on a line that cannot be read.
    bool importFromStream(std::istream& is);

    //! \brief The format of the lines of the [CombatGroups] section, written as a comment above them.
    static std::string getStreamFormat();

private:
    //! \brief Gives the fixed skill templates to the registered raid members that do not follow them yet.
    void applyFixedTemplates(const std::map<std::string, Creature*>& creatures);

    //! \brief Updates the raid groups from the living registered raid members.
    void updateRaidGroups(const std::map<uint32_t, std::vector<Creature*> >& raid);

    //! \brief Removes the members that can no longer be in their keeper group and lets new fighters join.
    void updateKeeperGroups(const std::vector<Creature*>& creatures, const std::map<std::string, Creature*>& byName,
        const std::map<uint32_t, std::vector<Creature*> >& raid);

    //! \brief Breaks up the keeper groups whose raid group is gone or out of reach, and removes empty groups.
    void removeEndedGroups(const std::map<std::string, Creature*>& byName,
        const std::map<uint32_t, std::vector<Creature*> >& raid);

    //! \brief Leader, facing, shared target, retreat, formation places and aggro of one group.
    void updateGroup(CombatGroup& group, const std::map<std::string, Creature*>& byName,
        const std::vector<Creature*>& creatures);

    //! \brief Chooses the gathering tile of a retreat: behind the next own door, else at the nearest own room
    //! away from the enemy. False when there is none.
    bool findRetreatTile(const CombatGroup& group, Creature& leader, double groupX, double groupY, double enemyX,
        double enemyY, int32_t& x, int32_t& y) const;

    //! \brief A walkable tile at or around the given position, nullptr when there is none.
    Tile* findStandingTile(double x, double y) const;

    //! \brief True when the creature can be (or stay) a member of a keeper group of the given seat.
    bool canStayInKeeperGroup(const Creature& creature, int32_t seatId) const;

    //! \brief True when the creature takes part in its raid group (no worker, alive, on the map, not imprisoned, not
    //! won over by a keeper).
    static bool isActiveRaidMember(const Creature& creature);

    //! \brief Returns the group with that id, nullptr when there is none.
    CombatGroup* findGroup(uint32_t groupId);

    //! \brief Rebuilds the member index from the groups.
    void rebuildMemberIndex();

    GameMap& mGameMap;
    //! \brief The registered raid members by creature name.
    std::map<std::string, RaidMemberEntry> mRaidMembers;
    //! \brief The named leaders by raid group.
    std::map<uint32_t, std::string> mRaidLeaders;
    //! \brief The current groups.
    std::vector<CombatGroup> mGroups;
    //! \brief The id the next new group gets.
    uint32_t mNextGroupId;
    //! \brief The aggro of the members hit by an enemy tank, by member name.
    std::map<std::string, GroupAggroEntry> mAggro;
    //! \brief Transient: the group id of every member, rebuilt at every update.
    std::map<std::string, uint32_t> mMemberGroup;
    //! \brief Transient: the formation tile of every member that has a place, rebuilt at every update.
    std::map<std::string, std::pair<int32_t, int32_t> > mPlaces;
    //! \brief Transient: the enemy tank every member attacks because of its aggro, rebuilt at every update.
    std::map<std::string, std::string> mAggroTargets;
    //! \brief Transient: raid members whose fixed template could not be given (logged once).
    std::set<std::string> mTemplateFailures;
    //! \brief Raid members taken out of their raid group (a fleeing raid leader); the raid sets them again on a load.
    std::set<std::string> mDetachedRaidMembers;
    //! \brief Transient: the role lists of the config, read at every update.
    CombatGroupRules::RoleSettings mRoleSettings;
};

#endif // COMBATGROUPMANAGER_H
