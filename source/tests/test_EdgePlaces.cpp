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

#include "utils/EdgePlaces.h"

#define BOOST_TEST_MODULE EdgePlaces
#include "BoostTestTargetConfig.h"

// A drag rectangle that crosses the left edge covers exactly the places left of the map, none inside it.
BOOST_AUTO_TEST_CASE(test_RectangleAcrossLeftEdge)
{
    std::vector<std::pair<int, int> > places = EdgePlaces::inRectangle(-3, 2, 2, 4, 10, 10);
    BOOST_CHECK_EQUAL(places.size(), 9u);
    for(size_t i = 0; i < places.size(); ++i)
    {
        BOOST_CHECK(places[i].first < 0);
        BOOST_CHECK(places[i].second >= 2 && places[i].second <= 4);
    }
}

// A drag across the bottom right corner covers the places beyond both edges and the corner block, in either corner order.
BOOST_AUTO_TEST_CASE(test_RectangleAcrossCorner)
{
    std::vector<std::pair<int, int> > places = EdgePlaces::inRectangle(8, 8, 11, 11, 10, 10);
    // 4x4 rectangle, of which the 2x2 block 8..9 lies inside the map
    BOOST_CHECK_EQUAL(places.size(), 12u);
    BOOST_CHECK(places == EdgePlaces::inRectangle(11, 11, 8, 8, 10, 10));
    BOOST_CHECK(std::find(places.begin(), places.end(), std::make_pair(10, 10)) != places.end());
    BOOST_CHECK(std::find(places.begin(), places.end(), std::make_pair(9, 9)) == places.end());
}

// A rectangle inside the map has no edge places, and the reach bounds a rectangle that runs far outside.
BOOST_AUTO_TEST_CASE(test_ReachIsBounded)
{
    BOOST_CHECK(EdgePlaces::inRectangle(1, 1, 5, 5, 10, 10).empty());
    std::vector<std::pair<int, int> > places = EdgePlaces::inRectangle(-1000, 0, 0, 0, 10, 10);
    BOOST_CHECK_EQUAL(places.size(), static_cast<size_t>(EdgePlaces::EDGE_PLACE_REACH));
    BOOST_CHECK(EdgePlaces::isMarkable(-EdgePlaces::EDGE_PLACE_REACH, 0, 10, 10));
    BOOST_CHECK(!EdgePlaces::isMarkable(-EdgePlaces::EDGE_PLACE_REACH - 1, 0, 10, 10));
    BOOST_CHECK(!EdgePlaces::isMarkable(3, 3, 10, 10));
    int x = -500;
    int y = 500;
    EdgePlaces::clampToReach(x, y, 10, 10);
    BOOST_CHECK(EdgePlaces::isMarkable(x, y, 10, 10));
}
