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

// Header-only Boost.Test, see test_DungeonHeartTier.cpp.
// OVERRIDE_BOOST_TEST_INCLUDED_WARNING
#define BOOST_TEST_MODULE LevelPreview
#include <boost/test/included/unit_test.hpp>

#include "gamemap/LevelPreview.h"
#include "entities/Tile.h"

#include "boost/filesystem.hpp"

#include <cstdlib>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace
{
//! \brief An RGB colour of one picture pixel in bytes.
struct PixelColour
{
    int red;
    int green;
    int blue;
};

//! \brief The seat colours the tests use: colour id "3" is a pink red, "4" a blue, "0" (rogue) a grey.
Ogre::ColourValue fixtureSeatColour(const std::string& colourId)
{
    if(colourId == "3")
        return Ogre::ColourValue(0.8f, 0.2f, 0.4f);
    if(colourId == "4")
        return Ogre::ColourValue(0.2f, 0.4f, 0.8f);
    return Ogre::ColourValue(0.6f, 0.6f, 0.6f);
}

//! \brief The seat colours used for the official levels: a different colour for every colour id 0 to 8.
Ogre::ColourValue levelSeatColour(const std::string& colourId)
{
    const int id = std::atoi(colourId.c_str());
    return Ogre::ColourValue(0.1f + 0.1f * static_cast<float>(id % 9), 0.9f - 0.1f * static_cast<float>(id % 9), 0.5f);
}

//! \brief Reads the colour of the picture pixel in the middle of the tile x, y (the top row is the north edge).
PixelColour tilePixel(const std::vector<uint8_t>& pixels, uint32_t width, uint32_t height, int mapSizeX,
    int mapSizeY, int x, int y)
{
    const uint32_t column = static_cast<uint32_t>((2 * x + 1) * static_cast<int>(width) / (2 * mapSizeX));
    const uint32_t row = height - 1 - static_cast<uint32_t>((2 * y + 1) * static_cast<int>(height) / (2 * mapSizeY));
    const size_t index = (static_cast<size_t>(row) * width + column) * 4;
    PixelColour colour = {pixels[index], pixels[index + 1], pixels[index + 2]};
    return colour;
}

//! \brief True if every channel of the colour is within one step of the expected bytes.
bool isColour(const PixelColour& colour, int red, int green, int blue)
{
    return std::abs(colour.red - red) <= 1 && std::abs(colour.green - green) <= 1 && std::abs(colour.blue - blue) <= 1;
}

//! \brief Converts a colour channel (0 to 1) into the byte the picture holds.
int channelByte(float channel)
{
    return static_cast<int>(channel * 255.0f + 0.5f);
}

//! \brief A small level: one row of terrain, one row of owned and room tiles, one row of special cases. The seat
//! colour ids (3 and 4) differ from the seat ids (1 and 2). Unlisted tiles are solid dirt.
const std::string FIXTURE_LEVEL =
    "OpenDungeons_Version:0.7.4\n"
    "[Info]\n"
    "Name\tFixture\n"
    "[/Info]\n"
    "[Seats]\n"
    "[Seat]\n"
    "seatId\t1\n"
    "teamId\t1\n"
    "player\tHuman\n"
    "faction\tKeeper\n"
    "colorId\t3\n"
    "[/Seat]\n"
    "[Seat]\n"
    "seatId\t2\n"
    "teamId\t2\n"
    "colorId\t4\n"
    "[/Seat]\n"
    "[/Seats]\n"
    "[Goals]\n"
    "[/Goals]\n"
    "[Tiles]\n"
    "# Map Size\n"
    "6 # MapSizeX\n"
    "4 # MapSizeY\n"
    "# posX\tposY\ttype\tfullness\tseatId(optional)\n"
    "0\t0\t3\t100\n"
    "1\t0\t2\t100\n"
    "2\t0\t6\t100\n"
    "3\t0\t4\n"
    "4\t0\t5\n"
    "5\t0\t7\n"
    "0\t1\t1\t0\n"
    "1\t1\t1\t0\t1\n"
    "2\t1\t1\t100\t1\n"
    "3\t1\t1\t0\t1\n"
    "4\t1\t1\t0\t0\n"
    "5\t1\t2\t0\t2\n"
    "0\t2\t2\t100\t2\n"
    "1\t2\t1\t0\t9\n"
    "2\t2\t3\t0\n"
    "[/Tiles]\n"
    "[Rooms]\n"
    "# typeRoom\tname\tseatId\tnumTiles\n"
    "[Room]\n"
    "1\tDungeonTemple1\t1\t1\n"
    "3\t1\n"
    "[/Room]\n"
    "[Room]\n"
    "4\tPortal1\t0\t1\n"
    "4\t1\n"
    "0\n"
    "[/Room]\n"
    "[Room]\n"
    "2\tDormitory1\t1\t1\n"
    "0\t1\n"
    "[/Room]\n"
    "[/Rooms]\n"
    "[Traps]\n"
    "[/Traps]\n";

//! \brief The words of a level file, without comments.
std::vector<std::string> levelWords(const std::string& fileName)
{
    std::ifstream file(fileName.c_str());
    std::vector<std::string> words;
    std::string line;
    while(std::getline(file, line))
    {
        std::istringstream stream(line.substr(0, line.find('#')));
        std::string word;
        while(stream >> word)
            words.push_back(word);
    }
    return words;
}

//! \brief A dungeon temple of a level file: its seat and its tiles.
struct TempleRoom
{
    int seatId;
    std::vector<std::pair<int, int>> tiles;
};

//! \brief Reads the dungeon temples (room type 1) out of the [Rooms] section of a level file.
std::vector<TempleRoom> readTemples(const std::string& fileName)
{
    const std::vector<std::string> words = levelWords(fileName);
    std::vector<TempleRoom> temples;
    bool inRooms = false;
    for(size_t i = 0; i < words.size(); ++i)
    {
        if(words[i] == "[Rooms]")
            inRooms = true;
        else if(words[i] == "[/Rooms]")
            break;
        if(!inRooms || words[i] != "[Room]" || i + 4 >= words.size() || words[i + 1] != "1")
            continue;
        TempleRoom temple;
        temple.seatId = std::atoi(words[i + 3].c_str());
        const int count = std::atoi(words[i + 4].c_str());
        for(int n = 0; n < count && i + 6 + 2 * n < words.size(); ++n)
            temple.tiles.push_back(std::make_pair(std::atoi(words[i + 5 + 2 * n].c_str()),
                std::atoi(words[i + 6 + 2 * n].c_str())));
        temples.push_back(temple);
    }
    return temples;
}

//! \brief Every level file of a folder of OD_LEVELS_DIR.
std::vector<std::string> levelFiles(const std::string& folder)
{
    std::vector<std::string> files;
    boost::filesystem::path path(std::string(OD_LEVELS_DIR) + "/" + folder);
    for(boost::filesystem::directory_iterator it(path); it != boost::filesystem::directory_iterator(); ++it)
    {
        if(it->path().extension().string() == ".level")
            files.push_back(folder + "/" + it->path().filename().string());
    }
    return files;
}
}

