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

#include "entities/BuildingObject.h"
#include "render/RenderManager.h"

#include "entities/Building.h"
#include "entities/GameEntityType.h"
#include "entities/Tile.h"
#include "network/ODPacket.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "ODApplication.h"
#include <OgreSubEntity.h>
#include <OgreManualObject.h>
#include "gamemap/GameMap.h"
#include "network/ODServer.h"
#include "network/ServerNotification.h"
#include "traps/TrapBoulder.h"
#include "traps/TrapCannon.h"
#include "traps/TrapSpike.h"
#include "utils/Random.h"
#include "utils/LogManager.h"

#include <algorithm>
#include <cmath>
#include <iostream>

BuildingObject::BuildingObject(GameMap* gameMap, Building& building, const std::string& meshName, Tile* targetTile,
        Ogre::Real x, Ogre::Real y, Ogre::Real z, Ogre::Real rotationAngle, bool hideCoveredTile, float opacity,
        const std::string& initialAnimationState, bool initialAnimationLoop) :
    RenderedMovableEntity(
        gameMap,
        targetTile == nullptr ? building.getName() : building.getName() + "_" + Tile::displayAsString(targetTile),
        meshName,
        rotationAngle,
        hideCoveredTile,
        opacity)
{
    mPosition = Ogre::Vector3(x, y, z);
    mPrevAnimationState = initialAnimationState;
    mPrevAnimationStateLoop = initialAnimationLoop;
}

BuildingObject::BuildingObject(GameMap* gameMap, Building& building, const std::string& meshName,
        Tile& targetTile, Ogre::Real rotationAngle, bool hideCoveredTile, float opacity,
        const std::string& initialAnimationState, bool initialAnimationLoop) :
    RenderedMovableEntity(
        gameMap,
        building.getName() + "_" + Tile::displayAsString(&targetTile),
        meshName,
        rotationAngle,
        hideCoveredTile,
        opacity)
{
    mPosition = Ogre::Vector3(targetTile.getX(), targetTile.getY(), 0);
    mPrevAnimationState = initialAnimationState;
    mPrevAnimationStateLoop = initialAnimationLoop;
}


BuildingObject::BuildingObject(GameMap* gameMap) :
    RenderedMovableEntity(gameMap)
{
}

GameEntityType BuildingObject::getObjectType() const
{
    return GameEntityType::buildingObject;
}

void BuildingObject::doUpkeep()
{
    RenderedMovableEntity::doUpkeep();

    for(std::vector<EntityParticleEffect*>::iterator it = mEntityParticleEffects.begin(); it != mEntityParticleEffects.end();)
    {
        EntityParticleEffect* effect = *it;
        if(effect->mNbTurnsEffect < 0)
        {
            ++it;
            continue;
        }

        if(effect->mNbTurnsEffect > 0)
        {
            --effect->mNbTurnsEffect;
            ++it;
            continue;
        }

        it = mEntityParticleEffects.erase(it);
        delete effect;
    }
}

BuildingObject* BuildingObject::getBuildingObjectFromPacket(GameMap* gameMap, ODPacket& is)
{
    BuildingObject* obj = new BuildingObject(gameMap);
    obj->importFromPacket(is);
    return obj;
}

void BuildingObject::addParticleEffect(const std::string& effectScript, uint32_t nbTurns)
{
    EntityParticleEffect* effect = new EntityParticleEffect(nextParticleSystemsName(), effectScript, nbTurns);
    mEntityParticleEffects.push_back(effect);
}

//! Height share of the client-side fill mesh (models/GhostCauldronFill.mesh, 0.6 high) that fills the inspection glass
//! of the closed cauldron (0.41 high) when the cauldron is full
static const float GHOST_FILL_HEIGHT=0.68f;

