"""Check the fixed room manager artwork inventory, native sizes, asset credits and the real painted detail of the room icons."""

from pathlib import Path
import re
import sys

from PIL import Image, ImageChops, ImageStat


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ASSETS = 31
ICONS = (
    'alchemy-lab', 'arena', 'casino', 'crypt', 'dormitory', 'ghost-room',
    'guard-room', 'hatchery', 'herb-garden', 'infirmary', 'library', 'merchant',
    'prayer-temple', 'prison', 'spa', 'stone-bridge', 'tavern', 'temple',
    'toilet', 'torture-chamber', 'training-hall', 'treasury', 'wooden-bridge',
    'workshop',
)
ARTWORK = (
    ('spa-bath.png', (118, 118)),
    ('ghost-mana-crystal.png', (52, 45)),
    ('ghost-research-book.png', (39, 33)),
    ('ghost-level-crystal.png', (38, 40)),
    ('ghost-vessel.png', (173, 233)),
    ('casino-smiles.png', (128, 110)),
    ('casino-money.png', (128, 110)),
)
# Effective detail of a 256x256 room icon. A Lanczos round trip through 128x128 removes every detail finer than
# 128 pixels; the RMS of what it removes (grey levels 0-255) measures that fine detail. Hand-painted 256x256 icons
# (the build icons of ODIcons.png and the repainted room icons) measure 8.3 to 15.4; smooth (bilinear, bicubic or
# Lanczos) upscales from 128x128 or less measure at most 3.5.
DETAIL_SIZE = 128
MIN_DETAIL_RMS = 5.0
# Share of neighbouring pixel pairs with exactly the same colour. Painted icons measure at most 0.03; nearest-neighbour
# upscales from 128x128 or less measure 0.50 or more.
MAX_EQUAL_NEIGHBOURS = 0.25
# Sizes an upscaled control copy is reduced to before it is enlarged again; the detail check must reject every copy.
CONTROL_SIZES = (48, 64, 96, 128)


def check_asset(relative, size, credits):
    """Require a readable image at its fixed size and its own complete credit row."""
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError('missing ' + relative)
    with Image.open(path) as picture:
        assert picture.format == 'PNG', relative + ': PNG format'
        assert picture.size == size, '%s: expected %s, got %s' % (relative, size, picture.size)
        picture.load()
    rows = [row for row in credits if row.split() and row.split()[0] == relative]
    assert len(rows) == 1, relative + ': exactly one CREDITS row'
    assert re.fullmatch(
        re.escape(relative) + r'\s+AI-generated with Codex\s+GPLv3\+\s+'
        r'Painted for this project \(\d{4}-\d{2}-\d{2}\)', rows[0]
    ), relative + ': author, licence and source'


def fine_detail_rms(picture):
    """Return the grey-level RMS of the detail finer than DETAIL_SIZE pixels in a 256x256 picture."""
    picture = picture.convert('RGB')
    smooth = picture.resize((DETAIL_SIZE, DETAIL_SIZE), Image.LANCZOS).resize(picture.size, Image.LANCZOS)
    return ImageStat.Stat(ImageChops.difference(picture.convert('L'), smooth.convert('L'))).rms[0]


def equal_neighbour_share(picture):
    """Return the share of horizontally or vertically neighbouring pixel pairs that have exactly the same colour."""
    picture = picture.convert('RGB')
    width, height = picture.size
    equal = 0
    pairs = 0
    for first, second in ((picture.crop((1, 0, width, height)), picture.crop((0, 0, width - 1, height))),
                          (picture.crop((0, 1, width, height)), picture.crop((0, 0, width, height - 1)))):
        red, green, blue = ImageChops.difference(first, second).split()
        largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        equal += largest.histogram()[0]
        pairs += largest.size[0] * largest.size[1]
    return float(equal) / pairs


def detail_failure(picture):
    """Return why a 256x256 icon holds less real detail than a painted icon, or None when its detail is full."""
    rms = fine_detail_rms(picture)
    share = equal_neighbour_share(picture)
    if rms < MIN_DETAIL_RMS:
        return 'fine detail RMS %.2f below %.2f (upscaled or blurred)' % (rms, MIN_DETAIL_RMS)
    if share > MAX_EQUAL_NEIGHBOURS:
        return 'equal neighbour share %.3f above %.2f (pixel blocks)' % (share, MAX_EQUAL_NEIGHBOURS)
    return None


def check_icon_detail(relative):
    """Require full painted detail in a room icon and prove that the measure rejects upscaled copies of it."""
    with Image.open(ROOT / relative) as picture:
        picture = picture.convert('RGB')
    failure = detail_failure(picture)
    assert failure is None, relative + ': ' + str(failure)
    for size in CONTROL_SIZES:
        small = picture.resize((size, size), Image.LANCZOS)
        for method in (Image.NEAREST, Image.BILINEAR, Image.BICUBIC, Image.LANCZOS):
            control = small.resize(picture.size, method)
            assert detail_failure(control) is not None,                 '%s: detail measure accepts a copy upscaled from %dx%d' % (relative, size, size)
    print('PASS detail %s rms=%.2f equal=%.3f' % (relative, fine_detail_rms(picture), equal_neighbour_share(picture)))


def main():
    """Check all 31 required files without hiding missing artwork behind passing icons."""
    credits = (ROOT / 'CREDITS').read_text(encoding='utf-8').splitlines()
    inventory = [('gui/RoomCentreIcons/' + name + '.png', (256, 256)) for name in ICONS]
    inventory.extend(('gui/RoomCentreArtwork/' + name, size) for name, size in ARTWORK)
    assert len(inventory) == EXPECTED_ASSETS, 'complete fixed artwork inventory'
    failed = 0
    for relative, size in inventory:
        try:
            check_asset(relative, size, credits)
            print('PASS ' + relative)
            if relative.startswith('gui/RoomCentreIcons/'):
                check_icon_detail(relative)
        except (AssertionError, OSError) as error:
            print('FAIL ' + str(error))
            failed += 1
    print('DONE total=%d red=%d' % (EXPECTED_ASSETS, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
