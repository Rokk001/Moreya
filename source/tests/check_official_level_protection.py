"""Check: the shipped levels are protected (package 6).

    python source/tests/check_official_level_protection.py   (cl must be on the path: run it under vcvars64)

The shipped levels are the .level files below levels/skirmish, levels/multiplayer and levels/campaign.
Requirements checked (each reported on its own, expected values are fixed):
  P1  the build computes the checksums of all shipped levels at every build and compiles them into the game: the CMake
      script covers the three folders, a custom target without output (it runs at every build) rewrites the generated
      source of the build directory, the game depends on it and lists the source; no checksum file is in the
      repository. The script is run with cmake: 56 entries with the content (32 without), each the SHA-256 of the
      level without carriage returns (compared with hashlib), an unchanged folder does not rewrite the output, a
      changed level does
  P2  a changed shipped level is rejected with a message when it is loaded, an unchanged one loads (compiled probe on
      OfficialLevels.cpp with a changed copy; static wiring in readGameMapFromFile and the single player menus)
  P3  the multiplayer host never starts a changed shipped level and shows a message (static wiring; probe: also a
      developer build rejects it in multiplayer)
  P4  the editor without the hidden option: the load dialog offers no shipped level, opening one is refused, a save
      never writes into the shipped folders (own copy in the user level folder with a notice); with the option:
      opening and saving in place (compiled probe for both states, static wiring)
  P5  own maps get the .mmap extension; the skirmish, multiplayer and editor load menus list both extensions; own
      .level maps stay usable (static, probe on the name rules)
  P6  developer option: off by default, compiled only under the option; with it a changed shipped level loads in
      single player but not in multiplayer, without it it is rejected (probe compiled with and without the define)
  P7  the developer option and the hidden option are not mentioned in tracked texts other than code
  P8  the checksums of the build match every shipped level of the repository, also through a folder junction as in a
      run-in-place build directory, so the level of the load test loads (probe with the generated table)
It compiles one probe twice with cl, runs cmake twice in script mode and starts no game.

Most shipped levels moved to the content packages (scripts/content_packages.py, scripts/campaign_packages.py): the
levels below levels/<folder> of the content packages and the levels of wing 1 (formerly levels/campaign/wing1). With
the content present the shipped levels are the public ones plus those (78 in all, keys as before); without the content
only the 37 public levels are checked and the content levels are named as not checked."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

started = time.monotonic()
failures = []

WITH_CONTENT = content_packages.has_content(repo)
# Number of shipped levels of the branch (32 skirmish, 9 multiplayer, 15 campaign), counted once
ALL_LEVEL_COUNT = 56
# Number of shipped levels of the public tree (19 skirmish, 9 multiplayer, 4 campaign), counted once
PUBLIC_LEVEL_COUNT = 32
EXPECTED_LEVEL_COUNT = ALL_LEVEL_COUNT if WITH_CONTENT else PUBLIC_LEVEL_COUNT
if not WITH_CONTENT:
    content_packages.unchecked('check_official_level_protection',
                               ['%d shipped levels of the content packages' % (ALL_LEVEL_COUNT - PUBLIC_LEVEL_COUNT)])
DEPS = Path(os.environ.get('BUILD_DEPS_ROOT', str(Path(os.environ.get('USERPROFILE', '.')) / 'build-deps')))
CMAKE = Path(os.environ.get('ODP_CMAKE', str(DEPS / 'tools' / 'cmake-4.4.1-windows-x86_64' / 'bin' / 'cmake.exe')))
OFFICIAL_FOLDERS = ('skirmish', 'multiplayer', 'campaign')


def check(condition, message):
    """Records a failed requirement."""
    if not condition:
        failures.append(message)


def strip_comments(text):
    """Removes C++ comments so that a requirement is not met by a comment."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def read(path, comments=False):
    """Reads a repository file (empty if missing), without comments unless asked."""
    file = repo / path
    if not file.is_file():
        return ''
    text = file.read_text(encoding='utf-8', errors='replace')
    return text if comments else strip_comments(text)


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


def before(text, first, second):
    """True when both texts occur and first comes first."""
    a, b = text.find(first), text.find(second)
    return a != -1 and b != -1 and a < b


def shipped_level_files():
    """The .level files of the three shipped folders as {path below levels/: file}: the public levels, the levels of
    the same folders in the content packages and the levels of wing 1 (keys below campaign/wing1/ as before)."""
    files = {}
    for folder in OFFICIAL_FOLDERS:
        for base in content_packages.data_folders(repo, 'levels/' + folder):
            for path in sorted(base.rglob('*.level')):
                files.setdefault(folder + '/' + path.relative_to(base).as_posix(), path)
    for entry in campaign_packages.entries(repo):
        if entry.get('Wing') == '1' and not entry['_public'] and entry['_path'].is_file():
            files.setdefault('campaign/wing1/' + entry['_path'].name, entry['_path'])
    return files