//! Checks that every tile of a level is drawn in the minimap colour of its look and owner: terrain, owned ground,
//! the dungeon temple, rooms of the rogue seat, gold seams with a seat, unknown seats and unlisted solid dirt, with the
//! north edge at the top and whole pixels per tile.
BOOST_AUTO_TEST_CASE(test_fixture_level_colours)
{
    LevelPreview preview;
    std::istringstream level(FIXTURE_LEVEL);
    BOOST_REQUIRE(preview.loadFromStream(level));
    BOOST_CHECK_EQUAL(preview.getMapSizeX(), 6);
    BOOST_CHECK_EQUAL(preview.getMapSizeY(), 4);

    // The looks as the game computes them at the start of the level
    BOOST_CHECK(preview.getTileVisual(3, 1) == TileVisual::dungeonTempleRoom);
    BOOST_CHECK(preview.getTileVisual(4, 1) == TileVisual::portalRoom);
    BOOST_CHECK(preview.getTileVisual(1, 1) == TileVisual::claimedGround);
    BOOST_CHECK(preview.getTileVisual(2, 1) == TileVisual::claimedFull);
    // A room on a tile the level does not claim does not change the tile
    BOOST_CHECK(preview.getTileVisual(0, 1) == TileVisual::dirtGround);
    BOOST_CHECK(preview.getTileVisual(5, 0) == TileVisual::manaWellGround);
    BOOST_CHECK(preview.getTileVisual(0, 2) == TileVisual::goldFull);
    BOOST_CHECK(preview.getTileVisual(5, 3) == TileVisual::dirtFull);
    BOOST_CHECK_EQUAL(preview.getTileSeatId(5, 1), 2);
    BOOST_CHECK_EQUAL(preview.getTileSeatId(0, 2), LevelPreview::NO_SEAT);
    BOOST_CHECK_EQUAL(preview.getTileSeatId(1, 2), LevelPreview::NO_SEAT);
    BOOST_CHECK_EQUAL(preview.getSeatColourId(1), "3");
    BOOST_CHECK_EQUAL(preview.getSeatColourId(0), "0");

    uint32_t width = 0;
    uint32_t height = 0;
    preview.getPictureSize(width, height);
    // 86 pixels per tile: the smallest whole number that makes the 6 tiles at least 512 pixels wide
    BOOST_CHECK_EQUAL(width, 516u);
    BOOST_CHECK_EQUAL(height, 344u);

    std::vector<uint8_t> pixels;
    LevelPreview::SeatColourFunction seatColour = fixtureSeatColour;
    preview.drawPicture(width, height, seatColour, pixels);
    BOOST_REQUIRE_EQUAL(pixels.size(), static_cast<size_t>(width) * height * 4);
    for(size_t alpha = 3; alpha < pixels.size(); alpha += 4)
        BOOST_REQUIRE_EQUAL(static_cast<int>(pixels[alpha]), 255);

    const int sx = preview.getMapSizeX();
    const int sy = preview.getMapSizeY();
    // Terrain row (y = 0, the bottom row of the picture)
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 0, 0), 51, 26, 10));    // solid rock
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 1, 0), 255, 230, 0));   // gold seam
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 2, 0), 161, 0, 209));   // gem seam
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 3, 0), 33, 54, 122));   // water
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 4, 0), 184, 77, 38));   // lava
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 5, 0), 46, 94, 199));   // mana well
    // Owned row: the seat colour of colour id 3 (204, 51, 102), darker on its walls, lighter on its temple
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 0, 1), 120, 69, 26));   // dug earth
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 1, 1), 204, 51, 102));  // claimed ground
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 2, 1), 92, 23, 46));    // claimed wall
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 3, 1), 222, 122, 156)); // dungeon temple
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 4, 1), 255, 0, 0));     // rogue room
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 5, 1), 51, 102, 204));  // gold ground of seat 2
    // Special row: a seat on a gold seam and an unknown seat are ignored, rock ground is earth
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 0, 2), 255, 230, 0));
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 1, 2), 120, 69, 26));
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 2, 2), 120, 69, 26));
    // Unlisted tiles are solid dirt
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 5, 3), 92, 46, 13));
    BOOST_CHECK(isColour(tilePixel(pixels, width, height, sx, sy, 0, 3), 92, 46, 13));

    // The top left pixel is the north west corner (unlisted dirt), the bottom left one the south west rock
    PixelColour topLeft = {pixels[0], pixels[1], pixels[2]};
    BOOST_CHECK(isColour(topLeft, 92, 46, 13));
    const size_t bottomLeftIndex = static_cast<size_t>(height - 1) * width * 4;
    PixelColour bottomLeft = {pixels[bottomLeftIndex], pixels[bottomLeftIndex + 1], pixels[bottomLeftIndex + 2]};
    BOOST_CHECK(isColour(bottomLeft, 51, 26, 10));
}

