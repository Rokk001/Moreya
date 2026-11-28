"""Static check: every filled slot of the Dungeonbook inventory page shows the item tooltip on hover (decision 863,
finding 3). No game and no compiler needed.

On the book page a slot is a framed box (InventoryPage/SlotBoxN, OD/StaticText) with the item picture (SlotN) in its
middle and the slot name (Label) below. Creature::fillItemSlotWindows sets the item tooltip (item->describe) on the
picture only, which covers about a third of the box, and the label passes the mouse to the box, so hovering the frame or
the name showed nothing. Checked here:
1. CEGUI hit testing (deepest visible, non pass-through window under the mouse, later siblings first): the picture is a
   hit target, its overlays (SlotType, QualityFrame, Lock) and the label pass the mouse on, the box is the hit target
   around the picture, and no later window of the page, the header or the navigation bar lies over a slot box.
2. refreshInventory copies the tooltip of every picture to its box right after fillItemSlotWindows, so the whole box
   shows the item values (or the lock text of a locked potion slot) and an empty slot shows nothing.
3. fillItemSlotWindows still sets the item tooltip (Gui::setItemTooltip) on the picture and leaves the parents of the
   slots alone (the shared profile page with its own slots was deleted, owner decision 2026-11-18).
The book layout lies in the content package core-gui (scripts/content_packages.py); without the content part 1 is
named as not checked and parts 2 and 3 still run.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
# The book layout of the content package core-gui (None without the content)
book = (ET.fromstring(content_packages.read_text(repo, 'gui/WindowSocial.layout', None)).find('Window')
        if content_packages.has_content(repo) else None)
social = (repo / 'source/render/SocialWindow.cpp').read_text()
creature = (repo / 'source/entities/Creature.cpp').read_text()

SLOTS = 13


def props(element):
    return {p.get('name'): p.get('value') for p in element.findall('Property')}


def area(element, box):
    dims = [float(a) for a, _ in re.findall(r'\{(-?[0-9.]+),(-?[0-9.]+)\}', props(element)['Area'])]
    width, height = box[2] - box[0], box[3] - box[1]
    return (box[0] + dims[0] * width, box[1] + dims[1] * height, box[0] + dims[2] * width, box[1] + dims[3] * height)


def child(element, name):
    found = [c for c in element.findall('Window') if c.get('name') == name]
    assert len(found) == 1, name
    return found[0]


def passes(element):
    return props(element).get('MousePassThroughEnabled') == 'True'


def overlaps(a, b):
    return a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9


def function_of(text, signature):
    body = text[text.index(signature):]
    return body[:body.index('\n}\n')]


# showPage shows one page of a creature at a time
show_page = function_of(social, 'void SocialWindow::showPage(Page page)')
assert '"InventoryPage", "SkillsPage"};' in show_page and 'Page::Inventory, Page::Skills};' in show_page and \
    'mWindow->getChild(pageNames[i])->setVisible(pages[i] == page);' in show_page, \
    'showPage shows the inventory page and the Skills page never at the same time'

# 1. Hit testing of the inventory page
if book is None:
    content_packages.unchecked('check_dungeonbook_inventory_tooltips', ['gui/WindowSocial.layout inventory page'])
else:
    client = (0.0, 0.0, 1.0, 1.0)
    top = book.findall('Window')
    names = [w.get('name') for w in top]
    # Pages of one creature that showPage shows one at a time: each is visible only while it is the shown page
    SHOWN_ALONE = ('SkillsPage',)
    assert all(props(child(book, name)).get('Visible') == 'False' for name in SHOWN_ALONE)
    page = child(book, 'InventoryPage')
    page_box = area(page, client)
    page_children = page.findall('Window')
    for i in range(SLOTS):
        box_window = child(page, 'SlotBox%d' % i)
        assert not passes(box_window), 'SlotBox%d must be the hit target around its picture' % i
        box = area(box_window, page_box)
        picture = child(box_window, 'Slot%d' % i)
        assert not passes(picture) and props(picture).get('Visible') != 'False', 'Slot%d must be hit' % i
        for overlay in picture.findall('Window'):
            assert passes(overlay), 'Slot%d/%s lies over the picture and must pass the mouse on' % (i, overlay.get('name'))
        label = child(box_window, 'Label')
        assert passes(label), 'SlotBox%d/Label must pass the mouse to the box' % i
        picture_box = area(picture, box)
        share = ((picture_box[2] - picture_box[0]) * (picture_box[3] - picture_box[1])) / ((box[2] - box[0]) * (box[3] - box[1]))
        assert share < 1.0, 'the picture covers only part of the box, so the box needs the tooltip too'
        # Later siblings are drawn and hit first
        for later in page_children[page_children.index(box_window) + 1:]:
            if not passes(later) and props(later).get('Visible') != 'False':
                assert not overlaps(area(later, page_box), box), '%s lies over SlotBox%d' % (later.get('name'), i)
        # Header and navigation bar come after the pages in the book. The Skills page (INGAME-QS-12 K7) follows the
        # inventory page but is hidden whenever the inventory page is shown (showPage shows exactly one page, below)
        for name in names[names.index('InventoryPage') + 1:]:
            sibling = child(book, name)
            if name in SHOWN_ALONE:
                continue
            if not passes(sibling):
                assert not overlaps(area(sibling, client), box), '%s lies over SlotBox%d' % (name, i)

# 2. The box repeats the tooltip of its picture
inventory = function_of(social, 'void SocialWindow::refreshInventory(')
fill_at = inventory.index('Creature::fillItemSlotWindows(creature, slots, true);')
copy = 'Gui::copyTooltip(slot, slot->getParent());'
assert copy in inventory and inventory.index(copy) > fill_at, 'the slot boxes take the tooltip after the slots are filled'
# every slot box, after an empty slot got its own name as hover text (no picture of the book without interaction)
assert re.search(r'for\(CEGUI::Window\* slot : slots\)\s*\n\s*\{\s*\n\s*if\(slot->getTooltipText\(\)\.empty\(\)\)\s*\n'
                 r'[^\n]*Gui::setPlainTooltip\(slot, trWith\("ui\.dungeonbook\.inventory\.empty", "slot",[^;]*\);\s*\n\s*' +
                 re.escape(copy) + r'\s*\n\s*\}', inventory), \
    'every slot box'
assert '"SlotBox" + std::to_string(slot) + "/Slot" + std::to_string(slot)' in inventory, 'the picture is a child of its box'

# 3. The shared fill
fill = function_of(creature, 'void Creature::fillItemSlotWindows(')
assert 'Gui::setItemTooltip(image, *item, creature->getGameMap(), heldWeapon);' in fill
assert 'Gui::setPlainTooltip(image, Translation::tr("ui.profile.potionlocked", lockValues));' in fill
assert 'getParent()' not in fill, 'the shared fill does not touch the parents of the slots'
assert 'fillItemSlotWindows(this, slotWindows, false);' not in creature, 'the shared profile page is deleted'

print('dungeonbook inventory tooltips: %d slot boxes show the item tooltip of their picture' % SLOTS)