def shipped_levels():
    """The paths below levels/ of the shipped levels (see shipped_level_files)."""
    return sorted(shipped_level_files())


def level_hash(data):
    """The reference checksum: SHA-256 of the bytes without carriage returns (hashlib, not the code under test)."""
    return hashlib.sha256(data.replace(b'\r', b'')).hexdigest()


def run_generator(levels_dir, output, content=False):
    """Runs the CMake script of the build; returns (ok, text). With content the shipped levels of the content
    packages are added like the build does (-DCONTENT_DIR, the packages folder of MOREYA_CONTENT_DIR)."""
    script = repo / 'cmake' / 'GenerateOfficialLevelChecksums.cmake'
    if not script.is_file():
        return False, 'script missing'
    arguments = [str(CMAKE), '-DLEVELS_DIR=' + str(levels_dir).replace('\\', '/')]
    folder = campaign_packages.content_folder(repo) if content else None
    if folder is not None:
        arguments.append('-DCONTENT_DIR=' + str(folder).replace('\\', '/'))
    run = subprocess.run(arguments + ['-DOUTPUT=' + str(output).replace('\\', '/'), '-P', str(script)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    return run.returncode == 0, run.stdout + run.stderr


def parse_entries(text):
    """The (key, checksum) pairs of a generated source."""
    return re.findall(r'\{"([^"]+)", "([0-9a-f]{64})"\}', text)


# ---------------------------------------------------------------- P1 (static)
cmake_lists = read('CMakeLists.txt', comments=True)
script = read('cmake/GenerateOfficialLevelChecksums.cmake', comments=True)
for folder in OFFICIAL_FOLDERS:
    check('foreach(FOLDER skirmish multiplayer campaign)' in script and 'GLOB_RECURSE' in script
          and '"${LEVELS_DIR}/${FOLDER}/*.level"' in script,
          'P1 the checksum script collects every .level below levels/%s (at any depth)' % folder)
target = re.search(r'add_custom_target\(od_official_level_checksums(.*?)\)\n', cmake_lists, re.S)
check(target is not None and 'OUTPUT ' not in target.group(1) and '-P "${OD_LEVEL_CHECKSUMS_SCRIPT}"' in target.group(1)
      and 'BYPRODUCTS "${OD_LEVEL_CHECKSUMS_SOURCE}"' in target.group(1),
      'P1 a custom target without output runs the checksum script at every build')
check('add_dependencies(${PROJECT_BINARY_NAME} od_official_level_checksums)' in cmake_lists,
      'P1 the game target depends on the checksum target')
check('set(OD_LEVEL_CHECKSUMS_SOURCE "${CMAKE_BINARY_DIR}/generated/OfficialLevelChecksums.cpp")' in cmake_lists
      and 'set(OD_LEVEL_CHECKSUMS_SCRIPT "${CMAKE_SOURCE_DIR}/cmake/GenerateOfficialLevelChecksums.cmake")' in cmake_lists
      and '"-DLEVELS_DIR=${CMAKE_SOURCE_DIR}/levels"' in cmake_lists,
      'P1 the checksums are generated from the levels folder of the repository into the build directory')
check(before(cmake_lists, 'SET(OD_SOURCEFILES ${OD_SOURCEFILES} ${OD_LEVEL_CHECKSUMS_SOURCE})',
             'add_executable(${PROJECT_BINARY_NAME}'),
      'P1 the generated source is compiled into the game')
check('${SRC}/gamemap/OfficialLevels.cpp' in cmake_lists, 'P1 OfficialLevels.cpp is compiled into the game')
tracked = subprocess.run(['git', '-C', str(repo), 'ls-files'], capture_output=True, text=True).stdout.splitlines()
check(not any(p.endswith('OfficialLevelChecksums.cpp') or '/generated/' in p for p in tracked),
      'P1 no generated checksum file is tracked in the repository')
# Split so that this check does not hold the text it searches for
marker = 'Generated at build time by ' + 'cmake/GenerateOfficialLevelChecksums.cmake'
holders = subprocess.run(['git', '-C', str(repo), 'grep', '--untracked', '-l', marker], capture_output=True, text=True).stdout.split()
check(holders == ['cmake/GenerateOfficialLevelChecksums.cmake'] or not script,
      'P1 no tracked file holds generated checksums; found: %s' % holders)

# ---------------------------------------------------------------- P1 (cmake run)
work = Path(tempfile.mkdtemp(prefix='odp-official-'))
generated = work / 'generated' / 'OfficialLevelChecksums.cpp'
level_files = shipped_level_files()
expected_keys = sorted(level_files)
check(len(expected_keys) == EXPECTED_LEVEL_COUNT,
      'P1 the branch has %d shipped levels (found %d)' % (EXPECTED_LEVEL_COUNT, len(expected_keys)))
ok, output = run_generator(repo / 'levels', generated, WITH_CONTENT)
entries = parse_entries(generated.read_text(encoding='utf-8')) if ok and generated.is_file() else []
check(ok and len(entries) == EXPECTED_LEVEL_COUNT,
      'P1 the script writes %d entries (got %d) %s' % (EXPECTED_LEVEL_COUNT, len(entries), output[:300]))
check(ok and 'const std::size_t ENTRY_COUNT = %d;' % EXPECTED_LEVEL_COUNT in generated.read_text(encoding='utf-8'),
      'P1 ENTRY_COUNT of the generated source is %d' % EXPECTED_LEVEL_COUNT)
check(ok and sorted(k for k, _ in entries) == expected_keys,
      'P1 the keys of the generated source are the paths of the shipped levels below levels/')
wrong = [k for k, h in entries if h != level_hash(level_files.get(k, repo / 'levels' / k).read_bytes())]
check(ok and not wrong, 'P1 every checksum is the SHA-256 without carriage returns; wrong: %s' % wrong[:5])
if ok:
    stamp = generated.stat().st_mtime_ns
    time.sleep(0.05)
    run_generator(repo / 'levels', generated, WITH_CONTENT)
    check(generated.stat().st_mtime_ns == stamp, 'P1 an unchanged levels folder does not rewrite the generated source')
    copy = work / 'levels'
    for key in expected_keys:
        (copy / key).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(level_files[key], copy / key)
    changed_key = 'skirmish/' + Path(next(k for k in expected_keys if k.startswith('skirmish/'))).name
    (copy / changed_key).write_bytes((copy / changed_key).read_bytes() + b'# changed\n')
    copied = work / 'copy' / 'OfficialLevelChecksums.cpp'
    run_generator(copy, copied)
    first = copied.read_text(encoding='utf-8')
    changed = dict(parse_entries(first))
    check(changed.get(changed_key) == level_hash((copy / changed_key).read_bytes())
          and changed.get(changed_key) != dict(entries).get(changed_key),
          'P1 a changed level gets its new checksum at the next run')

# ---------------------------------------------------------------- P2..P6 and P8: compiled probe
fixture = work / 'fixture'
levels_root = fixture / 'levels'
for folder in ('skirmish', 'multiplayer', 'campaign/wing1'):
    (levels_root / folder).mkdir(parents=True)
(fixture / 'other').mkdir()
(fixture / 'user' / 'skirmish').mkdir(parents=True)
(fixture / 'user' / 'multiplayer').mkdir(parents=True)
original = b'OpenDungeons_Version:0.7.4\n[Info]\nName\tKeep\n[/Info]\n'
(levels_root / 'skirmish' / 'Keep.level').write_bytes(original)
(levels_root / 'skirmish' / 'KeepCrlf.level').write_bytes(original.replace(b'\n', b'\r\n'))
(levels_root / 'skirmish' / 'Changed.level').write_bytes(original.replace(b'Keep', b'Kept'))
(levels_root / 'skirmish' / 'Added.level').write_bytes(original)
(levels_root / 'campaign' / 'wing1' / 'Wing.level').write_bytes(original)
(levels_root / 'multiplayer' / 'Duel.level').write_bytes(original)
(fixture / 'other' / 'Own.level').write_bytes(original)
(fixture / 'user' / 'skirmish' / 'Taken.mmap').write_bytes(original)
(levels_root / 'skirmish' / 'Taken.level').write_bytes(original)
digest = level_hash(original)
sizes = (0, 3, 55, 56, 63, 64, 65, 119, 120, 1000)
samples = [bytes((i * 7 + 3) % 251 for i in range(n)) for n in sizes]

PROBE = r'''
#include "gamemap/OfficialLevels.h"
#include "gamemap/OfficialLevelChecksums.h"
#include <iostream>
#include <string>
using namespace OfficialLevels;
static int failed = 0;
static void expect(bool condition, const std::string& text)
{
    if(!condition) { ++failed; std::cout << "FAIL " << text << std::endl; }
}
static std::string norm(std::string path)
{
    for(std::size_t i = 0; i < path.size(); ++i) if(path[i] == '\\') path[i] = '/';
    return path;
}
static std::string sample(std::size_t n)
{
    std::string s;
    for(std::size_t i = 0; i < n; ++i) s.push_back(static_cast<char>((i * 7 + 3) % 251));
    return s;
}
int main(int argc, char** argv)
{
    const std::string fixture = norm(argv[1]);
    const std::string root = fixture + "/levels";
    const std::string mode = argv[2];
    const std::string digest = "DIGEST";
    const ChecksumEntry table[] = {
        {"skirmish/Keep.level", digest.c_str()}, {"skirmish/KeepCrlf.level", digest.c_str()},
        {"skirmish/Changed.level", digest.c_str()}, {"campaign/wing1/Wing.level", digest.c_str()},
        {"multiplayer/Duel.level", digest.c_str()}, {"skirmish/Taken.level", digest.c_str()}};
    const std::size_t count = sizeof(table) / sizeof(table[0]);
    if(mode == "rules")
    {
        expect(computeSha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "sha abc");
        expect(computeSha256("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "sha empty");
        const std::size_t sizes[] = {SIZES};
        const char* hashes[] = {HASHES};
        for(std::size_t i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i)
            expect(computeSha256(sample(sizes[i])) == hashes[i], "sha of " + std::to_string(sizes[i]) + " bytes");
        expect(computeLevelChecksum("a\r\nb\r\n") == computeSha256("a\nb\n"), "carriage returns are ignored");
        // P2: a changed copy is rejected, the unchanged level loads
        expect(verifyLevelFile(root + "/skirmish/Keep.level", root, table, count) == Verdict::Unchanged, "unchanged");
        expect(verifyLevelFile(root + "/skirmish/KeepCrlf.level", root, table, count) == Verdict::Unchanged, "crlf");
        expect(verifyLevelFile(root + "/skirmish/Changed.level", root, table, count) == Verdict::Modified, "changed");
        expect(verifyLevelFile(root + "/campaign/wing1/Wing.level", root, table, count) == Verdict::Unchanged, "wing");
        expect(verifyLevelFile(root + "/multiplayer/Duel.level", root, table, count) == Verdict::Unchanged, "duel");
        expect(verifyLevelFile(root + "/skirmish/Added.level", root, table, count) == Verdict::NotShipped, "added");
        expect(verifyLevelFile(fixture + "/other/Own.level", root, table, count) == Verdict::NotOfficial, "own");
        expect(verifyLevelFile(root + "/../levels/skirmish/Keep.level", root, table, count) == Verdict::Unchanged,
            "dotted path");
        std::string key;
        expect(getOfficialKey(root + "/campaign/wing1/Wing.level", root, key) && key == "campaign/wing1/Wing.level",
            "key " + key);
        expect(mayLoad(Verdict::Unchanged, false) && mayLoad(Verdict::Unchanged, true), "unchanged loads");
        expect(mayLoad(Verdict::NotOfficial, true) && mayLoad(Verdict::NotShipped, true), "own levels load");
        // P4: the editor and the save target
        expect(!mayEditorOpen(true, false) && mayEditorOpen(true, true) && mayEditorOpen(false, false), "editor open");
        const std::string userSk = fixture + "/user/skirmish";
        const std::string userMp = fixture + "/user/multiplayer";
        EditorSaveTarget t = resolveEditorSaveTarget(root + "/skirmish/Keep.level", false, root, false, userSk, userMp);
        expect(t.mRedirected && norm(t.mPath) == userSk + "/Keep.mmap", "quick save copy " + t.mPath);
        t = resolveEditorSaveTarget(root + "/skirmish/Taken.level", false, root, false, userSk, userMp);
        expect(t.mRedirected && norm(t.mPath) == userSk + "/Taken-2.mmap", "copy name taken " + t.mPath);
        t = resolveEditorSaveTarget(root + "/multiplayer/Duel.level", false, root, false, userSk, userMp);
        expect(t.mRedirected && norm(t.mPath) == userMp + "/Duel.mmap", "multiplayer copy " + t.mPath);
        t = resolveEditorSaveTarget(root + "/campaign/wing1/Wing.level", false, root, false, userSk, userMp);
        expect(t.mRedirected && norm(t.mPath) == userSk + "/Wing.mmap", "campaign copy " + t.mPath);
        t = resolveEditorSaveTarget(root + "/skirmish/New.level", true, root, false, userSk, userMp);
        expect(t.mRedirected && norm(t.mPath) == userSk + "/New.mmap", "save as into a shipped folder " + t.mPath);
        t = resolveEditorSaveTarget(root + "/skirmish/Keep.level", false, root, true, userSk, userMp);
        expect(!t.mRedirected && norm(t.mPath) == root + "/skirmish/Keep.level", "option on: in place " + t.mPath);
        t = resolveEditorSaveTarget(root + "/skirmish/New.level", true, root, true, userSk, userMp);
        expect(!t.mRedirected && norm(t.mPath) == root + "/skirmish/New.level", "option on: save as " + t.mPath);
        // P5: the extension of the player maps
        expect(toUserMapName("a.level") == "a.mmap" && toUserMapName("a") == "a.mmap"
            && toUserMapName("a.mmap") == "a.mmap" && toUserMapName("a.map") == "a.map.mmap"
            && toUserMapName("").empty(), "map names");
        t = resolveEditorSaveTarget(fixture + "/other/Own.level", true, root, false, userSk, userMp);
        expect(!t.mRedirected && norm(t.mPath) == fixture + "/other/Own.mmap", "save as of an own map " + t.mPath);
        t = resolveEditorSaveTarget(fixture + "/other/Own.level", false, root, false, userSk, userMp);
        expect(!t.mRedirected && norm(t.mPath) == fixture + "/other/Own.level", "own .level saved in place " + t.mPath);
        std::cout << "developer=" << isDeveloperModeBuild() << " single=" << mayLoad(Verdict::Modified, false)
                  << " multi=" << mayLoad(Verdict::Modified, true) << std::endl;
    }
    else
    {
        // P8: the generated table matches every shipped level, given as paths of the repository; an argument
        // "<levels folder>|<file>" names the levels folder of a level of a content package
        const std::string levels = argv[3];
        int unchanged = 0;
        for(int i = 4; i < argc; ++i)
        {
            std::string root = levels;
            std::string file = argv[i];
            const std::string::size_type bar = file.find('|');
            if(bar != std::string::npos)
            {
                root = file.substr(0, bar);
                file = file.substr(bar + 1);
            }
            Verdict verdict = verifyLevelFile(file, root, OfficialLevelChecksums::ENTRIES,
                OfficialLevelChecksums::ENTRY_COUNT);
            expect(verdict == Verdict::Unchanged, std::string("generated table: ") + argv[i]);
            unchanged += (verdict == Verdict::Unchanged);
        }
        std::cout << "count=" << OfficialLevelChecksums::ENTRY_COUNT << " unchanged=" << unchanged << std::endl;
    }
    std::cout << (failed == 0 ? "PROBE OK" : "PROBE FAILED") << std::endl;
    return failed == 0 ? 0 : 1;
}
'''
probe_code = (PROBE.replace('DIGEST', digest).replace('SIZES', ', '.join(str(n) for n in sizes))
              .replace('HASHES', ', '.join('"%s"' % hashlib.sha256(s).hexdigest() for s in samples)))


def build_probe(name, defines):
    """Compiles the probe with OfficialLevels.cpp and the generated table; returns (binary or None, text)."""
    directory = work / name
    directory.mkdir()
    source = directory / 'probe.cpp'
    source.write_text(probe_code, encoding='utf-8')
    binary = directory / 'probe.exe'
    production = repo / 'source' / 'gamemap' / 'OfficialLevels.cpp'
    if not production.is_file() or not generated.is_file():
        return None, 'OfficialLevels.cpp or the generated table is missing'
    command = (['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', '/I' + str(repo / 'source'),
                '/I' + str(DEPS / 'install' / 'include' / 'boost-1_92')] + ['/D' + d for d in defines]
               + [str(source), str(production), str(generated), '/Fe:' + str(binary),
                  '/link', '/LIBPATH:' + str(DEPS / 'install' / 'lib')])
    build = subprocess.run(command, cwd=directory, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    if build.returncode != 0:
        return None, 'compile failed: ' + '\n'.join(l for l in build.stdout.splitlines() if 'error' in l)[:1500]
    return binary, ''


def run(binary, *args):
    """Runs the probe; returns (ok, output)."""
    result = subprocess.run([str(binary)] + [str(a) for a in args], capture_output=True, text=True,
                            stdin=subprocess.DEVNULL, timeout=120)
    return result.returncode == 0, result.stdout + result.stderr


release, release_error = build_probe('release', [])
developer, developer_error = build_probe('developer', ['OD_DEVELOPER_MODE'])
release_ok, release_out = run(release, fixture, 'rules') if release else (False, release_error)
developer_ok, developer_out = run(developer, fixture, 'rules') if developer else (False, developer_error)
check(release_ok, 'P2/P4/P5 the rules probe passes (changed copy rejected, save targets, names): ' + release_out[-1500:])
check(developer_ok, 'P2/P4/P5 the rules probe passes in a developer build: ' + developer_out[-1500:])
check('developer=0 single=0 multi=0' in release_out,
      'P2 without the developer option a changed shipped level is rejected in single player and multiplayer: '
      + release_out[-200:])
check('developer=1 single=1 multi=0' in developer_out,
      'P6 with the developer option a changed shipped level loads in single player and never in multiplayer: '
      + developer_out[-200:])
check('multi=0' in developer_out and 'multi=0' in release_out,
      'P3 a changed shipped level is rejected in multiplayer in every build')

# P8: the generated table against the repository levels, directly and through a junction like a build directory.
# A level of a content package is given with the levels folder of its package ("<folder>|<file>"); a level of wing 1
# lies directly in its package and is given from a copy below campaign/wing1/.
def p8_arguments():
    """The probe arguments of the shipped levels: public levels by path, package levels with their levels folder."""
    arguments = []
    for key in expected_keys:
        path = level_files[key]
        if path == repo / 'levels' / key:
            arguments.append(str(path))
        elif path.as_posix().endswith('/' + key):
            arguments.append(path.as_posix()[:-len(key) - 1] + '|' + str(path))
        else:
            copy_root = work / 'wing-levels'
            (copy_root / key).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copy_root / key)
            arguments.append(str(copy_root) + '|' + str(copy_root / key))
    return arguments


repo_levels = p8_arguments()
direct_ok, direct_out = run(release, fixture, 'table', repo / 'levels', *repo_levels) if release else (False, '')
check(direct_ok and 'count=%d unchanged=%d' % (EXPECTED_LEVEL_COUNT, EXPECTED_LEVEL_COUNT) in direct_out,
      'P8 every shipped level matches the checksum of the build: ' + direct_out[-600:])
junction = work / 'build' / 'levels'
junction.parent.mkdir()
made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(repo / 'levels')], capture_output=True,
                      text=True, stdin=subprocess.DEVNULL).returncode == 0
