"""Test deployment map selection against real temporary Git history, without a game build."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('load_selection', ROOT / 'scripts/run-campaign-load-tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


# Exercise immutable integration ranges and the selected runner's acceptance criteria.
class SelectionTests(unittest.TestCase):
    # Create isolated history with one campaign map and one unrelated map.
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='odp-selection-')
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.write('levels/campaign/Mossgate.level', 'first')
        self.write('levels/campaign/Second.level', 'second')
        self.write('levels/skirmish/Other.level', 'other')
        self.write('levels/campaign/Campaign.cfg', '[Level]\nFile=campaign/Mossgate.level\n[/Level]\n')
        self.commit()
        self.git('branch', 'baseline')
        self.saved = self.repo / 'range.json'

    # Run real Git operations without accessing project refs.
    def git(self, *args):
        return runner.git_output(self.repo, *args)

    # Write a fixture file with its parent directories.
    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    # Commit fixture changes as a normal new commit.
    def commit(self):
        self.git('add', 'levels')
        self.git('commit', '-qm', 'Fixture change')

    # Capture the current range and return portable selected paths.
    def selected(self):
        runner.capture_base(self.repo, 'baseline', self.saved)
        return [p.relative_to(self.repo).as_posix() for p in runner.integration_levels(self.repo, self.saved)]

    # No map changes must select exactly Mossgate.
    def test_no_changes(self):
        self.assertEqual(self.selected(), ['levels/campaign/Mossgate.level'])

    # Changed Mossgate must not run twice, and all changed map types are included.
    def test_changed_added_and_duplicate(self):
        self.write('levels/campaign/Mossgate.level', 'modified')
        self.write('levels/campaign/Second.level', 'modified')
        self.write('levels/skirmish/New map.level', 'new')
        self.commit()
        self.assertEqual(self.selected(), ['levels/campaign/Mossgate.level',
                         'levels/campaign/Second.level', 'levels/skirmish/New map.level'])

    # Renames select the destination, while deleted files cannot be loaded.
    def test_rename_and_delete(self):
        self.git('mv', 'levels/campaign/Second.level', 'levels/campaign/Renamed.level')
        self.git('rm', 'levels/skirmish/Other.level')
        self.commit()
        self.assertEqual(self.selected(), ['levels/campaign/Mossgate.level', 'levels/campaign/Renamed.level'])

    # Campaign metadata changes alone do not trigger a full campaign test.
    def test_config_only(self):
        self.write('levels/campaign/Campaign.cfg', '# changed metadata')
        self.commit()
        self.assertEqual(self.selected(), ['levels/campaign/Mossgate.level'])

    # A ref advancing after capture must not hide a changed map after push.
    def test_reference_advances(self):
        self.write('levels/campaign/Second.level', 'modified')
        self.commit()
        self.selected()
        self.git('switch', '-q', 'baseline')
        self.git('merge', '--ff-only', json.loads(self.saved.read_text())['tip'])
        self.assertEqual([p.name for p in runner.integration_levels(self.repo, self.saved)],
                         ['Mossgate.level', 'Second.level'])

    # Wrong or missing build metadata must fail, never silently select fewer maps.
    def test_invalid_metadata(self):
        with self.assertRaises(FileNotFoundError):
            runner.integration_levels(self.repo, self.saved)
        self.saved.write_text('{broken')
        with self.assertRaises(ValueError):
            runner.integration_levels(self.repo, self.saved)
        self.saved.write_text(json.dumps({'base': 'baseline', 'tip': 'HEAD'}))
        with self.assertRaises(RuntimeError):
            runner.integration_levels(self.repo, self.saved)

    # A later worktree commit invalidates metadata belonging to an earlier build.
    def test_stale_tip(self):
        self.selected()
        self.write('levels/campaign/Second.level', 'later')
        self.commit()
        with self.assertRaises(RuntimeError):
            runner.integration_levels(self.repo, self.saved)

    # Missing baseline refs must not produce a usable selection file.
    def test_missing_base(self):
        with self.assertRaises(subprocess.CalledProcessError):
            runner.capture_base(self.repo, 'missing', self.saved)
        self.assertFalse(self.saved.exists())

    # Deleted mandatory smoke maps must fail instead of skipping the smoke test.
    def test_missing_mossgate(self):
        self.git('rm', 'levels/campaign/Mossgate.level')
        self.commit()
        with self.assertRaises(RuntimeError):
            self.selected()

    # Selected-mode launches use the supplied deployed EXE and propagate all failures.
    def test_selected_runner_exit_codes(self):
        self.selected()
        executable = self.repo / 'deployed/game.exe'
        executable.parent.mkdir()
        executable.touch()
        success = b'GOALS registered=2\nPASS Mossgate.level : victory message shown, campaign map shows next\n'
        argv = ['runner', '--repo', str(self.repo), '--base-file', str(self.saved),
                '--executable', str(executable), '--output', str(self.repo / 'logs')]
        levels = runner.integration_levels(self.repo, self.saved)
        for code, output, timeout, expected in [(0, success, False, 0), (2, success, False, 1),
                                               (0, b'', False, 1), (0, success, True, 1)]:
            with self.subTest(code=code, timeout=timeout, output=output), \
                    patch.object(sys, 'argv', argv), \
                    patch.object(runner, 'integration_levels', return_value=levels), \
                    patch.object(runner, 'probe_environment', return_value={}), \
                    patch.object(runner, 'game_is_running', return_value=False), \
                    patch.object(runner.subprocess, 'run') as launch:
                if timeout:
                    launch.side_effect = subprocess.TimeoutExpired('game', 402)
                else:
                    launch.return_value = subprocess.CompletedProcess([], code, output, b'')
                self.assertEqual(runner.main(), expected)
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0][0], str(executable))

    # Full campaign execution requires an explicit user-selected CLI mode.
    def test_no_implicit_full_campaign(self):
        with patch.object(sys, 'argv', ['runner', '--output', str(self.repo / 'logs')]):
            with self.assertRaises(SystemExit) as error:
                runner.main()
        self.assertEqual(error.exception.code, 2)

    # Bind both orchestration steps to the same per-run immutable range.
    def test_orchestrator_wiring(self):
        build = (ROOT / 'scripts/win32/orchestrator-build.ps1').read_text()
        deploy = (ROOT / 'scripts/win32/orchestrator-deploy.ps1').read_text()
        self.assertIn('--capture-base $Base --output "$wt\\out\\load-base-$run.json"', build)
        self.assertLess(build.index('--capture-base'), build.index('configure started'))
        self.assertIn('--base $loadBase', build)
        self.assertIn('--base-file "$wt\\out\\load-base-$run.json" --executable $exe', deploy)
        self.assertNotIn('--all-campaign', deploy)
        self.assertLess(deploy.index('load test with the deployed exe failed'), deploy.index('Set-Content -Encoding ascii $Counter'))

    # Execute the real deployment wrapper with harmless deployment and probe substitutes.
    @unittest.skipUnless(shutil.which('powershell'), 'Windows deployment wrapper')
    def test_deploy_wrapper_failure_and_counter(self):
        scripts = self.repo / 'scripts/win32'
        scripts.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/win32/orchestrator-deploy.ps1', scripts / 'orchestrator-deploy.ps1')
        self.write('out/orch-run.txt', 'test')
        self.write('out/build-number-test.txt', '17')
        self.write('deploy-stub.ps1', 'exit 0\n')
        counter = self.repo / 'counter.txt'
        for result in (7, 0):
            counter.write_text('16')
            self.write('scripts/run-campaign-load-tests.py',
                       'import json, sys\nfrom pathlib import Path\n'
                       'Path(__file__).with_suffix(".args").write_text(json.dumps(sys.argv[1:]))\n'
                       'sys.exit(%d)\n' % result)
            completed = subprocess.run(['powershell', '-NoProfile', '-File',
                                       str(scripts / 'orchestrator-deploy.ps1'),
                                       '-Counter', str(counter), '-DeployScript', str(self.repo / 'deploy-stub.ps1')],
                                      capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 1 if result else 0, completed.stdout + completed.stderr)
            self.assertEqual(counter.read_text().strip(), '16' if result else '17')
            args = json.loads((self.repo / 'scripts/run-campaign-load-tests.args').read_text())
            self.assertEqual(Path(args[args.index('--executable') + 1]),
                             self.repo / 'build/windows/opendungeons-plus.exe')
            self.assertEqual(Path(args[args.index('--base-file') + 1]), self.repo / 'out/load-base-test.json')
            if result:
                self.assertNotIn('deployed build 17', completed.stdout)


if __name__ == '__main__':
    unittest.main()
