"""Check that players and files see the name Moreya, never the old project names.

Static part (pure Python):
- Player-facing texts: the shipped text data (config, gui, levels, python, licenses, particles, shaders), the string
  literals of the game source and the packaging and documentation files contain no "OpenDungeons", "Open Dungeons",
  "OpenDungeonsPlus" or "ODP". Allowed are only internal names (CEGUI image set and scheme names, the level file
  version header), licence and credit notices that name the projects Moreya is based on, the past release entries of
  RELEASE-NOTES.md, and the fixed list of internal source literals below.
- File names: no tracked file that is shipped or installed (game data, dist/, meta/, snap/, cmake/config/, the flatpak
  files in the top folder) has an old name in its path.
- Package names: executable moreya (CMake output name), Linux launcher and binary moreya, archives
  Moreya-<version>-linux-x86_64 and Moreya-<version>-windows-x64.zip, snap, desktop and metainfo ids, window title.
- Links: no player-facing link to the old project's websites or community.
- Exit screen: the "Join the community" screen (Advertisment.layout, AdvertMode) is gone, the Quit button closes the
  game directly.
- Icon: the Moreya icon exists in every size the executable, window and packages use (PNG 16-256, ICO 16-256, SVG).
Runtime part: ResourceManager::takeOverOldUserFolder, cut out of ResourceManager.cpp, is compiled with cl and the
Boost of the dependency folder and run on temporary folders: the old user data is copied completely (old log files
excepted), the old folder stays unchanged, an existing new folder is never touched, a missing old folder creates
nothing and a left-over partial copy of an interrupted start is replaced.

Fixed values: 7 allowed source literals, 7 ICO sizes, 6 PNG sizes, 5 take-over cases.
Usage: python -I source/tests/check_moreya_name.py
"""
from pathlib import Path
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OLD = re.compile(r'open ?dungeons|\bodp\b', re.I)
# Internal names that stay (code-internal, not shown to players): CEGUI image sets and scheme, the level file header.
INTERNAL = re.compile(r'OpenDungeons(Icons|Skin|GameWindow|Navigation)\b/?|'
                      r'OpenDungeons_Version:[0-9.]*(  # The version of OpenDungeons which created this file '
                      r'\(for compatibility reasons\)\.)?|GUIScheme name="OpenDungeons"')
# String literals of the game source that keep the old name: the comment of the level file header, the network
# protocol identifier,
# an OGRE window name, the folder name of older versions and a stack trace library macro (fixed list, counted once).
ALLOWED_LITERALS = {
    ('source/gamemap/MapHandler.cpp', '"  # The version of OpenDungeons which created this file (for compatibility reasons).\\n"'),
    ('source/modes/MenuModeReplay.cpp', '"OpenDungeons V "'),
    ('source/network/ODClient.cpp', '"OpenDungeons V "'),
    ('source/network/ODServer.cpp', '"OpenDungeons V "'),
    ('source/render/ODFrameListener.cpp', '"OpenDungeonsLiveSettings"'),
    ('source/utils/ResourceManager.cpp', '"opendungeons"'),
    ('source/utils/StackTraceWinMinGW.cpp', '"OpenDungeons"'),
}
assert len(ALLOWED_LITERALS) == 7
OLD_LINKS = re.compile(r'discord|freegamedev|sf\.net|sourceforge|fsdn\.com|github\.com/OpenDungeons|'
                       r'tomluchowski/(?!cegui\.git)', re.I)
# The CEGUI fork (github.com/tomluchowski/cegui.git) is a build dependency source, not a link shown to players.
SHIPPED_DIRS = ('config', 'gui', 'levels', 'licenses', 'materials', 'models', 'music', 'particles', 'python', 'shaders',
                'sounds', 'dist', 'meta', 'snap', 'cmake/config')
BINARY_SUFFIXES = ('.png', '.jpg', '.jpeg', '.ttf', '.otf', '.ogg', '.wav', '.mesh', '.skeleton', '.dds', '.ico', '.blend')
PNG_SIZES = (16, 32, 48, 64, 128, 256)
ICO_SIZES = {16, 24, 32, 48, 64, 128, 256}
failures = []


def check(condition, message):
    """Records a failed condition; all failures are printed at the end."""
    if not condition:
        failures.append(message)


