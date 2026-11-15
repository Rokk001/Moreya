"""The level load test can give the game its own server port, so parallel instances do not collide.

No compiler, no game: subprocess.Popen records the command lines and process timeouts.
The CLI supplies an available port for a level unless an explicit port was requested."""
from pathlib import Path
import ast
import importlib.util
import json
import socket
import subprocess
import sys
from unittest.mock import patch
from unittest import mock

root = Path(__file__).resolve().parents[2]

# The merge must retain one port selector rather than silently shadowing a duplicate.
# Independent port implementations added by both parents must merge into one definition.
runner_tree = ast.parse((root / 'scripts' / 'run-level-test.py').read_text(encoding='utf-8'))
assert sum(isinstance(node, ast.FunctionDef) and node.name == 'available_server_port'
           for node in runner_tree.body) == 1, 'expected exactly one available_server_port definition'

spec = importlib.util.spec_from_file_location('run_level_test', str(root / 'scripts' / 'run-level-test.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

commands = []
timeouts = []


class RecordedProcess(object):
    """Stands in for the game process: records nothing more than that it ran and ended with code 3."""
    returncode = 3

    def communicate(self, timeout=None):
        """Record the watchdog allowance and simulate a failed game run."""
        timeouts.append(timeout)
        return '', None


def record(command, **kwargs):
    """Record the invocation without starting the game."""
    commands.append(list(command))
    return RecordedProcess()


netstat = mock.patch.object(subprocess, 'run', return_value=mock.Mock(stdout=''))
netstat.start()
original = subprocess.Popen
subprocess.Popen = record
try:
    module.run_menu_test('game.exe', 1)
    module.run_menu_test('game.exe', 1, 31301)
    module.run_level_with_frame_time('game.exe', 'a.level', 1)
    module.run_level_with_frame_time('game.exe', 'a.level', 1, 31302)
finally:
    subprocess.Popen = original
    netstat.stop()

assert len(commands) == 4, commands
assert '--port' not in commands[0] and '--port' not in commands[2], 'no port requested, none may be passed'
assert commands[1][-2:] == ['--port', '31301'], commands[1]
assert commands[3][-2:] == ['--port', '31302'], commands[3]
assert module.port_arguments(None) == [] and module.port_arguments(5) == ['--port', '5']
assert timeouts == [402, 402, 402, 402], timeouts

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
    occupied.bind(('0.0.0.0', 0))
    occupied.listen()
    assert module.available_server_port() != occupied.getsockname()[1]

arguments = ['run-level-test.py', '--exe', str(root / 'scripts' / 'run-level-test.py'),
             '--menu-seconds', '0', '--seconds', '1', 'a.level']
with patch.object(sys, 'argv', arguments), \
        patch.object(module, 'available_server_port', return_value=31303) as choose_port, \
        patch.object(subprocess, 'Popen', record), \
        patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')), patch('builtins.print'):
    assert module.main() == 1
    choose_port.assert_called_once_with()
    assert commands[-1][-2:] == ['--port', '31303'], commands[-1]

with patch.object(sys, 'argv', arguments + ['--port', '31304']), \
        patch.object(module, 'available_server_port') as choose_port, \
        patch.object(subprocess, 'Popen', record), \
        patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')), patch('builtins.print'):
    assert module.main() == 1
    choose_port.assert_not_called()
    assert commands[-1][-2:] == ['--port', '31304'], commands[-1]

# The merged CLI shares one port across menu and levels and retains diagnostics and timeouts.
commands.clear()
timeouts.clear()
arguments = ['run-level-test.py', '--exe', str(root / 'scripts' / 'run-level-test.py'),
             '--menu-seconds', '1', '--seconds', '1', 'a.level', 'b.level']
with patch.object(sys, 'argv', arguments), \
        patch.object(module, 'available_server_port', return_value=31305) as choose_port, \
        patch.object(subprocess, 'Popen', record), \
        patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')) as listeners, \
        patch('builtins.print') as output:
    assert module.main() == 1
    choose_port.assert_called_once_with()
    assert len(commands) == 3, commands
    assert all(command[-2:] == ['--port', '31305'] for command in commands), commands
    assert commands[0][1:3] == ['--menu-test', '1'], commands[0]
    assert commands[1][1] == commands[2][1] == '--run-level', commands
    assert timeouts == [402, 402, 402], timeouts
    records = [json.loads(call.args[0][len('LOAD_PROCESS '):])
               for call in output.call_args_list
               if call.args and str(call.args[0]).startswith('LOAD_PROCESS ')]
    assert len(records) == 6, records
    assert [record['event'] for record in records] == ['started', 'finished'] * 3, records
    for index, command in enumerate(commands):
        started, finished = records[2 * index:2 * index + 2]
        assert started['argv'] == finished['argv'] == command
        assert started['port'] == finished['port'] == 31305
        assert started['started_at'] and finished['ended_at']
        assert finished['exit_code'] == 3
        if module.os.name == 'nt':
            assert finished['port_listeners'] == ''
    if module.os.name == 'nt':
        assert listeners.call_count == 3, listeners.call_count

# An explicit override also shares one port across menu and levels without invoking the selector.
commands.clear()
timeouts.clear()
with patch.object(sys, 'argv', arguments + ['--port', '31307']), \
        patch.object(module, 'available_server_port') as choose_port, \
        patch.object(subprocess, 'Popen', record), \
        patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')), patch('builtins.print'):
    assert module.main() == 1
    choose_port.assert_not_called()
    assert len(commands) == 3, commands
    assert all(command[-2:] == ['--port', '31307'] for command in commands), commands
    assert commands[0][1:3] == ['--menu-test', '1'], commands[0]
    assert commands[1][1] == commands[2][1] == '--run-level', commands
    assert timeouts == [402, 402, 402], timeouts

# A watchdog timeout still kills each process and emits finished port diagnostics.
for run, arguments in ((module.run_menu_test, ('game.exe', 1, 31306)),
                       (module.run_level_with_frame_time, ('game.exe', 'a.level', 1, 31306))):
    process = mock.Mock(pid=124, returncode=-1)
    process.communicate.side_effect = [subprocess.TimeoutExpired('game.exe', 402), ('', None)]
    with patch.object(subprocess, 'Popen', return_value=process), \
            patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')), \
            patch('builtins.print') as output:
        result = run(*arguments)
    assert not result[0] and 'timeout' in result[1] and '402 s' in result[1], result
    process.kill.assert_called_once_with()
    assert process.communicate.call_args_list == [mock.call(timeout=402), mock.call()]
    records = [json.loads(call.args[0][len('LOAD_PROCESS '):])
               for call in output.call_args_list
               if call.args and str(call.args[0]).startswith('LOAD_PROCESS ')]
    assert len(records) == 2 and records[-1]['event'] == 'finished', records
    assert records[-1]['pid'] == 124 and records[-1]['port'] == 31306
    assert records[-1]['exit_code'] is None and records[-1]['ended_at']
    if module.os.name == 'nt':
        assert records[-1]['port_listeners'] == ''

# The command line option exists and the game knows --port
assert '--port' in (root / 'scripts' / 'run-level-test.py').read_text(encoding='utf-8')
assert '("port"' in (root / 'source' / 'utils' / 'ResourceManager.cpp').read_text(encoding='utf-8'), 'game has no --port'
print('ok')
