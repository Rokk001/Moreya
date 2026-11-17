/*!
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

#include "gamemap/LevelPreview.h"

#include "entities/Tile.h"
#include "rooms/RoomType.h"

#include <algorithm>
#include <fstream>
#include <sstream>

const int LevelPreview::NO_SEAT;
const uint32_t LevelPreview::MIN_PICTURE_SIDE;
const uint32_t LevelPreview::MAX_PICTURE_SIDE;

namespace
{
//! \brief Largest side of a map that a level may declare, as in MapHandler.
const int MAX_MAP_SIDE = 4096;

//! \brief The id and the colour id of the rogue seat, which every game map has without a [Seat] entry.
const int ROGUE_SEAT_ID = 0;
const std::string ROGUE_SEAT_COLOUR_ID = "0";

//! \brief Splits a line of a level file into its words, without the comment that starts with '#'.
std::vector<std::string> splitLevelLine(const std::string& line)
{
    std::istringstream stream(line.substr(0, line.find('#')));
    std::vector<std::string> words;
    std::string word;
    while(stream >> word)
        words.push_back(word);
    return words;
}

//! \brief Reads a whole number out of a word; false if the word has anything else than the number.
bool parseWholeNumber(const std::string& text, int& value)
{
    std::istringstream stream(text);
    stream >> value;
    if(stream.fail())
        return false;
    stream >> std::ws;
    return stream.eof();
}

//! \brief Reads a decimal number out of a word; false if the word does not start with a number.
bool parseDecimalNumber(const std::string& text, double& value)
{
    std::istringstream stream(text);
    stream >> value;
    return !stream.fail();
}

//! \brief The look of a claimed ground tile covered by a room of the given type, as Tile::computeTileVisual
//! decides it; a room type without its own look (the bridges) gives nullTileVisual there too.
TileVisual roomTileVisual(int roomType)
{
    switch(static_cast<RoomType>(roomType))
    {
        case RoomType::arena:
            return TileVisual::arenaRoom;
        case RoomType::dungeonTemple:
            return TileVisual::dungeonTempleRoom;
        case RoomType::dormitory:
            return TileVisual::dormitoryRoom;
        case RoomType::treasury:
            return TileVisual::treasuryRoom;
        case RoomType::portal:
            return TileVisual::portalRoom;
        case RoomType::workshop:
            return TileVisual::workshopRoom;
        case RoomType::trainingHall:
            return TileVisual::trainingHallRoom;
        case RoomType::library:
            return TileVisual::libraryRoom;
        case RoomType::hatchery:
            return TileVisual::hatcheryRoom;
        case RoomType::crypt:
            return TileVisual::cryptRoom;
        case RoomType::portalWave:
            return TileVisual::portalWaveRoom;
        case RoomType::prison:
            return TileVisual::prisonRoom;
        case RoomType::casino:
            return TileVisual::casinoRoom;
        case RoomType::merchant:
            return TileVisual::merchantRoom;
        case RoomType::torture:
            return TileVisual::tortureRoom;
        case RoomType::ghostRoom:
            return TileVisual::ghostRoom;
        case RoomType::infirmary:
            return TileVisual::infirmaryRoom;
        case RoomType::guardRoom:
            return TileVisual::guardRoom;
        case RoomType::temple:
            return TileVisual::templeRoom;
        case RoomType::toilet:
            return TileVisual::toiletRoom;
        case RoomType::herbGarden:
            return TileVisual::herbGardenRoom;
        case RoomType::alchemyLab:
            return TileVisual::alchemyLabRoom;
        case RoomType::tavern:
            return TileVisual::tavernRoom;
        case RoomType::spa:
            return TileVisual::spaRoom;
        default:
            return TileVisual::nullTileVisual;
    }
}

//! \brief Converts a colour channel (0 to 1) into a byte.
uint8_t channelByte(float channel)
{
    const float clamped = std::max(0.0f, std::min(1.0f, channel));
    return static_cast<uint8_t>(clamped * 255.0f + 0.5f);
}
}

//! \brief Creates an empty preview without a map.
LevelPreview::LevelPreview() :
    mMapSizeX(0),
    mMapSizeY(0)
{
}

//! \brief Reads the seats, tiles and rooms of a level file.
bool LevelPreview::loadFromFile(const std::string& fileName)
{
    std::ifstream file(fileName.c_str(), std::ifstream::in);
    if(!file.good())
        return false;
    return loadFromStream(file);
}

//! \brief Reads the seats, tiles and rooms of the text of a level file. Tiles that the file does not list are solid
//! dirt, as GameMap::createNewMap makes them; a tile line is read as Tile::loadFromLine reads it and checked as
//! MapHandler checks it; the rooms give the claimed ground tiles they cover their room look.
bool LevelPreview::loadFromStream(std::istream& stream)
{
    mMapSizeX = 0;
    mMapSizeY = 0;
    mVisuals.clear();
    mSeatIds.clear();
    mSeatColourIds.clear();
    mSeatColourIds[ROGUE_SEAT_ID] = ROGUE_SEAT_COLOUR_ID;

    enum class Section { other, seats, tiles, rooms };
    Section section = Section::other;
    int currentSeat = NO_SEAT;
    int sizeX = 0;
    int sizeY = 0;
    int sizeValuesRead = 0;
    bool tilesRead = false;
    std::vector<TileType> types;
    std::vector<bool> full;
    std::vector<int> seatIds;
    std::vector<int> roomTypes;
    std::vector<std::string> roomWords;
    std::string line;
    while(std::getline(stream, line))
    {
        const std::vector<std::string> words = splitLevelLine(line);
        if(words.empty())
            continue;

        const std::string& first = words[0];
        if(section == Section::other)
        {
            if(first == "[Seats]")
                section = Section::seats;
            else if(first == "[Tiles]" && !tilesRead)
                section = Section::tiles;
            else if(first == "[Rooms]" && tilesRead)
                section = Section::rooms;
            continue;
        }

        if(section == Section::seats)
        {
            if(first == "[/Seats]")
                section = Section::other;
            else if(first == "[Seat]")
                currentSeat = NO_SEAT;
            else if(first == "seatId")
            {
                // A seat id that is no number leaves the seat without colour, so its tiles stay unowned
                if(words.size() < 2 || !parseWholeNumber(words[1], currentSeat))
                    currentSeat = NO_SEAT;
            }
            else if(first == "colorId" && words.size() >= 2 && currentSeat != NO_SEAT)
                mSeatColourIds[currentSeat] = words[1];
            continue;
        }

        if(section == Section::rooms)
        {
            if(first == "[/Rooms]")
                break;
            roomWords.insert(roomWords.end(), words.begin(), words.end());
            continue;
        }

        // The tiles: first the map size, then one line per tile
        if(sizeValuesRead < 2)
        {
            int value = 0;
            if(!parseWholeNumber(first, value))
                return false;
            if(sizeValuesRead == 0)
                sizeX = value;
            else
                sizeY = value;
            ++sizeValuesRead;
            if(sizeValuesRead < 2)
                continue;
            if(sizeX <= 0 || sizeY <= 0 || sizeX > MAX_MAP_SIDE || sizeY > MAX_MAP_SIDE)
                return false;
            const size_t count = static_cast<size_t>(sizeX) * static_cast<size_t>(sizeY);
            types.assign(count, TileType::dirt);
            full.assign(count, true);
            seatIds.assign(count, NO_SEAT);
            roomTypes.assign(count, static_cast<int>(RoomType::nullRoomType));
            continue;
        }

        if(first == "[/Tiles]")
        {
            tilesRead = true;
            section = Section::other;
            continue;
        }

        int x = 0;
        int y = 0;
        int type = 0;
        if(words.size() < 3 || !parseWholeNumber(words[0], x) || !parseWholeNumber(words[1], y) ||
           !parseWholeNumber(words[2], type))
            return false;
        if(x < 0 || y < 0 || x >= sizeX || y >= sizeY)
            return false;
        if(type < 0 || type >= static_cast<int>(TileType::countTileType))
            return false;

        const TileType tileType = static_cast<TileType>(type);
        // Water, lava and mana wells are always ground
        double fullness = 0.0;
        const bool ignoresFullness = (tileType == TileType::water) || (tileType == TileType::lava) ||
            (tileType == TileType::manaWell);
        if(!ignoresFullness)
        {
            if(words.size() < 4 || !parseDecimalNumber(words[3], fullness))
                return false;
        }

        // A seat is set on dirt, on mana wells and on gold ground, and only if the level has that seat
        int seatId = NO_SEAT;
        const bool canHaveSeat = (tileType == TileType::dirt) || (tileType == TileType::manaWell) ||
            ((tileType == TileType::gold) && (fullness == 0.0));
        int lineSeat = NO_SEAT;
        if(canHaveSeat && words.size() >= 5 && parseWholeNumber(words[4], lineSeat) &&
           mSeatColourIds.find(lineSeat) != mSeatColourIds.end())
        {
            seatId = lineSeat;
        }

        const size_t index = static_cast<size_t>(y) * static_cast<size_t>(sizeX) + static_cast<size_t>(x);
        types[index] = tileType;
        full[index] = fullness > 0.0;
        seatIds[index] = seatId;
    }

    if(!tilesRead)
        return false;

    // The rooms: "[Room]", the room type, its name, its seat, the number of tiles, the tiles, then room data up to
    // "[/Room]"
    for(size_t i = 0; i < roomWords.size(); ++i)
    {
        if(roomWords[i] != "[Room]" || i + 4 >= roomWords.size())
            continue;
        int roomType = 0;
        int tileCount = 0;
        if(!parseWholeNumber(roomWords[i + 1], roomType) || !parseWholeNumber(roomWords[i + 4], tileCount) ||
           tileCount < 0)
            continue;
        size_t next = i + 5;
        for(int n = 0; n < tileCount && next + 1 < roomWords.size(); ++n, next += 2)
        {
            int x = 0;
            int y = 0;
            if(!parseWholeNumber(roomWords[next], x) || !parseWholeNumber(roomWords[next + 1], y))
                break;
            if(x < 0 || y < 0 || x >= sizeX || y >= sizeY)
                continue;
            roomTypes[static_cast<size_t>(y) * static_cast<size_t>(sizeX) + static_cast<size_t>(x)] = roomType;
        }
        i = next - 1;
    }

    // The look of every tile, as Tile::computeTileVisual decides it
    mMapSizeX = sizeX;
    mMapSizeY = sizeY;
    mSeatIds = seatIds;
    mVisuals.assign(types.size(), TileVisual::nullTileVisual);
    for(size_t index = 0; index < types.size(); ++index)
    {
        const bool claimed = seatIds[index] != NO_SEAT;
        const bool room = roomTypes[index] != static_cast<int>(RoomType::nullRoomType);
        TileVisual visual = TileVisual::nullTileVisual;
        switch(types[index])
        {
            case TileType::dirt:
            case TileType::gold:
                if(full[index])
                {
                    if(claimed)
                        visual = TileVisual::claimedFull;
                    else
                        visual = types[index] == TileType::dirt ? TileVisual::dirtFull : TileVisual::goldFull;
                }
                else if(claimed)
                    visual = room ? roomTileVisual(roomTypes[index]) : TileVisual::claimedGround;
                else
                    visual = types[index] == TileType::dirt ? TileVisual::dirtGround : TileVisual::goldGround;
                break;
            case TileType::rock:
                visual = full[index] ? TileVisual::rockFull : TileVisual::rockGround;
                break;
            case TileType::water:
                visual = TileVisual::waterGround;
                break;
            case TileType::lava:
                visual = TileVisual::lavaGround;
                break;
            case TileType::gem:
                visual = full[index] ? TileVisual::gemFull : TileVisual::gemGround;
                break;
            case TileType::manaWell:
                visual = claimed ? TileVisual::claimedGround : TileVisual::manaWellGround;
                break;
            default:
                visual = TileVisual::nullTileVisual;
                break;
        }
        mVisuals[index] = visual;
    }
    return true;
}

//! \brief The index of the tile at x, y in mVisuals and mSeatIds.
size_t LevelPreview::tileIndex(int x, int y) const
{
    return static_cast<size_t>(y) * static_cast<size_t>(mMapSizeX) + static_cast<size_t>(x);
}

//! \brief How the tile at x, y looks at the start of the level.
TileVisual LevelPreview::getTileVisual(int x, int y) const
{
    if(x < 0 || y < 0 || x >= mMapSizeX || y >= mMapSizeY)
        return TileVisual::nullTileVisual;
    return mVisuals[tileIndex(x, y)];
}

//! \brief The id of the seat the tile at x, y belongs to, or NO_SEAT.
int LevelPreview::getTileSeatId(int x, int y) const
{
    if(x < 0 || y < 0 || x >= mMapSizeX || y >= mMapSizeY)
        return NO_SEAT;
    return mSeatIds[tileIndex(x, y)];
}

//! \brief The colour id of a seat, or an empty text for an unknown seat.
std::string LevelPreview::getSeatColourId(int seatId) const
{
    std::map<int, std::string>::const_iterator it = mSeatColourIds.find(seatId);
    if(it == mSeatColourIds.end())
        return std::string();
    return it->second;
}

//! \brief The minimap colour of the tile at x, y in the first animation phase.
MiniMapTileColour LevelPreview::getTileColour(int x, int y, const SeatColourFunction& seatColour) const
{
    const int seatId = getTileSeatId(x, y);
    const bool hasOwner = seatId != NO_SEAT;
    const Ogre::ColourValue ownerColour = hasOwner ? seatColour(getSeatColourId(seatId)) : Ogre::ColourValue::Black;
    return MiniMapColours::terrainColour(getTileVisual(x, y), hasOwner, seatId == ROGUE_SEAT_ID, ownerColour, 0);
}

//! \brief The picture size for the loaded map, keeping the aspect ratio of the map.
void LevelPreview::getPictureSize(uint32_t& width, uint32_t& height) const
{
    width = 0;
    height = 0;
    if(mMapSizeX <= 0 || mMapSizeY <= 0)
        return;

    const uint32_t sizeX = static_cast<uint32_t>(mMapSizeX);
    const uint32_t sizeY = static_cast<uint32_t>(mMapSizeY);
    const uint32_t longest = std::max(sizeX, sizeY);
    if(longest <= MAX_PICTURE_SIDE)
    {
        // Whole pixels per tile keep the tile borders sharp
        uint32_t pixelsPerTile = std::max<uint32_t>(1, (MIN_PICTURE_SIDE + longest - 1) / longest);
        while(pixelsPerTile > 1 && longest * pixelsPerTile > MAX_PICTURE_SIDE)
            --pixelsPerTile;
        width = sizeX * pixelsPerTile;
        height = sizeY * pixelsPerTile;
        return;
    }

    width = std::max<uint32_t>(1, (sizeX * MAX_PICTURE_SIDE + longest / 2) / longest);
    height = std::max<uint32_t>(1, (sizeY * MAX_PICTURE_SIDE + longest / 2) / longest);
}

//! \brief Draws the loaded map into RGBA pixels with the north edge at the top.
void LevelPreview::drawPicture(uint32_t width, uint32_t height, const SeatColourFunction& seatColour,
    std::vector<uint8_t>& pixels) const
{
    pixels.assign(static_cast<size_t>(width) * static_cast<size_t>(height) * 4, 0);
    if(width == 0 || height == 0 || mMapSizeX <= 0 || mMapSizeY <= 0)
        return;

    // The seat colours are looked up once
    std::map<int, Ogre::ColourValue> ownerColours;
    for(std::map<int, std::string>::const_iterator it = mSeatColourIds.begin(); it != mSeatColourIds.end(); ++it)
        ownerColours[it->first] = seatColour(it->second);

    const uint64_t sizeX = static_cast<uint64_t>(mMapSizeX);
    const uint64_t sizeY = static_cast<uint64_t>(mMapSizeY);
    for(uint32_t row = 0; row < height; ++row)
    {
        // Row 0 is the north edge, the tiles with the largest y
        const uint64_t fromBottom = static_cast<uint64_t>(height - 1 - row);
        const uint64_t tileYMin = fromBottom * sizeY / height;
        const uint64_t tileYMax = std::max(tileYMin + 1, (fromBottom + 1) * sizeY / height);
        for(uint32_t column = 0; column < width; ++column)
        {
            const uint64_t tileXMin = static_cast<uint64_t>(column) * sizeX / width;
            const uint64_t tileXMax = std::max(tileXMin + 1, (static_cast<uint64_t>(column) + 1) * sizeX / width);
            MiniMapTileColour selected;
            for(uint64_t x = tileXMin; x < tileXMax && x < sizeX; ++x)
            {
                for(uint64_t y = tileYMin; y < tileYMax && y < sizeY; ++y)
                {
                    const size_t index = tileIndex(static_cast<int>(x), static_cast<int>(y));
                    const int seatId = mSeatIds[index];
                    const bool hasOwner = seatId != NO_SEAT;
                    const Ogre::ColourValue ownerColour = hasOwner ? ownerColours[seatId] : Ogre::ColourValue::Black;
                    const MiniMapTileColour colour = MiniMapColours::terrainColour(mVisuals[index], hasOwner,
                        seatId == ROGUE_SEAT_ID, ownerColour, 0);
                    if(colour.priority > selected.priority)
                        selected = colour;
                }
            }
            const size_t pixel = (static_cast<size_t>(row) * static_cast<size_t>(width) + column) * 4;
            pixels[pixel] = channelByte(selected.colour.r);
            pixels[pixel + 1] = channelByte(selected.colour.g);
            pixels[pixel + 2] = channelByte(selected.colour.b);
            pixels[pixel + 3] = 255;
        }
    }
}