linked_ok, linked_out = run(release, fixture, 'table', junction, *repo_levels) if release and made else (False, '')
check(made and linked_ok and 'unchanged=%d' % EXPECTED_LEVEL_COUNT in linked_out,
      'P8 the levels given by their repository path match through the levels junction of a build directory: '
      + linked_out[-600:])
if made:
    os.rmdir(junction)

# ---------------------------------------------------------------- P2..P5 static wiring
maphandler = read('source/gamemap/MapHandler.cpp')
maphandler_h = read('source/gamemap/MapHandler.h')
official_cpp = read('source/gamemap/OfficialLevels.cpp')
official_cpp_raw = read('source/gamemap/OfficialLevels.cpp', comments=True)
official_h = read('source/gamemap/OfficialLevels.h')
gamemap = read('source/gamemap/GameMap.cpp')
server = read('source/network/ODServer.cpp')
editor = read('source/modes/EditorMode.cpp')
editor_load = read('source/modes/MenuModeEditorLoad.cpp')
editor_new = read('source/modes/MenuModeEditorNew.cpp')
skirmish = read('source/modes/MenuModeSkirmish.cpp')
multiplayer = read('source/modes/MenuModeMultiplayerServer.cpp')
campaign = read('source/modes/MenuModeCampaign.cpp')

