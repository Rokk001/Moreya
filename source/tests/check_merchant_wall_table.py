"""At least two sales tables in a merchant room from 3x3 upward (INGAME-QS-10 K21, owner answer to Q2 "Mindestens zwei"):
one table stands on every 3x3 centre, a second one on a free wall-side tile.

Two parts:
  wiring (no compiler)  RoomMerchant::updateActiveSpots runs the ordinary layout and then updateWallTables on the server;
                        updateWallTables adds a table through MerchantWallTable::choose while the room has a centre and
                        fewer than MIN_SALES_TABLES (2) tables, keeps a loaded wall table (its tile data mTable), and
                        drops its goods when a shelf or the loss of every centre takes its place; getSalesTables,
                        isFurnitureTile and the saved tile record (mTable) include the wall-side table
  probe (cl)            the unchanged production header source/rooms/MerchantWallTable.h is compiled with grids of
                        room, wall, opening and furniture tiles and asserts the chosen tile and angle:
                        - 3x3 room, walls left, top and right, open below, centre table and three shelves: the lower
                          left corner (0, 0), back to the left wall (90 degrees), where a free tile beside it remains
                        - fully walled 3x3 with four shelves: a corner tile is still chosen (at least two tables)
                        - a 3 x 1 row between walls with an opening on the left: the right end (2, 0) is chosen, not the
                          middle (would cut the free floor in two) and not the left end (beside the opening); angle 0
                        - a room with no wall beside it: no tile
Fixed expected values of this branch (counted once): MIN_SALES_TABLES 2, the tiles and angles above.
The probe compiles with cl, so the probe part runs in the compile phase of the integration only.

Call (from the repository root): python source/tests/check_merchant_wall_table.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def body(source, signature):
    """Returns the production text from the signature to the end of its braces block."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


fails = []
room = read('source/rooms/RoomMerchant.cpp')
room_h = read('source/rooms/RoomMerchant.h')
header = read('source/rooms/MerchantWallTable.h')

update = body(room, 'void RoomMerchant::updateActiveSpots(')
if not re.search(r'Room::updateActiveSpots\(gameMap\);\s*if\(!getIsOnServerMap\(\)\)\s*return;\s*updateWallTables\(\);', update):
    fails.append('wiring: updateActiveSpots must run the ordinary layout, then updateWallTables on the server')
wall = body(room, 'void RoomMerchant::updateWallTables(')
if 'MerchantWallTable::choose(roomTiles, cellAt, choice)' not in wall or 'createWallTable(tile, choice.mAngle)' not in wall:
    fails.append('wiring: updateWallTables does not place the chosen wall-side table')
if 'mCentralActiveSpotTiles.size() + wallTables >= MerchantWallTable::MIN_SALES_TABLES' not in wall:
    fails.append('wiring: the second table is not added up to MIN_SALES_TABLES')
if not re.search(r'if\(mCentralActiveSpotTiles\.empty\(\) \|\| shelf\)\s*\{\s*releaseTableGoods\(tile\);', wall):
    fails.append('wiring: a wall table that loses its place must drop its goods as sealed bags')
if 'getBuildingObjectFromTile(tile) == nullptr' not in wall:
    fails.append('wiring: a loaded wall table (mTable in the save) does not get its table object back')
if not re.search(r'static const unsigned int MIN_SALES_TABLES = 2;', header):
    fails.append('wiring: MIN_SALES_TABLES must be 2 (owner answer "Mindestens zwei")')
sales = body(room, 'std::vector<Tile*> RoomMerchant::getSalesTables(')
if '->mTable && !isCentreTable(tile)' not in sales:
    fails.append('wiring: getSalesTables misses the wall-side table (the merchant would never visit it)')
furniture = body(room, 'bool RoomMerchant::isFurnitureTile(')
if '->mTable' not in furniture:
    fails.append('wiring: isFurnitureTile misses the wall-side table (the merchant would walk through it)')
created = body(room, 'BuildingObject* RoomMerchant::notifyActiveSpotCreated(')
if 'removeBuildingObject(tile)' not in created or 'releaseTableGoods(tile)' not in created:
    fails.append('wiring: a centre table or shelf taking the tile of the wall table must replace it')
if 'void updateActiveSpots(GameMap* gameMap = nullptr) override;' not in room_h:
    fails.append('wiring: RoomMerchant does not override updateActiveSpots')
