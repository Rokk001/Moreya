"""Check the Room Manager and Dungeonbook icons above the minimap (INGAME-QS-10 K12b, T-N2).

The two HUD buttons must draw the chosen painted icons at full resolution: each button names an image whose
imageset is registered in the scheme and whose picture resolves in exactly one GUI resource folder, the pixels the
game loads are the chosen artwork, they carry real painted detail at 256 px (not an upscaled small picture), the motif
fills the button, and at the size the button is drawn they look clearly different from the Rooms tab icon
(NavigationRooms), the creature portrait (CreaturesIcon), each other and their neighbours in the row.
"""
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
# ODP_ASSETS_SRC (else <repo>/assets-src) holds the asset sources, see scripts/assets_src.py
sys.path.insert(0, str(ROOT / 'scripts'))
from assets_src import assets_src_dir  # noqa: E402

# Button name -> (image the button shows, chosen 1024 px artwork below <assets>/gui/navigation-icons).
BUTTONS = {
    'RoomManagerButton': ('NavigationRoomManager/Icon', 'NavigationRoomManager-1024.png'),
    'SocialButton': ('NavigationDungeonbook/Icon', 'NavigationDungeonbook-1024.png'),
}
# Images the new icons must not resemble: the old images of the two buttons and the other icons of the row.
FORBIDDEN = ('NavigationRooms', 'CreaturesIcon')
NEIGHBOURS = ('GoalsButton', 'ResearchButton', 'WorkersButton', 'SandboxButton')
FULL_SIZE = 256
# Mean RGB loss on opaque pixels when a picture is reduced to half size and enlarged again. Painted 256 px icons of the
# row lose 7 to 13 levels; a picture enlarged from 128 px or less loses about 1.
MIN_HALF_SIZE_DETAIL = 6.0
# Mean RGBA difference at the drawn button size. Different motifs of the row differ by 50 or more levels.
MIN_DIFFERENCE = 25.0
DESIGN_W, DESIGN_H, BUTTON = 1024.0, 768.0, 40.0


def props(node):
    """Return the properties of a layout window as a dictionary."""
    return {p.get('name'): p.get('value') for p in node.findall('Property')}


def gui_folders():
    """Return the folders the game registers non-recursively in its [GUI] resource group."""
    text = (ROOT / 'cmake/config/resources.cfg.in').read_text(encoding='utf-8')
    section = text.split('[GUI]', 1)[1].split('[', 1)[0]
    return [ROOT / line.split('=', 1)[1].strip() for line in section.splitlines() if line.startswith('FileSystem=')]


def load_image(reference, imagesets, folders):
    """Resolve 'Imageset/Image' the way CEGUI does and return the RGBA pixels of that image."""
    imageset_name, image_name = reference.split('/', 1)
    assert imageset_name in imagesets, reference + ': imageset registered in ODSkin.scheme'
    root = ET.parse(ROOT / 'gui' / imagesets[imageset_name]).getroot()
    assert root.get('name') == imageset_name, reference + ': imageset name matches the scheme'
    filename = root.get('imagefile')
    hits = [folder / filename for folder in folders if (folder / filename).is_file()]
    assert len(hits) == 1, '%s: %s resolves in exactly one GUI folder, found %d' % (reference, filename, len(hits))
    node = root.find("Image[@name='%s']" % image_name)
    assert node is not None, reference + ': image defined'
    x, y, w, h = (int(node.get(key)) for key in ('xPos', 'yPos', 'width', 'height'))
    with Image.open(hits[0]) as picture:
        sheet = picture.convert('RGBA')
    assert 0 <= x and 0 <= y and x + w <= sheet.width and y + h <= sheet.height, reference + ': image inside its picture'
    return sheet.crop((x, y, x + w, y + h))