loader = function(maphandler, 'bool readGameMapFromFile(')
check('checkOfficialLevel(fileName, strictOfficialCheck, officialRejection)' in loader
      and before(loader, 'checkOfficialLevel(', 'Helper::readFile(') and 'setLoadError(officialRejection)' in loader,
      'P2 readGameMapFromFile compares a shipped level with the build checksum before it reads it, with a message')
checker = function(maphandler, 'bool checkOfficialLevel(')
check('OfficialLevels::verifyLevelFile(' in checker and 'OfficialLevelChecksums::ENTRIES' in checker
      and 'OfficialLevels::mayLoad(verdict, multiplayer)' in checker and 'was changed and cannot be loaded' in checker,
      'P2 checkOfficialLevel compares with the compiled table and gives the reason of a rejection')
check('MapHandler::readGameMapFromFile(levelFilepath, *this, strictOfficialCheck)' in gamemap,
      'P2 GameMap::loadLevel hands the multiplayer strictness to the loader')
for label, text, signature, multi, out in (
        ('skirmish', skirmish, 'bool MenuModeSkirmish::launchSelectedButtonPressed(', 'false', 'SKM_TEXT_LOADING'),
        ('campaign', campaign, 'void MenuModeCampaign::startLevel(', 'false', 'statusText->setText(rejection)'),
        ('multiplayer', multiplayer, 'bool MenuModeMultiplayerServer::serverButtonPressed(', 'true', 'MPM_TEXT_LOADING')):
    body = function(text, signature)
    call = 'MapHandler::checkOfficialLevel(level, %s, rejection)' % multi
    check(call in body and before(body, call, 'startServer(') and out in body and 'setText(rejection)' in body,
          '%s the %s menu refuses a changed shipped level with its message before the server starts'
          % ('P3' if label == 'multiplayer' else 'P2', label))
