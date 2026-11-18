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

#ifndef ITEMTOOLTIPPLACEMENT_H
#define ITEMTOOLTIPPLACEMENT_H

#include <algorithm>

//! \brief Where the tooltip of an item goes on the screen (plan INGAME-QS-11 K11). Without dependencies, so that it can
//! be tested without the game (test_ItemTooltipPlacement.cpp).
//!
//! The tooltip goes to the right of and below the hand cursor: its left edge right of the hand and of the item, its top
//! edge just below the tip of the cursor. If it does not fit below, it stays right of the cursor and moves up just
//! enough to fit on the screen. It is never put left of the cursor; only when it does not fit right of the cursor
//! (an item at the right edge of the screen) it moves left as far as needed to stay on the screen, and then goes below
//! the item, or above it when there is no room below, so it never covers the item it describes.
namespace ItemTooltipPlacement
{
//! \brief A rectangle in screen pixels, left/top inclusive, right/bottom the far edges.
struct Box
{
    Box() : mLeft(0.0f), mTop(0.0f), mRight(0.0f), mBottom(0.0f) {}
    Box(float left, float top, float right, float bottom) : mLeft(left), mTop(top), mRight(right), mBottom(bottom) {}

    float mLeft;
    float mTop;
    float mRight;
    float mBottom;
};

//! \brief True when the two rectangles share an area (touching edges do not count).
inline bool overlaps(const Box& a, const Box& b)
{
    return a.mLeft < b.mRight && b.mLeft < a.mRight && a.mTop < b.mBottom && b.mTop < a.mBottom;
}

//! \brief Top left corner of the tooltip.
//! \param cursorX, cursorY The tip of the cursor (the point the mouse is at).
//! \param hand The picture of the hand cursor on the screen; a box of no size at the cursor without a hand picture.
//! \param item The item the tooltip describes (its slot or cell) on the screen.
//! \param width, height The size of the tooltip.
//! \param screenWidth, screenHeight The size of the screen.
//! \param gap The space between the tooltip and the hand, the cursor and the item.
//! \return The box of the tooltip, always on the screen when the tooltip is not larger than the screen.
inline Box place(float cursorX, float cursorY, const Box& hand, const Box& item, float width, float height,
    float screenWidth, float screenHeight, float gap)
{
    // Right of the hand and of the item, below the tip of the cursor
    float x = std::max(std::max(hand.mRight, item.mRight), cursorX) + gap;
    float y = cursorY + gap;
    // Not enough room below: up just enough, still right of the cursor
    if(y + height > screenHeight)
        y = screenHeight - height;
    // Not enough room right of the cursor: left only as far as needed, then away from the item vertically
    if(x + width > screenWidth)
    {
        x = screenWidth - width;
        Box box(x, y, x + width, y + height);
        if(overlaps(box, item))
        {
            const float below = std::max(item.mBottom, cursorY) + gap;
            const float above = item.mTop - gap - height;
            if(below + height <= screenHeight)
                y = below;
            else if(above >= 0.0f)
                y = above;
        }
    }
    x = std::max(0.0f, std::min(x, screenWidth - width));
    y = std::max(0.0f, std::min(y, screenHeight - height));
    return Box(x, y, x + width, y + height);
}
}

#endif // ITEMTOOLTIPPLACEMENT_H
