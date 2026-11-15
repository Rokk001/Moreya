"""The level load test can give the game its own server port, so parallel instances do not collide.

No compiler, no game: subprocess.Popen records the command lines and process timeouts.
The CLI supplies an available port for a level unless an explicit port was requested."""
from pathlib import Path
import ast
import importlib.util
import socket
import subprocess
import sys
from unittest.mock import patch
from unittest import mock

root = Path(__file__).resolve().parents[2]

# The merge must retain one port selector rather than silently shadowing a duplicate.
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
        timeouts.append(timeout)
        return '', None


def record(command, **kwargs):
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
with patch.object(sys, 'argv', arguments), patch.object(module, 'available_server_port', return_value=31303), \
        patch.object(subprocess, 'Popen', record), patch('builtins.print'), \
        mock.patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')):
    assert module.main() == 1
    assert commands[-1][-2:] == ['--port', '31303'], commands[-1]

with patch.object(sys, 'argv', arguments + ['--port', '31304']), \
        patch.object(module, 'available_server_port') as choose_port, \
        patch.object(subprocess, 'Popen', record), patch('builtins.print'), \
        mock.patch.object(subprocess, 'run', return_value=mock.Mock(stdout='')):
    assert module.main() == 1
    choose_port.assert_not_called()
    assert commands[-1][-2:] == ['--port', '31304'], commands[-1]

# The command line option exists and the game knows --port
assert '--port' in (root / 'scripts' / 'run-level-test.py').read_text(encoding='utf-8')
assert '("port"' in (root / 'source' / 'utils' / 'ResourceManager.cpp').read_text(encoding='utf-8'), 'game has no --port'
print('ok')
