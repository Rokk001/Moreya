"""Own rows of the mixed files: the public files keep the upstream rows, the own rows come from the content.

The mixed files are the upstream data tables of config/ and the upstream interface files of gui/ (layouts,
OD.looknfeel, ODSkin.scheme and fonts; the imagesets ODIcons and ODSkin lie whole in the package gui-skin) with rows the project wrote itself.

Static part, always:
  * Helper::readFile puts the own rows in place of the marker lines (ContentPackages::mergeOwnRows) and logs a
    missing or an unused block; ContentPackages.h finds the own rows file at the path with ".own" before the
    extension (getOwnRowsPath) like every game data file (resolveFile); the interface uses the resource provider
    OwnRowsResourceProvider of Gui.cpp, which joins the blocks the same way (joinOwnRows);
  * every mixed file of OWN_ROW_TABLES has exactly its fixed number of marker lines ("#@own <n>", in an interface
    file "<!--#@own <n>-->"), numbered 1, 2, 3, ... in order (counted once when the own rows were split off), and
    no other table of config/ or interface file of gui/ has one.
With the content present:
  * every file has its own rows file in the content package core-config (tables) or core-gui (interface files),
    every marker has exactly one block and every block a marker;
  * the joined table (as the game and content_packages.read_text read it) has the SHA-256 of
    checks/config_own_rows.json of the content repository: fixed there when the own rows were split off, so the
    game reads every value exactly as before the split, and updated there by every later change of a value;
  * a small probe compiled with cl from ContentPackages.h joins every table the way the game does; its text must
    equal the joined text of scripts/config_own_rows.py.

Usage: python source/tests/check_config_own_rows.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import campaign_packages  # noqa: E402
import config_own_rows  # noqa: E402
import content_packages  # noqa: E402

#: The mixed data tables and interface files and their number of marker lines, counted once when the own rows were
#: split off
OWN_ROW_TABLES = {
    'config/creatures.cfg': 603,
    'config/equipments.cfg': 153,
    'config/global.cfg': 17,
    'config/mainmenuscene.cfg': 19,
    'config/rooms.cfg': 25,
    'config/skills.cfg': 8,
    'config/spawnconditions.cfg': 9,
    'config/spells.cfg': 12,
    'config/tilesets.cfg': 30,
    'config/traps.cfg': 10,
    'gui/EditorLoad.layout': 6,
    'gui/EditorNew.layout': 4,
    'gui/EditorSave.layout': 7,
    'gui/LoadConfirm.layout': 3,
    'gui/MenuConfigureSeats.layout': 18,
    'gui/MenuEditorLoad.layout': 15,
    'gui/MenuEditorNew.layout': 6,
    'gui/MenuLoad.layout': 16,
    'gui/MenuMain.layout': 15,
    'gui/MenuMasterServerJoin.layout': 17,
    'gui/MenuMultiplayerClient.layout': 17,
    'gui/MenuMultiplayerServer.layout': 18,
    'gui/MenuReplay.layout': 15,
    'gui/MenuSkirmish.layout': 16,
    'gui/ModeEditor.layout': 27,
    'gui/ModeGame.layout': 54,
    'gui/OD.looknfeel': 814,
    'gui/ODSkin.scheme': 9,
    'gui/WidgetsTest.layout': 1,
    'gui/WindowApplyChanges.layout': 4,
    'gui/WindowConsole.layout': 1,
    'gui/WindowEditorHelp.layout': 1,
    'gui/WindowEditorOptions.layout': 4,
    'gui/WindowEditorPortalWaves.layout': 8,
    'gui/WindowEditorSubMenu.layout': 3,
    'gui/WindowEvent.layout': 1,
    'gui/WindowGameOptions.layout': 11,
    'gui/WindowHelp.layout': 1,
    'gui/WindowMultiplayerSubMenu.layout': 5,
    'gui/WindowObjectives.layout': 3,
    'gui/WindowQuit.layout': 5,
    'gui/WindowSettings.layout': 49,
    'gui/WindowSkillTree.layout': 190,
    'gui/WindowSkirmishSubMenu.layout': 3,
    'gui/WindowStats.layout': 1,
    'gui/WindowTabCreatures.layout': 9,
    'gui/WindowTabRooms.layout': 53,
    'gui/WindowTabSpells.layout': 41,
    'gui/WindowTabTraps.layout': 21,
    'gui/fonts/LiberationSans-10.font': 1,
    'gui/fonts/LiberationSans-20.font': 1,
    'gui/fonts/MedievalSharp-10.font': 1,
    'gui/fonts/MedievalSharp-12.font': 1,
}
#: Wall-clock limit of the probe compilation and of its run
PROBE_TIMEOUT = 300

failures = []

PROBE = r'''
#include "utils/ContentPackages.h"

#include <cstdio>
#include <fstream>
#include <iostream>

//! \brief Joins every table named on the command line the way Helper::readFile does and writes it to <out>/<n>.txt.
//! Arguments: <game data folder> <core-config folder> <core-gui folder> <out folder> <table>...
int main(int argc, char** argv)
{
    if(argc < 5)
        return 2;
    std::map<std::string, std::string> packages;
    packages["core-config"] = argv[2];
    packages["core-gui"] = argv[3];
    ContentPackages::setPackages(argv[1], packages);
    for(int index = 5; index < argc; ++index)
    {
        const std::string table = std::string(argv[1]) + "/" + argv[index];
        std::ifstream file(table.c_str(), std::ifstream::in);
        std::vector<std::string> lines;
        std::string line;
        while(std::getline(file, line))
        {
            if(!line.empty() && (line[line.size() - 1] == '\r'))
                line.erase(line.size() - 1);
            lines.push_back(line);
        }
        bool hasOwnRows = false;
        std::vector<int> missing;
        std::vector<int> unused;
        ContentPackages::mergeOwnRows(table, lines, hasOwnRows, missing, unused);
        if(!hasOwnRows || !missing.empty() || !unused.empty())
        {
            std::cout << argv[index] << ": own rows " << hasOwnRows << ", missing " << missing.size()
                      << ", unused " << unused.size() << std::endl;
            return 1;
        }
        char name[32];
        std::sprintf(name, "/%d.txt", index - 5);
        std::ofstream out((std::string(argv[4]) + name).c_str(), std::ios::binary);
        for(std::vector<std::string>::const_iterator it = lines.begin(); it != lines.end(); ++it)
            out << *it << "\n";
    }
    return 0;
}
'''


def check(condition, message):
    """Records a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(relative):
    """A file of the repository as text."""
    return (ROOT / relative).read_text(encoding='utf-8')


