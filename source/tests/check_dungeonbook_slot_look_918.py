"""Static check: filled and empty Dungeonbook slots differ at a glance (owner decision 918). No game and no compiler
needed.

A filled slot shows the picture of its own item in full colour inside the frame of its quality (Poor grey, Common white,
Rare blue, Epic purple, config/items.cfg); an empty slot shows the placeholder with the slot symbol clearly dimmed.
Checked here:
1. Creature::fillItemSlotWindows (the book calls it with showLocks) colours an empty slot with EMPTY_ITEM_SLOT_COLOURS,
   at most half opaque, a filled one opaque white, a locked potion slot keeps its grey under the lock; the picture is
   the item picture and the quality frame is shown only for a filled slot.
2. The four quality frames exist in gui/ODIcons.imageset and config/items.cfg names their colours; with Pillow present
   the frame pictures are measured: Poor and Common grey to white, Rare blue, Epic purple.
3. Every inventory slot of the book has the picture, the symbol and the quality frame windows.

config/items.cfg and the book layout are content (core-config and core-gui packages), the icon atlas lies whole in a
content package (all found through scripts/content_packages.py); without them the code is checked and the colour note
of items.cfg, the slot windows of the book and the quality frames are named as not checked.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

creature = (repo / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
social = (repo / 'source/render/SocialWindow.cpp').read_text(encoding='utf-8')
missing_content = content_packages.unchecked('check_dungeonbook_slot_look_918', [
    name for name in ('config/items.cfg', 'gui/WindowSocial.layout') if content_packages.data_file(repo, name) is None])
items_cfg = None if missing_content else content_packages.read_text(repo, 'config/items.cfg')
# gui/ODIcons.imageset as the game reads it: it lies whole in a content package (None without the content: the
# quality frames are then named as not checked)
imageset = content_packages.read_text(repo, 'gui/ODIcons.imageset') if content_packages.data_file(repo, 'gui/ODIcons.imageset') else None
book = None if missing_content else ET.fromstring(content_packages.read_text(repo, 'gui/WindowSocial.layout')).find('Window')


def function_of(text, signature):
    body = text[text.index(signature):]
    return body[:body.index('\n}\n')]


# 1. The colours of the slots
match = re.search(r'static const char\* const EMPTY_ITEM_SLOT_COLOURS = "([^"]+)";', creature)
assert match, 'the dimmed colour of an empty slot is a named constant'
colours = re.findall(r'(tl|tr|bl|br):([0-9A-F]{8})', match.group(1))
assert [c[0] for c in colours] == ['tl', 'tr', 'bl', 'br'] and len({c[1] for c in colours}) == 1
alpha = int(colours[0][1][:2], 16)
grey = max(int(colours[0][1][i:i + 2], 16) for i in (2, 4, 6))
assert alpha <= 0x80, 'an empty slot is clearly dimmed (at most half opaque)'
assert grey < 0xFF, 'and greyed'
fill = function_of(creature, 'void Creature::fillItemSlotWindows(')
assert re.search(r'const char\* const colours = locked \? "tl:FF606060 tr:FF606060 bl:FF606060 br:FF606060" :\s*'
                 r'\(item == nullptr \? EMPTY_ITEM_SLOT_COLOURS : "tl:FFFFFFFF tr:FFFFFFFF bl:FFFFFFFF br:FFFFFFFF"\);',
                 fill), 'empty dimmed, filled in full colour, locked grey'
assert 'image->setProperty("ImageColours", colours);' in fill and 'slotType->setProperty("ImageColours", colours);' in fill
assert fill.index('if(!showLocks)') < fill.index('image->setProperty("ImageColours", colours);'), \
    'only the book (showLocks) changes the colours; the creature card keeps its look'
assert '"ItemImages/" + item->getImageName(heldWeapon)' in fill and 'slotType->setVisible(item == nullptr);' in fill
assert 'frame->setVisible(item != nullptr);' in fill
assert 'frame->setProperty("Image", "OpenDungeonsIcons/ItemFrame" + qualityName(item->mQuality));' in fill
assert 'Creature::fillItemSlotWindows(creature, slots, true);' in function_of(social, 'void SocialWindow::refreshInventory(')

# 2. The quality frames (the icon atlas lies in a content package)
if imageset is None or content_packages.data_file(repo, 'gui/ODIcons.png') is None:
    content_packages.unchecked('check_dungeonbook_slot_look_918', ['gui/ODIcons.imageset', 'gui/ODIcons.png'])
    imageset = None
if items_cfg is not None:
    assert 'Quality colours: Poor grey, Common white, Rare blue, Epic purple' in items_cfg
if imageset is not None:
    frames = {}
    for quality in ('Poor', 'Common', 'Rare', 'Epic'):
        found = re.search(r'<Image height="(\d+)" name="ItemFrame%s" width="(\d+)" xPos="(\d+)" yPos="(\d+)" />' % quality,
                          imageset)
        assert found, 'ItemFrame' + quality
        frames[quality] = tuple(int(v) for v in found.groups())
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        atlas = Image.open(content_packages.resolve(repo, 'gui/ODIcons.png')).convert('RGBA')
        average = {}
        for quality, (height, width, x, y) in frames.items():
            pixels = [p for p in atlas.crop((x, y, x + width, y + height)).getdata() if p[3] > 200 and max(p[:3]) > 80]
            assert pixels, quality
            average[quality] = tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))
        for quality in ('Poor', 'Common'):
            r, g, b = average[quality]
            assert max(r, g, b) - min(r, g, b) < 25, quality + ' frame is grey to white'
        assert average['Common'][0] > average['Poor'][0], 'Common is lighter than Poor'
        r, g, b = average['Rare']
        assert b > r + 40 and b > g + 30, 'Rare frame is blue'
        r, g, b = average['Epic']
        assert b > g + 30 and r > g + 20, 'Epic frame is purple'

# 3. The slot windows of the book
if book is not None:
    page = [w for w in book.findall('Window') if w.get('name') == 'InventoryPage'][0]
    for slot in range(13):
        box = [w for w in page.findall('Window') if w.get('name') == 'SlotBox%d' % slot][0]
        picture = [w for w in box.findall('Window') if w.get('name') == 'Slot%d' % slot][0]
        names = [w.get('name') for w in picture.findall('Window')]
        assert 'SlotType' in names and 'QualityFrame' in names, slot

print('check_dungeonbook_slot_look_918: OK')
