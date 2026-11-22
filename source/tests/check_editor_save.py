"""Check: the data-loss paths of the level editor and of level saving are closed.

    python source/tests/check_editor_save.py        (cl must be on the path: run it under vcvars64)

Requirements checked (each reported on its own, expected values are fixed):
  D2  the New dialog of EditorMode and of MenuModeEditorNew appends the .mmap extension (the shared constant
      MapHandler::USER_MAP_EXTENSION, which is ".mmap") before it tests whether the file exists (static)
  D3  writeGameMapToFile writes the [Scripts] section the loader reads: the entries live in the GameMap, the loader
      fills them and skips comment lines, the section is written between [HerbBundles] and the level script, and
      ScriptEntry::format / ScriptEntry::parse (the production header) round-trip the [Scripts] lines of the
      TestLegacy level (static for the wiring, compiled probe for the line format)
  D4  the saved time limit is not rebased: a game goes on from its saved turn and the editor level restarts, so
      the limit written by the production block of writeGameMapToFile must stay the one in memory
      (compiled probe on the production block and on LevelScript.cpp)
  D5  saving is atomic (SafeSave.h, compiled probe on disk): the map is written to a temp file first, the .bak is
      made only from the complete old file, a failed write leaves the old file and the .bak as they were; the
      path of askSaveMap is built inside a try
  D6  the modified bit is reset only when the save request was sent; "Falle abreissen" sets it (static)
  D7  the server rejects a tile type outside the enum, a negative or NaN fullness, an unknown seat id (other
      than -1) and a region name that is empty or has white space (compiled probe on ServerGuards.h, static for
      the use in ODServer.cpp)
D1 (save target of shipped levels) belongs to another work package and is not checked here.
It starts no game."""
from pathlib import Path
import os
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


def read(path, comments=False):
    """Reads a repository file, without comments unless asked."""
    text = (repo / path).read_text(encoding='utf-8', errors='replace')
    return text if comments else strip_comments(text)


def function(text, start_text):
    """Returns the brace-matched block that starts at the first start_text."""
    start = text.index(start_text)
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


DEPS = Path(os.environ.get('BUILD_DEPS_ROOT', str(Path(os.environ.get('USERPROFILE', '.')) / 'build-deps')))


