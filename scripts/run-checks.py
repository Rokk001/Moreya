#!/usr/bin/env python3
"""Check runner of the integrator (fixed steps of the check runs in the integrator rules).

Usage (from anywhere):
    python run-checks.py --repo <worktree> --out <result file> [--base origin/main]
                         [--tip HEAD] [--only <script> ...] [--timeout 600] [--no-4551-retry]

Runs tools/check_*.py, source/tests/check_*.py, scripts/check_*.py and scripts/check-*.py of the
worktree, one after the other, each with its own time limit (default 10 minutes, a script that
hits it is red). scripts/check-protected-content.py is never run here (pre-push hook dry run
only). scripts/check-level-similarity.py runs only on the *.level files that the tip changes
against the base; if there are none it is skipped (not red, not missing). A script that fails
with WinError 4551 is run once more (it builds its test program anew, which is a new file).

Result file: one line per script ("<path> ok <s>s", "FAIL exit <n> <s>s" or "FAIL timeout"),
the output tail of a red script indented below it, last line "DONE total=<n> red=<m>".

The load test level Mossgate lies in the wing 1 content package (the public tree holds no campaign); a selected level
is found through scripts/campaign_packages.py of the worktree (level_file), and run-level-test.py gives the game the
content packages (MOREYA_CONTENT_DIR). Without the content packages a selected level is missing: its load check is red
(exit 125) and names the missing content packages; a load test never passes without the content.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hq_check_events as events

# Same locations as scripts/win32/windows-paths.ps1: OD_DEPS_ROOT and OD_VS_PATH override the defaults (OGRE 14 dependency folder, VS 18 build tools)
DEPS_ROOT = os.environ.get('OD_DEPS_ROOT') or os.path.join(os.path.expanduser('~'), 'build-deps')
VS_PATH = os.environ.get('OD_VS_PATH') or r'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools'
# OgreXMLConverter is built into the OGRE 14 dependency folder (install\bin) since OGRE_BUILD_TOOLS=ON
PATH_EXTRA = [os.path.join(DEPS_ROOT, 'install', 'bin')]
SKIP_NAMES = ['check-protected-content.py', 'check-level-similarity.py']
TAIL_LINES = 25
LOADED_LEVELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LOADED-LEVELS.md')
ALWAYS_LOADED = os.path.join('levels', 'campaign', 'wing1', 'Mossgate.level')
# Fixed time limit of the load test in seconds (56 levels need well over 1 hour)
LOAD_TEST_TIMEOUT = 10800
# Time limit in seconds for run-window-close-test.py: two game starts, each bounded by its own start and exit limits
WINDOW_CLOSE_TEST_TIMEOUT = 900
# Time limit in seconds for check-level-similarity.py (it grows with the number of level files)
SLOW_SCRIPT_TIMEOUT = 1800
VCVARS = os.path.join(VS_PATH, 'VC', 'Auxiliary', 'Build', 'vcvars64.bat')


# Legacy helper retained for external imports; protocol runs use owned Windows jobs instead.
def kill_tree(pid):
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)


# Capture complete output and actual exits, including timeout cleanup of owned descendants.
def run_script(repo, rel, extra_args, timeout, env):
    from owned_process import OwnedProcess
    start = time.monotonic()
    child = OwnedProcess([sys.executable, rel] + extra_args, cwd=repo,
                         env=events.child_environment(env), stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='replace')
    code, output = child.collect(timeout)
    return code, output, time.monotonic() - start


# SHA-256 of a level file with CRLF normalised to LF, so the hash does not depend on the checkout line endings.
def level_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read().replace(b'\r\n', b'\n')).hexdigest()


# Read LOADED-LEVELS.md: set of (level path, hash) pairs that passed the load test.
def read_loaded():
    loaded = set()
    if os.path.isfile(LOADED_LEVELS):
        with open(LOADED_LEVELS, encoding='utf-8') as f:
            for line in f:
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                if len(cells) >= 3 and re.fullmatch(r'[0-9a-f]{64}', cells[1]):
                    loaded.add((cells[0].replace(os.sep, '/'), cells[1]))
    return loaded


# Append passed levels (path, hash) of this run to LOADED-LEVELS.md.
def record_loaded(passed, run):
    with open(LOADED_LEVELS, 'a', encoding='utf-8', newline='\n') as f:
        for path, digest in passed:
            f.write('| %s | %s | %s |\n' % (path.replace(os.sep, '/'), digest, run))


# A helper module of the worktree's scripts folder, loaded by path (None when the worktree has no such file).
def worktree_module(repo, name):
    path = os.path.join(repo, 'scripts', name + '.py')
    if name not in sys.modules:
        if not os.path.isfile(path):
            return None
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


# The file of a selected level and an error text: the plain path below the worktree, else the file the worktree's
# package helpers find (a level of a wing or content package); without it (None) the text names the missing level
# and the missing content packages.
def selected_level_file(repo, level):
    plain = os.path.join(repo, level)
    if os.path.isfile(plain):
        return plain, ''
    error = 'Required level missing: ' + level
    if not all(worktree_module(repo, name) for name in ('campaign_packages', 'room_packages', 'content_packages')):
        return None, error
    found = sys.modules['campaign_packages'].level_file(repo, level)
    if found is not None:
        return str(found), ''
    missing = sys.modules['content_packages'].missing_packages(repo)
    return None, error + ('; content packages missing: ' + ', '.join(missing) if missing else '')


# Resolve changed level files strictly; invalid comparison references are prerequisite failures.
def changed_levels(repo, base, tip):
    p = subprocess.run(['git', '-C', repo, 'diff', '--name-only', base, tip], capture_output=True,
                       text=True, stdin=subprocess.DEVNULL, check=True, timeout=30)
    return [f for f in p.stdout.splitlines() if f.endswith('.level')]


# Load test: LOAD_PARALLEL game instances at once without port support (= one after the other). With a run-level-test.py that
# knows --port (checked in the worktree), up to LOAD_PARALLEL_WITH_PORTS instances run at once, each with its own server port
# (LOAD_PORT_BASE + batch index), its own --appData folder and private TEMP/TMP folders. StoneKeep, the most timing-sensitive
# level, runs last and alone.
LOAD_PARALLEL = 1
# The parallel value of the HaiveQueen build settings (BUILD_PARALLEL) wins over the default 3
LOAD_PARALLEL_WITH_PORTS = max(1, int(os.environ.get('BUILD_PARALLEL') or 3))
LOAD_PORT_BASE = 31411
# One game instance needs about this much RAM (GB); at least LOAD_FREE_RAM_GB must stay free while the instances run
LOAD_INSTANCE_RAM_GB = 2.2
# The minimum free RAM of the HaiveQueen build settings (BUILD_MIN_FREE_RAM_GB) wins over the default 2.0
LOAD_FREE_RAM_GB = float(os.environ.get('BUILD_MIN_FREE_RAM_GB') or 2.0)


# Read available memory before planning game instances.
def free_ram_gb():
    """Returns the free physical memory in GB (Windows GlobalMemoryStatusEx)."""
    # Match the Windows memory-status structure exactly.
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong),
                    ('avail', ctypes.c_ulonglong), ('totalPage', ctypes.c_ulonglong), ('availPage', ctypes.c_ulonglong),
                    ('totalVirtual', ctypes.c_ulonglong), ('availVirtual', ctypes.c_ulonglong),
                    ('availExtended', ctypes.c_ulonglong)]
    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.avail / (1024.0 ** 3)


# Inspect port support without launching the game.
def load_test_supports_port(repo, load_test):
    """True if the run-level-test.py of the worktree has a --port option (source text check, no game start)."""
    try:
        with open(os.path.join(repo, load_test), encoding='utf-8') as handle:
            return '"--port"' in handle.read()
    except OSError:
        return False


# Plan bounded load batches and preserve the existing port-selection policy.
def plan_load_calls(repo, load_test, executable, level_files, free_gb=None):
    """Returns (parallel batches, solo call) as lists of run-level-test.py arguments; parallel batches get an own --port.

    The number of parallel instances is limited by the free RAM: every instance needs LOAD_INSTANCE_RAM_GB and
    LOAD_FREE_RAM_GB must stay free (at least one instance always runs). free_gb overrides the measured value (dry run).
    """
    ports = load_test_supports_port(repo, load_test)
    # Modern runners select their own OS-assigned port, including the menu process.
    automatic_ports = False
    if ports:
        with open(os.path.join(repo, load_test), encoding='utf-8') as handle:
            automatic_ports = 'args.port = available_server_port()' in handle.read()
    count = LOAD_PARALLEL_WITH_PORTS if ports else LOAD_PARALLEL
    if free_gb is None:
        free_gb = free_ram_gb()
    count = max(1, min(count, int((free_gb - LOAD_FREE_RAM_GB) / LOAD_INSTANCE_RAM_GB)))
    solo = [n for n in level_files if os.path.basename(n) == 'StoneKeep.level']
    rest = [n for n in level_files if n not in solo]
    batches = [rest[i::count] for i in range(count)]
    batches = [b for b in batches if b]
    calls = []
    for index, batch in enumerate(batches):
        port = ['--port', str(LOAD_PORT_BASE + index)] if ports and not automatic_ports and len(batches) > 1 else []
        calls.append(['--exe', executable] + port + batch)
    solo_call = ['--exe', executable] + solo if solo else None
    return calls, solo_call


# Collect every selected load batch, including failures, before returning.
def run_load_parallel(repo, load_test, executable, level_files, env, dry_run=False, free_gb=None):
    import concurrent.futures
    import tempfile
    start = time.time()
    calls, solo_call = plan_load_calls(repo, load_test, executable, level_files, free_gb)
    if dry_run:
        for index, call in enumerate(calls):
            print('PLAN parallel %d: %s %s' % (index, load_test, ' '.join(call)))
        if solo_call:
            print('PLAN solo last: %s %s' % (load_test, ' '.join(solo_call)))
        return 0, '', 0.0

    # Isolate each load process temporary files while preserving all probe assertions.
    def one(index_call):
        index, call = index_call
        local = dict(env)
        tmp = tempfile.mkdtemp(prefix='od-load-%d-' % index)
        local['TEMP'] = tmp
        local['TMP'] = tmp
        return run_script(repo, load_test, call, LOAD_TEST_TIMEOUT, local)

    results = []
    if calls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(calls)) as pool:
            results = list(pool.map(one, list(enumerate(calls))))
    if solo_call:
        results.append(run_script(repo, load_test, solo_call, LOAD_TEST_TIMEOUT, env))
    code = 0
    for c, _, _ in results:
        if c != 0:
            code = c
    out = chr(10).join(o for _, o, _ in results)
    return code, out, time.time() - start




# Prepare the compiler environment without hiding missing prerequisites.
def check_environment():
    # Step 2: no Windows error dialogs for this process and all children (missing DLL = red check)
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    # Step 1: PATH
    # Compiler environment (the checks that build test programs need cl.exe) and prefix path
    cmd = subprocess.run('"%s" >nul && set' % VCVARS, shell=True, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, encoding='utf-8', errors='replace')
    if cmd.returncode != 0:
        raise RuntimeError('Compiler environment failed: ' + cmd.stdout + cmd.stderr)
    env = dict(os.environ)
    for line in cmd.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            env[key] = value
    env['OD_DEPS_ROOT'] = DEPS_ROOT
    env['CMAKE_PREFIX_PATH'] = os.path.join(DEPS_ROOT, 'install').replace(chr(92), '/')
    # vcvars writes the key as "Path", os.environ uses "PATH": merge both spellings into one entry so the extra folders are not lost
    path_value = os.pathsep.join([env.pop(k) for k in [k for k in env if k.upper() == 'PATH'][::-1]])
    env['PATH'] = os.pathsep.join(PATH_EXTRA + [path_value])

    return env


# Run selected static checks, or the complete integration checks followed by the load test (Mossgate plus the changed levels).
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=os.getcwd())
    ap.add_argument('--out', required=True)
    ap.add_argument('--base', default='origin/main')
    ap.add_argument('--tip', default='HEAD')
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('--only', nargs='*', default=[])
    ap.add_argument('--build-start', type=float, default=None, help='Epoch seconds of the build start; the load test fails if the exe is older')
    ap.add_argument('--load-test-only', action='store_true', help='Skip the static checks and run only the load test')
    ap.add_argument('--run', default='?', help='Run number recorded in LOADED-LEVELS.md for levels that pass')
    ap.add_argument('--no-4551-retry', action='store_true', help='Do not rerun checks after WinError 4551')
    ap.add_argument('--build-status', type=Path, help='Actual preflight/configure/build outcomes from the Build wrapper')
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    scripts = []
    for folder, pattern in [('tools', 'check_'), ('source/tests', 'check_'), ('scripts', 'check_'),
                            ('scripts', 'check-')]:
        d = os.path.join(repo, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.startswith(pattern) and name.endswith('.py') and name not in SKIP_NAMES:
                scripts.append(os.path.join(folder, name).replace('/', '\\'))
    scripts = sorted(set(scripts))
    wanted = [o.replace('/', '\\') for o in args.only]
    if wanted:
        scripts = sorted(set(wanted) - {r'scripts\check-level-similarity.py'})  # Similarity receives changed levels below; other missing scripts fail explicitly.

    lines = []
    red = 0
    total = 0

    # Persist the compact human-readable summary independently of full per-check logs.
    def record(text):
        lines.append(text)
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

    # check_windows_release_flags.py needs the generated project file of the release build
    project = os.path.join(repo, 'out', 'opendungeons-plus.vcxproj')
    if not os.path.exists(project):
        # a worktree build keeps its generated project in build\windows
        project = os.path.join(repo, 'build', 'windows', 'opendungeons-plus.vcxproj')
    jobs = [(s, [project] if s.endswith('check_windows_release_flags.py') and os.path.exists(project) else [])
            for s in scripts]
    selection_error = ''
    levels = []
    try:
        levels = changed_levels(repo, args.base, args.tip)
    except (OSError, subprocess.SubprocessError) as error:
        selection_error = 'Cannot resolve level comparison: ' + str(error)
    if not wanted or r'scripts\check-level-similarity.py' in wanted:
        if levels:
            jobs.append((r'scripts\check-level-similarity.py', levels))
        elif not selection_error:
            record(r'scripts\check-level-similarity.py skipped (no changed level files)')
    if args.load_test_only:
        jobs = []
    # Full integrator runs load Mossgate plus changed surviving levels, never the entire campaign.
    load_required = not wanted or args.load_test_only
    selected = {}
    if load_required:
        try:
            spec = importlib.util.spec_from_file_location('deploy_selection', Path(__file__).with_name('deploy-level-selection.py'))
            selector = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(selector)
            base = events.git(repo, 'rev-parse', '--verify', args.base + '^{commit}')
            tip = events.git(repo, 'rev-parse', '--verify', args.tip + '^{commit}')
            if args.build_status:
                # Publication probes use the same successful-deploy receipt as the later delivery step.
                common = Path(events.git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
                prepared = selector.prepare(Path(repo), tip, common / 'odp-deploy-success.json')
                base, selected = prepared['base'], prepared['levels']
            else:
                selected = selector.select(Path(repo), base, tip)
            record('Level selection base=%s tip=%s: %s' % (base, tip, json.dumps(selected, sort_keys=True)))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            selection_error = str(error)
        if selection_error:
            selected = {'levels/campaign/wing1/Mossgate.level': 'selection prerequisite failed'}
    stages = {}
    if args.build_status:
        try:
            stages = json.loads(args.build_status.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as error:
            stages = {name: {'exit':125,'kind':'prerequisite','output':'Build status unavailable: '+str(error)}
                      for name in ('build:preflight','build:configure','build:release')}
    checks = list(stages) + ['runner-prerequisites'] + [rel.replace('\\','/') for rel, _ in jobs]
    checks += ['load:' + level for level in selected]
    if load_required:
        checks += ['deploy-readiness', 'window-close']
    global LAST_SESSION
    session = events.Session(repo, args.out, checks, events.build_artifacts(Path(repo)))
    LAST_SESSION = session
    failed_build = False
    for name, status in stages.items():
        details = {'kind':status.get('kind','process-exit')}
        try:
            if status.get('log'):
                path=Path(status['log']); data=path.read_bytes()
                output=data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig',errors='replace')
                details.update(source_log=str(path.resolve()),source_log_sha256=events.digest(path))
            else:
                output=status.get('output','')
        except OSError as error:
            output='Required build log unavailable: '+str(error)
            details['process_exit']=status['exit']
            status={**status,'exit':status['exit'] or 125}
        session.result(name, int(status['exit']), output, **details)
        failed_build = failed_build or status['exit'] != 0
    try:
        env = check_environment()
        setup_error = selection_error or session.initial_error
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        env = dict(os.environ)
        setup_error = str(error)
    session.result('runner-prerequisites', 125 if setup_error else 0, setup_error or 'Compiler environment and level comparison verified')
    # Record every permitted attempt. Only exhausted retries or success produce final results.
    for rel, extra in jobs:
        total += 1
        script_timeout = SLOW_SCRIPT_TIMEOUT if rel.endswith('check-level-similarity.py') else args.timeout
        name = rel.replace('\\','/')
        for attempt in range(2):
            try:
                code, out, secs = run_script(repo, rel, extra, script_timeout, env)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                code, out, secs = 125, str(error), 0
            retry = code != 0 and 'WinError 4551' in out and not args.no_4551_retry and attempt == 0
            session.result(name, int(code), out, final=not retry)
            if not retry:
                break
        if code == 0:
            record('%s ok %ds' % (rel, secs))
        else:
            red += 1
            record('%s FAIL exit %s %ds' % (rel, code, secs))
            for line in out.splitlines()[-TAIL_LINES:]:
                record('    ' + line)
    # Red static checks never suppress independent level diagnostics. Missing build prerequisites are explicit failures.
    executable = os.path.join(repo, 'build', 'windows', 'moreya.exe')
    load_test = os.path.join(repo, 'scripts', 'run-level-test.py')
    prerequisite = selection_error or session.initial_error
    if load_required:
        if failed_build:
            prerequisite = 'This run did not produce a successful build; refusing stale artifacts'
        elif not os.path.isfile(executable):
            prerequisite = 'Build executable missing: ' + executable
        elif args.build_start is not None and os.path.getmtime(executable) < args.build_start:
            prerequisite = 'Build executable is older than this build start'
        elif not os.path.isfile(load_test):
            prerequisite = 'Required load-test script missing: ' + load_test
    for level in selected:
        total += 1
        level_file, missing_level = selected_level_file(repo, level) if not prerequisite else (None, '')
        if prerequisite or level_file is None:
            code,out,secs = 125, prerequisite or missing_level,0
        else:
            try:
                code,out,secs = run_load_parallel(repo,load_test,executable,[level],env)
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                code,out,secs = 125,str(error),0
        session.result('load:'+level,int(code),out)
        # Each changed level is tested in this run; no shared hash cache can omit a required result.
        record('load test %s (%s) %ds' % ('ok' if code==0 else 'FAIL exit '+str(code),level,secs))
        red += int(code!=0)
    # Publication-gating campaign assertions run against the built EXE before Push; Deploy repeats them on the delivered EXE.
    if load_required:
        total += 1
        if prerequisite:
            code,out,secs=125,prerequisite,0
        else:
            manifest=Path(args.out).with_suffix('.deployment-selection.json')
            manifest.write_text(json.dumps({'schema':1,'base':base,'tip':tip,'mode':'selected','levels':selected}),encoding='utf-8')
            try:
                code,out,secs=run_script(repo,'scripts/run-campaign-load-tests.py',
                    ['--repo',repo,'--deployment-selection',str(manifest),'--executable',executable,
                     '--output',str(Path(args.out).with_suffix('.deploy-readiness'))],LOAD_TEST_TIMEOUT,env)
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                code,out,secs=125,str(error),0
        session.result('deploy-readiness',int(code),out)
        record('deploy readiness %s %ds' % ('ok' if code==0 else 'FAIL exit '+str(code),secs))
        red += int(code!=0)
    # The X button of the built game, pressed while it loads and in the main menu, must end it with exit code 0.
    if load_required:
        total += 1
        if prerequisite:
            code,out,secs=125,prerequisite,0
        else:
            try:
                code,out,secs=run_script(repo,'scripts/run-window-close-test.py',['--exe',executable],
                    WINDOW_CLOSE_TEST_TIMEOUT,env)
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                code,out,secs=125,str(error),0
        session.result('window-close',int(code),out)
        record('window close %s %ds' % ('ok' if code==0 else 'FAIL exit '+str(code),secs))
        if code != 0:
            for line in out.splitlines()[-TAIL_LINES:]:
                record('    ' + line)
        red += int(code!=0)
    code=session.finish()
    red=sum(value!=0 for value in session.results.values())
    record('DONE total=%d red=%d' % (len(session.checks),red))
    return code


if __name__ == '__main__':
    sys.exit(main())
