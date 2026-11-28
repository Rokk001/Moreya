"""Integrator-only campaign load/goal-registration probes using an already built game.

Run with --executable <game> --output <worktree output directory> and either
--base-file <captured integration range> or --all-campaign while the game
is closed. This exercises the timed win probe (all main goals set as reached, then the win; the
victory message and the campaign map with the next level must appear), not natural playability.

The game gets the content packages through MOREYA_CONTENT_DIR (scripts/content_packages.py: game_environment). The
smoke level Mossgate lies in the wing 1 content package; a selected level that moved into a content package is found
there by its path below the repository (scripts/campaign_packages.py: level_file). Without the content packages a
selected level is missing or the game quits with exit code 7: the probe fails loudly and names the missing content.
"""
import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys


# Put the dependency DLL folder (BUILD_DEPS_ROOT, default build-deps in the home folder) on PATH and disable modal loader errors.
def probe_environment():
    if os.name != 'nt':
        raise RuntimeError('Campaign load probes require the Windows integration host')
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    environment = dict(os.environ)
    dependency_root = Path(os.environ.get('BUILD_DEPS_ROOT') or Path.home() / 'build-deps')
    dll_paths = [dependency_root / 'install/bin']
    environment['PATH'] = os.pathsep.join([str(path) for path in dll_paths]
                                          + [environment.get('PATH', '')])
    return environment


# A helper module of this folder, loaded by path so that isolated Python finds it.
def script_module(name):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


# The helper module for the campaign wing packages, loaded by path so that isolated Python finds it.
def packages_module():
    return script_module('campaign_packages')


# The helper module for the content packages (with the wing and room package modules it imports).
def content_module():
    packages_module()
    script_module('room_packages')
    return script_module('content_packages')


# The file of a selected repository-relative level (public tree, content package or wing package), else an error that
# names the missing content packages: a load probe never passes without the content.
def selected_level(repo, name):
    content_module()
    found = packages_module().level_file(repo, name)
    if found is None:
        missing = content_module().missing_packages(repo)
        raise RuntimeError('Selected level is missing: ' + str(name)
                           + ('; content packages missing: ' + ', '.join(missing) if missing else ''))
    return found


# Read only real campaign entries of the wing packages (with the content packages when present), in campaign order.
def campaign_levels(repo):
    return [entry['_path'] for entry in packages_module().entries(repo)]


# Refuse to launch probes while another copy of this executable is running.
def game_is_running(executable):
    """Compare full process paths, retaining the guard when identity cannot be read."""
    if os.name != 'nt':
        raise RuntimeError('Game process detection requires the Windows integration host')
    environment = dict(os.environ, ODP_PROBE_IMAGE_NAME=executable.name)
    command = ("$ErrorActionPreference = 'Stop'; "
               "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
               "ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | "
               "Where-Object { $_.Name -eq $env:ODP_PROBE_IMAGE_NAME } | "
               "Select-Object ProcessId, ExecutablePath)")
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                            stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=30, check=True, env=environment)
    # Process paths are emitted as UTF-8 rather than localized tasklist console text.
    # CIM emits explicit JSON, including an empty array when the game is not running.
    processes = json.loads(result.stdout.decode('utf-8-sig'))
    target = os.path.normcase(str(executable.resolve()))
    for process in processes:
        path = process.get('ExecutablePath')
        # An inaccessible executable path is unsafe to assume belongs to a different checkout.
        if not path:
            raise RuntimeError('Cannot identify running game PID %s' % process.get('ProcessId'))
        if os.path.normcase(str(Path(path).resolve())) == target:
            return True
    return False


