"""Focused deployment recovery regressions; no game or build is started."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('odp_deployment', ROOT / 'scripts/odp_deployment.py')
deployment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = deployment
spec.loader.exec_module(deployment)


class Recovery(unittest.TestCase):
    """Reject stale builds and exclude a competing plan for the whole operation."""

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
        """The lock encloses normal-exit waiting, guarded deploy, probes and counter."""
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
                """Assert the counter remains old until successful probes finish."""
                self.assertEqual(counter.read_text(), '41')
                events.append('probe')
                return 0

            from types import SimpleNamespace
            running = iter([True, False, False])
            runner = SimpleNamespace(game_is_running=lambda exe: events.append('process') or next(running), main=probes)

            def git(repo, *args):
                """Supply a consistent target and data snapshot for the guarded run."""
                return str(Path(directory) / '.git') if '--git-common-dir' in args else 'a' * 40

            with patch.object(deployment, 'executable_lock', lock), patch.object(deployment, 'campaign_runner', return_value=runner), \
                    patch.object(deployment.time, 'sleep', side_effect=lambda seconds: events.append('wait')), \
                    patch.object(deployment, 'git', side_effect=git), \
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
            self.assertEqual(events, ['lock', 'process', 'wait', 'process', 'deploy', 'probe', 'unlock',
                                      'lock', 'process', 'deploy', 'probe', 'unlock'])


if __name__ == '__main__':
    unittest.main()