start = function(server, 'bool ODServer::startServer(')
check('gameMap->loadLevel(levelFilename, mode == ServerMode::ModeGameMultiPlayer)' in start,
      'P3 the server start rejects a changed shipped level always in multiplayer')
check('gameMap->loadLevel(levelFilename, false)' in function(server, 'int32_t ODServer::startHeadlessGame('),
      'P2 the raid simulation loads its level as a single player game')
check('MapHandler::checkEditorMayOpen(levelFilename, refusal)' in start
      and before(start, 'checkEditorMayOpen(', 'loadLevel(') and 'mode == ServerMode::ModeEditor' in start
      and 'mEditOfficialLevels = MapHandler::isEditOfficialLevelsEnabled();' in start,
      'P4 the server refuses to open a shipped level in the editor without the hidden option')
enabled = function(maphandler, 'bool isEditOfficialLevelsEnabled(')
check('getGameValue(EDIT_OFFICIAL_LEVELS_KEY, "0", false)' in enabled
      and 'EDIT_OFFICIAL_LEVELS_KEY = "EditOfficialLevels"' in maphandler,
      'P4 the hidden option is the key EditOfficialLevels of the user config file and is off when missing')
save = function(server, 'case ClientNotificationType::askSaveMap:')
check('MapHandler::resolveEditorSaveTarget(levelSave.string(), saveAs, mEditOfficialLevels)' in save
      and before(save, 'resolveEditorSaveTarget(', 'SafeSave::replaceFile(')
      and 'Shipped levels cannot be changed. Your own copy was saved as: ' in save
      and 'gameMap->setLevelFileName(levelSaveText)' in save,
      'P4 every editor save (quick save, Save As, options) goes through the save target rule, with a notice for a copy')
