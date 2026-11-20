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

#include "game/CombatGroupManager.h"

#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntity.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "game/RaidManager.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "gamemap/Pathfinding.h"
#include "rooms/Room.h"
#include "traps/Trap.h"
#include "utils/ConfigManager.h"
#include "utils/LogManager.h"
#include "ODApplication.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <istream>
#include <ostream>
#include <sstream>

namespace
{
//! \brief Written instead of an empty name in the [CombatGroups] section.
const std::string NO_NAME = "-";

//! \brief Returns the name, "-" for an empty one.
std::string nameOrDash(const std::string& name)
{
    return name.empty() ? NO_NAME : name;
}

//! \brief Returns the name read from the section, empty for "-".
std::string dashToEmpty(const std::string& token)
{
    return (token == NO_NAME) ? std::string() : token;
}

//! \brief Returns a number of the [GroupCombat] block of global.cfg.
double groupConfig(const std::string& key)
{
    return ConfigManager::getSingleton().getGroupCombatConfigDouble(key);
}

//! \brief The distance between two tiles in tiles: the largest of the x and y distance.
int32_t tileDistance(const Tile& first, const Tile& second)
{
    return std::max(std::abs(first.getX() - second.getX()), std::abs(first.getY() - second.getY()));
}

//! \brief The squared distance between two points, rounded to a whole number of squared tiles.
int32_t squaredDistance(double x1, double y1, double x2, double y2)
{
    const double dx = x1 - x2;
    const double dy = y1 - y2;
    return static_cast<int32_t>(std::lround(dx * dx + dy * dy));
}

//! \brief Seconds of one game turn.
double secondsPerTurn()
{
    return 1.0 / ODApplication::turnsPerSecond;
}

//! \brief The living, visible, not knocked out enemy creatures the creature sees.
std::vector<Creature*> visibleEnemyCreatures(Creature& creature)
{
    std::vector<Creature*> enemies;
    const std::vector<GameEntity*> objects = creature.getVisibleEnemyObjects();
    for(GameEntity* entity : objects)
    {
        if(entity->getObjectType() != GameEntityType::creature)
            continue;

        Creature* enemy = static_cast<Creature*>(entity);
        if(!enemy->isAlive() || enemy->isKo() || enemy->isInvisible() || (enemy->getPositionTile() == nullptr))
            continue;

        enemies.push_back(enemy);
    }
    return enemies;
}

//! \brief True when the seats of the two creatures are enemies (both known and not allied).
bool areEnemies(const Creature& first, const Creature& second)
{
    if((first.getSeat() == nullptr) || (second.getSeat() == nullptr))
        return false;

    return !first.getSeat()->isAlliedSeat(second.getSeat());
}
}

//! \brief Creates an empty keeper group of no seat that faces +x and neither retreats nor waits for a retreat.
CombatGroup::CombatGroup() :
    mId(0),
    mIsRaid(false),
    mSeatId(0),
    mRaidGroupId(0),
    mFacingX(1.0),
    mFacingY(0.0),
    mLastLeaderX(-1),
    mLastLeaderY(-1),
    mRetreating(false),
    mRetreatX(0),
    mRetreatY(0),
    mRetreatSeconds(0.0),
    mRetreatCooldown(0.0)
{
}

//! \brief Creates an empty manager for the map; the first group gets the id 1.
CombatGroupManager::CombatGroupManager(GameMap& gameMap) :
    mGameMap(gameMap),
    mNextGroupId(1)
{
}

//! \brief Forgets the raid registry, the groups, the aggro, the detached raid members and the transient state.
void CombatGroupManager::clear()
{
    mRaidMembers.clear();
    mRaidLeaders.clear();
    mGroups.clear();
    mNextGroupId = 1;
    mAggro.clear();
    mMemberGroup.clear();
    mPlaces.clear();
    mAggroTargets.clear();
    mTemplateFailures.clear();
    mDetachedRaidMembers.clear();
}

//! \brief Adds or changes the entry of a raid member; a raid group id of 0 is refused.
void CombatGroupManager::registerRaidMember(const std::string& creatureName, uint32_t raidGroupId,
    const std::string& templateName)
{
    if(creatureName.empty() || (raidGroupId == 0))
    {
        OD_LOG_ERR("Invalid raid member name=" + creatureName + ", raidGroup=" + std::to_string(raidGroupId));
        return;
    }

    RaidMemberEntry& entry = mRaidMembers[creatureName];
    entry.mRaidGroupId = raidGroupId;
    entry.mTemplate = templateName;
    mTemplateFailures.erase(creatureName);
    OD_LOG_INF("Raid member registered name=" + creatureName + ", raidGroup=" + std::to_string(raidGroupId)
        + ", template=" + nameOrDash(templateName));
}

//! \brief Sets (or with an empty name removes) the named leader of a raid group.
void CombatGroupManager::setRaidLeader(uint32_t raidGroupId, const std::string& leaderName)
{
    if(raidGroupId == 0)
    {
        OD_LOG_ERR("Invalid raid group 0 for the leader " + leaderName);
        return;
    }

    if(leaderName.empty())
        mRaidLeaders.erase(raidGroupId);
    else
        mRaidLeaders[raidGroupId] = leaderName;

    OD_LOG_INF("Raid leader of raid group " + std::to_string(raidGroupId) + " is " + nameOrDash(leaderName));
}

//! \brief Adds the raid member to the detached members or removes it from them.
void CombatGroupManager::setRaidMemberDetached(const std::string& creatureName, bool detached)
{
    if(detached)
        mDetachedRaidMembers.insert(creatureName);
    else
        mDetachedRaidMembers.erase(creatureName);
}

//! \brief Looks the creature up in the detached raid members.
bool CombatGroupManager::isRaidMemberDetached(const std::string& creatureName) const
{
    return mDetachedRaidMembers.count(creatureName) > 0;
}

