"""Integrator-only campaign load/goal-registration probes using an already built game.

Run with --executable <game> --output <worktree output directory> while the game
is closed. This exercises the timed win probe (all main goals set as reached, then the win; the
victory message and the campaign map with the next level must appear), not natural playability.
"""
import argparse
import ctypes
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


# Read only real campaign entries, ignoring commented examples.
def campaign_levels(repo):
    text = (repo / 'levels/campaign/Campaign.cfg').read_text(encoding='utf-8')
    active = False
    levels = []
    for raw in text.splitlines():
        line = raw.strip()
        if line == '[Level]':
            active = True
        elif line == '[/Level]':
            active = False
        elif active and line.startswith('File='):
            levels.append(repo / 'levels' / line.split('=', 1)[1].strip())
    return levels


# Refuse to launch probes while another copy of this game is running.
def game_is_running(executable):
    """Guard this executable's resources without rejecting isolated worktree tests."""
    if os.name != 'nt':
        raise RuntimeError('Game process detection requires the Windows integration host')
    name = executable.name.replace("'", "''")
    command = ("[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; "
               "$games = @(Get-CimInstance Win32_Process -Filter \"Name='" + name + "'\" "
               "-ErrorAction Stop | Select-Object ExecutablePath); "
               "ConvertTo-Json -Compress -InputObject $games")
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=30, check=True)
    # Avoid tasklist's localized console-codepage messages: CIM emits explicit UTF-8 JSON,
    # including an empty array when the game is not running.
    games = json.loads(result.stdout.decode('utf-8-sig'))
    target = os.path.normcase(str(executable.resolve()))
    # An inaccessible executable path is unsafe to assume belongs to a different checkout.
    return any(not game['ExecutablePath'] or
               os.path.normcase(str(Path(game['ExecutablePath']).resolve())) == target
               for game in games)


def available_server_port():
    """Select an available listener port so other worktree probes can run independently."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('0.0.0.0', 0))
        return probe.getsockname()[1]


# Run every configured map once, retaining logs and real process exit codes.
def main():
    """Run each campaign probe with isolated data and port, retaining strict acceptance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    # Match run-level-test.py's 2 * seconds + 400 wall-clock budget for --seconds 1.
    # The game watchdog bounds loading/play; normal renderer teardown also needs time.
    parser.add_argument('--timeout', type=int, default=402)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    repo = args.repo.resolve(strict=True)
    levels = campaign_levels(repo)
    if not levels:
        parser.error('No configured campaign maps found')
    args.output.mkdir(parents=True, exist_ok=True)
    environment = probe_environment()
    failed = 0
    for level in levels:
        if game_is_running(executable):
            raise RuntimeError('Close the running game before campaign load probes')
        app_data = args.output.resolve() / level.stem
        app_data.mkdir(parents=True, exist_ok=True)
        command = [str(executable), '--run-level', str(level), '--seconds', '1',
                   '--appData', str(app_data), '--port', str(available_server_port())]
        try:
            result = subprocess.run(command, cwd=executable.parent,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=args.timeout, env=environment)
            log = (result.stdout + result.stderr).decode('utf-8', errors='replace')
            passed = (result.returncode == 0 and re.search(r'GOALS registered=[1-9][0-9]*', log)
                      and re.search(r'^PASS .*victory message shown, campaign map shows', log, re.MULTILINE))
            status = 'PASS' if passed else 'FAIL exit=' + str(result.returncode)
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
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
