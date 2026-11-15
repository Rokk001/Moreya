"""Preserve asset checks while sharing fresh preparation and batching identical geometry."""
import contextlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'source' / 'tests'))
import asset_check_timing as timing
import check_animation_assets as animation
import check_tavern_drink_834 as drink
import check_tavern_seat_clips as seated
import fix_walk_feet as feet


# Reproduce the original per-frame/per-scale maximum, including strict furniture boundary tests.
def original_stool_clip_depth(points):
    return max(drink.stool_depth(points[frame] * level) for frame in range(len(points))
               for level in (seated.seats.LEVEL_SCALE_LOW, seated.seats.LEVEL_SCALE_HIGH))


# Supply fixed transforms independently of production assets for selected/full parser equivalence.
def skeleton_xml():
    animations = []
    for name, amount in (('Drink', 1), ('SitDrink', 2), ('Unused', 3)):
        animations.append('''<animation name="%s" length="2"><tracks><track bone="child"><keyframes>
<keyframe time="0"><translate x="0" y="0" z="0"/></keyframe>
<keyframe time="2"><translate x="%d" y="1" z="0"/><rotate angle="0.4"><axis x="0" y="0" z="1"/></rotate><scale x="1.2" y="1" z="0.9"/></keyframe>
</keyframes></track></tracks></animation>''' % (name, amount))
    return '''<skeleton><bones>
<bone id="0" name="root"><position x="1" y="0" z="0"/></bone>
<bone id="1" name="child"><position x="0" y="2" z="0"/></bone>
</bones><bonehierarchy><boneparent bone="child" parent="root"/></bonehierarchy><animations>''' + ''.join(animations) + '</animations></skeleton>'


