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

#include "creatureskill/CreatureSkillTreeView.h"

#include <cctype>
#include <map>
#include <sstream>

namespace CreatureSkillTree
{
namespace
{
//! \brief Returns the text in lower case.
std::string lowerText(const std::string& text)
{
    std::string result = text;
    for(std::string::iterator it = result.begin(); it != result.end(); ++it)
        *it = static_cast<char>(std::tolower(static_cast<unsigned char>(*it)));
    return result;
}

//! \brief Returns a number as the shortest usual text (5, 12.5).
std::string numberText(double value)
{
    std::ostringstream ss;
    ss << value;
    return ss.str();
}

//! \brief Returns "<rank>/<max>".
std::string barText(uint32_t rank, uint32_t maxRank)
{
    std::ostringstream ss;
    ss << rank << "/" << maxRank;
    return ss.str();
}

//! \brief Returns the "Cooldown:" line of a cooldown cell.
std::string cooldownLine(const SkillNumber& cooldown)
{
    if(!cooldown.mSet)
        return "Cooldown: none";
    return "Cooldown: " + numberText(cooldown.mValue) + " turns";
}

//! \brief Fills a node of a tier 1 to 3 skill: rank, bar text, unlock state and tooltip.
ViewNode pathNode(const SkillTreeConfig& config, const SkillBuild& build, const std::string& owner,
    const std::string& path, uint32_t tier, const ViewRules& rules)
{
    ViewNode node;
    node.mId = config.findPathSkill(owner, path, tier);
    node.mMaxRank = rules.mMaxRank;
    if(node.mId.empty())
        return node;

    node.mRank = getRank(build, node.mId);
    node.mBarText = barText(node.mRank, node.mMaxRank);
    if(tier <= 1)
        node.mUnlocked = true;
    else
    {
        const std::string previous = config.findPathSkill(owner, path, tier - 1);
        const uint32_t needed = (tier == 2) ? rules.mTier2UnlockRanks : rules.mTier3UnlockRanks;
        node.mUnlocked = !previous.empty() && (getRank(build, previous) >= needed);
    }
    // A rank the creature has is always shown as unlocked
    node.mUnlocked = node.mUnlocked || (node.mRank > 0);
    const SkillDef* skill = config.findSkill(node.mId);
    if(skill != nullptr)
        node.mTooltip = skillTooltip(*skill, node.mRank);
    return node;
}
}

std::string kindText(const std::string& kind)
{
    static const std::map<std::string, std::string> TEXTS = {
        {"PASSIVE_dmg%", "Damage"}, {"PASSIVE_spell%", "Spell damage"}, {"PASSIVE_alldmg%", "All damage"},
        {"PASSIVE_hp%", "Max HP"}, {"PASSIVE_crit", "Critical chance"}, {"PASSIVE_cd%", "Cooldown"},
        {"PASSIVE_avoid", "Avoid"}, {"PASSIVE_ar%", "Attack rating"}, {"PASSIVE_dr%", "Defense rating"},
        {"PASSIVE_dig%", "Digging"}, {"PASSIVE_claim%", "Claiming"}, {"PASSIVE_carry%", "Carrying"},
        {"PASSIVE_move%", "Move speed"}, {"PASSIVE_wake%", "Wakefulness"}, {"PASSIVE_manacost%", "Mana cost"},
        {"STRIKE", "Strike"}, {"HEAL_SELF", "Heal self"}, {"HEAL_ALLY", "Heal ally"}, {"HEAL_AREA", "Heal area"},
        {"BUFF_SELF_StrengthChange", "Strength (self)"}, {"BUFF_SELF_SpeedChange", "Speed (self)"},
        {"BUFF_SELF_Defense", "Defense (self)"}, {"AURA_ALLY_StrengthChange", "Strength aura (allies)"},
        {"DEBUFF_Weak", "Weaken enemy"}, {"DEBUFF_Slow", "Slow enemy"}, {"EXPLOSION", "Explosion"},
        {"HAILSTORM", "Hailstorm"}, {"GASCLOUD", "Gas cloud"}, {"GRENADE", "Grenade"},
        {"GUIDEDBOLT", "Guided bolt"}, {"WHIRLWIND", "Whirlwind"}, {"FREEZE", "Freeze"},
        {"INVISIBLE", "Invisibility"}, {"TELEPORT", "Teleport"}, {"DRAIN", "Drain"}, {"RAISEDEAD", "Raise dead"},
        {"SKELARMY", "Skeleton army"},
        {"TAUNT", "Taunt"}, {"PARRY_COUNTER", "Parry"}, {"AURA_ALLY_Defense", "Defense aura (allies)"},
        {"BUFF_ALLY_Defense", "Defense (ally)"}, {"SHIELD_ALLY", "Shield (ally)"}, {"SHIELD_AREA", "Shield (group)"},
        {"HEAL_INSTANT", "Instant heal"}, {"HOT_AREA", "Heal over time (area)"}, {"HOT_SELF", "Heal over time (self)"},
        {"CURSE_DOT", "Curse"}, {"MARK", "Mark"}, {"HOLD", "Hold"}, {"BLEED", "Bleeding"}, {"POISON", "Poison"},
        {"BURN_DOT", "Burn"}, {"DRAIN_HEAL_ALLIES", "Life drain (allies)"}, {"CHAIN_LIGHTNING", "Lightning"},
        {"FLURRY", "Flurry"}
    };
    std::map<std::string, std::string>::const_iterator it = TEXTS.find(kind);
    if(it == TEXTS.end())
        return kind;
    return it->second;
}

std::string effectValueText(const std::string& kind, const std::string& value)
{
    if(kind == "WHIRLWIND")
    {
        const std::string::size_type slash = value.find('/');
        if(slash != std::string::npos)
            return "push " + value.substr(0, slash) + ", stun " + value.substr(slash + 1);
    }
    if(kind == "FLURRY")
    {
        const std::string::size_type slash = value.find('/');
        if(slash != std::string::npos)
            return "blows " + value.substr(0, slash) + ", factor " + value.substr(slash + 1);
    }
    if(!kind.empty() && (kind[kind.size() - 1] == '%'))
        return value + "%";
    return value;
}

//! \brief The tooltip lines of a skill at a rank; the first line is its name in the chosen language.
std::vector<std::string> skillTooltip(const SkillDef& skill, uint32_t rank)
{
    // A skill without a rank shows what rank 1 would give
    const std::size_t index = (rank == 0) ? 0 : static_cast<std::size_t>(rank - 1);
    std::vector<std::string> lines;
    lines.push_back(skill.getDisplayText());
    const std::string value = (index < skill.mValues.size()) ? skill.mValues[index] :
        (skill.mValues.empty() ? std::string() : skill.mValues.back());
    lines.push_back("Effect: " + kindText(skill.mKind) + " " + effectValueText(skill.mKind, value));
    if(skill.mMana.empty())
        lines.push_back("Mana: none");
    else
        lines.push_back("Mana: " + numberText((index < skill.mMana.size()) ? skill.mMana[index] : skill.mMana.back()));
    lines.push_back(cooldownLine(skill.mCooldown));
    return lines;
}

//! \brief The tooltip lines of a tier 4 skill; the first line is its name in the chosen language.
std::vector<std::string> tierFourTooltip(const TierFourDef& skill)
{
    std::vector<std::string> lines;
    lines.push_back(skill.getDisplayText());
    lines.push_back("Effect: " + kindText(skill.mKind) + " " + effectValueText(skill.mKind, skill.mValue));
    lines.push_back(skill.mMana.mSet ? "Mana: " + numberText(skill.mMana.mValue) : std::string("Mana: none"));
    lines.push_back(cooldownLine(skill.mCooldown));
    return lines;
}

TreeView buildTreeView(const SkillTreeConfig& config, const TypeInfo& type, const SkillBuild& build,
    const ViewRules& rules)
{
    TreeView view;
    // A type without skill group has no tree
    if(type.mGroup.empty())
        return view;

    std::string primary;
    const TemplateDef* chosen = config.findTemplate(type.mGroup, build.mTemplate);
    if(chosen != nullptr)
        primary = lowerText(chosen->mPrimary);

    const std::vector<std::string> paths = config.getPathNames(type);
    for(std::vector<std::string>::const_iterator it = paths.begin(); it != paths.end(); ++it)
    {
        ViewColumn column;
        column.mPath = *it;
        column.mHighlighted = !primary.empty() && (lowerText(*it) == primary);
        // The group paths come first; a path the group does not have is the family path
        const std::string owner = config.findPathSkill(type.mGroup, *it, 1).empty() ? type.mFamily : type.mGroup;
        for(uint32_t tier = 1; tier <= MAX_TIER; ++tier)
            column.mTiers.push_back(pathNode(config, build, owner, *it, tier, rules));
        view.mColumns.push_back(column);
    }

    const TierFourDef* tierFour = type.mTierFour.empty() ? nullptr : config.findTierFourById(type.mTierFour);
    if(tierFour != nullptr)
    {
        view.mHasTierFour = true;
        view.mTierFour.mId = type.mTierFour;
        view.mTierFour.mRank = getRank(build, type.mTierFour);
        view.mTierFour.mMaxRank = 1;
        view.mTierFour.mBarText = barText(view.mTierFour.mRank, 1);
        view.mTierFour.mUnlocked = (view.mTierFour.mRank > 0) || (spentInPaths(build, type) >= rules.mTier4MinSpent);
        view.mTierFour.mTooltip = tierFourTooltip(*tierFour);
    }
    return view;
}
}
