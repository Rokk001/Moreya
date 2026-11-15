"""Check shared XML preparation against both independent skeleton parsers."""
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

import check_tavern_seat_clips as seat
from check_asset_runtime_equivalence import skeleton_xml


# Both parser representations must retain identical values and independent mutable arrays.
def compare(test, first, second):
    if isinstance(first, np.ndarray):
        np.testing.assert_array_equal(first, second)
        test.assertFalse(np.shares_memory(first, second))
    elif isinstance(first, dict):
        test.assertEqual(first.keys(), second.keys())
        for key in first:
            compare(test, first[key], second[key])
    elif isinstance(first, (list, tuple)):
        test.assertEqual(type(first), type(second))
        test.assertEqual(len(first), len(second))
        for left, right in zip(first, second):
            compare(test, left, right)
    elif hasattr(first, '__dict__'):
        compare(test, vars(first), vars(second))
    else:
        test.assertEqual(first, second)


# Include unused clips and mandatory legacy rotation elements in the synthetic full rig.
def fixture():
    return skeleton_xml().replace('<translate x="0" y="0" z="0"/>',
        '<translate x="0" y="0" z="0"/><rotate angle="0"><axis x="1" y="0" z="0"/></rotate>')


# Opt-in XML sharing must preserve both full parser validation contracts.
class PreparationTests(unittest.TestCase):
    # Unicode parsing must not hide an encoding error caught by the original byte-oriented parser.
    def test_declared_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            text = '<?xml version="1.0" encoding="UTF-16"?>' + fixture()
            # Write actual UTF-8 bytes, including the deliberate encoding mismatch.
            def convert(name, target, return_tree):
                (target / (name + '.xml')).write_text(text, encoding='utf-8')
            with patch.object(seat, 'export', side_effect=convert), \
                    patch.object(seat.seats.rig, 'config', return_value=[]):
                with self.assertRaises(ET.ParseError):
                    seat.SeatAssets(out).skeleton('rig')
            text = ('<?xml version="1.0" encoding="ISO-8859-1"?>' + fixture()).replace('child', 'café')
            with patch.object(seat, 'export', side_effect=convert), \
                    patch.object(seat.seats.rig, 'config', return_value=[]) as config:
                actual = seat.SeatAssets(out).skeleton('rig')
                path = str(out / 'rig.skeleton.xml')
                compare(self, seat.feet.Skel(path), actual)
                compare(self, seat.seats.rig.Skeleton(path), config.call_args.args[1])

    # Conversion and XML syntax failures remain fatal and cannot populate either cache.
    def test_conversion_and_xml_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            assets = seat.SeatAssets(out)
            with patch.object(seat, 'export', side_effect=subprocess.CalledProcessError(7, 'converter')):
                with self.assertRaises(subprocess.CalledProcessError) as failure:
                    assets.skeleton('rig')
                self.assertEqual(failure.exception.returncode, 7)
            self.assertEqual(assets.skeletons, {})
            self.assertEqual(assets.body_rigs, {})
            # An invalid fresh XML document must not reuse a prior successful parse.
            def convert(name, target, return_tree):
                (target / (name + '.xml')).write_text('<skeleton>', encoding='utf-8')
            with patch.object(seat, 'export', side_effect=convert):
                with self.assertRaises(ET.ParseError):
                    assets.skeleton('rig')
            self.assertEqual(assets.skeletons, {})
            self.assertEqual(assets.body_rigs, {})

    # New runs reconvert inputs; within one run both complete parsers share one immutable tree.
    def test_fresh_run_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            # Stand in for serialization only; the two actual parsers still execute.
            def convert(name, target, return_tree):
                (target / (name + '.xml')).write_text(fixture(), encoding='utf-8')
            with patch.object(seat, 'export', side_effect=convert) as export, \
                    patch.object(seat.seats.rig, 'config', return_value=['configured']) as config, \
                    patch.object(seat.ET, 'fromstring', wraps=ET.fromstring) as parse:
                assets = seat.SeatAssets(out)
                first = assets.skeleton('rig')
                self.assertIs(first, assets.skeleton('rig'))
                self.assertEqual(assets.body_rigs['rig'], ['configured'])
                second = seat.SeatAssets(out).skeleton('rig')
                self.assertIsNot(first, second)
                self.assertEqual(export.call_count, 2)
                self.assertEqual(parse.call_count, 2)
                self.assertEqual(config.call_count, 2)

    # A failure unique to the second parser must not publish a partially valid cache entry.
    def test_failed_second_parser_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            text = fixture().replace('<translate x="3" y="1" z="0"/>', '')
            # Missing legacy translation is accepted by Skel but rejected by Skeleton.
            def convert(name, target, return_tree):
                (target / (name + '.xml')).write_text(text, encoding='utf-8')
            assets = seat.SeatAssets(out)
            with patch.object(seat, 'export', side_effect=convert), \
                    patch.object(seat.seats.rig, 'config', return_value=[]):
                with self.assertRaises(AttributeError):
                    assets.skeleton('rig')
                self.assertNotIn('rig', assets.skeletons)
                self.assertNotIn('rig', assets.body_rigs)
                text = fixture()
                self.assertIsNotNone(assets.skeleton('rig'))

    # Every field of both parsers is equal and neither parser mutates the shared XML.
    def test_shared_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rig.xml'
            text = fixture()
            path.write_text(text, encoding='utf-8')
            root = ET.fromstring(text)
            before = ET.tostring(root)
            compare(self, seat.feet.Skel(path), seat.feet.Skel(path, xml_root=root))
            compare(self, seat.seats.rig.Skeleton(path),
                    seat.seats.rig.Skeleton(path, xml_source=(text, root)))
            self.assertEqual(before, ET.tostring(root))

    # Configuration failure also leaves both caches empty and forces a fresh conversion on retry.
    def test_failed_configuration_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            # Serialize valid input so the failure originates only in configuration.
            def convert(name, target, return_tree):
                (target / (name + '.xml')).write_text(fixture(), encoding='utf-8')
            assets = seat.SeatAssets(out)
            with patch.object(seat, 'export', side_effect=convert) as export, \
                    patch.object(seat.seats.rig, 'config', side_effect=[ValueError('configuration'), []]):
                with self.assertRaisesRegex(ValueError, 'configuration'):
                    assets.skeleton('rig')
                self.assertEqual(assets.skeletons, {})
                self.assertEqual(assets.body_rigs, {})
                assets.skeleton('rig')
                self.assertEqual(export.call_count, 2)

    # Bad values or required missing elements in unused clips fail through both preparation routes.
    def test_malformed_unused_clip(self):
        changes = [lambda text: text.replace('name="Unused" length="2"', 'name="Unused" length="bad"'),
                   lambda text: text.replace('x="3" y="1"', 'x="bad" y="1"'),
                   lambda text: text.replace('<rotate angle="0.4">', '<rotate angle="bad">'),
                   lambda text: text.replace('<translate x="3" y="1" z="0"/>', ''),
                   lambda text: text.replace('<rotate angle="0.4"><axis x="0" y="0" z="1"/></rotate>', '')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rig.xml'
            for change in changes:
                text = change(fixture())
                self.assertNotEqual(text, fixture())
                path.write_text(text, encoding='utf-8')
                for parser, keyword in ((seat.feet.Skel, {'xml_root': ET.fromstring(text)}),
                                        (seat.seats.rig.Skeleton, {'xml_source': (text, ET.fromstring(text))})):
                    try:
                        expected = parser(path)
                    except Exception as error:
                        with self.assertRaises(type(error)):
                            parser(path, **keyword)
                    else:
                        compare(self, expected, parser(path, **keyword))


if __name__ == '__main__':
    unittest.main()
