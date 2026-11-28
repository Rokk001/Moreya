"""Check body clearance against 121 skinned Walk poses of every creature model."""
from pathlib import Path
import argparse
import os
import re
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--height-profile', action='store_true', help='Measure triangle-clipped walking envelopes below furniture heights without changing collision policy')
parser.add_argument('--frames', type=int, default=120, help='Number of equal Walk intervals to sample, including both ends')
parser.add_argument('--bone-profile', help='Report dominant-bone vertex extents for one mesh, without changing poses or collision policy')
args = parser.parse_args()
assert args.frames > 0

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
prefix = Path(os.environ['CMAKE_PREFIX_PATH'])
# creatures.cfg as the game reads it: most creature rows are own rows of the content package core-config; without the
# content the model catalog cannot be compared and the probe is not run
if not content_packages.has_content(repo):
    content_packages.unchecked('check_creature_walking_bounds', ['config/creatures.cfg MeshName/BedMeshName rows',
                                                                 'walking bounds probe'])
    sys.exit(0)
creatures_cfg = content_packages.read_text(repo, 'config/creatures.cfg')
models = set(re.findall(r'^\s*MeshName\s+(\S+)', creatures_cfg, re.M))
catalog = set(re.findall(r'\{"([^"\n]+\.mesh)"', (repo / 'source/gamemap/RoomObjectBounds.h').read_text()))
assert models == catalog, f'Walking bounds catalog mismatch: {models ^ catalog}'
assert args.bone_profile is None or args.bone_profile in catalog
renderer = (repo / 'source/render/RenderManager.cpp').read_text()
bed_support = renderer.split('Ogre::Vector3 getBedSupportPoint(', 1)[1].split('\nbool needsCreatureDropFallback(', 1)[0]
bed_names = sorted(set(re.findall(r'^\s*BedMeshName\s+(\S+)', creatures_cfg, re.M)))
bed_names = sorted(set(bed_names) | {name for name in re.findall(r'\{"([^"\n]+)"',
    (repo / 'source/gamemap/RoomObjectBounds.h').read_text()) if name.endswith(('Bed', 'Coffin'))})
leg_names = {}
for side in ('left', 'right'):
    for joint in ('Upper', 'Lower', 'Tip'):
        leg_names[(side, joint)] = re.search(side + r'Leg\.m' + joint + r' = findFeedingBone\(skeleton, (\{[^\n]+\})\);', renderer)[1]