//! \brief Looks the creature up in the raid registry.
bool CombatGroupManager::isRaidMember(const std::string& creatureName) const
{
    return mRaidMembers.find(creatureName) != mRaidMembers.end();
}

//! \brief Returns the registered raid group of the creature or 0.
uint32_t CombatGroupManager::getRaidGroupId(const std::string& creatureName) const
{
    std::map<std::string, RaidMemberEntry>::const_iterator it = mRaidMembers.find(creatureName);
    if(it == mRaidMembers.end())
        return 0;

    return it->second.mRaidGroupId;
}

//! \brief Returns the named leader of the raid group or an empty name.
std::string CombatGroupManager::getRaidLeaderName(uint32_t raidGroupId) const
{
    std::map<uint32_t, std::string>::const_iterator it = mRaidLeaders.find(raidGroupId);
    if(it == mRaidLeaders.end())
        return std::string();

    return it->second;
}

//! \brief True when the registry gives the creature a fixed template.
bool CombatGroupManager::hasFixedSkillTemplate(const std::string& creatureName) const
{
    std::map<std::string, RaidMemberEntry>::const_iterator it = mRaidMembers.find(creatureName);
    return (it != mRaidMembers.end()) && !it->second.mTemplate.empty();
}

//! \brief Finds the group of a member through the member index.
const CombatGroup* CombatGroupManager::getGroupOf(const std::string& creatureName) const
{
    std::map<std::string, uint32_t>::const_iterator it = mMemberGroup.find(creatureName);
    if(it == mMemberGroup.end())
        return nullptr;

    for(const CombatGroup& group : mGroups)
    {
        if(group.mId == it->second)
            return &group;
    }
    return nullptr;
}

//! \brief True when the member index knows the creature.
bool CombatGroupManager::isGroupMember(const std::string& creatureName) const
{
    return mMemberGroup.find(creatureName) != mMemberGroup.end();
}

//! \brief True without raid registry and without groups.
bool CombatGroupManager::isEmpty() const
{
    return mRaidMembers.empty() && mRaidLeaders.empty() && mGroups.empty();
}

//! \brief Finds a group by its id.
CombatGroup* CombatGroupManager::findGroup(uint32_t groupId)
{
    for(CombatGroup& group : mGroups)
    {
        if(group.mId == groupId)
            return &group;
    }
    return nullptr;
}

//! \brief Indexes every member by its group and forgets the aggro of creatures that are no members anymore.
void CombatGroupManager::rebuildMemberIndex()
{
    mMemberGroup.clear();
    for(const CombatGroup& group : mGroups)
    {
        for(const std::string& member : group.mMembers)
            mMemberGroup[member] = group.mId;
    }

    std::map<std::string, GroupAggroEntry>::iterator it = mAggro.begin();
    while(it != mAggro.end())
    {
        if(mMemberGroup.find(it->first) == mMemberGroup.end())
            it = mAggro.erase(it);
        else
            ++it;
    }
}

//! \brief Maps the template of the creature to its role with the role lists of the config.
CombatGroupRules::Role CombatGroupManager::getRole(const Creature& creature) const
{
    const CreatureDefinition* definition = creature.getDefinition();
    if(definition == nullptr)
        return CombatGroupRules::Role::melee;

    const std::string& skillGroup = definition->getSkillGroup();
    const CreatureSkillTree::TemplateDef* templ = ConfigManager::getSingleton().getCreatureSkillTree().findTemplate(
        skillGroup, creature.getSkillBuild().mTemplate);
    const std::string primaryPath = (templ != nullptr) ? templ->mPrimary : std::string();
    return CombatGroupRules::roleOf(mRoleSettings, skillGroup, templ != nullptr, primaryPath);
}

//! \brief Keeper seats: every seat except the neutral seat and the hero seats.
bool CombatGroupManager::isKeeperSeat(const Seat* seat)
{
    if(seat == nullptr)
        return false;

    return !seat->isRogueSeat() && (seat->getFaction() != "Hero");
}

//! \brief A raid member takes part while it lives on the map, is not imprisoned and was not won over by a keeper. A
//! worker is never a group member.
bool CombatGroupManager::isActiveRaidMember(const Creature& creature)
{
    if((creature.getDefinition() == nullptr) || creature.getDefinition()->isWorker())
        return false;

    return creature.isAlive() && creature.getIsOnMap() && !creature.isInPrison() &&
        (creature.getSeat() != nullptr) && !isKeeperSeat(creature.getSeat());
}

//! \brief A keeper's fighter stays in its group while it lives on the map, is not in the hand, not imprisoned, not
//! possessed, still belongs to the seat of the group and is no raid member.
bool CombatGroupManager::canStayInKeeperGroup(const Creature& creature, int32_t seatId) const
{
    if(!creature.isAlive() || !creature.getIsOnMap() || creature.isInHand() || creature.isInPrison() ||
       creature.isPossessed())
        return false;

    if((creature.getDefinition() == nullptr) || creature.getDefinition()->isWorker())
        return false;

    if((creature.getSeat() == nullptr) || (creature.getSeat()->getId() != seatId))
        return false;

    return !isRaidMember(creature.getName());
}

//! \brief Calls Creature::setFixedSkillTemplate for every raid member that does not follow its fixed template yet.
void CombatGroupManager::applyFixedTemplates(const std::map<std::string, Creature*>& creatures)
{
    for(std::map<std::string, RaidMemberEntry>::const_iterator it = mRaidMembers.begin(); it != mRaidMembers.end(); ++it)
    {
        if(it->second.mTemplate.empty())
            continue;

        std::map<std::string, Creature*>::const_iterator found = creatures.find(it->first);
        if((found == creatures.end()) || !found->second->isAlive())
            continue;

        Creature* creature = found->second;
        if(creature->getSkillTemplateName() == it->second.mTemplate)
            continue;

        if(mTemplateFailures.count(it->first) > 0)
            continue;

        if(creature->setFixedSkillTemplate(it->second.mTemplate))
        {
            OD_LOG_INF("Raid member " + it->first + " follows the fixed template " + it->second.mTemplate);
            continue;
        }

        mTemplateFailures.insert(it->first);
        OD_LOG_WRN("Raid member " + it->first + " cannot follow the template " + it->second.mTemplate
            + " (not a template of its skill group)");
    }
}

