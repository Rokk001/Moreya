"""Run the existing ODP check runner with advisory, reproducible timing reports.

Usage: python run-checks-profiled.py --runner <run-checks.py> --repo <worktree>
       --out <checks.txt> [all other original runner arguments]
The original test exit status is preserved. Timing thresholds request investigation,
not removal of checks or a larger timeout. No extra game builds are started.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import uuid

SCHEMA = 1
SLOW_SECONDS = 30
PROFILE_SECONDS = 120
REGRESSION_RATIO = 1.25
REGRESSION_SECONDS = 5
BUILD_PROCESSES = {'cl.exe', 'msbuild.exe', 'cmake.exe', 'ninja.exe',
                   'moreya.exe'}


# Read process ancestry without launching monitoring processes or changing their state.
def process_snapshot():
    if os.name != 'nt':
        return None  # Unknown load is never silently treated as comparable.

    # Layout required by the Windows Toolhelp process snapshot API.
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD),
                    ('pid', wintypes.DWORD), ('heap', ctypes.c_size_t),
                    ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG),
                    ('flags', wintypes.DWORD), ('name', wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            return None
        entries = []
        while True:
            entries.append((entry.pid, entry.parent, entry.name))
            if not kernel.Process32NextW(handle, ctypes.byref(entry)):
                break
        return entries
    finally:
        kernel.CloseHandle(handle)


# Distinguish expected child probe compilation from competing builds and games.
def foreign_load(entries, owner):
    if entries is None:
        return ['load-monitor-unavailable']
    own = {owner}
    while True:
        descendants = {pid for pid, parent, _ in entries if parent in own}
        if descendants <= own:
            break
        own.update(descendants)
    return sorted({name.lower() for pid, _, name in entries
                   if pid not in own and name.lower() in BUILD_PROCESSES})


# Sample foreign load throughout checks, including processes that exit before the check ends.
class LoadMonitor:
    # Initialize an independent monitor for this runner invocation.
    def __init__(self):
        self.reasons = set()
        self.stop = threading.Event()
        self.thread = None

    # Treat monitoring errors as unknown comparability, not as a test failure.
    def sample(self):
        try:
            self.reasons.update(foreign_load(process_snapshot(), os.getpid()))
        except Exception:
            self.reasons.add('load-monitor-unavailable')

    # Use interruptible waits so instrumentation never delays runner shutdown.
    def watch(self):
        while not self.stop.wait(1):
            self.sample()

    # Start sampling before any test is launched.
    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()
        return self

    # Stop sampling and capture the final load state without stopping another process.
    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join()
        self.sample()


# Resolve refs once before the runner can observe a later fetch or push.
def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args],
                                   text=True, encoding='utf-8', timeout=30).strip()


# Compare only the same host, interpreter, runner and execution settings.
def execution_profile(runner, timeout, runner_mode):
    return {'host': platform.node(), 'platform': platform.platform(),
            'cpu': platform.processor(), 'cpus': os.cpu_count(),
            'python': sys.version, 'executable': sys.executable,
            'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
            'timeout': timeout, 'runner_mode': runner_mode,
            'settings': {key: os.environ.get(key, '') for key in
                         ('BUILD_PARALLEL', 'BUILD_JOBS', 'BUILD_MP_JOBS', 'BUILD_DEPS_ROOT', 'OD_DEPS_ROOT', 'OD_VS_PATH',
                          'ODP_ASSETS_SRC', 'BUILD_MIN_FREE_RAM_GB')}}


# Parse optional sub-phase measurements emitted by a test without changing its assertions.
def phases(output):
    result = []
    for line in output.splitlines():
        if not line.startswith('ODP_TEST_PHASE '):
            continue
        try:
            item = json.loads(line[len('ODP_TEST_PHASE '):])
            if (isinstance(item.get('name'), str) and isinstance(item.get('seconds'), (int, float))
                    and not isinstance(item['seconds'], bool)
                    and math.isfinite(item['seconds']) and item['seconds'] >= 0):
                result.append({'name': item['name'], 'seconds': item['seconds']})
        except (ValueError, AttributeError, TypeError):
            continue
    return result


# Include arguments in identity so different level sets and test modes are not compared.
def test_key(row):
    return json.dumps([row['test'], row['arguments']], separators=(',', ':'))


# Find the most recent clean, successful measurement of the exact base commit.
def baseline(history, base, profile):
    candidates = []
    for path in history.glob('*.json'):
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict) or not isinstance(saved.get('tests'), list):
                continue
            if not isinstance(saved.get('started'), str) or any(
                    not isinstance(row, dict) or not isinstance(row.get('test'), str)
                    or not isinstance(row.get('arguments'), list)
                    or not isinstance(row.get('seconds'), (int, float))
                    or isinstance(row.get('seconds'), bool) or not math.isfinite(row['seconds'])
                    or row['seconds'] < 0 or not isinstance(row.get('attempts'), list)
                    or not row['attempts'] or 'exit_code' not in row
                    for row in saved['tests']):
                continue
            if (saved.get('schema') == SCHEMA and saved.get('commit') == base
                    and saved.get('profile') == profile and saved.get('exit_code') == 0
                    and saved.get('comparable') is True):
                candidates.append(saved)
        except (OSError, ValueError):
            continue
    return max(candidates, key=lambda item: item['started'], default=None)


# Classify timing evidence without converting advisory thresholds into failing tests.
def analyse(report, previous):
    old = {test_key(row): row for row in previous['tests']} if previous else {}
    for row in report['tests']:
        duration = row['seconds']
        row['findings'] = []
        if duration > SLOW_SECONDS:
            row['findings'].append('slow-test')
        if duration > PROFILE_SECONDS:
            row['findings'].append('phase-profile-required')
        prior = old.get(test_key(row))
        usable = (report['comparable'] and prior and len(row['attempts']) == 1
                  and len(prior['attempts']) == 1 and row['exit_code'] == prior['exit_code'] == 0)
        row['comparison'] = 'comparable' if usable else 'unavailable'
        if usable:
            row['baseline_seconds'] = prior['seconds']
            row['delta_seconds'] = duration - prior['seconds']
            if duration > prior['seconds'] * REGRESSION_RATIO and row['delta_seconds'] >= REGRESSION_SECONDS:
                row['findings'].append('runtime-regression')
            if duration > SLOW_SECONDS and prior['seconds'] <= SLOW_SECONDS:
                row['findings'].append('new-slow-test')
        elif not prior and duration > SLOW_SECONDS:
            row['findings'].append('slow-without-baseline')
    report['review_required'] = any(row['findings'] for row in report['tests'])


# Render the slowest tests and every investigation item for agents and integration logs.
def summary(report):
    lines = ['ODP test runtime review: ' + ('REQUIRED' if report['review_required'] else 'no threshold findings'),
             'Timing limits are advisory; the original test exit code is %s.' % report['exit_code'],
             'Comparison: ' + ('eligible' if report['comparable'] else ', '.join(report['load_reasons'])),
             'Baseline: ' + (report.get('baseline_commit') or 'no comparable measurement available'),
             'Slowest tests:']
    ordered = sorted(report['tests'], key=lambda row: row['seconds'], reverse=True)
    for row in ordered[:10]:
        lines.append('  %.3fs %s (%d attempt(s))' % (row['seconds'], row['test'], len(row['attempts'])))
    for row in ordered:
        if row['findings']:
            lines.append('REVIEW %s: %s; %.3fs; comparison=%s' %
                         (row['test'], ', '.join(row['findings']), row['seconds'], row['comparison']))
            if 'baseline_seconds' in row:
                lines.append('  base %.3fs; delta %+.3fs' % (row['baseline_seconds'], row['delta_seconds']))
            for phase in row['phases']:
                lines.append('  phase %s: %.3fs' % (phase['name'], phase['seconds']))
    return '\n'.join(lines) + '\n'


# Instrument the existing runner rather than duplicating its test discovery and failure rules.
def execute(runner, arguments, report):
    spec = importlib.util.spec_from_file_location('odp_original_check_runner', runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.run_script
    lock = threading.Lock()
    rows = {}

    # Capture every attempt, including retries and parallel load tests, with a monotonic clock.
    def measured(repo, rel, extra_args, timeout, env):
        started = time.perf_counter()
        code, output, ignored_seconds = original(repo, rel, extra_args, timeout, env)
        elapsed = time.perf_counter() - started
        item = {'test': rel.replace('\\', '/'), 'arguments': list(extra_args)}
        key = test_key(item)
        with lock:
            row = rows.setdefault(key, {**item, 'seconds': 0.0, 'attempts': [], 'phases': []})
            row['seconds'] += elapsed
            row['exit_code'] = code
            row['attempts'].append({'seconds': elapsed, 'exit_code': code, 'timeout': timeout})
            row['phases'].extend(phases(output))
        return code, output, ignored_seconds

    module.run_script = measured
    previous_defer = os.environ.get('HQ_CHECK_DEFER_RELEASE')
    os.environ['HQ_CHECK_DEFER_RELEASE'] = '1'
    saved_argv = sys.argv
    sys.argv = [str(runner)] + arguments
    try:
        with LoadMonitor() as monitor:
            code = module.main()
        report['_hq_session'] = getattr(module, 'LAST_SESSION', None)
        report['load_reasons'] = sorted(monitor.reasons)
        report['comparable'] = not monitor.reasons
        return code
    finally:
        report['tests'] = list(rows.values())
        sys.argv = saved_argv
        if previous_defer is None:
            os.environ.pop('HQ_CHECK_DEFER_RELEASE', None)
        else:
            os.environ['HQ_CHECK_DEFER_RELEASE'] = previous_defer


# Save reports beside the check output and retain immutable local history shared by worktrees.
# Forward unknown runner flags exactly; --run must never abbreviate our --runner option.
def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--runner', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    original = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    original.add_argument('--repo', type=Path, default=Path.cwd())
    original.add_argument('--out', type=Path, required=True)
    original.add_argument('--base', default='origin/main')
    original.add_argument('--tip', default='HEAD')
    original.add_argument('--timeout', type=int, default=600)
    original.add_argument('--only', nargs='*', default=[])
    original.add_argument('--load-test-only', action='store_true')
    original.add_argument('--no-4551-retry', action='store_true')
    settings, _ = original.parse_known_args(remaining)
    comparison_error = False
    try:
        base = git(settings.repo, 'rev-parse', settings.base + '^{commit}')
        commit = git(settings.repo, 'rev-parse', settings.tip + '^{commit}')
    except subprocess.SubprocessError:
        # The required runner reports invalid refs and still executes independent checks.
        base = ''
        commit = git(settings.repo, 'rev-parse', 'HEAD')
        comparison_error = True
    history = Path(git(settings.repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')) / 'odp-test-timings'
    report = {'schema': SCHEMA, 'started': datetime.now(timezone.utc).isoformat(),
              'base': base, 'commit': commit, 'profile': execution_profile(
                  args.runner, settings.timeout, {'only': settings.only,
                  'load_test_only': settings.load_test_only,
                  'no_4551_retry': settings.no_4551_retry})}
    dirty_before = git(settings.repo, 'status', '--porcelain', '--untracked-files=no')
    previous = baseline(history, base, report['profile'])
    code = execute(args.runner, remaining, report)
    diagnostic_session = report.pop('_hq_session', None)
    if dirty_before or git(settings.repo, 'status', '--porcelain', '--untracked-files=no'):
        report['load_reasons'].append('tracked-worktree-changes')
    if comparison_error:
        report['load_reasons'].append('invalid-comparison-reference')
    if git(settings.repo, 'rev-parse', 'HEAD') != commit:
        report['load_reasons'].append('tip-changed-during-checks')
    report['comparable'] = not report['load_reasons']
    report['exit_code'] = code
    report['baseline_commit'] = previous['commit'] if previous else None
    analyse(report, previous)
    rendered = summary(report)
    print(rendered, end='', flush=True)
    try:
        settings.out.with_suffix('.timings.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        settings.out.with_suffix('.timings.txt').write_text(rendered, encoding='utf-8')
        history.mkdir(parents=True, exist_ok=True)
        (history / (uuid.uuid4().hex + '.json')).write_text(json.dumps(report) + '\n', encoding='utf-8')
    except OSError as error:
        print('TIMING REPORT ERROR: ' + str(error), file=sys.stderr)
    # Shared timing history has now been written and every check has returned.
    if (diagnostic_session is not None and not diagnostic_session.initial_error
            and not os.environ.get('HQ_CHECK_DEFER_RELEASE') and not diagnostic_session.verify()):
        sys.modules['hq_check_events'].report('shared_writes_finished')
    return code


if __name__ == '__main__':
    sys.exit(main())
