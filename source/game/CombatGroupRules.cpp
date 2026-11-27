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

#include "game/CombatGroupRules.h"

#include <algorithm>
#include <cmath>

namespace CombatGroupRules
{
namespace
{
//! \brief True when the word is one of the words of the list (compared exactly).
bool contains(const std::vector<std::string>& words, const std::string& word)
{
    return std::find(words.begin(), words.end(), word) != words.end();
}

//! \brief Priority of a target for the shared target: 0 for a healer, 1 for every other role.
int32_t targetPriority(Role role)
{
    return (role == Role::healer) ? 0 : 1;
}

//! \brief True when the first target candidate is better than the second: higher priority, then nearer to the
//! leader, then the first name.
bool isBetterTarget(const TargetCandidate& first, const TargetCandidate& second)
{
    if(targetPriority(first.mRole) != targetPriority(second.mRole))
        return targetPriority(first.mRole) < targetPriority(second.mRole);
    if(first.mSquaredDistance != second.mSquaredDistance)
        return first.mSquaredDistance < second.mSquaredDistance;
    return first.mName < second.mName;
}

//! \brief True when the first leader candidate leads before the second: higher level, then more experience, then the
//! first name.
bool leadsBefore(const LeaderCandidate& first, const LeaderCandidate& second)
{
    if(first.mLevel != second.mLevel)
        return first.mLevel > second.mLevel;
    if(first.mExperience != second.mExperience)
        return first.mExperience > second.mExperience;
    return first.mName < second.mName;
}

//! \brief Sorts formation members by their names.
bool nameBefore(const FormationMember& first, const FormationMember& second)
{
    return first.mName < second.mName;
}
}

//! \brief The roles from the front of the formation to its back.
std::vector<Role> formationOrder()
{
    std::vector<Role> order;
    order.push_back(Role::tank);
    order.push_back(Role::melee);
    order.push_back(Role::supporter);
    order.push_back(Role::ranged);
    order.push_back(Role::healer);
    return order;
}

//! \brief Returns the stable name of a role for the log and the save.
const char* roleName(Role role)
{
    switch(role)
    {
        case Role::tank:
            return "tank";
        case Role::melee:
            return "melee";
        case Role::supporter:
            return "supporter";
        case Role::ranged:
            return "ranged";
        case Role::healer:
            return "healer";
    }
    return "melee";
}

//! \brief Maps the skill group of a creature to its role (tank, healer, supporter and ranged groups, else melee).
Role roleOf(const RoleSettings& settings, const std::string& skillGroup)
{
    if(contains(settings.mTankSkillGroups, skillGroup))
        return Role::tank;
    if(contains(settings.mHealerSkillGroups, skillGroup))
        return Role::healer;
    if(contains(settings.mSupporterSkillGroups, skillGroup))
        return Role::supporter;
    if(contains(settings.mRangedSkillGroups, skillGroup))
        return Role::ranged;

    return Role::melee;
}

//! \brief Picks the named leader while he is a candidate, else the best candidate by level and experience.
int32_t chooseLeader(const std::vector<LeaderCandidate>& candidates, const std::string& namedLeader)
{
    if(!namedLeader.empty())
    {
        for(size_t i = 0; i < candidates.size(); ++i)
        {
            if(candidates[i].mName == namedLeader)
                return static_cast<int32_t>(i);
        }
    }

    int32_t best = -1;
    for(size_t i = 0; i < candidates.size(); ++i)
    {
        if((best < 0) || leadsBefore(candidates[i], candidates[static_cast<size_t>(best)]))
            best = static_cast<int32_t>(i);
    }
    return best;
}

//! \brief Picks the healers first, then the nearest enemy; keeps the current target while it is as good in priority.
int32_t chooseSharedTarget(const std::vector<TargetCandidate>& candidates, const std::string& currentTarget)
{
    int32_t best = -1;
    int32_t current = -1;
    for(size_t i = 0; i < candidates.size(); ++i)
    {
        if(candidates[i].mName == currentTarget)
            current = static_cast<int32_t>(i);
        if((best < 0) || isBetterTarget(candidates[i], candidates[static_cast<size_t>(best)]))
            best = static_cast<int32_t>(i);
    }

    if((current >= 0) && (best >= 0) &&
       (targetPriority(candidates[static_cast<size_t>(current)].mRole) ==
        targetPriority(candidates[static_cast<size_t>(best)].mRole)))
        return current;

    return best;
}

//! \brief The tank that hit the member first, else the nearest enemy tank next to the member.
std::string chooseAggroTank(const std::string& attackingTank, const std::vector<AggroCandidate>& nearTanks,
    int32_t adjacentTiles)
{
    if(!attackingTank.empty())
        return attackingTank;

    const AggroCandidate* best = nullptr;
    for(const AggroCandidate& candidate : nearTanks)
    {
        if(candidate.mDistance > adjacentTiles)
            continue;
        if((best == nullptr) || (candidate.mDistance < best->mDistance) ||
           ((candidate.mDistance == best->mDistance) && (candidate.mName < best->mName)))
            best = &candidate;
    }

    if(best == nullptr)
        return std::string();

    return best->mName;
}

//! \brief Puts the roles one behind the other, each role in rows of rowWidth places centred behind the leader.
std::vector<FormationPlace> formationPlaces(const std::vector<FormationMember>& members, uint32_t rowWidth)
{
    std::vector<FormationPlace> places;
    if(rowWidth == 0)
        rowWidth = 1;

    uint32_t nextRow = 1;
    const std::vector<Role> order = formationOrder();
    for(Role role : order)
    {
        std::vector<FormationMember> ofRole;
        for(const FormationMember& member : members)
        {
            if(member.mRole == role)
                ofRole.push_back(member);
        }
        if(ofRole.empty())
            continue;

        std::sort(ofRole.begin(), ofRole.end(), nameBefore);
        for(size_t start = 0; start < ofRole.size(); start += rowWidth)
        {
            const size_t inRow = std::min(static_cast<size_t>(rowWidth), ofRole.size() - start);
            for(size_t i = 0; i < inRow; ++i)
            {
                FormationPlace place;
                place.mName = ofRole[start + i].mName;
                place.mRow = nextRow;
                place.mSide = static_cast<double>(i) - static_cast<double>(inRow - 1) / 2.0;
                places.push_back(place);
            }
            ++nextRow;
        }
    }
    return places;
}

//! \brief Converts a formation place into map coordinates behind the leader.
void placePosition(double leaderX, double leaderY, double facingX, double facingY, const FormationPlace& place,
    double spacing, double& x, double& y)
{
    double length = std::sqrt(facingX * facingX + facingY * facingY);
    if(length <= 0.0)
    {
        facingX = 1.0;
        facingY = 0.0;
        length = 1.0;
    }
    const double forwardX = facingX / length;
    const double forwardY = facingY / length;
    // The side axis points to the left of the walking direction
    const double sideX = -forwardY;
    const double sideY = forwardX;
    const double back = static_cast<double>(place.mRow) * spacing;
    const double side = place.mSide * spacing;
    x = leaderX - forwardX * back + sideX * side;
    y = leaderY - forwardY * back + sideY * side;
}

//! \brief The retreat condition of the leader: enemy in sight and the group's hit points below the share.
bool shouldRetreat(double groupHp, double groupMaxHp, bool enemyInSight, double retreatHealthShare)
{
    if(!enemyInSight || (groupMaxHp <= 0.0))
        return false;

    return (groupHp / groupMaxHp) < retreatHealthShare;
}

//! \brief Keeps the options away from the enemy and sorts them by their distance to the group.
std::vector<size_t> orderRetreatOptions(const std::vector<RetreatOption>& options, int32_t groupToEnemySquared)
{
    std::vector<size_t> order;
    for(size_t i = 0; i < options.size(); ++i)
    {
        if(options[i].mSquaredDistanceToEnemy <= groupToEnemySquared)
            continue;

        std::vector<size_t>::iterator position = order.begin();
        while(position != order.end())
        {
            const RetreatOption& other = options[*position];
            const RetreatOption& option = options[i];
            if((option.mSquaredDistanceToGroup < other.mSquaredDistanceToGroup) ||
               ((option.mSquaredDistanceToGroup == other.mSquaredDistanceToGroup) &&
                ((option.mX < other.mX) || ((option.mX == other.mX) && (option.mY < other.mY)))))
                break;
            ++position;
        }
        order.insert(position, i);
    }
    return order;
}

//! \brief The retreat ends when every present member arrived or the maximum time has passed.
bool retreatFinished(uint32_t arrivedMembers, uint32_t presentMembers, double elapsedSeconds, double maxSeconds)
{
    if(elapsedSeconds >= maxSeconds)
        return true;

    return arrivedMembers >= presentMembers;
}
}