//! \brief Creates a raid group at the first living member and sets its members; a raid group without living members
//! keeps no member and is removed afterwards.
void CombatGroupManager::updateRaidGroups(const std::map<uint32_t, std::vector<Creature*> >& raid)
{
    for(CombatGroup& group : mGroups)
    {
        if(group.mIsRaid && (raid.find(group.mRaidGroupId) == raid.end()))
            group.mMembers.clear();
    }

    for(std::map<uint32_t, std::vector<Creature*> >::const_iterator it = raid.begin(); it != raid.end(); ++it)
    {
        if(it->second.empty())
            continue;

        CombatGroup* group = nullptr;
        for(CombatGroup& candidate : mGroups)
        {
            if(candidate.mIsRaid && (candidate.mRaidGroupId == it->first))
            {
                group = &candidate;
                break;
            }
        }

        if(group == nullptr)
        {
            // The seat of the raid group is the seat of its named leader, else of its first member
            Creature* first = it->second.front();
            const std::string leaderName = getRaidLeaderName(it->first);
            for(Creature* member : it->second)
            {
                if(member->getName() == leaderName)
                    first = member;
            }

            CombatGroup newGroup;
            newGroup.mId = mNextGroupId++;
            newGroup.mIsRaid = true;
            newGroup.mSeatId = first->getSeat()->getId();
            newGroup.mRaidGroupId = it->first;
            mGroups.push_back(newGroup);
            group = &mGroups.back();
            OD_LOG_INF("Raid group " + std::to_string(it->first) + " forms as combat group "
                + std::to_string(newGroup.mId) + ", seat=" + std::to_string(newGroup.mSeatId));
        }

        group->mMembers.clear();
        for(Creature* member : it->second)
        {
            if(member->getSeat()->getId() == group->mSeatId)
                group->mMembers.push_back(member->getName());
        }
        std::sort(group->mMembers.begin(), group->mMembers.end());
    }
}

//! \brief Removes the members that left their keeper group, then lets every keeper's fighter that is near a member of
//! an enemy raid group join the group of its keeper against that raid group (one group per keeper and raid group).
void CombatGroupManager::updateKeeperGroups(const std::vector<Creature*>& creatures,
    const std::map<std::string, Creature*>& byName, const std::map<uint32_t, std::vector<Creature*> >& raid)
{
    for(CombatGroup& group : mGroups)
    {
        if(group.mIsRaid)
            continue;

        std::vector<std::string> kept;
        for(const std::string& member : group.mMembers)
        {
            std::map<std::string, Creature*>::const_iterator found = byName.find(member);
            if((found != byName.end()) && canStayInKeeperGroup(*found->second, group.mSeatId))
            {
                kept.push_back(member);
                continue;
            }
            OD_LOG_INF("Creature " + member + " leaves the combat group " + std::to_string(group.mId));
        }
        group.mMembers = kept;
    }
    rebuildMemberIndex();

    const double formingDistance = groupConfig("GroupFormingDistance");
    const double formingSquared = formingDistance * formingDistance;
    for(Creature* creature : creatures)
    {
        if(isGroupMember(creature->getName()) || (creature->getSeat() == nullptr) ||
           !canStayInKeeperGroup(*creature, creature->getSeat()->getId()) || !isKeeperSeat(creature->getSeat()))
            continue;

        Tile* tile = creature->getPositionTile();
        if(tile == nullptr)
            continue;

        for(std::map<uint32_t, std::vector<Creature*> >::const_iterator it = raid.begin(); it != raid.end(); ++it)
        {
            bool isNear = false;
            for(Creature* raider : it->second)
            {
                Tile* raiderTile = raider->getPositionTile();
                if((raiderTile == nullptr) || !areEnemies(*creature, *raider))
                    continue;

                if(static_cast<double>(Pathfinding::squaredDistanceTile(*tile, *raiderTile)) <= formingSquared)
                {
                    isNear = true;
                    break;
                }
            }
            if(!isNear)
                continue;

            CombatGroup* group = nullptr;
            for(CombatGroup& candidate : mGroups)
            {
                if(!candidate.mIsRaid && (candidate.mRaidGroupId == it->first) &&
                   (candidate.mSeatId == creature->getSeat()->getId()))
                {
                    group = &candidate;
                    break;
                }
            }
            if(group == nullptr)
            {
                CombatGroup newGroup;
                newGroup.mId = mNextGroupId++;
                newGroup.mIsRaid = false;
                newGroup.mSeatId = creature->getSeat()->getId();
                newGroup.mRaidGroupId = it->first;
                mGroups.push_back(newGroup);
                group = &mGroups.back();
                OD_LOG_INF("Combat group " + std::to_string(newGroup.mId) + " of seat " + std::to_string(newGroup.mSeatId)
                    + " forms against raid group " + std::to_string(it->first));
            }

            group->mMembers.push_back(creature->getName());
            mMemberGroup[creature->getName()] = group->mId;
            OD_LOG_INF("Creature " + creature->getName() + " joins the combat group " + std::to_string(group->mId));
            break;
        }
    }
}

