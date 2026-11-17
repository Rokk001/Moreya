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

#include "gamemap/MiniMapColours.h"

#include "entities/Tile.h"

namespace
{
//! \brief Minimap colour channels (0 to 1) of a mana well ground tile (blue).
const float MANA_WELL_COLOUR_RED = 0.18f;
const float MANA_WELL_COLOUR_GREEN = 0.37f;
const float MANA_WELL_COLOUR_BLUE = 0.78f;
}

//! \brief Computes the colour of a seen tile from its look and its owner, shared by the minimaps and the level preview.
MiniMapTileColour MiniMapColours::terrainColour(TileVisual visual, bool hasOwner, bool rogueOwner,
    const Ogre::ColourValue& ownerColour, unsigned int phase)
{
    MiniMapTileColour result;
    // The mana well ground is appended after the room visuals but is not a room
    const bool room = visual >= TileVisual::dungeonTempleRoom && visual < TileVisual::countTileVisual &&
        visual != TileVisual::manaWellGround;
    result.priority = 1;
    if(room || visual == TileVisual::claimedGround || visual == TileVisual::claimedFull)
    {
        result.priority = 3;
        if(room && (!hasOwner || rogueOwner))
        {
            const Ogre::ColourValue colours[] = {Ogre::ColourValue::Red, Ogre::ColourValue::Green,
                Ogre::ColourValue::Blue, Ogre::ColourValue(1.0f, 1.0f, 0.0f)};
            result.colour = colours[phase % 4];
            result.animated = true;
        }
        else
        {
            result.colour = !hasOwner ? DIRT_COLOUR : ownerColour;
            if(visual == TileVisual::dungeonTempleRoom)
                result.colour = result.colour * 0.65f + Ogre::ColourValue::White * 0.35f;
            else if(visual == TileVisual::claimedFull)
                result.colour = result.colour * 0.45f;
        }
    }
    else
    {
        switch(visual)
        {
            case TileVisual::dirtGround:
            case TileVisual::goldGround:
            case TileVisual::gemGround:
            case TileVisual::rockGround:
                result.colour = EARTH_GROUND_COLOUR;
                break;
            case TileVisual::dirtFull:
                result.colour = DIRT_COLOUR;
                break;
            case TileVisual::rockFull:
                result.colour = Ogre::ColourValue(0.20f, 0.10f, 0.04f);
                break;
            case TileVisual::goldFull:
                result.colour = Ogre::ColourValue(1.0f, 0.90f, 0.0f);
                result.priority = 4;
                break;
            case TileVisual::gemFull:
                result.colour = Ogre::ColourValue(0.63f, 0.0f, 0.82f);
                result.priority = 4;
                break;
            case TileVisual::waterGround:
                result.colour = Ogre::ColourValue(0.13f, 0.21f, 0.48f);
                result.priority = 2;
                break;
            case TileVisual::lavaGround:
                result.colour = Ogre::ColourValue(0.72f, 0.30f, 0.15f);
                result.priority = 2;
                break;
            case TileVisual::manaWellGround:
                result.colour = Ogre::ColourValue(MANA_WELL_COLOUR_RED, MANA_WELL_COLOUR_GREEN,
                    MANA_WELL_COLOUR_BLUE);
                result.priority = 2;
                break;
            default:
                break;
        }
    }
    return result;
}
