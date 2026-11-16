"""Regress the missing hose shaders and cauldron outlet from owner decision 1250.

Runs the production outlet builder and drop selector in a small C++ probe. Shader
bindings, colour flow, resource discovery and attachment lifetime are checked too.
No game build, window or screenshot is needed.
"""
from pathlib import Path
import importlib.util
import re
import time

repo = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ghost_rules", Path(__file__).with_name("check_ghost_rules.py"))
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


# Require the exact authored shader chain so generated unlit passes cannot silently replace the vertex colours.
def shaders():
    material = rules.read("materials/scripts/Ghost.material")
    for name, fragment in (("GhostHose", "GhostHoseFragment"), ("GhostHoseWire", "GhostHoseWireFragment")):
        block = re.search(r"^material " + name + r"\s*\n\{(.*?)^\}", material, re.M | re.S).group(1)
        assert "vertex_program_ref GhostHoseVertex" in block, (name, "missing colour vertex shader")
        assert "fragment_program_ref " + fragment in block, (name, "missing colour fragment shader")
        assert "lighting off" in block
        assert "scheme ShaderGeneratorDefaultScheme" in block, (name, "game viewport must select authored colours directly")
    assert "mViewport->setMaterialScheme(Ogre::RTShader::ShaderGenerator::DEFAULT_SCHEME_NAME);" in rules.read("source/render/RenderManager.cpp")
    for program, filename in (("GhostHoseVertex", "GhostHose.vert"), ("GhostHoseFragment", "GhostHose.frag"),
                              ("GhostHoseWireFragment", "GhostHoseWire.frag")):
        assert re.search(r"(?:vertex|fragment)_program " + program + r" glsl\s*\{\s*source " + re.escape(filename), material)
        assert (repo / "materials/scripts" / filename).is_file()
    vertex = rules.read("materials/scripts/GhostHose.vert")
    rubber = rules.read("materials/scripts/GhostHose.frag")
    wire = rules.read("materials/scripts/GhostHoseWire.frag")
    for expected in ("layout(location = 3) in vec4 colour;", "hoseColour = colour;", "gl_Position = worldViewProj * vertex;"):
        assert expected in vertex
    assert "texture(rubberMap, hoseUV).rgb * hoseColour.rgb" in rubber
    assert "fragColour = vec4(hoseColour.rgb, 1.0);" in wire
    assert "param_named_auto worldViewProj worldviewproj_matrix" in material
    assert "param_named rubberMap int 0" in material
    shape = rules.function(rules.read("source/entities/Creature.cpp"), "static void shapeGhostHose(")
    assert "hose.colour(shadeGhostHose(look.mWires[wire],normal,look.mGlow));" in shape
    assert "hose.textureCoord(0.0f,share);" in shape
    assert "FileSystem=materials/scripts" in rules.read("cmake/config/resources.cfg.in")


# Keep the permanent outlet independent of the fill height, and release it on reload, sale and destruction.
def lifetime():
    building = rules.read("source/entities/BuildingObject.cpp")
    create = rules.function(building, "void BuildingObject::createMeshLocal(")
    destroy = rules.function(building, "void BuildingObject::destroyMeshLocal(")
    assert create.index('getMeshName()=="GhostCauldron"') < create.index("buildGhostCauldronOutlet(*mGhostOutlet);") < create.index('getMeshName()=="GhostHook"')
    assert "getEntityNode()->attachObject(mGhostOutlet);" in create
    assert "mGhostFillNode->attachObject(mGhostOutlet)" not in create
    assert "mGhostOutlet->detachFromParent();" in destroy
    assert "destroyManualObject(mGhostOutlet);mGhostOutlet=nullptr;" in destroy
    assert destroy.index("destroyManualObject(mGhostOutlet)") < destroy.index("RenderedMovableEntity::destroyMeshLocal(type);")
    produce = rules.function(rules.read("source/rooms/RoomGhostRoom.cpp"), "void RoomGhostRoom::produceEctoplasm(")
    assert "findDropTile(cauldron,0.5)" in produce
    assert "spawnItem(*drop,ItemInstance::createGhostItem(GhostItem::ectoplasm),seat);" in produce
    assert "if(drop==nullptr) break;" in produce, "a full room must retain its ectoplasm"


