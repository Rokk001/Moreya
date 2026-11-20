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

#ifndef COMBATGROUPRULES_H
#define COMBATGROUPRULES_H

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

//! \brief The decisions of the group combat: the role of a member, the leader, the shared target, the aggro of the
//! enemy tanks, the places of the formation and the choice of the retreat. The engine side (CombatGroupManager)
//! collects the facts of the game and applies the results. This file only depends on the standard library so that
//! its rules can be checked on their own.
namespace CombatGroupRules
{
//! \brief The role of a group member. The order of the values is the order of the formation from the front: tanks,
//! melee fighters, ranged fighters and casters, healers.
enum class Role
{
    tank = 0,
    melee = 1,
    ranged = 2,
    healer = 3
};

//! \brief The roles in the order of the formation from the front.
std::vector<Role> formationOrder();

//! \brief Returns the name of a role ("tank", "melee", "ranged", "healer").
const char* roleName(Role role);

//! \brief The config lists the role rule reads (GroupTankPaths, GroupHealerPaths, GroupRangedSkillGroups).
struct RoleSettings
{
    //! \brief Primary paths of the templates that make a member a tank.
    std::vector<std::string> mTankPaths;
    //! \brief Primary paths of the templates that make a member a healer.
    std::vector<std::string> mHealerPaths;
    //! \brief Skill groups whose other templates (and whose creatures without a template) are ranged.
    std::vector<std::string> mRangedSkillGroups;
};

//! \brief The role of a creature from the skill template it follows: a template with a tank path as primary path is
//! a tank, one with a healer path a healer; any other template of a ranged skill group is ranged, any other template
//! melee. A creature without a template is ranged in a ranged skill group, otherwise melee.
//! \param skillGroup The skill group of the creature type ("none" or empty when it has none).
//! \param hasTemplate True when the creature follows a template.
//! \param primaryPath The primary path of that template (ignored without a template).
Role roleOf(const RoleSettings& settings, const std::string& skillGroup, bool hasTemplate,
    const std::string& primaryPath);

//! \brief A member that can lead a group.
struct LeaderCandidate
{
    //! \brief Creates a candidate of level 0 without experience.
    LeaderCandidate() :
        mLevel(0),
        mExperience(0.0)
    {}

    std::string mName;
    uint32_t mLevel;
    //! \brief Experience gathered towards the next level.
    double mExperience;
};

//! \brief Chooses the leader of a group: the named leader while he is a candidate (the named leader of a raid group),
//! otherwise the candidate with the highest level, on equal level the one with more experience, on equal experience
//! the first name in alphabetical order.
//! \return The index of the leader in the candidates, -1 when there is none.
int32_t chooseLeader(const std::vector<LeaderCandidate>& candidates, const std::string& namedLeader);

//! \brief An enemy creature the leader can choose as the shared target.
struct TargetCandidate
{
    //! \brief Creates a melee candidate at distance 0.
    TargetCandidate() :
        mRole(Role::melee),
        mSquaredDistance(0)
    {}

    std::string mName;
    Role mRole;
    //! \brief Squared distance in tiles from the leader.
    int32_t mSquaredDistance;
};

//! \brief Chooses the shared target of a group: the enemy healers first, then any other enemy; among equals the one
//! nearest to the leader, then the first name. The current target is kept while it is a candidate of the same
//! priority as the best one, so that the group does not switch between equal targets.
//! \return The index of the target in the candidates, -1 when there is none.
int32_t chooseSharedTarget(const std::vector<TargetCandidate>& candidates, const std::string& currentTarget);

//! \brief An enemy tank near a member.
struct AggroCandidate
{
    //! \brief Creates a candidate at distance 0.
    AggroCandidate() :
        mDistance(0)
    {}

    std::string mName;
    //! \brief Distance in tiles from the member (the largest of the x and y distance).
    int32_t mDistance;
};

//! \brief The aggro of the enemy tanks: a member that was hit by an enemy tank attacks that tank; otherwise a member
//! that stands next to enemy tanks (at most adjacentTiles away) attacks the nearest of them, then the first name.
//! \param attackingTank The living enemy tank that hit the member within the aggro memory, empty for none.
//! \param nearTanks The living enemy tanks around the member.
//! \return The name of the tank the member attacks, empty when the member follows the shared target.
std::string chooseAggroTank(const std::string& attackingTank, const std::vector<AggroCandidate>& nearTanks,
    int32_t adjacentTiles);

//! \brief A member that gets a place in the formation (the leader gets none, he stands in front).
struct FormationMember
{
    //! \brief Creates a melee member.
    FormationMember() :
        mRole(Role::melee)
    {}

    std::string mName;
    Role mRole;
};

//! \brief The place of a member in the formation behind the leader.
struct FormationPlace
{
    //! \brief Creates the place in the first row in the middle.
    FormationPlace() :
        mRow(1),
        mSide(0.0)
    {}

    std::string mName;
    //! \brief Row behind the leader, 1 is the first row.
    uint32_t mRow;
    //! \brief Place in the row counted from its middle in places (negative: left of the walking direction).
    double mSide;
};

//! \brief The places of the formation: the roles in the formation order, each role starting a new row behind the
//! rows of the roles before it; inside a role the members in the order of their names, rowWidth places per row,
//! every row centred behind the leader.
std::vector<FormationPlace> formationPlaces(const std::vector<FormationMember>& members, uint32_t rowWidth);

//! \brief The position of a formation place: rows go back against the facing of the group, places go sideways.
//! \param facingX The facing of the group (need not be normalised; a zero facing counts as facing +x).
void placePosition(double leaderX, double leaderY, double facingX, double facingY, const FormationPlace& place,
    double spacing, double& x, double& y);

//! \brief True when the leader orders the retreat: an enemy is in sight and the hit points of the group are below the
//! configured share of its maximum hit points.
bool shouldRetreat(double groupHp, double groupMaxHp, bool enemyInSight, double retreatHealthShare);

//! \brief A gathering tile the group could retreat to.
struct RetreatOption
{
    //! \brief Creates an option at tile 0,0.
    RetreatOption() :
        mX(0),
        mY(0),
        mSquaredDistanceToGroup(0),
        mSquaredDistanceToEnemy(0)
    {}

    int32_t mX;
    int32_t mY;
    //! \brief Squared distance in tiles from the centre of the group.
    int32_t mSquaredDistanceToGroup;
    //! \brief Squared distance in tiles from the centre of the enemies in sight.
    int32_t mSquaredDistanceToEnemy;
};

//! \brief The order in which the options are tried: only options that lie further away from the enemy than the
//! group itself (away from the enemy), the nearest to the group first, then the smaller x, then the smaller y.
//! \param groupToEnemySquared Squared distance in tiles between the centre of the group and that of the enemies.
//! \return The indices of the options to try.
std::vector<size_t> orderRetreatOptions(const std::vector<RetreatOption>& options, int32_t groupToEnemySquared);

//! \brief True when the retreat is over: every present member has arrived at the gathering tile or the retreat lasted
//! the configured maximum.
bool retreatFinished(uint32_t arrivedMembers, uint32_t presentMembers, double elapsedSeconds, double maxSeconds);
}

#endif // COMBATGROUPRULES_H