may_open = function(maphandler, 'bool checkEditorMayOpen(')
check('OfficialLevels::mayEditorOpen(isOfficialLevelPath(fileName), isEditOfficialLevelsEnabled())' in may_open
      and 'checkOfficialLevel(fileName, false, message)' in may_open,
      'P4 checkEditorMayOpen applies the hidden option and the checksum')
constructor = function(editor_load, 'MenuModeEditorLoad::MenuModeEditorLoad(')
guarded = function(constructor, 'if(MapHandler::isEditOfficialLevelsEnabled())')
check('"Official Skirmish Levels"' in guarded and '"Official Multiplayer Levels"' in guarded
      and constructor.count('"Official') == 2,
      'P4 the editor load dialog lists the shipped level types only with the hidden option')
files = function(editor_load, 'bool MenuModeEditorLoad::updateFilesList(')
check('selectedType->getID()' in files and 'getItemIndex(' not in files
      and '!MapHandler::isEditOfficialLevelsEnabled()' in files,
      'P4 the editor load dialog chooses the folder by the item id and never a shipped folder without the option')
launch = function(editor_load, 'bool MenuModeEditorLoad::launchSelectedButtonPressed(')
check('MapHandler::checkEditorMayOpen(level, refusal)' in launch and before(launch, 'checkEditorMayOpen(', 'startServer('),
      'P4 the editor load dialog refuses a shipped level with a message')
