"""Focused deployment recovery regressions; no game or build is started."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('odp_deployment', ROOT / 'scripts/odp_deployment.py')
deployment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = deployment
spec.loader.exec_module(deployment)


class Recovery(unittest.TestCase):
    """Reject stale builds and exclude a competing plan for the whole operation."""

    def test_digest_vectors(self):
        """SHA-256 matches fixed empty, short and multi-chunk vectors on Python 3.10."""
        vectors = [
            (b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
            (b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'),
            (b'a' * 1048577, '4a3f0c0c213adea174f9a3d4c13177315b588bdb2e9c1012d3d0bf0453ca0f6a'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / 'game.exe'
            for content, expected in vectors:
                with self.subTest(size=len(content)):
                    artifact.write_bytes(content)
                    self.assertEqual(deployment.digest(artifact), expected)
            artifact.unlink()
            with self.assertRaises(FileNotFoundError):
                deployment.digest(artifact)

    def test_bounded_wait_under_shared_lock(self):
        """Zero and expired deadlines prohibit deployment and leave the counter unchanged."""
        from contextlib import contextmanager
        from types import SimpleNamespace
        cases = [(0, 0, False, [], 1), (0, 100, True, [], 1),
                 (2, 2, False, [1, 1], 3), (2, 100, True, [1, 1], 3)]
        for bound, busy_queries, fails, expected_sleeps, expected_queries in cases:
            with self.subTest(bound=bound, busy_queries=busy_queries), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                (repo / 'out').mkdir()
                (repo / 'out/orch-run.txt').write_text('test')
                script = repo / 'deploy.ps1'
                script.write_text('ODP_DEPLOY_EXPECTED_COMMIT')
                counter = repo / 'counter'
                counter.write_text('41')
                clock = [0]
                queries = []
                sleeps = []
                events = []
                actual_lock = deployment.executable_lock

                def assert_locked():
                    """Verify the actual OS lock is owned during wait and deployment stages."""
                    self.assertTrue(deployment._locks.held)

                @contextmanager
                def lock(executable):
                    """Time spent acquiring the shared lock must not consume the game wait."""
                    with actual_lock(executable):
                        clock[0] += 100
                        events.append('lock')
                        try:
                            yield
                        finally:
                            events.append('unlock')

                def running(executable):
                    """Provide fixed game observations while asserting shared lock ownership."""
                    assert_locked()
                    queries.append(executable)
                    return len(queries) <= busy_queries

                def sleep(seconds):
                    """Advance the deadline deterministically without touching any process."""
                    assert_locked()
                    sleeps.append(seconds)
                    clock[0] += seconds

                def git(repo, *args):
                    """Record freshness queries to prove a timeout never starts deployment."""
                    if '--git-common-dir' in args:
                        return str(Path(directory) / '.git')
                    assert_locked()
                    events.append('git')
                    return 'a' * 40

                def deploy_child(*args, **kwargs):
                    """Check the expected-commit guard survives the merged wait flow."""
                    assert_locked()
                    self.assertEqual(counter.read_text(), '41')
                    self.assertEqual(kwargs['env']['ODP_DEPLOY_EXPECTED_COMMIT'], 'a' * 40)
                    events.append('deploy')

                runner = SimpleNamespace(game_is_running=running, main=lambda: events.append('probe') or 0)
                with patch.object(deployment, 'executable_lock', lock), \
                        patch.object(deployment, 'campaign_runner', return_value=runner), \
                        patch.object(deployment.time, 'monotonic', side_effect=lambda: clock[0]), \
                        patch.object(deployment.time, 'sleep', side_effect=sleep), \
                        patch.object(deployment, 'git', side_effect=git), \
                        patch.object(deployment, 'deployment_selection', return_value=Mock(
                            prepare=Mock(return_value={'base': 'b' * 40, 'tip': 'a' * 40, 'levels': {}}),
                            main=Mock(return_value=0))), \
                        patch.object(deployment, 'validate_build', return_value={
                            'commit': 'a' * 40, 'sha256': 'hash', 'number': '42'}) as validation, \
                        patch.object(deployment, 'digest', return_value='hash'), \
                        patch.object(deployment.subprocess, 'run', side_effect=deploy_child) as child:
                    if fails:
                        with self.assertRaisesRegex(RuntimeError, 'deployment was not started'):
                            deployment.deploy(repo, counter, script, bound)
                        child.assert_not_called()
                        validation.assert_not_called()
                        self.assertEqual(events, ['lock', 'unlock'])
                        self.assertEqual(counter.read_text(), '41')
                    else:
                        deployment.deploy(repo, counter, script, bound)
                        self.assertEqual(child.call_count, 1)
                        self.assertEqual(counter.read_text().strip(), '42')
                        self.assertLess(events.index('deploy'), events.index('probe'))
                    self.assertEqual(sleeps, expected_sleeps)
                    self.assertEqual(len(queries), expected_queries)
                self.assertFalse(deployment._locks.held)

    def test_wait_cli_forwarding(self):
        """The CLI forwards zero and custom bounds and rejects out-of-range deadlines."""
        for bound in ('0', '23'):
            with patch.object(sys, 'argv', ['deploy', 'deploy', '--repo', '.',
                                           '--game-wait-seconds', bound]), \
                    patch.object(deployment, 'deploy') as run:
                deployment.main()
                run.assert_called_once_with(Path('.'), None, None, int(bound))
        from contextlib import redirect_stderr
        from io import StringIO
        for bound in ('-1', '86401'):
            with patch.object(sys, 'argv', ['deploy', 'deploy', '--repo', '.',
                                           '--game-wait-seconds', bound]), \
                    patch.object(deployment, 'deploy') as run, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    deployment.main()
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def test_cross_plan_exclusion(self):
        """A separate process cannot enter until the deploy/load/counter owner exits."""
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'game.exe'
            entered = Path(directory) / 'entered'
            child = ("import importlib.util,sys; from pathlib import Path; "
                     "s=importlib.util.spec_from_file_location('lock',sys.argv[1]); "
                     "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                     "exec('with m.executable_lock(sys.argv[2]):\\n Path(sys.argv[3]).touch()')")
            with deployment.executable_lock(executable):
                with deployment.executable_lock(executable):
                    process = subprocess.Popen([sys.executable, '-I', '-c', child,
                                                str(ROOT / 'scripts/odp_deployment.py'), str(executable), str(entered)])
                    try:
                        with self.assertRaises(subprocess.TimeoutExpired):
                            process.wait(timeout=.5)
                        self.assertFalse(entered.exists())
                    except BaseException:
                        process.kill()
                        process.wait()
                        raise
            self.assertEqual(process.wait(timeout=10), 0)
            self.assertTrue(entered.exists())

    def test_runner_entry_points(self):
        """Both probe CLIs acquire the shared lock, including equals-style arguments."""
        from contextlib import contextmanager
        for filename, option in [('run-campaign-load-tests.py', '--executable'), ('run-level-test.py', '--exe')]:
            spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts' / filename)
            runner = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
            events = []

            @contextmanager
            def lock(executable):
                """Observe ownership around the unmodified probe acceptance path."""
                events.append(('lock', executable))
                yield
                events.append('unlock')

            with patch.object(sys, 'argv', ['probe', option + '=game.exe']), \
                    patch.object(deployment, 'executable_lock', lock), \
                    patch.object(runner, 'main', side_effect=lambda: events.append('probe') or 7):
                self.assertEqual(runner.locked_main(), 7)
            self.assertEqual(events, [('lock', 'game.exe'), 'probe', 'unlock'])

    def test_build_provenance(self):
        """Only a checked unchanged commit and matching exact artifact can be reused."""
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / 'out').mkdir()
            (repo / 'build/windows').mkdir(parents=True)
            exe = repo / 'build/windows/opendungeons-plus.exe'
            exe.write_bytes(b'validated')
            (repo / 'out/build-number-test.txt').write_text('42')
            with patch.object(deployment, 'git', side_effect=lambda repo, *args: '' if args[0] == 'status' else 'a' * 40):
                with self.assertRaisesRegex(RuntimeError, 'normal integration revalidation required'):
                    deployment.validate_build(repo, 'test', 'a' * 40)
                (repo / 'out/validated-test.json').write_text('{}')
                with self.assertRaisesRegex(RuntimeError, 'normal integration revalidation required'):
                    deployment.validate_build(repo, 'test', 'a' * 40)
                deployment.record_build(repo, 'test', '42', 'a' * 40)
                self.assertEqual(deployment.validate_build(repo, 'test', 'a' * 40)['number'], '42')
                with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                    deployment.validate_build(repo, 'test', 'b' * 40)
                exe.write_bytes(b'replaced')
                with self.assertRaisesRegex(RuntimeError, 'artifact changed'):
                    deployment.validate_build(repo, 'test', 'a' * 40)
                with self.assertRaisesRegex(RuntimeError, 'Source changed'):
                    deployment.record_build(repo, 'test', '42', 'b' * 40)

    def test_normal_deploy_order(self):
        """The lock encloses waiting, selection, guarded deploy, probes, receipt and counter."""
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / 'out').mkdir()
            (repo / 'out/orch-run.txt').write_text('test')
            script = repo / 'deploy.ps1'
            script.write_text('$env:ODP_DEPLOY_EXPECTED_COMMIT')
            counter = repo / 'counter'
            counter.write_text('41')
            events = []
            from contextlib import contextmanager

            @contextmanager
            def lock(executable):
                """Record ownership across every stage without launching a game."""
                events.append('lock')
                try:
                    yield
                finally:
                    events.append('unlock')

            def probes():
                """Keep saved map selection inside the lock before publishing the counter."""
                self.assertEqual(counter.read_text(), '41')
                self.assertEqual(sys.argv, ['campaign-load', '--executable',
                                           str(repo / 'build/windows/opendungeons-plus.exe'),
                                           '--repo', str(repo / 'build/current-worktree'), '--deployment-selection',
                                           str(repo / 'out/deploy-selection-test.json'),
                                           '--output', str(repo / 'out/deployed-load-test')])
                events.append('probe')
                return 0

            from types import SimpleNamespace
            running = iter([True, False, False])
            runner = SimpleNamespace(game_is_running=lambda exe: events.append('process') or next(running), main=probes)

            def git(repo, *args):
                """Supply a consistent target and data snapshot for the guarded run."""
                return str(Path(directory) / '.git') if '--git-common-dir' in args else 'a' * 40

            def prepare(*args):
                """Select maps inside the lock before deployment changes any artifact."""
                self.assertEqual(events[0], 'lock')
                self.assertEqual(counter.read_text(), '41')
                events.append('select')
                return {'base': 'b' * 40, 'tip': 'a' * 40, 'levels': {}}

            def publish():
                """Publish success after probes and before the counter while still locked."""
                self.assertEqual(events[-1], 'probe')
                self.assertEqual(counter.read_text(), '41')
                self.assertIn('--record-success', sys.argv)
                events.append('receipt')
                return 0

            with patch.object(deployment, 'executable_lock', lock), patch.object(deployment, 'campaign_runner', return_value=runner), \
                    patch.object(deployment.time, 'sleep', side_effect=lambda seconds: events.append('wait')), \
                    patch.object(deployment, 'git', side_effect=git), \
                    patch.object(deployment, 'deployment_selection', return_value=Mock(
                        prepare=Mock(side_effect=prepare), main=Mock(side_effect=publish))), \
                    patch.object(deployment, 'validate_build', return_value={'commit': 'a' * 40, 'sha256': 'hash', 'number': '42'}), \
                    patch.object(deployment, 'digest', return_value='hash'), \
                    patch.object(deployment.subprocess, 'run', side_effect=lambda *a, **kw: events.append('deploy')):
                deployment.deploy(repo, counter, script)
                self.assertEqual(counter.read_text().strip(), '42')
                counter.write_text('41')
                runner.main = lambda: probes() or 1
                with self.assertRaisesRegex(RuntimeError, 'load test failed'):
                    deployment.deploy(repo, counter, script)
                self.assertEqual(counter.read_text(), '41')
            self.assertEqual(events, ['lock', 'process', 'wait', 'process', 'select', 'deploy', 'probe', 'receipt', 'unlock',
                                      'lock', 'process', 'select', 'deploy', 'probe', 'unlock'])


if __name__ == '__main__':
    unittest.main()
