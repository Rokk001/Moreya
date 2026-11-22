"""Check: the plausible editor audit findings (package 5), each proven or disproven.

    python source/tests/check_editor_findings.py        (cl must be on the path: run it under vcvars64)

Requirements checked (each reported on its own, expected values are fixed):
  F1  seat ids with gaps: the pool of the ever visited tiles has a slot for the highest seat id of the level, not
      only for the number of seats (compiled probe on the production blocks of MapHandler.cpp: seats 1, 2, 5 need
      6 slots, seats 1, 2 keep 3); a negative seat id is refused like seat id 0 (static)
  F2  no defect: the trap copy (tile - x1) and the room copy (tile - container position) use the same offset,
      because the server sets the container position only when it creates it, from the same corner the client
      sends with the reveal requests, and the client sends these requests right after the creation; the seat of a
      copied trap is checked for null (static)
  F3  the editor builders of rooms and traps read every tile of the request before they change one, and delete the
      room or trap they were given when they fail (compiled probe on the production functions of RoomManager.cpp
      and TrapManager.cpp)
  F4  a click in the editor picks the tile on the same plane as the hover (KEEPER_HAND_WORLD_Z), not on the plane
      of the copy block (static)
  F5  importWaveConfig drops target team 0 and creature class names the level file cannot hold (empty or with
      white space); the production loader cannot read back an empty class name (compiled probes on
      PortalWaveRules.h and on the production loader and writer blocks of RoomPortalWave.cpp)
  F6  "Save as" with a name that names no file is refused by the server with a message, and the client keeps the
      map marked as modified then (compiled probe on LevelFileNameInput.h, static wiring)
  F7  the New dialogs of EditorMode and MenuModeEditorNew accept only a plain file name (no folder, no "..")
      and say so in their message field (compiled probe on LevelFileNameInput.h, static wiring)
It compiles five small probes with cl, in parallel, and starts no game."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[2]
started = time.monotonic()
failures = []


def check(condition, message):
    """Records a failed requirement."""
    if not condition:
        failures.append(message)


def strip_comments(text):
    """Removes C++ comments so that a requirement is not met by a comment."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def read(path):
    """Reads a repository file without comments."""
    return strip_comments((repo / path).read_text(encoding='utf-8', errors='replace'))


def function(text, start_text):
    """Returns the brace-matched block that starts at the first start_text, or '' when it is missing."""
    start = text.find(start_text)
    if start == -1:
        return ''
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def before(text, first, second):
    """True when both texts occur and first comes first."""
    a, b = text.find(first), text.find(second)
    return a != -1 and b != -1 and a < b


def run_probe(name, code):
    """Compiles one probe with cl, runs it and returns (ok, output)."""
    with tempfile.TemporaryDirectory(prefix='odp-' + name + '-') as directory:
        work = Path(directory)
        source = work / (name + '.cpp')
        source.write_text(code, encoding='utf-8')
        binary = work / (name + '.exe')
        command = ['cl', '/nologo', '/EHsc', '/MD', '/std:c++14', '/I' + str(repo / 'source'), str(source),
                   '/Fe:' + str(binary)]
        try:
            build = subprocess.run(command, cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                   timeout=300)
        except FileNotFoundError:
            return False, 'cl not found: run this check under vcvars64'
        if build.returncode != 0:
            return False, 'compile failed: ' + '\n'.join(l for l in build.stdout.splitlines() if 'error' in l)[:1200]
        run = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                             timeout=60)
        return run.returncode == 0, run.stdout + run.stderr


maphandler = read('source/gamemap/MapHandler.cpp')
seat_cpp = read('source/game/Seat.cpp')
server = read('source/network/ODServer.cpp')
client = read('source/network/ODClient.cpp')
editor = read('source/modes/EditorMode.cpp')
menu_new = read('source/modes/MenuModeEditorNew.cpp')
tile_marker = read('source/gamemap/TileMarker.h')
room_manager = read('source/rooms/RoomManager.cpp')
trap_manager = read('source/traps/TrapManager.cpp')
portal_wave = read('source/rooms/RoomPortalWave.cpp')
probes = {}