# Execute actual geometry and floor selection, observing fixed dimensions, open bore, winding and obstacle exclusions.
def geometry_and_drop():
    code = r"""
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <algorithm>
//! \brief Fails the focused production probe on an unexpected observation.
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
namespace Ogre {
using uint32=uint32_t;
//! \brief Records the production mesh coordinates and normals.
struct Vector3 {float x,y,z;Vector3(float a=0,float b=0,float c=0):x(a),y(b),z(c){}static const Vector3 UNIT_Y,UNIT_Z;};
const Vector3 Vector3::UNIT_Y(0,1,0),Vector3::UNIT_Z(0,0,1);
struct Math {static constexpr float TWO_PI=6.283185307179586f;};
struct RenderOperation {enum {OT_TRIANGLE_LIST};};
//! \brief Captures actual vertex and index emissions without replacing the geometry builder.
struct ManualObject {
 struct Vertex {Vector3 p,n;};
 struct Section {std::string material;std::vector<Vertex> vertices;std::vector<uint32> indices;};
 std::vector<Section> sections;
 void begin(const std::string& material,int){sections.push_back({material,{},{}});}
 void position(float x,float y,float z){sections.back().vertices.push_back({Vector3(x,y,z),Vector3()});}
 void normal(const Vector3& n){sections.back().vertices.back().n=n;}
 void normal(float x,float y,float z){normal(Vector3(x,y,z));}
 void textureCoord(float,float){}
 void triangle(uint32 a,uint32 b,uint32 c){std::vector<uint32>& i=sections.back().indices;i.insert(i.end(),{a,b,c});}
 void end(){}
};
}
//! \brief Supplies fixed floor coordinates for the unchanged placement body.
struct Tile {int x,y;int getX()const{return x;}int getY()const{return y;}};
//! \brief Provides only the containers consumed by the production drop selector.
struct RoomGhostRoom {
 struct Cauldron {Tile* anchor;};struct Apparatus {Tile* tile;};
 std::vector<Tile*> mCoveredTiles;std::vector<Cauldron> mCauldrons;std::vector<Apparatus> mApparatuses;
 Tile* findDropTile(const Tile&,double)const;
};
"""
    room = rules.read("source/rooms/RoomGhostRoom.cpp")
    code += rules.function(rules.read("source/entities/BuildingObject.cpp"), "static void buildGhostCauldronOutlet(")
    code += rules.function(room, "bool tileOrder(")
    code += rules.function(room, "Tile* RoomGhostRoom::findDropTile(")
    code += r"""
//! \brief Checks the actual brass spout, open dark bore, green liquid, and floor destinations.
int main(){
 Ogre::ManualObject outlet;buildGhostCauldronOutlet(outlet);
 check(outlet.sections.size()==3,"three outlet surfaces");
 const size_t vertices[]={150,50,8},indices[]={720,144,12};
 const char* materials[]={"GhostBrass","GhostIron","GhostCauldronEctoplasm"};
 for(size_t s=0;s<3;++s){
  const Ogre::ManualObject::Section& section=outlet.sections[s];
  check(section.material==materials[s],"brass casing, dark bore, wet liquid");
  check(section.vertices.size()==vertices[s]&&section.indices.size()==indices[s],"fixed complete geometry");
  for(const Ogre::ManualObject::Vertex& v:section.vertices){
   check(std::abs(v.p.x)<=.201f&&v.p.y>=.479f&&v.p.y<=.991f&&v.p.z>=.039f&&v.p.z<=.481f,"outlet under the glass in the cauldron footprint");
  }
  for(size_t i=0;i<section.indices.size();i+=3){
   const Ogre::ManualObject::Vertex& a=section.vertices.at(section.indices[i]);
   const Ogre::ManualObject::Vertex& b=section.vertices.at(section.indices[i+1]);
   const Ogre::ManualObject::Vertex& c=section.vertices.at(section.indices[i+2]);
   float ux=b.p.x-a.p.x,uy=b.p.y-a.p.y,uz=b.p.z-a.p.z;
   float vx=c.p.x-a.p.x,vy=c.p.y-a.p.y,vz=c.p.z-a.p.z;
   float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
   check(nx*nx+ny*ny+nz*nz>1e-12f,"no degenerate triangles");
   if(s==0&&i>=576)check(ny>0,"lip faces out of the open bore");
   else check(nx*a.n.x+ny*a.n.y+nz*a.n.z>0,"visible face winding matches its normal");
   if(s==0&&i>=576)for(const Ogre::ManualObject::Vertex* v:{&a,&b,&c})
    check(v->p.x*v->p.x+(v->p.z-.28f)*(v->p.z-.28f)>=.00999f,"lip leaves the bore open");
  }
 }
 const Ogre::ManualObject::Section& liquid=outlet.sections[2];
 check(liquid.vertices[6].p.y==.99f&&liquid.vertices[7].p.y==.99f&&
       liquid.vertices[6].p.z==.04f&&liquid.vertices[7].p.z==.04f,
       "green discharge extends outside and below the brass lip");
 Tile anchor{0,0},back{0,-1},front{0,2},frontRight{1,2},side{-1,1},inside{0,1};
 RoomGhostRoom room;room.mCauldrons.push_back({&anchor});
 room.mCoveredTiles={&back,&front,&frontRight,&side,&inside};
 check(room.findDropTile(anchor,.5)==&front,"ectoplasm exits beside the +y outlet, not the opposite side");
 room.mApparatuses.push_back({&front});
 check(room.findDropTile(anchor,.5)==&frontRight,"an apparatus cannot receive the floor drop");
 room.mApparatuses.push_back({&frontRight});
 check(room.findDropTile(anchor,.5)==&side,"blocked outlet falls back to nearest free floor");
 room.mCoveredTiles={&inside};check(room.findDropTile(anchor,.5)==nullptr,"never drop inside cauldron footprint");
 room.mCoveredTiles={&back,&front};room.mApparatuses.clear();
 check(room.findDropTile(anchor,0)==&back,"apparatus output keeps its original nearest-floor rule");
 std::cout<<"production outlet geometry, face winding and floor drop selection: ok\n";
}
"""
    rules.run_probe("ghost-output", code)


# Report actual wall time for the targeted command without a build or observation delay.
def main():
    start = time.monotonic()
    shaders()
    lifetime()
    geometry_and_drop()
    print(f"ghost output presentation: ok ({time.monotonic()-start:.3f}s)")


if __name__ == "__main__":
    main()
