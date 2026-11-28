"""Regress the missing hose shaders and cauldron outlet from owner decision 1250.

Runs the production outlet builder and drop selector in a small C++ probe. Shader
bindings, colour flow, resource discovery and attachment lifetime are checked too.
The probe records the resource group of every outlet section and the texture
coordinates of every vertex: each section is looked up in the Graphics group and
every triangle covers texture area, so no part of the outlet is drawn white or flat.
No game build, window or screenshot is needed.

Ghost.material and the hose shaders are content (core-models package, found through scripts/content_packages.py);
without them the shader chain is named as not checked and the code parts and the probe of production code run.
"""
from pathlib import Path
import importlib.util
import re
import sys
import time

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

#: The material script and the shader files of the hose (core-models package)
SHADER_FILES = ("materials/scripts/Ghost.material", "materials/scripts/GhostHose.vert",
                "materials/scripts/GhostHose.frag", "materials/scripts/GhostHoseWire.frag")
spec = importlib.util.spec_from_file_location("ghost_rules", Path(__file__).with_name("check_ghost_rules.py"))
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


# Require the exact authored shader chain so generated unlit passes cannot silently replace the vertex colours.
def shaders():
    # The code side: the viewport scheme, the colours of the hose and the resource folder of the scripts
    assert "mViewport->setMaterialScheme(Ogre::RTShader::ShaderGenerator::DEFAULT_SCHEME_NAME);" in rules.read("source/render/RenderManager.cpp")
    # Since the owner decision of 2026-11-28 the cables of the flat bundle carry the configured colours
    shape = rules.function(rules.read("source/entities/Creature.cpp"), "static void shapeGhostCableBundle(")
    assert "bundle.colour(shadeGhostHose(wearGhostCable(look.mWires[cable],normal,share,cable),normal,look.mGlow));" in shape
    assert "bundle.textureCoord(0.0f,share);" in shape
    assert "FileSystem=materials/scripts" in rules.read("cmake/config/resources.cfg.in")
    missing = [name for name in SHADER_FILES if content_packages.data_file(repo, name) is None]
    if content_packages.unchecked("check_ghost_output_presentation", missing):
        return
    material = content_packages.read_text(repo, "materials/scripts/Ghost.material")
    for name, fragment in (("GhostHose", "GhostHoseFragment"), ("GhostHoseWire", "GhostHoseWireFragment")):
        block = re.search(r"^material " + name + r"\s*\n\{(.*?)^\}", material, re.M | re.S).group(1)
        assert "vertex_program_ref GhostHoseVertex" in block, (name, "missing colour vertex shader")
        assert "fragment_program_ref " + fragment in block, (name, "missing colour fragment shader")
        assert "lighting off" in block
        assert "scheme ShaderGeneratorDefaultScheme" in block, (name, "game viewport must select authored colours directly")
    for program, filename in (("GhostHoseVertex", "GhostHose.vert"), ("GhostHoseFragment", "GhostHose.frag"),
                              ("GhostHoseWireFragment", "GhostHoseWire.frag")):
        assert re.search(r"(?:vertex|fragment)_program " + program + r" glsl\s*\{\s*source " + re.escape(filename), material)
        assert content_packages.resolve(repo, "materials/scripts/" + filename).is_file()
    vertex = content_packages.read_text(repo, "materials/scripts/GhostHose.vert")
    rubber = content_packages.read_text(repo, "materials/scripts/GhostHose.frag")
    wire = content_packages.read_text(repo, "materials/scripts/GhostHoseWire.frag")
    for expected in ("layout(location = 3) in vec4 colour;", "hoseColour = colour;", "gl_Position = worldViewProj * vertex;"):
        assert expected in vertex
    assert "texture(rubberMap, hoseUV).rgb * hoseColour.rgb" in rubber
    assert "fragColour = vec4(hoseColour.rgb, 1.0);" in wire
    assert "param_named_auto worldViewProj worldviewproj_matrix" in material
    assert "param_named rubberMap int 0" in material


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
 struct Vertex {Vector3 p,n;float u=-1.0f,v=-1.0f;};
 struct Section {std::string material,group;std::vector<Vertex> vertices;std::vector<uint32> indices;};
 std::vector<Section> sections;
 void begin(const std::string& material,int,const std::string& group="General"){sections.push_back({material,group,{},{}});}
 void position(float x,float y,float z){sections.back().vertices.push_back({Vector3(x,y,z),Vector3()});}
 void normal(const Vector3& n){sections.back().vertices.back().n=n;}
 void normal(float x,float y,float z){normal(Vector3(x,y,z));}
 void textureCoord(float u,float v){sections.back().vertices.back().u=u;sections.back().vertices.back().v=v;}
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
//! \brief Checks the green liquid in the spout of the closed cauldron mesh (2026-11-28: the spout itself is part of the
//! mesh, its mouth at y 1.0, z 0.14 to 0.31), and floor destinations.
int main(){
 Ogre::ManualObject outlet;buildGhostCauldronOutlet(outlet);
 check(outlet.sections.size()==1,"one outlet surface, the liquid");
 const size_t vertices[]={8},indices[]={12};
 const char* materials[]={"GhostCauldronEctoplasm"};
 for(size_t s=0;s<1;++s){
  const Ogre::ManualObject::Section& section=outlet.sections[s];
  check(section.material==materials[s],"wet liquid");
  check(section.group=="Graphics","outlet material is looked up in the group that loads Ghost.material");
  check(section.vertices.size()==vertices[s]&&section.indices.size()==indices[s],"fixed complete geometry");
  for(const Ogre::ManualObject::Vertex& v:section.vertices){
   check(std::abs(v.p.x)<=.081f&&v.p.y>=.829f&&v.p.y<=1.021f&&v.p.z>=.039f&&v.p.z<=.306f,"liquid in the spout under the glass in the cauldron footprint");
  }
  for(size_t i=0;i<section.indices.size();i+=3){
   const Ogre::ManualObject::Vertex& a=section.vertices.at(section.indices[i]);
   const Ogre::ManualObject::Vertex& b=section.vertices.at(section.indices[i+1]);
   const Ogre::ManualObject::Vertex& c=section.vertices.at(section.indices[i+2]);
   float ux=b.p.x-a.p.x,uy=b.p.y-a.p.y,uz=b.p.z-a.p.z;
   float vx=c.p.x-a.p.x,vy=c.p.y-a.p.y,vz=c.p.z-a.p.z;
   float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
   check(nx*nx+ny*ny+nz*nz>1e-12f,"no degenerate triangles");
   check(a.u>=0.0f&&b.u>=0.0f&&c.u>=0.0f,"every outlet vertex has texture coordinates");
   const float uvArea=(b.u-a.u)*(c.v-a.v)-(c.u-a.u)*(b.v-a.v);
   check(std::abs(uvArea)>1e-6f,"every outlet triangle covers texture area, no flat untextured face");
   check(nx*a.n.x+ny*a.n.y+nz*a.n.z>0,"visible face winding matches its normal");
  }
 }
 const Ogre::ManualObject::Section& liquid=outlet.sections[0];
 check(liquid.vertices[6].p.y==1.02f&&liquid.vertices[7].p.y==1.02f&&
       liquid.vertices[6].p.z==.04f&&liquid.vertices[7].p.z==.04f,
       "green discharge extends outside and below the spout lip");
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