def read(relative):
    """Text of a repository file."""
    return (ROOT / relative).read_text(encoding='utf-8')


def tracked(*paths):
    """Tracked files below the given paths, relative with forward slashes."""
    output = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--'] + list(paths), capture_output=True, text=True,
                            check=True).stdout
    return [line for line in output.splitlines() if line]


def old_name_lines(relative, text, allowed=None):
    """Lines of text that contain an old name outside the internal names and the allowed credit lines."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        rest = INTERNAL.sub('', line)
        if allowed is not None and allowed.search(rest):
            continue
        if OLD.search(rest):
            found.append('%s:%d: %s' % (relative, number, line.strip()[:140]))
    return found


def function_body(text, signature):
    """Cuts one function definition (signature up to its matching closing brace) out of a source file."""
    start = text.index(signature)
    depth = 0
    for index in range(text.index('{', start), len(text)):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError(signature)


def png_size(path):
    """Width and height from the PNG header."""
    data = path.read_bytes()[:24]
    check(data[:8] == b'\x89PNG\r\n\x1a\n', str(path) + ' is a PNG file')
    return struct.unpack('>II', data[16:24])


def ico_sizes(path):
    """Image sizes listed in the directory of an ICO file (0 stands for 256)."""
    data = path.read_bytes()
    reserved, kind, count = struct.unpack('<HHH', data[:6])
    check(reserved == 0 and kind == 1, str(path) + ' is an ICO file')
    return {(data[6 + 16 * i] or 256) for i in range(count)}


started = time.monotonic()

# Player-facing data texts
for relative in tracked('config', 'gui', 'levels', 'python', 'licenses', 'particles', 'shaders'):
    if relative.lower().endswith(BINARY_SUFFIXES):
        continue
    text = read(relative)
    # gui/GoalStatus.svg names its authors in its metadata (credit notice).
    failures.extend(old_name_lines(relative, text, re.compile(r'<metadata>.*contributors')))
    check(not OLD_LINKS.search(text), relative + ': link to the old project or its community')

# String literals of the game source
literal = re.compile(r'"(?:[^"\\\n]|\\.)*"')
seen = set()
for relative in tracked('source'):
    if relative.startswith('source/tests/') or not relative.endswith(('.cpp', '.h')):
        continue
    for number, line in enumerate(read(relative).splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(('//', '*', '/*')):
            continue
        for text in literal.findall(line):
            if OLD_LINKS.search(text):
                failures.append('%s:%d: link %s' % (relative, number, text))
            if OLD.search(INTERNAL.sub('', text)):
                if (relative, text) in ALLOWED_LITERALS:
                    seen.add((relative, text))
                else:
                    failures.append('%s:%d: player-facing literal %s' % (relative, number, text))
check(seen == ALLOWED_LITERALS, 'allowed literals no longer present: %s' % sorted(ALLOWED_LITERALS - seen))

# Packaging, metadata and documents
# Credit lines naming the projects Moreya is based on, and the internal CMake target name in build commands.
CREDIT = re.compile(r'based on|OpenDungeons project|first written|CMake target|--target opendungeons-plus')
for relative in tracked('dist', 'meta', 'snap', 'cmake/config', '.github/workflows/linux-release.yml',
                        'scripts/unix/package-linux-release.sh', 'scripts/win32/package-windows-release.ps1',
                        'io.github.rokk001.Moreya.desktop', 'io.github.rokk001.Moreya.metainfo.xml', 'README.md', 'AUTHORS'):
    if relative.lower().endswith(BINARY_SUFFIXES):
        continue
    text = read(relative)
    failures.extend(old_name_lines(relative, text, CREDIT))
    check(not OLD_LINKS.search(text), relative + ': link to the old project or its community')
notes = read('RELEASE-NOTES.md')
current = notes[:notes.index('### Version ')]
failures.extend(old_name_lines('RELEASE-NOTES.md', current, CREDIT))
check(not OLD_LINKS.search(current), 'RELEASE-NOTES.md: link to the old project above the past release entries')
check(notes.startswith('## Moreya Release Notes'), 'RELEASE-NOTES.md is titled Moreya')

# File names of everything shipped or installed
for relative in tracked(*SHIPPED_DIRS) + [p for p in tracked('.') if '/' not in p]:
    check(not OLD.search(relative), 'file name with an old name: ' + relative)

# Package names, executable and window title
cmake = read('CMakeLists.txt')
check('set(OD_EXECUTABLE_NAME "moreya")' in cmake, 'CMake executable name is moreya')
check('set_target_properties(${PROJECT_BINARY_NAME} PROPERTIES OUTPUT_NAME "${OD_EXECUTABLE_NAME}")' in cmake,
      'the game target writes moreya(.exe)')
check('share/games/${OD_EXECUTABLE_NAME}' in cmake and '/etc/${OD_EXECUTABLE_NAME}' in cmake and
      'doc/${OD_EXECUTABLE_NAME}' in cmake, 'installed folders are named moreya')
check('${CMAKE_SOURCE_DIR}/scripts\n' not in cmake, 'developer scripts are not installed')
linux = read('scripts/unix/package-linux-release.sh')
check('BINARY=moreya\n' in linux and 'cat > "$OUT/moreya" <<EOF' in linux and 'exec "\\$HERE/bin/$BINARY"' in linux,
      'Linux package: launcher moreya starts bin/moreya')
check(' scripts ' not in linux.split('for dir in ')[1].split(';')[0], 'Linux package ships no developer scripts')
workflow = read('.github/workflows/linux-release.yml')
check('name="Moreya-${version}-linux-x86_64"' in workflow and 'test -x build/moreya' in workflow,
      'Linux workflow builds build/moreya and names the archive Moreya-<version>-linux-x86_64')
windows = read('scripts/win32/package-windows-release.ps1')
check('$name = "Moreya-$version-windows-x64"' in windows and '$zip = Join-Path $OutDir "$name.zip"' in windows and
      "Join-Path $Build 'moreya.exe'" in windows, 'Windows package: moreya.exe in Moreya-<version>-windows-x64.zip')
check("'scripts'" not in windows.split('$dataDirs = ')[1].split('\n')[0], 'Windows package ships no developer scripts')
snap = read('snap/snapcraft.yaml')
check(snap.startswith('name: moreya') and 'apps:\n  moreya:\n    command: usr/bin/moreya' in snap.replace('\r\n', '\n'),
      'snap name and command are moreya')
desktop = read('io.github.rokk001.Moreya.desktop')
check('Name=Moreya' in desktop and 'Exec=moreya' in desktop and 'Icon=io.github.rokk001.Moreya' in desktop, 'flatpak desktop entry')
metainfo = read('io.github.rokk001.Moreya.metainfo.xml')
check('<id>io.github.rokk001.Moreya</id>' in metainfo and '<name>Moreya</name>' in metainfo, 'flatpak metainfo id and name')
check('<id>moreya.desktop</id>' in read('dist/moreya.appdata.xml'), 'appdata id')
check('Exec=@OD_BIN_PATH@/moreya' in read('cmake/config/moreya.desktop.in'), 'installed desktop entry starts moreya')
check('Icon=${SNAP}/meta/gui/moreya.svg' in read('meta/gui/moreya.desktop'), 'snap desktop entry uses the Moreya icon')
check('.B moreya' in read('cmake/config/moreya.6.in'), 'manual page is for moreya')
application = read('source/ODApplication.cpp')
check('const std::string windowTitle = "Moreya " + VERSION;' in application, 'window title is Moreya <version>')
check('ss << "Moreya version: " << ODApplication::VERSION' in read('source/main.cpp'), 'help text names Moreya')
check('LOGFILENAME = "moreya.log"' in read('source/utils/ResourceManager.cpp'), 'log file is moreya.log')

# Exit screen removed, Quit closes directly
for gone in ('gui/Advertisment.layout', 'gui/ODAdvertisment.imageset', 'gui/ODAdvertisment.png',
             'source/modes/AdvertMode.cpp', 'source/modes/AdvertMode.h'):
    check(not (ROOT / gone).exists(), gone + ' is removed')
for relative in tracked('source', 'gui', 'CMakeLists.txt'):
    if relative.startswith('source/tests/') or relative.lower().endswith(BINARY_SUFFIXES):
        continue
    text = read(relative)
    check(not re.search(r'ADVERTISMENT|AdvertMode|Advertisment|advertisment', text), relative + ' still refers to the exit screen')
menu = read('source/modes/MenuModeMain.cpp')
check('rootWin->getChild(BUTTON_QUIT)->subscribeEvent(\n            CEGUI::PushButton::EventClicked,\n'
      '            CEGUI::Event::Subscriber(&MenuModeMain::quitButtonPressed, this)' in menu, 'Quit button calls quitButtonPressed')
check('ODFrameListener::getSingleton().requestExit();' in function_body(menu, 'bool MenuModeMain::quitButtonPressed('),
      'quitButtonPressed closes the game')

# Icon files
check(re.search(r'^1 ICON "moreya\.ico"', read('dist/icon.rc'), re.M) is not None, 'executable and window use moreya.ico')
check('<svg' in read('dist/hicolor/scalable/apps/moreya.svg') and read('meta/gui/moreya.svg') == read('dist/hicolor/scalable/apps/moreya.svg'),
      'scalable Moreya icon')
for size in PNG_SIZES:
    path = ROOT / ('dist/hicolor/%dx%d/apps/moreya.png' % (size, size))
    check(path.is_file() and png_size(path) == (size, size), 'PNG icon %d px' % size)
check(ico_sizes(ROOT / 'dist/moreya.ico') == ICO_SIZES, 'ICO holds 16, 24, 32, 48, 64, 128 and 256 px')
credits = read('CREDITS')
check(re.search(r'^hicolor/\*/apps/moreya\.\*\s+AI-generated', credits, re.M) is not None and
      re.search(r'^moreya\.ico\s+AI-generated', credits, re.M) is not None, 'CREDITS marks the icon as AI-generated')

# Old user data taken over: static wiring
resources = read('source/utils/ResourceManager.cpp')
check('const std::string ResourceManager::OLDUSERFOLDERNAME = "opendungeons";' in resources, 'old folder name')
check('const std::string ResourceManager::USERFOLDERNAME = "Moreya";' in resources and
      'const std::string ResourceManager::USERFOLDERNAME = "moreya";' in resources, 'new folder names')
setup = function_body(resources, 'void ResourceManager::setupUserDataFolders(')
check(setup.count('takeOverOldUserFolder(') == 4, 'take-over on Windows, macOS and for both Linux folders')
check('takeOverOldUserFolder(std::string(path) + "/" + OLDUSERFOLDERNAME + "/", mUserDataPath);' in setup,
      'Windows takes %APPDATA%/opendungeons over')
print('ODP_TEST_PHASE ' + json.dumps({'name': 'static', 'seconds': round(time.monotonic() - started, 3)}))

# Old user data taken over: runtime probe of the production function
PROBE = r'''
#include <boost/filesystem.hpp>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#define OD_LOG_INF(message) std::cout << (message) << std::endl
#define OD_LOG_WRN(message) std::cout << (message) << std::endl
//! \brief Holds only the production take-over function.
class ResourceManager
{
public:
    static bool takeOverOldUserFolder(const std::string& oldPath, const std::string& newPath);
};
FUNCTION

static int failed = 0;
//! \brief Prints a failed expectation.
static void expect(bool condition, const std::string& message)
{
    if(!condition)
    {
        std::cout << "FAIL: " << message << std::endl;
        ++failed;
    }
}
//! \brief Writes a small file, creating its folder.
static void put(const boost::filesystem::path& file, const std::string& text)
{
    boost::filesystem::create_directories(file.parent_path());
    std::ofstream out(file.string().c_str(), std::ios::binary);
    out << text;
}
//! \brief Reads a whole file, empty when missing.
static std::string get(const boost::filesystem::path& file)
{
    std::ifstream in(file.string().c_str(), std::ios::binary);
    std::stringstream text;
    text << in.rdbuf();
    return text.str();
}
int main(int argc, char** argv)
{
    const boost::filesystem::path base(argv[1]);
    const boost::filesystem::path old = base / "opendungeons";
    const boost::filesystem::path moreya = base / "Moreya";
    put(old / "cfg" / "config.cfg", "Video settings\n");
    put(old / "saves" / "Mossgate-1.level", "saved game\n");
    put(old / "campaign.progress", "Completed\n");
    put(old / "replay" / "nested" / "r.replay", "replay\n");
    put(old / "opendungeons.log", "old log\n");
    boost::filesystem::create_directories(old / "screenshots");
    // 1: first start copies everything except the old log file; the old folder stays.
    expect(ResourceManager::takeOverOldUserFolder(old.string() + "/", moreya.string() + "/"), "first start takes over");
    expect(get(moreya / "cfg" / "config.cfg") == "Video settings\n", "settings taken over");
    expect(get(moreya / "saves" / "Mossgate-1.level") == "saved game\n", "saved game taken over");
    expect(get(moreya / "campaign.progress") == "Completed\n", "campaign progress taken over");
    expect(get(moreya / "replay" / "nested" / "r.replay") == "replay\n", "nested folders taken over");
    expect(boost::filesystem::is_directory(moreya / "screenshots"), "empty folders taken over");
    expect(!boost::filesystem::exists(moreya / "opendungeons.log"), "old log file not carried over");
    expect(get(old / "saves" / "Mossgate-1.level") == "saved game\n" && get(old / "opendungeons.log") == "old log\n",
        "old folder unchanged");
    expect(!boost::filesystem::exists(base / "Moreya.takeover"), "no partial folder left");
    // 2: later starts never touch an existing new folder.
    put(moreya / "cfg" / "config.cfg", "changed in Moreya\n");
    expect(!ResourceManager::takeOverOldUserFolder(old.string() + "/", moreya.string() + "/"), "second start does nothing");
    expect(get(moreya / "cfg" / "config.cfg") == "changed in Moreya\n", "existing new data kept");
    // 3: no old folder: nothing is created.
    const boost::filesystem::path fresh = base / "fresh";
    expect(!ResourceManager::takeOverOldUserFolder((base / "missing").string() + "/", fresh.string() + "/"), "no old folder");
    expect(!boost::filesystem::exists(fresh), "nothing created without old data");
    // 4: a partial copy of an interrupted start is replaced by a complete one.
    const boost::filesystem::path again = base / "again";
    put(base / "again.takeover" / "stale.txt", "stale\n");
    expect(ResourceManager::takeOverOldUserFolder(old.string() + "/", again.string() + "/"), "take-over after an interrupted start");
    expect(!boost::filesystem::exists(again / "stale.txt") && get(again / "saves" / "Mossgate-1.level") == "saved game\n",
        "partial copy replaced");
    // 5: the old folder is a file, not a folder: nothing happens.
    put(base / "plainfile", "x");
    expect(!ResourceManager::takeOverOldUserFolder((base / "plainfile").string() + "/", (base / "other").string() + "/"),
        "old path that is no folder");
    std::cout << (failed == 0 ? "PROBE OK" : "PROBE FAILED") << std::endl;
    return failed == 0 ? 0 : 1;
}
'''
probe_started = time.monotonic()
deps = Path(os.environ.get('OD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'
boost_include = sorted((deps / 'include').glob('boost-*'))
boost_lib = sorted((deps / 'lib').glob('libboost_filesystem-vc*-mt-x64-*.lib'))
if os.name != 'nt' or not boost_include or not boost_lib:
    failures.append('runtime probe needs Windows, cl and the Boost of ' + str(deps))
else:
    source = PROBE.replace('FUNCTION', function_body(resources, 'bool ResourceManager::takeOverOldUserFolder('))
    with tempfile.TemporaryDirectory(prefix='moreya-name-') as directory:
        work = Path(directory)
        (work / 'probe.cpp').write_text(source, encoding='utf-8')
        compiled = subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/O1', '/std:c++14', '/I', str(boost_include[-1]),
                                   'probe.cpp', '/Feprobe.exe', '/link', '/LIBPATH:' + str(deps / 'lib')],
                                  cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
        if compiled.returncode != 0:
            failures.append('probe does not compile:\n' + compiled.stdout[-3000:] + compiled.stderr[-1000:])
        else:
            (work / 'data').mkdir()
            ran = subprocess.run([str(work / 'probe.exe'), str(work / 'data')], cwd=work, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=60)
            print(ran.stdout.strip())
            check(ran.returncode == 0 and 'PROBE OK' in ran.stdout, 'take-over probe failed')
print('ODP_TEST_PHASE ' + json.dumps({'name': 'probe', 'seconds': round(time.monotonic() - probe_started, 3)}))

if failures:
    for failure in failures:
        print('FAIL: ' + failure)
    sys.exit(1)
print('OK: Moreya name, exit screen, icon files and user data take-over')
