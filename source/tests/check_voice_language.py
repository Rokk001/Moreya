"""Voice lines of the chosen language (localization plan R9): runs source/tests/test_VoiceLanguage.cpp without
Boost.Test and checks the use of the lookup in the game.

The test file is compiled with sound/VoiceLanguage.cpp against a tiny stand-in for the Boost.Test macros it uses (like
check_localization.py); no game build and no sound library is needed. The test cases work on a test voice folder in a
temporary folder: German and English file for one family, one family only in English, a voice with the recordings of
today directly below the voice folder, and a language package that brings its own recordings.

Fixed expected values, counted once for this branch: EXPECTED_CASES test cases with 0 failures; EXPECTED_RECORDINGS
recordings below sounds/Relative of the game data (all English, none moved); EXPECTED_FIRE_SITES calls of
fireRelativeSound and EXPECTED_PLAY_SITES calls of playRelativeSound outside their definitions (L0 inventory R9).

Calls (from the repository root):
  python source/tests/check_voice_language.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]

EXPECTED_CASES = 5
EXPECTED_RECORDINGS = 64
EXPECTED_FIRE_SITES = 12
EXPECTED_PLAY_SITES = 4

boost_shim = r'''
#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

struct ShimCase {std::string name; std::function<void()> body;};
inline std::vector<ShimCase>& shimCases() {static std::vector<ShimCase> cases; return cases;}
inline int& shimFailures() {static int failures = 0; return failures;}
struct ShimRegister
{
    ShimRegister(const std::string& name, std::function<void()> body)
    { shimCases().push_back(ShimCase{name, body}); }
};
struct ShimAbort {};

#define BOOST_AUTO_TEST_CASE(name) \
    static void name(); \
    static ShimRegister shimRegister_##name(#name, name); \
    static void name()
#define SHIM_CHECK(cond, text, fatal) \
    do { if(!(cond)) { ++shimFailures(); std::cout << "FAIL " << __LINE__ << ": " << text << "\n"; \
         if(fatal) throw ShimAbort(); } } while(0)
#define BOOST_CHECK(cond) SHIM_CHECK((cond), #cond, false)
#define BOOST_REQUIRE(cond) SHIM_CHECK((cond), #cond, true)
#define BOOST_CHECK_EQUAL(a, b) SHIM_CHECK((a) == (b), #a " == " #b, false)
#define BOOST_REQUIRE_EQUAL(a, b) SHIM_CHECK((a) == (b), #a " == " #b, true)
'''

main = r'''
#include "BoostTestTargetConfig.h"
int main()
{
    for(const ShimCase& c : shimCases())
    {
        try { c.body(); }
        catch(const ShimAbort&) {}
    }
    std::cout << shimCases().size() << " cases, " << shimFailures() << " failures\n";
    return shimFailures() == 0 ? 0 : 1;
}
'''

errors = []


def find_vcvars():
    """Returns vcvars64.bat of the installed Visual Studio Build Tools (18 or 2022), or None."""
    bases = [os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
             os.environ.get('ProgramFiles', r'C:\Program Files')]
    for base in bases:
        for version in ('18', '2022'):
            for edition in ('BuildTools', 'Community', 'Professional', 'Enterprise'):
                path = Path(base) / 'Microsoft Visual Studio' / version / edition / 'VC/Auxiliary/Build/vcvars64.bat'
                if path.exists():
                    return path
    return None


def run_test_cases():
    """Compiles and runs the test cases; returns their exit code and output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'BoostTestTargetConfig.h').write_text(boost_shim)
        (tmp / 'main.cpp').write_text(main)
        sources = [repo / 'source/sound/VoiceLanguage.cpp', repo / 'source/tests/test_VoiceLanguage.cpp',
                   tmp / 'main.cpp']
        exe = tmp / 'voice_language_check.exe'
        compiler = shutil.which('g++') or shutil.which('clang++')
        if compiler:
            command = [compiler, '-std=c++11', '-o', str(exe), '-I' + str(tmp), '-I' + str(repo / 'source')] + [
                       str(s) for s in sources] + ['-lboost_filesystem', '-lboost_system']
            subprocess.run(command, check=True)
        else:
            vcvars = find_vcvars()
            assert shutil.which('cl') is not None or vcvars is not None, 'no C++ compiler found (cl or vcvars64.bat)'
            prefix = '' if shutil.which('cl') else 'call "%s" >nul 2>&1 && ' % vcvars
            flags = '/nologo /EHsc /MD /std:c++17 /Fe"%s" /Fo"%s/" /I"%s" /I"%s"' % (
                exe, tmp.as_posix(), tmp, repo / 'source')
            deps = Path(os.environ.get('OD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'
            boost_include = sorted((deps / 'include').glob('boost-*'))
            assert boost_include, 'no Boost headers in ' + str(deps / 'include')
            flags += ' /I"%s"' % boost_include[-1]
            line = (prefix + 'cl ' + flags + ' ' + ' '.join('"%s"' % s for s in sources)
                    + ' /link /LIBPATH:"%s"' % (deps / 'lib'))
            subprocess.run(line, shell=True, check=True, stdout=subprocess.DEVNULL)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        return result.returncode, result.stdout


def read(path):
    """The text of a repository file."""
    return (repo / path).read_text(encoding='utf-8', errors='replace')


code, output = run_test_cases()
print(output.strip())
if code != 0 or ('%d cases, 0 failures' % EXPECTED_CASES) not in output:
    errors.append('test cases: expected %d cases with 0 failures' % EXPECTED_CASES)

# R9.4: the existing recordings stay where they are (no file moved, created or removed)
recordings = [p for p in (repo / 'sounds/Relative').rglob('*') if p.is_file()]
if len(recordings) != EXPECTED_RECORDINGS:
    errors.append('sounds/Relative: %d files, expected %d' % (len(recordings), EXPECTED_RECORDINGS))
language_folders = [p for p in (repo / 'sounds/Relative').glob('*/*') if p.is_dir() and re.fullmatch(r'[a-z]{2}', p.name)]
if language_folders:
    errors.append('sounds/Relative: language folder %s exists; this branch adds no recordings' % language_folders[0])

# The voice lines of the game use the lookup with the chosen language, and the recordings of the language packages
manager = read('source/sound/SoundEffectsManager.cpp')
for needle in ('VoiceLanguage::getLookupKeys(keeperVoice, ConfigManager::DEFAULT_KEEPER_VOICE,',
               'Translation::getLanguage(), family);', 'VoiceLanguage::chooseKey(keys, hasKey);',
               'VoiceLanguage::collectPackageFiles(language.mDirectory, language.mCode, relativeFiles);',
               'VoiceLanguage::collectFiles(soundFolderPath + "Relative/" + keeper, keeper, relativeFiles)'):
    if needle not in manager:
        errors.append('source/sound/SoundEffectsManager.cpp: %s missing' % needle)
play = manager[manager.index('void SoundEffectsManager::playRelativeSound'):]
play = play[:play.index('\n}\n')]
if 'Translation::getLanguage()' not in play or 'mLanguage' in play:
    errors.append('playRelativeSound must read the chosen language at every call (R9.5)')

# The call sites of the voice lines are the same as in the inventory
fire = play_sites = 0
for path in (repo / 'source').rglob('*.cpp'):
    if 'tests' in path.parts:
        continue
    text = path.read_text(encoding='utf-8', errors='replace')
    fire += len(re.findall(r'\bfireRelativeSound\(', text.replace('void GameMap::fireRelativeSound(', '')))
    play_sites += len(re.findall(r'(?<!ServerNotificationType::)\bplayRelativeSound\(',
                                 text.replace('void SoundEffectsManager::playRelativeSound(', '')))
if fire != EXPECTED_FIRE_SITES:
    errors.append('fireRelativeSound: %d call sites, expected %d' % (fire, EXPECTED_FIRE_SITES))
if play_sites != EXPECTED_PLAY_SITES:
    errors.append('playRelativeSound: %d call sites, expected %d' % (play_sites, EXPECTED_PLAY_SITES))

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: %d test cases, %d recordings unchanged, %d fire and %d play sites' % (
    EXPECTED_CASES, EXPECTED_RECORDINGS, EXPECTED_FIRE_SITES, EXPECTED_PLAY_SITES))
