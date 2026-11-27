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

#include <OgreManualObject.h>
#include <OgreMeshManager.h>
#include <OgreSceneManager.h>
#include <OgreVector3.h>

#include <cmath>

namespace LooseGoldMesh
{
namespace
{
const std::string CoinMaterial = "TreasuryGoldPile";
const std::string StackPrefix = "GoldstackLv";
const std::string HeapPrefix = "GoldHeap_";
const std::string SackPrefix = "GoldSack_";

const int HeapRings = 5;
const int HeapSectors = 12;
const float Pi = 3.14159265f;
// Texture repeats per tile unit, so the coins stay small
const float TextureRepeat = 2.0f;

//! Radius of a coin heap on the floor, in tile units
float heapRadius(int size)
{
    return 0.15f + 0.045f * static_cast<float>(size);
}

//! Height of a coin heap on the floor
float heapHeight(int size)
{
    return 0.04f + 0.035f * static_cast<float>(size);
}

//! Surface height of a heap at distance t (0 centre .. 1 rim) and angle, with a few lumps
float heapSurface(float peak, int size, float t, float angle)
{
    if(t >= 1.0f)
        return 0.0f;
    const float dome = std::pow(1.0f - t * t, 0.75f);
    const float lumps = 1.0f + 0.14f * t * std::sin(5.0f * angle + static_cast<float>(size));
    return peak * dome * lumps;
}

//! Adds a coin heap (circular, rising to the peak) to an open manual section
void addHeap(Ogre::ManualObject* object, const Ogre::Vector3& centre, float radius, float peak, int size)
{
    const int baseIndex = static_cast<int>(object->getCurrentVertexCount());
    const int rows = HeapRings + 1;
    for(int ring = 0; ring < rows; ++ring)
    {
        const float t = static_cast<float>(ring) / static_cast<float>(HeapRings);
        for(int sector = 0; sector < HeapSectors; ++sector)
        {
            const float angle = 2.0f * Pi * static_cast<float>(sector) / static_cast<float>(HeapSectors);
            const float height = heapSurface(peak, size, t, angle);
            const float x = std::cos(angle) * radius * t;
            const float y = std::sin(angle) * radius * t;
            object->position(centre + Ogre::Vector3(x, y, height));

            // Normal from the slope along the radius (the lumps are too small to matter)
            const float next = heapSurface(peak, size, t + 0.05f, angle);
            const float slope = (next - height) / (0.05f * radius);
            Ogre::Vector3 normal(-std::cos(angle) * slope, -std::sin(angle) * slope, 1.0f);
            normal.normalise();
            object->normal(normal);
            object->textureCoord(x * TextureRepeat, y * TextureRepeat);
        }
    }

    for(int ring = 0; ring < rows - 1; ++ring)
    {
        for(int sector = 0; sector < HeapSectors; ++sector)
        {
            const int nextSector = (sector + 1) % HeapSectors;
            const int a = baseIndex + ring * HeapSectors + sector;
            const int b = baseIndex + ring * HeapSectors + nextSector;
            const int c = baseIndex + (ring + 1) * HeapSectors + nextSector;
            const int d = baseIndex + (ring + 1) * HeapSectors + sector;
            // Counter-clockwise seen from above
            object->triangle(a, d, c);
            object->triangle(a, c, b);
        }
    }
}

//! Builds the mesh of a coin heap of the given size and registers it under the resource name
void buildHeapMesh(Ogre::SceneManager* sceneManager, const std::string& resourceName, int size)
{
    Ogre::ManualObject* object = sceneManager->createManualObject();
    object->begin(CoinMaterial, Ogre::RenderOperation::OT_TRIANGLE_LIST, "Graphics");
    addHeap(object, Ogre::Vector3(0.0f, 0.0f, 0.004f), heapRadius(size), heapHeight(size), size);
    object->end();
    object->convertToMesh(resourceName, "Graphics");
    sceneManager->destroyManualObject(object);
}

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

    const std::string name = HeapPrefix + static_cast<char>('0' + size);
    if(!Ogre::MeshManager::getSingleton().resourceExists(name + ".mesh", "Graphics"))
        buildHeapMesh(sceneManager, name + ".mesh", size);
    return name;
}

std::string prepareSack(Ogre::SceneManager* sceneManager, const std::string& meshName)
{
    const int size = sizeFromStackName(meshName);
    if(size == 0 || TreasuryGoldMesh::getDetail() == TreasuryGoldMesh::Detail::off)
        return std::string();

    // The coin pouches are shipped meshes (GoldSack_1..4, material GoldSack)
    return SackPrefix + static_cast<char>('0' + size);
}
}
