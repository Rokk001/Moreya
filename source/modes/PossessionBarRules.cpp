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

#include "modes/PossessionBarRules.h"

#include <algorithm>

namespace PossessionBarRules
{
namespace
{
//! Number of keys in one row: 1 to 9 and 0
const uint32_t KEYS_PER_ROW = 10;
//! Prefix of the keys of the second row (Shift held)
const char* const SHIFT_PREFIX = "S+";
//! Imageset of the painted skill icons, addressed by skill id
const char* const SKILL_ICON_SET = "CreatureSkillIcons/";
//! Spell icons that show a skill of a creature definition with the same effect
const char* const EXPLOSION_ICON = "OpenDungeonsIcons/CreatureExplosionButton";
//! General skill icon for every other skill of a creature definition
const char* const GENERAL_ICON = "OpenDungeonsIcons/SkillIcon";
//! Side of a slot in design pixels, and its share of the window height when that is larger
const float SLOT_DESIGN_SIZE = 56.0f;
const float SLOT_HEIGHT_SHARE = 0.065f;
//! Smallest side of a slot in pixels, so that the icon and the key stay readable at 640x480
const float SLOT_MIN_SIZE = 24.0f;
//! Gap between the slots as a share of the slot side
const float GAP_SHARE = 0.12f;
//! Width of the exit plate as a multiple of the slot side
const float PLATE_WIDTH_SLOTS = 2.4f;
//! Space between the bar and the bottom of the window as a share of the slot side
const float BOTTOM_SHARE = 0.25f;
//! Share of the window width the whole bar may take
const float MAX_WIDTH_SHARE = 0.96f;
}

std::string keyLabel(uint32_t slot)
{
    if(slot >= MAX_SLOTS)
        return std::string();

    const uint32_t key = (slot % KEYS_PER_ROW) + 1;
    const std::string digit = std::to_string(key % KEYS_PER_ROW);
    return (slot < KEYS_PER_ROW) ? digit : (SHIFT_PREFIX + digit);
}

std::string iconImage(const std::string& treeSkillId, const std::string& skillName)
{
    if(!treeSkillId.empty())
        return SKILL_ICON_SET + treeSkillId;

    if(skillName == "Explosion")
        return EXPLOSION_ICON;

    return GENERAL_ICON;
}

float recoveryShare(const Slot& slot)
{
    if((slot.mRemaining <= 0.0) || (slot.mDuration <= 0.0))
        return 0.0f;

    return static_cast<float>(std::min(1.0, slot.mRemaining / slot.mDuration));
}

Layout computeLayout(uint32_t slotCount, float width, float height, float layoutScale)
{
    const uint32_t count = std::min(slotCount, MAX_SLOTS);
    Layout layout;
    float size = std::max(SLOT_DESIGN_SIZE * layoutScale, height * SLOT_HEIGHT_SHARE);

    // Width of the bar for a slot side: the slots with their gaps, a gap, the plate and a gap
    const float units = static_cast<float>(count) * (1.0f + GAP_SHARE) + GAP_SHARE + PLATE_WIDTH_SLOTS +
        2.0f * GAP_SHARE;
    const float maxWidth = width * MAX_WIDTH_SHARE;
    if(size * units > maxWidth)
        size = maxWidth / units;
    size = std::max(size, SLOT_MIN_SIZE);

    layout.mSlotSize = size;
    layout.mGap = size * GAP_SHARE;
    layout.mSlotsWidth = static_cast<float>(count) * (size + layout.mGap) + layout.mGap;
    layout.mPlateWidth = size * PLATE_WIDTH_SLOTS;
    layout.mHeight = size + 2.0f * layout.mGap;
    const float total = layout.mSlotsWidth + layout.mGap + layout.mPlateWidth;
    layout.mLeft = std::max(0.0f, (width - total) * 0.5f);
    layout.mTop = std::max(0.0f, height - layout.mHeight - size * BOTTOM_SHARE);
    return layout;
}

float slotLeft(const Layout& layout, uint32_t slot)
{
    return layout.mLeft + layout.mGap + static_cast<float>(slot) * (layout.mSlotSize + layout.mGap);
}
}