# ---------------------------------------------------------------- F1
scan = function(maphandler, 'void getXandYandSeatsNumber(')
load_start = maphandler.find('int mapSizeX;')
pool_call = maphandler.find('initializeEverVisitedFlagTilesPools(', load_start)
load_block = maphandler[load_start:maphandler.index(';', pool_call) + 1] if load_start != -1 and pool_call != -1 else ''
check(scan != '' and load_block != '', 'F1 MapHandler.cpp has getXandYandSeatsNumber and the pool set-up of the loader')
F1_PROBE = r'''
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#define OD_ASSERT_TRUE_MSG(a, b) (void)0
static const int MAX_MAP_SIDE = 4096;
//! \brief Number formatting of the messages.
struct Helper { static std::string toString(int value) { std::ostringstream s; s << value; return s.str(); } };
//! \brief Load errors are printed.
static void setLoadError(const std::string& text) { std::cout << "loaderror " << text << std::endl; }
//! \brief Records the number of seat slots the loader asks for.
struct GameMapStub
{
    uint32_t mSlots = 0;
    void initializeEverVisitedFlagTilesPools(uint32_t, uint32_t, uint32_t nbSeats) { mSlots = nbSeats; }
};
@@SCAN@@
//! \brief The production block of readGameMapFromFile up to the pool set-up.
static bool loadBlock(std::stringstream& levelFile, GameMapStub& gameMap, const std::string& fileName)
{
@@BLOCK@@
    return true;
}
//! \brief Loads the seat part of a level and returns the slots of the pool.
static uint32_t slots(const std::string& level)
{
    std::stringstream levelFile(level);
    GameMapStub gameMap;
    if(!loadBlock(levelFile, gameMap, "probe.level"))
        return 0;
    return gameMap.mSlots;
}
int main()
{
    const std::string head = "OpenDungeons_Version:0.7.1\n[Info]\nName\tProbe\n[/Info]\n[Seats]\n";
    const std::string tail = "[/Seats]\n[Goals]\n[/Goals]\n[Tiles]\n3 3\n[/Tiles]\n";
    std::string gap = head;
    gap += "[Seat]\nseatId\t1\nteamId\t1\nplayer\tHuman\n";
    gap += "[Seat]\nseatId\t2\nteamId\t2\nplayer\tAI\n";
    gap += "[Seat]\nseatId\t5\nteamId\t5\nplayer\tAI\n" + tail;
    std::string plain = head;
    plain += "[Seat]\nseatId\t1\nteamId\t1\nplayer\tHuman\n";
    plain += "[Seat]\nseatId\t2\nteamId\t2\nplayer\tAI\n" + tail;
    std::cout << "gap=" << slots(gap) << " plain=" << slots(plain) << std::endl;
    return 0;
}
'''
probes['f1'] = F1_PROBE.replace('@@SCAN@@', scan).replace('@@BLOCK@@', load_block)
import_seat = function(seat_cpp, 'bool Seat::importSeatFromStream(')
check(re.search(r'if\s*\(\s*mId\s*<=\s*0\s*\)', import_seat) is not None,
      'F1 Seat::importSeatFromStream refuses a seat id below 1 (negative ids index the pool too)')

# ---------------------------------------------------------------- F2
create = function(server, 'case ClientNotificationType::editorAskCreateDraggableTileContainer:')
check(server.count('mDraggableTileContainer->setPosition(') == 1
      and 'mDraggableTileContainer->setPosition(Ogre::Vector2(posX,posY))' in create
      and before(create, 'mDraggableTileContainer==nullptr', 'setPosition('),
      'F2 the server sets the copy block position only when it creates the block, from posX/posY of the request')
copy = function(editor, 'void EditorMode::onEditCopy(')
check(re.search(r'std::min\(mTileMarker\.mark\.x,\s*mTileMarker\.point\.x\)', copy) is not None
      and re.search(r'std::min\(mTileMarker\.mark\.y,\s*mTileMarker\.point\.y\)', copy) is not None
      and 'mTileMarker.getMinX()' in copy and 'mTileMarker.getMinY()' in copy
      and re.search(r'getMinX\(\)\s*\{\s*return\s+std::min\(point\.x,\s*mark\.x\);', tile_marker) is not None
      and re.search(r'getMinY\(\)\s*\{\s*return\s+std::min\(point\.y,\s*mark\.y\);', tile_marker) is not None,
      'F2 onEditCopy sends the same corner as the block position and as the minimum of the marked area')
