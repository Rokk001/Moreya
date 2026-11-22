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

#ifndef POSSESSIONBARRULES_H
#define POSSESSIONBARRULES_H

#include <cstdint>
#include <string>
#include <vector>

//! \brief The skill bar shown while the player possesses a creature (possession view A): a low iron bar at the
//! bottom centre with one slot per skill key (icon, key and recovery), and at its right end the plate that names the
//! Esc key as the way out. The server sends the slots (see Creature::sendPossessionSkillBar), GameMode draws them.
//! This file only depends on the standard library so that its rules can be checked on their own.
namespace PossessionBarRules
{
//! \brief Most slots the bar shows: 1 to 9 and 0, then Shift with the same keys.
const uint32_t MAX_SLOTS = 20;

//! \brief One slot of the bar, in the order of the skill keys.
struct Slot
{
    //! \brief Image of the slot (see iconImage).
    std::string mIcon;
    //! \brief Turns left until the skill can be used again (0 when it is ready).
    double mRemaining = 0.0;
    //! \brief Turns of the whole recovery that mRemaining counts down from.
    double mDuration = 0.0;
    //! \brief False while the creature cannot use the skill for another reason than its recovery (no mana).
    bool mUsable = true;
};

//! \brief Place and size of the bar in screen pixels.
struct Layout
{
    //! \brief Side of one square slot.
    float mSlotSize = 0.0f;
    //! \brief Space between two slots and between the slots and the edge of the bar.
    float mGap = 0.0f;
    //! \brief Left edge and top edge of the bar (slots and exit plate).
    float mLeft = 0.0f;
    float mTop = 0.0f;
    //! \brief Width of the part of the bar that holds the slots.
    float mSlotsWidth = 0.0f;
    //! \brief Width of the exit plate at the right end.
    float mPlateWidth = 0.0f;
    //! \brief Height of the bar.
    float mHeight = 0.0f;
};

//! \brief Text under the slot: "1" to "9" and "0" for the first ten slots, "S+1" to "S+0" (Shift and the key) for the
//! next ten; empty for a slot without a key.
std::string keyLabel(uint32_t slot);

//! \brief Image of a skill: the painted icon CreatureSkillIcons/<id> of a skill tree skill, for a skill of the creature
//! definition the spell icon of the same effect when there is one, otherwise the general skill icon.
//! \param treeSkillId Id of the skill tree entry the skill was made from (empty for a line of the definition).
//! \param skillName Name of the skill kind (getSkillName, for example "Explosion").
std::string iconImage(const std::string& treeSkillId, const std::string& skillName);

//! \brief Share of the recovery still to run, from 0 (ready) to 1 (just used); the slot shows it like a spell button
//! that recovers.
float recoveryShare(const Slot& slot);

//! \brief Place of the bar for the window size: slots grow with the window height and the UI scale and shrink so that
//! all slots and the plate fit into the width; the bar sits at the bottom centre.
//! \param slotCount Number of slots (0 shows only the exit plate).
//! \param width Width of the window in pixels.
//! \param height Height of the window in pixels.
//! \param layoutScale Factor from design pixels to screen pixels (display size and UI scale).
Layout computeLayout(uint32_t slotCount, float width, float height, float layoutScale);

//! \brief Left edge of a slot.
float slotLeft(const Layout& layout, uint32_t slot);
}

#endif // POSSESSIONBARRULES_H
