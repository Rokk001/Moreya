"""Load failures retain the exact invocation and listening process IDs; no game is started."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from unittest import mock

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('load_runner', root / 'scripts/run-level-test.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
process = mock.Mock(pid=123, returncode=3)
process.communicate.return_value = ('FAIL sample.level: Could not listen to server port status=4', None)
captured = io.StringIO()
with mock.patch.object(runner.subprocess, 'Popen', return_value=process), \
     mock.patch.object(runner.subprocess, 'run', return_value=mock.Mock(stdout='  TCP    0.0.0.0:31301    0.0.0.0:0    LISTENING    456\n')), \
     contextlib.redirect_stdout(captured):
    passed, _, _ = runner.run_level_with_frame_time('game.exe', 'sample.level', 1, 31301)
assert not passed
records = [json.loads(line[len('LOAD_PROCESS '):]) for line in captured.getvalue().splitlines()
           if line.startswith('LOAD_PROCESS ')]
assert records, 'Missing load process diagnostics'
assert records[0]['pid'] == 123
assert records[0]['port'] == 31301
assert records[0]['argv'][-2:] == ['--port', '31301']
assert records[0]['started_at']
assert records[-1]['exit_code'] == 3
if runner.os.name == 'nt':
    assert '456' in records[-1]['port_listeners']
print('ok')

# Bind two real listeners while choosing a third port, without starting the game.
import socket
with socket.socket() as first, socket.socket() as second:
    first.bind(("0.0.0.0", 0))
    first.listen()
    second.bind(("0.0.0.0", 0))
    second.listen()
    chosen = runner.available_server_port()
    assert chosen not in (first.getsockname()[1], second.getsockname()[1])