# Verify exact batching, fresh per-run caching, selected transforms and unchanged failure propagation.
class AssetRuntimeTests(unittest.TestCase):
    # Retain every random sample, both scales, contact boundaries and nonfinite rejection behavior.
    def test_batched_depth_matches_original(self):
        random = np.random.default_rng(873)
        samples = random.uniform((-1, -1.5, -0.1), (1, 0.5, 0.6), (17, 43, 3))
        boundary = np.array([[[0.323, -0.8, 0.4], [-0.323, -0.8, 0.4],
                              [0, -0.8 - 0.588, 0.4], [0, -0.8 + 0.588, 0.4],
                              [0, -0.8, 0.37], [0, -0.8, 0.4425],
                              [np.nan, 0, 0], [np.inf, 0, 0], [-np.inf, 0, 0]]])
        for points in (samples, boundary, np.zeros((3, 0, 3)), samples[:1]):
            with self.subTest(shape=points.shape):
                self.assertEqual(seated.stool_clip_depth(points), original_stool_clip_depth(points))
        with self.assertRaises(ValueError):
            seated.stool_clip_depth(np.zeros((0, 2, 3)))

    # A penetrating vertex past the first bounded batch in the final frame must still fail.
    def test_last_frame_collision_is_not_lost(self):
        points = np.full((385, 100, 3), 10.0)
        self.assertEqual(seated.stool_clip_depth(points), 0.0)
        points[-1, -1] = [0.0, -0.5, 0.15]
        depth = seated.stool_clip_depth(points)
        self.assertEqual(depth, original_stool_clip_depth(points))
        self.assertGreater(depth, seated.MAX_TABLE_DEPTH)

    # Opt-in parsing retains identical rig metadata and every requested keyframe transform.
    def test_selected_clip_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rig.xml'
            path.write_text(skeleton_xml())
            full = feet.Skel(path)
            selected = feet.Skel(path, clip_names=('Drink', 'SitDrink'))
            self.assertEqual(set(full.clips), {'Drink', 'SitDrink', 'Unused'})
            self.assertEqual(set(selected.clips), {'Drink', 'SitDrink'})
            self.assertEqual(full.names, selected.names)
            self.assertEqual(full.parent, selected.parent)
            self.assertEqual(full.topo, selected.topo)
            for name in selected.clips:
                self.assertEqual(full.clips[name].length, selected.clips[name].length)
                self.assertEqual(full.clips[name].order, selected.clips[name].order)
                times = np.array([0, 0.25, 1, 1.75, 2])
                for first, second in zip(full.locals_at(full.clips[name], times),
                                         selected.locals_at(selected.clips[name], times)):
                    for a, b in zip(first, second):
                        np.testing.assert_array_equal(a, b)
            with self.assertRaises(KeyError):
                selected.clips['KnockedOut']
            path.write_text(skeleton_xml().replace('time="2"', 'time="invalid"'))
            with self.assertRaises(ValueError):
                feet.Skel(path, clip_names=('Drink',))

    # A discarded clip still receives every structural and numeric validation of the original parser.
    def test_unselected_clip_failures_are_preserved(self):
        key = 'tracks/track/keyframes/keyframe[@time="2"]'
        cases = [('', 'length', 'invalid', ValueError), ('', 'length', None, TypeError),
                 (key, 'time', 'invalid', ValueError), (key, 'time', None, TypeError),
                 (key + '/translate', 'x', 'invalid', ValueError),
                 (key + '/translate', 'y', None, TypeError),
                 (key + '/scale', 'z', 'invalid', ValueError),
                 (key + '/scale', 'x', None, TypeError),
                 (key + '/rotate', 'angle', 'invalid', ValueError),
                 (key + '/rotate', 'angle', 'inf', ValueError),
                 (key + '/rotate/axis', 'x', 'invalid', ValueError),
                 (key + '/rotate/axis', 'z', None, TypeError)]
        removed = [('', 'tracks'), ('tracks/track', 'keyframes'), (key + '/rotate', 'axis')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rig.xml'
            for locator, attribute, value, error in cases:
                with self.subTest(locator=locator, attribute=attribute, value=value):
                    root = ET.fromstring(skeleton_xml())
                    unused = root.find('animations/animation[@name="Unused"]')
                    element = unused.find(locator) if locator else unused
                    if value is None:
                        element.attrib.pop(attribute)
                    else:
                        element.set(attribute, value)
                    path.write_text(ET.tostring(root, encoding='unicode'))
                    for selection in (None, ('Drink', 'SitDrink')):
                        with self.assertRaises(error):
                            feet.Skel(path, clip_names=selection)
            for locator, tag in removed:
                with self.subTest(missing=tag):
                    root = ET.fromstring(skeleton_xml())
                    unused = root.find('animations/animation[@name="Unused"]')
                    element = unused.find(locator) if locator else unused
                    element.remove(element.find(tag))
                    path.write_text(ET.tostring(root, encoding='unicode'))
                    for selection in (None, ('Drink', 'SitDrink')):
                        with self.assertRaises(AttributeError):
                            feet.Skel(path, clip_names=selection)

    # Repeated XML rotations match uncached conversion exactly, keep signed-zero keys and share no mutable output.
    def test_rotation_cache_matches_uncached_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rig.xml'
            path.write_text(skeleton_xml())
            original = feet.aa2q
            with patch.object(feet, 'aa2q', wraps=original) as convert:
                rig = feet.Skel(path)
                self.assertEqual(convert.call_count, 1)
                feet.Skel(path)
                self.assertEqual(convert.call_count, 2)
            expected = original(0.4, [0.0, 0.0, 1.0])
            for clip in rig.clips.values():
                np.testing.assert_array_equal(clip.tracks['child'].Q[1], expected)
            rig.clips['Drink'].tracks['child'].Q[1, 0] = 99
            np.testing.assert_array_equal(rig.clips['SitDrink'].tracks['child'].Q[1], expected)
            root = ET.fromstring(skeleton_xml())
            rotations = root.findall('animations/animation/tracks/track/keyframes/keyframe/rotate')
            for rotation, value in zip(rotations, ('0', '-0', '0.0')):
                rotation.set('angle', value)
            path.write_text(ET.tostring(root, encoding='unicode'))
            with patch.object(feet, 'aa2q', wraps=original) as convert:
                rig = feet.Skel(path)
                self.assertEqual(convert.call_count, 3)
            for clip, value in zip(rig.clips.values(), ('0', '-0', '0.0')):
                expected = original(float(value), [0.0, 0.0, 1.0])
                actual = clip.tracks['child'].Q[1]
                np.testing.assert_array_equal(actual, expected)
                np.testing.assert_array_equal(np.signbit(actual), np.signbit(expected))

    # Share preparation only within one instance and do not cache conversion failures or stale prior runs.
    def test_assets_cache_scope_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            mesh = (np.array([[1.0, 2.0, 3.0]]), [], [[]])
            skeleton = object()
            with patch('check_animation_assets.export') as export, \
                    patch('author_rest_poses.mesh_data', return_value=mesh) as parsed, \
                    patch.object(feet, 'Skel', return_value=skeleton) as rig:
                assets = drink.TavernAssets(out, clip_names=None)
                self.assertIs(assets.mesh('one.mesh'), mesh)
                self.assertIs(assets.mesh('one.mesh'), mesh)
                self.assertEqual(parsed.call_count, 1)
                self.assertIs(assets.skeleton('one'), skeleton)
                self.assertIs(assets.skeleton('one'), skeleton)
                self.assertEqual(rig.call_count, 1)
                self.assertIsNone(rig.call_args.kwargs['clip_names'])
                self.assertEqual(export.call_count, 2)
                fresh = drink.TavernAssets(out)
                fresh.mesh('one.mesh')
                fresh.skeleton('one')
                self.assertEqual(export.call_count, 4)
                self.assertEqual(rig.call_args.kwargs['clip_names'], ('Drink', 'SitDrink', 'KnockedOut'))
                export.side_effect = RuntimeError('conversion failed')
                with self.assertRaisesRegex(RuntimeError, 'conversion failed'):
                    assets.mesh('broken.mesh')
                self.assertNotIn('broken.mesh', assets.meshes)

    # Deferring redundant XML parsing keeps converter failures and the consuming parser's syntax errors.
    def test_export_parse_and_converter_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            # Model a fresh converter output rather than trusting a file from a preceding run.
            def convert(command, **kwargs):
                self.assertTrue(kwargs['check'])
                self.assertEqual(kwargs['timeout'], 60)
                Path(command[-1]).write_text(skeleton_xml())

            with patch.object(animation.subprocess, 'run', side_effect=convert):
                root = animation.export('rig.skeleton', out)
                self.assertEqual(root.tag, 'skeleton')
                self.assertIsNone(animation.export('rig.skeleton', out, return_tree=False))
                self.assertEqual(set(feet.Skel(out / 'rig.skeleton.xml').clips),
                                 {'Drink', 'SitDrink', 'Unused'})
            with patch.object(animation.subprocess, 'run', side_effect=subprocess.CalledProcessError(7, 'converter')):
                with self.assertRaises(subprocess.CalledProcessError):
                    animation.export('rig.skeleton', out, return_tree=False)
            # Malformed fresh output still fails at the mandatory immediate full-file parse.
            def broken_convert(command, **kwargs):
                Path(command[-1]).write_text('<broken>')

            with patch.object(animation.subprocess, 'run', side_effect=broken_convert):
                with self.assertRaises(ET.ParseError):
                    animation.export('rig.skeleton', out)
                animation.export('rig.skeleton', out, return_tree=False)
                with self.assertRaises(ET.ParseError):
                    feet.Skel(out / 'rig.skeleton.xml')
            assets = drink.TavernAssets(out)
            with patch.object(animation.subprocess, 'run', side_effect=broken_convert):
                with self.assertRaises(ET.ParseError):
                    assets.skeleton('rig')
            self.assertNotIn('rig', assets.skeletons)
            with patch.object(animation.subprocess, 'run', side_effect=broken_convert):
                with self.assertRaises(ET.ParseError):
                    assets.mesh('broken.mesh')
            self.assertNotIn('broken.mesh', assets.meshes)

    # Nested preparation is counted once and failures keep their original exception and measured phases.
    def test_phase_measurement_and_failure(self):
        # Simulate nested setup without depending on wall-clock scheduling or fixed sleeps.
        @timing.preparation
        def setup():
            return timing.prepare(lambda: 4)

        # Keep the failing assertion visible after setup instrumentation.
        @timing.profile_check
        def check():
            self.assertEqual(setup(), 4)
            raise AssertionError('original failure')

        output = io.StringIO()
        with patch.object(timing.time, 'perf_counter', side_effect=[0, 1, 3, 5]), \
                contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(AssertionError, 'original failure'):
                check()
        phases = [json.loads(line.split(' ', 1)[1]) for line in output.getvalue().splitlines()]
        self.assertEqual(phases, [{'name': 'setup', 'seconds': 2}, {'name': 'test', 'seconds': 3}])
        self.assertIsNone(timing._current.get())


if __name__ == '__main__':
    unittest.main()
