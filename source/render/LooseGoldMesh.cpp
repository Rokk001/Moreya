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

#include "render/LooseGoldMesh.h"

#include "render/TreasuryGoldMesh.h"

namespace LooseGoldMesh
{
namespace
{
const std::string StackPrefix = "GoldstackLv";
// The shipped meshes: the coin heaps (material GoldHeap), the coin pouches (GoldSack) and the loads (GoldLoad)
const std::string HeapPrefix = "GoldHeap_";
const std::string SackPrefix = "GoldSack_";
const std::string LoadPrefix = "GoldLoad_";
}

int sizeFromStackName(const std::string& meshName)
{
    if(meshName.size() != StackPrefix.size() + 1 || meshName.compare(0, StackPrefix.size(), StackPrefix) != 0)
        return 0;
    const int size = meshName[StackPrefix.size()] - '0';
    if(size < 1 || size > sizeCount)
        return 0;
    return size;
}

std::string prepareHeap(Ogre::SceneManager* sceneManager, const std::string& meshName)
{
    // The heap is drawn at every treasury detail: the classic stack meshes no longer exist
    const int size = sizeFromStackName(meshName);
    if(size == 0)
        return meshName;

    return HeapPrefix + static_cast<char>('0' + size);
}

std::string prepareSack(Ogre::SceneManager* sceneManager, const std::string& meshName)
{
    const int size = sizeFromStackName(meshName);
    if(size == 0 || TreasuryGoldMesh::getDetail() == TreasuryGoldMesh::Detail::off)
        return std::string();

    // The coin pouches are shipped meshes (GoldSack_1..4, material GoldSack)
    return SackPrefix + static_cast<char>('0' + size);
}

std::string prepareLoad(Ogre::SceneManager* sceneManager, const std::string& meshName)
{
    // Left out together with the sack
    if(prepareSack(sceneManager, meshName).empty())
        return std::string();

    return LoadPrefix + static_cast<char>('0' + sizeFromStackName(meshName));
}
}