//! \brief Builds the visible green liquid in the outlet spout below the inspection glass. The spout itself is part of the
//! cauldron mesh (the approved closed cauldron, its spout mouth at y 1.0, z 0.14 to 0.31); the liquid uses the cauldron's
//! ectoplasm material from the Graphics resource group (Ogre's default group does not hold it and would draw the outlet
//! white) and unrolls its texture over the surface, so no face is flat.
static void buildGhostCauldronOutlet(Ogre::ManualObject& outlet)
{
    // A wet green tongue at the bottom of the spout bore identifies the ectoplasm output even while idle.
    // Continue below the lip so the output is visible from above instead of hiding entirely inside the bore.
    outlet.begin("GhostCauldronEctoplasm",Ogre::RenderOperation::OT_TRIANGLE_LIST,"Graphics");
    outlet.position(-0.05f,0.86f,0.172f);outlet.normal(Ogre::Vector3::UNIT_Z);outlet.textureCoord(0.1f,0.1f);
    outlet.position(0.05f,0.86f,0.172f);outlet.normal(Ogre::Vector3::UNIT_Z);outlet.textureCoord(0.9f,0.1f);
    outlet.position(-0.05f,1.0f,0.165f);outlet.normal(Ogre::Vector3::UNIT_Z);outlet.textureCoord(0.1f,0.9f);
    outlet.position(0.05f,1.0f,0.165f);outlet.normal(Ogre::Vector3::UNIT_Z);outlet.textureCoord(0.9f,0.9f);
    outlet.triangle(0,1,2);outlet.triangle(1,3,2);
    outlet.position(-0.05f,1.0f,0.165f);outlet.normal(Ogre::Vector3::UNIT_Y);outlet.textureCoord(0.1f,0.9f);
    outlet.position(0.05f,1.0f,0.165f);outlet.normal(Ogre::Vector3::UNIT_Y);outlet.textureCoord(0.9f,0.9f);
    outlet.position(-0.03f,1.02f,0.04f);outlet.normal(Ogre::Vector3::UNIT_Y);outlet.textureCoord(0.3f,1.0f);
    outlet.position(0.03f,1.02f,0.04f);outlet.normal(Ogre::Vector3::UNIT_Y);outlet.textureCoord(0.7f,1.0f);
    outlet.triangle(4,5,6);outlet.triangle(5,7,6);outlet.end();
}

//! \brief Builds the furniture, the cauldron's fill and output spout, and a decorative bag's shared quality materials.
void BuildingObject::createMeshLocal(NodeType type)
{
    RenderedMovableEntity::createMeshLocal(type);
    if(!getIsOnServerMap() && getMeshName()=="GhostCauldron" && getEntityNode()!=nullptr)
    {
        Ogre::Entity* fill=RenderManager::getSingleton().getSceneManager()->createEntity(getName()+"_GhostFill","GhostCauldronFill.mesh");
        fill->setCastShadows(false);fill->setQueryFlags(0);
        // Just behind the inspection glass of the closed cauldron (glass at y 0.668, x -0.18 to 0.22, z 0.38 to 0.79; a
        // dark plate at y 0.598 closes the pot behind it); the full fill reaches the top of the glass
        mGhostFillNode=getEntityNode()->createChildSceneNode(getName()+"_GhostFillNode",Ogre::Vector3(0.02f,0.64f,0.38f));
        mGhostFillNode->attachObject(fill);
        mGhostFillNode->setScale(1.0f,1.0f,GHOST_FILL_HEIGHT*static_cast<float>(std::max(0.0,mGhostFill)));
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        mGhostOutlet=scene->createManualObject(getName()+"_GhostOutlet");
        mGhostOutlet->setQueryFlags(0);mGhostOutlet->setCastShadows(true);
        buildGhostCauldronOutlet(*mGhostOutlet);
        getEntityNode()->attachObject(mGhostOutlet);
    }
    if(!getIsOnServerMap() && getMeshName()=="GhostHook" && getEntityNode()!=nullptr)
    {
        // The pack on the wall hook is the textured pack the hunters wear (decision 798): the renderer draws the bare
        // hook (GhostHookEmpty) for a full hook, and the worn GhostBackpack with its holstered capture cannon hangs on it.
        // In the hook's frame the wall bolts lie at -y and the hook tip at about y 0.075, z 0.49 to 0.64.
        const Ogre::Real packHeight=0.30f,packBackY=0.03f,packTopZ=0.56f;
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        Ogre::Entity* pack=scene->createEntity(getName()+"_GhostHookPack","GhostBackpack.mesh");
        pack->setCastShadows(true);pack->setQueryFlags(0);
        const Ogre::AxisAlignedBox packBounds=pack->getMesh()->getBounds();
        const Ogre::Vector3 packSize=packBounds.getSize();
        const Ogre::Real fit=packHeight/packSize.z;
        // Half a turn round the vertical axis: the straps (+y of the pack) go round the hook to the wall, the generator
        // plate with its power cells faces the room as on the hunter's back. As there, the pack's back plate lies at half
        // its depth (the approved gear: the strap loops reach on behind it), so the back plate rests on the hook.
        mGhostHookPackNode=getEntityNode()->createChildSceneNode(getName()+"_GhostHookPackNode",
            Ogre::Vector3(fit*0.5f*(packBounds.getMinimum().x+packBounds.getMaximum().x),
                packBackY+fit*0.5f*packSize.y,packTopZ-fit*packBounds.getMaximum().z),
            Ogre::Quaternion(Ogre::Degree(180.0f),Ogre::Vector3::UNIT_Z));
        mGhostHookPackNode->setScale(Ogre::Vector3(fit,fit,fit));
        mGhostHookPackNode->attachObject(pack);
        // The capture cannon waits upright in the holster cup on the pack's side, exactly as on the worn pack
        // (Creature::updateGhostHuntVisuals)
        Ogre::Entity* gun=scene->createEntity(getName()+"_GhostHookPackGun","GhostCaptureGun.mesh");
        gun->setCastShadows(true);gun->setQueryFlags(0);
        const Ogre::Real holster=0.89f*packSize.z/gun->getMesh()->getBounds().getSize().z;
        Ogre::SceneNode* holsterNode=mGhostHookPackNode->createChildSceneNode(getName()+"_GhostHookHolsterNode",
            Ogre::Vector3(packBounds.getMinimum().x+0.108f*packSize.x,packBounds.getMinimum().y+0.068f*packSize.y,0.24f*packSize.z));
        holsterNode->setScale(Ogre::Vector3(holster,holster,holster));
        holsterNode->attachObject(gun);
    }
    if(!getIsOnServerMap() && mItemBagQuality >= 0)
        RenderManager::getSingleton().rrRefreshItemBagAppearance(this, static_cast<Quality>(mItemBagQuality), mItemBagSealed);
}

