"""Check what the minimap draws for earth and for tiles the player has never seen.

The production MiniMap::colourFromTile, the shared production terrain colours (MiniMapColours.h/.cpp: the TileColour
struct, the colour constants and terrainColour) and the production TileVisual list are compiled into a small probe
with stand-ins for Tile, Seat and the entities. The probe asks the production function for the colour of:
- a seen solid earth tile and a seen earth floor tile: both brown and opaque;
- an unseen tile of every terrain and room visual (gold, rock, gem, water, lava, mana well, every room), also when the
  tile has an owner, an enemy creature on it or a pickable entity: always the same brown as seen solid earth, and
  opaque on the round minimap (priority above 0, the value both minimap drawers turn into a transparent pixel).

Fixed values of this branch: 38 tile visuals before countTileVisual. The probe compiles with cl, so this check runs in
the compile phase of the integration only.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def block(source, signature):
    """Returns the production text from the signature to the end of its braces block, unchanged."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


minimap_cpp = read('source/gamemap/MiniMap.cpp')
tile_h = read('source/entities/Tile.h')


def without_preprocessor(text):
    """Drops the include and guard lines of a production file; the probe supplies what they bring in."""
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))


production_function = block(minimap_cpp, 'MiniMap::TileColour MiniMap::colourFromTile(')
tile_visual_enum = block(tile_h, 'enum class TileVisual') + ';'
# The shared terrain colours (constants, TileColour struct and terrainColour) used by colourFromTile, unchanged.
colours_h = without_preprocessor(read('source/gamemap/MiniMapColours.h'))
colours_cpp = without_preprocessor(read('source/gamemap/MiniMapColours.cpp'))
assert 'struct MiniMapTileColour' in colours_h and 'MiniMapColours::terrainColour(' in colours_cpp
usings = re.findall(r'^using MiniMapColours::\w+;$', minimap_cpp, re.M)
assert 'using MiniMapColours::DIRT_COLOUR;' in usings, usings
assert 'typedef MiniMapTileColour TileColour;' in read('source/gamemap/MiniMap.h')

visual_names = re.findall(r'^\s*(\w+)(?:\s*=\s*\d+)?,?\s*$', tile_visual_enum[tile_visual_enum.index('{') + 1:], re.M)
assert visual_names[-1] == 'countTileVisual', visual_names
assert len(visual_names) - 1 == 38, len(visual_names)

# Both drawers turn priority 0 into a transparent pixel on the round minimap; the probe relies on that rule.
drawn = read('source/gamemap/MiniMapDrawn.cpp')
drawn_full = read('source/gamemap/MiniMapDrawnFull.cpp')
assert 'circular && colour.priority == 0 ? 0 : 255' in drawn
assert 'if(selected.priority == 0 && mMiniMapWindow->isUserStringDefined("Circular")' in drawn_full

PREAMBLE = r'''
#include <cassert>
#include <cstdio>
#include <vector>

namespace Ogre
{
//! Stand-in for the Ogre colour with the operators the production function uses.
struct ColourValue
{
    float r, g, b, a;
    ColourValue(float red = 0.0f, float green = 0.0f, float blue = 0.0f, float alpha = 1.0f) :
        r(red), g(green), b(blue), a(alpha)
    {}
    ColourValue operator*(float f) const { return ColourValue(r * f, g * f, b * f, a * f); }
    ColourValue operator+(const ColourValue& o) const { return ColourValue(r + o.r, g + o.g, b + o.b, a + o.a); }
    bool operator==(const ColourValue& o) const { return r == o.r && g == o.g && b == o.b; }
    static const ColourValue Black, White, Red, Green, Blue;
};
const ColourValue ColourValue::Black(0.0f, 0.0f, 0.0f);
const ColourValue ColourValue::White(1.0f, 1.0f, 1.0f);
const ColourValue ColourValue::Red(1.0f, 0.0f, 0.0f);
const ColourValue ColourValue::Green(0.0f, 1.0f, 0.0f);
const ColourValue ColourValue::Blue(0.0f, 0.0f, 1.0f);
}

class Player {};

//! Stand-in seat with a fixed colour.
class Seat
{
public:
    Player mPlayer;
    Ogre::ColourValue mColour = Ogre::ColourValue(0.1f, 0.8f, 0.1f);
    bool isRogueSeat() const { return false; }
    const Ogre::ColourValue& getColorValue() const { return mColour; }
    Player* getPlayer() { return &mPlayer; }
};

enum class GameEntityType { creature, treasuryObject };

//! Stand-in entity: a creature of a seat or a pickable object.
class GameEntity
{
public:
    GameEntityType mType = GameEntityType::creature;
    Seat* mSeat = nullptr;
    GameEntityType getObjectType() const { return mType; }
    Seat* getSeat() const { return mSeat; }
    bool tryPickup(Seat*) { return true; }
};
'''