load = function(editor, 'bool EditorMode::loadLevelFromFile(')
check('MapHandler::checkEditorMayOpen(fileName, refusal)' in load and before(load, 'checkEditorMayOpen(', 'stopServer()')
      and 'displayText(' in load,
      'P4 the editor refuses a shipped level before it tears the open level down (recent files, file browser)')
browser = function(editor, 'bool EditorMode::loadMenuFilePathTextChanged(')
check('MapHandler::isOfficialLevelPath(xx.path().string())' in browser and 'isEditOfficialLevelsEnabled()' in browser,
      'P4 the file browser of the editor does not offer shipped levels without the hidden option')

# ---------------------------------------------------------------- P5 static
check('USER_MAP_EXTENSION = ".mmap"' in official_h and 'LEVEL_FILE_EXTENSION = ".level"' in official_h,
      'P5 OfficialLevels.h defines the two extensions')
check('static const std::string USER_MAP_EXTENSION = OfficialLevels::USER_MAP_EXTENSION;' in maphandler_h
      and 'static const std::string LEVEL_EXTENSION = OfficialLevels::LEVEL_FILE_EXTENSION;' in maphandler_h,
      'P5 MapHandler.h has the shared constant USER_MAP_EXTENSION next to LEVEL_EXTENSION')
fill = function(maphandler, 'bool fillLevelFilesList(')
check('Helper::fillFilesList(folder, listFiles, LEVEL_EXTENSION)' in fill
      and 'Helper::fillFilesList(folder, listFiles, USER_MAP_EXTENSION)' in fill
      and 'ContentPackages::getDataFolders(path)' in fill,
      'P5 fillLevelFilesList lists both extensions in the folder and the same folder of every content package')
for label, text in (('skirmish', skirmish), ('multiplayer', multiplayer), ('editor load', editor_load)):
    check('MapHandler::fillLevelFilesList(' in text and 'MapHandler::LEVEL_EXTENSION' not in text,
          'P5 the %s menu lists both extensions' % label)
for label, text, signature in (('EditorMode', editor, 'bool EditorMode::launchNewLevelPressed('),
                               ('MenuModeEditorNew', editor_new, 'bool MenuModeEditorNew::launchSelectedButtonPressed(')):
    body = function(text, signature)
    check('".mmap"' not in body and 'level.append(MapHandler::USER_MAP_EXTENSION)' in body
          and before(body, 'MapHandler::USER_MAP_EXTENSION', 'exists(level'),
          'P5 the New dialog of %s uses the shared constant before it tests whether the file exists' % label)
check('".level"' not in editor and 'L".level"' not in editor and editor.count('MapHandler::isLevelFileExtension(') == 5,
      'P5 the file browsers of the editor accept both extensions (5 places, no .level literal)')
for path in ('source/modes', 'source/network'):
    literal = [p.name for p in (repo / path).glob('*.cpp') if '".mmap"' in read(str(p.relative_to(repo)))]
    check(not literal, 'P5 no ".mmap" literal outside OfficialLevels.h in %s: %s' % (path, literal))

# ---------------------------------------------------------------- P6 static
check(re.search(r'option\(OD_DEVELOPER_MODE "[^"]*" OFF\)', cmake_lists) is not None,
      'P6 the CMake option OD_DEVELOPER_MODE exists and is off by default')
