"""Helper relay transport: runs source/tests/test_HelperRelay.cpp without Boost.Test against the fake helper.

The fake helper program (source/tests/mocks/FakeNetHelper.cpp) and the test are compiled with cl, the test with
OD_NET_HELPER_RELAY, network/HelperRelayProcess.cpp, network/HelperRelayTransport.cpp, the TCP backend and
ODPacket, against a tiny stand-in for the Boost.Test macros and the log manager (like check_level_script.py).
The test then starts the fake helper as a child process through the real pipes and runs handshake, lobby
requests, the host listener (own client by TCP on localhost and a relayed peer), the client connection and the
detection of a helper exit. No platform SDK is involved.

The new relay sources, the test and the fake helper are compiled with warnings as errors at /W4, the existing TCP
backend and ODPacket at the /W3 of the MSVC game build (third party headers excluded).

Expected: 6 test cases, 0 failures.

Calls (from the repository root):
  python -I source/tests/check_helper_relay.py
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[2]

# Test cases of test_HelperRelay.cpp
EXPECTED_CASES = 6
# Each wait of the test is bounded at 2 seconds; the whole run stays far below this limit
RUN_TIMEOUT_S = 120
COMPILE_TIMEOUT_S = 600

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

# Stand-in for utils/LogManager.h: errors and warnings go to stderr, the rest is dropped
log_stub = r'''
#ifndef LOGMANAGER_H
#define LOGMANAGER_H
#include <iostream>
#include <string>
class LogManager
{
public:
    LogManager() {}
};
#define OD_LOG_ERR(_message) (std::cerr << (std::string("ERR ") + _message) << std::endl)
#define OD_LOG_WRN(_message) (std::cerr << (std::string("WRN ") + _message) << std::endl)
#define OD_LOG_INF(_message) ((void)(std::string("") + _message))
#define OD_LOG_DBG(_message) ((void)(std::string("") + _message))
#endif
'''

main = r'''
#include "BoostTestTargetConfig.h"
#include <chrono>
int main()
{
    for(const ShimCase& c : shimCases())
    {
        std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
        try { c.body(); }
        catch(const ShimAbort&) {}
        double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        std::cout << "case " << c.name << " " << seconds << "s\n";
    }
    std::cout << shimCases().size() << " cases, " << shimFailures() << " failures\n";
    return shimFailures() == 0 ? 0 : 1;
}
'''


def phase(name, seconds):
    """Prints one phase measurement for the profiled check runner."""
    print('ODP_TEST_PHASE ' + json.dumps({'name': name, 'seconds': round(seconds, 3)}))


def compiler_prefix():
    """Returns the shell prefix that puts cl in the PATH, '' if it is there, or None without a compiler."""
    if shutil.which('cl'):
        return ''
    vs_path = os.environ.get('OD_VS_PATH') or r'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools'
    vcvars = Path(vs_path) / 'VC' / 'Auxiliary' / 'Build' / 'vcvars64.bat'
    if vcvars.exists():
        return 'call "%s" >nul && ' % vcvars
    return None


def compile_objects(prefix, sources, objdir, includes, defines, warnings):
    """Compiles sources to objects with cl and the given warning flags, third party headers excluded."""
    objdir.mkdir(exist_ok=True)
    flags = ['/nologo', '/c', '/EHsc', '/std:c++17', '/MD'] + warnings + ['/external:anglebrackets',
             '/external:W0', '/Fo"%s/"' % objdir.as_posix()]
    flags += ['/I"%s"' % path for path in includes]
    flags += ['/D%s' % define for define in defines]
    line = prefix + 'cl ' + ' '.join(flags) + ' ' + ' '.join('"%s"' % source for source in sources)
    subprocess.run(line, shell=True, check=True, timeout=COMPILE_TIMEOUT_S)


def link_program(prefix, objdir, exe, libs, libpath):
    """Links all objects of objdir into exe."""
    line = prefix + 'link /nologo /OUT:"%s" "%s/*.obj"' % (exe, objdir.as_posix())
    if libs:
        line += ' /LIBPATH:"%s" %s' % (libpath, ' '.join(libs))
    subprocess.run(line, shell=True, check=True, timeout=COMPILE_TIMEOUT_S)


if sys.platform != 'win32':
    print('SKIP: this check compiles with cl on Windows')
    sys.exit(0)

prefix = compiler_prefix()
if prefix is None:
    print('SKIP: no C++ compiler found')
    sys.exit(0)

deps = Path(os.environ.get('BUILD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'

with tempfile.TemporaryDirectory(prefix='odp-helper-relay-') as tmp:
    tmp = Path(tmp)
    (tmp / 'BoostTestTargetConfig.h').write_text(boost_shim)
    (tmp / 'utils').mkdir()
    (tmp / 'utils' / 'LogManager.h').write_text(log_stub)
    (tmp / 'main.cpp').write_text(main)
    source = repo / 'source'

    start = time.monotonic()
    fake = tmp / 'fake_net_helper.exe'
    compile_objects(prefix, [source / 'tests/mocks/FakeNetHelper.cpp'], tmp / 'fake-obj', [source], [], ['/W4', '/WX'])
    link_program(prefix, tmp / 'fake-obj', fake, [], None)
    test = tmp / 'helper_relay_check.exe'
    # The stand-in directory comes first, so "utils/LogManager.h" resolves to the stub
    includes = [tmp, source, deps / 'include', deps / 'include' / 'OGRE']
    defines = ['OD_NET_HELPER_RELAY', 'OD_FAKE_NET_HELPER=\\"%s\\"' % fake.as_posix()]
    # New relay code and its test at /W4 as errors; the existing TCP backend and ODPacket as the MSVC game build does
    compile_objects(prefix, [source / 'tests/test_HelperRelay.cpp', source / 'network/HelperRelayProcess.cpp',
                             source / 'network/HelperRelayTransport.cpp', tmp / 'main.cpp'],
                    tmp / 'test-obj', includes, defines, ['/W4', '/WX'])
    compile_objects(prefix, [source / 'network/TcpNetTransport.cpp', source / 'network/ODPacket.cpp'],
                    tmp / 'test-obj', includes, defines, ['/W3'])
    link_program(prefix, tmp / 'test-obj', test, ['sfml-network.lib', 'sfml-system.lib'], deps / 'lib')
    phase('compile', time.monotonic() - start)

    environment = dict(os.environ)
    environment['PATH'] = str(deps / 'bin') + os.pathsep + environment.get('PATH', '')
    start = time.monotonic()
    # Propagate start errors: the check runner rebuilds the whole probe after WinError 4551.
    result = subprocess.run([str(test)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=RUN_TIMEOUT_S)
    phase('run', time.monotonic() - start)
    print(result.stdout, end='')
    expected = '%d cases, 0 failures' % EXPECTED_CASES
    if result.returncode != 0 or expected not in result.stdout:
        print('FAIL: expected "%s"' % expected)
        sys.exit(1)
    print('PASS: ' + expected)
