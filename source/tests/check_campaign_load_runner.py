"""Exercise campaign probe acceptance and timeout handling without starting the game."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
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
        original_guard = runner.game_is_running
        original_environment = runner.probe_environment
        original_levels = runner.campaign_levels
        original_argv = sys.argv
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
            runner.game_is_running = original_guard
            runner.probe_environment = original_environment
            runner.campaign_levels = original_levels
            sys.argv = original_argv
        log = (logs / 'Mossgate.log').read_text(encoding='utf-8')
    assert len(commands) == 1
    command, options = commands[0]
    assert command[1:5] == ['--run-level', str(ROOT / 'levels/campaign/Mossgate.level'), '--seconds', '1']
    assert options['timeout'] == (402 if requested_timeout is None else requested_timeout)
    assert command[-2] == '--port'
    assert 0 < int(command[-1]) <= 65535
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
print('Campaign load runner: bounded deadline and nine acceptance/failure cases verified')


def check_process_identity():
    """Keep the deployed-executable guard without rejecting independent worktrees."""
    executable = ROOT / 'build/windows/opendungeons-plus.exe'
    other = ROOT / 'other-worktree/build/windows/opendungeons-plus.exe'
    cases = [([], False),
             ([{'ProcessId': 42, 'ExecutablePath': str(other)}], False),
             ([{'ProcessId': 43, 'ExecutablePath': str(executable).upper()}], True),
             ([{'ProcessId': 42, 'ExecutablePath': str(other)},
               {'ProcessId': 43, 'ExecutablePath': str(executable)}], True)]
    for processes, expected in cases:
        completed = subprocess.CompletedProcess([], 0, json.dumps(processes).encode('utf-8'), b'')
        with patch.object(runner.subprocess, 'run', return_value=completed) as query:
            assert runner.game_is_running(executable) == expected
        assert query.call_args.kwargs['check'] is True
        assert query.call_args.kwargs['timeout'] == 30
        assert query.call_args.kwargs['env']['ODP_PROBE_IMAGE_NAME'] == executable.name
    unknown = subprocess.CompletedProcess([], 0, b'[{"ProcessId":44,"ExecutablePath":null}]', b'')
    with patch.object(runner.subprocess, 'run', return_value=unknown):
        try:
            runner.game_is_running(executable)
        except RuntimeError as error:
            assert 'PID 44' in str(error)
        else:
            raise AssertionError('Unreadable process identity must block probes')
    for error in [subprocess.CalledProcessError(1, 'powershell'),
                  subprocess.TimeoutExpired('powershell', 30)]:
        with patch.object(runner.subprocess, 'run', side_effect=error):
            try:
                runner.game_is_running(executable)
            except type(error):
                pass
            else:
                raise AssertionError('Process inspection failure must block probes')


def check_mid_campaign_process():
    """Reproduce another worktree starting after five successful campaign probes."""
    with tempfile.TemporaryDirectory(prefix='campaign-identity-') as temporary:
        directory = Path(temporary)
        executable = directory / 'deployed/opendungeons-plus.exe'
        executable.parent.mkdir()
        executable.touch()
        other = directory / 'other-worktree/opendungeons-plus.exe'
        levels = [directory / ('probe%d.level' % index) for index in range(6)]
        launches = []
        inspections = []

        def run(command, **kwargs):
            """Introduce the unrelated process at the exact original failure boundary."""
            if command[0] == 'powershell':
                processes = [] if len(launches) < 5 else [
                    {'ProcessId': 42, 'ExecutablePath': str(other)}]
                inspections.append(processes)
                return subprocess.CompletedProcess(command, 0, json.dumps(processes).encode('utf-8'), b'')
            launches.append(command)
            return subprocess.CompletedProcess(command, 0, success, b'')

        arguments = ['campaign-load-runner', '--executable', str(executable),
                     '--output', str(directory / 'logs')]
        with patch.object(runner.subprocess, 'run', side_effect=run), \
                patch.object(runner, 'probe_environment', return_value={}), \
                patch.object(runner, 'campaign_levels', return_value=levels), \
                patch.object(sys, 'argv', arguments), redirect_stdout(StringIO()) as captured:
            assert runner.main() == 0
        assert len(launches) == 6
        assert len(inspections) == 6 and inspections[-1][0]['ProcessId'] == 42
        assert 'total=6 failed=0' in captured.getvalue()
        for command in launches:
            assert command[-2] == '--port' and 0 < int(command[-1]) <= 65535
        assert len(list((directory / 'logs').glob('*.log'))) == 6


check_process_identity()
check_mid_campaign_process()
print('Campaign load runner: seven process identity/error cases and mid-campaign concurrency verified')
