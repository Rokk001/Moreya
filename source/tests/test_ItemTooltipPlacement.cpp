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

#include "render/ItemTooltipPlacement.h"

#define BOOST_TEST_MODULE ItemTooltipPlacement
#include "BoostTestTargetConfig.h"

namespace
{
//! Size of the tooltip and of the gap used by the cases (pixels)
const float TOOLTIP_WIDTH = 300.0f;
const float TOOLTIP_HEIGHT = 220.0f;
const float GAP = 4.0f;

//! \brief The hand picture of the cursor: 40 x 48 pixels from the tip of the cursor to the right and down.
ItemTooltipPlacement::Box handAt(float x, float y)
{
    return ItemTooltipPlacement::Box(x, y, x + 40.0f, y + 48.0f);
}

//! \brief A slot of 60 x 60 pixels around the cursor, the cursor 10 pixels right of its left edge.
ItemTooltipPlacement::Box slotAt(float x, float y)
{
    return ItemTooltipPlacement::Box(x - 10.0f, y - 30.0f, x + 50.0f, y + 30.0f);
}

//! \brief True when the box lies completely on a screen of the given size.
bool onScreen(const ItemTooltipPlacement::Box& box, float width, float height)
{
    return box.mLeft >= 0.0f && box.mTop >= 0.0f && box.mRight <= width && box.mBottom <= height;
}
}

//! Checks that the tooltip lies right of and below the cursor, right of the hand and of the slot, where it fits
BOOST_AUTO_TEST_CASE(test_tooltip_goes_right_and_below_when_it_fits)
{
    const ItemTooltipPlacement::Box box = ItemTooltipPlacement::place(200.0f, 150.0f, handAt(200.0f, 150.0f),
        slotAt(200.0f, 150.0f), TOOLTIP_WIDTH, TOOLTIP_HEIGHT, 1920.0f, 1200.0f, GAP);
    BOOST_CHECK_EQUAL(box.mLeft, 254.0f);
    BOOST_CHECK_EQUAL(box.mTop, 154.0f);
    BOOST_CHECK(!ItemTooltipPlacement::overlaps(box, slotAt(200.0f, 150.0f)));
    BOOST_CHECK(onScreen(box, 1920.0f, 1200.0f));
}

//! Checks that a tooltip without room below stays right of the cursor and moves up just enough
BOOST_AUTO_TEST_CASE(test_tooltip_moves_up_just_enough)
{
    const ItemTooltipPlacement::Box box = ItemTooltipPlacement::place(300.0f, 1100.0f, handAt(300.0f, 1100.0f),
        slotAt(300.0f, 1100.0f), TOOLTIP_WIDTH, TOOLTIP_HEIGHT, 1920.0f, 1200.0f, GAP);
    BOOST_CHECK_EQUAL(box.mBottom, 1200.0f);
    BOOST_CHECK(box.mLeft > 300.0f);
    BOOST_CHECK(!ItemTooltipPlacement::overlaps(box, slotAt(300.0f, 1100.0f)));
}

//! Checks that a tooltip without room right of the cursor moves left only as far as needed and leaves the slot free
BOOST_AUTO_TEST_CASE(test_tooltip_moves_left_only_as_needed)
{
    const ItemTooltipPlacement::Box box = ItemTooltipPlacement::place(1800.0f, 200.0f, handAt(1800.0f, 200.0f),
        slotAt(1800.0f, 200.0f), TOOLTIP_WIDTH, TOOLTIP_HEIGHT, 1920.0f, 1200.0f, GAP);
    BOOST_CHECK_EQUAL(box.mRight, 1920.0f);
    BOOST_CHECK(box.mTop >= 230.0f);
    BOOST_CHECK(!ItemTooltipPlacement::overlaps(box, slotAt(1800.0f, 200.0f)));
    BOOST_CHECK(onScreen(box, 1920.0f, 1200.0f));
}

//! Checks that in the lower right corner the tooltip goes above the slot instead of covering it
BOOST_AUTO_TEST_CASE(test_tooltip_in_the_corner_goes_above_the_slot)
{
    const ItemTooltipPlacement::Box box = ItemTooltipPlacement::place(600.0f, 440.0f, handAt(600.0f, 440.0f),
        slotAt(600.0f, 440.0f), TOOLTIP_WIDTH, TOOLTIP_HEIGHT, 640.0f, 480.0f, GAP);
    BOOST_CHECK(onScreen(box, 640.0f, 480.0f));
    BOOST_CHECK(!ItemTooltipPlacement::overlaps(box, slotAt(600.0f, 440.0f)));
    BOOST_CHECK(box.mBottom <= 410.0f);
}

//! Checks that in every quadrant of both screens the tooltip is on the screen, never left of the cursor where it fits
//! right of it, and never over the slot
BOOST_AUTO_TEST_CASE(test_tooltip_in_all_quadrants)
{
    const float screens[2][2] = {{640.0f, 480.0f}, {1920.0f, 1200.0f}};
    for(const float* screen : screens)
    {
        const float xs[] = {screen[0] * 0.2f, screen[0] * 0.8f};
        const float ys[] = {screen[1] * 0.2f, screen[1] * 0.8f};
        for(float x : xs)
        {
            for(float y : ys)
            {
                const float width = 200.0f;
                const float height = 150.0f;
                const ItemTooltipPlacement::Box box = ItemTooltipPlacement::place(x, y, handAt(x, y), slotAt(x, y),
                    width, height, screen[0], screen[1], GAP);
                BOOST_CHECK(onScreen(box, screen[0], screen[1]));
                BOOST_CHECK(!ItemTooltipPlacement::overlaps(box, slotAt(x, y)));
                if(x + 50.0f + GAP + width <= screen[0])
                    BOOST_CHECK(box.mLeft >= x);
                if(y + GAP + height <= screen[1])
                    BOOST_CHECK(box.mTop >= y);
            }
        }
    }
}
