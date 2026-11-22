"""Room packages: ten rooms take their assets from a private room package; without it the room is unavailable.

Static part, always:
  * source/rooms/RoomPackages.cpp names exactly the ten packaged rooms of scripts/room_packages.py (room name and room
    type number, fixed for this branch) and finds the packages in the folders of the wing packages;
  * the gates exist: the server, the editor, the AI and the build of a room on tiles refuse a room without package
    (SkillManager::isRoomAvailable, RoomManager::buildRoom/buildRoomEditor/buildRoomOnTiles), its build button is hidden
    and its research shown not allowed (SkillDefRoom, GameMode::refreshSkillButtonState), a level or save leaves such a
    room out and keeps loading (MapHandler), the ghost room equipment and saved capture boxes and herb bundles need
    their packages, the asset folders and sounds of found packages are loaded (ResourceManager, SoundEffectsManager)
    and the packages are found at startup (ODApplication);
  * the public tree holds none of the 319 packaged room assets (PACKAGED_ASSETS of scripts/room_packages.py, fixed for
    this branch);
  * with the content present: every package of the content repository has its Package.cfg naming its room and exactly
    the files of PACKAGED_ASSETS.
Probe (needs cl): RoomPackages.cpp compiled with small stand-ins for the logger, the wing package folders and
boost::filesystem (std::filesystem) answers: a room without package is unavailable, a room with package is available,
a room that needs no package is always available, a wing package names no room, the first package of a room wins.
Runtime part, when the built game build/windows/moreya.exe exists: the game plays levels/skirmish/TestSpa.level (a
tavern and a spa) with the load test parameters (--run-level, 1 second) without MOREYA_CONTENT_DIR, so no room package
is found; the run must pass and the log must show both rooms left out.

Usage: python source/tests/check_room_packages.py
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import campaign_packages  # noqa: E402
import room_packages  # noqa: E402

#: Files of each room package, counted once for this branch (Package.cfg included)
PACKAGE_FILES = {"GuardRoom": 1, "Temple": 2, "Toilet": 39, "Merchant": 35, "HerbGarden": 22, "AlchemyLab": 9,
                 "Tavern": 84, "Infirmary": 32, "GhostRoom": 80, "Spa": 25}
#: The level of the runtime part and the packaged rooms it holds
RUNTIME_LEVEL = "levels/skirmish/TestSpa.level"
RUNTIME_ROOMS = ("Tavern", "Spa")
EXECUTABLE = ROOT / "build/windows/moreya.exe"
#: Game seconds of the runtime part (the load test minimum) and its wall-clock limit (the load test's 2 * seconds + 400)
PROBE_SECONDS = 1
PROBE_TIMEOUT = 420

failures = []


def check(condition, message):
    """Records a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(relative):
    """A file of the repository as text."""
    return (ROOT / relative).read_text(encoding="utf-8")


def body(source, signature):
    """A complete brace-delimited function starting at its signature."""
    start = source.index(signature)
    depth = 0
    for index in range(source.index("{", start), len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start:index + 1]
    return source[start:]


def phase(name, started):
    """Prints a phase measurement of this check."""
    print("ODP_TEST_PHASE " + json.dumps({"name": name, "seconds": round(time.monotonic() - started, 3)}), flush=True)


started = time.monotonic()
check(len(room_packages.ROOMS) == 10 and sum(PACKAGE_FILES.values()) == 329,
      "ten packaged rooms with 329 package files are fixed for this branch")
check(all(len(room_packages.PACKAGED_ASSETS[name]) + 1 == PACKAGE_FILES[name] for name in room_packages.ROOM_NAMES),
      "PACKAGED_ASSETS of room_packages.py must list the package files of this branch")

# The table of the game is the table of the scripts
packages_cpp = read("source/rooms/RoomPackages.cpp")
table = re.findall(r'\{ RoomType::(\w+), "(\w+)" \}', packages_cpp)
check([name for _, name in table] == list(room_packages.ROOM_NAMES),
      "RoomPackages.cpp must name the ten packaged rooms of room_packages.py in room type order: %s" % table)
enum = re.search(r"enum class RoomType\s*\{(.*?)\};", read("source/rooms/RoomType.h"), re.S).group(1)
numbers = {name: index for index, name in enumerate(re.findall(r"^\s*(\w+)", enum, re.M))}
check([numbers.get(kind) for kind, _ in table] == [number for _, _, number in room_packages.ROOMS],
      "the room type numbers of the packaged rooms must be those of room_packages.py")