def available_server_port():
    """Choose an available TCP port so other worktree games do not share our listener."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('0.0.0.0', 0))
        return probe.getsockname()[1]


# Resolve Git output strictly; a missing comparison base must never mean no changes.
def git_output(repo, *arguments):
    return subprocess.run(['git', '-C', str(repo), *arguments], check=True,
                          capture_output=True, text=True, encoding='utf-8',
                          stdin=subprocess.DEVNULL, timeout=30).stdout.strip()


# Freeze the pre-push integration reference and the built tip for this build run.
def capture_base(repo, base, output):
    baseline = git_output(repo, 'rev-parse', '--verify', base + '^{commit}')
    tip = git_output(repo, 'rev-parse', 'HEAD')
    git_output(repo, 'merge-base', '--is-ancestor', baseline, tip)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'base': baseline, 'tip': tip}) + '\n', encoding='utf-8')


# Select Mossgate only (owner decision 2026-11-28: one test level, changed maps are not loaded in addition), checked
# against the immutable build range.
def integration_levels(repo, base_file):
    saved = json.loads(base_file.read_text(encoding='utf-8'))
    base, tip = saved.get('base', ''), saved.get('tip', '')
    if not all(re.fullmatch(r'[0-9a-f]{40,64}', value) for value in (base, tip)):
        raise RuntimeError('Invalid saved integration commits')
    if git_output(repo, 'rev-parse', 'HEAD') != tip:
        raise RuntimeError('Saved integration tip differs from the deployed worktree')
    git_output(repo, 'merge-base', '--is-ancestor', base, tip)
    # Mossgate of the public wing 1 package, or at its former path in a tree of an older layout; in the current layout
    # (no public campaign) Mossgate of the wing 1 content package
    smoke = next((name for name in ('levels/campaign/wing1/Mossgate.level', 'levels/campaign/Mossgate.level')
                  if (repo / name).is_file()), 'levels/campaign/wing1/Mossgate.level')
    names = [smoke]
    if packages_module().has_public_campaign(repo):
        levels = [repo / name for name in names]
        for level in levels:
            if not level.is_file():
                raise RuntimeError('Selected level is missing: ' + str(level))
    else:
        levels = [selected_level(repo, name) for name in names]
    print('Integration load range: ' + base + '..' + tip, flush=True)
    return levels


# Run selected maps once, retaining logs and real process exit codes.
def deployment_levels(repo, manifest):
    """Revalidate selection against the actual deployed data snapshot before starting any game."""
    spec = importlib.util.spec_from_file_location('deploy_selection', Path(__file__).with_name('deploy-level-selection.py'))
    selector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector)
    saved = json.loads(manifest.read_text(encoding='utf-8'))
    if saved.get('schema') != 1 or saved.get('mode') not in ('selected', 'full'):
        raise RuntimeError('Invalid deployment selection manifest')
    if git_output(repo, 'rev-parse', 'HEAD') != saved['tip']:
        raise RuntimeError('Selected commit differs from actual deployed data')
    levels = selector.select(repo, saved['base'], saved['tip'], saved['mode'] == 'full')
    if levels != saved['levels']:
        raise RuntimeError('Deployment selection changed since preparation')
    print('Deploy load range: ' + str(saved['base']) + ' -> ' + saved['tip'], flush=True)
    for name, reason in levels.items():
        print('SELECT ' + name + ': ' + reason, flush=True)
    return [selected_level(repo, name) for name in levels]


# Run selected maps once, retaining logs and real process exit codes.
def main():
    """Capture a build range or run selected probes with isolated data, port and all acceptance checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--capture-base', help='Freeze the integration base before the push')
    selection.add_argument('--base-file', type=Path, help='Mossgate only, checked against this saved range')
    selection.add_argument('--deployment-selection', type=Path, help='Verified deployment receipt range and selected maps')
    selection.add_argument('--all-campaign', action='store_true', help='Explicit full campaign test')
    # Match run-level-test.py's 2 * seconds + 400 wall-clock budget for --seconds 1.
    # The game watchdog bounds loading/play; normal renderer teardown also needs time.
    parser.add_argument('--timeout', type=int, default=402)
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    if args.capture_base:
        capture_base(repo, args.capture_base, args.output)
        return 0
    if args.executable is None:
        parser.error('--executable is required for load probes')
    executable = args.executable.resolve(strict=True)
    campaign = campaign_levels(repo)
    levels = (deployment_levels(repo, args.deployment_selection) if args.deployment_selection
              else campaign if args.all_campaign else integration_levels(repo, args.base_file))
    if not levels:
        parser.error('No configured campaign maps found')
    args.output.mkdir(parents=True, exist_ok=True)
    # The game finds the content packages through MOREYA_CONTENT_DIR when they are present
    environment = content_module().game_environment(repo, probe_environment())
    port = available_server_port()
    failed = 0
    for level in levels:
        if game_is_running(executable):
            raise RuntimeError('Close the running game before campaign load probes')
        app_data = args.output.resolve() / level.stem
        app_data.mkdir(parents=True, exist_ok=True)
        command = [str(executable), '--run-level', str(level), '--seconds', '1',
                   '--appData', str(app_data), '--port', str(port)]
        try:
            result = subprocess.run(command, cwd=executable.parent,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=args.timeout, env=environment)
            log = (result.stdout + result.stderr).decode('utf-8', errors='replace')
            success = r'^PASS ' + re.escape(level.name) + r' : '
            if level in campaign:
                success += r'.*victory message shown, campaign map shows'
            # The game reports registered goals only for campaign maps (RunLevelTest), so only those must show them.
            goals = level not in campaign or re.search(r'GOALS registered=[1-9][0-9]*', log)
            passed = (result.returncode == 0 and goals
                      and re.search(success, log, re.MULTILINE))
            status = 'PASS' if passed else 'FAIL exit=' + str(result.returncode)
            if result.returncode == content_module().MISSING_CONTENT_EXIT_CODE:
                status += ' (content missing)'
        except subprocess.TimeoutExpired as error:
            log = ((error.stdout or b'') + (error.stderr or b'')).decode('utf-8', errors='replace')
            passed = False
            status = 'FAIL timeout'
        (args.output / (level.stem + '.log')).write_text(log, encoding='utf-8')
        print(level.name + ': ' + status, flush=True)
        if not passed:
            failed += 1
    print('Campaign load probes: total=%d failed=%d' % (len(levels), failed))
    return int(failed != 0)



def locked_main():
    """Serialize the complete invocation with deploy and other users of this executable."""
    import importlib.util
    from pathlib import Path
    # Explicit loading also supports isolated Python and source-probe imports.
    if 'odp_deployment' not in sys.modules:
        spec = importlib.util.spec_from_file_location('odp_deployment', Path(__file__).with_name('odp_deployment.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules['odp_deployment'] = module
        spec.loader.exec_module(module)
    lock_parser = argparse.ArgumentParser(add_help=False)
    lock_parser.add_argument('--executable', dest='executable')
    lock_args, _ = lock_parser.parse_known_args()
    if not lock_args.executable:
        return main()
    executable = lock_args.executable
    with sys.modules['odp_deployment'].executable_lock(executable):
        return main()


if __name__ == '__main__':
    try:
        sys.exit(locked_main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