//! Checks that a map larger than the picture keeps its aspect ratio and that a pixel shared by several tiles shows
//! the tile with the highest minimap priority (a gold seam wins against solid dirt), as on the in-game minimap.
BOOST_AUTO_TEST_CASE(test_big_map_shares_pixels_by_priority)
{
    LevelPreview preview;
    std::istringstream level(
        "OpenDungeons_Version:0.7.4\n[Seats]\n[/Seats]\n[Tiles]\n2048\n4\n1\t0\t2\t100\n[/Tiles]\n[Rooms]\n[/Rooms]\n");
    BOOST_REQUIRE(preview.loadFromStream(level));
    uint32_t width = 0;
    uint32_t height = 0;
    preview.getPictureSize(width, height);
    BOOST_CHECK_EQUAL(width, 1024u);
    BOOST_CHECK_EQUAL(height, 2u);

    std::vector<uint8_t> pixels;
    LevelPreview::SeatColourFunction seatColour = fixtureSeatColour;
    preview.drawPicture(width, height, seatColour, pixels);
    // The bottom row holds the tiles y = 0 and 1; its first pixel covers the tiles x = 0 and 1
    const size_t bottomFirst = static_cast<size_t>(width) * 4;
    PixelColour shared = {pixels[bottomFirst], pixels[bottomFirst + 1], pixels[bottomFirst + 2]};
    BOOST_CHECK(isColour(shared, 255, 230, 0));
    PixelColour next = {pixels[bottomFirst + 4], pixels[bottomFirst + 5], pixels[bottomFirst + 6]};
    BOOST_CHECK(isColour(next, 92, 46, 13));
    PixelColour top = {pixels[0], pixels[1], pixels[2]};
    BOOST_CHECK(isColour(top, 92, 46, 13));
}