//! \brief Removes empty groups and the keeper groups whose raid group is defeated or no longer within
//! GroupDissolveDistance of any of their members.
void CombatGroupManager::removeEndedGroups(const std::map<std::string, Creature*>& byName,
    const std::map<uint32_t, std::vector<Creature*> >& raid)
{
    const double dissolveDistance = groupConfig("GroupDissolveDistance");
    const double dissolveSquared = dissolveDistance * dissolveDistance;
    std::vector<CombatGroup>::iterator it = mGroups.begin();
    while(it != mGroups.end())
    {
        bool ended = it->mMembers.empty();
        if(!ended && !it->mIsRaid)
        {
            std::map<uint32_t, std::vector<Creature*> >::const_iterator raidIt = raid.find(it->mRaidGroupId);
            bool raidNear = false;
            if(raidIt != raid.end())
            {
                for(const std::string& member : it->mMembers)
                {
                    std::map<std::string, Creature*>::const_iterator found = byName.find(member);
                    Tile* memberTile = (found != byName.end()) ? found->second->getPositionTile() : nullptr;
                    if(memberTile == nullptr)
                        continue;

                    for(Creature* raider : raidIt->second)
                    {
                        Tile* raiderTile = raider->getPositionTile();
                        if((raiderTile != nullptr) &&
                           (static_cast<double>(Pathfinding::squaredDistanceTile(*memberTile, *raiderTile)) <= dissolveSquared))
                        {
                            raidNear = true;
                            break;
                        }
                    }
                    if(raidNear)
                        break;
                }
            }
            ended = !raidNear;
        }

        if(!ended)
        {
            ++it;
            continue;
        }

        OD_LOG_INF("Combat group " + std::to_string(it->mId) + " breaks up");
        it = mGroups.erase(it);
    }
}

//! \brief Runs the group rules once per turn (see the header). A detached raid member is left out of its raid group.
void CombatGroupManager::update()
{
    if(isEmpty())
        return;

    ConfigManager& config = ConfigManager::getSingleton();
    mRoleSettings.mTankPaths = config.getGroupCombatConfigWords("GroupTankPaths");
    mRoleSettings.mHealerPaths = config.getGroupCombatConfigWords("GroupHealerPaths");
    mRoleSettings.mRangedSkillGroups = config.getGroupCombatConfigWords("GroupRangedSkillGroups");

    // The aggro of a hit fades after its turns
    std::map<std::string, GroupAggroEntry>::iterator aggroIt = mAggro.begin();
    while(aggroIt != mAggro.end())
    {
        --aggroIt->second.mTurnsLeft;
        if(aggroIt->second.mTurnsLeft <= 0)
            aggroIt = mAggro.erase(aggroIt);
        else
            ++aggroIt;
    }

    const std::vector<Creature*>& creatures = mGameMap.getCreatures();
    std::map<std::string, Creature*> byName;
    for(Creature* creature : creatures)
        byName[creature->getName()] = creature;

    applyFixedTemplates(byName);

    // The living raid members by raid group. A member won over by a keeper leaves the raid registry for good
    std::map<uint32_t, std::vector<Creature*> > raid;
    std::vector<std::string> wonOver;
    for(std::map<std::string, RaidMemberEntry>::const_iterator it = mRaidMembers.begin(); it != mRaidMembers.end(); ++it)
    {
        std::map<std::string, Creature*>::const_iterator found = byName.find(it->first);
        if(found == byName.end())
            continue;

        Creature* creature = found->second;
        if(creature->isAlive() && isKeeperSeat(creature->getSeat()))
        {
            wonOver.push_back(it->first);
            continue;
        }

        // A detached member (a raid leader fleeing to the gate) no longer takes part in its raid group
        if(isActiveRaidMember(*creature) && !isRaidMemberDetached(it->first))
            raid[it->second.mRaidGroupId].push_back(creature);
    }
    for(const std::string& name : wonOver)
    {
        OD_LOG_INF("Raid member " + name + " was won over by a keeper and leaves the raid");
        mRaidMembers.erase(name);
    }

    updateRaidGroups(raid);
    rebuildMemberIndex();
    updateKeeperGroups(creatures, byName, raid);
    removeEndedGroups(byName, raid);
    rebuildMemberIndex();

    mPlaces.clear();
    mAggroTargets.clear();
    for(CombatGroup& group : mGroups)
        updateGroup(group, byName, creatures);
}