ping = function(client, 'case ServerNotificationType::pingCreateDraggableTileContainer:')
check(client.count('ClientNotificationType::editorAskRevealTraps') == 1
      and client.count('ClientNotificationType::editorAskRevealRooms') == 1
      and before(ping, 'setPosition(', 'editorAskRevealTraps') and before(ping, 'setPosition(', 'editorAskRevealRooms'),
      'F2 the client asks for the traps and rooms only right after the copy block was created')
reveal_traps = function(server, 'case ClientNotificationType::editorAskRevealTraps:')
copy_trap = function(server, 'case ClientNotificationType::editorAskCopyTrap:')
check('int32_t offset_x = tile->getX() - x1;' in reveal_traps
      and 'tile->getX() -  mDraggableTileContainer->getPosition().x' in function(
          server, 'case ClientNotificationType::editorAskRevealRooms:'),
      'F2 the trap copy is offset by x1, the room copy by the container position (equal by the rules above)')
for label, body in (('editorAskRevealTraps', reveal_traps), ('editorAskCopyTrap', copy_trap)):
    check(re.search(r'trap->getSeat\(\)\s*==\s*nullptr\s*\)?\s*\?\s*-1', body) is not None
          and len(re.findall(r'trap->getSeat\(\)->', body)) == 1,
          'F2 %s checks the seat of the trap for null before it reads its id' % label)

# ---------------------------------------------------------------- F3
F3_HEAD = r'''
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#define OD_ASSERT_TRUE(x) (void)(x)
#define OD_LOG_ERR(x) (void)0
//! \brief Number formatting of the messages.
struct Helper { static std::string toString(int value) { std::ostringstream s; s << value; return s.str(); } };
enum class TileType { dirt, gold, rock };
//! \brief A seat.
struct Seat { int mId; };
//! \brief A tile that counts its changes.
struct Tile
{
    TileType mType = TileType::rock;
    int mChanges = 0;
    void* mBuilding = nullptr;
    void* getCoveringBuilding() const { return mBuilding; }
    TileType getType() const { return mType; }
    void setType(TileType type) { mType = type; ++mChanges; }
    void setFullness(double) { ++mChanges; }
    void claimTile(Seat*) { ++mChanges; }
    void computeTileVisual() {}
    static std::string displayAsString(const Tile*) { return "tile"; }
};
//! \brief A packet of numbers.
struct ODPacket
{
    std::vector<int32_t> mValues;
    size_t mPos = 0;
    bool read(int32_t& value) { if(mPos >= mValues.size()) return false; value = mValues[mPos++]; return true; }
    ODPacket& operator>>(int32_t& value) { read(value); return *this; }
    ODPacket& operator>>(uint32_t& value) { int32_t v = 0; read(v); value = static_cast<uint32_t>(v); return *this; }
};
//! \brief A 4x4 map with seat 1.
struct GameMap
{
    Seat mSeat;
    Tile mTiles[16];
    GameMap() { mSeat.mId = 1; }
    Seat* getSeatById(int id) { return (id == 1) ? &mSeat : nullptr; }
    Tile* tileFromPacket(ODPacket& packet)
    {
        int32_t x = -1;
        int32_t y = -1;
        packet >> x >> y;
        if((x < 0) || (y < 0) || (x >= 4) || (y >= 4))
            return nullptr;
        return &mTiles[x + 4 * y];
    }
};
static int deletedBuildings = 0;
static int addedBuildings = 0;
//! \brief A room or trap that counts its deletion.
struct Building
{
    ~Building() { ++deletedBuildings; }
    std::string getName() const { return "building"; }
};
typedef Building Room;
typedef Building Trap;
//! \brief The default builders: nothing to build without tiles, otherwise the map owns the building.
static bool buildRoomDefault(GameMap*, Room*, Seat*, const std::vector<Tile*>& tiles)
{
    if(tiles.empty())
        return false;
    ++addedBuildings;
    return true;
}
//! \brief The trap variant of the default builder.
static bool buildTrapDefault(GameMap*, Trap*, Seat*, const std::vector<Tile*>& tiles)
{
    return buildRoomDefault(nullptr, nullptr, nullptr, tiles);
}
'''
F3_MAIN = r'''
typedef bool (*Builder)(GameMap*, Building*, ODPacket&);
//! \brief Runs one request and prints result, changed tiles, deleted and added buildings.
static void runCase(const char* label, Builder builder, int32_t seatId, const std::vector<int32_t>& tiles,
                    bool coverAll)
{
    GameMap gameMap;
    Building marker;
    if(coverAll)
    {
        for(int i = 0; i < 16; ++i)
            gameMap.mTiles[i].mBuilding = &marker;
    }
    ODPacket packet;
    packet.mValues.push_back(seatId);
    packet.mValues.push_back(static_cast<int32_t>(tiles.size() / 2));
    packet.mValues.insert(packet.mValues.end(), tiles.begin(), tiles.end());
    deletedBuildings = 0;
    addedBuildings = 0;
    Building* building = new Building;
    bool result = builder(&gameMap, building, packet);
    int changed = 0;
    for(int i = 0; i < 16; ++i)
        changed += (gameMap.mTiles[i].mChanges > 0) ? 1 : 0;
    std::cout << label << " result=" << result << " changed=" << changed << " deleted=" << deletedBuildings
              << " added=" << addedBuildings << std::endl;
    if(addedBuildings > 0)
        delete building;
}
int main()
{
    const int32_t goodTiles[] = {0, 0, 1, 0};
    const int32_t badTiles[] = {0, 0, 1, 0, 9, 9};
    std::vector<int32_t> good(goodTiles, goodTiles + 4);
    std::vector<int32_t> bad(badTiles, badTiles + 6);
    runCase("room-good", buildRoomDefaultEditor, 1, good, false);
    runCase("room-nulltile", buildRoomDefaultEditor, 1, bad, false);
    runCase("room-noseat", buildRoomDefaultEditor, 7, good, false);
    runCase("room-covered", buildRoomDefaultEditor, 1, good, true);
    runCase("trap-good", buildTrapDefaultEditor, 1, good, false);
    runCase("trap-nulltile", buildTrapDefaultEditor, 1, bad, false);
    runCase("trap-noseat", buildTrapDefaultEditor, 7, good, false);
    runCase("trap-covered", buildTrapDefaultEditor, 1, good, true);
    return 0;
}
'''


