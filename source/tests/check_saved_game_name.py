"""Check: saved games of games played on own maps (.mmap) are listed by the Load menu.

    python source/tests/check_saved_game_name.py   (cl must be on the path: run it under vcvars64)

A saved game is named <date>-SK-<level file> or <date>-MP-<level file>. Own maps end in .mmap, the Load menu lists
only .level files of the saved game folder, so a saved game keeps the .level extension whatever the map's extension.
Requirements checked (each reported on its own, expected values are fixed):
  S1  OfficialLevels::toSavedGameName turns a trailing .mmap into .level and leaves every other name as it is
      (compiled probe on OfficialLevels.cpp)
  S2  askSaveMap builds the path of a saved game (not of an editor save) with OfficialLevels::toSavedGameName, after
      the SK-/MP- prefix is chosen (static)
  S3  the consumers of saved-game names stay as they were: the Load menu lists ".level" in the saved game folder,
      the load filter and the campaign look for "SK-" and "MP-" (static)
It compiles one probe with cl and starts no game."""
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
DEPS = Path(os.environ.get('BUILD_DEPS_ROOT', str(Path(os.environ.get('USERPROFILE', '.')) / 'build-deps')))


def check(condition, message):
    """Records a failed requirement."""
    if not condition:
        failures.append(message)


def read(path):
    """Reads a repository file without C++ comments (empty if missing)."""
    file = repo / path
    if not file.is_file():
        return ''
    text = file.read_text(encoding='utf-8', errors='replace')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def function(text, start_text):
    """Returns the brace-matched block that starts at the first start_text (empty if missing)."""
    start = text.find(start_text)
    if start == -1:
        return ''
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


# ---------------------------------------------------------------- S1: compiled probe
PROBE = r'''
#include "gamemap/OfficialLevels.h"
#include <iostream>
int main()
{
    const char* names[] = {"2026-11-22_101500-SK-MyMap.mmap", "2026-11-22_101500-MP-Duel.mmap",
        "2026-11-22_101500-SK-Shipped.level", "MyMap.mmap", "a.mmap.level", "x.mmapx", ".mmap", "plain", ""};
    for(const char* name : names)
        std::cout << "[" << name << "]->[" << OfficialLevels::toSavedGameName(name) << "]" << std::endl;
    return 0;
}
'''
EXPECTED = ['[2026-11-22_101500-SK-MyMap.mmap]->[2026-11-22_101500-SK-MyMap.level]',
            '[2026-11-22_101500-MP-Duel.mmap]->[2026-11-22_101500-MP-Duel.level]',
            '[2026-11-22_101500-SK-Shipped.level]->[2026-11-22_101500-SK-Shipped.level]',
            '[MyMap.mmap]->[MyMap.level]',
            '[a.mmap.level]->[a.mmap.level]',
            '[x.mmapx]->[x.mmapx]',
            '[.mmap]->[.mmap]',
            '[plain]->[plain]',
            '[]->[]']

with tempfile.TemporaryDirectory(prefix='odp-savename-') as directory:
    work = Path(directory)
    source = work / 'probe.cpp'
    source.write_text(PROBE, encoding='utf-8')
    binary = work / 'probe.exe'
    command = ['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', '/I' + str(repo / 'source'),
               '/I' + str(DEPS / 'install' / 'include' / 'boost-1_92'), str(source),
               str(repo / 'source' / 'gamemap' / 'OfficialLevels.cpp'), '/Fe:' + str(binary),
               '/link', '/LIBPATH:' + str(DEPS / 'install' / 'lib')]
    build = subprocess.run(command, cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    if build.returncode != 0:
        output = 'compile failed: ' + '\n'.join(l for l in build.stdout.splitlines() if 'error' in l)[:1500]
    else:
        result = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                timeout=60)
        output = result.stdout + result.stderr
check(output.splitlines() == EXPECTED,
      'S1 toSavedGameName turns a trailing .mmap into .level and keeps every other name; got: ' + output[:1500])

# ---------------------------------------------------------------- S2: static wiring
server = read('source/network/ODServer.cpp')
ask = function(server, 'case ClientNotificationType::askSaveMap:')
saved_game = re.sub(r'\s+', ' ', ask[ask.find('switch(mServerMode)'):])
check('switch(mServerMode)' in ask
      and 'getSaveGamePath() + OfficialLevels::toSavedGameName(ss.str())' in saved_game,
      'S2 askSaveMap names a saved game with OfficialLevels::toSavedGameName after the SK-/MP- prefix')

# ---------------------------------------------------------------- S3: consumers unchanged
load = read('source/modes/MenuModeLoad.cpp')
check('SAVEGAME_EXTENSION = ".level"' in load
      and 'fillFilesList(ResourceManager::getSingleton().getSaveGamePath(), saves, SAVEGAME_EXTENSION)' in load,
      'S3 the Load menu lists the .level files of the saved game folder')
load_filter = read('source/modes/LoadGameFilter.h')
campaign = read('source/game/Campaign.cpp')
check('filename.find("MP-")' in load_filter and 'filename.find("SK-")' in load_filter,
      'S3 the load filter tells skirmish and multiplayer saves apart by "SK-" and "MP-"')
check('filename.find("SK-")' in campaign and 'filename.find("MP-")' in campaign,
      'S3 the campaign finds the level of a legacy save by "SK-" and "MP-"')

if failures:
    print('FAIL: %d requirement(s) not met (%.1f s):' % (len(failures), time.monotonic() - started))
    for failure in failures:
        print('  - ' + failure)
    sys.exit(1)
print('OK: saved game name checks passed (%.1f s)' % (time.monotonic() - started))