check('ROOM_KEY = "%s"' % room_packages.ROOM_KEY in packages_cpp
      and "CampaignPackages::getPackageFolders(gameDataPath)" in body(packages_cpp, "void RoomPackages::discover(")
      and "CampaignPackages::DEFINITION_FILE" in packages_cpp,
      "the game must find room packages by Package.cfg in the folders of the wing packages")

# The gates
skills = read("source/game/SkillManager.cpp")
check("RoomPackages::isRoomAvailable(type)" in body(skills, "bool SkillManager::isRoomAvailable("),
      "SkillManager::isRoomAvailable (server, AI) must refuse a room without package")
check("button->hide()" in skills and "bool isContentAvailable() const override" in skills,
      "the build button of a room without package must be hidden and its skill must need the package")
rooms = read("source/rooms/RoomManager.cpp")
for signature in ("bool RoomManager::buildRoom(", "bool RoomManager::buildRoomEditor(",
                  "bool RoomManager::buildRoomOnTiles("):
    check("isRoomPackageAvailable(type)" in body(rooms, signature), signature + " must refuse a room without package")
game_mode = body(read("source/modes/GameMode.cpp"), "void GameMode::refreshSkillButtonState(")
check("SkillManager::isSkillContentAvailable(resType)" in game_mode and "&& isContentAvailable)" in game_mode,
      "the research of a room without package must be not allowed and its build button hidden")
loader = read("source/gamemap/MapHandler.cpp")
check("RoomPackages::isRoomAvailable(tempRoom->getType())" in loader and "delete tempRoom;" in loader,
      "a level or save must leave a room without package out and keep loading")
check("RoomPackages::isRoomAvailable(RoomType::ghostRoom)" in loader
      and "RoomPackages::isRoomAvailable(RoomType::herbGarden)" in loader,
      "saved capture boxes and herb bundles need their room packages")
check("RoomPackages::isRoomAvailable(RoomType::ghostRoom)" in body(read("source/entities/Creature.cpp"),
                                                                   "void Creature::updateGhostHuntVisuals("),
      "ghost hunters show their equipment only with the ghost room package")
resources = read("source/utils/ResourceManager.cpp")
folders = body(resources, "void ResourceManager::addRoomPackageResources(")
check(all('"%s"' % folder in folders for folder in ("models", "materials/scripts", "materials/textures", "particles"))
      and "addRoomPackageResources();" in body(resources, "void ResourceManager::setupOgreResources("),
      "the asset folders of the room packages must be added to the Graphics group")
check("RoomPackages::getPackageDirectories()" in read("source/sound/SoundEffectsManager.cpp"),
      "the sounds of the room packages must be loaded")
check("RoomPackages::discover(resMgr.getGameDataPath())" in read("source/ODApplication.cpp"),
      "the game must find the room packages at startup")

# The public tree holds none of the packaged room assets
tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True,
                             check=True).stdout.split("\n"))
for relative in sorted(room_packages.ASSET_ROOMS):
    check(relative not in tracked, "%s moved into the package of room %s" % (relative,
                                                                            room_packages.ASSET_ROOMS[relative]))

# The content packages
content = room_packages.packages(ROOT)
content_note = "content not present: package contents not checked"
if content:
    check(sorted(content) == sorted(room_packages.ROOM_NAMES), "the content must hold a package of every packaged "
          "room, found: %s" % sorted(content))
    for name, folder, _ in room_packages.ROOMS:
        if name not in content:
            continue
        check(content[name].name == folder, "%s: package folder %s, expected %s" % (name, content[name].name, folder))
        files = sorted(path.relative_to(content[name]).as_posix() for path in content[name].rglob("*")
                       if path.is_file())
        expected = sorted(list(room_packages.PACKAGED_ASSETS[name]) + [campaign_packages.DEFINITION_FILE])
        check(files == expected, "%s: the package files differ from PACKAGED_ASSETS: extra %s, missing %s"
              % (name, sorted(set(files) - set(expected)), sorted(set(expected) - set(files))))
        definition = (content[name] / campaign_packages.DEFINITION_FILE).read_text(encoding="utf-8")
        check(room_packages.parse_definition(definition) == name, "%s: Package.cfg must name its room" % name)
        # The names the checks know without the package are the names its scripts define
        materials = sorted(re.findall(r"^\s*material\s+([^\s:{]+)", "".join(
            path.read_text(encoding="utf-8") for path in (content[name] / "materials/scripts").glob("*.material")), re.M))
        particles = sorted(re.findall(r"^\s*particle_system\s+(\S+)", "".join(
            path.read_text(encoding="utf-8") for path in (content[name] / "particles").glob("*.particle")), re.M))
        check(materials == sorted(room_packages.PACKAGED_MATERIALS.get(name, ())),
              "%s: the materials of the package differ from PACKAGED_MATERIALS: %s" % (name, materials))
        check(particles == sorted(room_packages.PACKAGED_PARTICLES.get(name, ())),
              "%s: the particle systems of the package differ from PACKAGED_PARTICLES: %s" % (name, particles))
    content_note = "content present: %d packages, %d files" % (len(content), sum(PACKAGE_FILES.values()))
