"""Regress Deploy interruption by another worktree while retaining campaign acceptance checks."""
import ast
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
# Both parents added these helpers; conflict resolution must retain exactly one of each.
tree = ast.parse((ROOT / 'scripts/run-campaign-load-tests.py').read_text(encoding='utf-8'))
for name in ('game_is_running', 'available_server_port', 'main'):
    assert sum(isinstance(node, ast.FunctionDef) and node.name == name
               for node in tree.body) == 1, 'merged runner must define ' + name + ' exactly once'

spec = importlib.util.spec_from_file_location('campaign_probe_isolation', ROOT / 'scripts/run-campaign-load-tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def process_result(records):
    """Represent the actual Windows process query without starting a game."""
    return subprocess.CompletedProcess([], 0, json.dumps(records).encode('utf-8'), b'')


def verify_isolation():
    """A foreign game appearing after two passes must allow the third isolated probe."""
    with tempfile.TemporaryDirectory(prefix='campaign-isolation-') as temporary:
        directory = Path(temporary)
        executable = directory / 'deployed' / 'opendungeons-plus.exe'
        executable.parent.mkdir()
        executable.touch()
        foreign = directory / 'another-worktree' / executable.name
        foreign_record = {'ProcessId': 456, 'ExecutablePath': str(foreign)}
        same_record = {'ProcessId': 123, 'ExecutablePath': str(executable).upper()}
        with mock.patch.object(runner.subprocess, 'run', return_value=process_result([foreign_record])):
            assert not runner.game_is_running(executable)
        with mock.patch.object(runner.subprocess, 'run', return_value=process_result([foreign_record, same_record])):
            assert runner.game_is_running(executable), 'the deployed executable must still be blocked'
        with mock.patch.object(runner.subprocess, 'run', return_value=process_result([])):
            assert not runner.game_is_running(executable)
        with mock.patch.object(runner.subprocess, 'run', return_value=process_result([{'ProcessId': 789, 'ExecutablePath': None}])):
            try:
                runner.game_is_running(executable)
            except RuntimeError as error:
                assert '789' in str(error)
            else:
                raise AssertionError('unreadable process identity must fail closed')
        with mock.patch.object(runner.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'powershell')):
            try:
                runner.game_is_running(executable)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError('failed process queries must not mean no game')

        commands = []
        queries = []
        levels = [directory / name for name in ('Mossgate.level', 'Brackenford.level', 'Third.level')]

        def run(command, **options):
            """Introduce a foreign process before probe three, as in the failed Deploy."""
            if command[0] == 'powershell':
                queries.append(command)
                return process_result([foreign_record] if len(commands) >= 2 else [])
            commands.append(command)
            assert options['timeout'] == 402
            assert options['cwd'] == executable.parent
            output = ('GOALS registered=2\nPASS ' + Path(command[2]).name
                      + ' : victory message shown, campaign map shows the next level\n').encode('utf-8')
            return subprocess.CompletedProcess(command, 0, output, b'')

        arguments = ['campaign-probes', '--executable', str(executable), '--output', str(directory / 'logs')]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(('0.0.0.0', 0))
            occupied.listen()
            with mock.patch.object(runner.subprocess, 'run', side_effect=run), \
                    mock.patch.object(runner, 'campaign_levels', return_value=levels), \
                    mock.patch.object(runner, 'probe_environment', return_value={}), \
                    mock.patch.object(sys, 'argv', arguments), redirect_stdout(StringIO()) as output:
                assert runner.main() == 0
            assert len(commands) == len(queries) == 3
            ports = [int(command[command.index('--port') + 1]) for command in commands]
            assert len(set(ports)) == 1
            assert 0 < ports[0] <= 65535 and ports[0] != occupied.getsockname()[1]
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as selected:
                selected.bind(('0.0.0.0', ports[0]))
            assert [command[2] for command in commands] == [str(level) for level in levels]
            assert len({command[command.index('--appData') + 1] for command in commands}) == 3
            assert 'Campaign load probes: total=3 failed=0' in output.getvalue()
            assert len(list((directory / 'logs').glob('*.log'))) == 3


verify_isolation()
runpy.run_path(str(ROOT / 'source/tests/check_campaign_load_runner.py'), run_name='__main__')
print('Campaign probe isolation: executable identity, fail-closed detection, three probes and available port verified')
