/*
 *  Copyright (C) 2026 OpenDungeons Team
 *  SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "modes/InputCommand.h"

#include "entities/GameEntity.h"
#include "entities/Tile.h"
#include "utils/Translation.h"

#include <OgreColourValue.h>

#include <algorithm>
#include <string>

void InputCommand::displayTileBuildFailure(const Tile* tile, Seat* seat)
{
    std::string reason;
    if(tile == nullptr)
        reason = Translation::tr("mode.input.outside_map");
    else if(tile->isFullTile())
        reason = Translation::tr("mode.input.dig_first");
    else if(tile->getIsBuilding())
        reason = Translation::tr("mode.input.occupied");
    else if(!tile->isClaimedForSeat(seat))
        reason = Translation::tr("mode.input.claim_first");
    else
        reason = Translation::tr("mode.input.no_buildable");

    displayText(Ogre::ColourValue::Red, reason);
}

void InputCommand::selectTilesOfEntities(const std::vector<GameEntity*>& entities)
{
    std::vector<Tile*> tiles;
    for(GameEntity* entity : entities)
    {
        Tile* tile = entity->getPositionTile();
        if(tile != nullptr && std::find(tiles.begin(), tiles.end(), tile) == tiles.end())
            tiles.push_back(tile);
    }
    selectTiles(tiles);
}