def free_builder(text, signature):
    """Cuts a production builder out of its file and turns it into a free function of the probe."""
    body = function(text, signature)
    body = body.replace('RoomFactory::', '').replace('TrapFactory::', '')
    return re.sub(r'\)\s*const\s*\{', ') {', body, count=1)


room_builder = free_builder(room_manager, 'bool RoomFactory::buildRoomDefaultEditor(')
trap_builder = free_builder(trap_manager, 'bool TrapFactory::buildTrapDefaultEditor(')
check(room_builder != '' and trap_builder != '', 'F3 RoomManager.cpp and TrapManager.cpp have the editor builders')
probes['f3'] = F3_HEAD + room_builder + '\n' + trap_builder + '\n' + F3_MAIN

# ---------------------------------------------------------------- F4
pressed = function(editor, 'bool EditorMode::mousePressed(')
moved = function(editor, 'bool EditorMode::mouseMoved(')
check(pressed.count('findWorldPositionFromMouse(') == 1 and 'RenderManager::KEEPER_HAND_WORLD_Z' in pressed
      and 'Draggable_scene_node' not in pressed,
      'F4 mousePressed picks the clicked tile only on the KEEPER_HAND_WORLD_Z plane, not on the copy block plane')
check('RenderManager::KEEPER_HAND_WORLD_Z' in moved, 'F4 mouseMoved shows the hovered tile on the same plane')

# ---------------------------------------------------------------- F5
rules_header = repo / 'source/rooms/PortalWaveRules.h'
check(rules_header.exists(), 'F5 source/rooms/PortalWaveRules.h exists')
F5_PROBE = r'''
#include "rooms/PortalWaveRules.h"
#include <iostream>
#include <string>
int main()
{
    int failures = 0;
    failures += PortalWaveRules::isTargetTeamAllowed(0) ? 1 : 0;
    failures += PortalWaveRules::isTargetTeamAllowed(1) ? 0 : 1;
    failures += PortalWaveRules::isTargetTeamAllowed(7) ? 0 : 1;
    failures += PortalWaveRules::isTargetTeamAllowed(-2) ? 0 : 1;
    failures += PortalWaveRules::isStorableClassName("") ? 1 : 0;
    failures += PortalWaveRules::isStorableClassName(" ") ? 1 : 0;
    failures += PortalWaveRules::isStorableClassName("Dark Elf") ? 1 : 0;
    failures += PortalWaveRules::isStorableClassName("Orc\t") ? 1 : 0;
    failures += PortalWaveRules::isStorableClassName("Line\nBreak") ? 1 : 0;
    failures += PortalWaveRules::isStorableClassName("Orc") ? 0 : 1;
    failures += PortalWaveRules::isStorableClassName("Wizard_2") ? 0 : 1;
    std::cout << "rules failures=" << failures << std::endl;
    return 0;
}
'''
if rules_header.exists():
    probes['f5'] = F5_PROBE