phase("static", started)

# Probe: the real RoomPackages.cpp with stand-ins for its logger, the wing package folders and boost::filesystem
PROBE = r'''
#include "rooms/RoomPackages.cpp"
#include <fstream>
#include <iostream>

const std::string CampaignPackages::DEFINITION_FILE = "Package.cfg";
//! Folder of the test content (the stand-in of MOREYA_CONTENT_DIR)
static std::string contentFolder;

//! \brief levels/campaign/ of the game data, then the test content folder, like the game.
std::vector<std::string> CampaignPackages::getPackageFolders(const std::string& gameDataPath)
{
    std::vector<std::string> folders;
    folders.push_back(gameDataPath + "levels/campaign/");
    folders.push_back(contentFolder);
    return folders;
}

static int failures = 0;

//! \brief Reports a failed expectation without stopping the other cases.
static void check(bool condition, const char* message)
{
    if(!condition)
    {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

//! \brief Writes a Package.cfg with the given text into a new folder.
static void writePackage(const std::filesystem::path& folder, const std::string& text)
{
    std::filesystem::create_directories(folder);
    std::ofstream file((folder / "Package.cfg").string().c_str(), std::ios::binary);
    file << text;
}

//! \brief Runs the package cases in the folder given as first argument.
int main(int argc, char** argv)
{
    const std::filesystem::path root(argv[1]);
    check(RoomPackages::getPackagedRooms().size() == 10, "ten packaged rooms");
    check(RoomPackages::parseDefinition("# comment\nRoom = Tavern\n") == RoomType::tavern, "Room=Tavern names the tavern");
    check(RoomPackages::parseDefinition("Room=Dormitory\n") == RoomType::nullRoomType, "a room that needs no package");
    check(RoomPackages::parseDefinition("[Level]\nFile=campaign/A.level\nWing=2\n") == RoomType::nullRoomType,
        "a wing package names no room");

    // Without packages: every packaged room is unavailable, every other room available
    RoomPackages::setPackages(std::map<RoomType, std::string>());
    for(RoomType type : RoomPackages::getPackagedRooms())
        check(!RoomPackages::isRoomAvailable(type), "a packaged room without package is unavailable");
    check(RoomPackages::isRoomAvailable(RoomType::dormitory) && RoomPackages::isRoomAvailable(RoomType::dungeonTemple),
        "a room that needs no package is always available");
    check(RoomPackages::getPackageDirectory(RoomType::tavern).empty(), "no folder without package");

    // With the packages of the tavern (twice) and the spa next to a wing package
    contentFolder = (root / "content").generic_string();
    writePackage(root / "data/levels/campaign/wing1", "[Level]\nFile=campaign/One.level\nWing=1\n");
    writePackage(root / "content/room-tavern", "Room=Tavern\n");
    writePackage(root / "content/room-spa", "# Room package\nRoom=Spa\n");
    writePackage(root / "content/wing2", "[Level]\nFile=campaign/Two.level\nWing=2\n");
    writePackage(root / "content/zz-tavern-copy", "Room=Tavern\n");
    std::filesystem::create_directories(root / "content/room-ghost-room");
    RoomPackages::discover((root / "data").generic_string() + "/");
    check(RoomPackages::isRoomAvailable(RoomType::tavern) && RoomPackages::isRoomAvailable(RoomType::spa),
        "a room with package is available");
    check(!RoomPackages::isRoomAvailable(RoomType::ghostRoom), "a folder without Package.cfg is no package");
    check(!RoomPackages::isRoomAvailable(RoomType::merchant), "a room without package stays unavailable");
    check(RoomPackages::getPackageDirectory(RoomType::tavern) == (root / "content/room-tavern").generic_string(),
        "the first package of a room wins");
    check(RoomPackages::getPackageDirectories().size() == 2, "two packages found");
    std::cout << "room packages probe: failures=" << failures << '\n';
    return failures == 0 ? 0 : 1;
}
'''

