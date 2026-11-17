/*
 *  Copyright (C) 2026  OpenDungeons Team
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

#ifndef CREATURESKILLTREEVIEW_H
#define CREATURESKILLTREEVIEW_H

#include "creatureskill/CreatureSkillTree.h"

#include <cstdint>
#include <string>
#include <vector>

//! \brief What the creature skill tree window shows of one creature: the four paths of its type as columns with
//! tier 1 to 3, the tier 4 skill on top, the rank, the unlock state, the highlighted template path and the tooltip
//! of every skill. Like CreatureSkillTree it only depends on the standard library so that it can be tested alone.
namespace CreatureSkillTree
{
//! \brief The rule values the view needs (SkillRanksPerSkill and the unlock values of global.cfg).
struct ViewRules
{
    //! \brief Creates rules with the values of today's global.cfg.
    ViewRules() :
        mMaxRank(5),
        mTier2UnlockRanks(1),
        mTier3UnlockRanks(2),
        mTier4MinSpent(20)
    {}
    //! \brief Highest rank of a tier 1 to 3 skill (SkillRanksPerSkill).
    uint32_t mMaxRank;
    //! \brief Ranks in tier 1 of a path that unlock tier 2 (SkillTier2UnlockRanks).
    uint32_t mTier2UnlockRanks;
    //! \brief Ranks in tier 2 of a path that unlock tier 3 (SkillTier3UnlockRanks).
    uint32_t mTier3UnlockRanks;
    //! \brief Points spent in the paths that unlock the tier 4 skill (SkillTier4MinSpent).
    uint32_t mTier4MinSpent;
};

//! \brief One skill of the tree as the window shows it.
struct ViewNode
{
    //! \brief Creates an empty node.
    ViewNode() :
        mRank(0),
        mMaxRank(0),
        mUnlocked(false)
    {}
    //! \brief Skill id (the image name in the imageset CreatureSkillIcons), empty when the path has no such tier.
    std::string mId;
    //! \brief Current rank of the creature.
    uint32_t mRank;
    //! \brief Highest rank (SkillRanksPerSkill, 1 for the tier 4 skill).
    uint32_t mMaxRank;
    //! \brief False while the unlock rule of the tier is not met (shown dark).
    bool mUnlocked;
    //! \brief Text of the rank bar, "<rank>/<max>".
    std::string mBarText;
    //! \brief The four tooltip lines: name, effect, mana and cooldown.
    std::vector<std::string> mTooltip;
};

//! \brief One path of the tree: a column with tier 1 to 3.
struct ViewColumn
{
    //! \brief Creates an empty column.
    ViewColumn() :
        mHighlighted(false)
    {}
    //! \brief Path name (column title).
    std::string mPath;
    //! \brief True for the primary path of the creature's template.
    bool mHighlighted;
    //! \brief Tier 1, 2 and 3 of the path (always three entries).
    std::vector<ViewNode> mTiers;
};

//! \brief The whole tree of one creature.
struct TreeView
{
    //! \brief Creates an empty tree.
    TreeView() :
        mHasTierFour(false)
    {}
    //! \brief The paths: the three group paths in config order, then the family path. Empty when the type has no
    //! skill group (it has no tree).
    std::vector<ViewColumn> mColumns;
    //! \brief True when the type has a tier 4 skill.
    bool mHasTierFour;
    //! \brief The tier 4 skill of the type (shown above the columns).
    ViewNode mTierFour;
};

//! \brief Builds what the window shows for a creature of the given type with the given build.
TreeView buildTreeView(const SkillTreeConfig& config, const TypeInfo& type, const SkillBuild& build,
    const ViewRules& rules);

//! \brief Returns the readable text of a skill kind for the "Effect:" tooltip line, the kind token itself when it
//! is unknown.
std::string kindText(const std::string& kind);

//! \brief Returns the value part of the "Effect:" line: the value as written, "%" after it for kinds ending in
//! "%", and "push p, stun s" for a WHIRLWIND value "p/s".
std::string effectValueText(const std::string& kind, const std::string& value);

//! \brief Returns the four tooltip lines of a tier 1 to 3 skill at the given rank (rank 0 uses the rank 1 values).
std::vector<std::string> skillTooltip(const SkillDef& skill, uint32_t rank);

//! \brief Returns the four tooltip lines of a tier 4 skill.
std::vector<std::string> tierFourTooltip(const TierFourDef& skill);
}

#endif // CREATURESKILLTREEVIEW_H
