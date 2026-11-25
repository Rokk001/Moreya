"""Content packages: the content of the game lies in content packages; without them the game says so and quits.

Static part, always:
  * source/utils/ContentPackages.cpp names exactly the 25 required content packages of scripts/content_packages.py
    (REQUIRED_PACKAGES, fixed for this branch) and finds them in the folders of the wing packages;
  * the gates exist: ODApplication refuses the start when a required package is missing, main shows the message
    (a message box unless the run is headless) and returns exit code 7; every game data lookup falls back to the
    packages: resources.cfg locations (ResourceManager::addGameDataResourceLocation), the startup loading folders,
    the sound families, the level lists and their official level check, Helper::readFile and the direct readers of
    config/ tables, the portraits and the campaign map;
  * the public tree holds no folder that moved into the packages as a whole (PACKAGED_FOLDERS, fixed).
With the content present: every required package has its Package.cfg naming it, holds exactly the number of files of
checks/content_packages.json of the content repository (fixed there, counted once per content branch), and no file
of a content package is also in the public tree.
Runtime part, when the built game build/windows/moreya.exe exists: the game plays levels/skirmish/TestSpa.level with the
load test parameters (--run-level, 1 second) without content (MOREYA_CONTENT_DIR empty); it must quit with exit code 7
and print the missing content message.

Usage: python source/tests/check_content_packages.py
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

#: Folders of the game data that moved into the content packages as a whole, fixed for this branch
PACKAGED_FOLDERS = ('gui/RoomCentreArtwork', 'gui/RoomCentreIcons', 'gui/campaign', 'gui/herbs', 'gui/items',
                    'gui/potions', 'levels/campaign/wing1', 'materials/portraits', 'materials/textures/loading',
                    'materials/textures/menu', 'materials/textures/tavern')
#: The level of the runtime part and the game it starts
RUNTIME_LEVEL = 'levels/skirmish/TestSpa.level'
EXECUTABLE = ROOT / 'build/windows/moreya.exe'
#: Game seconds of the runtime part (the load test minimum) and its wall-clock limit (the load test's 2 * seconds + 400)
PROBE_SECONDS = 1
PROBE_TIMEOUT = 420
MISSING_TEXT = 'The content of Moreya is missing'

failures = []


def check(condition, message):
    """Records a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(relative):
    """A file of the repository as text."""
    return (ROOT / relative).read_text(encoding='utf-8')


def body(source, signature):
    """A complete brace-delimited function starting at its signature."""
    start = source.index(signature)
    depth = 0
    for index in range(source.index('{', start), len(source)):
        depth += (source[index] == '{') - (source[index] == '}')
        if depth == 0:
            return source[start:index + 1]
    return source[start:]


def phase(name, started):
    """Prints a phase measurement of this check."""
    print('ODP_TEST_PHASE {"name":"%s","seconds":%.3f}' % (name, time.monotonic() - started))