import_body = function(portal_wave, 'bool RoomPortalWave::importFromStream(')
loader_loop = function(import_body, 'while(true)\n        {\n            if(!(is >> str))')
if loader_loop == '':
    loader_loop = function(import_body[import_body.find('"[Creatures]"'):], 'while(true)')
export_body = function(portal_wave, 'void RoomPortalWave::exportToStream(')
writer_loop = function(export_body, 'for(const std::pair<std::string, uint32_t>& p : roomPortalWaveData->mSpawnCreatureClassName)')
check('p.first = str;' in loader_loop and 'os << p.first' in writer_loop,
      'F5 RoomPortalWave.cpp has the creature loader loop and writer loop')
F5B_PROBE = r'''
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
//! \brief The creatures of one wave.
struct WaveStub { std::vector<std::pair<std::string, uint32_t> > mSpawnCreatureClassName; };
//! \brief The production writer loop of exportToStream.
static void writeCreatures(std::ostream& os, const WaveStub* roomPortalWaveData)
{
@@WRITER@@
    os << "[/Creatures]" << "\n";
}
//! \brief The production loader loop of importFromStream.
static bool readCreatures(std::istream& is, WaveStub* roomPortalWaveData)
{
    std::string str;
@@LOADER@@
    return true;
}
//! \brief True when the creatures read back equal the ones written.
static bool roundTrip(const WaveStub& wave)
{
    std::stringstream file;
    writeCreatures(file, &wave);
    WaveStub back;
    return readCreatures(file, &back) && (back.mSpawnCreatureClassName == wave.mSpawnCreatureClassName);
}
int main()
{
    WaveStub plain;
    plain.mSpawnCreatureClassName.push_back(std::make_pair(std::string("Orc"), 2u));
    plain.mSpawnCreatureClassName.push_back(std::make_pair(std::string("Wizard"), 3u));
    WaveStub empty;
    empty.mSpawnCreatureClassName.push_back(std::make_pair(std::string(""), 3u));
    empty.mSpawnCreatureClassName.push_back(std::make_pair(std::string("Orc"), 2u));
    std::cout << "plain=" << roundTrip(plain) << " empty=" << roundTrip(empty) << std::endl;
    return 0;
}
'''
probes['f5b'] = F5B_PROBE.replace('@@WRITER@@', writer_loop).replace('@@LOADER@@', loader_loop)
wave_import = function(portal_wave, 'void RoomPortalWave::importWaveConfig(')
check('PortalWaveRules::isTargetTeamAllowed(' in wave_import and 'PortalWaveRules::isStorableClassName(' in wave_import,
      'F5 importWaveConfig drops team 0 and class names the level file cannot hold')

# ---------------------------------------------------------------- F6 / F7
name_header = repo / 'source/utils/LevelFileNameInput.h'
check(name_header.exists(), 'F6/F7 source/utils/LevelFileNameInput.h exists')
F67_PROBE = r'''
#include "utils/LevelFileNameInput.h"
#include <iostream>
#include <string>
static int namesFailures = 0;
static int plainFailures = 0;
//! \brief Compares namesFile with the expected answer.
static void names(const std::string& text, bool expected)
{
    if(LevelFileNameInput::namesFile(text) != expected)
    {
        std::cout << "namesFile '" << text << "'" << std::endl;
        ++namesFailures;
    }
}
//! \brief Compares isPlainFileName with the expected answer.
static void plain(const std::string& text, bool expected)
{
    if(LevelFileNameInput::isPlainFileName(text) != expected)
    {
        std::cout << "isPlainFileName '" << text << "'" << std::endl;
        ++plainFailures;
    }
}
int main()
{
    names("map", true);
    names("map.mmap", true);
    names("sub/map", true);
    names("..map", true);
    names("", false);
    names("   ", false);
    names(".", false);
    names("..", false);
    names("sub/", false);
    names("sub\\", false);
    names("sub/..", false);
    names("sub/ ", false);
    plain("map", true);
    plain("my map.mmap", true);
    plain("..map", true);
    plain("map..", true);
    plain("", false);
    plain(".", false);
    plain("..", false);
    plain("../x", false);
    plain("..\\x", false);
    plain("a/b", false);
    plain("C:x", false);
    plain("C:\\x", false);
    std::cout << "names failures=" << namesFailures << " plain failures=" << plainFailures << std::endl;
    return 0;
}
'''
if name_header.exists():
    probes['f67'] = F67_PROBE
