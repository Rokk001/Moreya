"""Check exact font-cache keys and one-pass Git diff equivalence, including failure paths."""
import ast
import contextlib
from functools import lru_cache
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('coverage_check', ROOT / 'source/tests/check_pr_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


# Exercise the actual cached functions with explicit font metrics and recorded shaping calls.
class FontCacheTests(unittest.TestCase):
    # Cache keys must include the full text and font, while preserving exact measured widths.
    def test_exact_font_and_text_keys(self):
        source = ast.parse((ROOT / 'source/tests/check_dungeonbook_profile_layout.py').read_text())
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('text_width', 'line_height')]
        calls = []

        # Fixed shaped widths deliberately differ from summed character widths (kerning).
        class Face:
            # Remember the font identity used by each shape request.
            def __init__(self, name):
                self.name = name

            # Supply exact explicit text widths, including whitespace and a non-ASCII label.
            def getlength(self, text):
                calls.append((self.name, text))
                return {'AV': 7.25, 'A V': 12.5, 'é': 3.125}[text]

            # Metrics remain an exact pair, rather than approximated from the test viewport.
            def getmetrics(self):
                return (8, 3)

        namespace = {'lru_cache': lru_cache,
                     'font_files': {'small': (Face('small'), 0.5), 'large': (Face('large'), 2)}}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<actual-font-functions>', 'exec'), namespace)
        width = namespace['text_width']
        for _ in range(3):
            self.assertEqual(width('small', 'AV'), 3.625)
            self.assertEqual(width('large', 'AV'), 14.5)
            self.assertEqual(width('small', 'A V'), 6.25)
            self.assertEqual(width('small', 'é'), 1.5625)
        self.assertEqual(calls, [('small', 'AV'), ('large', 'AV'), ('small', 'A V'), ('small', 'é')])
        self.assertEqual(namespace['line_height']('small'), 5.5)
        self.assertEqual(namespace['line_height']('large'), 22)
        with self.assertRaises(KeyError):
            width('missing', 'AV')
        with self.assertRaises(KeyError):
            width('small', 'missing')


# Compare the real combined Git command against the previous two-command algorithm on fresh history.
class CoverageDiffTests(unittest.TestCase):
    # Include added, edited, deleted, renamed and binary files without changing rename detection.
    def test_combined_diff_matches_original(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)

            # Run Git only inside this isolated fixture and fail on any command error.
            def git(*args):
                return subprocess.check_output(['git', '-C', folder, *args], text=True,
                                               encoding='utf-8', stderr=subprocess.STDOUT).strip()

            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            git('config', 'core.autocrlf', 'false')
            (repo / 'edit.txt').write_text('old\nretained\n')
            (repo / 'delete.txt').write_text('gone\n')
            (repo / 'rename.txt').write_text('rename content\n' * 20)
            (repo / 'binary.dat').write_bytes(b'\0original')
            git('add', '.')
            git('commit', '-qm', 'Base fixture')
            base = git('rev-parse', 'HEAD')
            (repo / 'edit.txt').write_text('new\nretained\n  extra  \n\n')
            (repo / 'delete.txt').unlink()
            (repo / 'rename.txt').rename(repo / 'renamed.txt')
            (repo / 'new.txt').write_text('addition\n')
            (repo / 'binary.dat').write_bytes(b'\0changed')
            git('add', '-A')
            git('commit', '-qm', 'Changed fixture')
            tip = git('rev-parse', 'HEAD')
            with patch.object(coverage, 'ROOT', folder):
                files, added = coverage.diff_added(base, tip)
                old_files = set(coverage.run(['git', 'diff', '--name-only', base, tip], 'old names').splitlines())
                old_patch = coverage.run(['git', 'diff', '-U0', '--no-color', '--no-ext-diff', base, tip], 'old patch')
                old_added = {}
                current = None
                for line in old_patch.splitlines():
                    if line.startswith('+++ '):
                        current = line[6:] if line.startswith('+++ b/') else None
                        if current is not None:
                            old_added.setdefault(current, set())
                    elif line.startswith('+') and current is not None and line[1:].strip():
                        old_added[current].add(line[1:].strip())
                self.assertEqual(files, old_files)
                self.assertEqual(added, old_added)
                self.assertEqual(files, {'edit.txt', 'delete.txt', 'renamed.txt', 'new.txt', 'binary.dat'})
                self.assertEqual(added['edit.txt'], {'new', 'extra'})
                self.assertEqual(coverage.diff_added(tip, tip), (set(), {}))
                with self.assertRaises(coverage.CheckError):
                    coverage.diff_added(base, 'missing-ref')

    # A malformed raw section is an infrastructure failure, never an empty successful comparison.
    def test_malformed_raw_section_fails(self):
        for text in ('missing separator', ':bad\0file\0\0patch', ':100644 100644 a b R100\0old\0\0patch'):
            with self.subTest(text=text), self.assertRaises(coverage.CheckError):
                coverage.raw_files_and_patch(text)


# Timing output must not shorten the real observation windows or alter pass/fail decisions.
class LoadPhaseTests(unittest.TestCase):
    # Exercise the real CLI with deterministic clocks and both menu and level failure paths.
    def test_observation_windows_and_failures(self):
        spec = importlib.util.spec_from_file_location('load_phase_fixture', ROOT / 'scripts/run-level-test.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / 'fixture.exe'
            exe.touch()
            level = str(ROOT / 'levels/campaign/Mossgate.level')
            for menu_ok, level_ok in ((True, True), (False, True), (True, False)):
                output = io.StringIO()
                with patch.object(sys, 'argv', ['runner', '--exe', str(exe), '--port', '31419', level]), \
                     patch.object(runner, 'run_menu_test', return_value=(menu_ok, 'menu result')) as menu, \
                     patch.object(runner, 'run_level_with_frame_time', return_value=(level_ok, 'level result', None)) as load, \
                     patch.object(runner.time, 'perf_counter', side_effect=[1, 3, 4, 12]), \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(runner.main(), 0 if menu_ok and level_ok else 1)
                menu.assert_called_once_with(str(exe.resolve()), 8, 31419)
                load.assert_called_once_with(str(exe.resolve()), str(Path(level).resolve()), 120, 31419)
                phases = [json.loads(line[len('ODP_TEST_PHASE '):]) for line in output.getvalue().splitlines()
                          if line.startswith('ODP_TEST_PHASE ')]
                self.assertEqual(phases, [{'name': 'menu', 'seconds': 2},
                                          {'name': 'level:Mossgate.level', 'seconds': 8}])


if __name__ == '__main__':
    unittest.main()