def fit_artwork(path):
    """Crop the chosen artwork to its painted body and fit it into a 256 px square with the margin of the N1 sheets."""
    with Image.open(path) as picture:
        art = picture.convert('RGBA')
    art = art.crop(art.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox())
    side = int(max(art.size) / 0.94)
    square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    square.alpha_composite(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square.resize((FULL_SIZE, FULL_SIZE), Image.LANCZOS)


def half_size_detail(picture):
    """Mean RGB loss on opaque pixels after reducing the picture to half size and enlarging it again."""
    original = np.array(picture, dtype=np.float32)
    half = (picture.width // 2, picture.height // 2)
    blurred = np.array(picture.resize(half, Image.LANCZOS).resize(picture.size, Image.LANCZOS), dtype=np.float32)
    opaque = original[..., 3] > 200
    return float(np.abs(original[..., :3] - blurred[..., :3])[opaque].mean())


def difference(first, second, size):
    """Mean RGBA difference of two icons drawn at the same button size."""
    a = np.array(first.resize((size, size), Image.LANCZOS), dtype=np.float32)
    b = np.array(second.resize((size, size), Image.LANCZOS), dtype=np.float32)
    return float(np.abs(a - b).mean())


def drawn_sizes():
    """Button sizes in pixels from 640x480 to 8K at UI scale 80 to 120 percent (Gui::getLayoutScale)."""
    sizes = set()
    for width, height in ((640, 480), (1024, 768), (1920, 1080), (1920, 1200), (3840, 2160), (7680, 4320)):
        for user in (0.8, 1.0, 1.2):
            sizes.add(int(round(BUTTON * min(width / DESIGN_W, height / DESIGN_H) * user)))
    return sorted(sizes)


def main():
    """Run every T-N2 assertion and print one line per result."""
    start = time.monotonic()
    scheme = ET.parse(ROOT / 'gui/ODSkin.scheme').getroot()
    imagesets = {node.get('name'): node.get('filename') for node in scheme.findall('Imageset')}
    folders = gui_folders()
    hud = ET.parse(ROOT / 'gui/ModeGame.layout').getroot()
    windows = {node.get('name'): node for node in hud.iter('Window')}
    forbidden = {name: load_image('OpenDungeonsIcons/' + name, imagesets, folders) for name in FORBIDDEN}
    neighbours = {name: load_image(props(windows[name])['NormalImage'], imagesets, folders) for name in NEIGHBOURS}
    sizes = drawn_sizes()
    assert sizes[0] <= 25 and sizes[-1] >= 260, sizes
    icons = {}
    for button, (reference, artwork) in BUTTONS.items():
        p = props(windows[button])
        assert windows[button].get('type') == 'OD/GameTabButton' and p['NavigationFrame'] == 'True', button
        assert p['NormalImage'] == reference, '%s shows %s' % (button, p['NormalImage'])
        icon = load_image(reference, imagesets, folders)
        assert icon.size == (FULL_SIZE, FULL_SIZE), '%s: %s is %dx%d, not full resolution' % ((button, reference) + icon.size)
        chosen = np.array(fit_artwork(assets_src_dir(ROOT) / 'gui/navigation-icons' / artwork), dtype=np.int16)
        assert np.abs(np.array(icon, dtype=np.int16) - chosen).max() <= 1, button + ': pixels are the chosen artwork'
        detail = half_size_detail(icon)
        assert detail >= MIN_HALF_SIZE_DETAIL, '%s: only %.2f levels of detail at full size (upscaled?)' % (button, detail)
        alpha = np.array(icon.getchannel('A'))
        left, top, right, bottom = Image.fromarray(alpha).point(lambda v: 255 if v > 24 else 0).getbbox()
        assert max(right - left, bottom - top) >= FULL_SIZE * 0.9, button + ': the motif fills the button'
        assert (alpha > 200).mean() > 0.4, button + ': painted body, not a thin sketch'
        for size in sizes:
            for name, other in list(forbidden.items()) + list(neighbours.items()):
                d = difference(icon, other, size)
                assert d >= MIN_DIFFERENCE, '%s looks like %s at %d px (%.1f)' % (button, name, size, d)
        icons[button] = icon
        print('PASS %s -> %s: 256 px, detail %.2f, min difference %.1f at %s px' % (
            button, reference, detail,
            min(difference(icon, other, s) for s in sizes for other in list(forbidden.values()) + list(neighbours.values())),
            sizes))
    for size in sizes:
        d = difference(icons['RoomManagerButton'], icons['SocialButton'], size)
        assert d >= MIN_DIFFERENCE, 'Room Manager and Dungeonbook icons look alike at %d px (%.1f)' % (size, d)
    # The Rooms tab keeps its own icon; only the HUD button changed.
    tab = (ROOT / 'gui/WindowTabRooms.layout').read_text(encoding='utf-8')
    assert re.search(r'name="NavigationImage" value="OpenDungeonsIcons/NavigationRooms"', tab), 'Rooms tab icon unchanged'
    print('ODP_TEST_PHASE {"name":"test","seconds":%.3f}' % (time.monotonic() - start))
    print('ok: Room Manager and Dungeonbook buttons show their own full-resolution icons')


if __name__ == '__main__':
    main()
