"""Exercise campaign probe acceptance and timeout handling without starting the game."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile


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
            sys.argv = original_argv
        log = (logs / 'Mossgate.log').read_text(encoding='utf-8')
    assert len(commands) == 1
    command, options = commands[0]
    assert command[1:5] == ['--run-level', str(ROOT / 'levels/campaign/Mossgate.level'), '--seconds', '1']
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
print('Campaign load runner: bounded deadline and nine acceptance/failure cases verified')