//! \brief Leader (G2), facing, shared target (G4), retreat (G7), formation places (G6) and aggro (G5) of one group.
void CombatGroupManager::updateGroup(CombatGroup& group, const std::map<std::string, Creature*>& byName,
    const std::vector<Creature*>& creatures)
{
    std::vector<Creature*> present;
    for(const std::string& member : group.mMembers)
    {
        std::map<std::string, Creature*>::const_iterator found = byName.find(member);
        if((found == byName.end()) || !found->second->isAlive() || !found->second->getIsOnMap() ||
           (found->second->getPositionTile() == nullptr))
            continue;

        present.push_back(found->second);
    }
    if(present.empty())
        return;

    // G2: the named raid leader while he lives, else the highest level, then the most experience
    std::vector<CombatGroupRules::LeaderCandidate> candidates;
    for(Creature* member : present)
    {
        CombatGroupRules::LeaderCandidate candidate;
        candidate.mName = member->getName();
        candidate.mLevel = member->getLevel();
        candidate.mExperience = member->getExp();
        candidates.push_back(candidate);
    }
    const std::string namedLeader = group.mIsRaid ? getRaidLeaderName(group.mRaidGroupId) : std::string();
    const int32_t leaderIndex = CombatGroupRules::chooseLeader(candidates, namedLeader);
    if(leaderIndex < 0)
        return;

    Creature* leader = present[static_cast<size_t>(leaderIndex)];
    if(group.mLeader != leader->getName())
    {
        OD_LOG_INF("Combat group " + std::to_string(group.mId) + " is led by " + leader->getName()
            + (group.mLeader.empty() ? std::string() : " after " + group.mLeader));
        group.mLeader = leader->getName();
    }
    Tile* leaderTile = leader->getPositionTile();

    // G4: the leader chooses the shared target among the enemies he sees, else among those a member sees
    std::vector<Creature*> enemies = visibleEnemyCreatures(*leader);
    for(size_t i = 0; enemies.empty() && (i < present.size()); ++i)
        enemies = visibleEnemyCreatures(*present[i]);

    std::vector<CombatGroupRules::TargetCandidate> targets;
    double enemyX = 0.0;
    double enemyY = 0.0;
    for(Creature* enemy : enemies)
    {
        Tile* enemyTile = enemy->getPositionTile();
        CombatGroupRules::TargetCandidate target;
        target.mName = enemy->getName();
        target.mRole = getRole(*enemy);
        target.mSquaredDistance = Pathfinding::squaredDistanceTile(*leaderTile, *enemyTile);
        targets.push_back(target);
        enemyX += static_cast<double>(enemyTile->getX());
        enemyY += static_cast<double>(enemyTile->getY());
    }
    if(!enemies.empty())
    {
        enemyX /= static_cast<double>(enemies.size());
        enemyY /= static_cast<double>(enemies.size());
    }

    const int32_t targetIndex = CombatGroupRules::chooseSharedTarget(targets, group.mTarget);
    const std::string target = (targetIndex >= 0) ? targets[static_cast<size_t>(targetIndex)].mName : std::string();
    if(target != group.mTarget)
    {
        OD_LOG_INF("Combat group " + std::to_string(group.mId) + " targets " + nameOrDash(target));
        group.mTarget = target;
    }

    // The group faces its target, else the way its leader walks
    double facingX = 0.0;
    double facingY = 0.0;
    if(targetIndex >= 0)
    {
        Tile* targetTile = enemies[static_cast<size_t>(targetIndex)]->getPositionTile();
        facingX = static_cast<double>(targetTile->getX() - leaderTile->getX());
        facingY = static_cast<double>(targetTile->getY() - leaderTile->getY());
    }
    else if(group.mLastLeaderX >= 0)
    {
        facingX = static_cast<double>(leaderTile->getX() - group.mLastLeaderX);
        facingY = static_cast<double>(leaderTile->getY() - group.mLastLeaderY);
    }
    if((facingX != 0.0) || (facingY != 0.0))
    {
        group.mFacingX = facingX;
        group.mFacingY = facingY;
    }
    group.mLastLeaderX = leaderTile->getX();
    group.mLastLeaderY = leaderTile->getY();

    // G7: the leader decides the retreat from the hit points of the group
    double groupHp = 0.0;
    double groupMaxHp = 0.0;
    double groupX = 0.0;
    double groupY = 0.0;
    for(Creature* member : present)
    {
        groupHp += member->getHP();
        groupMaxHp += member->getMaxHp();
        groupX += static_cast<double>(member->getPositionTile()->getX());
        groupY += static_cast<double>(member->getPositionTile()->getY());
    }
    groupX /= static_cast<double>(present.size());
    groupY /= static_cast<double>(present.size());

    if(group.mRetreating)
    {
        group.mRetreatSeconds += secondsPerTurn();
        Tile* gathering = mGameMap.getTile(group.mRetreatX, group.mRetreatY);
        uint32_t arrived = 0;
        for(Creature* member : present)
        {
            if((gathering != nullptr) && isAtGatheringTile(*member, *gathering))
                ++arrived;
        }
        if((gathering == nullptr) || CombatGroupRules::retreatFinished(arrived, static_cast<uint32_t>(present.size()),
            group.mRetreatSeconds, groupConfig("GroupRetreatMaxSeconds")))
        {
            group.mRetreating = false;
            group.mRetreatSeconds = 0.0;
            group.mRetreatCooldown = groupConfig("GroupRetreatCooldownSeconds");
            OD_LOG_INF("Combat group " + std::to_string(group.mId) + " gathered again after its retreat");
        }
    }
    else if(group.mRetreatCooldown > 0.0)
    {
        group.mRetreatCooldown = std::max(0.0, group.mRetreatCooldown - secondsPerTurn());
    }
    else if(CombatGroupRules::shouldRetreat(groupHp, groupMaxHp, !enemies.empty(), groupConfig("GroupRetreatHealthShare")))
    {
        int32_t retreatX = 0;
        int32_t retreatY = 0;
        // A raid group retreats towards the Moreya gate (Q20.3); a keeper group behind a door or to an own room
        const bool found = (group.mIsRaid && mGameMap.getRaid().hasRaid()) ?
            findRaidRetreatTile(*leader, retreatX, retreatY) :
            findRetreatTile(group, *leader, groupX, groupY, enemyX, enemyY, retreatX, retreatY);
        if(found)
        {
            group.mRetreating = true;
            group.mRetreatX = retreatX;
            group.mRetreatY = retreatY;
            group.mRetreatSeconds = 0.0;
            group.mTarget.clear();
            OD_LOG_INF("Combat group " + std::to_string(group.mId) + " retreats to " + std::to_string(retreatX) + ","
                + std::to_string(retreatY));
        }
        else
        {
            // Without a door and an own room the group stays; the search waits for the cooldown
            group.mRetreatCooldown = groupConfig("GroupRetreatCooldownSeconds");
            OD_LOG_INF("Combat group " + std::to_string(group.mId) + " finds no place to retreat to");
        }
    }

    // G6: the places of the formation behind the leader
    if(!group.mRetreating)
    {
        std::vector<CombatGroupRules::FormationMember> formationMembers;
        for(Creature* member : present)
        {
            if(member == leader)
                continue;

            CombatGroupRules::FormationMember formationMember;
            formationMember.mName = member->getName();
            formationMember.mRole = getRole(*member);
            formationMembers.push_back(formationMember);
        }

        const double rowWidth = groupConfig("GroupFormationRowWidth");
        const double spacing = groupConfig("GroupFormationRowSpacing");
        const std::vector<CombatGroupRules::FormationPlace> places = CombatGroupRules::formationPlaces(formationMembers,
            static_cast<uint32_t>(std::max(1.0, rowWidth)));
        for(const CombatGroupRules::FormationPlace& place : places)
        {
            double x = 0.0;
            double y = 0.0;
            CombatGroupRules::placePosition(static_cast<double>(leaderTile->getX()),
                static_cast<double>(leaderTile->getY()), group.mFacingX, group.mFacingY, place, spacing, x, y);
            Tile* placeTile = findStandingTile(x, y);
            if(placeTile == nullptr)
                placeTile = leaderTile;

            mPlaces[place.mName] = std::make_pair(placeTile->getX(), placeTile->getY());
        }
    }

    // G5: the enemy tanks draw the aggro of the members that they hit or that stand next to them
    const int32_t adjacentTiles = static_cast<int32_t>(groupConfig("GroupAggroAdjacentTiles"));
    std::vector<Creature*> enemyTanks;
    for(Creature* creature : creatures)
    {
        if(!creature->isAlive() || creature->isKo() || !creature->getIsOnMap() ||
           (creature->getPositionTile() == nullptr) || !areEnemies(*leader, *creature))
            continue;

        if(getRole(*creature) == CombatGroupRules::Role::tank)
            enemyTanks.push_back(creature);
    }
    for(Creature* member : present)
    {
        std::string attackingTank;
        std::map<std::string, GroupAggroEntry>::const_iterator aggro = mAggro.find(member->getName());
        if(aggro != mAggro.end())
        {
            std::map<std::string, Creature*>::const_iterator tank = byName.find(aggro->second.mTank);
            if((tank != byName.end()) && tank->second->isAlive() && !tank->second->isKo() &&
               tank->second->getIsOnMap() && areEnemies(*member, *tank->second))
                attackingTank = aggro->second.mTank;
        }

        std::vector<CombatGroupRules::AggroCandidate> nearTanks;
        for(Creature* tank : enemyTanks)
        {
            if(!areEnemies(*member, *tank))
                continue;

            CombatGroupRules::AggroCandidate candidate;
            candidate.mName = tank->getName();
            candidate.mDistance = tileDistance(*member->getPositionTile(), *tank->getPositionTile());
            nearTanks.push_back(candidate);
        }

        const std::string aggroTank = CombatGroupRules::chooseAggroTank(attackingTank, nearTanks, adjacentTiles);
        if(!aggroTank.empty())
            mAggroTargets[member->getName()] = aggroTank;
    }
}