BOOST_STAND_IN = r'''
#pragma once
#include <filesystem>
#include <system_error>
namespace boost { namespace system { typedef std::error_code error_code; }
namespace filesystem
{
typedef std::filesystem::path path;
typedef std::filesystem::directory_iterator directory_iterator;
inline bool is_directory(const path& p, std::error_code& e) { return std::filesystem::is_directory(p, e); }
inline bool is_regular_file(const path& p, std::error_code& e) { return std::filesystem::is_regular_file(p, e); }
} }
'''
CAMPAIGN_STAND_IN = r'''
#pragma once
#include <string>
#include <vector>
namespace CampaignPackages
{
    extern const std::string DEFINITION_FILE;
    std::vector<std::string> getPackageFolders(const std::string& gameDataPath);
}
'''
LOG_STAND_IN = r'''
#pragma once
#include <iostream>
#include <string>
#define OD_LOG_INF(_message) (std::clog << (std::string("") + _message) << '\n')
#define OD_LOG_WRN(_message) (std::clog << (std::string("") + _message) << '\n')
'''

probe_note = "probe not run: cl is not on the PATH"
if shutil.which("cl") and not failures:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="odp-room-packages-") as directory:
        work = Path(directory)
        for relative, text in (("boost/filesystem.hpp", BOOST_STAND_IN), ("game/CampaignPackages.h", CAMPAIGN_STAND_IN),
                               ("utils/LogManager.h", LOG_STAND_IN), ("probe.cpp", PROBE)):
            (work / relative).parent.mkdir(parents=True, exist_ok=True)
            (work / relative).write_text(text, encoding="utf-8")
        build = subprocess.run(["cl", "/nologo", "/EHsc", "/std:c++17", "/I" + str(work), "/I" + str(ROOT / "source"),
                                "probe.cpp", "/Feprobe.exe"], cwd=work, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=600)
        check(build.returncode == 0, "the probe must compile:\n" + build.stdout[-2000:])
        phase("probe:compile", started)
        if build.returncode == 0:
            started = time.monotonic()
            cases = work / "cases"
            cases.mkdir()
            run = subprocess.run([str(work / "probe.exe"), str(cases)], cwd=work, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=120)
            check(run.returncode == 0, "the room package probe failed:\n" + (run.stdout + run.stderr)[-2000:])
            phase("probe:execute", started)
            probe_note = "probe passed"

# Runtime: a level with a tavern and a spa loads without the room packages
runtime_note = "not run: the built game %s is missing" % EXECUTABLE.relative_to(ROOT)
if EXECUTABLE.is_file() and not failures:
    started = time.monotonic()
    environment = dict(os.environ)
    environment[campaign_packages.CONTENT_VARIABLE] = ""
    app_data = tempfile.mkdtemp(prefix="od-no-room-packages-")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    try:
        result = subprocess.run([str(EXECUTABLE), "--run-level", str(ROOT / RUNTIME_LEVEL), "--seconds",
                                 str(PROBE_SECONDS), "--appData", app_data, "--port", str(port)],
                                cwd=str(EXECUTABLE.parent), env=environment, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT, stdin=subprocess.DEVNULL)
        logs = "".join(path.read_text(encoding="utf-8", errors="replace") for path in Path(app_data).rglob("*.log"))
    finally:
        shutil.rmtree(app_data, ignore_errors=True)
    phase("runtime", started)
    output = result.stdout + result.stderr + logs
    check(result.returncode == 0 and "PASS " + Path(RUNTIME_LEVEL).name in output,
          "the level with a tavern and a spa must load and pass without room packages:\n"
          + "\n".join(output.splitlines()[-12:]))
    for room in RUNTIME_ROOMS:
        check("the package of room %s is missing" % room in output, "the log must show the %s left out" % room)
    runtime_note = "%s passed without room packages, tavern and spa left out" % Path(RUNTIME_LEVEL).name

if failures:
    print("\n".join(failures).encode("ascii", "replace").decode("ascii"))
    sys.exit(1)
print("room packages: 10 packaged rooms, gates in place, 319 packaged assets absent from the public tree; %s; %s; %s: PASS"
      % (content_note, probe_note, runtime_note))
