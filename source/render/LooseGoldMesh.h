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

#ifndef LOOSEGOLDMESH_H
#define LOOSEGOLDMESH_H

#include <string>

namespace Ogre
{
class SceneManager;
}

//! \brief Client side meshes for gold outside the treasury: a small coin heap for gold lying on the
//! floor and a sack with coins for gold carried by a worker. Both come in four sizes that follow the
//! four classic stack names the server already sends (GoldstackLv1..4, names only: there are no
//! meshes of that name any more), so no new data is sent. The heaps are built here the first time
//! they are needed, from the coins of our gold heap model; the sacks are the shipped pouch meshes. The heap is drawn at every treasury detail; the sack is left out when the
//! treasury detail option is off.
namespace LooseGoldMesh
{
//! Number of sizes (1 = least gold)
static const int sizeCount = 4;

//! Size 1..sizeCount of a classic stack mesh name ("GoldstackLv1".."GoldstackLv4"), 0 for any other name
int sizeFromStackName(const std::string& meshName);

//! Returns the name of the coin heap mesh for the stack name (built on demand), at every treasury
//! detail. Names that are not stack names are returned unchanged.
std::string prepareHeap(Ogre::SceneManager* sceneManager, const std::string& meshName);

//! Returns the name of the shipped sack mesh for the stack mesh name, or an empty string
//! when no sack is to be used (not a stack name, or the detail option is "off").
std::string prepareSack(Ogre::SceneManager* sceneManager, const std::string& meshName);
}

#endif // LOOSEGOLDMESH_H
