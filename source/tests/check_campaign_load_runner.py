"""Exercise campaign probe acceptance and timeout handling without starting the game."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import json
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('campaign_load_runner', ROOT / 'scripts/run-campaign-load-tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def exercise(output, code=0, timeout=False, requested_timeout=None):
    """Run one recorded probe and retain its real acceptance decision and log."""
    commands = []

    def run(command, **kwargs):
        """Record the game's command and simulate completion or a real deadline expiry."""
        commands.append((command, kwargs))
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output=output)
        return subprocess.CompletedProcess(command, code, output, b'')

    with tempfile.TemporaryDirectory(prefix='campaign-runner-') as temporary:
        directory = Path(temporary)
        executable = directory / 'game.exe'
        executable.touch()
        logs = directory / 'logs'
        original_run = runner.subprocess.run
        original_argv = sys.argv
        original_running = runner.game_is_running
        original_environment = runner.probe_environment
        original_levels = runner.campaign_levels
        runner.game_is_running = lambda executable: False
        runner.probe_environment = lambda: {}
        runner.campaign_levels = lambda repo: [ROOT / 'levels/campaign/Mossgate.level']
        runner.subprocess.run = run
        sys.argv = ['campaign-load-runner', '--executable', str(executable), '--output', str(logs)]
        if requested_timeout is not None:
            sys.argv += ['--timeout', str(requested_timeout)]
        try:
            with redirect_stdout(StringIO()) as captured:
                result = runner.main()
        finally:
            runner.subprocess.run = original_run
            runner.game_is_running = original_running
            runner.probe_environment = original_environment
            runner.campaign_levels = original_levels
            sys.argv = original_argv
        log = (logs / 'Mossgate.log').read_text(encoding='utf-8')
    assert len(commands) == 1
    command, options = commands[0]
    assert command[1:5] == ['--run-level', str(ROOT / 'levels/campaign/Mossgate.level'), '--seconds', '1']
    assert command[-2] == '--port' and 0 < int(command[-1]) <= 65535
    assert options['timeout'] == (402 if requested_timeout is None else requested_timeout)
    assert log == output.decode('utf-8')
    return result, captured.getvalue()


success = b'GOALS registered=2\nPASS Mossgate.level : victory message shown, campaign map shows the next level\n'
assert exercise(success)[0] == 0
assert exercise(success, code=2)[0] == 1
assert exercise(success, timeout=True)[0] == 1
assert exercise(success, timeout=True, requested_timeout=7)[0] == 1
assert exercise(success.replace(b'GOALS registered=2\n', b''))[0] == 1
assert exercise(success.replace(b'registered=2', b'registered=0'))[0] == 1
assert exercise(b'GOALS registered=2\n')[0] == 1
assert exercise(success.replace(b'victory message shown, campaign map shows', b'loaded'))[0] == 1
assert exercise(b'FAIL Mossgate.level : load error\n', code=2)[0] == 1


def check_process_scope():
    """Reject the deployed game and unknown paths, but permit a separate worktree game."""
    executable = ROOT / 'build/windows/opendungeons-plus.exe'
    other = ROOT / 'other-worktree/build/windows/opendungeons-plus.exe'
    for paths, expected in (([], False), ([str(other)], False), ([str(executable)], True),
                            ([str(other), str(executable)], True)):
        output = json.dumps([{'ExecutablePath': path} for path in paths]).encode('utf-8')
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output)) as run:
            assert runner.game_is_running(executable) == expected
        assert run.call_args.args[0][:2] == ['powershell', '-NoProfile']
        assert run.call_args.kwargs['check'] and run.call_args.kwargs['timeout'] == 30
    output = json.dumps([{'ProcessId': 789, 'ExecutablePath': None}]).encode('utf-8')
    with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output)):
        try:
            runner.game_is_running(executable)
        except RuntimeError as error:
            assert '789' in str(error), 'unreadable identity must identify the blocked process'
        else:
            raise AssertionError('An unreadable executable path must block probes')
    with patch.object(runner.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'powershell')):
        try:
            runner.game_is_running(executable)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('Failed process enumeration must block the probes')


def check_interleaved_worktree():
    """Reproduce another worktree appearing between passing probes without aborting deployment."""
    with tempfile.TemporaryDirectory(prefix='campaign-concurrency-') as temporary:
        directory = Path(temporary)
        executable = directory / 'opendungeons-plus.exe'
        executable.touch()
        levels = [ROOT / 'levels/campaign/Mossgate.level', ROOT / 'levels/campaign/HollinFen.level']
        commands = []

        def run(command, **kwargs):
            """Introduce a different worktree process before the second probe."""
            if command[0] == 'powershell':
                paths = [] if not commands else [{'ExecutablePath': str(directory / 'other/opendungeons-plus.exe')}]
                return subprocess.CompletedProcess(command, 0, json.dumps(paths).encode('utf-8'))
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, success, b'')

        with patch.object(sys, 'argv', ['runner', '--executable', str(executable), '--output', str(directory / 'logs')]), \
                patch.object(runner, 'probe_environment', return_value={}), \
                patch.object(runner, 'campaign_levels', return_value=levels), \
                patch.object(runner.subprocess, 'run', side_effect=run), redirect_stdout(StringIO()) as captured:
            assert runner.main() == 0
        assert len(commands) == 2
        assert 'Campaign load probes: total=2 failed=0' in captured.getvalue()
        for command in commands:
            assert command[-2] == '--port' and int(command[-1]) > 0
        with patch.object(sys, 'argv', ['runner', '--executable', str(executable), '--output', str(directory / 'logs')]), \
                patch.object(runner, 'probe_environment', return_value={}), \
                patch.object(runner, 'campaign_levels', return_value=levels), \
                patch.object(runner, 'game_is_running', return_value=True), \
                patch.object(runner.subprocess, 'run') as launch:
            try:
                runner.main()
            except RuntimeError as error:
                assert str(error) == 'Close the running game before campaign load probes'
            else:
                raise AssertionError('An existing deployed game must still block probes')
            launch.assert_not_called()


check_process_scope()
check_interleaved_worktree()
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
    occupied.bind(('0.0.0.0', 0))
    occupied.listen()
    assert runner.available_server_port() != occupied.getsockname()[1]
print('Campaign load runner: nine acceptance cases, process scope, interleaved worktrees and occupied-port avoidance verified')