check(re.search(r'if\(OD_DEVELOPER_MODE\)\s*target_compile_definitions\(\$\{PROJECT_BINARY_NAME\} PRIVATE '
                r'OD_DEVELOPER_MODE\)\s*endif\(\)', cmake_lists) is not None
      and cmake_lists.count('OD_DEVELOPER_MODE') == 4,
      'P6 the define is set only under the option')
users = sorted(str(p.relative_to(repo)).replace('\\', '/') for p in (repo / 'source').rglob('*')
               if p.suffix in ('.cpp', '.h') and 'tests' not in p.parts
               and 'OD_DEVELOPER_MODE' in strip_comments(p.read_text(encoding='utf-8', errors='replace')))
check(users == ['source/gamemap/MapHandler.cpp', 'source/gamemap/OfficialLevels.cpp'],
      'P6 only OfficialLevels.cpp and MapHandler.cpp know the developer option; found %s' % users)
may_load = function(official_cpp, 'bool mayLoad(')
dev_block = re.search(r'#ifdef OD_DEVELOPER_MODE(.*?)#(else|endif)', may_load, re.S)
outside = re.sub(r'#ifdef OD_DEVELOPER_MODE.*?#(else|endif)', '', may_load, flags=re.S)
check(dev_block is not None and 'if(!multiplayer)' in dev_block.group(1) and 'return true;' in dev_block.group(1)
      and outside.count('return true;') == 1 and before(outside, 'if(verdict != Verdict::Modified)', 'return true;'),
      'P6 the only path that loads a changed shipped level is compiled under OD_DEVELOPER_MODE')

# ---------------------------------------------------------------- P7
CODE = ('.cpp', '.h', '.hpp', '.c', '.py', '.cmake', '.ps1', '.sh', '.bat')
mentions = []
for path in tracked:
    if path.endswith(CODE) or path.endswith('CMakeLists.txt') or not (repo / path).is_file():
        continue
    try:
        text = (repo / path).read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue
    if re.search(r'EditOfficialLevels|OD_DEVELOPER_MODE|developer[ -]mode|Developer-Modus', text, re.I):
        mentions.append(path)
check(not mentions, 'P7 tracked texts (docs, README, layouts, ...) do not mention the hidden options: %s' % mentions)

# ---------------------------------------------------------------- P8 hidden fixtures (static)
# The maps of the first game that only checks use: kept in the repository, offered by no list of the game.
# Fixed list, counted once: 8 skirmish, 9 multiplayer, 4 campaign = 21.
HIDDEN_FIXTURES = [
    'skirmish/DuelToDeath.level', 'skirmish/FallingKeeper.level', 'skirmish/ForgottenTreasures.level',
    'skirmish/StoneKeep.level', 'skirmish/TestLegacy.level', 'skirmish/TestLegacyNoScripts.level',
    'skirmish/TestSingleplayerSmall.level', 'skirmish/TestSingleplayerSmallEmpty.level',
    'multiplayer/Angel.level', 'multiplayer/GreedOrMight.level', 'multiplayer/RuinsOfTheConfluent.level',
    'multiplayer/ScreamInTheDark.level', 'multiplayer/TheBridge.level',
    'multiplayer/TestMultiplayerSmallAlliance.level', 'multiplayer/TestMultiplayerSmallFreeForAll.level',
    'multiplayer/aa.level', 'multiplayer/ab.level',
    'campaign/Bonus1.level', 'campaign/Campaign1.level', 'campaign/Campaign2.level', 'campaign/Campaign3.level',
]
check(len(HIDDEN_FIXTURES) == 21, 'P8 the list of hidden fixtures has 21 entries')
check(all(key in expected_keys for key in HIDDEN_FIXTURES),
      'P8 every hidden fixture is still a shipped level of the repository')
check(all(('"%s"' % key) in official_cpp_raw for key in HIDDEN_FIXTURES),
      'P8 OfficialLevels.cpp names all 21 hidden fixtures')
fill_hidden = function(maphandler, 'bool fillLevelFilesList(')
check('isHiddenFixtureLevelPath(' in fill_hidden,
      'P8 fillLevelFilesList leaves the hidden fixtures out of the skirmish, multiplayer and editor load lists')
check('isHiddenFixtureLevelPath(' in editor,
      'P8 the file browser of the editor leaves the hidden fixtures out')
for own in ('skirmish/TestRaid.level', 'skirmish/TestSpa.level', 'skirmish/TestTavern.level'):
    check(own not in HIDDEN_FIXTURES and ('"%s"' % own) not in official_cpp_raw,
          'P8 the own test level %s is not hidden' % own)

shutil.rmtree(work, ignore_errors=True)
if failures:
    print('FAIL: %d requirement(s) not met (%.1f s):' % (len(failures), time.monotonic() - started))
    for failure in failures:
        print('  - ' + failure)
    sys.exit(1)
print('OK: shipped level protection checks passed (%.1f s)' % (time.monotonic() - started))
