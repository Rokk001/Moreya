"""Check advisory runtime thresholds, comparability, retries and real runner forwarding."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('runtime_profile', ROOT / 'scripts/run-checks-profiled.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


# Construct explicit timing evidence independent of the implementation under test.
def row(seconds, name='source/tests/check_example.py', args=None, code=0, attempts=1):
    return {'test': name, 'arguments': args or [], 'seconds': seconds, 'exit_code': code,
            'attempts': [{'exit_code': code}] * attempts, 'phases': []}


# Check that runtime advice does not weaken functional pass/fail decisions.
class RuntimeTests(unittest.TestCase):
    # Evaluate explicit current/base timings with a chosen load condition.
    def findings(self, current, old=None, comparable=True):
        report = {'tests': [current], 'comparable': comparable}
        profile.analyse(report, {'tests': [old]} if old else None)
        return current['findings']

    # Thresholds are strict at 30/120 seconds, more than 25 percent and at least five seconds.
    def test_threshold_boundaries(self):
        self.assertEqual(self.findings(row(30), row(30)), [])
        self.assertNotIn('phase-profile-required', self.findings(row(120), row(120)))
        self.assertIn('phase-profile-required', self.findings(row(120.01), row(120.01)))
        self.assertNotIn('runtime-regression', self.findings(row(25), row(20)))
        self.assertIn('runtime-regression', self.findings(row(25.01), row(20)))
        self.assertIn('runtime-regression', self.findings(row(15), row(10)))
        self.assertNotIn('runtime-regression', self.findings(row(14.99), row(10)))

    # Detect newly slow checks without pretending missing baselines prove regressions.
    def test_new_and_missing_baselines(self):
        self.assertIn('new-slow-test', self.findings(row(31), row(29)))
        findings = self.findings(row(40))
        self.assertIn('slow-without-baseline', findings)
        self.assertNotIn('runtime-regression', findings)

    # Different arguments, failed checks, retries and competing builds are not comparable.
    def test_incomparable_measurements(self):
        cases = [(row(50), row(10), False), (row(50, args=['--other']), row(10), True),
                 (row(50, code=1), row(10), True), (row(50), row(10, code=1), True),
                 (row(50, code='timeout'), row(10), True),
                 (row(50, attempts=2), row(10), True), (row(50), row(10, attempts=2), True)]
        for current, old, comparable in cases:
            with self.subTest(current=current, old=old):
                self.assertNotIn('runtime-regression', self.findings(current, old, comparable))

    # Ignore our own compiler children while recording foreign builds and unknown sampling.
    def test_process_ancestry(self):
        entries = [(10, 1, 'python.exe'), (11, 10, 'python.exe'), (12, 11, 'cl.exe'),
                   (50, 1, 'MSBuild.exe'), (51, 50, 'cl.exe')]
        self.assertEqual(profile.foreign_load(entries, 10), ['cl.exe', 'msbuild.exe'])
        self.assertEqual(profile.foreign_load(entries[:3], 10), [])
        self.assertEqual(profile.foreign_load(None, 10), ['load-monitor-unavailable'])

    # Preserve valid phase timings and reject malformed, negative and non-finite measurements.
    def test_phase_records(self):
        text = '\n'.join(['ODP_TEST_PHASE {"name":"setup","seconds":2.5}',
                          'ODP_TEST_PHASE {"name":"bad","seconds":-1}',
                          'ODP_TEST_PHASE {"name":"bad","seconds":NaN}',
                          'ODP_TEST_PHASE {broken', 'ODP_TEST_PHASE []'])
        self.assertEqual(profile.phases(text), [{'name': 'setup', 'seconds': 2.5}])

    # Reuse only exact-commit, same-profile, clean successful history, ignoring corrupt JSON.
    def test_history_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            history = Path(temporary)
            good = {'schema': 1, 'commit': 'base', 'profile': {'host': 'one'},
                    'exit_code': 0, 'comparable': True, 'started': '2026-01-01', 'tests': []}
            (history / 'good.json').write_text(json.dumps(good))
            for index, change in enumerate([{'commit': 'other'}, {'profile': {'host': 'two'}},
                                             {'exit_code': 1}, {'comparable': False}, {'schema': 2}]):
                (history / ('bad%d.json' % index)).write_text(json.dumps({**good, **change, 'started': '2027'}))
            (history / 'corrupt.json').write_text('{broken')
            (history / 'array.json').write_text('[]')
            (history / 'missing-tests.json').write_text(json.dumps({**good, 'tests': [None]}))
            self.assertEqual(profile.baseline(history, 'base', {'host': 'one'}), good)
            self.assertIsNone(profile.baseline(history, 'missing', {'host': 'one'}))

    # Exercise actual imported runner calls and deterministic timing for both attempts.
    def test_runner_forwarding_and_retries(self):
        source = '''import sys
+def run_script(repo, rel, extra_args, timeout, env):
+    return (1 if extra_args == ['fail'] else 0), 'ODP_TEST_PHASE {"name":"setup","seconds":2}', 99
+def main():
+    assert sys.argv[1:] == ['--original', 'value']
+    run_script('.', 'check.py', [], 600, {})
+    run_script('.', 'check.py', [], 600, {})
+    return 7
+'''.replace('\n+', '\n')
        with tempfile.TemporaryDirectory() as temporary:
            runner = Path(temporary) / 'runner.py'
            runner.write_text(source)
            report = {}
            argv = sys.argv
            with patch.object(profile, 'process_snapshot', return_value=[]), \
                    patch.object(profile.time, 'perf_counter', side_effect=[10, 12, 20, 23]):
                self.assertEqual(profile.execute(runner, ['--original', 'value'], report), 7)
            self.assertIs(sys.argv, argv)
            self.assertTrue(report['comparable'])
            self.assertEqual(len(report['tests']), 1)
            self.assertEqual(report['tests'][0]['seconds'], 5)
            self.assertEqual(len(report['tests'][0]['attempts']), 2)

    # Run the command-line wrapper on an isolated Git fixture and retain a red runner's exit code.
    def test_cli_reports_and_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            # Build isolated history without touching the project checkout or refs.
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (repo / 'tracked.txt').write_text('fixture')
            git('add', 'tracked.txt')
            git('commit', '-qm', 'Fixture')
            runner = repo / 'runner.py'
            runner.write_text('def run_script(*args): return 3, "failed", 0\ndef main():\n    run_script(".", "check.py", [], 600, {})\n    return 3\n')
            output = repo / 'checks.txt'
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/run-checks-profiled.py'),
                                     '--runner', str(runner), '--repo', str(repo), '--base', 'HEAD',
                                     '--out', str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 3, result.stderr)
            saved = json.loads(output.with_suffix('.timings.json').read_text())
            self.assertEqual(saved['exit_code'], 3)
            self.assertEqual(saved['tests'][0]['exit_code'], 3)
            self.assertTrue(output.with_suffix('.timings.txt').exists())
            self.assertEqual(len(list((repo / '.git/odp-test-timings').glob('*.json'))), 1)

    # Print every investigation item, even when it is outside the ten slowest tests.
    def test_summary_keeps_all_findings(self):
        report = {'tests': [row(40 + index, name='check_%d.py' % index) for index in range(12)],
                  'comparable': True, 'exit_code': 0, 'load_reasons': [], 'baseline_commit': None}
        profile.analyse(report, None)
        text = profile.summary(report)
        self.assertEqual(text.count('REVIEW check_'), 12)
        self.assertIn('original test exit code is 0', text)
        self.assertIn('no comparable measurement', text)

    # Sampling failures cannot create a clean baseline or interrupt the tests.
    def test_monitor_failure(self):
        with patch.object(profile, 'process_snapshot', side_effect=OSError('unavailable')):
            with profile.LoadMonitor() as monitor:
                pass
        self.assertEqual(monitor.reasons, {'load-monitor-unavailable'})

    # Preserve the ODP build's native check status and require timing instrumentation on its normal path.
    def test_build_wiring(self):
        source = (ROOT / 'scripts/win32/orchestrator-build.ps1').read_text()
        self.assertIn('run-checks-profiled.py" --runner $Checks', source)
        self.assertIn('$code = $LASTEXITCODE', source)
        self.assertTrue(source.rstrip().endswith('exit $code'))


if __name__ == '__main__':
    unittest.main()