def phase(name, started):
    """Prints the measured seconds of a phase for the profiled check wrapper."""
    print('ODP_TEST_PHASE ' + json.dumps({'name': name, 'seconds': round(time.monotonic() - started, 3)}))


def check_static():
    """The game joins the tables; the public tables have their fixed markers and nothing else has one."""
    helper = read('source/utils/Helper.cpp')
    check('ContentPackages::mergeOwnRows(fileName, lines, hasOwnRows, missing, unused);' in helper,
          'Helper::readFile joins the own rows')
    check('is missing for' in helper and 'has no marker in' in helper,
          'Helper::readFile logs a missing and an unused block')
    header = read('source/utils/ContentPackages.h')
    for name in ('getOwnRowsPath', 'getOwnRowsMarker', 'readOwnRows', 'mergeOwnRows'):
        check('inline ' in header and name + '(' in header, 'ContentPackages.h defines ' + name)
    check('resolveFile(getOwnRowsPath(tablePath))' in header, 'the own rows file is found like every game data file')
    check(config_own_rows.own_rows_path('config/global.cfg') == 'config/global.own.cfg',
          'the own rows file of config/global.cfg is config/global.own.cfg')
    gui = read('source/render/Gui.cpp')
    check('class OwnRowsResourceProvider : public CEGUI::OgreResourceProvider' in gui
          and 'ContentPackages::joinOwnRows(lines, blocks, missing, unused);' in gui
          and '*(new OwnRowsResourceProvider())' in gui,
          'the interface loads its files through OwnRowsResourceProvider, which joins the own rows')
    files = sorted((ROOT / 'config').glob('*.cfg'))
    files += sorted(path for path in (ROOT / 'gui').rglob('*') if config_own_rows.is_xml(path.name))
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        numbers = config_own_rows.markers(path.read_text(encoding='utf-8'))
        expected = OWN_ROW_TABLES.get(relative, 0)
        check(len(numbers) == expected, '%s has %d marker lines, expected %d' % (relative, len(numbers), expected))
        check(numbers == list(range(1, len(numbers) + 1)), relative + ': the markers are numbered 1, 2, 3, ...')
    for relative in OWN_ROW_TABLES:
        check((ROOT / relative).is_file(), relative + ' is in the public tree')