//! \brief Sends the furniture footprint and decorative merchant bag properties.
void BuildingObject::exportToPacket(ODPacket& os, const Seat* seat) const
{
    RenderedMovableEntity::exportToPacket(os, seat);
    os << mFurnitureScale.x << mFurnitureScale.y;
    os << mItemBagQuality << mItemBagSealed;
    os << mGhostFill << mGhostAlarm;
}

//! \brief Reads the furniture footprint and decorative merchant bag properties.
void BuildingObject::importFromPacket(ODPacket& is)
{
    RenderedMovableEntity::importFromPacket(is);
    OD_ASSERT_TRUE(is >> mFurnitureScale.x >> mFurnitureScale.y);
    OD_ASSERT_TRUE(is >> mItemBagQuality >> mItemBagSealed);
    OD_ASSERT_TRUE(is >> mGhostFill >> mGhostAlarm);
}

void BuildingObject::fireRefresh()
{
    for(Seat* seat : mSeatsWithVisionNotified)
    {
        if(seat->getPlayer() == nullptr)
            continue;
        if(!seat->getPlayer()->getIsHuman())
            continue;

        const std::string& name = getName();
        ServerNotification *serverNotification = new ServerNotification(
            ServerNotificationType::entitiesRefresh, seat->getPlayer());
        uint32_t nb = 1;
        GameEntityType entityType = getObjectType();
        serverNotification->mPacket << nb;
        serverNotification->mPacket << entityType;
        serverNotification->mPacket << name;
        exportToPacketForUpdate(serverNotification->mPacket, seat);
        ODServer::getSingleton().queueServerNotification(serverNotification);
    }
}

//! \brief Sends one add packet per current viewer, carrying the old identity for removal after mesh creation.
void BuildingObject::notifyReplacement(BuildingObject& previous)
{
    mSeatsWithVisionNotified = getPositionTile()->getSeatsWithVision();
    for(Seat* seat : mSeatsWithVisionNotified)
    {
        std::vector<Seat*>::iterator oldSeat = std::find(previous.mSeatsWithVisionNotified.begin(),
            previous.mSeatsWithVisionNotified.end(), seat);
        if(oldSeat != previous.mSeatsWithVisionNotified.end())
            previous.mSeatsWithVisionNotified.erase(oldSeat);
        if(seat->getPlayer() == nullptr || !seat->getPlayer()->getIsHuman())
            continue;

        ServerNotification* notification = new ServerNotification(ServerNotificationType::addEntity, seat->getPlayer());
        notification->mPacket << getGameMap()->getNodeType();
        exportHeadersToPacket(notification->mPacket);
        exportToPacket(notification->mPacket, seat);
        notification->mPacket << previous.getObjectType() << previous.getName();
        ODServer::getSingleton().queueServerNotification(notification);
    }
}

