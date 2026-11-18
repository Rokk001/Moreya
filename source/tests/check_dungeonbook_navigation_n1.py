"""Check Dungeonbook navigation wiring and the six existing visual asset blobs."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
source = (repo / 'source/render/SocialWindow.cpp').read_text(encoding='utf-8')
book = ET.parse(repo / 'gui/WindowSocial.layout').getroot().find('Window')
home = book.find("Window[@name='HomePage']")
assert home.find("Window[@name='Filter']").get('type') == 'OD/Combobox'
assert home.find("Window[@name='Filter']/Property[@name='ReadOnly']").get('value') == 'True'
assert all(label in source for label in ('"All", "Workers", "Fighters", "Unhappy"',))

def body(signature):
    return source.split(signature, 1)[1].split('\n}', 1)[0]

assert 'mFilter = CreatureFilter::All' in body('void SocialWindow::show()')
for signature in ('void SocialWindow::show()', 'void SocialWindow::showCreature(',
                  'void SocialWindow::selectCreature('):
    assert 'setItemSelectState(static_cast<std::size_t>(0), true)' in body(signature), signature
assert 'Page::Inventory' in body('void SocialWindow::showCreature(')
assert 'Page::Inventory' in body('bool SocialWindow::onListRowClicked(')
assert 'Page::Inventory' in body('bool SocialWindow::onLinkClicked(')
assert 'mSelectedCreature.clear()' in body('bool SocialWindow::onFilterClicked(')
assert 'showPage(Page::Home)' in body('bool SocialWindow::onFilterClicked(')
# The pages of one creature replace the start page; the creature list is hidden while they are shown (plan
# INGAME-QS-11 K3, book-switch-variant-1)
assert 'mWindow->getChild("HomePage")->setVisible(page == Page::Home);' in body('void SocialWindow::showPage(')
assert 'setVisible(page != Page::Home)' in body('void SocialWindow::showPage(')
assert 'if(!all && (it->mCreature != mSelectedCreature))' in body('void SocialWindow::rebuildFeed()')
for name in ('NavFeed', 'NavProfile', 'NavValues', 'NavInventory', 'NavSkills'):
    assert book.find("Window[@name='NavBar']/Window[@name='%s']" % name) is not None
# A post of the start page opens its creature; the feed of one creature holds no button (plan INGAME-QS-11 K4)
for row in range(3):
    assert book.find("Window[@name='HomePage']/Window[@name='FeedRows']/Window[@name='Row%d']/Window[@name='ProfileLink']" % row) is not None
    assert book.find("Window[@name='FeedPage']/Window[@name='FeedRows']/Window[@name='Row%d']/Window[@name='ProfileLink']" % row) is None


def rectangle(window):
    """Read the layout's relative rectangle for arrangement assertions."""
    value = window.find("Property[@name='Area']").get('value')
    return tuple(float(n) for n in re.findall(r'\{([0-9.]+),0\}', value))


label = rectangle(home.find("Window[@name='CreaturesLabel']"))
dropdown = rectangle(home.find("Window[@name='Filter']"))
assert label[2] == dropdown[0] and label[1] <= dropdown[1] < label[3]
list_left = rectangle(home.find("Window[@name='ListPanel']"))[0]
feed_right = rectangle(home.find("Window[@name='FeedPanel']"))[2]
nav = book.find("Window[@name='NavBar']")
assert nav.find("Property[@name='Visible']").get('value') == 'False'
nav_box = rectangle(nav)
for name in ('FeedPage', 'ProfilePage', 'ValuesPage', 'InventoryPage'):
    page_box = rectangle(book.find("Window[@name='%s']" % name))
    # The page of one creature takes the whole width the list and the feed of the start page share
    assert page_box[0] <= list_left + 0.01 and page_box[2] >= feed_right - 0.01 and page_box[3] <= nav_box[1]
    assert (page_box[0], page_box[2]) == (nav_box[0], nav_box[2])

styles = []


def collect_styles(window, path=''):
    """Pin all 877 existing image, font, background and frame properties, excluding replaced filter buttons.

    787 before the window got the frame of the menu sheet: the 15 properties of the ornate book frame and its title
    band (TitlebarFont, Frame*Image, Title*Image on the window and its title bar) are gone, every page style is kept.
    772 before plan INGAME-QS-11 B1 built the pages of one creature as book-variant-2: 27 properties went (the social
    holder, info and keeper texts of the profile, the MedievalSharp-6 slot names, the back arrow of the head) and 78
    came (the rows, rules and post frames of the profile, the MedievalSharp-8 slot names, the MedievalSharp-12 name of
    the head, the back arrow in the title bar and the Skills button of the navigation bar), 21 more for the keeper
    mark of the seven list entries (INGAME-QS-7 U-2, Font and no background or frame), 6 more when the flat rule bars
    became the painted iron rule of the book (BookTitleRule, BookFrameLeft) and the values panels and tiles got the
    rust frame, 27 more for the nine social lines of the profile (owner decision 2026-11-18: likes, dislikes,
    friends, foe, status, three buff and debuff lines, remarks; Font, no background or frame).
    """
    path += '/' + window.get('name', '')
    if window.get('name', '').startswith('Filter'):
        return
    for prop in window.findall('Property'):
        name = prop.get('name')
        if name in ('Font', 'Image', 'BackgroundEnabled', 'BackgroundColours', 'FrameEnabled', 'FrameColours',
                    'TitlebarFont') or name.startswith('Frame') or name.startswith('Title'):
            styles.append((path, name, prop.get('value')))
    for child in window.findall('Window') + window.findall('AutoWindow'):
        collect_styles(child, path)


collect_styles(book)
assert len(styles) == 877
assert hashlib.sha256(json.dumps(styles, separators=(',', ':')).encode()).hexdigest() == \
    '5339f5b2640405b50e49a9cb120f8fa9df750db5e3f66af0a252c1a99fc686f0'

expected = {
    'DungeonbookIcons.png': '1f8c0171d312b6a7c432eb9640cd754089ace73f',
    'DungeonbookIcons.imageset': '917403f14a5141d3596a8ce695644c9a73930ddb',
    'DungeonbookFrame.png': '063c2b8218920147fc09e48895625fd1ef8b4588',
    'DungeonbookFrame.imageset': 'a3849a2059181573d6bfa587858c10598de4f8d6',
    'DungeonbookPage.png': 'b0486c52b0fe410979301f20636dd3fb03a36bce',
    'DungeonbookPage.imageset': 'c1003912e3e5c1037805e6ef1311d527eef393d1',
}
for name, digest in expected.items():
    data = (repo / 'gui' / name).read_bytes()
    if name.endswith('.imageset'):
        data = data.replace(b'\r\n', b'\n')
    assert hashlib.sha1(('blob %d\0' % len(data)).encode() + data).hexdigest() == digest, name
print('Dungeonbook navigation wiring and six visual assets: OK')