//! \brief Tries the gathering tiles behind the own doors (nearest to the group first), then the own rooms; only tiles
//! away from the enemy that the leader can reach count.
bool CombatGroupManager::findRetreatTile(const CombatGroup& group, Creature& leader, double groupX, double groupY,
    double enemyX, double enemyY, int32_t& x, int32_t& y) const
{
    Tile* leaderTile = leader.getPositionTile();
    if(leaderTile == nullptr)
        return false;

    const int32_t groupToEnemy = squaredDistance(groupX, groupY, enemyX, enemyY);

    // Behind a door: the neighbour tile of a door tile that lies furthest from the enemy
    std::vector<CombatGroupRules::RetreatOption> doorOptions;
    for(Trap* trap : mGameMap.getTraps())
    {
        if(!trap->isDoor() || (trap->getSeat() == nullptr) || (trap->getSeat()->getId() != group.mSeatId))
            continue;

        const std::vector<Tile*> doorTiles = trap->getCoveredTiles();
        for(Tile* doorTile : doorTiles)
        {
            Tile* behind = nullptr;
            int32_t behindDistance = -1;
            for(Tile* neighbor : doorTile->getAllNeighbors())
            {
                if(neighbor->isFullTile() || (neighbor->getCoveringTrap() == trap))
                    continue;

                const int32_t distance = squaredDistance(static_cast<double>(neighbor->getX()),
                    static_cast<double>(neighbor->getY()), enemyX, enemyY);
                if(distance > behindDistance)
                {
                    behind = neighbor;
                    behindDistance = distance;
                }
            }
            if(behind == nullptr)
                continue;

            CombatGroupRules::RetreatOption option;
            option.mX = behind->getX();
            option.mY = behind->getY();
            option.mSquaredDistanceToGroup = squaredDistance(static_cast<double>(option.mX),
                static_cast<double>(option.mY), groupX, groupY);
            option.mSquaredDistanceToEnemy = behindDistance;
            doorOptions.push_back(option);
        }
    }

    const std::vector<size_t> doorOrder = CombatGroupRules::orderRetreatOptions(doorOptions, groupToEnemy);
    for(size_t index : doorOrder)
    {
        Tile* tile = mGameMap.getTile(doorOptions[index].mX, doorOptions[index].mY);
        if((tile != nullptr) && mGameMap.pathExists(&leader, leaderTile, tile))
        {
            x = doorOptions[index].mX;
            y = doorOptions[index].mY;
            return true;
        }
    }

    // Fallback: the nearest own room away from the enemy
    std::vector<CombatGroupRules::RetreatOption> roomOptions;
    for(Room* room : mGameMap.getRooms())
    {
        if((room->getSeat() == nullptr) || (room->getSeat()->getId() != group.mSeatId) || (room->numCoveredTiles() == 0))
            continue;

        Tile* roomTile = room->getCentralTile();
        if((roomTile == nullptr) || roomTile->isFullTile())
            roomTile = room->getCoveredTile(0);
        if(roomTile == nullptr)
            continue;

        CombatGroupRules::RetreatOption option;
        option.mX = roomTile->getX();
        option.mY = roomTile->getY();
        option.mSquaredDistanceToGroup = squaredDistance(static_cast<double>(option.mX), static_cast<double>(option.mY),
            groupX, groupY);
        option.mSquaredDistanceToEnemy = squaredDistance(static_cast<double>(option.mX), static_cast<double>(option.mY),
            enemyX, enemyY);
        roomOptions.push_back(option);
    }

    const std::vector<size_t> roomOrder = CombatGroupRules::orderRetreatOptions(roomOptions, groupToEnemy);
    for(size_t index : roomOrder)
    {
        Tile* tile = mGameMap.getTile(roomOptions[index].mX, roomOptions[index].mY);
        if((tile != nullptr) && mGameMap.pathExists(&leader, leaderTile, tile))
        {
            x = roomOptions[index].mX;
            y = roomOptions[index].mY;
            return true;
        }
    }

    return false;
}