def check_static():
    """The required package table, the start gate and the lookups of the game code."""
    packages_cpp = read('source/utils/ContentPackages.cpp')
    table = packages_cpp[packages_cpp.index('REQUIRED_PACKAGES[] ='):]
    table = table[:table.index('};')]
    names = tuple(re.findall(r'"([a-z0-9-]+)"', table))
    check(names == content_packages.REQUIRED_PACKAGES, 'ContentPackages.cpp names the 25 required packages')
    check(len(content_packages.REQUIRED_PACKAGES) == 25, 'scripts/content_packages.py names 25 required packages')
    check(list(names) == sorted(names), 'the required packages are sorted')
    check('CampaignPackages::getPackageFolders(gameDataPath)' in body(packages_cpp, 'void ContentPackages::discover('),
          'the packages are found in the folders of the wing packages')
    header = read('source/utils/ContentPackages.h')
    check('const int MISSING_CONTENT_EXIT_CODE = 7;' in header, 'exit code 7 without content')
    check('CONTENT_KEY = "Content"' in packages_cpp, 'Package.cfg names a content package with Content=')

    application = read('source/ODApplication.cpp')
    start = body(application, 'void ODApplication::startGame(')
    gate = 'ContentPackages::discover(resMgr.getGameDataPath());'
    check(gate in start and start.index(gate) < start.index('ContentPackages::setStartRefused(true);')
          < start.index('startClient();'), 'the game refuses to start before any mode when content is missing')
    main = read('source/main.cpp')
    check('ContentPackages::isStartRefused()' in main and 'return ContentPackages::MISSING_CONTENT_EXIT_CODE;' in main
          and 'MessageBox(0, message.c_str(), "Moreya"' in main, 'main shows the message and returns exit code 7')
    check(MISSING_TEXT in packages_cpp, 'the message says that the content is missing')

    resources = read('source/utils/ResourceManager.cpp')
    check('addGameDataResourceLocation(archName, typeName, secName);' in resources,
          'resources.cfg locations come from the game data and the content packages')
    check('ContentPackages::setPackages(mGameDataPath,' in resources, 'the packages are known before the options')
    check('getStartupLoadingFolders(resMgr.getGameDataPath())' in application, 'startup loading folders of the packages')
    check('ContentPackages::getPackageDirectories()' in read('source/sound/SoundEffectsManager.cpp'),
          'the sounds of the content packages are loaded')
    map_handler = read('source/gamemap/MapHandler.cpp')
    check('ContentPackages::getDataFolders(path)' in body(map_handler, 'bool fillLevelFilesList('),
          'the level lists include the content packages')
    check(map_handler.count('getGameLevelsRootOf(') >= 4, 'the official level check knows the package level folders')
    check('ContentPackages::resolveFile(fileName)' in read('source/utils/Helper.cpp'),
          'Helper::readFile reads game data files of the packages')
    for reader in ('source/social/SocialData.cpp', 'source/render/DungeonbookAppearanceConfig.cpp',
                   'source/render/DungeonbookQuirks.cpp', 'source/render/PortraitTint.cpp',
                   'source/render/RenderManager.cpp', 'source/render/RoomAmbienceConfig.cpp'):
        check('ContentPackages::resolveFile(' in read(reader), reader + ' reads its table from the packages')
    for reader in ('source/entities/Creature.cpp', 'source/render/CreatureAppearancePicture.cpp'):
        check('ContentPackages::resolveFolder(' in read(reader), reader + ' finds the portraits in the packages')
    check(read('source/modes/MenuModeCampaign.cpp').count('ContentPackages::resolveFile(') == 2,
          'the campaign map and its images are found in the packages')
    check('ContentPackages.cpp' in read('CMakeLists.txt'), 'ContentPackages.cpp is built')

    for folder in PACKAGED_FOLDERS:
        check(not (ROOT / folder).exists(), 'the public tree no longer has ' + folder)


def check_content():
    """With the content present: the packages, their file counts and no file in both places."""
    if not content_packages.has_content(ROOT):
        content_packages.unchecked('check_content_packages', ['package definitions and file counts of '
                                                              + ', '.join(content_packages.missing_packages(ROOT))])
        return
    expected = campaign_packages.content_data(ROOT, 'content_packages')['files']
    found = content_packages.packages(ROOT)
    check(sorted(expected) == list(content_packages.REQUIRED_PACKAGES),
          'checks/content_packages.json names the required packages')
    for name in content_packages.REQUIRED_PACKAGES:
        folder = found[name]
        definition = (folder / content_packages.DEFINITION_FILE).read_text(encoding='utf-8')
        check(content_packages.parse_definition(definition) == name, name + ': Package.cfg names the package')
        files = [path for path in folder.rglob('*') if path.is_file()]
        check(len(files) == expected.get(name), '%s holds %s files, found %d' % (name, expected.get(name), len(files)))
        for path in files:
            relative = path.relative_to(folder).as_posix()
            if relative != content_packages.DEFINITION_FILE:
                check(not (ROOT / relative).exists(), 'in the public tree and in ' + name + ': ' + relative)


def check_runtime():
    """The built game without content quits with exit code 7 and the message."""
    if not EXECUTABLE.is_file():
        print('check_content_packages: build/windows/moreya.exe not built, runtime part not run')
        return
    environment = dict(os.environ)
    environment[campaign_packages.CONTENT_VARIABLE] = ''
    level = (ROOT / RUNTIME_LEVEL).resolve()
    result = subprocess.run([str(EXECUTABLE), '--run-level', str(level), '--seconds', str(PROBE_SECONDS)],
                            cwd=str(EXECUTABLE.parent), env=environment, capture_output=True, text=True,
                            errors='replace', timeout=PROBE_TIMEOUT)
    check(result.returncode == content_packages.MISSING_CONTENT_EXIT_CODE,
          'without content the game quits with exit code 7, got %d' % result.returncode)
    check(MISSING_TEXT in result.stderr, 'without content the game prints the missing content message')


def main():
    """Runs the parts and reports the failures."""
    started = time.monotonic()
    check_static()
    phase('static', started)
    started = time.monotonic()
    check_content()
    phase('content', started)
    started = time.monotonic()
    check_runtime()
    phase('runtime', started)
    if failures:
        for failure in failures:
            print('FAIL: ' + failure)
        return 1
    print('check_content_packages: ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