TILE_STUB = r'''
//! Stand-in tile with the state colourFromTile reads.
class Tile
{
public:
    bool mEverVisible = false;
    bool mVision = false;
    TileVisual mVisual = TileVisual::dirtFull;
    Seat* mSeat = nullptr;
    std::vector<GameEntity*> mEntities;
    bool getEverVisible() const { return mEverVisible; }
    bool getLocalPlayerHasVision() const { return mVision; }
    TileVisual getTileVisual() const { return mVisual; }
    Seat* getSeat() const { return mSeat; }
    bool getMarkedForDigging(const Player*) const { return false; }
    const std::vector<GameEntity*>& getEntitiesInTile() const { return mEntities; }
};

//! The production minimap class reduced to the colour function and its result type.
class MiniMap
{
public:
'''

MAIN = r'''
//! True for the dark, saturated brown of earth: red above green above blue, never grey or sandy.
static bool isBrown(const Ogre::ColourValue& c)
{
    return c.r > c.g && c.g > c.b && c.r - c.b >= 0.3f && c.r <= 0.6f;
}

//! Checks the colour of seen earth and of unseen tiles of every visual.
int main()
{
    Seat player;
    Seat enemy;
    enemy.mColour = Ogre::ColourValue(0.9f, 0.1f, 0.1f);

    Tile solid;
    solid.mEverVisible = true;
    solid.mVision = true;
    solid.mVisual = TileVisual::dirtFull;
    const MiniMap::TileColour solidColour = MiniMap::colourFromTile(solid, player, 0);
    assert(isBrown(solidColour.colour) && solidColour.priority > 0);

    Tile floor;
    floor.mEverVisible = true;
    floor.mVision = true;
    floor.mVisual = TileVisual::dirtGround;
    const MiniMap::TileColour floorColour = MiniMap::colourFromTile(floor, player, 0);
    assert(isBrown(floorColour.colour) && floorColour.priority > 0);

    GameEntity enemyCreature;
    enemyCreature.mSeat = &enemy;
    GameEntity object;
    object.mType = GameEntityType::treasuryObject;
    int checked = 0;
    for(int v = 0; v < static_cast<int>(TileVisual::countTileVisual); ++v)
    {
        for(int variant = 0; variant < 4; ++variant)
        {
            for(unsigned int phase = 0; phase < 4; ++phase)
            {
                Tile unseen;
                unseen.mVisual = static_cast<TileVisual>(v);
                if(variant == 1)
                    unseen.mSeat = &enemy;
                if(variant == 2)
                    unseen.mEntities.push_back(&enemyCreature);
                if(variant == 3)
                    unseen.mEntities.push_back(&object);
                const MiniMap::TileColour colour = MiniMap::colourFromTile(unseen, player, phase);
                assert(colour.colour == solidColour.colour);
                assert(colour.priority > 0);
                assert(!colour.animated);
                ++checked;
            }
        }
    }
    assert(checked == 38 * 16);
    std::printf("minimap unseen earth probe passed (%d cases)\n", checked);
    return 0;
}
'''


def main():
    """Compiles and runs the probe of the production minimap colour function."""
    source = (PREAMBLE + tile_visual_enum + '\n' + colours_h + '\n' + colours_cpp + '\n' + TILE_STUB
              + '    typedef MiniMapTileColour TileColour;\n'
              '    static TileColour colourFromTile(Tile& tile, Seat& playerSeat, unsigned int phase);\n};\n\n'
              + '\n'.join(usings) + '\n\n' + production_function + '\n' + MAIN)
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        cpp = directory / 'probe.cpp'
        cpp.write_text(source, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++14 "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)
    print('minimap unseen earth passes the checks')


if __name__ == '__main__':
    main()