if 'stream << " MerchantGoods " << data->mTable' not in room:
    fails.append('wiring: the table flag of every tile (the wall table too) must stay in the save')
if 'rooms/MerchantWallTable.h' not in read('CMakeLists.txt'):
    fails.append('wiring: MerchantWallTable.h is not in the source list')
if fails:
    print('FAIL')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('merchant wall table wiring ok')

MAIN = r'''
#include <cassert>
#include <cstdio>
#include <map>

//! A test grid: every listed tile has its kind, every other tile is an opening (outside).
struct Grid
{
    std::map<std::pair<int, int>, MerchantCell> mCells;
    std::vector<std::pair<int, int>> mRoom;
    //! Adds a tile of the room (free floor or furniture), in the order the room lists its tiles.
    void room(int x, int y, MerchantCell kind) { mCells[std::make_pair(x, y)] = kind; mRoom.push_back(std::make_pair(x, y)); }
    //! Adds a wall tile.
    void wall(int x, int y) { mCells[std::make_pair(x, y)] = MerchantCell::wall; }
    //! Returns the kind of a tile.
    MerchantCell at(int x, int y) const
    {
        std::map<std::pair<int, int>, MerchantCell>::const_iterator it = mCells.find(std::make_pair(x, y));
        return it == mCells.end() ? MerchantCell::outside : it->second;
    }
};

//! Builds a 3x3 room (tiles 0..2) with its centre table; shelves on the given tiles; walls on the given sides.
static Grid room3x3(bool left, bool top, bool right, bool bottom)
{
    Grid g;
    for(int x = 0; x < 3; ++x)
        for(int y = 0; y < 3; ++y)
        {
            bool shelf = (x == 0 && y == 1 && left) || (x == 1 && y == 2 && top) || (x == 2 && y == 1 && right) ||
                (x == 1 && y == 0 && bottom);
            g.room(x, y, (x == 1 && y == 1) || shelf ? MerchantCell::furniture : MerchantCell::floor);
        }
    for(int i = -1; i <= 3; ++i)
    {
        if(left) g.wall(-1, i);
        if(right) g.wall(3, i);
        if(top) g.wall(i, 3);
        if(bottom) g.wall(i, -1);
    }
    return g;
}

//! Runs the production choice on a grid.
static bool run(const Grid& g, MerchantWallTableChoice& choice)
{
    const std::function<MerchantCell(int, int)> cellAt = std::bind(&Grid::at, &g, std::placeholders::_1, std::placeholders::_2);
    return MerchantWallTable::choose(g.mRoom, cellAt, choice);
}

//! Checks the chosen tile and angle in the four rooms of the docstring.
int main()
{
    assert(MerchantWallTable::MIN_SALES_TABLES == 2);
    MerchantWallTableChoice choice;

    // 3x3, walls left, top, right, open below: lower left corner, back to the left wall
    assert(run(room3x3(true, true, true, false), choice));
    assert(choice.mX == 0 && choice.mY == 0 && choice.mAngle == 90.0f);

    // fully walled 3x3 with four shelves: still a corner, so the room shows two tables
    assert(run(room3x3(true, true, true, true), choice));
    assert((choice.mX == 0 || choice.mX == 2) && (choice.mY == 0 || choice.mY == 2));

    // 3 x 1 row between walls, opening on the left: the right end, back to the top wall
    Grid row;
    for(int x = 0; x < 3; ++x)
    {
        row.room(x, 0, MerchantCell::floor);
        row.wall(x, 1);
        row.wall(x, -1);
    }
    row.wall(3, 0);
    assert(run(row, choice));
    assert(choice.mX == 2 && choice.mY == 0 && choice.mAngle == 0.0f);

    // no wall beside the room: no wall-side tile
    Grid open;
    for(int x = 0; x < 3; ++x)
        for(int y = 0; y < 3; ++y)
            open.room(x, y, x == 1 && y == 1 ? MerchantCell::furniture : MerchantCell::floor);
    assert(!run(open, choice));

    std::printf("merchant wall table probe passed\n");
    return 0;
}
'''


def main():
    """Compiles and runs the probe of the production wall-table choice."""
    source = header + '\n' + MAIN
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
    print('merchant wall table passes the checks')


if __name__ == '__main__':
    main()
