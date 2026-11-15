"""Exercise deployed-state selection without starting a game or a deployment."""
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('selection', ROOT / 'scripts/deploy-level-selection.py')
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


# Use real Git snapshots to detect incorrect moving-ref and missing-baseline handling.
class DeployedSelectionTests(unittest.TestCase):
    # Create three independent maps and a shared campaign definition.
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        for name in ('Mossgate', 'Second', 'Third'):
            self.write('levels/campaign/' + name + '.level', name)
        self.write('levels/campaign/Campaign.cfg', '[Level]\nFile=campaign/Mossgate.level\n[Level]\nFile=campaign/Second.level\n[Level]\nFile=campaign/Third.level\n')
        self.base = self.commit()
        self.receipt = self.repo / 'receipt.json'
        self.receipt.write_text(json.dumps({'schema': 1, 'status': 'success', 'data_commit': self.base,
                                         'evidence': 'verified deployment exit 0'}))

    # Keep Git operations bounded and isolated from project refs.
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, timeout=15).strip()

    # Write fixture text without unnecessary preparation.
    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    # Commit fixture maps and return the immutable outgoing SHA.
    def commit(self):
        self.git('add', 'levels')
        self.git('commit', '-qm', 'Fixture')
        return self.git('rev-parse', 'HEAD')

    # Build a selection from the last successful deployment receipt.
    def prepare(self, full=False):
        return selection.prepare(self.repo, self.git('rev-parse', 'HEAD'), self.receipt, full)

    # No changes still exercise the agreed smoke level.
    def test_no_level_changes(self):
        self.assertEqual(list(self.prepare()['levels']), ['levels/campaign/Mossgate.level'])

    # Multiple changes include each map, with Mossgate only once.
    def test_multiple_changes_and_duplicate(self):
        for name in ('Mossgate', 'Second', 'Third'):
            self.write('levels/campaign/' + name + '.level', name + ' changed')
        self.commit()
        self.assertEqual(list(self.prepare()['levels']), ['levels/campaign/Mossgate.level',
                         'levels/campaign/Second.level', 'levels/campaign/Third.level'])

    # Neither an absent nor a failed deployment is a valid comparison base.
    def test_missing_or_failed_baseline(self):
        self.receipt.unlink()
        with self.assertRaisesRegex(RuntimeError, 'successful deploy'):
            self.prepare()
        self.receipt.write_text(json.dumps({'schema': 1, 'status': 'failed', 'data_commit': self.base}))
        with self.assertRaisesRegex(RuntimeError, 'successful deploy'):
            self.prepare()

    # Explicit full mode works without fabricating a comparison baseline.
    def test_explicit_full(self):
        self.receipt.unlink()
        result = self.prepare(full=True)
        self.assertIsNone(result['base'])
        self.assertEqual(len(result['levels']), 3)
        self.assertTrue(all('explicit full' in reason for reason in result['levels'].values()))

    # A changed shared entry selects the affected map even when its level is unchanged.
    def test_shared_campaign_entry(self):
        path = 'levels/campaign/Campaign.cfg'
        self.write(path, (self.repo / path).read_text().replace('File=campaign/Third.level', 'File=campaign/Third.level\nTitle=Changed'))
        self.commit()
        result = self.prepare()
        self.assertEqual(list(result['levels']), ['levels/campaign/Mossgate.level', 'levels/campaign/Third.level'])
        self.assertIn('Campaign.cfg', result['levels']['levels/campaign/Third.level'])

    # Unknown shared files cannot silently escape validation or trigger all maps.
    def test_unknown_shared_file(self):
        self.write('levels/shared.cfg', 'new dependency')
        self.commit()
        with self.assertRaisesRegex(RuntimeError, 'shared'):
            self.prepare()

    # Preparing another attempt never advances the success receipt.
    def test_prepare_does_not_advance_receipt(self):
        before = self.receipt.read_bytes()
        self.write('levels/campaign/Second.level', 'changed')
        tip = self.commit()
        result = self.prepare()
        self.assertEqual((result['base'], result['tip']), (self.base, tip))
        self.assertEqual(before, self.receipt.read_bytes())

    # The deployed runner rejects a forged scope and a different deployed snapshot.
    def test_deployed_manifest_validation(self):
        runner_spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts/run-campaign-load-tests.py')
        probe = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(probe)
        manifest = self.repo / 'selection.json'
        saved = self.prepare()
        manifest.write_text(json.dumps(saved))
        self.assertEqual([p.name for p in probe.deployment_levels(self.repo, manifest)], ['Mossgate.level'])
        saved['levels'] = {}
        manifest.write_text(json.dumps(saved))
        with self.assertRaisesRegex(RuntimeError, 'selection changed'):
            probe.deployment_levels(self.repo, manifest)
        manifest.write_text(json.dumps(self.prepare()))
        self.write('levels/campaign/Second.level', 'later')
        self.commit()
        with self.assertRaisesRegex(RuntimeError, 'actual deployed data'):
            probe.deployment_levels(self.repo, manifest)

    # Real PowerShell wiring must propagate failures and update the receipt only on success.
    @unittest.skipUnless(shutil.which('powershell'), 'Windows wrapper')
    def test_wrapper_success_and_failures(self):
        scripts = self.repo / 'scripts'
        (scripts / 'win32').mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/deploy-level-selection.py', scripts / 'deploy-level-selection.py')
        wrapper = scripts / 'win32/orchestrator-deploy-selected.ps1'
        shutil.copyfile(ROOT / 'scripts/win32/orchestrator-deploy-selected.ps1', wrapper)
        self.git('fetch', '.', 'HEAD:refs/remotes/origin/integration/all')
        self.git('worktree', 'add', '--detach', str(self.repo / 'build/current-worktree'), self.base)
        self.write('build/windows/opendungeons-plus.exe', 'fixture executable')
        self.write('out/orch-run.txt', 'test')
        self.write('out/build-number-test.txt', '17')
        receipt = self.repo / '.git/odp-deploy-success.json'
        original = self.receipt.read_bytes()
        counter = self.repo / 'counter.txt'
        for deploy_exit, probe_exit in ((5, 0), (0, 7), (0, 0)):
            with self.subTest(deploy_exit=deploy_exit, probe_exit=probe_exit):
                receipt.write_bytes(original)
                counter.write_text('16')
                self.write('deploy.ps1', 'param($ExeDir, $SelectionFile)\nif (-not (Test-Path $SelectionFile)) {exit 8}\nexit ' + str(deploy_exit))
                self.write('scripts/run-campaign-load-tests.py', 'import sys\nsys.exit(' + str(probe_exit) + ')\n')
                result = subprocess.run(['powershell', '-NoProfile', '-File', str(wrapper),
                                         '-Worktree', str(self.repo), '-Counter', str(counter),
                                         '-DeployScript', str(self.repo / 'deploy.ps1')],
                                        capture_output=True, text=True, timeout=30)
                failed = bool(deploy_exit or probe_exit)
                self.assertEqual(result.returncode, 1 if failed else 0, result.stdout + result.stderr)
                self.assertEqual(counter.read_text().strip(), '16' if failed else '17')
                if failed:
                    self.assertEqual(receipt.read_bytes(), original)
                    self.assertNotIn('deployed build 17', result.stdout)
                else:
                    saved = json.loads(receipt.read_text())
                    self.assertEqual(saved['data_commit'], self.base)
                    self.assertEqual(saved['status'], 'success')
                    self.assertEqual(len(saved['exe_sha256']), 64)
        # An existing game-close helper must run before deployment and retain its failure status.
        receipt.write_bytes(original)
        counter.write_text('16')
        self.write('scripts/win32/wait-game-exit.ps1',
                   'function Wait-GameExit { param($TimeoutSeconds)\n'
                   'if ($TimeoutSeconds -ne 0) {throw "Wrong wait budget"}\n'
                   'throw "Fixture game remains open"\n}\n')
        self.write('deploy.ps1', 'throw "Deployment must not start before game closes"\n')
        result = subprocess.run(['powershell', '-NoProfile', '-File', str(wrapper),
                                 '-Worktree', str(self.repo), '-Counter', str(counter),
                                 '-DeployScript', str(self.repo / 'deploy.ps1'), '-GameWaitSeconds', '0'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Fixture game remains open', result.stderr)
        self.assertNotIn('Deployment must not start', result.stderr)
        self.assertEqual(counter.read_text(), '16')
        self.assertEqual(receipt.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