def run_probe(name, code, boost=False):
    """Compiles one probe with cl, runs it and returns (ok, output)."""
    with tempfile.TemporaryDirectory(prefix='odp-' + name + '-') as directory:
        work = Path(directory)
        source = work / (name + '.cpp')
        source.write_text(code, encoding='utf-8')
        binary = work / (name + '.exe')
        command = ['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', '/I' + str(repo / 'source')]
        if boost:
            command += ['/I' + str(DEPS / 'install' / 'include' / 'boost-1_92')]
        if name in headers_need_deps:
            command += ['/I' + str(DEPS / 'install' / 'include' / sub) for sub in ('', 'OGRE', 'boost-1_92', 'SFML')]
        command += [str(source)] + extra_sources.get(name, []) + ['/Fe:' + str(binary)]
        if boost:
            command += ['/link', '/LIBPATH:' + str(DEPS / 'install' / 'lib')]
        build = subprocess.run(command, cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
        if build.returncode != 0:
            return False, 'compile failed: ' + '\n'.join(l for l in build.stdout.splitlines() if 'error' in l)[:1500]
        run = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        return run.returncode == 0, run.stdout + run.stderr


extra_sources = {}
# probes that include a production header which pulls in the engine headers (no linking needed)
headers_need_deps = ('d7',)

editor = read('source/modes/EditorMode.cpp')
new_menu = read('source/modes/MenuModeEditorNew.cpp')
server = read('source/network/ODServer.cpp')
maphandler = read('source/gamemap/MapHandler.cpp')

# ---------------------------------------------------------------- D2
for label, text, name in (('EditorMode', editor, 'bool EditorMode::launchNewLevelPressed('),
                          ('MenuModeEditorNew', new_menu, 'bool MenuModeEditorNew::launchSelectedButtonPressed(')):
    body = function(text, name)
    # The extension is the shared constant of MapHandler.h (".mmap", checked by check_official_level_protection P5)
    extension = 'MapHandler::USER_MAP_EXTENSION'
    check('append(%s)' % extension in body and before(body, extension, 'exists(level'),
          'D2 %s appends .mmap before it tests whether the file exists' % label)
    check('append(".level")' not in body, 'D2 %s no longer appends the .level extension' % label)

# ---------------------------------------------------------------- D3
game_map_h = read('source/gamemap/GameMap.h')
game_map = read('source/gamemap/GameMap.cpp')
writer = function(maphandler, 'bool writeGameMapToFile(')
loader = function(maphandler, 'bool readGameMapFromFile(')
check('getScriptEntries' in game_map_h and 'addScriptEntry' in game_map_h,
      'D3 GameMap keeps the [Scripts] entries of the level')
check('mScriptEntries.clear()' in function(game_map, 'void GameMap::clearAll('),
      'D3 GameMap::clearAll forgets the [Scripts] entries of the old level')
check('ScriptEntry::parse(' in loader and 'addScriptEntry(' in loader and 'clearScriptEntries()' in loader,
      'D3 the loader parses a [Scripts] line with ScriptEntry::parse and keeps it in the map')
check('[Scripts]' in writer and '[/Scripts]' in writer and 'getScriptEntries()' in writer
      and 'ScriptEntry::format(' in loader,
      'D3 writeGameMapToFile writes the [Scripts] section from the entries of the map')
check(before(writer, '[/HerbBundles]', '[Scripts]') and before(writer, '[/Scripts]', 'getLevelScript().isEmpty()'),
      'D3 [Scripts] is written after [HerbBundles] and before the level script, where the loader reads it')

legacy = (repo / 'levels/skirmish/TestLegacy.level').read_text(encoding='utf-8', errors='replace')
script_lines = legacy.split('[Scripts]', 1)[1].split('[/Scripts]', 1)[0].splitlines()
cpp_lines = ',\n'.join('"%s"' % l.replace('\\', '\\\\').replace('"', '\\"').replace('\t', '\\t') for l in script_lines)
D3_PROBE = r'''
#include "gamemap/ScriptEntry.h"
#include <iostream>
#include <string>
#include <vector>
int main()
{
    const char* lines[] = {
''' + cpp_lines + r'''
    };
    int entries = 0;
    for(const char* raw : lines)
    {
        std::string action, script;
        std::vector<int> values;
        if(!ScriptEntry::parse(raw, action, script, values))
            continue;
        ++entries;
        std::string written = ScriptEntry::format(action, script, values);
        std::string action2, script2;
        std::vector<int> values2;
        if(!ScriptEntry::parse(written, action2, script2, values2) || action2 != action || script2 != script
           || values2 != values)
        {
            std::cout << "round trip differs: " << raw << std::endl;
            return 1;
        }
        std::cout << "entry " << written << std::endl;
    }
    std::cout << "entries=" << entries << std::endl;
    std::string a, s;
    std::vector<int> v;
    std::cout << "comment=" << ScriptEntry::parse("#EventName  Script  Trigger", a, s, v) << std::endl;
    std::cout << "blank=" << ScriptEntry::parse("   \t", a, s, v) << std::endl;
    return 0;
}
'''
ok, output = run_probe('d3', D3_PROBE)
check(ok and 'entries=2' in output and 'entry ClockTick hello3.py 0 10' in output
      and 'entry ClockTick hello4.py 0 15' in output and 'comment=0' in output and 'blank=0' in output,
      'D3 the [Scripts] lines of TestLegacy round-trip through ScriptEntry (expected 2 entries); got: ' + output[:300])

# The production [Scripts] loader block (readGameMapFromFile) and writer block (writeGameMapToFile), compiled together:
# the section of TestLegacy is read, written, and read again
loader_block = function(loader, 'if(nextParam == "[Scripts]")')
writer_block = function(writer, 'if(!gameMap.getScriptEntries().empty())')
section_text = '[Scripts]\n' + '\n'.join(script_lines) + '\n[/Scripts]\n'
cpp_section = ''.join('"%s\\n"\n' % l.replace('\\', '\\\\').replace('"', '\\"').replace('\t', '\\t')
                      for l in section_text.split('\n')[:-1])
D3B_HEAD = r"""
#include "gamemap/ScriptEntry.h"
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#define OD_LOG_ERR(x) (void)0
//! \brief The loader keeps the lines of the section in the map.
struct GameMapStub
{
    std::vector<std::string> mEntries;
    const std::vector<std::string>& getScriptEntries() const { return mEntries; }
    void addScriptEntry(const std::string& entry) { mEntries.push_back(entry); }
};
//! \brief The script register of the console.
struct GameEditorModeConsole
{
    static std::unordered_map<std::string, std::multimap<std::vector<int>, std::string> > scriptRegister;
};
std::unordered_map<std::string, std::multimap<std::vector<int>, std::string> > GameEditorModeConsole::scriptRegister;
//! \brief The script file reader; the body of a script is not needed here.
struct Helper
{
    static bool readFile(const std::string&, std::stringstream& out, bool) { out << "body"; return true; }
};
//! \brief The folder of the script files.
struct ResourceManagerStub { std::string getGameScriptsPath() const { return "scripts/"; } };
//! \brief Gives the stub of the resource manager.
struct ResourceManager { static ResourceManagerStub& getSingleton() { static ResourceManagerStub r; return r; } };
//! \brief Load errors are not expected.
static void setLoadError(const std::string& text) { std::cout << "loaderror " << text << std::endl; }
//! \brief The production loader block for the [Scripts] section.
static bool loadScripts(GameMapStub& gameMap, std::stringstream& levelFile, const std::string& fileName)
{
    std::string nextParam;
    levelFile >> nextParam;
"""
D3B_MID = r"""
    return true;
}
//! \brief The production writer block for the [Scripts] section.
static std::string writeScripts(GameMapStub& gameMap)
{
    std::ostringstream out;
    std::ostream& levelFile = out;
"""
D3B_MAIN = r"""
    return out.str();
}
int main()
{
    std::stringstream first(std::string(
"""
D3B_TAIL = r"""    ));
    GameMapStub one;
    if(!loadScripts(one, first, "x"))
        return 1;
    std::string written = writeScripts(one);
    std::stringstream second(written);
    GameMapStub two;
    GameEditorModeConsole::scriptRegister.clear();
    if(!loadScripts(two, second, "y"))
        return 1;
    std::cout << "first=" << one.mEntries.size() << " second=" << two.mEntries.size()
              << " same=" << (one.mEntries == two.mEntries) << " registered="
              << GameEditorModeConsole::scriptRegister["ClockTick"].size() << std::endl;
    for(size_t i = 0; i < two.mEntries.size(); ++i)
        std::cout << "entry " << two.mEntries[i] << std::endl;
    return 0;
}
"""
D3B_PROBE = D3B_HEAD + loader_block + D3B_MID + writer_block + D3B_MAIN + cpp_section + D3B_TAIL
ok, output = run_probe('d3b', D3B_PROBE)
check(ok and 'first=2 second=2 same=1 registered=2' in output and 'entry ClockTick hello3.py 0 10' in output
      and 'entry ClockTick hello4.py 0 15' in output,
      'D3 the production loader and writer blocks carry the 2 TestLegacy [Scripts] entries through write and read-back; got: '
      + output[:400])

# ---------------------------------------------------------------- D4
# The production block that writes the level script, compiled against the real LevelScript.cpp
block = function(writer, 'if(!gameMap.getLevelScript().isEmpty())')
D4_PROBE = r'''
#include "gamemap/LevelScript.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <sstream>
//! \brief The turn rate of the game (ODApplication.cpp).
struct ODApplication { static constexpr double turnsPerSecond = 1.4; };
//! \brief The two things of the game map the block reads.
struct GameMapStub
{
    LevelScript mScript;
    int64_t mTurn;
    LevelScript& getLevelScript() { return mScript; }
    int64_t getTurnNumber() const { return mTurn; }
};
//! \brief The production block of writeGameMapToFile that writes the level script.
static std::string writeScript(GameMapStub& gameMap)
{
    std::ostringstream out;
    std::ostream& levelFile = out;
''' + block + r'''
    return out.str();
}
int main()
{
    // A limit of 600 seconds, the game or the editor has run 100 seconds (140 turns) when the map is saved
    GameMapStub gameMap;
    gameMap.mScript.setTimeLimitSeconds(600);
    gameMap.mTurn = 140;
    std::string written = writeScript(gameMap);
    std::istringstream in(written);
    std::string tag;
    in >> tag;
    LevelScript loaded;
    if(tag != "[Triggers]" || !loaded.importFromStream(in))
    {
        std::cout << "cannot read back: " << written << std::endl;
        return 1;
    }
    // A saved game goes on from its saved turn (ODServer::startGame uses getSavedTurnNumber) and counts the limit
    // from turn 0, so what is left after loading is the written limit minus the saved turn in seconds
    std::cout << "written=" << loaded.getTimeLimitSeconds() << std::endl;
    std::cout << "left=" << (loaded.getTimeLimitSeconds() - static_cast<int64_t>(140 / ODApplication::turnsPerSecond)) << std::endl;
    std::cout << "memory=" << gameMap.mScript.getTimeLimitSeconds() << std::endl;
    return 0;
}
'''
extra_sources['d4'] = [str(repo / 'source/gamemap/LevelScript.cpp')]
ok, output = run_probe('d4', D4_PROBE)
check(ok and 'written=600' in output and 'left=500' in output and 'memory=600' in output,
      'D4 the saved time limit is the one in memory (600 of 600, 500 left after 100 seconds); got: ' + output[:300])
check('firstTurn = gameMap->getSavedTurnNumber()' in server and 'setTurnNumber(firstTurn)' in server, 'D4 the loaded game goes on from the saved turn (the reason a rebase subtracts twice)')

# ---------------------------------------------------------------- D5
D5_PROBE = r'''
#include "utils/SafeSave.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
namespace fs = boost::filesystem;
//! \brief Reads a whole file, or "<missing>".
static std::string slurp(const fs::path& p)
{
    std::ifstream in(p.string().c_str(), std::ios::binary);
    if(!in)
        return "<missing>";
    std::stringstream ss;
    ss << in.rdbuf();
    return ss.str();
}
//! \brief Writes a file.
static void put(const fs::path& p, const std::string& text)
{
    std::ofstream out(p.string().c_str(), std::ios::binary);
    out << text;
}
//! \brief Writes the new content completely.
static bool writeNew(const std::string& name)
{
    put(name, "new");
    return true;
}
//! \brief Writes the second content completely.
static bool writeSecond(const std::string& name)
{
    put(name, "second");
    return true;
}
//! \brief Writes half of the file and reports the failure.
static bool writePartial(const std::string& name)
{
    put(name, "ne");
    return false;
}
//! \brief Writes half of the file and throws.
static bool writeThrow(const std::string& name)
{
    put(name, "ne");
    throw std::runtime_error("disk full");
}
//! \brief True when the folder holds only the named files.
static bool only(const fs::path& dir, const std::string& a, const std::string& b = "", const std::string& c = "")
{
    int count = 0;
    for(fs::directory_iterator it(dir); it != fs::directory_iterator(); ++it)
    {
        std::string n = it->path().filename().string();
        if(n != a && n != b && n != c)
            return false;
        ++count;
    }
    return count > 0;
}
int main()
{
    fs::path dir = fs::path(".") / "savedir";
    fs::create_directories(dir);
    fs::path target = dir / "map.level";
    std::string error;

    // fresh target: new content, no backup, no temp file
    bool r1 = SafeSave::replaceFile(target, writeNew, error);
    if(!r1)
        std::cout << "error: " << error << std::endl;
    std::cout << "fresh=" << r1 << ":" << slurp(target) << ":" << slurp(dir / "map.level.bak") << ":" << only(dir, "map.level") << std::endl;

    // existing target: the backup is the complete old file
    bool r2 = SafeSave::replaceFile(target, writeSecond, error);
    std::cout << "second=" << r2 << ":" << slurp(target) << ":" << slurp(dir / "map.level.bak") << ":" << only(dir, "map.level", "map.level.bak") << std::endl;

    // a write that fails: old file and backup stay as they were, no temp file is left
    bool r3 = SafeSave::replaceFile(target, writePartial, error);
    std::cout << "partial=" << r3 << ":" << slurp(target) << ":" << slurp(dir / "map.level.bak") << ":" << only(dir, "map.level", "map.level.bak") << std::endl;

    // a write that throws: same
    bool r4 = SafeSave::replaceFile(target, writeThrow, error);
    std::cout << "throw=" << r4 << ":" << slurp(target) << ":" << slurp(dir / "map.level.bak") << ":" << only(dir, "map.level", "map.level.bak") << std::endl;

    // a later good save replaces the backup with the then old file
    bool r5 = SafeSave::replaceFile(target, writeNew, error);
    std::cout << "third=" << r5 << ":" << slurp(target) << ":" << slurp(dir / "map.level.bak") << ":" << only(dir, "map.level", "map.level.bak") << std::endl;

    // a target in a folder that does not exist: failure with a message, nothing thrown
    bool r6 = SafeSave::replaceFile(dir / "nothere" / "x.level", writeNew, error);
    std::cout << "nofolder=" << r6 << ":" << (error.empty() ? "noerror" : "error") << std::endl;
    return 0;
}
'''
ok, output = run_probe('d5', D5_PROBE, boost=True)
expected = ['fresh=1:new:<missing>:1', 'second=1:second:new:1', 'partial=0:second:new:1', 'throw=0:second:new:1',
            'third=1:new:second:1', 'nofolder=0:error']
check(ok and all(line in output.splitlines() for line in expected),
      'D5 SafeSave writes to a temp file, backs up only a complete old file and keeps both on failure; got: ' + output[:600])
ask = function(server, 'case ClientNotificationType::askSaveMap:')
check('SafeSave::replaceFile(' in ask and 'writeGameMapToFile(levelSave' not in ask,
      'D5 askSaveMap saves through SafeSave::replaceFile, not with a direct write')
check('try' in ask and 'levelSave =' in function(ask, 'try') and 'levelPath' in function(ask, 'try'),
      'D5 the path of the save is built inside a try block (path construction can throw)')
check('rename(levelSave' not in ask, 'D5 askSaveMap no longer renames the old file before the new one is written')

# ---------------------------------------------------------------- D6
for name, signature in (('onSaveButtonClickFromOptions', 'bool EditorMode::onSaveButtonClickFromOptions('),
                        ('quickSavePopUpMenu', 'bool EditorMode::quickSavePopUpMenu('),
                        ('saveMenuSaveButtonClicked', 'bool EditorMode::saveMenuSaveButtonClicked(')):
    body = function(editor, signature)
    sent = body.index('queueClientNotification') if 'queueClientNotification' in body else -1
    reset = body.find('mModifiedMapBit = false')
    # the reset has to be inside the block of the if that sends the request: after the send, before the closing brace
    close = body.find('}', sent) if sent != -1 else -1
    check(sent != -1 and reset != -1 and sent < reset < close,
          'D6 %s resets mModifiedMapBit only when the request was queued' % name)
trap = editor[editor.index('case SelectedAction::destroyTrap:'):]
trap = trap[:trap.index('case SelectedAction::castSpell:')]
check(before(trap, 'mModifiedMapBit = true', 'return'), 'D6 destroying a trap sets the modified bit before the return')

# ---------------------------------------------------------------- D7
D7_PROBE = r'''
#include "network/ServerGuards.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <vector>
int main()
{
    const int32_t count = 8;
    std::cout << "type=" << ServerGuards::isTileTypeValue(1, count) << ServerGuards::isTileTypeValue(7, count)
              << ServerGuards::isTileTypeValue(8, count) << ServerGuards::isTileTypeValue(-1, count)
              << ServerGuards::isTileTypeValue(1000, count) << std::endl;
    const double nan = std::numeric_limits<double>::quiet_NaN();
    std::cout << "full=" << ServerGuards::isFullnessAllowed(0.0) << ServerGuards::isFullnessAllowed(100.0)
              << ServerGuards::isFullnessAllowed(-0.5) << ServerGuards::isFullnessAllowed(nan)
              << ServerGuards::isFullnessAllowed(std::numeric_limits<double>::infinity()) << std::endl;
    std::vector<int32_t> seats;
    seats.push_back(1);
    seats.push_back(2);
    std::cout << "seat=" << ServerGuards::isSeatIdKnown(-1, seats) << ServerGuards::isSeatIdKnown(1, seats)
              << ServerGuards::isSeatIdKnown(2, seats) << ServerGuards::isSeatIdKnown(3, seats)
              << ServerGuards::isSeatIdKnown(0, seats) << ServerGuards::isSeatIdKnown(-2, seats) << std::endl;
    std::cout << "region=" << ServerGuards::isRegionNameAllowed("Gate") << ServerGuards::isRegionNameAllowed("")
              << ServerGuards::isRegionNameAllowed("Main Gate") << ServerGuards::isRegionNameAllowed("a\tb")
              << ServerGuards::isRegionNameAllowed(" ") << ServerGuards::isRegionNameAllowed("Gate_2")
              << ServerGuards::isRegionNameAllowed("a\nb") << std::endl;
    return 0;
}
'''
ok, output = run_probe('d7', D7_PROBE)
check(ok and 'type=11000' in output and 'full=11000' in output and 'seat=111000' in output
      and 'region=1000010' in output,
      'D7 the ServerGuards rules reject a bad tile type, fullness, seat id and region name; got: ' + output[:400])
one = function(server, 'case ClientNotificationType::editorAskChangeTile:')
many = function(server, 'case ClientNotificationType::editorAskChangeTiles:')
for label, body in (('editorAskChangeTile', one), ('editorAskChangeTiles', many)):
    check('isEditorTileChangeValid(' in body and before(body, 'isEditorTileChangeValid(', 'setType('),
          'D7 %s checks tile type, fullness and seat id before it changes a tile' % label)
helper = function(server, 'bool isEditorTileChangeValid(')
check('ServerGuards::isTileTypeValue(' in helper and 'ServerGuards::isFullnessAllowed(' in helper
      and 'ServerGuards::isSeatIdKnown(' in helper,
      'D7 isEditorTileChangeValid applies the tile type, fullness and seat id rules of ServerGuards')

if failures:
    print('FAIL: %d requirement(s) not met (%.1f s):' % (len(failures), time.monotonic() - started))
    for failure in failures:
        print('  - ' + failure)
    sys.exit(1)
print('OK: editor save checks passed (%.1f s)' % (time.monotonic() - started))
