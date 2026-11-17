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

#ifndef MINIMAPCOLOURS_H
#define MINIMAPCOLOURS_H

#include <OgreColourValue.h>

enum class TileVisual;

//! \brief The colour a tile is drawn with on the map.
struct MiniMapTileColour
{
    Ogre::ColourValue colour = Ogre::ColourValue::Black;
    //! Tiles with a higher priority win when several tiles share one map pixel.
    unsigned int priority = 0;
    //! True if the colour changes with the animation phase.
    bool animated = false;
};

//! \brief The colours of the ground and the walls of the map. The in-game minimaps and the map preview of the
//! skirmish level selection both draw with them, so a level looks the same in both.
namespace MiniMapColours
{
    //! Colour of solid dirt, also used for unowned claimed tiles.
    const Ogre::ColourValue DIRT_COLOUR(0.36f, 0.18f, 0.05f);

    //! Colour of dug-out earth ground (also gold, gem and rock ground): the dark brown of the earth, lighter than
    //! solid dirt so that floor and wall stay apart, but never grey or sandy like stone.
    const Ogre::ColourValue EARTH_GROUND_COLOUR(0.47f, 0.27f, 0.10f);

    //! \brief Computes the colour of a tile that has been seen, from its look and its owner only (no creatures,
    //! no items and no dig marks).
    //! \param visual How the tile looks.
    //! \param hasOwner True if the tile belongs to a seat.
    //! \param rogueOwner True if that seat is the rogue seat.
    //! \param ownerColour The colour of that seat; not used without an owner.
    //! \param phase The current animation phase; rooms of no keeper cycle through colours with it.
    MiniMapTileColour terrainColour(TileVisual visual, bool hasOwner, bool rogueOwner,
        const Ogre::ColourValue& ownerColour, unsigned int phase);
}

#endif // MINIMAPCOLOURS_H