//! Checks that a level whose map cannot be read gives no preview: a missing file, no [Tiles] section, a map size of
//! zero, a tile outside of the map, an unknown tile type and a tile line without its fullness.
BOOST_AUTO_TEST_CASE(test_unreadable_levels_have_no_preview)
{
    LevelPreview preview;
    BOOST_CHECK(!preview.loadFromFile(std::string(OD_LEVELS_DIR) + "/skirmish/NoSuchLevel.level"));

    const char* const broken[] = {
        "OpenDungeons_Version:0.7.4\n[Seats]\n[/Seats]\n",
        "OpenDungeons_Version:0.7.4\n[Tiles]\n0\n4\n[/Tiles]\n",
        "OpenDungeons_Version:0.7.4\n[Tiles]\n4\n4\n4\t0\t1\t0\n[/Tiles]\n",
        "OpenDungeons_Version:0.7.4\n[Tiles]\n4\n4\n0\t0\t9\t0\n[/Tiles]\n",
        "OpenDungeons_Version:0.7.4\n[Tiles]\n4\n4\n0\t0\t1\n[/Tiles]\n"
    };
    for(const char* text : broken)
    {
        std::istringstream level(text);
        BOOST_CHECK_MESSAGE(!preview.loadFromStream(level), text);
    }
}