def joined_tables():
    """The joined text of every table, by its path; records the failures of the content part."""
    expected = (campaign_packages.content_data(ROOT, 'config_own_rows') or {}).get('tables', {})
    check(sorted(expected) == sorted(OWN_ROW_TABLES), 'checks/config_own_rows.json names the mixed files')
    joined = {}
    for relative in sorted(OWN_ROW_TABLES):
        own = config_own_rows.own_rows_file(ROOT, relative)
        package = content_packages.packages(ROOT).get(config_own_rows.own_rows_package(relative))
        check(own is not None and package is not None and own == Path(package) / config_own_rows.own_rows_path(relative),
              relative + ': its own rows file lies in the package ' + config_own_rows.own_rows_package(relative))
        if own is None:
            continue
        public = read(relative)
        blocks = config_own_rows.parse_own_rows(own.read_text(encoding='utf-8'))
        check(sorted(blocks) == config_own_rows.markers(public), relative + ': every marker has exactly one block')
        try:
            text = config_own_rows.join(public, own.read_text(encoding='utf-8'))
        except ValueError as error:
            check(False, '%s: %s' % (relative, error))
            continue
        check(text == content_packages.read_text(ROOT, relative), relative + ': read_text gives the joined table')
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        check(digest == expected.get(relative), '%s: the joined table has the SHA-256 %s, expected %s'
              % (relative, digest, expected.get(relative)))
        joined[relative] = text
    return joined


def check_probe(joined):
    """The C++ join of ContentPackages.h gives the same text as the Python join."""
    if not joined:
        return
    found = content_packages.packages(ROOT)
    packages = [str(found.get(config_own_rows.OWN_ROWS_PACKAGE)), str(found.get(config_own_rows.OWN_GUI_PACKAGE))]
    tables = sorted(joined)
    work = Path(tempfile.mkdtemp(prefix='own_rows_'))
    try:
        (work / 'probe.cpp').write_text(PROBE, encoding='utf-8')
        result = subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/I', str(ROOT / 'source'), 'probe.cpp',
                                 '/Feprobe.exe'], cwd=str(work), capture_output=True, text=True, errors='replace',
                                timeout=PROBE_TIMEOUT)
        check(result.returncode == 0, 'the probe compiles: ' + result.stdout[-2000:])
        if result.returncode != 0:
            return
        result = subprocess.run([str(work / 'probe.exe'), str(ROOT)] + packages + [str(work)] + tables,
                                cwd=str(work), capture_output=True, text=True, errors='replace',
                                timeout=PROBE_TIMEOUT)
        check(result.returncode == 0, 'the probe joins every table: ' + result.stdout[-2000:])
        if result.returncode != 0:
            return
        for index, relative in enumerate(tables):
            text = (work / ('%d.txt' % index)).read_bytes().decode('utf-8')
            check(text.splitlines() == joined[relative].splitlines(), relative + ': the game joins the table like scripts/config_own_rows.py')
    finally:
        shutil.rmtree(str(work), ignore_errors=True)


def main():
    """Runs the parts and reports the failures."""
    started = time.monotonic()
    check_static()
    phase('static', started)
    if content_packages.has_content(ROOT):
        started = time.monotonic()
        joined = joined_tables()
        phase('content', started)
        started = time.monotonic()
        check_probe(joined)
        phase('probe', started)
    else:
        content_packages.unchecked('check_config_own_rows', ['own rows and joined values of the %d mixed files'
                                                             % len(OWN_ROW_TABLES)])
    if failures:
        for failure in failures:
            print('FAIL: ' + failure)
        return 1
    print('check_config_own_rows: ok')
    return 0


if __name__ == '__main__':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    sys.exit(main())