probe = r'''
#include <Ogre.h>
#include "gamemap/RoomObjectBounds.h"
#include <iostream>
#include <sstream>
#include <set>
Ogre::Vector3 getBedSupportPoint(BED_SUPPORT
Ogre::Bone* findBone(Ogre::Skeleton* skeleton,std::initializer_list<const char*> names){
 for(const auto* name:names)if(skeleton->hasBone(name))return skeleton->getBone(name);
 return nullptr;
}
Ogre::AxisAlignedBox poseBounds;
// One band for every furniture top that carries a measured height (all beds): the creature is clipped
// at that height in mesh units, i.e. at the furniture top divided by the level-one scale (1.0, the unit size).
std::vector<float> furnitureTops,heights;
std::vector<Ogre::AxisAlignedBox> heightBounds;
bool profile=false;
const std::string boneProfile="BONE_PROFILE";
std::map<unsigned short,Ogre::AxisAlignedBox> boneBounds,lowBoneBounds;
// The carried weapon part that the walking row leaves out (decision of the plan: the Defender keeps its walking radius
// of 0.37 with the glaive, as the worker kept its rows; the long weapons of the roster follow it: the Hunter's spear, the
// Shadow Lord's sword and the Paladin's mace keep the radius of their bodies, and so does Ziv's pick,
// 2026-11-27): the meshes and the index of their first weapon submesh (the weapon parts are appended after the body, the
// probe loads no material scripts, so the part is found by its index)
const std::set<std::string> WALKING_RADIUS_CARRIED_MESHES={"Defender.mesh","Hunter.mesh","ShadowLord.mesh","Paladin.mesh",
 "Kobold.mesh"};
const unsigned WALKING_RADIUS_CARRIED_FIRST_SUB=1;
// Largest XY distance of the skinned vertices of the current pose (body only); also fills the pose bounds and, over
// every part, the height bands
float radius(Ogre::Entity* entity){
 entity->addSoftwareAnimationRequest(false);entity->_updateAnimation();entity->removeSoftwareAnimationRequest(false);
 float result=0;poseBounds.setNull();
 for(unsigned sub=0;sub<entity->getNumSubEntities();++sub){
  auto* part=entity->getSubEntity(sub);
  // A carried weapon part (the Defender's glaive, the Hunter's spear, the Shadow Lord's sword, the Paladin's mace, Ziv's
  // pick) is not body: it stays out of the walking row, the body bands see it
  const bool carried=WALKING_RADIUS_CARRIED_MESHES.count(entity->getMesh()->getName())!=0&&
   sub>=WALKING_RADIUS_CARRIED_FIRST_SUB;
  auto* data=part->getSubMesh()->useSharedVertices?entity->_getSkelAnimVertexData():part->_getSkelAnimVertexData();
  auto* position=data->vertexDeclaration->findElementBySemantic(Ogre::VES_POSITION);
  auto buffer=data->vertexBufferBinding->getBuffer(position->getSource());
  Ogre::HardwareBufferLockGuard lock(buffer,Ogre::HardwareBuffer::HBL_READ_ONLY);
  auto* bytes=static_cast<unsigned char*>(lock.pData);
  for(size_t i=0;i<data->vertexCount;++i){
   float* vertex;position->baseVertexPointerToElement(bytes+(data->vertexStart+i)*buffer->getVertexSize(),&vertex);
   if(!carried){result=std::max(result,std::hypot(vertex[0],vertex[1]));poseBounds.merge(Ogre::Vector3(vertex));}
   if(entity->getMesh()->getName()==boneProfile){
    const auto& assignments=part->getSubMesh()->useSharedVertices?entity->getMesh()->getBoneAssignments():part->getSubMesh()->getBoneAssignments();
    const auto range=assignments.equal_range(i);auto strongest=range.second;
    for(auto weight=range.first;weight!=range.second;++weight)
     if(strongest==range.second||weight->second.weight>strongest->second.weight)strongest=weight;
    if(strongest==range.second)throw std::runtime_error("Bone profile found an unweighted vertex");
    const auto bone=strongest->second.boneIndex;boneBounds[bone].merge(Ogre::Vector3(vertex));
    if(vertex[2]<=heights.back())lowBoneBounds[bone].merge(Ogre::Vector3(vertex));
   }
  }
  {
   if(part->getSubMesh()->operationType!=Ogre::RenderOperation::OT_TRIANGLE_LIST)
    throw std::runtime_error("Height profiling requires triangle-list meshes");
   auto* indices=part->getSubMesh()->indexData;
   Ogre::HardwareBufferLockGuard indexLock(indices->indexBuffer,Ogre::HardwareBuffer::HBL_READ_ONLY);
   const bool wide=indices->indexBuffer->getType()==Ogre::HardwareIndexBuffer::IT_32BIT;
   for(size_t triangle=0;triangle+2<indices->indexCount;triangle+=3){
    Ogre::Vector3 points[3];
    for(int corner=0;corner<3;++corner){
     const auto offset=indices->indexStart+triangle+corner;
     const auto index=wide?static_cast<const uint32_t*>(indexLock.pData)[offset]:static_cast<const uint16_t*>(indexLock.pData)[offset];
     if(index>=data->vertexCount)throw std::runtime_error("Height profile vertex index outside animated data");
     float* vertex;position->baseVertexPointerToElement(bytes+(data->vertexStart+index)*buffer->getVertexSize(),&vertex);points[corner]=Ogre::Vector3(vertex);
    }
    for(size_t band=0;band<heights.size();++band)for(int corner=0;corner<3;++corner){
     const auto& a=points[corner];const auto& b=points[(corner+1)%3];
     if(a.z<=heights[band])heightBounds[band].merge(a);
     if((a.z<heights[band]&&b.z>heights[band])||(a.z>heights[band]&&b.z<heights[band]))
      heightBounds[band].merge(a+(b-a)*((heights[band]-a.z)/(b.z-a.z)));
    }
   }
  }
 }
 return result;
}
int main(int argc,char** argv){try{
 Ogre::Root root("","","walking-bounds.log");root.loadPlugin("RenderSystem_GL3Plus");
 root.setRenderSystem(root.getAvailableRenderers().front());root.initialise(false);
 Ogre::NameValuePairList opts;opts["hidden"]="true";root.createRenderWindow("Walking bounds",64,64,false,&opts);
 auto& groups=Ogre::ResourceGroupManager::getSingleton();groups.createResourceGroup("Graphics");
 groups.addResourceLocation(std::string(argv[1])+"/models","FileSystem","Graphics",true);
 // The models folders of the content packages that are present (creatures, beds and furniture moved there)
 {std::istringstream folders(argv[3]);std::string folder;while(std::getline(folders,folder,';'))if(!folder.empty())groups.addResourceLocation(folder,"FileSystem","Graphics",false);}
 groups.initialiseAllResourceGroups();
 auto* scene=root.createSceneManager();int checks=0,failures=0;
 for(const auto& row:RoomObjectPath::meshBounds)if(std::isfinite(row.maxZ))furnitureTops.push_back(row.maxZ);
 std::sort(furnitureTops.begin(),furnitureTops.end());
 furnitureTops.erase(std::unique(furnitureTops.begin(),furnitureTops.end()),furnitureTops.end());
 for(float top:furnitureTops)heights.push_back(top);
 heightBounds.resize(heights.size());
 profile=argc>4;
 const int frames=std::stoi(argv[2]);
 if(profile)for(const std::string name:{BED_NAMES}){
  const auto mesh=Ogre::MeshManager::getSingleton().load(name+".mesh","Graphics");
  const auto support=getBedSupportPoint(mesh);
  ++checks;if(!std::isfinite(support.z)||support.z<mesh->getBounds().getMinimum().z-.00001f||support.z>mesh->getBounds().getMaximum().z+.00001f){++failures;std::cout<<"FAIL invalid bed support "<<name<<'\n';}
  std::cout<<"FURNITURE_HEIGHT "<<name<<" min="<<mesh->getBounds().getMinimum().z<<" max="<<mesh->getBounds().getMaximum().z<<" support="<<support.z<<'\n';
 }
 for(const auto& model:RoomObjectPath::walkingRadii){
  boneBounds.clear();lowBoneBounds.clear();
  for(auto& bounds:heightBounds)bounds.setNull();
  auto* entity=scene->createEntity(model.name,model.name,"Graphics");
  auto* node=scene->getRootSceneNode()->createChildSceneNode();node->attachObject(entity);
  auto* walk=entity->getAnimationState("Walk");walk->setEnabled(true);
  auto* skeleton=entity->getSkeleton();
  Ogre::Bone* joints[]={LEFT_UPPER,LEFT_LOWER,LEFT_TIP,RIGHT_UPPER,RIGHT_LOWER,RIGHT_TIP};
  Ogre::AxisAlignedBox jointBounds[6];
  for(int frame=0;frame<=frames;++frame){
   walk->setTimePosition(walk->getLength()*frame/frames);root._fireFrameStarted();root._fireFrameRenderingQueued();
   float actual=radius(entity);++checks;
   if(profile)for(int joint=0;joint<6;++joint)if(joints[joint])jointBounds[joint].merge(joints[joint]->_getDerivedPosition());
   if(actual>model.radius||poseBounds.getMinimum().x<model.minX||poseBounds.getMinimum().y<model.minY||poseBounds.getMaximum().x>model.maxX||poseBounds.getMaximum().y>model.maxY){++failures;std::cout<<"FAIL "<<model.name<<" pose "<<frame<<" exceeds walking bounds "<<poseBounds<<'\n';}
   root._fireFrameEnded();
  }
  for(size_t band=0;band<heights.size();++band){
   const auto& actual=heightBounds[band];const float margin=RoomObjectPath::lowWalkingMargin;
   const RoomObjectPath::BodyBand* low=RoomObjectPath::bodyBand(model.name,furnitureTops[band]);
   if(profile){
    const Ogre::Vector3 lo=actual.isNull()?Ogre::Vector3::ZERO:actual.getMinimum(),hi=actual.isNull()?Ogre::Vector3::ZERO:actual.getMaximum();
    const auto down=[](float v){return std::floor(v*1.0e6f)/1.0e6f;};const auto up=[](float v){return std::ceil(v*1.0e6f)/1.0e6f;};
    std::cout<<"BODY_ROW {\""<<model.name<<"\", "<<furnitureTops[band]<<"f, "<<down(lo.x)<<"f, "<<down(lo.y)<<"f, "<<up(hi.x)<<"f, "<<up(hi.y)<<"f, "
     <<(actual.isNull()?"true":"false")<<", "<<down(lo.z)<<"f},\n";
   }
   ++checks;if(low==nullptr){++failures;std::cout<<"FAIL missing body band "<<model.name<<" height="<<furnitureTops[band]<<'\n';continue;}
   ++checks;if(low->empty?!actual.isNull():(actual.isNull()||actual.getMinimum().x<low->minX-margin||
    actual.getMinimum().y<low->minY-margin||actual.getMaximum().x>low->maxX+margin||actual.getMaximum().y>low->maxY+margin||
    actual.getMinimum().z<low->minZ-margin)){
    ++failures;std::cout<<"FAIL body band "<<model.name<<" height="<<furnitureTops[band]<<" "<<actual<<'\n';
   }
  }
  if(profile)for(int joint=0;joint<6;++joint){
   std::cout<<"LEG_PROFILE "<<model.name<<" joint="<<joint;
   if(joints[joint])std::cout<<" bone="<<joints[joint]->getName()<<" bounds="<<jointBounds[joint];else std::cout<<" missing";
   std::cout<<'\n';
  }
  if(std::string(model.name)==boneProfile)for(const auto& part:boneBounds){
   std::cout<<"DOMINANT_BONE "<<model.name<<" bone="<<skeleton->getBone(part.first)->getName()<<" bounds="<<part.second;
   const auto low=lowBoneBounds.find(part.first);
   if(low!=lowBoneBounds.end())std::cout<<" low="<<low->second;
   std::cout<<'\n';
  }
  node->detachAllObjects();scene->destroyEntity(entity);scene->destroySceneNode(node);
 }
 root.destroySceneManager(scene);std::cout<<"CHECKS="<<checks<<" FAILURES="<<failures<<'\n';return failures?1:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
'''
probe = probe.replace('BED_SUPPORT', bed_support).replace('BED_NAMES', ','.join('"' + name + '"' for name in bed_names))
probe = probe.replace('BONE_PROFILE', args.bone_profile or '')
for side in ('left', 'right'):
    for joint in ('Upper', 'Lower', 'Tip'):
        probe = probe.replace(side.upper() + '_' + joint.upper(), 'findBone(skeleton,' + leg_names[(side, joint)] + ')')
with tempfile.TemporaryDirectory(prefix='odp-walking-bounds-') as directory:
    work = Path(directory)
    (work / 'check.cpp').write_text(probe)
    subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', f'/I{repo / "source"}',
                    f'/I{prefix / "include/OGRE"}', 'check.cpp', '/Fecheck.exe', '/link',
                    f'/LIBPATH:{prefix / "lib"}', 'OgreMain.lib'], cwd=work, check=True)
    # The meshes of the content packages are read from their models folders, not only from the public models folder
    package_models = ';'.join(str(folder) for folder in content_packages.data_folders(repo, 'models')
                              if folder != repo / 'models')
    result = subprocess.run([str(work / 'check.exe'), str(repo), str(args.frames), package_models] +
                            (['profile'] if args.height_profile else []), cwd=work, capture_output=True, text=True)
    print('\n'.join(line for line in result.stdout.splitlines() if any(marker in line for marker in ('CHECKS=', 'FAIL ', 'BODY_ROW ', 'FURNITURE_HEIGHT ', 'LEG_PROFILE ', 'DOMINANT_BONE '))))
    if result.returncode:
        if 'FAIL ' not in result.stdout:
            print(result.stderr)
        result.check_returncode()