//! Checks every official skirmish and multiplayer level, which the skirmish level selection lists: the level gives
//! a preview with the shape of its map, every dungeon temple of the level shows on its own tiles in the temple
//! colour of its seat (rooms of the rogue seat in red), and two levels give the same picture only when they share
//! the same map: the same tiles and owners, with rooms that differ at most in a type of the same colour (fixed list
//! of 9 pairs, counted once on this branch).
BOOST_AUTO_TEST_CASE(test_every_official_level_shows_its_own_map)
{
    std::vector<std::string> files = levelFiles("skirmish");
    const std::vector<std::string> multiplayer = levelFiles("multiplayer");
    files.insert(files.end(), multiplayer.begin(), multiplayer.end());
    // 40 skirmish and 22 multiplayer levels were counted on this branch
    BOOST_REQUIRE_GE(files.size(), 62u);

    std::set<std::pair<std::string, std::string>> sameMap;
    sameMap.insert(std::make_pair("multiplayer/TestMultiplayerSmallAlliance.level",
        "multiplayer/TestMultiplayerSmallFreeForAll.level"));
    sameMap.insert(std::make_pair("skirmish/Sandbox.level", "skirmish/SandboxEverything.level"));
    sameMap.insert(std::make_pair("skirmish/TestCleaning.level", "skirmish/TestTavern.level"));
    sameMap.insert(std::make_pair("skirmish/TestCleaning.level", "skirmish/TestTavernNone.level"));
    sameMap.insert(std::make_pair("skirmish/TestTavern.level", "skirmish/TestTavernNone.level"));
    sameMap.insert(std::make_pair("skirmish/TestLegacy.level", "skirmish/TestLegacyNoScripts.level"));
    sameMap.insert(std::make_pair("skirmish/TestLevelScripting.level", "skirmish/TestRegionScripting.level"));
    sameMap.insert(std::make_pair("skirmish/TestLevelScripting.level", "skirmish/TestSingleplayerSmallEmpty.level"));
    sameMap.insert(std::make_pair("skirmish/TestRegionScripting.level", "skirmish/TestSingleplayerSmallEmpty.level"));

    LevelPreview::SeatColourFunction seatColour = levelSeatColour;
    std::map<std::string, std::vector<uint8_t>> pictures;
    for(const std::string& file : files)
    {
        const std::string path = std::string(OD_LEVELS_DIR) + "/" + file;
        LevelPreview preview;
        BOOST_REQUIRE_MESSAGE(preview.loadFromFile(path), file);
        uint32_t width = 0;
        uint32_t height = 0;
        preview.getPictureSize(width, height);
        BOOST_REQUIRE_MESSAGE(width > 0 && height > 0, file);
        // Whole pixels per tile for every official map (none is larger than the picture)
        BOOST_CHECK_MESSAGE(width % static_cast<uint32_t>(preview.getMapSizeX()) == 0 &&
            height % static_cast<uint32_t>(preview.getMapSizeY()) == 0 &&
            width / static_cast<uint32_t>(preview.getMapSizeX()) == height / static_cast<uint32_t>(preview.getMapSizeY()),
            file);

        std::vector<uint8_t> pixels;
        preview.drawPicture(width, height, seatColour, pixels);

        const std::vector<TempleRoom> temples = readTemples(path);
        BOOST_CHECK_MESSAGE(!temples.empty(), file + " has no dungeon temple");
        for(const TempleRoom& temple : temples)
        {
            int expectedRed = 255;
            int expectedGreen = 0;
            int expectedBlue = 0;
            if(temple.seatId != 0)
            {
                const Ogre::ColourValue seat = levelSeatColour(preview.getSeatColourId(temple.seatId));
                expectedRed = channelByte(seat.r * 0.65f + 0.35f);
                expectedGreen = channelByte(seat.g * 0.65f + 0.35f);
                expectedBlue = channelByte(seat.b * 0.65f + 0.35f);
            }
            int shown = 0;
            for(const std::pair<int, int>& tile : temple.tiles)
            {
                if(isColour(tilePixel(pixels, width, height, preview.getMapSizeX(), preview.getMapSizeY(),
                    tile.first, tile.second), expectedRed, expectedGreen, expectedBlue))
                    ++shown;
            }
            BOOST_CHECK_MESSAGE(shown > 0, file + ": the temple of seat " + std::to_string(temple.seatId) +
                " is not shown");
        }
        pictures[file] = pixels;
    }

    for(std::map<std::string, std::vector<uint8_t>>::const_iterator first = pictures.begin(); first != pictures.end();
        ++first)
    {
        std::map<std::string, std::vector<uint8_t>>::const_iterator second = first;
        for(++second; second != pictures.end(); ++second)
        {
            const bool shared = sameMap.count(std::make_pair(first->first, second->first)) > 0 ||
                sameMap.count(std::make_pair(second->first, first->first)) > 0;
            BOOST_CHECK_MESSAGE((first->second == second->second) == shared,
                first->first + " and " + second->first + (shared ? " share a map but show different pictures" : " show the same picture"));
        }
    }
}
