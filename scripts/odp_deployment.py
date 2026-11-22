"""Serialize executable users and bind deployment to a validated build receipt."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

_locks = threading.local()


@contextmanager
def executable_lock(executable):
    """Hold one OS file lock across deployment, probes and counter publication."""
    path = Path(executable).resolve().parent / '.odp-executable.lock'
    key = os.path.normcase(str(path))
    if not hasattr(_locks, 'held'):
        _locks.held = set()
    if key in _locks.held:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                time.sleep(.2)
        _locks.held.add(key)
        try:
            yield
        finally:
            _locks.held.remove(key)
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def git(repo, *args):
    """Run checked Git commands without accepting failed freshness queries."""
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def digest(path):
    """Identify the exact linked executable in bounded chunks on Python 3.10 too."""
    checksum = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            checksum.update(chunk)
    return checksum.hexdigest()


def record_build(repo, run, number, commit):
    """Publish provenance only after the normal build and all checks succeeded."""
    if git(repo, 'rev-parse', 'HEAD') != commit or git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Source changed during Build; normal integration revalidation required')
    receipt = {'commit': commit, 'run': run, 'number': number,
               'sha256': digest(repo / 'build/windows/moreya.exe')}
    (repo / 'out' / ('validated-' + run + '.json')).write_text(json.dumps(receipt), encoding='utf-8')


def validate_build(repo, run, target):
    """Require fresh validation of this commit and exact target, never infer old provenance."""
    try:
        receipt = json.loads((repo / 'out' / ('validated-' + run + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RuntimeError('Build validation receipt missing or invalid; normal integration revalidation required') from error
    if not isinstance(receipt, dict) or any(not isinstance(receipt.get(key), str)
                                          for key in ('commit', 'run', 'number', 'sha256')):
        raise RuntimeError('Build validation receipt missing or invalid; normal integration revalidation required')
    head = git(repo, 'rev-parse', 'HEAD')
    if receipt['run'] != run or receipt['commit'] != head or target != head:
        raise RuntimeError('Build/commit/target mismatch; normal integration revalidation required')
    if git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Tracked changes invalidate the validated build; normal integration revalidation required')
    if receipt['sha256'] != digest(repo / 'build/windows/moreya.exe'):
        raise RuntimeError('Build artifact changed since validation; normal integration revalidation required')
    number = (repo / 'out' / ('build-number-' + run + '.txt')).read_text().strip()
    if str(receipt['number']) != number:
        raise RuntimeError('Build number changed since validation; normal integration revalidation required')
    return receipt


def campaign_runner():
    """Load the existing probe implementation with its acceptance checks intact."""
    spec = importlib.util.spec_from_file_location('odp_campaign', Path(__file__).with_name('run-campaign-load-tests.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deployment_selection():
    """Reuse the selected entry point's immutable successful-deployment comparison."""
    spec = importlib.util.spec_from_file_location('odp_selection', Path(__file__).with_name('deploy-level-selection.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_integration_ref(integration_ref):
    """Split an integration ref of the form <remote>/<branch> (origin/main, moreya/main, origin/integration/all)."""
    remote, _, branch = str(integration_ref).partition('/')
    if not remote or not branch or remote.startswith('-') or branch.startswith('-'):
        raise ValueError('Integration ref must be <remote>/<branch>: ' + str(integration_ref))
    return remote, branch


def deploy(repo, counter, script, game_wait_seconds=1800, integration_ref='origin/main'):
    """Deploy a validated target and its successful-deployment selection under one lock.

    The deployed target is the tip of integration_ref (origin/integration/all for the old line, origin/main in the
    Moreya clone or moreya/main in a checkout with that remote); the deployed folder is build/windows of the main
    checkout of the shared Git directory.
    """
    if not 0 <= game_wait_seconds <= 86400:
        raise ValueError('Game wait seconds must be between 0 and 86400')
    remote, branch = split_integration_ref(integration_ref)
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    executable = common.parent / 'build/windows/moreya.exe'
    runner = campaign_runner()
    with executable_lock(executable):
        deadline = time.monotonic() + game_wait_seconds
        announced = False
        while runner.game_is_running(executable):
            if not announced:
                print('Waiting up to %s seconds for the deployed game to exit normally under the shared lock; '
                      'no process will be stopped' % game_wait_seconds, flush=True)
                announced = True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Game is still running after %s seconds; deployment was not started. '
                                   'Close the game and retry.' % game_wait_seconds)
            time.sleep(min(1, remaining))
        git(repo, 'fetch', remote, branch)
        run = (repo / 'out/orch-run.txt').read_text().strip()
        target = git(repo, 'rev-parse', remote + '/' + branch)
        receipt = validate_build(repo, run, target)
        selection = deployment_selection()
        success_file = common / 'odp-deploy-success.json'
        manifest = repo / 'out' / ('deploy-selection-' + run + '.json')
        scope = selection.prepare(common.parent, receipt['commit'], success_file)
        print('Deploy comparison: ' + str(scope['base']) + ' -> ' + scope['tip'], flush=True)
        for name, reason in scope['levels'].items():
            print('SELECT ' + name + ': ' + reason, flush=True)
        selection.write_json(manifest, scope)
        if 'ODP_DEPLOY_EXPECTED_COMMIT' not in script.read_text(encoding='utf-8-sig'):
            raise RuntimeError('Deploy script requires the expected-commit guard before retry')
        # Retain the deployment script's process, resource and locked-file guards.
        command = ("Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop; "
                   "& '" + str(script).replace("'", "''") + "' -ExeDir '" + str(repo / 'build/windows').replace("'", "''") +
                   "' -SelectionFile '" + str(manifest).replace("'", "''") + "'; "
                   "if ($?) { exit 0 }; if ($LASTEXITCODE) { exit $LASTEXITCODE }; exit 1")
        # The deploy script reads the integration ref so its data snapshot is checked against the same branch.
        environment = dict(os.environ, ODP_DEPLOY_EXPECTED_COMMIT=receipt['commit'],
                           ODP_DEPLOY_LOCK_OWNER=str(os.getpid()),
                           ODP_DEPLOY_INTEGRATION_REF=remote + '/' + branch)
        subprocess.run(['powershell', '-NoProfile', '-Command', command], check=True, env=environment)
        snapshot = git(common.parent / 'build/current-worktree', 'rev-parse', 'HEAD')
        if snapshot != receipt['commit'] or digest(executable) != receipt['sha256']:
            raise RuntimeError('Deployed snapshot/artifact mismatch; counter was not advanced')
        previous = sys.argv
        try:
            sys.argv = ['campaign-load', '--executable', str(executable),
                        '--repo', str(common.parent / 'build/current-worktree'),
                        '--deployment-selection', str(manifest),
                        '--output', str(repo / 'out' / ('deployed-load-' + run))]
            if runner.main():
                raise RuntimeError('Deployed load test failed; counter was not advanced')
        finally:
            sys.argv = previous
        # The selected wrapper's CLI publishes the same atomic success receipt after its probes.
        previous = sys.argv
        try:
            sys.argv = ['deployment-selection', '--repo', str(common.parent), '--tip', receipt['commit'],
                        '--receipt', str(success_file), '--output', str(manifest),
                        '--record-success', '--executable', str(executable)]
            if selection.main():
                raise RuntimeError('Could not record successful deployment; counter was not advanced')
        finally:
            sys.argv = previous
        counter.write_text(str(receipt['number']) + '\n', encoding='ascii')
        print('deployed build ' + str(receipt['number']), flush=True)


def main():
    """Expose build receipt recording and the normal guarded Deploy operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['record', 'deploy'])
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--run')
    parser.add_argument('--number')
    parser.add_argument('--commit')
    parser.add_argument('--counter', type=Path)
    parser.add_argument('--deploy-script', type=Path)
    parser.add_argument('--game-wait-seconds', type=int, default=1800, choices=range(86401),
                        metavar='0..86400')
    parser.add_argument('--integration-ref', default='origin/main',
                        help='<remote>/<branch> whose tip is deployed, e.g. origin/main in the Moreya clone')
    args = parser.parse_args()
    if args.action == 'record':
        record_build(args.repo, args.run, args.number, args.commit)
    else:
        deploy(args.repo, args.counter, args.deploy_script, args.game_wait_seconds, args.integration_ref)


if __name__ == '__main__':
    # Isolated Python excludes the script directory; import our shared lock explicitly.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.modules['odp_deployment'] = sys.modules[__name__]
    main()