save = function(server, 'case ClientNotificationType::askSaveMap:')
refusal = function(save, 'if((mServerMode == ServerMode::ModeEditor) && !(receivedFilePath.empty() && receivedFileLevel.empty())')
check('LevelFileNameInput::namesFile(receivedFileLevel)' in refusal and 'sendAsyncMsg' in refusal
      and 'break;' in refusal and before(save, 'LevelFileNameInput::namesFile(receivedFileLevel)', 'SafeSave::replaceFile('),
      'F6 askSaveMap refuses a "Save as" name that names no file, with a message, before anything is written')
save_click = function(editor, 'bool EditorMode::saveMenuSaveButtonClicked(')
check(re.search(r'if\s*\(\s*LevelFileNameInput::namesFile\(fileName\)\s*\)\s*mModifiedMapBit\s*=\s*false;', save_click)
      is not None,
      'F6 saveMenuSaveButtonClicked keeps the map modified when the name names no file')
for label, text, signature, field in (
        ('EditorMode', editor, 'bool EditorMode::launchNewLevelPressed(', '"LevelWindowFrame/LevelMessageText"'),
        ('MenuModeEditorNew', menu_new, 'bool MenuModeEditorNew::launchSelectedButtonPressed(', 'TEXT_LOADING')):
    body = function(text, signature)
    guard = function(body, 'if(!LevelFileNameInput::isPlainFileName(level))')
    check(guard != '' and field in guard and 'return true;' in guard
          and before(body, 'LevelFileNameInput::isPlainFileName(level)', 'level = levelPath + "/" + level;'),
          'F7 %s refuses a file name with a folder or ".." in its message field before it builds the path' % label)


# ---------------------------------------------------------------- probes
def run_item(item):
    """Runs one named probe."""
    return run_probe(item[0], item[1])


with ThreadPoolExecutor(max_workers=len(probes)) as pool:
    results = dict(zip(probes.keys(), pool.map(run_item, list(probes.items()))))

if 'f1' in results:
    ok, output = results['f1']
    check(ok and 'gap=6 plain=3' in output,
          'F1 the pool has 6 slots for seats 1, 2, 5 and 3 slots for seats 1, 2; got: ' + output.strip()[:400])
if 'f3' in results:
    ok, output = results['f3']
    expected = ['room-good result=1 changed=2 deleted=0 added=1', 'room-nulltile result=0 changed=0 deleted=1 added=0',
                'room-noseat result=0 changed=0 deleted=1 added=0', 'room-covered result=0 changed=0 deleted=1 added=0',
                'trap-good result=1 changed=2 deleted=0 added=1', 'trap-nulltile result=0 changed=0 deleted=1 added=0',
                'trap-noseat result=0 changed=0 deleted=1 added=0', 'trap-covered result=0 changed=0 deleted=1 added=0']
    lines = output.splitlines()
    missing = [line for line in expected if line not in lines]
    check(ok and not missing,
          'F3 the editor builders change no tile and delete the building on failure; missing: %s; got: %s'
          % (missing, output.strip()[:600]))
if 'f5' in results:
    ok, output = results['f5']
    check(ok and 'rules failures=0' in output, 'F5 PortalWaveRules accepts teams other than 0 and single-word class '
          'names only; got: ' + output.strip()[:300])
ok, output = results['f5b']
check(ok and 'plain=1 empty=0' in output,
      'F5 the production loader reads back plain class names and cannot read back an empty one; got: '
      + output.strip()[:300])
if 'f67' in results:
    ok, output = results['f67']
    check(ok and 'names failures=0 plain failures=0' in output,
          'F6/F7 LevelFileNameInput answers the fixed name cases; got: ' + output.strip()[:600])

elapsed = time.monotonic() - started
if failures:
    print('FAIL: %d requirement(s) not met:' % len(failures))
    for failure in failures:
        print('  - ' + failure)
    print('runtime %.1f s' % elapsed)
    sys.exit(1)
print('OK: the plausible editor findings are proven and the confirmed ones fixed (runtime %.1f s)' % elapsed)
