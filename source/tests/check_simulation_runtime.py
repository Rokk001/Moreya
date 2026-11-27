"""Preserve seeded outcomes and error propagation while removing repeated test work.

The skill scheduler test needs config/creatureSkills.cfg, a file of the core-config content package
(scripts/content_packages.py); without the content it is named as not checked and skipped. The plain combat tests need
the creature definitions and the chicken test the hatchery values: config/creatures.cfg and config/rooms.cfg are whole
only with their own rows of the same package, so without the content these tests are named and skipped too.
"""
import importlib.util
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/balance'))
import combat_sim as combat
import item_probe_support as items
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402


# Skip a test that needs the own rows of the mixed data tables when the content packages are not present.
def skip_without_content(test, name):
    """Names the test as not checked and skips it when the content packages are not present."""
    if not content_packages.has_content(ROOT):
        content_packages.unchecked('check_simulation_runtime', [name])
        test.skipTest('content not present')


# Load chase definitions without executing the full 144,000-case script during unit checks.
def chicken_definitions():
    path = ROOT / 'source/tests/check_chicken_catch_time.py'
    module = types.ModuleType('chicken_runtime_fixture')
    module.__file__ = str(path)
    text = path.read_text(encoding='utf-8').split('\nresults = {}', 1)[0]
    exec(compile(text, str(path), 'exec'), module.__dict__)
    return module


# Independently retain the original uncached placement algorithm and its random draw order.
def uncached_positions(module, room, seed):
    rng = random.Random('start-%s-%s' % (room.name, seed))
    chicken = None
    while chicken is None:
        chicken = room.pick_free_point(rng)
    candidates = [p for p in (room.pick_free_point(rng) for _ in range(40)) if p is not None]
    creature = max(candidates, key=lambda p: min(module.dist(p, chicken), 3.5) + rng.random() * 0.5)
    return chicken, creature


# Compare exact outcomes and remaining generator states, not only passing aggregate thresholds.
class SimulationRuntimeTests(unittest.TestCase):
    # Prepared ordinary attacks must preserve miss, avoidance, damage and conditional draw counts.
    def test_plain_blow_equivalence(self):
        skip_without_content(self, 'plain blow equivalence (own rows of config/creatures.cfg)')
        roster = combat.Roster(ROOT)
        names = roster.fighters()
        for index, name in enumerate(names):
            first = roster.unit(name, 1 + index % 30)
            second = roster.unit(names[-1 - index], 30 - index % 30)
            profile = combat.prepare_blow(roster, first, second)
            expected, actual = random.Random(index), random.Random(index)
            for _ in range(100):
                self.assertEqual(combat.blow(roster, first, second, expected), combat.prepared_blow(profile, actual))
            self.assertEqual(expected.getstate(), actual.getstate())

    # Every duel/group result remains identical when prepared arithmetic is replaced by the reference.
    def test_plain_scheduler_equivalence(self):
        skip_without_content(self, 'plain scheduler equivalence (own rows of config/creatures.cfg)')
        roster = combat.Roster(ROOT)
        names = roster.fighters()
        for index, name in enumerate(names):
            first, second = roster.unit(name, 10), roster.unit(names[-1 - index], 5)
            for function, extra in [(combat.duel, ()), (combat.duel_turns, ()), (combat.fight_group, (3,))]:
                actual_rng, expected_rng = random.Random(index), random.Random(index)
                for _ in range(4):
                    actual = function(roster, first, second, *extra, 1, actual_rng)
                    with patch.object(combat, 'prepare_blow', side_effect=lambda *args: args), \
                         patch.object(combat, 'prepared_blow', side_effect=lambda args, rng: combat.blow(*args, rng)):
                        expected = function(roster, first, second, *extra, 1, expected_rng)
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual_rng.getstate(), expected_rng.getstate())

    # Skills retain critical rolls, casts, healing, stuns and all per-fight results across every matrix case.
    def test_skill_scheduler_equivalence(self):
        if content_packages.data_file(ROOT, 'config/creatureSkills.cfg') is None and \
                not content_packages.has_content(ROOT):
            content_packages.unchecked('check_simulation_runtime', ['skill scheduler equivalence (config/creatureSkills.cfg)'])
            self.skipTest('content not present')
        roster = combat.Roster(ROOT)
        world = combat.World(roster)
        for level, template in combat.CASES_MATRIX:
            for index, name in enumerate(world.names):
                first = world.unit(name, level, template)
                second = world.unit(world.names[-1 - index], level, template)
                actual_rng, expected_rng = random.Random(index), random.Random(index)
                actual = combat.skill_fight(roster, world.glob['CritDamageMultiplier'], first, second, 2, 1, actual_rng)
                # The original skill_blow orders RNG before the multiplier in its argument list.
                with patch.object(combat, 'prepare_skill_blow', side_effect=lambda *args: args), \
                     patch.object(combat, 'prepared_skill_blow',
                                  side_effect=lambda args, rng: combat.skill_blow(*args[:-1], rng, args[-1])):
                    expected = combat.skill_fight(roster, world.glob['CritDamageMultiplier'], first, second, 2, 1, expected_rng)
                self.assertEqual(actual, expected)
                self.assertEqual(actual_rng.getstate(), expected_rng.getstate())

    # Reused positions match uncached placement and every selected chase result for every shape/kind/speed/logic.
    def test_chicken_placement_and_outcomes(self):
        skip_without_content(self, 'chicken placement and outcomes (own rows of config/rooms.cfg)')
        chicken = chicken_definitions()
        for room in chicken.make_rooms():
            for seed in range(8):
                expected = uncached_positions(chicken, room, seed)
                self.assertEqual(room.starting_positions(seed), expected)
                with patch.object(room, 'pick_free_point', side_effect=AssertionError('placement recomputed')):
                    self.assertEqual(room.starting_positions(seed), expected)
                for hen in (False, True):
                    for speed in chicken.CREATURE_SPEEDS:
                        for logic in ('old', 'new'):
                            actual = chicken.run(room, logic, speed, hen, seed)
                            with patch.object(room, 'starting_positions', side_effect=lambda value: uncached_positions(chicken, room, value)):
                                expected_turn = chicken.run(room, logic, speed, hen, seed)
                            self.assertEqual(actual, expected_turn, (room.name, seed, hen, speed, logic))

    # Optimization keeps checks enabled, bounded subprocesses, and compilation/execution failures visible.
    def test_item_probe_flags_and_failures(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(items, 'ROOT', Path(directory)):
            with patch.object(items.subprocess, 'run') as run:
                items.compile_and_run('fixture', 'int main() { return 0; }', optimize=True)
                command = run.call_args_list[0].args[0]
                self.assertIn('/O2', command)
                self.assertFalse(any('NDEBUG' in arg for arg in command))
                for call in run.call_args_list:
                    self.assertTrue(call.kwargs['check'])
                    self.assertEqual(call.kwargs['timeout'], 600)
            for fail_at in (0, 1):
                effects = [None] * fail_at + [subprocess.CalledProcessError(7, 'fixture')]
                with patch.object(items.subprocess, 'run', side_effect=effects) as run:
                    with self.assertRaises(subprocess.CalledProcessError):
                        items.compile_and_run('fixture', 'int main() { return 7; }', optimize=True)
                    self.assertEqual(run.call_count, fail_at + 1)


if __name__ == '__main__':
    unittest.main()