void BuildingObject::setGhostRoomState(double fill,double alarm)
{
    if(mGhostFill==fill && mGhostAlarm==alarm) return;
    mGhostFill=fill;mGhostAlarm=alarm;
    fireRefresh();
}
void BuildingObject::exportToPacketForUpdate(ODPacket& packet,Seat* seat)
{
    RenderedMovableEntity::exportToPacketForUpdate(packet,seat);
    packet << mGhostFill << mGhostAlarm;
}
void BuildingObject::updateFromPacket(ODPacket& packet)
{
    RenderedMovableEntity::updateFromPacket(packet);
    OD_ASSERT_TRUE(packet >> mGhostFill >> mGhostAlarm);
}
void BuildingObject::update(Ogre::Real seconds)
{
    RenderedMovableEntity::update(seconds);
    if(getIsOnServerMap()) return;
    if(mGhostFillNode!=nullptr) mGhostFillNode->setScale(1.0f,1.0f,GHOST_FILL_HEIGHT*static_cast<float>(std::max(0.0,std::min(1.0,mGhostFill))));
    mGhostAlarm=std::max(0.0,mGhostAlarm-seconds*ODApplication::turnsPerSecond*getGameMap()->getGameSpeedFactor());
    if(getMeshName()!="GhostBell" || getEntityNode()==nullptr) return;
    // While the bell rings (GhostBellSeconds) a red and a green alarm lamp beside it blink; no wall panel carries them.
    const bool flash=mGhostAlarm>0.0 && std::fmod(mGhostAlarm/ODApplication::turnsPerSecond,0.5)<0.25;
    if(mGhostLampNode==nullptr)
    {
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        Ogre::BillboardSet* lamps=scene->createBillboardSet(getOgreNamePrefix()+getName()+"_AlarmLamps",2);
        lamps->setMaterialName("ReactionParticleGlow");lamps->setDefaultDimensions(0.16f,0.16f);
        lamps->setCastShadows(false);lamps->setQueryFlags(0);
        lamps->createBillboard(Ogre::Vector3(-0.24f,0.06f,0.80f),Ogre::ColourValue(1.0f,0.12f,0.08f));
        lamps->createBillboard(Ogre::Vector3(0.24f,0.06f,0.80f),Ogre::ColourValue(0.2f,1.0f,0.3f));
        mGhostLampNode=getEntityNode()->createChildSceneNode();mGhostLampNode->attachObject(lamps);
    }
    mGhostLampNode->setVisible(flash);
}
//! \brief Releases cauldron and hook attachments before destroying their furniture node.
void BuildingObject::destroyMeshLocal(NodeType type)
{
    if(mGhostOutlet!=nullptr)
    {
        mGhostOutlet->detachFromParent();
        RenderManager::getSingleton().getSceneManager()->destroyManualObject(mGhostOutlet);mGhostOutlet=nullptr;
    }
    if(mGhostFillNode!=nullptr)
    {
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        while(mGhostFillNode->numAttachedObjects()>0)
        {
            Ogre::MovableObject* object=mGhostFillNode->getAttachedObject(static_cast<unsigned short>(0));
            mGhostFillNode->detachObject(object);scene->destroyMovableObject(object);
        }
        scene->destroySceneNode(mGhostFillNode);mGhostFillNode=nullptr;
    }
    if(mGhostLampNode!=nullptr)
    {
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        while(mGhostLampNode->numAttachedObjects()>0)
        {
            Ogre::MovableObject* object=mGhostLampNode->getAttachedObject(static_cast<unsigned short>(0));
            mGhostLampNode->detachObject(object);scene->destroyMovableObject(object);
        }
        scene->destroySceneNode(mGhostLampNode);mGhostLampNode=nullptr;
    }
    if(mGhostHookPackNode!=nullptr)
    {
        // The holster node with the cannon first, then the pack itself
        Ogre::SceneManager* scene=RenderManager::getSingleton().getSceneManager();
        while(mGhostHookPackNode->numChildren()>0)
        {
            Ogre::SceneNode* child=static_cast<Ogre::SceneNode*>(mGhostHookPackNode->getChild(static_cast<unsigned short>(0)));
            while(child->numAttachedObjects()>0)
            {
                Ogre::MovableObject* object=child->getAttachedObject(static_cast<unsigned short>(0));
                child->detachObject(object);scene->destroyMovableObject(object);
            }
            scene->destroySceneNode(child);
        }
        while(mGhostHookPackNode->numAttachedObjects()>0)
        {
            Ogre::MovableObject* object=mGhostHookPackNode->getAttachedObject(static_cast<unsigned short>(0));
            mGhostHookPackNode->detachObject(object);scene->destroyMovableObject(object);
        }
        scene->destroySceneNode(mGhostHookPackNode);mGhostHookPackNode=nullptr;
    }
    RenderedMovableEntity::destroyMeshLocal(type);
}
