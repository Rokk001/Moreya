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

#ifndef LEVELPREVIEW_H
#define LEVELPREVIEW_H

#include "gamemap/MiniMapColours.h"

#include <OgreColourValue.h>

#include <cstdint>
#include <functional>
#include <iosfwd>
#include <map>
#include <string>
#include <vector>

enum class TileVisual;

//! \brief The map of a level file as a picture in the minimap colours, shown by the skirmish level selection.
//! It reads only the seats, tiles and rooms of the file; no game map is created. Every tile counts as seen, so
//! the picture shows the whole level as it is at the start.
class LevelPreview
{
public:
    //! \brief The seat id of a tile that belongs to no seat.
    static const int NO_SEAT = -1;
    //! \brief The picture is drawn with whole pixels per tile until its longest side reaches at least this size.
    static const uint32_t MIN_PICTURE_SIDE = 512;
    //! \brief The longest side of the picture is never larger than this; bigger maps share pixels between tiles.
    static const uint32_t MAX_PICTURE_SIDE = 1024;

    //! \brief The seat colour lookup: returns the colour of a seat colour id (colorId of the [Seats] section).
    typedef std::function<Ogre::ColourValue(const std::string&)> SeatColourFunction;

    //! \brief Creates an empty preview without a map.
    LevelPreview();

    //! \brief Reads the seats, tiles and rooms of a level file.
    //! \return False if the file cannot be read or its map size or one of its tile lines is invalid.
    bool loadFromFile(const std::string& fileName);

    //! \brief Reads the seats, tiles and rooms of the text of a level file, as loadFromFile does.
    bool loadFromStream(std::istream& stream);

    //! \brief The map size of the last loaded level (0 before a level is loaded).
    int getMapSizeX() const
    { return mMapSizeX; }
    int getMapSizeY() const
    { return mMapSizeY; }

    //! \brief How the tile at x, y looks at the start of the level, as Tile::computeTileVisual decides it.
    TileVisual getTileVisual(int x, int y) const;

    //! \brief The id of the seat the tile at x, y belongs to, or NO_SEAT.
    int getTileSeatId(int x, int y) const;

    //! \brief The colour id of a seat (colorId in the level file); the rogue seat 0 has the colour id "0".
    //! Returns an empty text for an unknown seat.
    std::string getSeatColourId(int seatId) const;

    //! \brief The minimap colour of the tile at x, y, computed by MiniMapColours::terrainColour as the in-game
    //! minimaps do for a seen tile in the first animation phase.
    MiniMapTileColour getTileColour(int x, int y, const SeatColourFunction& seatColour) const;

    //! \brief The size of the picture for the loaded map: the map size times a whole number of pixels per tile, at
    //! least MIN_PICTURE_SIDE on the longest side for small maps, and shrunk to MAX_PICTURE_SIDE for big maps.
    //! The aspect ratio of the picture is that of the map.
    void getPictureSize(uint32_t& width, uint32_t& height) const;

    //! \brief Draws the loaded map into RGBA pixels (4 bytes per pixel, rows from the top). The top row is the
    //! north edge of the map (largest y) as on the in-game minimap. When several tiles share a pixel, the tile
    //! with the highest minimap priority wins, as on the in-game minimap.
    //! \param width The picture width in pixels, at least 1.
    //! \param height The picture height in pixels, at least 1.
    //! \param seatColour Returns the colour of a seat colour id.
    //! \param pixels Receives width * height * 4 bytes.
    void drawPicture(uint32_t width, uint32_t height, const SeatColourFunction& seatColour,
        std::vector<uint8_t>& pixels) const;

private:
    //! \brief The index of the tile at x, y in mVisuals and mSeatIds.
    size_t tileIndex(int x, int y) const;

    int mMapSizeX;
    int mMapSizeY;
    //! \brief How every tile looks, row by row from y = 0.
    std::vector<TileVisual> mVisuals;
    //! \brief The seat every tile belongs to, row by row from y = 0 (NO_SEAT for none).
    std::vector<int> mSeatIds;
    //! \brief The colour id of every seat of the level, including the rogue seat 0.
    std::map<int, std::string> mSeatColourIds;
};

#endif // LEVELPREVIEW_H