//! \brief The gathering tile of a raid group's retreat: the gate tile, or a tile next to it that is no wall; only
//! when the leader can reach it.
bool CombatGroupManager::findRaidRetreatTile(Creature& leader, int32_t& x, int32_t& y) const
{
    Tile* leaderTile = leader.getPositionTile();
    Tile* gateTile = mGameMap.getRaid().getGateTile();
    if((leaderTile == nullptr) || (gateTile == nullptr))
        return false;

    Tile* gathering = findStandingTile(static_cast<double>(gateTile->getX()), static_cast<double>(gateTile->getY()));
    if((gathering == nullptr) || !mGameMap.pathExists(&leader, leaderTile, gathering))
        return false;

    x = gathering->getX();
    y = gathering->getY();
    return true;
}

//! \brief The tile under the position when it is no wall, else a neighbour that is no wall.
Tile* CombatGroupManager::findStandingTile(double x, double y) const
{
    Tile* tile = mGameMap.getTile(static_cast<int>(std::lround(x)), static_cast<int>(std::lround(y)));
    if(tile == nullptr)
        return nullptr;

    if(!tile->isFullTile())
        return tile;

    for(Tile* neighbor : tile->getAllNeighbors())
    {
        if(!neighbor->isFullTile())
            return neighbor;
    }
    return nullptr;
}

//! \brief Remembers the enemy tank that hit a member (the hit itself was already dealt).
void CombatGroupManager::notifyAttacked(Creature& victim, Creature& attacker)
{
    if(mMemberGroup.empty() || (&victim == &attacker) || !isGroupMember(victim.getName()))
        return;

    if(!areEnemies(victim, attacker) || (getRole(attacker) != CombatGroupRules::Role::tank))
        return;

    GroupAggroEntry& entry = mAggro[victim.getName()];
    entry.mTank = attacker.getName();
    entry.mTurnsLeft = static_cast<int64_t>(std::ceil(groupConfig("GroupAggroMemorySeconds") * ODApplication::turnsPerSecond));
}

//! \brief The aggro tank first (G5), else the shared target (G4); only a living, attackable enemy.
GameEntity* CombatGroupManager::getFightTarget(Creature& creature) const
{
    if(mMemberGroup.empty())
        return nullptr;

    const CombatGroup* group = getGroupOf(creature.getName());
    if((group == nullptr) || group->mRetreating)
        return nullptr;

    std::string targetName = group->mTarget;
    std::map<std::string, std::string>::const_iterator aggro = mAggroTargets.find(creature.getName());
    if(aggro != mAggroTargets.end())
        targetName = aggro->second;

    if(targetName.empty())
        return nullptr;

    Creature* target = mGameMap.getCreature(targetName);
    if((target == nullptr) || !target->isAlive() || target->isKo() || !target->getIsOnMap() ||
       !areEnemies(creature, *target))
        return nullptr;

    Tile* targetTile = target->getPositionTile();
    if((targetTile == nullptr) || !target->isAttackable(targetTile, creature.getSeat()))
        return nullptr;

    return target;
}

//! \brief True while the group of the creature retreats.
bool CombatGroupManager::isRetreating(const Creature& creature) const
{
    const CombatGroup* group = getGroupOf(creature.getName());
    return (group != nullptr) && group->mRetreating;
}

//! \brief Every member of a group that does not retreat keeps its place, except the leader of a raid group.
bool CombatGroupManager::shouldKeepFormation(const Creature& creature) const
{
    const CombatGroup* group = getGroupOf(creature.getName());
    if((group == nullptr) || group->mRetreating)
        return false;

    return !(group->mIsRaid && (group->mLeader == creature.getName()));
}

//! \brief The tile of the place computed at the last update, nullptr for the leader.
Tile* CombatGroupManager::getFormationTile(const Creature& creature) const
{
    std::map<std::string, std::pair<int32_t, int32_t> >::const_iterator it = mPlaces.find(creature.getName());
    if(it == mPlaces.end())
        return nullptr;

    return mGameMap.getTile(it->second.first, it->second.second);
}

//! \brief The gathering tile of the retreat of the creature's group.
Tile* CombatGroupManager::getRetreatTile(const Creature& creature) const
{
    const CombatGroup* group = getGroupOf(creature.getName());
    if((group == nullptr) || !group->mRetreating)
        return nullptr;

    return mGameMap.getTile(group->mRetreatX, group->mRetreatY);
}

//! \brief Compares the distance to the place with GroupFormationTolerance.
bool CombatGroupManager::isAtFormationPlace(const Creature& creature, const Tile& place) const
{
    Tile* tile = creature.getPositionTile();
    if(tile == nullptr)
        return false;

    return static_cast<double>(tileDistance(*tile, place)) <= groupConfig("GroupFormationTolerance");
}

//! \brief Compares the distance to the gathering tile with GroupGatherRadius.
bool CombatGroupManager::isAtGatheringTile(const Creature& creature, const Tile& gathering) const
{
    Tile* tile = creature.getPositionTile();
    if(tile == nullptr)
        return false;

    return static_cast<double>(tileDistance(*tile, gathering)) <= groupConfig("GroupGatherRadius");
}

//! \brief The line formats of the section, one per kind of line.
std::string CombatGroupManager::getStreamFormat()
{
    return "RaidGroup RaidGroupId LeaderName | RaidMember CreatureName RaidGroupId Template | NextGroupId Id | "
        "Group Id IsRaid SeatId RaidGroupId Leader Target FacingX FacingY LastLeaderX LastLeaderY Retreating RetreatX "
        "RetreatY RetreatSeconds RetreatCooldown NbMembers Member... | Aggro CreatureName TankName TurnsLeft";
}

