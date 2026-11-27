#!/usr/bin/env python3
"""Check whole-portrait delivery: catalog coverage, JPEGs, perceptual uniqueness, tags and runtime references.

The portraits and config/dungeonbook-quirks.cfg are content (core-portraits and core-config packages, found through
scripts/content_packages.py). Without the content the runtime reference scan of the public tree runs and the portrait
and quirk part is named as not checked.
"""
from pathlib import Path
from itertools import combinations
import re
import sys
import json
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

#: The content folders and table of the portrait and quirk part
CONTENT_PATHS = ('materials/portraits/whole', 'materials/portraits/neutral-bases', 'config/dungeonbook-quirks.cfg')
missing_content = [name for name in CONTENT_PATHS if content_packages.data_file(ROOT, name) is None]
WHOLE = content_packages.resolve(ROOT, 'materials/portraits/whole')
errors = []
near_duplicates = {}


# Report a failed requirement while allowing the other catalogs to be checked.
def fail(message):
    errors.append(message)


# Compare the 64 horizontal luminance gradients used by the standard difference hash.
def difference_hash(image):
    pixels = list(image.convert('L').resize((9, 8), Image.Resampling.LANCZOS).getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return value


expected_total = 3200
total = 0
if not missing_content:
    portrait_started = time.perf_counter()
    decode_seconds = 0.0
    catalogs = sorted(path.stem for path in content_packages.data_glob(ROOT, 'materials/portraits/neutral-bases', '*.png')
                      if '.original-' not in path.name)
    if len(catalogs) != 34:
        fail('Expected 34 canonical neutral-base catalogs; found %d' % len(catalogs))
    actual = {path.name for path in WHOLE.iterdir() if path.is_dir()} if WHOLE.exists() else set()
    if actual != set(catalogs):
        fail('Catalog folders differ: missing=%s extra=%s' % (sorted(set(catalogs) - actual), sorted(actual - set(catalogs))))
    hidden_face_catalogs = {'Knight.mesh', 'Knight.mesh-female', 'Cultist.mesh', 'Cultist.mesh-female'}
    all_tags = set()
    for catalog in catalogs:
        folder = WHOLE / catalog
        index = folder / 'index.cfg'
        if not index.is_file():
            fail(catalog + ': missing index.cfg')
            continue
        expected_count = 50 if catalog in hidden_face_catalogs else 100
        shade_choices = set()
        rows = []
        for line_number, line in enumerate(index.read_text(encoding='utf-8').splitlines(), 1):
            if not line or line.startswith('#'):
                continue
            columns = line.split('\t')
            if (len(columns) != 3 or not columns[0].isdigit()
                    or not re.fullmatch(r'[a-z0-9-]+(?:,[a-z0-9-]+)*', columns[2])):
                fail('%s/index.cfg:%d: malformed row' % (catalog, line_number))
                continue
            number, filename, tags = int(columns[0]), columns[1], columns[2].split(',')
            if filename != '%02d.jpg' % number or len(tags) != len(set(tags)):
                fail('%s/index.cfg:%d: invalid filename or duplicate tags' % (catalog, line_number))
            rows.append((number, filename))
            all_tags.update(tags)
            if number > 50:
                skin_tags = tuple(sorted(tag for tag in tags if tag.startswith('skin-')))
                if not skin_tags or skin_tags in shade_choices:
                    fail('%s/index.cfg:%d: missing or repeated skin shade tags' % (catalog, line_number))
                shade_choices.add(skin_tags)
        numbers = [number for number, _ in rows]
        if (len(numbers) != expected_count or len(set(numbers)) != expected_count
                or set(numbers) != set(range(1, expected_count + 1))):
            fail('%s: expected image numbers 1..%d exactly once, found %d rows'
                 % (catalog, expected_count, len(numbers)))
        listed = {filename for _, filename in rows}
        delivered = {path.name for path in folder.iterdir() if path.name != 'index.cfg'}
        if delivered != listed:
            fail('%s: unlisted or missing images %s' % (catalog, sorted(delivered ^ listed)))
        hashes = []
        for number, filename in rows:
            path = folder / filename
            decode_started = time.perf_counter()
            try:
                with Image.open(path) as image:
                    image.load()
                    if image.format != 'JPEG' or image.size != (1024, 1024):
                        fail('%s: expected a 1024x1024 JPEG' % content_packages.relative_path(ROOT, path))
                        continue
                    hashes.append((filename, difference_hash(image)))
                    total += 1
            except (OSError, ValueError) as error:
                fail('%s: %s' % (content_packages.relative_path(ROOT, path), error))
            finally:
                decode_seconds += time.perf_counter() - decode_started
        for (first, a), (second, b) in combinations(hashes, 2):
            distance = (a ^ b).bit_count()
            if distance <= 5:
                near_duplicates.setdefault(catalog, []).append("%s/%s:%d" % (first, second, distance))
                fail('%s: near-identical images %s and %s (64-bit dHash distance %d <= 5)'
                     % (catalog, first, second, distance))

    portrait_seconds = time.perf_counter() - portrait_started
    print('ODP_TEST_PHASE ' + json.dumps({'name': 'jpeg-decode-and-exact-hash', 'seconds': decode_seconds}))
    print('ODP_TEST_PHASE ' + json.dumps({'name': 'catalog-and-uniqueness', 'seconds': portrait_seconds - decode_seconds}))

    keys = set()
    for line_number, line in enumerate(content_packages.read_text(ROOT, 'config/dungeonbook-quirks.cfg').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        columns = line.split('\t')
        if len(columns) != 2 or not columns[1].strip() or columns[0] in keys:
            fail('Quirks line %d: malformed or duplicate tag' % line_number)
            continue
        keys.add(columns[0])
        if columns[0] not in all_tags:
            fail('Quirk tag not present in any image index: ' + columns[0])

else:
    content_packages.unchecked('check_dungeonbook_whole', missing_content)

# Old-save syntax migration retains no runtime part-system dependencies.
obsolete = ('PortraitManifest', 'AppearanceCompose', 'dungeonbook-base-tints', 'dungeonbook-part-tints',
            'dungeonbook-portrait-framing', 'portraits/variants', 'generated-features', 'generated-helmets',
            'generated-outfits', 'helmet-variants', 'neutral-variants')
runtime_started = time.perf_counter()
# Every table of the public tree and of the content packages
runtime = [ROOT / 'CMakeLists.txt', *content_packages.data_glob(ROOT, 'config', '*.cfg')]
runtime += [path for path in (ROOT / 'source').rglob('*') if path.suffix in ('.cpp', '.h', '.txt')]
for path in runtime:
    text = path.read_text(encoding='utf-8', errors='replace')
    for name in obsolete:
        if name in text:
            fail('%s references removed part system: %s' % (content_packages.relative_path(ROOT, path), name))
print('ODP_TEST_PHASE ' + json.dumps({'name': 'runtime-reference-scan', 'seconds': time.perf_counter() - runtime_started}))

for error in errors:
    print('FAIL: ' + error)
for catalog, pairs in sorted(near_duplicates.items()):
    print('NEAR-DUPLICATES %s: %s' % (catalog, ', '.join(pairs)))
print('Whole portraits: %d / %d valid JPEG files; %d errors. Head/headgear containment and skin shade differences also require individual visual review.'
      % (total, expected_total, len(errors)))
sys.exit(1 if errors else 0)
