"""Fault-inject the ten probe launch paths without compiling or starting a game."""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('defeat_camera_culling', 'defeat_debriefing', 'defeat_debriefing_click',
         'defeat_heart_burst', 'defeat_sequence', 'heart_badge_texture',
         'heart_health_ring', 'level_script', 'level_statistics', 'room_capture')


# Extract the executable launch tail, including any retry handlers around it.
def launch_body(tree, name):
    if name in ('defeat_heart_burst', 'heart_health_ring'):
        return next(n.body for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    if name in ('level_statistics', 'room_capture'):
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_probe')
        body = next(n.body for n in function.body if isinstance(n, ast.With))
    else:
        body = next(n.body for n in reversed(tree.body) if isinstance(n, ast.With))
    # Keep all launch result handling; omit fixture preparation and compilation.
    for index, node in enumerate(body):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == 'attempt':
            return body[index:]
    for index, node in enumerate(body):
        text = ast.unparse(node)
        if 'subprocess.run' in text and "'cl'" not in text and not isinstance(node, ast.If):
            return body[index:]
    raise AssertionError('No fixture launch found: ' + name)


# Preserve successes and failures while forbidding a second start of the same binary.
class ProbeStartTests(unittest.TestCase):
    # Exercise every production launch tail with success, nonzero exit and two OS errors.
    def test_launch_outcomes(self):
        for name in NAMES:
            tree = ast.parse((ROOT / 'source/tests' / ('check_' + name + '.py')).read_text())
            body = launch_body(tree, name)
            # A function wrapper preserves the production return and sys.exit statements.
            function = ast.FunctionDef(name='exercise', args=ast.arguments(posonlyargs=[], args=[],
                kwonlyargs=[], kw_defaults=[], defaults=[]), body=body, decorator_list=[])
            module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
            for outcome in ('pass', 'failed', 'blocked', 'missing'):
                with self.subTest(test=name, outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                    work = Path(temporary)
                    namespace = dict(subprocess=subprocess, sys=sys, work=work, cwd=work,
                        executable='check.exe', arguments=[], environment={}, exe=work/'check.exe',
                        command=[str(work/'check.exe')], deps=work, repo=ROOT, failures=[],
                        args=SimpleNamespace(loading_screens=False, menu_scene=False))
                    exec(compile(module, '<production launch>', 'exec'), namespace)
                    calls = []
                    # Simulate native launch semantics, retaining check=True behavior.
                    def run(command, **kwargs):
                        calls.append(command)
                        if outcome in ('blocked', 'missing'):
                            error = OSError('WinError 4551' if outcome == 'blocked' else 'missing executable')
                            error.winerror = 4551 if outcome == 'blocked' else 2
                            raise error
                        code = 0 if outcome == 'pass' else 7
                        if code and kwargs.get('check'):
                            raise subprocess.CalledProcessError(code, command)
                        return subprocess.CompletedProcess(command, code, '', '')
                    with patch.object(subprocess, 'run', side_effect=run):
                        try:
                            result = namespace['exercise']()
                        except OSError:
                            self.assertIn(outcome, ('blocked', 'missing'))
                        except subprocess.CalledProcessError as error:
                            self.assertEqual(outcome, 'failed')
                            self.assertEqual(error.returncode, 7)
                        except SystemExit as error:
                            self.assertEqual(error.code, 0 if outcome == 'pass' else 7)
                            self.assertEqual(name, 'level_script')
                        else:
                            self.assertNotIn(outcome, ('blocked', 'missing'))
                            if outcome == 'failed':
                                self.assertEqual(name, 'room_capture')
                                self.assertEqual(namespace['failures'], ['probe failed'])
                    self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