//! \brief Writes the raid registry, and in a saved game the groups and the aggro, as tab separated lines.
void CombatGroupManager::exportToStream(std::ostream& os, bool isGameSave) const
{
    if(isEmpty())
        return;

    // The numbers are written with all their digits, so that a saved game continues exactly
    const std::streamsize oldPrecision = os.precision(17);
    os << "\n[CombatGroups]\n";
    os << "# " << getStreamFormat() << "\n";
    for(std::map<uint32_t, std::string>::const_iterator it = mRaidLeaders.begin(); it != mRaidLeaders.end(); ++it)
        os << "RaidGroup\t" << it->first << "\t" << nameOrDash(it->second) << "\n";

    for(std::map<std::string, RaidMemberEntry>::const_iterator it = mRaidMembers.begin(); it != mRaidMembers.end(); ++it)
        os << "RaidMember\t" << it->first << "\t" << it->second.mRaidGroupId << "\t" << nameOrDash(it->second.mTemplate) << "\n";

    if(isGameSave)
    {
        os << "NextGroupId\t" << mNextGroupId << "\n";
        for(const CombatGroup& group : mGroups)
        {
            os << "Group\t" << group.mId << "\t" << (group.mIsRaid ? 1 : 0) << "\t" << group.mSeatId << "\t"
                << group.mRaidGroupId << "\t" << nameOrDash(group.mLeader) << "\t" << nameOrDash(group.mTarget) << "\t"
                << group.mFacingX << "\t" << group.mFacingY << "\t" << group.mLastLeaderX << "\t" << group.mLastLeaderY
                << "\t" << (group.mRetreating ? 1 : 0) << "\t" << group.mRetreatX << "\t" << group.mRetreatY << "\t"
                << group.mRetreatSeconds << "\t" << group.mRetreatCooldown << "\t" << group.mMembers.size();
            for(const std::string& member : group.mMembers)
                os << "\t" << member;
            os << "\n";
        }

        for(std::map<std::string, GroupAggroEntry>::const_iterator it = mAggro.begin(); it != mAggro.end(); ++it)
            os << "Aggro\t" << it->first << "\t" << it->second.mTank << "\t" << it->second.mTurnsLeft << "\n";
    }

    os << "[/CombatGroups]\n";
    os.precision(oldPrecision);
}

//! \brief Reads the lines written by exportToStream; an unknown or broken line refuses the section.
bool CombatGroupManager::importFromStream(std::istream& is)
{
    std::string token;
    while(is >> token)
    {
        if(token == "[/CombatGroups]")
        {
            rebuildMemberIndex();
            return true;
        }

        std::string rest;
        std::getline(is, rest);
        std::stringstream line(rest);
        if(token == "RaidGroup")
        {
            uint32_t raidGroupId = 0;
            std::string leader;
            if(!(line >> raidGroupId >> leader) || (raidGroupId == 0))
            {
                OD_LOG_ERR("Invalid RaidGroup line=" + rest);
                return false;
            }
            if(!dashToEmpty(leader).empty())
                mRaidLeaders[raidGroupId] = leader;
            continue;
        }

        if(token == "RaidMember")
        {
            std::string name;
            uint32_t raidGroupId = 0;
            std::string templateName;
            if(!(line >> name >> raidGroupId >> templateName) || (raidGroupId == 0))
            {
                OD_LOG_ERR("Invalid RaidMember line=" + rest);
                return false;
            }
            RaidMemberEntry& entry = mRaidMembers[name];
            entry.mRaidGroupId = raidGroupId;
            entry.mTemplate = dashToEmpty(templateName);
            continue;
        }

        if(token == "NextGroupId")
        {
            uint32_t nextId = 0;
            if(!(line >> nextId))
            {
                OD_LOG_ERR("Invalid NextGroupId line=" + rest);
                return false;
            }
            mNextGroupId = std::max(mNextGroupId, nextId);
            continue;
        }

        if(token == "Group")
        {
            CombatGroup group;
            int32_t isRaid = 0;
            int32_t retreating = 0;
            uint32_t nbMembers = 0;
            std::string leader;
            std::string target;
            if(!(line >> group.mId >> isRaid >> group.mSeatId >> group.mRaidGroupId >> leader >> target >> group.mFacingX
                >> group.mFacingY >> group.mLastLeaderX >> group.mLastLeaderY >> retreating >> group.mRetreatX
                >> group.mRetreatY >> group.mRetreatSeconds >> group.mRetreatCooldown >> nbMembers))
            {
                OD_LOG_ERR("Invalid Group line=" + rest);
                return false;
            }
            for(uint32_t i = 0; i < nbMembers; ++i)
            {
                std::string member;
                if(!(line >> member))
                {
                    OD_LOG_ERR("Group line with too few members=" + rest);
                    return false;
                }
                group.mMembers.push_back(member);
            }
            group.mIsRaid = (isRaid != 0);
            group.mRetreating = (retreating != 0);
            group.mLeader = dashToEmpty(leader);
            group.mTarget = dashToEmpty(target);
            if(group.mId >= mNextGroupId)
                mNextGroupId = group.mId + 1;
            mGroups.push_back(group);
            continue;
        }

        if(token == "Aggro")
        {
            std::string name;
            GroupAggroEntry entry;
            if(!(line >> name >> entry.mTank >> entry.mTurnsLeft))
            {
                OD_LOG_ERR("Invalid Aggro line=" + rest);
                return false;
            }
            mAggro[name] = entry;
            continue;
        }

        OD_LOG_ERR("Unknown line in [CombatGroups]: " + token + rest);
        return false;
    }

    OD_LOG_ERR("Missing [/CombatGroups]");
    return false;
}
